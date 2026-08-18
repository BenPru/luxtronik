"""Diagnostics support for Luxtronik."""

# region Imports
from __future__ import annotations

from asyncio import timeout
from collections.abc import Mapping
from hashlib import sha256
import json
import re
from typing import Any, TypeIs

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import LuxtronikConfigEntry
from .common import async_get_mac_address
from .const import LOGGER
from .coordinator import LuxtronikCoordinator, LuxtronikSerialNumberError
from .log_capture import get_captured_log_records

# endregion Imports

TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_HOST,
    "unique_id",
    "serial_number",
    "identifiers",
    "via_device",
    "configuration_url",
}

# P0874 ID_WP_SerienNummer_DATUM and P0875 ID_WP_SerienNummer_HEX are the two
# halves the serial number is built from (see LuxtronikCoordinator.serial_number),
# so leaving them readable would undo the redaction of every other copy of it.
# P0876 ID_WP_SerienNummer_INDEX is not part of the serial and stays visible.
SERIAL_PARAMETER_INDICES = frozenset({874, 875})

_HEATPUMP_ID_LENGTH = 10

HOST_PLACEHOLDER = "**REDACTED_HOST**"

# Below this length a serial spelling is too generic to substitute blindly -
# a degenerate "0_00" would rewrite unrelated text all over the payload.
_MIN_SERIAL_LENGTH = 6


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LuxtronikConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # Optionally refresh data to ensure it's up to date
    await coordinator.async_request_refresh()

    host = entry.data[CONF_HOST]
    mac: str | None = None
    async with timeout(10):
        mac = await async_get_mac_address(hass, host)

    entry_dict = async_redact_data(entry.as_dict(), TO_REDACT)
    if "data" not in entry_dict:
        entry_dict["data"] = {}
    if mac is not None:
        # Keep only the OUI (vendor prefix); the device-specific octets are
        # the sensitive/unique part and are masked out.
        entry_dict["data"]["mac"] = mac[:9] + "*"

    heatpump_id = _heatpump_id(coordinator)
    substitutions = _substitutions(coordinator, entry, host, heatpump_id)

    diag_data = {
        "heatpump_id": heatpump_id,
        "entry": entry_dict,
        "devices": async_redact_data(coordinator.device_infos, TO_REDACT),
        "parameters": _dump_items(
            coordinator.data.parameters.parameters,
            redact_indices=SERIAL_PARAMETER_INDICES,
        ),
        "calculations": _dump_items(coordinator.data.calculations.calculations),
        "visibilities": _dump_items(coordinator.data.visibilities.visibilities),
        "log_records": get_captured_log_records(),
    }
    # Substitute once, over the finished payload. Doing it per-section is how
    # `entry.discovery_keys` and calculations 91-94 (the controller's own IP,
    # netmask, broadcast and gateway) were missed twice: every new section is
    # a new thing to remember. One pass at the end cannot be forgotten.
    scrubbed = _substitute(diag_data, substitutions)
    _warn_if_unscrubbed(scrubbed, substitutions)
    return scrubbed


def _usable_serial(unique_id: str | None) -> TypeIs[str]:
    """Is this serial specific enough to identify one heat pump?

    A controller that has not been commissioned reports P0874/P0875 as 0,
    yielding `0_00`. That is not a serial: every such unit would share one
    `heatpump_id`, silently merging unrelated pumps into what looks like one
    unit's history - worse for analysis than having no pseudonym at all.
    """
    if not unique_id or len(unique_id) < _MIN_SERIAL_LENGTH:
        return False
    date, _, _index = unique_id.partition("_")
    return date.strip("0") != ""


def _substitutions(
    coordinator: LuxtronikCoordinator,
    entry: LuxtronikConfigEntry,
    host: str,
    heatpump_id: str | None,
) -> dict[str, str]:
    """Build the value-level replacements applied across the whole payload.

    `TO_REDACT` matches on dict *keys*, which only works for fields that hold
    a sensitive value and nothing else. The serial number and the host also
    turn up embedded inside other strings - `ha_sensor_prefix` is built as
    `luxtronik_<unique_id>`, older entry titles read `<manufacturer> <model>
    <serial>`, current ones read `<manufacturer> @ <host>:<port>`, log lines
    quote entity ids built from the prefix, and calculation 91 is the
    controller's own IP. Keyed redaction cannot see any of those, so they are
    substituted by value instead.

    The serial is replaced by `heatpump_id` rather than by a placeholder, so
    an entity id stays traceable through a dump: `luxtronik_<serial>_flow` and
    `luxtronik_<heatpump_id>_flow` are still recognisably the same entity.

    Both the coordinator's current serial *and* the one recorded on the config
    entry are used as needles. They can differ: `ha_sensor_prefix` and legacy
    titles are frozen at setup time, so a controller that later reports a
    different serial would leave the original spelling unreachable.
    """
    substitutions: dict[str, str] = {}
    if heatpump_id is not None:
        for unique_id in (coordinator.unique_id, entry.unique_id):
            if not _usable_serial(unique_id):
                continue
            # Both spellings occur: `unique_id` uses '_', `serial_number` '-'.
            substitutions[unique_id] = heatpump_id
            substitutions[unique_id.replace("_", "-")] = heatpump_id
    if host:
        substitutions[host] = HOST_PLACEHOLDER
    return substitutions


def _substitute(value: Any, substitutions: dict[str, str]) -> Any:
    """Recursively replace sensitive substrings anywhere inside `value`."""
    if not substitutions:
        return value
    # One alternation, longest needle first, applied in a single pass - so no
    # replacement's output can be re-matched by a later needle.
    pattern = re.compile(
        "|".join(re.escape(n) for n in sorted(substitutions, key=len, reverse=True))
    )
    return _apply(value, pattern, substitutions)


def _apply(value: Any, pattern: re.Pattern[str], substitutions: dict[str, str]) -> Any:
    """Walk `value`, rewriting every string it contains.

    Tuples, sets and frozensets are walked too, and not for symmetry: HA's
    `ConfigEntry.as_dict()` returns `discovery_keys` as tuples of
    `DiscoveryKey` (whose `key` is the full MAC address for a DHCP-discovered
    entry), and device `identifiers`/`connections` are sets of tuples.
    `async_redact_data` skips all three types as well, so anything of that
    shape is scrubbed here or not at all.
    """
    if isinstance(value, str):
        return pattern.sub(lambda m: substitutions[m.group(0)], value)
    if isinstance(value, Mapping):
        return {k: _apply(v, pattern, substitutions) for k, v in value.items()}  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, (list, tuple, set, frozenset)):
        rebuilt = [_apply(item, pattern, substitutions) for item in value]  # pyright: ignore[reportUnknownVariableType]
        if isinstance(value, list):
            return rebuilt
        # Sets of tuples are unhashable once rebuilt as lists, so serialise
        # them as a list rather than losing the values entirely.
        return tuple(rebuilt) if isinstance(value, tuple) else rebuilt
    return value


def _warn_if_unscrubbed(payload: Any, substitutions: dict[str, str]) -> None:
    """Log if a sensitive value survived, instead of quietly publishing it.

    Four distinct paths have now leaked the serial or the host - two matched
    by key, two by type. Each was found by reading the code rather than by
    the code noticing. This makes the next one a warning in the user's log
    instead of a disclosure in a public issue.
    """
    if not substitutions:
        return
    serialised = json.dumps(payload, default=str)
    leaked = [needle for needle in substitutions if needle in serialised]
    if leaked:
        LOGGER.warning(
            "Diagnostics: %d sensitive value(s) survived redaction and are "
            "present in the download - please report this, and review the "
            "file before sharing it",
            len(leaked),
        )


def _dump_items(
    items: dict[int, Any], redact_indices: frozenset[int] = frozenset()
) -> dict[str, str]:
    dump = {}
    for index, item in sorted(items.items()):
        value = REDACTED if index in redact_indices else f"{item}"
        dump[f"{index:<4d} {item.name:<60}"] = value
    return dump


def _heatpump_id(coordinator: LuxtronikCoordinator) -> str | None:
    """Return a stable pseudonym for the physical heat pump.

    The serial number identifies the unit, which is what makes a shared
    diagnostics dump useful - it is how several dumps get recognised as the
    same pump, and how two config entries are told apart. It is also printed
    on the unit and used towards the manufacturer, so it should not be
    published verbatim in a file attached to a public issue. Hashing it keeps
    the first property without the second: the same pump always yields the
    same id, and two different pumps practically never collide.

    This is a pseudonym, not a secret. The serial's input space is small (a
    six-digit date plus a short hex index), so anyone determined could
    enumerate it against this hash. It removes the plate-readable number from
    the file and stops casual harvesting; it is not a cryptographic
    guarantee, and nothing here should be relied on as one.

    The pre-image is `unique_id`, i.e. the serial lowercased with '-' replaced
    by '_' (`330123-0145` hashes as `330123_0145`). Anyone re-keying an older
    dump to match a newer one needs that exact spelling.

    Returns None when the serial is unavailable or degenerate, so producing a
    diagnostics dump never depends on the heat pump being reachable - a dump
    that loses its pseudonym is far better than no dump at all. `unique_id`
    derives from P0874/P0875 via int()/hex(), so a malformed reading raises
    ValueError or TypeError rather than LuxtronikSerialNumberError.
    """
    try:
        unique_id = coordinator.unique_id
    except (LuxtronikSerialNumberError, TypeError, ValueError):
        return None
    if not _usable_serial(unique_id):
        return None
    return sha256(unique_id.encode()).hexdigest()[:_HEATPUMP_ID_LENGTH]


def _redact_log_records(records: list[str], host: str) -> list[str]:
    """Scrub the configured host/IP out of captured log lines.

    Thin wrapper kept for the host-only case; the diagnostics payload itself
    goes through `_substitute`, which also catches the serial number where it
    is embedded in logged entity ids.

    Log messages are free text, not structured data, so they can't go through
    `async_redact_data` like the rest of this payload - this only catches the
    values we know for certain might appear in a connection-error, discovery
    or entity-update log line. It is not a substitute for skimming logs before
    sharing them (see REPORTING_ISSUES.md).
    """
    if not host:
        return records
    return _substitute(records, {host: HOST_PLACEHOLDER})

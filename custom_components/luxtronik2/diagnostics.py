"""Diagnostics support for Luxtronik."""

# region Imports
from __future__ import annotations

from asyncio import timeout
from collections.abc import Mapping
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import LuxtronikConfigEntry
from .common import async_get_mac_address
from .log_capture import get_captured_log_records

# endregion Imports

TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_HOST,
    "unique_id",
    "identifiers",
    "via_device",
    "configuration_url",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LuxtronikConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # Optionally refresh data to ensure it's up to date
    await coordinator.async_request_refresh()

    mac: str | None = None
    async with timeout(10):
        mac = await async_get_mac_address(hass, entry.data[CONF_HOST])

    entry_data = async_redact_data(entry.as_dict(), TO_REDACT)
    if "data" not in entry_data:
        entry_data["data"] = {}
    if mac is not None:
        # Keep only the OUI (vendor prefix); the device-specific octets are
        # the sensitive/unique part and are masked out.
        entry_data["data"]["mac"] = mac[:9] + "*"

    diag_data = {
        "entry": entry_data,
        "devices": async_redact_data(coordinator.device_infos, TO_REDACT),
        "parameters": _dump_items(coordinator.data.parameters.parameters),
        "calculations": _dump_items(coordinator.data.calculations.calculations),
        "visibilities": _dump_items(coordinator.data.visibilities.visibilities),
        "log_records": _redact_log_records(
            get_captured_log_records(), entry.data[CONF_HOST]
        ),
    }
    return diag_data


def _dump_items(items: dict[int, Any]) -> dict[str, str]:
    dump = {}
    for index, item in sorted(items.items()):
        dump[f"{index:<4d} {item.name:<60}"] = f"{item}"
    return dump


def _redact_log_records(records: list[str], host: str) -> list[str]:
    """Scrub the configured host/IP out of captured log lines.

    Log messages are free text, not structured data, so they can't go
    through `async_redact_data` like the rest of this payload - this only
    catches the one sensitive value (the LAN host/IP) we know for certain
    might appear in a connection-error or discovery log line. It is not a
    substitute for skimming logs before sharing them (see REPORTING_ISSUES.md).
    """
    if not host:
        return records
    return [record.replace(host, "**REDACTED_HOST**") for record in records]

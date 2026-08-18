"""Tests for custom_components.luxtronik2.diagnostics."""

from __future__ import annotations

import json
import re
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_HOST
import pytest

from conftest import FakeSensorItem
from custom_components.luxtronik2.const import DEFAULT_PORT
from custom_components.luxtronik2.diagnostics import (
    SERIAL_PARAMETER_INDICES,
    _dump_items,
    _redact_log_records,
)


class TestDumpItems:
    def test_empty_dict(self):
        result = _dump_items({})
        assert result == {}

    def test_single_item(self):
        items = {0: FakeSensorItem("test_param", 42)}
        result = _dump_items(items)
        assert len(result) == 1
        key = next(iter(result.keys()))
        assert "0" in key
        assert "test_param" in key

    def test_multiple_items_sorted(self):
        items = {
            2: FakeSensorItem("param_c", 3),
            0: FakeSensorItem("param_a", 1),
            1: FakeSensorItem("param_b", 2),
        }
        result = _dump_items(items)
        assert len(result) == 3
        keys = list(result.keys())
        # Should be sorted by index
        assert "0" in keys[0]
        assert "1" in keys[1]
        assert "2" in keys[2]


class TestAsyncGetConfigEntryDiagnostics:
    @pytest.mark.asyncio
    async def test_returns_diagnostics(self):
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value="aa:bb:cc:dd:ee:ff")

        data = MagicMock()
        data.parameters.parameters = {0: FakeSensorItem("p1", 1)}
        data.calculations.calculations = {0: FakeSensorItem("c1", 2)}
        data.visibilities.visibilities = {0: FakeSensorItem("v1", 3)}

        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data = data
        coordinator.unique_id = "20230101_0ff"
        coordinator.serial_number = "20230101-0ff"
        coordinator.device_infos = {"hp": {"name": "test"}}

        entry = MagicMock()
        entry.runtime_data = coordinator
        entry.unique_id = "20230101_0ff"
        entry.data = {"host": "192.168.1.100", "port": DEFAULT_PORT}
        entry.as_dict.return_value = {
            "unique_id": "20230101_0xff",
            "data": {"host": "192.168.1.100"},
        }

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert "entry" in result
        assert "devices" in result
        assert "parameters" in result
        assert "calculations" in result
        assert "visibilities" in result
        assert "log_records" in result
        # MAC keeps only the OUI (vendor prefix); the device-specific part
        # is masked out - not routed through TO_REDACT (M9).
        assert result["entry"]["data"]["mac"] == "aa:bb:cc:*"
        # Host and serial-derived unique_id must be fully redacted (M9).
        assert result["entry"]["data"]["host"] == REDACTED
        assert result["entry"]["unique_id"] == REDACTED

    @pytest.mark.asyncio
    async def test_includes_and_redacts_captured_log_records(self):
        """Log records are embedded so a single diagnostics download covers
        both state and recent log activity; the configured host is scrubbed
        out of them since log lines aren't structured data and can't go
        through TO_REDACT like the rest of the payload."""
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)

        data = MagicMock()
        data.parameters.parameters = {}
        data.calculations.calculations = {}
        data.visibilities.visibilities = {}

        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data = data
        coordinator.unique_id = "20230101_0ff"
        coordinator.serial_number = "20230101-0ff"
        coordinator.device_infos = {}

        entry = MagicMock()
        entry.runtime_data = coordinator
        entry.unique_id = "20230101_0ff"
        entry.data = {CONF_HOST: "192.168.1.100"}
        entry.as_dict.return_value = {"data": {}}

        fake_records = [
            "2026-07-21 10:00:00 DEBUG some.logger: connecting to 192.168.1.100:8889",
            "2026-07-21 10:00:01 ERROR some.logger: unrelated failure",
        ]
        with patch(
            "custom_components.luxtronik2.diagnostics.get_captured_log_records",
            return_value=fake_records,
        ):
            result = await async_get_config_entry_diagnostics(hass, entry)

        assert "192.168.1.100" not in result["log_records"][0]
        assert "**REDACTED_HOST**" in result["log_records"][0]
        assert result["log_records"][1] == fake_records[1]


class TestRedactLogRecords:
    def test_replaces_host_occurrences(self):
        records = ["connecting to 10.0.0.5:8889", "no host here"]
        result = _redact_log_records(records, "10.0.0.5")
        assert result == ["connecting to **REDACTED_HOST**:8889", "no host here"]

    def test_empty_host_returns_records_unchanged(self):
        records = ["some log line"]
        assert _redact_log_records(records, "") == records

    def test_empty_records_list(self):
        assert _redact_log_records([], "10.0.0.5") == []

    @pytest.mark.asyncio
    async def test_no_mac(self):
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)

        data = MagicMock()
        data.parameters.parameters = {}
        data.calculations.calculations = {}
        data.visibilities.visibilities = {}

        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data = data
        coordinator.unique_id = "20230101_0ff"
        coordinator.serial_number = "20230101-0ff"
        coordinator.device_infos = {}

        entry = MagicMock()
        entry.runtime_data = coordinator
        entry.unique_id = "20230101_0ff"
        entry.data = {"host": "192.168.1.100"}
        entry.as_dict.return_value = {"data": {}}

        result = await async_get_config_entry_diagnostics(hass, entry)
        assert "mac" not in result["entry"]["data"]

    @pytest.mark.asyncio
    async def test_device_identifiers_are_redacted(self):
        """M9: device identifiers/via_device/configuration_url embed the
        serial number and host, and must be redacted like core integrations."""
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)

        data = MagicMock()
        data.parameters.parameters = {}
        data.calculations.calculations = {}
        data.visibilities.visibilities = {}

        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data = data
        coordinator.unique_id = "20230101_0ff"
        coordinator.serial_number = "20230101-0ff"
        coordinator.device_infos = {
            "heatpump": {
                "identifiers": {("luxtronik2", "20230101_0xff_heatpump")},
                "configuration_url": "http://192.168.1.100/",
                "name": "heatpump",
            },
            "heating": {
                "identifiers": {("luxtronik2", "20230101_0xff_heating")},
                "via_device": ("luxtronik2", "20230101_0xff_heatpump"),
                "name": "heating",
            },
        }

        entry = MagicMock()
        entry.runtime_data = coordinator
        entry.unique_id = "20230101_0ff"
        entry.data = {"host": "192.168.1.100"}
        entry.as_dict.return_value = {"data": {}}

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["devices"]["heatpump"]["identifiers"] == REDACTED
        assert result["devices"]["heatpump"]["configuration_url"] == REDACTED
        assert result["devices"]["heating"]["identifiers"] == REDACTED
        assert result["devices"]["heating"]["via_device"] == REDACTED
        # Non-sensitive fields must survive untouched
        assert result["devices"]["heatpump"]["name"] == "heatpump"


class TestDiagnosticsNoDataKey:
    @pytest.mark.asyncio
    async def test_entry_data_without_data_key(self):
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)

        data = MagicMock()
        data.parameters.parameters = {}
        data.calculations.calculations = {}
        data.visibilities.visibilities = {}

        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data = data
        coordinator.unique_id = "20230101_0ff"
        coordinator.serial_number = "20230101-0ff"
        coordinator.device_infos = {}

        entry = MagicMock()
        entry.runtime_data = coordinator
        entry.unique_id = "20230101_0ff"
        entry.data = {CONF_HOST: "192.168.1.100"}
        # as_dict returns WITHOUT "data" key — triggers the branch
        entry.as_dict.return_value = {"options": {}}

        result = await async_get_config_entry_diagnostics(hass, entry)
        assert "entry" in result
        assert "data" in result["entry"]


def _coordinator_with(serial: str, device_infos: dict | None = None) -> MagicMock:
    """Build a coordinator whose payload carries `serial` in every place it leaks."""
    date, _, index = serial.partition("_")
    data = MagicMock()
    data.parameters.parameters = {
        874: FakeSensorItem("ID_WP_SerienNummer_DATUM", int(date)),
        875: FakeSensorItem("ID_WP_SerienNummer_HEX", int(index, 16)),
        876: FakeSensorItem("ID_WP_SerienNummer_INDEX", 2),
    }
    data.calculations.calculations = {}
    data.visibilities.visibilities = {}

    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.data = data
    coordinator.unique_id = serial
    # `serial_number` is the '-' spelling, `unique_id` the '_' one; both occur
    # in real payloads and both have to be scrubbed.
    coordinator.serial_number = serial.replace("_", "-")
    coordinator.device_infos = (
        device_infos
        if device_infos is not None
        else {
            "heatpump": {
                "name": "heatpump",
                "model": "MSW2-9S",
                "serial_number": serial,
            }
        }
    )
    return coordinator


def _entry_for(coordinator: MagicMock) -> MagicMock:
    """Build an entry shaped like a real one.

    An empty `data` dict is not what any real config entry looks like, and a
    mock that omits `ha_sensor_prefix`/`title` hides two of the places the
    serial actually leaks - which is exactly how they were missed once.
    """
    serial = coordinator.unique_id
    entry = MagicMock()
    entry.runtime_data = coordinator
    entry.unique_id = serial
    entry.data = {CONF_HOST: "192.168.1.100"}
    entry.as_dict.return_value = {
        "unique_id": serial,
        # Legacy entries kept a title built from the serial; current ones
        # embed the host instead. __init__ preserves whichever exists.
        "title": f"Alpha Innotec MSW2-9S {serial.replace('_', '-')}",
        "data": {
            "host": "192.168.1.100",
            "port": 8889,
            "ha_sensor_prefix": f"luxtronik_{serial}",
        },
    }
    return entry


class TestSerialPseudonym:
    """The serial identifies the physical unit, which the diagnostics workflow
    needs, but it should not be published verbatim in a file users attach to
    public issues. It is replaced everywhere by a stable pseudonym."""

    def test_dump_items_masks_the_serial_parameters(self):
        items = {
            874: FakeSensorItem("ID_WP_SerienNummer_DATUM", 330123),
            875: FakeSensorItem("ID_WP_SerienNummer_HEX", 325),
            876: FakeSensorItem("ID_WP_SerienNummer_INDEX", 2),
        }
        result = _dump_items(items, redact_indices=SERIAL_PARAMETER_INDICES)
        values = list(result.values())
        assert values[0] == REDACTED
        assert values[1] == REDACTED
        # The index is not part of the serial and stays readable.
        assert "2" in values[2]
        # Names/indices survive so the dump is still navigable.
        assert "ID_WP_SerienNummer_DATUM" in next(iter(result.keys()))

    def test_dump_items_masks_nothing_by_default(self):
        items = {874: FakeSensorItem("ID_WP_SerienNummer_DATUM", 330123)}
        assert REDACTED not in list(_dump_items(items).values())

    @pytest.mark.asyncio
    async def test_serial_never_appears_in_the_payload(self):
        """End-to-end: the serial leaked three ways before (entry.unique_id,
        devices.serial_number, parameters 874/875). None may survive."""
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)
        coordinator = _coordinator_with("330123_0145")

        result = await async_get_config_entry_diagnostics(hass, _entry_for(coordinator))

        payload = json.dumps(result, default=str)
        assert "330123" not in payload
        assert result["entry"]["unique_id"] == REDACTED
        assert result["devices"]["heatpump"]["serial_number"] == REDACTED
        assert list(result["parameters"].values())[:2] == [REDACTED, REDACTED]
        # Model and other device fields are not sensitive and must survive.
        assert result["devices"]["heatpump"]["model"] == "MSW2-9S"

    @pytest.mark.asyncio
    async def test_heatpump_id_is_stable_and_distinguishes_units(self):
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)

        async def diag(serial: str):
            coordinator = _coordinator_with(serial)
            return await async_get_config_entry_diagnostics(
                hass, _entry_for(coordinator)
            )

        first = await diag("330123_0145")
        again = await diag("330123_0145")
        other = await diag("260126_0477")

        assert first["heatpump_id"] == again["heatpump_id"]
        assert first["heatpump_id"] != other["heatpump_id"]
        assert re.fullmatch(r"[0-9a-f]{10}", first["heatpump_id"])

    @pytest.mark.asyncio
    async def test_heatpump_id_when_serial_unavailable(self):
        """`unique_id` raises when P0874 has not been read yet; the dump must
        still be produced rather than failing on the pseudonym."""
        from custom_components.luxtronik2.coordinator import (
            LuxtronikSerialNumberError,
        )
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)
        coordinator = _coordinator_with("330123_0145", device_infos={})
        type(coordinator).unique_id = property(
            lambda _self: (_ for _ in ()).throw(LuxtronikSerialNumberError("no P0874"))
        )
        entry = MagicMock()
        entry.runtime_data = coordinator
        entry.unique_id = "20230101_0ff"
        entry.data = {CONF_HOST: "192.168.1.100"}
        entry.as_dict.return_value = {"data": {}}

        result = await async_get_config_entry_diagnostics(hass, entry)
        assert result["heatpump_id"] is None

    @pytest.mark.asyncio
    async def test_embedded_serial_is_swapped_for_the_pseudonym(self):
        """The serial also turns up *inside* other strings, where keyed
        redaction cannot see it: `ha_sensor_prefix` is built as
        `luxtronik_<unique_id>`, and legacy entry titles end in the serial."""
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)
        coordinator = _coordinator_with("330123_0145")

        result = await async_get_config_entry_diagnostics(hass, _entry_for(coordinator))

        heatpump_id = result["heatpump_id"]
        # Swapped for the pseudonym rather than blanked, so the prefix still
        # cross-references the entity ids in the log records.
        assert result["entry"]["data"]["ha_sensor_prefix"] == f"luxtronik_{heatpump_id}"
        assert heatpump_id in result["entry"]["title"]
        assert "330123" not in result["entry"]["title"]
        # The host is embedded in current-format titles the same way.
        assert "192.168.1.100" not in json.dumps(result["entry"], default=str)

    @pytest.mark.asyncio
    async def test_log_records_scrub_serial_bearing_entity_ids(self):
        """Entity ids are built from the sensor prefix, so debug lines quoting
        them carry the serial into `log_records`."""
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)
        coordinator = _coordinator_with("330123_0145")

        records = [
            "DEBUG luxtronik2: Setting select.luxtronik_330123_0145_mode to 'auto'",
            "DEBUG luxtronik2: connecting to 192.168.1.100:8889",
        ]
        with patch(
            "custom_components.luxtronik2.diagnostics.get_captured_log_records",
            return_value=records,
        ):
            result = await async_get_config_entry_diagnostics(
                hass, _entry_for(coordinator)
            )

        heatpump_id = result["heatpump_id"]
        assert result["log_records"][0] == (
            f"DEBUG luxtronik2: Setting select.luxtronik_{heatpump_id}_mode to 'auto'"
        )
        assert "192.168.1.100" not in result["log_records"][1]

    def test_substitute_is_a_no_op_without_replacements(self):
        """When the serial is unavailable and no host is configured there is
        nothing to swap, and the payload must pass through untouched."""
        from custom_components.luxtronik2.diagnostics import _substitute

        payload = {"a": ["keep", {"b": "me"}], "n": 1}
        assert _substitute(payload, {}) is payload


class TestPayloadWideScrubbing:
    """Shapes taken from real dumps in the local corpus. Every one of these
    leaked in an earlier revision of this module; the first two were missed
    because they are reached by *type* rather than by key."""

    @pytest.mark.asyncio
    async def test_discovery_keys_tuple_is_scrubbed(self):
        """`ConfigEntry.as_dict()` returns discovery_keys as tuples, and
        `async_redact_data` skips tuples entirely - so a DHCP-discovered entry
        published the full MAC next to the deliberately masked one."""
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value="00:19:99:7d:b0:49")
        coordinator = _coordinator_with("330123_0145")
        entry = _entry_for(coordinator)
        entry.as_dict.return_value["discovery_keys"] = {
            "dhcp": ({"domain": "dhcp", "key": "330123_0145", "host": "192.168.1.100"},)
        }

        result = await async_get_config_entry_diagnostics(hass, entry)

        discovered = result["entry"]["discovery_keys"]["dhcp"]
        assert isinstance(discovered, tuple)
        assert discovered[0]["key"] == result["heatpump_id"]
        assert discovered[0]["host"] == "**REDACTED_HOST**"

    @pytest.mark.asyncio
    async def test_network_calculations_do_not_republish_the_host(self):
        """Calculations 91-94 are the controller's own IP, netmask, broadcast
        and gateway. Calculation 91 is the configured host - the same value
        TO_REDACT blanks in entry.data and _redact_log_records strips from
        log lines - and it appears in nearly every real dump."""
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)
        coordinator = _coordinator_with("330123_0145")
        coordinator.data.calculations.calculations = {
            91: FakeSensorItem("ID_WEB_AdresseIP_akt", "192.168.1.100"),
            92: FakeSensorItem("ID_WEB_SubNetMask_akt", "255.255.255.0"),
        }

        result = await async_get_config_entry_diagnostics(hass, _entry_for(coordinator))

        values = list(result["calculations"].values())
        assert "192.168.1.100" not in values[0]
        assert "**REDACTED_HOST**" in values[0]
        # The netmask is not sensitive and must survive.
        assert "255.255.255.0" in values[1]

    @pytest.mark.asyncio
    async def test_serial_recorded_on_the_entry_is_scrubbed_too(self):
        """ha_sensor_prefix and legacy titles are frozen at setup time. If the
        controller later reports a different serial, the recorded spelling is
        only reachable via the entry's own unique_id."""
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)
        coordinator = _coordinator_with("320707_0395")
        entry = _entry_for(coordinator)
        entry.unique_id = "320707_0390"
        entry.as_dict.return_value["data"]["ha_sensor_prefix"] = "luxtronik_320707_0390"

        result = await async_get_config_entry_diagnostics(hass, entry)

        payload = json.dumps(result, default=str)
        assert "320707_0390" not in payload
        assert "320707_0395" not in payload

    @pytest.mark.asyncio
    async def test_uncommissioned_serial_yields_no_pseudonym(self):
        """An uncommissioned controller reports P0874/P0875 as 0, giving
        `0_00`. Hashing that would hand every such unit the same id, merging
        unrelated pumps into one apparent history - and `0_00` is short enough
        that substituting it would rewrite unrelated text."""
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)
        coordinator = _coordinator_with("330123_0145")
        coordinator.unique_id = "0_00"
        coordinator.data.parameters.parameters = {
            874: FakeSensorItem("ID_WP_SerienNummer_DATUM", 0),
            875: FakeSensorItem("ID_WP_SerienNummer_HEX", 0),
        }
        entry = _entry_for(coordinator)
        entry.unique_id = "0_00"
        entry.as_dict.return_value["title"] = "Nulldata 0-00 at 0_00"

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["heatpump_id"] is None
        # Not substituted: too generic to rewrite blindly.
        assert result["entry"]["title"] == "Nulldata 0-00 at 0_00"

    def test_apply_walks_sets_and_tuples(self):
        """Device `identifiers`/`connections` are sets of tuples."""
        from custom_components.luxtronik2.diagnostics import _substitute

        payload = {
            "identifiers": {("luxtronik2", "330123_0145_heatpump")},
            "coords": ("330123_0145", 5),
        }
        result = _substitute(payload, {"330123_0145": "PSEUDONYM"})

        assert result["coords"] == ("PSEUDONYM", 5)
        # The set becomes a list (rebuilt tuples stay tuples but are no
        # longer hashable as a set once their contents change).
        assert result["identifiers"] == [("luxtronik2", "PSEUDONYM_heatpump")]

    def test_warns_when_a_value_survives(self, caplog):
        """The backstop turns the next missed path into a warning rather than
        a silent disclosure."""
        from custom_components.luxtronik2.diagnostics import _warn_if_unscrubbed

        _warn_if_unscrubbed({"leftover": "330123_0145"}, {"330123_0145": "x"})
        assert "survived redaction" in caplog.text

    def test_does_not_warn_when_clean(self, caplog):
        from custom_components.luxtronik2.diagnostics import _warn_if_unscrubbed

        _warn_if_unscrubbed({"ok": "nothing here"}, {"330123_0145": "x"})
        assert "survived redaction" not in caplog.text

    def test_all_zero_serial_date_is_rejected_even_when_long_enough(self):
        """`0_00` is caught by the length guard, but a controller reporting a
        zero *date* with a real index (`000000_0145`) is long enough to pass
        that and still isn't a serial."""
        from custom_components.luxtronik2.diagnostics import _usable_serial

        assert not _usable_serial("000000_0145")
        assert not _usable_serial("0_00")
        assert not _usable_serial(None)
        assert _usable_serial("330123_0145")

    @pytest.mark.asyncio
    async def test_entry_without_a_recorded_unique_id(self):
        """A config entry can legitimately have unique_id None; only the
        coordinator's serial is then available as a needle."""
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)
        coordinator = _coordinator_with("330123_0145")
        entry = _entry_for(coordinator)
        entry.unique_id = None

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert "330123" not in json.dumps(result, default=str)

    def test_no_warning_when_there_is_nothing_to_scrub(self, caplog):
        from custom_components.luxtronik2.diagnostics import _warn_if_unscrubbed

        _warn_if_unscrubbed({"anything": "330123_0145"}, {})
        assert "survived redaction" not in caplog.text

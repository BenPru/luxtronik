"""Tests for custom_components.luxtronik2.diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_HOST
import pytest

from conftest import FakeSensorItem
from custom_components.luxtronik2.const import DEFAULT_PORT
from custom_components.luxtronik2.diagnostics import _dump_items, _redact_log_records


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
        coordinator.device_infos = {"hp": {"name": "test"}}

        entry = MagicMock()
        entry.runtime_data = coordinator
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
        coordinator.device_infos = {}

        entry = MagicMock()
        entry.runtime_data = coordinator
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
        coordinator.device_infos = {}

        entry = MagicMock()
        entry.runtime_data = coordinator
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
        coordinator.device_infos = {}

        entry = MagicMock()
        entry.runtime_data = coordinator
        entry.data = {CONF_HOST: "192.168.1.100"}
        # as_dict returns WITHOUT "data" key — triggers the branch
        entry.as_dict.return_value = {"options": {}}

        result = await async_get_config_entry_diagnostics(hass, entry)
        assert "entry" in result
        assert "data" in result["entry"]

"""Tests for custom_components.luxtronik2.diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.const import CONF_HOST
import pytest

from conftest import FakeSensorItem
from custom_components.luxtronik2.const import DEFAULT_PORT
from custom_components.luxtronik2.diagnostics import _dump_items


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
        entry.as_dict.return_value = {"data": {"host": "192.168.1.100"}}

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert "entry" in result
        assert "devices" in result
        assert "parameters" in result
        assert "calculations" in result
        assert "visibilities" in result
        # MAC should be redacted
        assert result["entry"]["data"]["mac"].endswith("*")

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

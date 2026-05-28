"""Tests for custom_components.luxtronik2.select entity classes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from conftest import make_coordinator_data
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
import pytest

from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxDaySelectorParameter,
    SensorKey,
)
from custom_components.luxtronik2.model import LuxtronikSelectEntityDescription
from custom_components.luxtronik2.select import LuxtronikThermalDesinfectionDaySelector

_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
    CONF_HA_SENSOR_PREFIX: DOMAIN,
}


def _mock_entry():
    entry = MagicMock()
    entry.data = _ENTRY_DATA.copy()
    entry.options = {}
    return entry


def _mock_coordinator(data=None):
    if data is None:
        data = make_coordinator_data()
    coord = MagicMock()
    coord.data = data
    coord.entity_active.return_value = True
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    coord.async_write = AsyncMock(return_value=data)
    return coord


def _patch_entity(entity):
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()


# ===========================================================================
# select.py — data is None guard (line 239)
# ===========================================================================


class TestSelectDataNone:
    @pytest.mark.asyncio
    async def test_async_select_option_data_none(self):
        desc = LuxtronikSelectEntityDescription(
            key=SensorKey.THERMAL_DESINFECTION_DAY,
            device_key=DeviceKey.domestic_water,
            luxtronik_key=LuxDaySelectorParameter.MONDAY,  # pyright: ignore[reportArgumentType]
        )
        coord = _mock_coordinator()
        entry = _mock_entry()
        entity = LuxtronikThermalDesinfectionDaySelector(
            entry, coord, desc, DeviceKey.domestic_water
        )
        _patch_entity(entity)

        # Set data to None
        entity.coordinator.data = None
        await entity.async_select_option("Monday")
        # Should return early without error


# ===========================================================================
# select.py — async_update
# ===========================================================================


class TestThermalDesinfectionAsyncUpdate:
    def _make_entity(self, coord=None):
        desc = LuxtronikSelectEntityDescription(
            key=SensorKey.THERMAL_DESINFECTION_DAY,
            device_key=DeviceKey.domestic_water,
            luxtronik_key=LuxDaySelectorParameter.MONDAY,  # pyright: ignore[reportArgumentType]
        )
        if coord is None:
            coord = _mock_coordinator()
        entry = _mock_entry()
        entity = LuxtronikThermalDesinfectionDaySelector(
            entry, coord, desc, DeviceKey.domestic_water
        )
        _patch_entity(entity)
        return entity

    @pytest.mark.asyncio
    async def test_async_update_data_none(self):
        entity = self._make_entity()
        entity.coordinator.data = None
        await entity.async_update()
        # Should return early, current_option unchanged

    @pytest.mark.asyncio
    async def test_async_update_no_day_selected(self):
        coord = _mock_coordinator()
        entity = self._make_entity(coord)
        # All day parameters return "0" by default (mock)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "custom_components.luxtronik2.select.get_sensor_data",
                lambda data, key: "0",
            )
            await entity.async_update()
        assert entity._attr_current_option == "none"

    @pytest.mark.asyncio
    async def test_async_update_day_selected(self):
        coord = _mock_coordinator()
        entity = self._make_entity(coord)
        wednesday_param = LuxDaySelectorParameter.WEDNESDAY.value

        def fake_sensor_data(data, key):
            return "1" if key == wednesday_param else "0"

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "custom_components.luxtronik2.select.get_sensor_data",
                fake_sensor_data,
            )
            await entity.async_update()
        assert entity._attr_current_option == "wednesday"

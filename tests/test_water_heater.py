"""Tests for custom_components.luxtronik.water_heater constants and mappings."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from conftest import make_coordinator_data
from homeassistant.components.water_heater import (
    STATE_ELECTRIC,
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, STATE_OFF
import pytest

from custom_components.luxtronik.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxMode,
    LuxOperationMode,
)
from custom_components.luxtronik.water_heater import (
    OPERATION_MAPPING,
    WATER_HEATERS,
)


class TestOperationMapping:
    def test_off(self):
        assert OPERATION_MAPPING[LuxMode.off] == STATE_OFF

    def test_automatic(self):
        assert OPERATION_MAPPING[LuxMode.automatic] == STATE_HEAT_PUMP

    def test_second_heatsource(self):
        assert OPERATION_MAPPING[LuxMode.second_heatsource] == STATE_ELECTRIC

    def test_party(self):
        assert OPERATION_MAPPING[LuxMode.party] == STATE_PERFORMANCE

    def test_holidays(self):
        assert OPERATION_MAPPING[LuxMode.holidays] == STATE_HEAT_PUMP


class TestWaterHeaterDescriptions:
    def test_water_heaters_count(self):
        assert len(WATER_HEATERS) == 2  # old firmware + new firmware

    def test_all_domestic_water(self):
        for wh in WATER_HEATERS:
            assert wh.device_key == DeviceKey.heatpump  # default
            assert wh.luxtronik_action_heating == LuxOperationMode.domestic_water

    def test_firmware_version_split(self):
        """First WH is for firmware < 88.3, second for >= 88.3."""
        from packaging.version import Version

        old = WATER_HEATERS[0]
        new = WATER_HEATERS[1]
        assert old.max_firmware_version_minor == Version("88.2")
        assert new.min_firmware_version_minor == Version("88.3")


# ===========================================================================
# Helpers for water heater entity tests
# ===========================================================================

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
    coord.last_update_success = True
    return coord


def _patch_entity(entity):
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()


# ===========================================================================
# water_heater.py — unavailable_keys log (line 115)
# ===========================================================================


class TestWaterHeaterUnavailableKeys:
    @pytest.mark.asyncio
    async def test_unavailable_keys_logged(self):
        from custom_components.luxtronik.water_heater import async_setup_entry

        coord = _mock_coordinator(make_coordinator_data())
        entry = MagicMock()
        entry.runtime_data = coord

        added = []
        with (
            patch(
                "custom_components.luxtronik.water_heater.key_exists",
                return_value=False,
            ),
            patch("custom_components.luxtronik.water_heater.LOGGER") as mock_logger,
        ):
            await async_setup_entry(
                MagicMock(), entry, lambda entities, update: added.extend(entities)
            )
            mock_logger.debug.assert_called()


# ===========================================================================
# water_heater.py — max_temp (lines 177-182)
# ===========================================================================


class TestWaterHeaterMaxTemp:
    def test_max_temp_from_data(self):
        from custom_components.luxtronik.water_heater import LuxtronikWaterHeater

        data = make_coordinator_data(parameters={"ID_Einst_BW_max": 65.0})
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        hass = MagicMock()
        entity = LuxtronikWaterHeater(hass, entry, coord, WATER_HEATERS[0])
        _patch_entity(entity)
        result = entity.max_temp
        assert result == 65.0

    def test_max_temp_fallback_on_missing_key(self):
        from custom_components.luxtronik.water_heater import LuxtronikWaterHeater

        data = make_coordinator_data(parameters={})
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        hass = MagicMock()
        entity = LuxtronikWaterHeater(hass, entry, coord, WATER_HEATERS[0])
        _patch_entity(entity)
        result = entity.max_temp
        assert result == 60.0

    def test_max_temp_fallback_on_conversion_error(self):
        from custom_components.luxtronik.water_heater import LuxtronikWaterHeater

        data = make_coordinator_data(parameters={"ID_Einst_BW_max": "not_a_number"})
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        hass = MagicMock()
        entity = LuxtronikWaterHeater(hass, entry, coord, WATER_HEATERS[0])
        _patch_entity(entity)
        result = entity.max_temp
        assert result == 60.0

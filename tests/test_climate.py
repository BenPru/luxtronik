"""Tests for custom_components.luxtronik2.climate constants and mappings."""

from __future__ import annotations

from dataclasses import replace as dc_replace
from unittest.mock import MagicMock, patch

from conftest import make_coordinator_data
from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_NONE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
import pytest

from custom_components.luxtronik2.climate import (
    HVAC_ACTION_MAPPING_COOL,
    HVAC_ACTION_MAPPING_HEAT,
    HVAC_MODE_MAPPING_COOL,
    HVAC_MODE_MAPPING_HEAT,
    HVAC_PRESET_MAPPING,
    MAX_TEMPERATURE,
    MIN_TEMPERATURE,
    THERMOSTATS,
    LuxtronikClimateExtraStoredData,
    LuxtronikThermostat,
)
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
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


class TestHVACMappings:
    def test_heat_action_mapping_complete(self):
        """All LuxOperationMode values are mapped for heating."""
        for mode in LuxOperationMode:
            assert mode in HVAC_ACTION_MAPPING_HEAT, f"Missing: {mode}"

    def test_cool_action_mapping_complete(self):
        """All LuxOperationMode values are mapped for cooling."""
        for mode in LuxOperationMode:
            assert mode in HVAC_ACTION_MAPPING_COOL, f"Missing: {mode}"

    def test_heating_maps_to_heating_action(self):
        assert (
            HVAC_ACTION_MAPPING_HEAT[LuxOperationMode.heating]
            == HVACAction.HEATING.value
        )

    def test_cooling_maps_to_cooling_action(self):
        assert (
            HVAC_ACTION_MAPPING_COOL[LuxOperationMode.cooling]
            == HVACAction.COOLING.value
        )

    def test_no_request_maps_to_idle(self):
        assert (
            HVAC_ACTION_MAPPING_HEAT[LuxOperationMode.no_request]
            == HVACAction.IDLE.value
        )
        assert (
            HVAC_ACTION_MAPPING_COOL[LuxOperationMode.no_request]
            == HVACAction.IDLE.value
        )

    def test_evu_maps_to_idle(self):
        assert HVAC_ACTION_MAPPING_HEAT[LuxOperationMode.evu] == HVACAction.IDLE.value

    def test_heat_mode_mapping(self):
        assert HVAC_MODE_MAPPING_HEAT[LuxMode.off] == HVACMode.OFF.value
        assert HVAC_MODE_MAPPING_HEAT[LuxMode.automatic] == HVACMode.HEAT.value
        assert HVAC_MODE_MAPPING_HEAT[LuxMode.party] == HVACMode.HEAT.value

    def test_cool_mode_mapping(self):
        assert HVAC_MODE_MAPPING_COOL[LuxMode.off] == HVACMode.OFF.value
        assert HVAC_MODE_MAPPING_COOL[LuxMode.automatic] == HVACMode.COOL.value


class TestHVACPresetMapping:
    def test_off_preset(self):
        assert HVAC_PRESET_MAPPING[LuxMode.off] == PRESET_NONE

    def test_automatic_preset(self):
        assert HVAC_PRESET_MAPPING[LuxMode.automatic] == PRESET_NONE

    def test_party_preset(self):
        assert HVAC_PRESET_MAPPING[LuxMode.party] == PRESET_COMFORT

    def test_holidays_preset(self):
        assert HVAC_PRESET_MAPPING[LuxMode.holidays] == PRESET_AWAY

    def test_second_heatsource_preset(self):
        assert HVAC_PRESET_MAPPING[LuxMode.second_heatsource] == PRESET_BOOST


class TestThermostats:
    def test_thermostat_count(self):
        assert len(THERMOSTATS) >= 3  # heating new, heating old, cooling

    def test_heating_thermostat_exists(self):
        heating = [t for t in THERMOSTATS if t.device_key == DeviceKey.heating]
        assert len(heating) >= 1

    def test_cooling_thermostat_exists(self):
        cooling = [t for t in THERMOSTATS if t.device_key == DeviceKey.cooling]
        assert len(cooling) == 1

    def test_temperature_bounds(self):
        assert MIN_TEMPERATURE == 8
        assert MAX_TEMPERATURE == 28


class TestClimateExtraStoredData:
    def test_as_dict(self):
        data = LuxtronikClimateExtraStoredData(
            _attr_target_temperature=21.0,
            _attr_hvac_mode=HVACMode.HEAT,
            _attr_preset_mode=PRESET_NONE,
        )
        d = data.as_dict()
        assert d["_attr_target_temperature"] == 21.0
        assert d["_attr_hvac_mode"] == HVACMode.HEAT
        assert d["_attr_preset_mode"] == PRESET_NONE

    def test_defaults(self):
        data = LuxtronikClimateExtraStoredData()
        d = data.as_dict()
        assert d["_attr_target_temperature"] is None
        assert d["_attr_hvac_mode"] is None
        assert d["last_hvac_mode_before_preset"] is None


# ===========================================================================
# Helpers for climate entity tests
# ===========================================================================

_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
    CONF_HA_SENSOR_PREFIX: DOMAIN,
}


def _mock_entry(**overrides):
    entry = MagicMock()
    data = _ENTRY_DATA.copy()
    data.update(overrides)
    entry.data = data
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
    return coord


def _patch_entity(entity):
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()


# ===========================================================================
# climate.py — unavailable_keys log (line 193)
# ===========================================================================


class TestClimateUnavailableKeys:
    @pytest.mark.asyncio
    async def test_unavailable_keys_logged(self):
        """When a thermostat key is missing from data, it's logged."""
        from custom_components.luxtronik2.climate import async_setup_entry

        coord = _mock_coordinator(make_coordinator_data())
        entry = MagicMock()
        entry.runtime_data = coord

        added = []
        with (
            patch(
                "custom_components.luxtronik2.climate.key_exists", return_value=False
            ),
            patch("custom_components.luxtronik2.climate.LOGGER") as mock_logger,
        ):
            await async_setup_entry(
                MagicMock(), entry, lambda entities, update: added.extend(entities)
            )
            mock_logger.debug.assert_called()


# ===========================================================================
# climate.py — configured_indoor_temp_sensor (lines 267-271)
# ===========================================================================


class TestClimateConfiguredIndoorTempSensor:
    def test_configured_sensor_replaces_key(self):
        coord = _mock_coordinator()
        entry = _mock_entry()
        entry.options = {CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.my_temp"}
        hass = MagicMock()

        thermostat = LuxtronikThermostat(hass, entry, coord, THERMOSTATS[0])
        assert (
            thermostat.entity_description.luxtronik_key_current_temperature
            == "sensor.my_temp"
        )


# ===========================================================================
# climate.py — key None/empty and sensor.* branches (lines 337, 339-340)
# ===========================================================================


class TestClimateTemperatureKeyBranches:
    def test_key_none_sets_current_temp_none(self):
        coord = _mock_coordinator()
        entry = _mock_entry()
        hass = MagicMock()

        thermostat = LuxtronikThermostat(hass, entry, coord, THERMOSTATS[0])
        _patch_entity(thermostat)
        thermostat.entity_description = dc_replace(
            thermostat.entity_description,
            luxtronik_key_current_temperature=None,
        )
        data = make_coordinator_data(
            parameters={"ID_Ba_Hz_akt": LuxMode.automatic},
            calculations={"ID_WEB_WP_BZ_akt": LuxOperationMode.heating},
        )
        thermostat._handle_coordinator_update(data)
        assert thermostat._attr_current_temperature is None

    def test_key_empty_sets_current_temp_none(self):
        coord = _mock_coordinator()
        entry = _mock_entry()
        hass = MagicMock()

        thermostat = LuxtronikThermostat(hass, entry, coord, THERMOSTATS[0])
        _patch_entity(thermostat)
        thermostat.entity_description = dc_replace(
            thermostat.entity_description,
            luxtronik_key_current_temperature="",
        )
        data = make_coordinator_data(
            parameters={"ID_Ba_Hz_akt": LuxMode.automatic},
            calculations={"ID_WEB_WP_BZ_akt": LuxOperationMode.heating},
        )
        thermostat._handle_coordinator_update(data)
        assert thermostat._attr_current_temperature is None

    def test_key_sensor_reads_from_hass_states(self):
        coord = _mock_coordinator()
        entry = _mock_entry()
        hass = MagicMock()

        thermostat = LuxtronikThermostat(hass, entry, coord, THERMOSTATS[0])
        _patch_entity(thermostat)
        thermostat.entity_description = dc_replace(
            thermostat.entity_description,
            luxtronik_key_current_temperature="sensor.living_room_temp",
        )
        mock_state = MagicMock()
        mock_state.state = "21.5"
        thermostat.hass.states.get.return_value = mock_state
        data = make_coordinator_data(
            parameters={"ID_Ba_Hz_akt": LuxMode.automatic},
            calculations={"ID_WEB_WP_BZ_akt": LuxOperationMode.heating},
        )
        thermostat._handle_coordinator_update(data)
        thermostat.hass.states.get.assert_called_with("sensor.living_room_temp")
        assert thermostat._attr_current_temperature == 21.5

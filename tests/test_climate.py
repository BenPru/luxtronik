"""Tests for custom_components.luxtronik2.climate constants and mappings."""

from __future__ import annotations

from dataclasses import replace as dc_replace
from unittest.mock import MagicMock, patch

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

from conftest import make_coordinator_data
from custom_components.luxtronik2.climate import (
    HVAC_ACTION_MAPPING_COOL,
    HVAC_ACTION_MAPPING_HEAT,
    HVAC_MODE_MAPPING_COOL,
    HVAC_MODE_MAPPING_HEAT,
    HVAC_PRESET_MAPPING,
    MAX_TEMPERATURE,
    MIN_TEMPERATURE,
    THERMOSTATS,
    THERMOSTATS_OTHER,
    THERMOSTATS_SMART,
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
    LuxCalculation,
    LuxMode,
    LuxOperationMode,
    LuxRoomThermostatType,
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
    def test_smart_thermostat_count(self):
        assert len(THERMOSTATS_SMART) == 2  # 1 heating + 1 cooling

    def test_other_thermostat_count(self):
        assert len(THERMOSTATS_OTHER) == 2  # 1 heating + 1 cooling

    def test_heating_thermostat_exists_smart(self):
        heating = [t for t in THERMOSTATS_SMART if t.device_key == DeviceKey.heating]
        assert len(heating) == 1

    def test_cooling_thermostat_exists_smart(self):
        cooling = [t for t in THERMOSTATS_SMART if t.device_key == DeviceKey.cooling]
        assert len(cooling) == 1

    def test_heating_thermostat_exists_other(self):
        heating = [t for t in THERMOSTATS_OTHER if t.device_key == DeviceKey.heating]
        assert len(heating) == 1

    def test_cooling_thermostat_exists_other(self):
        cooling = [t for t in THERMOSTATS_OTHER if t.device_key == DeviceKey.cooling]
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
                MagicMock(), entry, lambda entities: added.extend(entities)
            )
            mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_smart_thermostat_branch(self):
        """When room_thermostat_type is smart, THERMOSTATS_SMART is used."""
        from custom_components.luxtronik2.climate import async_setup_entry

        coord = _mock_coordinator(make_coordinator_data())
        coord.room_thermostat_type = LuxRoomThermostatType.smart
        entry = MagicMock()
        entry.runtime_data = coord

        added = []
        with patch(
            "custom_components.luxtronik2.climate.key_exists", return_value=True
        ):
            await async_setup_entry(
                MagicMock(), entry, lambda entities: added.extend(entities)
            )
        assert len(added) == len(THERMOSTATS_SMART)


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
# climate.py — current temperature source vs room thermostat type
# ===========================================================================


def _update_with_room_temp(thermostat, room_temp: float, ha_state=None):
    _patch_entity(thermostat)
    if ha_state is not None:
        mock_state = MagicMock()
        mock_state.state = ha_state
        thermostat.hass.states.get.return_value = mock_state
    data = make_coordinator_data(
        parameters={"ID_Ba_Hz_akt": LuxMode.automatic},
        calculations={
            "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
            "ID_WEB_RBE_RT_Ist": room_temp,
        },
    )
    thermostat._handle_coordinator_update(data)


class TestClimateNoRoomThermostat:
    """P0033 = 0 means no room thermostat is fitted, and C0227 then reads a
    permanent 0.0 (24 of 29 units in the diagnostics corpus). A climate card
    showing 0 °C as the room temperature is worse than one showing none.
    """

    def test_no_thermostat_reports_no_current_temperature(self):
        coord = _mock_coordinator()
        coord.room_thermostat_type = LuxRoomThermostatType.none
        thermostat = LuxtronikThermostat(
            MagicMock(), _mock_entry(), coord, THERMOSTATS_OTHER[0]
        )
        _update_with_room_temp(thermostat, 0.0)
        assert thermostat.current_temperature is None

    def test_no_thermostat_still_uses_configured_ha_sensor(self):
        """A sensor picked in the options flow is the user's own room
        temperature and wins regardless of what the controller has fitted."""
        coord = _mock_coordinator()
        coord.room_thermostat_type = LuxRoomThermostatType.none
        entry = _mock_entry()
        entry.options = {CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.my_temp"}
        thermostat = LuxtronikThermostat(
            MagicMock(), entry, coord, THERMOSTATS_OTHER[0]
        )
        _update_with_room_temp(thermostat, 0.0, ha_state="20.5")
        thermostat.hass.states.get.assert_called_with("sensor.my_temp")
        assert thermostat.current_temperature == 20.5

    def test_rbe_thermostat_reads_c0227(self):
        coord = _mock_coordinator()
        coord.room_thermostat_type = LuxRoomThermostatType.rbe
        thermostat = LuxtronikThermostat(
            MagicMock(), _mock_entry(), coord, THERMOSTATS_OTHER[0]
        )
        _update_with_room_temp(thermostat, 21.8)
        assert thermostat.current_temperature == 21.8

    def test_unknown_thermostat_type_reads_c0227(self):
        """None (P0033 absent) is not evidence of a missing thermostat."""
        coord = _mock_coordinator()
        coord.room_thermostat_type = None
        thermostat = LuxtronikThermostat(
            MagicMock(), _mock_entry(), coord, THERMOSTATS_OTHER[0]
        )
        _update_with_room_temp(thermostat, 21.8)
        assert thermostat.current_temperature == 21.8


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


# ===========================================================================
# climate.py — unmapped mode value (M7 regression)
# ===========================================================================


class TestClimateUnmappedMode:
    def test_missing_mode_sets_hvac_and_preset_none(self):
        """No mode reported (e.g. key absent) clears both hvac and preset mode."""
        coord = _mock_coordinator()
        entry = _mock_entry()
        hass = MagicMock()

        thermostat = LuxtronikThermostat(hass, entry, coord, THERMOSTATS[0])
        _patch_entity(thermostat)
        data = make_coordinator_data(
            parameters={},
            calculations={"ID_WEB_WP_BZ_akt": LuxOperationMode.heating},
        )
        thermostat._handle_coordinator_update(data)
        assert thermostat._attr_hvac_mode is None
        assert thermostat._attr_preset_mode is None

    def test_unmapped_mode_does_not_raise(self):
        """An unexpected mode value must not raise KeyError from the coordinator listener."""
        coord = _mock_coordinator()
        entry = _mock_entry()
        hass = MagicMock()

        thermostat = LuxtronikThermostat(hass, entry, coord, THERMOSTATS[0])
        _patch_entity(thermostat)
        data = make_coordinator_data(
            parameters={"ID_Ba_Hz_akt": "unexpected_mode"},
            calculations={"ID_WEB_WP_BZ_akt": LuxOperationMode.heating},
        )
        thermostat._handle_coordinator_update(data)
        assert thermostat._attr_hvac_mode is None
        assert thermostat._attr_preset_mode is None

    def test_mapped_mode_still_works(self):
        """Known modes keep resolving to their mapped hvac/preset mode."""
        coord = _mock_coordinator()
        entry = _mock_entry()
        hass = MagicMock()

        thermostat = LuxtronikThermostat(hass, entry, coord, THERMOSTATS[0])
        _patch_entity(thermostat)
        data = make_coordinator_data(
            parameters={"ID_Ba_Hz_akt": LuxMode.party},
            calculations={"ID_WEB_WP_BZ_akt": LuxOperationMode.heating},
        )
        thermostat._handle_coordinator_update(data)
        assert thermostat._attr_hvac_mode == HVAC_MODE_MAPPING_HEAT[LuxMode.party]
        assert thermostat._attr_preset_mode == HVAC_PRESET_MAPPING[LuxMode.party]


class TestClimateKeyAttributes:
    """The luxtronik_key_current_temperature attribute names what is really read."""

    def test_current_temperature_key_attribute_names_c0227(self):
        """The attribute is built before the key is swapped in, so it has to be
        rebuilt from the final description - it used to read "NSET UNSET"."""
        coord = _mock_coordinator()
        coord.room_thermostat_type = LuxRoomThermostatType.rbe
        thermostat = LuxtronikThermostat(
            MagicMock(), _mock_entry(), coord, THERMOSTATS_OTHER[0]
        )
        attrs = thermostat._attr_extra_state_attributes
        assert attrs["luxtronik_key_current_temperature"] == (
            f"0227 {LuxCalculation.C0227_ROOM_THERMOSTAT_TEMPERATURE.value}"
        )

    def test_current_temperature_key_attribute_names_the_configured_sensor(self):
        coord = _mock_coordinator()
        coord.room_thermostat_type = LuxRoomThermostatType.none
        entry = _mock_entry()
        entry.options = {CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.my_temp"}
        thermostat = LuxtronikThermostat(
            MagicMock(), entry, coord, THERMOSTATS_OTHER[0]
        )
        attrs = thermostat._attr_extra_state_attributes
        assert attrs["luxtronik_key_current_temperature"] == "sensor.my_temp"

    def test_no_current_temperature_key_attribute_without_a_thermostat(self):
        coord = _mock_coordinator()
        coord.room_thermostat_type = LuxRoomThermostatType.none
        thermostat = LuxtronikThermostat(
            MagicMock(), _mock_entry(), coord, THERMOSTATS_OTHER[0]
        )
        attrs = thermostat._attr_extra_state_attributes
        assert "luxtronik_key_current_temperature" not in attrs

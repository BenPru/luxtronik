"""Tests for custom_components.luxtronik2.climate constants and mappings."""

from __future__ import annotations

import asyncio
from dataclasses import replace as dc_replace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_NONE,
    ClimateEntityFeature,
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
    THERMOSTATS_RBE_CALCULATED,
    THERMOSTATS_SMART,
    LuxtronikClimateExtraStoredData,
    LuxtronikRbeCalculatedThermostat,
    LuxtronikThermostat,
    rbe_correction_for_target,
    rbe_target_bounds,
    rbe_target_for_correction,
    round_correction,
)
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    CONF_RBE_CALCULATED_ROOM_TARGET,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxCalculation,
    LuxMode,
    LuxOperationMode,
    LuxParameter,
    LuxRoomThermostatType,
    SensorKey,
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
        assert d["_last_hvac_mode_before_preset"] is None


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


class TestClimatePresetReturnMode:
    """Ending a preset writes back the Luxtronik mode that was active before.

    It used to remember the HA hvac mode ("heat"), which P0003 cannot take:
    the library converts it to None, the write is dropped and the heat pump
    stays in Holidays.
    """

    @staticmethod
    def _thermostat(mode):
        coord = _mock_coordinator()
        thermostat = LuxtronikThermostat(
            MagicMock(), _mock_entry(), coord, THERMOSTATS_OTHER[0]
        )
        _patch_entity(thermostat)

        def data_for(lux_mode):
            return make_coordinator_data(
                parameters={"ID_Ba_Hz_akt": lux_mode},
                calculations={"ID_WEB_WP_BZ_akt": LuxOperationMode.heating},
            )

        async def write(name, value):
            coord.data = data_for(value)
            return coord.data

        coord.async_write = AsyncMock(side_effect=write)
        coord.data = data_for(mode)
        thermostat._handle_coordinator_update(coord.data)
        return thermostat, coord

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mode", [LuxMode.automatic, LuxMode.off, LuxMode.party])
    @pytest.mark.parametrize("preset", [PRESET_AWAY, PRESET_BOOST])
    async def test_preset_none_returns_to_previous_lux_mode(self, mode, preset):
        thermostat, coord = self._thermostat(mode)
        await thermostat.async_set_preset_mode(preset)
        await thermostat.async_set_preset_mode(PRESET_NONE)
        coord.async_write.assert_awaited_with("ID_Ba_Hz_akt", mode)

    @pytest.mark.asyncio
    async def test_return_mode_survives_a_restart(self):
        """base.py restores extra data with setattr(entity, key, value), so every
        stored field must be named exactly like the entity attribute."""
        thermostat, _ = self._thermostat(LuxMode.automatic)
        await thermostat.async_set_preset_mode(PRESET_AWAY)
        stored = thermostat.extra_restore_state_data.as_dict()

        restarted, coord = self._thermostat(LuxMode.holidays)
        restarted._last_hvac_mode_before_preset = None
        for key, value in stored.items():
            setattr(restarted, key, value)
        restarted._handle_coordinator_update(coord.data)
        await restarted.async_set_preset_mode(PRESET_NONE)
        coord.async_write.assert_awaited_with("ID_Ba_Hz_akt", LuxMode.automatic)

    def test_stored_fields_are_entity_attributes(self):
        # The RBE subclass carries every field; its own one
        # (_last_written_correction) is a harmless extra on the base class.
        for name in LuxtronikClimateExtraStoredData.__dataclass_fields__:
            assert hasattr(LuxtronikRbeCalculatedThermostat, name), name

    @pytest.mark.asyncio
    async def test_switching_between_presets_keeps_the_first_mode(self):
        thermostat, coord = self._thermostat(LuxMode.automatic)
        await thermostat.async_set_preset_mode(PRESET_AWAY)
        await thermostat.async_set_preset_mode(PRESET_BOOST)
        await thermostat.async_set_preset_mode(PRESET_NONE)
        coord.async_write.assert_awaited_with("ID_Ba_Hz_akt", LuxMode.automatic)


# ===========================================================================
# Plain RBE room target (#684)
# ===========================================================================


class TestRbeMath:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0.0, 0.0),
            (0.24, 0.0),
            (0.25, 0.5),
            (-0.25, -0.5),
            (1.7, 1.5),
            (1.75, 2.0),
            (-0.1, 0.0),
            (3.4, 3.5),
        ],
    )
    def test_round_correction(self, value, expected):
        result = round_correction(value)
        assert result == expected
        assert str(result) != "-0.0"

    def test_correction_for_target(self):
        assert rbe_correction_for_target(22.0, 20.0, 1.0) == 2.0
        assert rbe_correction_for_target(22.0, 21.0, 1.7) == 1.5
        assert rbe_correction_for_target(30.0, 20.0, 1.0) == 5.0
        assert rbe_correction_for_target(10.0, 20.0, 1.0) == -5.0

    def test_target_for_correction_round_trips(self):
        t = rbe_target_for_correction(1.5, 21.0, 1.7)
        assert t == pytest.approx(21.0 + 1.5 / 1.7)
        assert rbe_correction_for_target(t, 21.0, 1.7) == 1.5

    def test_bounds(self):
        assert rbe_target_bounds(21.0, 2.0) == (18.5, 23.5)


class TestRbeCalculatedSelection:
    @staticmethod
    async def _setup(rt, option):
        from custom_components.luxtronik2.climate import async_setup_entry

        coord = _mock_coordinator(make_coordinator_data())
        coord.room_thermostat_type = rt
        entry = MagicMock()
        entry.runtime_data = coord
        entry.data = _ENTRY_DATA.copy()
        entry.options = {CONF_RBE_CALCULATED_ROOM_TARGET: option}
        added = []
        with patch(
            "custom_components.luxtronik2.climate.key_exists", return_value=True
        ):
            await async_setup_entry(
                MagicMock(), entry, lambda entities: added.extend(entities)
            )
        return {e.entity_description.key: e for e in added}

    @pytest.mark.asyncio
    async def test_rbe_with_option_uses_calculated_heating(self):
        added = await self._setup(LuxRoomThermostatType.rbe, True)
        assert type(added[SensorKey.HEATING]) is LuxtronikRbeCalculatedThermostat
        assert type(added[SensorKey.COOLING]) is LuxtronikThermostat
        assert (
            added[SensorKey.COOLING].entity_description.luxtronik_key_target_temperature
            == THERMOSTATS_OTHER[1].luxtronik_key_target_temperature
        )

    @pytest.mark.asyncio
    async def test_rbe_without_option_is_unchanged(self):
        added = await self._setup(LuxRoomThermostatType.rbe, False)
        assert type(added[SensorKey.HEATING]) is LuxtronikThermostat
        assert (
            added[SensorKey.HEATING].entity_description.luxtronik_key_target_temperature
            == THERMOSTATS_OTHER[0].luxtronik_key_target_temperature
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "rt",
        [
            LuxRoomThermostatType.rbe_plus,
            LuxRoomThermostatType.smart,
            LuxRoomThermostatType.none,
            None,
        ],
    )
    async def test_other_types_ignore_option(self, rt):
        added = await self._setup(rt, True)
        assert type(added[SensorKey.HEATING]) is LuxtronikThermostat

    def test_calculated_description_keeps_heating_key(self):
        heating = THERMOSTATS_RBE_CALCULATED[0]
        assert heating.key == SensorKey.HEATING
        assert heating.luxtronik_key_target_temperature == LuxParameter.UNSET
        assert heating.luxtronik_key_room_target == (
            LuxCalculation.C0228_ROOM_THERMOSTAT_TEMPERATURE_TARGET
        )


def _rbe_data(p=0.0, c=21.0, factor=100):
    return make_coordinator_data(
        parameters={
            "ID_Ba_Hz_akt": LuxMode.automatic,
            "ID_Einst_WK_akt": p,
            "ID_RBE_Einflussfaktor_RT_akt": factor,
        },
        calculations={
            "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
            "ID_WEB_RBE_RT_Ist": 20.5,
            "ID_WEB_RBE_RT_Soll": c,
        },
    )


class _Rbe:
    """A calculated thermostat whose writes really run and are awaited."""

    def __init__(self, data):
        self.coord = _mock_coordinator(data)
        self.coord.room_thermostat_type = LuxRoomThermostatType.rbe
        self.tasks: list[asyncio.Task] = []
        self.entity = LuxtronikRbeCalculatedThermostat(
            MagicMock(), _mock_entry(), self.coord, THERMOSTATS_RBE_CALCULATED[0]
        )
        _patch_entity(self.entity)
        self.entity.hass.async_create_task = lambda coro, *a, **k: self.tasks.append(
            asyncio.ensure_future(coro)
        )
        self.coord.async_write = AsyncMock(side_effect=self._write)
        # Tests call _async_write_temperature directly, as the debouncer would.
        self.entity._debouncer_set_temp = MagicMock()
        self.entity._debouncer_set_temp.async_call = AsyncMock()

    async def _write(self, name, value):
        # The device accepts the value; the refresh inside async_write calls
        # the listener while the write is still in flight.
        self.coord.data.parameters.set(name, value)
        self.entity._handle_coordinator_update(self.coord.data)
        return self.coord.data

    def update(self, data=None):
        if data is not None:
            self.coord.data = data
        self.entity._handle_coordinator_update(self.coord.data)

    async def drain(self):
        while self.tasks:
            await self.tasks.pop(0)


class TestRbeCalculatedThermostat:
    @pytest.mark.asyncio
    async def test_first_run_derives_target_without_write(self):
        rbe = _Rbe(_rbe_data(p=1.5, c=21.0, factor=170))
        rbe.update()
        await rbe.drain()
        assert rbe.entity.target_temperature == pytest.approx(21.0 + 1.5 / 1.7)
        rbe.coord.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_restored_offset_from_off_mode_is_not_used_as_room_target(self):
        rbe = _Rbe(_rbe_data(p=1.0, c=21.0, factor=100))
        rbe.entity._attr_target_temperature = 1.0  # P0001 stored by off mode
        rbe.entity._last_written_correction = None
        rbe.update()
        await rbe.drain()
        assert rbe.entity.target_temperature == 22.0
        rbe.coord.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_set_temperature_writes_rounded_correction_once_and_awaits(self):
        rbe = _Rbe(_rbe_data(p=0.0, c=21.0, factor=170))
        rbe.update()
        await rbe.entity.async_set_temperature(temperature=22.0)
        await rbe.entity._async_write_temperature()  # what the debouncer calls
        await rbe.drain()
        rbe.coord.async_write.assert_awaited_once_with("ID_Einst_WK_akt", 1.5)
        assert rbe.entity.target_temperature == 22.0  # T is kept exactly

    @pytest.mark.asyncio
    async def test_rounding_at_f_1_7_does_not_loop(self):
        rbe = _Rbe(_rbe_data(p=0.0, c=21.0, factor=170))
        rbe.update()
        await rbe.entity.async_set_temperature(temperature=22.0)
        await rbe.entity._async_write_temperature()
        await rbe.drain()
        for _ in range(3):
            rbe.update()
            await rbe.drain()
        assert rbe.coord.async_write.await_count == 1

    @pytest.mark.asyncio
    async def test_own_refresh_does_not_rewrite(self):
        """_write() calls the listener mid-write; that must not schedule a 2nd write."""
        rbe = _Rbe(_rbe_data(p=0.0, c=21.0, factor=100))
        rbe.update()
        await rbe.entity.async_set_temperature(temperature=23.0)
        await rbe.entity._async_write_temperature()
        await rbe.drain()
        rbe.coord.async_write.assert_awaited_once_with("ID_Einst_WK_akt", 2.0)

    @pytest.mark.asyncio
    async def test_room_target_change_rewrites_correction(self):
        rbe = _Rbe(_rbe_data(p=1.0, c=21.0, factor=100))
        rbe.update()  # T = 22
        rbe.update(_rbe_data(p=1.0, c=20.0, factor=100))  # dial turned down
        await rbe.drain()
        rbe.coord.async_write.assert_awaited_once_with("ID_Einst_WK_akt", 2.0)
        assert rbe.entity.target_temperature == 22.0

    @pytest.mark.asyncio
    async def test_external_correction_change_moves_target(self):
        rbe = _Rbe(_rbe_data(p=1.0, c=21.0, factor=100))
        rbe.update()
        rbe.update(_rbe_data(p=-1.0, c=21.0, factor=100))
        await rbe.drain()
        assert rbe.entity.target_temperature == 20.0
        rbe.coord.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_external_correction_wins_over_room_target_change(self):
        rbe = _Rbe(_rbe_data(p=1.0, c=21.0, factor=100))
        rbe.update()
        rbe.update(_rbe_data(p=0.0, c=20.0, factor=100))
        await rbe.drain()
        assert rbe.entity.target_temperature == 20.0
        rbe.coord.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_off_grid_external_correction_is_not_rewritten(self):
        rbe = _Rbe(_rbe_data(p=1.0, c=21.0, factor=100))
        rbe.update()
        rbe.update(_rbe_data(p=0.3, c=21.0, factor=100))
        rbe.update()
        await rbe.drain()
        rbe.coord.async_write.assert_not_awaited()
        assert rbe.entity.target_temperature == pytest.approx(21.3)

    @pytest.mark.asyncio
    async def test_restored_consistent_target_does_not_write(self):
        rbe = _Rbe(_rbe_data(p=1.5, c=21.0, factor=170))
        rbe.entity._attr_target_temperature = 22.0
        rbe.entity._last_written_correction = 1.5
        rbe.update()
        await rbe.drain()
        assert rbe.entity.target_temperature == 22.0
        rbe.coord.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_restored_target_with_changed_correction_adopts_it(self):
        rbe = _Rbe(_rbe_data(p=-1.0, c=21.0, factor=100))
        rbe.entity._attr_target_temperature = 22.0
        rbe.entity._last_written_correction = 1.0  # P0001 changed while HA was down
        rbe.update()
        await rbe.drain()
        assert rbe.entity.target_temperature == 20.0
        rbe.coord.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bounds_follow_room_target_and_clamp(self):
        rbe = _Rbe(_rbe_data(p=0.0, c=21.0, factor=200))
        rbe.update()
        assert (rbe.entity.min_temp, rbe.entity.max_temp) == (18.5, 23.5)
        rbe.entity._attr_target_temperature = 23.5
        rbe.entity._last_written_correction = 0.0
        rbe.update(_rbe_data(p=0.0, c=19.0, factor=200))
        await rbe.drain()
        assert (rbe.entity.min_temp, rbe.entity.max_temp) == (16.5, 21.5)
        assert rbe.entity.target_temperature == 21.5
        rbe.coord.async_write.assert_awaited_once_with("ID_Einst_WK_akt", 5.0)

    @pytest.mark.asyncio
    async def test_set_temperature_is_clamped(self):
        rbe = _Rbe(_rbe_data(p=0.0, c=21.0, factor=100))
        rbe.update()
        await rbe.entity.async_set_temperature(temperature=35.0)
        assert rbe.entity.target_temperature == 26.0
        await rbe.entity._async_write_temperature()
        await rbe.drain()
        rbe.coord.async_write.assert_awaited_once_with("ID_Einst_WK_akt", 5.0)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "data",
        [
            _rbe_data(p=1.0, c=21.0, factor=0),
            _rbe_data(p=1.0, c=0.0, factor=100),
            _rbe_data(p=None, c=21.0, factor=100),
        ],
    )
    async def test_guard_no_target_no_write(self, data):
        rbe = _Rbe(data)
        rbe.update()
        await rbe.drain()
        assert rbe.entity.target_temperature is None
        assert not (
            rbe.entity.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
        )
        rbe.coord.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_guard_recovers_without_write(self):
        rbe = _Rbe(_rbe_data(p=1.0, c=21.0, factor=100))
        rbe.update()
        rbe.update(_rbe_data(p=1.0, c=None, factor=100))
        rbe.update(_rbe_data(p=1.0, c=21.0, factor=100))
        await rbe.drain()
        assert rbe.entity.target_temperature == 22.0
        assert rbe.entity.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
        rbe.coord.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_failed_write_backs_off(self):
        from homeassistant.exceptions import HomeAssistantError

        rbe = _Rbe(_rbe_data(p=0.0, c=21.0, factor=100))
        rbe.update()
        rbe.coord.async_write.side_effect = HomeAssistantError("refused")
        with patch(
            "custom_components.luxtronik2.climate.monotonic", return_value=1000.0
        ):
            await rbe.entity.async_set_temperature(temperature=22.0)
            await rbe.entity._async_write_temperature()
            await rbe.drain()
            rbe.update()
            await rbe.drain()
        assert rbe.coord.async_write.await_count == 1
        assert rbe.entity.target_temperature == 22.0
        with patch(
            "custom_components.luxtronik2.climate.monotonic", return_value=1601.0
        ):
            rbe.update()
            await rbe.drain()
        assert rbe.coord.async_write.await_count == 2

    @pytest.mark.asyncio
    async def test_failed_write_retries_when_inputs_change(self):
        from homeassistant.exceptions import HomeAssistantError

        rbe = _Rbe(_rbe_data(p=0.0, c=21.0, factor=100))
        rbe.update()
        rbe.coord.async_write.side_effect = HomeAssistantError("refused")
        with patch(
            "custom_components.luxtronik2.climate.monotonic", return_value=1000.0
        ):
            await rbe.entity.async_set_temperature(temperature=22.0)
            await rbe.entity._async_write_temperature()
            await rbe.drain()
            await rbe.entity.async_set_temperature(temperature=22.5)
            await rbe.entity._async_write_temperature()
            await rbe.drain()
        assert rbe.coord.async_write.await_count == 2

    def test_attributes_explain_effective_target(self):
        rbe = _Rbe(_rbe_data(p=1.5, c=21.0, factor=170))
        rbe.entity._attr_target_temperature = 22.0
        rbe.entity._last_written_correction = 1.5
        rbe.update()
        attrs = rbe.entity._attr_extra_state_attributes
        assert attrs["room_target_rbe"] == 21.0
        assert attrs["correction"] == 1.5
        assert attrs["effective_room_target"] == pytest.approx(21.88, abs=0.01)

    @pytest.mark.asyncio
    async def test_configured_indoor_sensor_is_display_only(self):
        """The HA sensor is shown as current temperature but never enters P0001."""
        rbe = _Rbe(_rbe_data(p=0.0, c=21.0, factor=100))
        entry = _mock_entry()
        entry.options = {CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.living_room"}
        rbe.entity = LuxtronikRbeCalculatedThermostat(
            MagicMock(), entry, rbe.coord, THERMOSTATS_RBE_CALCULATED[0]
        )
        _patch_entity(rbe.entity)
        rbe.entity.hass.async_create_task = lambda coro, *a, **k: rbe.tasks.append(
            asyncio.ensure_future(coro)
        )
        rbe.entity._debouncer_set_temp = MagicMock()
        rbe.entity._debouncer_set_temp.async_call = AsyncMock()
        state = MagicMock()
        state.state = "18.0"  # far below the RBE's own 20.5
        rbe.entity.hass.states.get.return_value = state
        rbe.update()
        assert rbe.entity.current_temperature == 18.0
        await rbe.entity.async_set_temperature(temperature=22.0)
        await rbe.entity._async_write_temperature()
        await rbe.drain()
        rbe.coord.async_write.assert_awaited_once_with("ID_Einst_WK_akt", 1.0)

    @pytest.mark.asyncio
    async def test_missing_poll_keeps_exact_target(self):
        """A one-poll gap hides T; it must not re-derive it from P0001 (0.25/f drift)."""
        rbe = _Rbe(_rbe_data(p=0.0, c=21.0, factor=170))
        rbe.update()
        await rbe.entity.async_set_temperature(temperature=22.0)
        await rbe.entity._async_write_temperature()
        await rbe.drain()
        rbe.update(_rbe_data(p=1.5, c=None, factor=170))
        assert rbe.entity.target_temperature is None
        rbe.update(_rbe_data(p=1.5, c=21.0, factor=170))
        await rbe.drain()
        assert rbe.entity.target_temperature == 22.0
        assert rbe.coord.async_write.await_count == 1

    @pytest.mark.asyncio
    async def test_room_target_change_during_missing_poll_still_rewrites(self):
        """D4 holds across a gap: HA's T wins over a dial change it did not see."""
        rbe = _Rbe(_rbe_data(p=0.0, c=21.0, factor=170))
        rbe.update()
        await rbe.entity.async_set_temperature(temperature=22.0)
        await rbe.entity._async_write_temperature()
        await rbe.drain()
        rbe.update(_rbe_data(p=1.5, c=None, factor=170))
        rbe.update(_rbe_data(p=1.5, c=20.0, factor=170))
        await rbe.drain()
        assert rbe.entity.target_temperature == 22.0
        rbe.coord.async_write.assert_awaited_with("ID_Einst_WK_akt", 3.5)

    def test_no_coordinator_data_is_ignored(self):
        rbe = _Rbe(_rbe_data())
        rbe.coord.data = None
        rbe.entity._handle_coordinator_update()
        rbe.coord.async_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_temperature_before_first_update_is_not_clamped(self):
        """No bounds yet: keep the value; the first update clamps and adopts."""
        rbe = _Rbe(_rbe_data())
        await rbe.entity.async_set_temperature(temperature=30.0)
        assert rbe.entity.target_temperature == 30.0

    def test_extra_restore_data_persists_last_written_correction(self):
        rbe = _Rbe(_rbe_data(p=1.0, c=21.0, factor=100))
        rbe.update()
        stored = rbe.entity.extra_restore_state_data.as_dict()
        assert stored["_last_written_correction"] == 1.0
        assert stored["_attr_target_temperature"] == 22.0

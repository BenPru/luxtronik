"""Tests for custom_components.luxtronik2.select entity classes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
import pytest

from conftest import make_coordinator_data
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxDaySelectorParameter,
    LuxParameter,
    LuxPoolPVMode,
    SensorKey,
)
from custom_components.luxtronik2.model import LuxtronikSelectEntityDescription
from custom_components.luxtronik2.select import (
    LuxtronikThermalDesinfectionDaySelector,
    _build_pv_mode_selector_description,
    build_select_descriptions,
)

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
# _build_pv_mode_selector_description
# ===========================================================================


class TestBuildPVModeSelectorDescription:
    def test_pv_off_value_returns_reduced_options(self):
        """When value is pv_off, only automatic and pv_off options are returned."""
        coord = _mock_coordinator()
        coord.get_value.return_value = LuxPoolPVMode.pv_off
        desc = LuxtronikSelectEntityDescription(
            key=SensorKey.PV_MODE_SELECTOR,
            device_key=DeviceKey.heatpump,
            luxtronik_key="test_key",
            options=["automatic", "pv_off", "pool_party", "pool_holidays", "pool_off"],
        )

        result = _build_pv_mode_selector_description(coord, desc)

        assert result.options == [
            m.value for m in (LuxPoolPVMode.automatic, LuxPoolPVMode.pv_off)
        ]

    def test_pool_mode_value_returns_all_pool_options(self):
        """When value is pool_party/pool_holidays/pool_off, all pool options are returned."""
        coord = _mock_coordinator()
        for pool_value in (
            LuxPoolPVMode.pool_party,
            LuxPoolPVMode.pool_holidays,
            LuxPoolPVMode.pool_off,
        ):
            coord.get_value.return_value = pool_value
            desc = LuxtronikSelectEntityDescription(
                key=SensorKey.PV_MODE_SELECTOR,
                device_key=DeviceKey.heatpump,
                luxtronik_key="test_key",
                options=[
                    "automatic",
                    "pv_off",
                    "pool_party",
                    "pool_holidays",
                    "pool_off",
                ],
            )

            result = _build_pv_mode_selector_description(coord, desc)

            assert result.options == [
                m.value
                for m in (
                    LuxPoolPVMode.automatic,
                    LuxPoolPVMode.pool_off,
                    LuxPoolPVMode.pool_party,
                    LuxPoolPVMode.pool_holidays,
                )
            ]

    def test_automatic_value_returns_original_description(self):
        """When value is automatic, original description is returned unchanged."""
        coord = _mock_coordinator()
        coord.get_value.return_value = LuxPoolPVMode.automatic
        desc = LuxtronikSelectEntityDescription(
            key=SensorKey.PV_MODE_SELECTOR,
            device_key=DeviceKey.heatpump,
            luxtronik_key="test_key",
            options=["automatic", "pv_off", "pool_party", "pool_holidays", "pool_off"],
        )

        result = _build_pv_mode_selector_description(coord, desc)

        assert result is desc

    def test_unknown_value_returns_original_description(self):
        """When value is unknown, original description is returned unchanged."""
        coord = _mock_coordinator()
        coord.get_value.return_value = "unknown_mode"
        desc = LuxtronikSelectEntityDescription(
            key=SensorKey.PV_MODE_SELECTOR,
            device_key=DeviceKey.heatpump,
            luxtronik_key="test_key",
            options=["automatic", "pv_off", "pool_party", "pool_holidays", "pool_off"],
        )

        result = _build_pv_mode_selector_description(coord, desc)

        assert result is desc


# ===========================================================================
# build_select_descriptions
# ===========================================================================


class TestBuildSelectDescriptions:
    def test_builds_descriptions_with_pv_mode_adjusted(self):
        """build_select_descriptions adjusts PV mode options based on current value."""
        coord = _mock_coordinator()
        coord.get_value.return_value = LuxPoolPVMode.pv_off

        descriptions = build_select_descriptions(coord)

        pv_desc = next(d for d in descriptions if d.key == SensorKey.PV_MODE_SELECTOR)
        assert pv_desc.options == [
            m.value for m in (LuxPoolPVMode.automatic, LuxPoolPVMode.pv_off)
        ]

    def test_non_pv_descriptions_unchanged(self):
        """Non-PV mode descriptions are returned unchanged."""
        coord = _mock_coordinator()
        coord.get_value.return_value = LuxPoolPVMode.automatic

        descriptions = build_select_descriptions(coord)

        for d in descriptions:
            if d.key != SensorKey.PV_MODE_SELECTOR:
                assert d.options is not None


# ===========================================================================
# raw_option_map (timer program selector)
# ===========================================================================


class TestRawOptionMap:
    def _make_selector(self, raw_value: str):
        from custom_components.luxtronik2.select import LuxtronikModeSelector

        desc = LuxtronikSelectEntityDescription(
            key=SensorKey.TIMER_DHW_PROGRAM,
            device_key=DeviceKey.domestic_water,
            luxtronik_key=LuxParameter.P0405_TIMER_PROGRAM_DHW,
            options=["week", "weekday_weekend", "daily"],
            raw_option_map={"week": "week", "weekday_weekend": "5+2", "daily": "days"},
        )
        data = make_coordinator_data(parameters={"ID_Einst_SUBW_akt2": raw_value})
        coord = _mock_coordinator(data)
        entity = LuxtronikModeSelector(
            _mock_entry(), coord, desc, DeviceKey.domestic_water
        )
        _patch_entity(entity)
        return entity, coord

    def test_options_are_the_ha_names(self):
        entity, _coord = self._make_selector("week")
        assert entity._attr_options == ["week", "weekday_weekend", "daily"]

    def test_raw_value_maps_to_ha_option(self):
        entity, _coord = self._make_selector("5+2")
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "weekday_weekend"

    @pytest.mark.asyncio
    async def test_selecting_option_writes_raw_value(self):
        entity, coord = self._make_selector("week")
        await entity.async_select_option("weekday_weekend")
        coord.async_write.assert_awaited_once_with("ID_Einst_SUBW_akt2", "5+2")

    def test_an_unrecognised_raw_value_is_warned_about_once(self):
        """The coordinator polls constantly; one bad code must not spam the log.

        The ventilation timer program's code mapping (parameter 895) is an
        inference, so a controller whose codes differ would otherwise emit
        one WARNING per poll forever. The first occurrence still warns, and
        a second, different bad value warns again.
        """
        entity, coord = self._make_selector("week")
        with patch("custom_components.luxtronik2.select.LOGGER") as logger:
            coord.data = make_coordinator_data(
                parameters={"ID_Einst_SUBW_akt2": "nonsense"}
            )
            entity._handle_coordinator_update()
            entity._handle_coordinator_update()
            entity._handle_coordinator_update()
            assert logger.warning.call_count == 1

            coord.data = make_coordinator_data(
                parameters={"ID_Einst_SUBW_akt2": "other-nonsense"}
            )
            entity._handle_coordinator_update()
            assert logger.warning.call_count == 2
        # State is untouched by an unrecognised value, as before.
        assert entity._attr_current_option is None

    def test_existing_selectors_keep_working_without_a_map(self):
        from custom_components.luxtronik2.select import LuxtronikModeSelector

        desc = LuxtronikSelectEntityDescription(
            key=SensorKey.DOMESTIC_WATER_MODE_SELECTOR,
            device_key=DeviceKey.domestic_water,
            luxtronik_key=LuxParameter.P0004_MODE_DHW,
            options=["Automatic", "Off"],
        )
        data = make_coordinator_data(parameters={"ID_Ba_Bw_akt": "Automatic"})
        entity = LuxtronikModeSelector(
            _mock_entry(), _mock_coordinator(data), desc, DeviceKey.domestic_water
        )
        _patch_entity(entity)
        entity._handle_coordinator_update()
        assert entity._attr_options == ["automatic", "off"]
        assert entity._attr_current_option == "automatic"


# ===========================================================================
# Heating and ventilation timer program selects
# ===========================================================================


class TestTimerProgramSelects:
    """The program selector of every schedule-carrying circuit is settable."""

    def _description(self, key):
        from custom_components.luxtronik2.select_entities_predefined import (
            SELECT_ENTITIES,
        )

        return next(d for d in SELECT_ENTITIES if d.key == key)

    def test_heating_program_select(self):
        description = self._description(SensorKey.TIMER_HEATING_PROGRAM)
        assert description.luxtronik_key == LuxParameter.P0222_TIMER_PROGRAM_HEATING
        assert description.device_key is DeviceKey.heating
        assert description.raw_option_map == {
            "week": "week",
            "weekday_weekend": "5+2",
            "daily": "days",
        }

    def test_ventilation_program_select(self):
        description = self._description(SensorKey.TIMER_VENTILATION_PROGRAM)
        assert description.luxtronik_key == LuxParameter.P0895_TIMER_PROGRAM_VENTILATION
        assert description.device_key is DeviceKey.ventilation
        assert description.options == ["week", "weekday_weekend", "daily"]

    def test_parameter_strings_match_the_schedule_selectors(self):
        """The select and the schedule entities must drive the same register.

        A typo in either parameter string would silently give the user a
        selector that writes somewhere else while the schedules keep reading
        the real one.
        """
        from custom_components.luxtronik2.timer_schedule_entities_predefined import (
            TIMER_SCHEDULE_ENTITIES,
        )

        selectors = {
            SensorKey.TIMER_HEATING_SCHEDULE_WEEK: (
                LuxParameter.P0222_TIMER_PROGRAM_HEATING
            ),
            SensorKey.TIMER_VENTILATION_DAY_SCHEDULE_WEEK: (
                LuxParameter.P0895_TIMER_PROGRAM_VENTILATION
            ),
            SensorKey.TIMER_VENTILATION_NIGHT_SCHEDULE_WEEK: (
                LuxParameter.P0895_TIMER_PROGRAM_VENTILATION
            ),
        }
        for schedule_key, parameter in selectors.items():
            description = next(
                d for d in TIMER_SCHEDULE_ENTITIES if d.key == schedule_key
            )
            assert parameter.value == f"parameters.{description.mode_selector_name}"


# ===========================================================================
# SmartGrid mode selector (P1030)
# ===========================================================================


class TestSmartGridModeSelector:
    """P1030 holds a four-option mode, so it must not be a switch."""

    def _description(self):
        from custom_components.luxtronik2.select_entities_predefined import (
            SELECT_ENTITIES,
        )

        return next(d for d in SELECT_ENTITIES if d.key == SensorKey.SMART_GRID_MODE)

    def _make_selector(self, raw_value):
        from custom_components.luxtronik2.select import LuxtronikModeSelector

        data = make_coordinator_data(parameters={"ID_Einst_SmartGrid": raw_value})
        coord = _mock_coordinator(data)
        entity = LuxtronikModeSelector(
            _mock_entry(), coord, self._description(), DeviceKey.heatpump
        )
        _patch_entity(entity)
        return entity, coord

    def test_p1030_is_no_longer_a_switch(self):
        """A switch toggled off and on rewrote 3 to 0 to 1, silently changing
        the user's SmartGrid variant."""
        from custom_components.luxtronik2.switch_entities_predefined import (
            SWITCHES,
        )

        assert all(
            d.luxtronik_key != LuxParameter.P1030_SMART_GRID_SWITCH for d in SWITCHES
        )

    def test_options_are_the_menu_entries(self):
        description = self._description()
        assert description.luxtronik_key == LuxParameter.P1030_SMART_GRID_SWITCH
        assert description.device_key is DeviceKey.heatpump
        assert description.options == ["off", "plus_minus", "sg_1_0", "sg_1_1"]
        # No raw_option_map: the SmartGridMode datatype does the conversion,
        # so the option name is what gets read back and written.
        assert description.raw_option_map is None

    def test_raw_value_maps_to_the_menu_entry(self):
        """The #669 unit reads 3, which the datatype decodes to "SG 1.1"."""
        entity, _coord = self._make_selector("sg_1_1")
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "sg_1_1"

    def test_switched_off_reads_as_off(self):
        entity, _coord = self._make_selector("off")
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "off"

    @pytest.mark.asyncio
    async def test_selecting_a_mode_writes_its_raw_value(self):
        entity, coord = self._make_selector("sg_1_1")
        await entity.async_select_option("sg_1_0")
        coord.async_write.assert_awaited_once_with("ID_Einst_SmartGrid", "sg_1_0")


class TestSelectOptionsSurviveTheLibraryWritePath:
    """luxtronik.Luxtronik.write drops any queued value that is not an int.

    A select whose option (or mapped raw value) is still a string after
    Parameters.set therefore writes nothing at all: the heat pump never sees
    it, and the coordinator's write confirmation then fails the call at the
    user. What saves a select is the parameter's datatype - a SelectionBase
    maps the name back to its code, an Unknown parameter does not.
    """

    def test_every_option_reaches_the_queue_as_an_int(self):
        from luxtronik.parameters import Parameters

        from custom_components.luxtronik2 import lux_overrides
        from custom_components.luxtronik2.select_entities_predefined import (
            SELECT_ENTITIES,
        )

        # The integration patches the library once per process before it ever
        # writes (connect_and_get_coordinator), and that is what gives the
        # timer programs and the two mode selectors their datatypes.
        lux_overrides.update_Luxtronik_HeatpumpCodes()
        lux_overrides.update_Luxtronik_Parameters()

        for description in SELECT_ENTITIES:
            if description.key == SensorKey.THERMAL_DESINFECTION_DAY:
                # Writes its own 0/1 day flags, not an option value.
                continue
            raw_values = (
                list(description.raw_option_map.values())
                if description.raw_option_map
                else list(description.options or [])
            )
            name = str(description.luxtronik_key).split(".")[1]
            for raw in raw_values:
                parameters = Parameters(safe=False)
                parameters.set(name, raw)
                queued = list(parameters.queue.values())
                assert queued and isinstance(queued[0], int), (
                    f"{name} option {raw!r} queues {queued!r}, "
                    "which Luxtronik.write silently discards"
                )


class TestHeatingControlCircuitModeOptions:
    """P0103's options used to be the raw digits "0"/"1"/"2", which said
    nothing to anyone reading the state."""

    def test_options_are_named(self):
        from custom_components.luxtronik2.select_entities_predefined import (
            SELECT_ENTITIES,
        )

        description = next(
            d
            for d in SELECT_ENTITIES
            if d.key == SensorKey.HEATING_CONTROL_CIRCUIT_MODE
        )
        assert description.options == [
            "heating_curve_control",
            "fixed_temperature",
            "analog_in",
        ]

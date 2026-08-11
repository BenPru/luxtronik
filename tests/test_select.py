"""Tests for custom_components.luxtronik2.select entity classes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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

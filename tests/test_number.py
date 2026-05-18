"""Tests for number.py LuxtronikNumberEntity methods."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

from conftest import make_coordinator_data
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
import pytest

from custom_components.luxtronik.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxParameter as LP,
    SensorAttrFormat,
    SensorAttrKey as SA,
    SensorKey,
)
from custom_components.luxtronik.model import (
    LuxtronikEntityAttributeDescription,
    LuxtronikNumberDescription,
)
from custom_components.luxtronik.number import LuxtronikNumberEntity

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


def _make_number_entity(data=None, description=None):
    hass = MagicMock()
    entry = _mock_entry()
    coord = _mock_coordinator(data)
    if description is None:
        description = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
        )
    entity = LuxtronikNumberEntity(hass, entry, coord, description, DeviceKey.heating)
    _patch_entity(entity)
    return entity


# ===========================================================================
# _handle_coordinator_update
# ===========================================================================


class TestNumberHandleCoordinatorUpdate:
    def test_none_data_returns_early(self):
        entity = _make_number_entity()
        entity.coordinator.data = None
        entity._handle_coordinator_update(None)
        entity.async_write_ha_state.assert_not_called()

    def test_none_value(self):
        data = make_coordinator_data(parameters={"ID_Einst_WK_akt": None})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
        )
        entity = _make_number_entity(data, desc)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None

    def test_numeric_with_factor_and_precision(self):
        data = make_coordinator_data(parameters={"ID_Einst_WK_akt": 50})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
            factor=0.1,
            native_precision=1,
        )
        entity = _make_number_entity(data, desc)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 5.0

    def test_string_passthrough(self):
        data = make_coordinator_data(parameters={"ID_Einst_WK_akt": "text"})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
        )
        entity = _make_number_entity(data, desc)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == "text"


# ===========================================================================
# async_set_native_value + debounce
# ===========================================================================


class TestNumberAsyncSetValue:
    @pytest.mark.asyncio
    async def test_set_native_value_stores_pending(self):
        entity = _make_number_entity()
        entity._debouncer = MagicMock()
        entity._debouncer.async_call = AsyncMock()
        await entity.async_set_native_value(42.0)
        assert entity._pending_value == 42.0
        entity._debouncer.async_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_set_native_value_with_factor(self):
        data = make_coordinator_data(parameters={"ID_Einst_WK_akt": 50})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
            factor=0.1,
        )
        entity = _make_number_entity(data, desc)
        entity._pending_value = 5.0
        await entity._async_set_native_value()
        entity.coordinator.async_write.assert_awaited_once_with("ID_Einst_WK_akt", 50)

    @pytest.mark.asyncio
    async def test_async_set_native_value_none_pending(self):
        entity = _make_number_entity()
        entity._pending_value = None
        await entity._async_set_native_value()
        entity.coordinator.async_write.assert_not_awaited()


# ===========================================================================
# formatted_data (TIMESTAMP_LAST_OVER)
# ===========================================================================


class TestNumberFormattedData:
    def test_non_timestamp_delegates_to_super(self):
        entity = _make_number_entity()
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
        )
        result = entity.formatted_data(attr)
        assert isinstance(result, str)

    def test_timestamp_last_over_none_value(self):
        data = make_coordinator_data(parameters={})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
            factor=0.1,
        )
        entity = _make_number_entity(data, desc)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            format=SensorAttrFormat.TIMESTAMP_LAST_OVER,
        )
        result = entity.formatted_data(attr)
        assert result == ""

    def test_timestamp_last_over_with_value_above_threshold(self):
        data = make_coordinator_data(parameters={"ID_Einst_WK_akt": 100})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
            factor=0.1,
        )
        entity = _make_number_entity(data, desc)
        entity._attr_state = 5.0  # 5.0 * 0.1 = 0.5, value=100 >= 0.5
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            format=SensorAttrFormat.TIMESTAMP_LAST_OVER,
        )
        result = entity.formatted_data(attr)
        # Should set cache and return today's date
        assert result != ""

    def test_timestamp_last_over_cached_result(self):
        data = make_coordinator_data(parameters={"ID_Einst_WK_akt": 100})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
            factor=0.1,
        )
        entity = _make_number_entity(data, desc)
        entity._attr_state = 5.0
        entity._attr_cache[SA.TIMER_HEATPUMP_ON] = date(2099, 12, 31)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            format=SensorAttrFormat.TIMESTAMP_LAST_OVER,
        )
        result = entity.formatted_data(attr)
        assert "2099" in result


# ===========================================================================
# _is_past
# ===========================================================================


class TestIsPast:
    def test_none_is_past(self):
        entity = _make_number_entity()
        assert entity._is_past(None) is True

    def test_empty_string_is_past(self):
        entity = _make_number_entity()
        assert entity._is_past("") is True

    def test_past_date_string(self):
        entity = _make_number_entity()
        assert entity._is_past("2020-01-01") is True

    def test_future_date(self):
        entity = _make_number_entity()
        future = date(2099, 12, 31)
        assert entity._is_past(future) is False

    def test_invalid_date_string(self):
        entity = _make_number_entity()
        assert entity._is_past("not-a-date") is True

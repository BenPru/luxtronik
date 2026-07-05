"""Tests for number.py LuxtronikNumberEntity methods."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

from conftest import make_coordinator_data
from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TIMEOUT,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
import pytest

from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    DeviceKey,
    LuxParameter as LP,
    SensorAttrFormat,
    SensorAttrKey as SA,
    SensorKey,
)
from custom_components.luxtronik2.coordinator import LuxtronikCoordinator
from custom_components.luxtronik2.model import (
    LuxtronikCoordinatorData,
    LuxtronikEntityAttributeDescription,
    LuxtronikNumberDescription,
)
from custom_components.luxtronik2.number import LuxtronikNumberEntity

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


def _make_coordinator_direct(data=None):
    """Create a real coordinator with data for visibility tests."""
    coord = object.__new__(LuxtronikCoordinator)
    coord._lock = MagicMock()
    coord.hass = MagicMock()
    coord.client = MagicMock()
    coord._config = {"host": "1.2.3.4", "port": 8889}
    coord.device_infos = {}
    coord.update_reason_write = False
    coord.async_request_refresh = MagicMock()
    coord.async_refresh = MagicMock()
    coord.update_interval = DEFAULT_UPDATE_INTERVAL
    if data is None:
        data = LuxtronikCoordinatorData(
            parameters={"ID_WEB_WP_BZ_akt": (0, 0)},
            calculations={"ID_WEB_WP_BZ_akt": (0, 0)},
            visibilities={"ID_WEB_Sichtbar_Solar": (0, 1)},
        )
    coord.data = data
    return coord


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
# DHW MANUAL FREQUENCY
# ===========================================================================


class TestDHWManualFrequency:
    def _make_freq_entity(self, data=None, raw_value=0):
        from custom_components.luxtronik2.lux_overrides import (
            update_Luxtronik_Parameters,
        )

        update_Luxtronik_Parameters()
        if data is None:
            data = make_coordinator_data(
                parameters={"ID_Einst_P155_DHW_Freq": raw_value}
            )
        desc = LuxtronikNumberDescription(
            key=SensorKey.DHW_MANUAL_FREQUENCY,
            luxtronik_key=LP.P1045_DHW_FREQUENCY_CONTROL,
            device_key=DeviceKey.domestic_water,
        )
        entity = _make_number_entity(data, desc)
        entity._handle_coordinator_update(data)
        return entity

    def test_state_returns_zero_for_automatic(self):
        entity = self._make_freq_entity(raw_value=0)
        assert entity.state == 0

    def test_state_returns_hz_for_manual(self):
        entity = self._make_freq_entity(raw_value=25)
        # Simulate what the real FrequencyAutomatic datatype would produce
        entity._attr_native_value = 45
        assert entity.state == 45

    def test_extra_state_attributes_automatic(self):
        entity = self._make_freq_entity(raw_value=0)
        assert entity.extra_state_attributes == {"mode": "Automatic"}

    def test_extra_state_attributes_manual(self):
        entity = self._make_freq_entity(raw_value=25)
        entity._attr_native_value = 45
        assert entity.extra_state_attributes == {"mode": "Manual at 45 Hz"}

    def test_extra_state_attributes_none_value(self):
        data = make_coordinator_data(parameters={"ID_Einst_P155_DHW_Freq": None})
        desc = LuxtronikNumberDescription(
            key=SensorKey.DHW_MANUAL_FREQUENCY,
            luxtronik_key=LP.P1045_DHW_FREQUENCY_CONTROL,
            device_key=DeviceKey.domestic_water,
        )
        entity = _make_number_entity(data, desc)
        entity._handle_coordinator_update(data)
        assert entity.extra_state_attributes == {}

    def test_extra_state_attributes_other_keys_returns_empty(self):
        data = make_coordinator_data(parameters={"ID_Einst_WK_akt": 50})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
        )
        entity = _make_number_entity(data, desc)
        assert entity.extra_state_attributes == {}

    @pytest.mark.asyncio
    async def test_rejects_invalid_frequency_between_0_and_20(self):
        entity = self._make_freq_entity()
        entity._debouncer = MagicMock()
        entity._debouncer.async_call = AsyncMock()
        await entity.async_set_native_value(5.0)
        assert entity._pending_value is None
        entity.coordinator.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_accepts_zero(self):
        entity = self._make_freq_entity()
        entity._debouncer = MagicMock()
        entity._debouncer.async_call = AsyncMock()
        await entity.async_set_native_value(0.0)
        assert entity._pending_value == 0.0
        entity._debouncer.async_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_accepts_twenty(self):
        entity = self._make_freq_entity()
        entity._debouncer = MagicMock()
        entity._debouncer.async_call = AsyncMock()
        await entity.async_set_native_value(20.0)
        assert entity._pending_value == 20.0
        entity._debouncer.async_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_writes_raw_value(self):
        entity = self._make_freq_entity()
        entity._pending_value = 45.0
        await entity._async_set_native_value()
        entity.coordinator.async_write.assert_awaited_once_with(
            "ID_Einst_P155_DHW_Freq", 45.0
        )

    @pytest.mark.asyncio
    async def test_writes_zero_raw_value(self):
        entity = self._make_freq_entity()
        entity._pending_value = 0.0
        await entity._async_set_native_value()
        entity.coordinator.async_write.assert_awaited_once_with(
            "ID_Einst_P155_DHW_Freq", 0
        )


# ===========================================================================
# _is_past
# ===========================================================================


class TestCoolingTargetTemperatureDynamicMinMax:
    def test_dynamic_min_value_from_parameter(self):
        data = make_coordinator_data(parameters={"ID_Einst_min_VL_Kuehl": 15.0})
        desc = LuxtronikNumberDescription(
            key=SensorKey.COOLING_TARGET_TEMPERATURE_MK1,
            luxtronik_key=LP.P0132_COOLING_TARGET_TEMPERATURE_MK1,
            device_key=DeviceKey.cooling,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            native_min_value=18.0,
            native_max_value=30.0,
            native_step=0.5,
            mode=NumberMode.BOX,
            visibility=LP.P0042_MIXING_CIRCUIT1_TYPE,
            min_value_luxtronik_key=LP.P0993_COOLING_MIN_FLOW_OUT_TEMPERATURE,
        )
        entity = _make_number_entity(data, desc)
        assert entity.native_min_value == 15.0
        assert entity.native_max_value == 30.0

    def test_fallback_to_static_min_when_parameter_missing(self):
        data = make_coordinator_data()
        desc = LuxtronikNumberDescription(
            key=SensorKey.COOLING_TARGET_TEMPERATURE_MK1,
            luxtronik_key=LP.P0132_COOLING_TARGET_TEMPERATURE_MK1,
            device_key=DeviceKey.cooling,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            native_min_value=18.0,
            native_max_value=30.0,
            native_step=0.5,
            mode=NumberMode.BOX,
            min_value_luxtronik_key=LP.P0993_COOLING_MIN_FLOW_OUT_TEMPERATURE,
        )
        entity = _make_number_entity(data, desc)
        assert entity.native_min_value == 18.0
        assert entity.native_max_value == 30.0

    def test_invalid_dynamic_min_falls_back_to_static(self):
        data = make_coordinator_data(
            parameters={"ID_Einst_min_VL_Kuehl": "not_a_number"}
        )
        desc = LuxtronikNumberDescription(
            key=SensorKey.COOLING_TARGET_TEMPERATURE_MK1,
            luxtronik_key=LP.P0132_COOLING_TARGET_TEMPERATURE_MK1,
            device_key=DeviceKey.cooling,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            native_min_value=18.0,
            native_max_value=30.0,
            native_step=0.5,
            mode=NumberMode.BOX,
            min_value_luxtronik_key=LP.P0993_COOLING_MIN_FLOW_OUT_TEMPERATURE,
        )
        entity = _make_number_entity(data, desc)
        assert entity.native_min_value == 18.0
        assert entity.native_max_value == 30.0

    def test_invalid_dynamic_max_falls_back_to_static(self):
        data = make_coordinator_data(
            parameters={
                "ID_Einst_MK1Typ_akt": "not_a_number",
            }
        )
        desc = LuxtronikNumberDescription(
            key=SensorKey.COOLING_TARGET_TEMPERATURE_MK1,
            luxtronik_key=LP.P0132_COOLING_TARGET_TEMPERATURE_MK1,
            device_key=DeviceKey.cooling,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            native_min_value=18.0,
            native_max_value=30.0,
            native_step=0.5,
            mode=NumberMode.BOX,
            min_value_luxtronik_key=LP.P0993_COOLING_MIN_FLOW_OUT_TEMPERATURE,
            max_value_luxtronik_key=LP.P0042_MIXING_CIRCUIT1_TYPE,
        )
        entity = _make_number_entity(data, desc)
        assert entity.native_min_value == 18.0
        assert entity.native_max_value == 30.0


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


class TestEfficiencyPump:
    def test_efficiency_pump_voltage(self):
        data = make_coordinator_data(
            parameters={"ID_Einst_Effizienzpumpe_Nominal_akt": 500}
        )
        desc_volt = LuxtronikNumberDescription(
            key=SensorKey.EFFICIENCY_PUMP_NOMINAL_VOLTAGE,
            luxtronik_key=LP.P0867_EFFICIENCY_PUMP_NOMINAL,
            translation_key_name=SensorKey.EFFICIENCY_PUMP_NOMINAL_VOLTAGE,
            device_class=NumberDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            native_min_value=3,
            native_max_value=10,
            native_step=0.1,
            factor=0.01,
            mode=NumberMode.BOX,
        )

        entity = _make_number_entity(data, desc_volt)
        entity._handle_coordinator_update(data)

        assert entity._attr_native_value == 5.0

    def test_efficiency_pump_percentage(self):
        data = make_coordinator_data(
            parameters={"ID_Einst_Effizienzpumpe_Nominal_akt": 50}
        )
        desc_percent = LuxtronikNumberDescription(
            key=SensorKey.EFFICIENCY_PUMP_NOMINAL_PERCENTAGE,
            luxtronik_key=LP.P0867_EFFICIENCY_PUMP_NOMINAL,
            translation_key_name=SensorKey.EFFICIENCY_PUMP_NOMINAL_PERCENTAGE,
            device_class=NumberDeviceClass.SPEED,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0,
            native_max_value=100,
            native_step=1,
            mode=NumberMode.BOX,
        )
        entity = _make_number_entity(data, desc_percent)
        entity._handle_coordinator_update(data)

        assert entity._attr_native_value == 50.0

    def test_efficiency_pump_visibility_formula_high_value(self):
        data = make_coordinator_data(
            parameters={"ID_Einst_Effizienzpumpe_Nominal_akt": 500}
        )
        desc_volt = LuxtronikNumberDescription(
            key=SensorKey.EFFICIENCY_PUMP_NOMINAL_VOLTAGE,
            luxtronik_key=LP.P0867_EFFICIENCY_PUMP_NOMINAL,
            visibility=LP.P0867_EFFICIENCY_PUMP_NOMINAL,
            visibility_formula="> 100",
        )
        desc_percent = LuxtronikNumberDescription(
            key=SensorKey.EFFICIENCY_PUMP_NOMINAL_PERCENTAGE,
            luxtronik_key=LP.P0867_EFFICIENCY_PUMP_NOMINAL,
            visibility=LP.P0867_EFFICIENCY_PUMP_NOMINAL,
            visibility_formula="<= 100",
        )
        # Real coordinator to evaluate visibility formulas
        coord = _make_coordinator_direct(data)
        assert coord.entity_visible(desc_volt) is True
        assert coord.entity_visible(desc_percent) is False

    def test_efficiency_pump_visibility_formula_low_value(self):
        data = make_coordinator_data(
            parameters={"ID_Einst_Effizienzpumpe_Nominal_akt": 50}
        )
        desc_volt = LuxtronikNumberDescription(
            key=SensorKey.EFFICIENCY_PUMP_NOMINAL_VOLTAGE,
            luxtronik_key=LP.P0867_EFFICIENCY_PUMP_NOMINAL,
            visibility=LP.P0867_EFFICIENCY_PUMP_NOMINAL,
            visibility_formula="> 100",
        )
        desc_percent = LuxtronikNumberDescription(
            key=SensorKey.EFFICIENCY_PUMP_NOMINAL_PERCENTAGE,
            luxtronik_key=LP.P0867_EFFICIENCY_PUMP_NOMINAL,
            visibility=LP.P0867_EFFICIENCY_PUMP_NOMINAL,
            visibility_formula="<= 100",
        )
        coord = _make_coordinator_direct(data)
        assert coord.entity_visible(desc_volt) is False
        assert coord.entity_visible(desc_percent) is True

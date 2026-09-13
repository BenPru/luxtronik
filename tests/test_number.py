"""Tests for number.py LuxtronikNumberEntity methods."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

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

from conftest import make_coordinator_data
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
from custom_components.luxtronik2.number_entities_predefined import NUMBER_SENSORS
from custom_components.luxtronik2.water_heater import WATER_HEATERS

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
        """Regression: DHW_THERMAL_DESINFECTION_TARGET (the only real entity
        using TIMESTAMP_LAST_OVER) declares no `factor` - the comparison
        must work against `_attr_native_value` directly, not silently no-op
        because `entity_description.factor` is None."""
        data = make_coordinator_data(parameters={"ID_Einst_WK_akt": 100})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
        )
        entity = _make_number_entity(data, desc)
        entity._attr_native_value = 50.0  # value=100 >= 50.0
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            format=SensorAttrFormat.TIMESTAMP_LAST_OVER,
        )
        result = entity.formatted_data(attr)
        # Should set cache and return today's date
        assert result != ""

    def test_timestamp_last_over_below_threshold_stays_empty(self):
        data = make_coordinator_data(parameters={"ID_Einst_WK_akt": 40})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
        )
        entity = _make_number_entity(data, desc)
        entity._attr_native_value = 50.0  # value=40 < 50.0
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            format=SensorAttrFormat.TIMESTAMP_LAST_OVER,
        )
        result = entity.formatted_data(attr)
        assert result == ""

    def test_timestamp_last_over_cached_result(self):
        data = make_coordinator_data(parameters={"ID_Einst_WK_akt": 100})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
        )
        entity = _make_number_entity(data, desc)
        entity._attr_native_value = 50.0
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

    # Every entity's `_attr_extra_state_attributes` always carries a
    # diagnostic Luxtronik_Key entry, set unconditionally in base.py's
    # __init__ - the merged `extra_state_attributes` property must preserve
    # it rather than replacing the dict outright (that was the regression).
    _FREQ_LUXTRONIK_KEY_ATTR = {
        SA.LUXTRONIK_KEY.value: "1045 parameters.ID_Einst_P155_DHW_Freq"
    }
    _CORRECTION_LUXTRONIK_KEY_ATTR = {
        SA.LUXTRONIK_KEY.value: "0001 parameters.ID_Einst_WK_akt"
    }

    def test_extra_state_attributes_automatic(self):
        entity = self._make_freq_entity(raw_value=0)
        assert entity.extra_state_attributes == {
            **self._FREQ_LUXTRONIK_KEY_ATTR,
            "mode": "Automatic",
        }

    def test_extra_state_attributes_manual(self):
        entity = self._make_freq_entity(raw_value=25)
        entity._attr_native_value = 45
        assert entity.extra_state_attributes == {
            **self._FREQ_LUXTRONIK_KEY_ATTR,
            "mode": "Manual at 45 Hz",
        }

    def test_extra_state_attributes_none_value(self):
        data = make_coordinator_data(parameters={"ID_Einst_P155_DHW_Freq": None})
        desc = LuxtronikNumberDescription(
            key=SensorKey.DHW_MANUAL_FREQUENCY,
            luxtronik_key=LP.P1045_DHW_FREQUENCY_CONTROL,
            device_key=DeviceKey.domestic_water,
        )
        entity = _make_number_entity(data, desc)
        entity._handle_coordinator_update(data)
        assert entity.extra_state_attributes == self._FREQ_LUXTRONIK_KEY_ATTR

    def test_extra_state_attributes_other_keys_omit_mode(self):
        data = make_coordinator_data(parameters={"ID_Einst_WK_akt": 50})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
        )
        entity = _make_number_entity(data, desc)
        assert entity.extra_state_attributes == self._CORRECTION_LUXTRONIK_KEY_ATTR

    def test_extra_state_attributes_preserves_base_attributes_for_other_keys(self):
        """Regression: the DHW-frequency 'mode' special case must merge with,
        not discard, extra_attributes the base entity computed for other
        Number entities (e.g. the DHW thermal desinfection target's
        last_thermal_desinfection)."""
        data = make_coordinator_data(parameters={"ID_Einst_WK_akt": 50})
        desc = LuxtronikNumberDescription(
            key=SensorKey.HEATING_TARGET_CORRECTION,
            luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
            device_key=DeviceKey.heating,
            extra_attributes=(
                LuxtronikEntityAttributeDescription(
                    key=SA.LAST_THERMAL_DESINFECTION,
                    luxtronik_key=LP.P0001_HEATING_TARGET_CORRECTION,
                ),
            ),
        )
        entity = _make_number_entity(data, desc)
        entity._handle_coordinator_update(data)
        assert entity.extra_state_attributes == {
            **self._CORRECTION_LUXTRONIK_KEY_ATTR,
            SA.LAST_THERMAL_DESINFECTION.value: "50",
        }

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


# ===========================================================================
# Firmware gates must be series-agnostic
# ===========================================================================


def _coord_on_firmware(version: str) -> LuxtronikCoordinator:
    """Build a real coordinator reporting `version` as its firmware."""
    return _make_coordinator_direct(
        make_coordinator_data(calculations={"ID_WEB_SoftStand": version})
    )


def _number_desc(key: SensorKey, lux_key: str, **match) -> LuxtronikNumberDescription:
    """Return the single predefined number description matching the criteria."""
    found = [
        d
        for d in NUMBER_SENSORS
        if d.key == key
        and d.luxtronik_key == lux_key
        and all(getattr(d, name) == value for name, value in match.items())
    ]
    assert len(found) == 1, f"expected exactly one description, got {len(found)}"
    return found[0]


class TestFirmwareGatesAreSeriesAgnostic:
    """Register-availability gates must compare the minor version only.

    The firmware major digit is the controller *series* - V1.x, V2.x and
    V3.x are different hardware generations - and it never advances on a
    firmware update. The minor digit is what tracks the register layout, so
    a V1.90.1 controller carries the same registers as a V3.90.1 one.

    An absolute `Version("3.90.1")` gate compares 1.90.1 as older than
    everything, so every V1.x and V2.x owner is served the pre-90.1 entity
    set no matter how current their firmware is. Use the `*_minor` fields;
    for a genuine per-generation difference use `coordinator.firmware_series`.
    """

    def test_dhw_target_modern_register_active_on_v1(self):
        """P0105 is the 88.3+ DHW setpoint and must reach a V1.90.1 unit."""
        coord = _coord_on_firmware("V1.90.1")
        desc = _number_desc(
            SensorKey.DHW_TARGET_TEMPERATURE, LP.P0105_DHW_TARGET_TEMPERATURE
        )
        assert coord._is_version_not_compatible(desc) is False

    def test_dhw_target_legacy_register_hidden_on_v1(self):
        """P0002 is the pre-88.3 setpoint; a V1.90.1 unit must not get it."""
        coord = _coord_on_firmware("V1.90.1")
        desc = _number_desc(
            SensorKey.DHW_TARGET_TEMPERATURE, LP.P0002_DHW_TARGET_TEMPERATURE
        )
        assert coord._is_version_not_compatible(desc) is True

    def test_dhw_target_legacy_register_active_on_v2_below_cutover(self):
        """A V2.88.0 unit predates the 88.3 change and keeps P0002."""
        coord = _coord_on_firmware("V2.88.0")
        desc = _number_desc(
            SensorKey.DHW_TARGET_TEMPERATURE, LP.P0002_DHW_TARGET_TEMPERATURE
        )
        assert coord._is_version_not_compatible(desc) is False

    def test_dhw_target_modern_register_still_active_on_v3(self):
        """Regression guard: the V3 behaviour the absolute gates got right."""
        coord = _coord_on_firmware("V3.90.1")
        desc = _number_desc(
            SensorKey.DHW_TARGET_TEMPERATURE, LP.P0105_DHW_TARGET_TEMPERATURE
        )
        assert coord._is_version_not_compatible(desc) is False

    def test_dhw_target_modern_register_active_on_v1_90_0(self):
        """Issue #785: a V1.90.0 unit controls on P0105 and ignores P0002.

        Measured on the reporter's WZS 101 H/K: with P0002 written to 58 and
        P0105 left at 54, the compressor cut in at 48 and out at 54 - exactly
        P0105 with the 6 K hysteresis - without anyone touching the panel. So
        P0002 is inert there and the number entity must expose P0105, which
        moves the cutover below 90.0.
        """
        coord = _coord_on_firmware("V1.90.0")
        assert (
            coord._is_version_not_compatible(
                _number_desc(
                    SensorKey.DHW_TARGET_TEMPERATURE, LP.P0105_DHW_TARGET_TEMPERATURE
                )
            )
            is False
        )
        assert (
            coord._is_version_not_compatible(
                _number_desc(
                    SensorKey.DHW_TARGET_TEMPERATURE, LP.P0002_DHW_TARGET_TEMPERATURE
                )
            )
            is True
        )

    def test_dhw_target_number_and_water_heater_share_one_cutover(self):
        """Both platforms expose the same physical setpoint, so they must
        switch registers at the same firmware minor - otherwise the number
        entity and the water heater card show two different targets and
        write two different registers (the divergence recorded in
        DHW_TARGET_REGISTERS.md)."""

        def gates(descs, key, register_attr):
            return {
                getattr(d, register_attr): (
                    d.min_firmware_version_minor,
                    d.max_firmware_version_minor,
                )
                for d in descs
                if d.key == key
            }

        number_gates = gates(
            NUMBER_SENSORS, SensorKey.DHW_TARGET_TEMPERATURE, "luxtronik_key"
        )
        heater_gates = gates(
            WATER_HEATERS, SensorKey.DOMESTIC_WATER, "luxtronik_key_target_temperature"
        )
        assert number_gates == heater_gates

    def test_cooling_threshold_wide_range_active_on_v2(self):
        """The 92.1+ cooling threshold spans 10-35 C and must reach V2.92.1."""
        coord = _coord_on_firmware("V2.92.1")
        desc = _number_desc(
            SensorKey.COOLING_OUTDOOR_TEMP_THRESHOLD,
            LP.P0110_COOLING_OUTDOOR_TEMP_THRESHOLD,
            native_min_value=10.0,
        )
        assert coord._is_version_not_compatible(desc) is False

    def test_cooling_threshold_narrow_range_hidden_on_v2(self):
        """The pre-92.1 variant spans 18-30 C and must not reach V2.92.1."""
        coord = _coord_on_firmware("V2.92.1")
        desc = _number_desc(
            SensorKey.COOLING_OUTDOOR_TEMP_THRESHOLD,
            LP.P0110_COOLING_OUTDOOR_TEMP_THRESHOLD,
            native_min_value=18.0,
        )
        assert coord._is_version_not_compatible(desc) is True

    @pytest.mark.parametrize(
        "firmware",
        [
            "V1.88.0",
            "V1.90",  # no patch digit -> minor 90.0
            "V1.90.0",
            "V1.90.1",
            "V1.92.0",
            "V1.92.1",
            "V2.88.0",
            "V2.92.0",
            "V2.92.1",
            "V3.90.0",
            "V3.90.1",
            "V3.92.1",
            "not a version",  # unparsable -> Version("0") -> minor 0.0
        ],
    )
    def test_exactly_one_variant_of_each_pair_is_active(self, firmware):
        """Exactly one variant of each gated pair may clear the version gate.

        Each pair shares one SensorKey, and number.py derives both
        `entity_id` and `unique_id` from that key alone - so the two
        variants are one entity, differing only in which register backs it
        (DHW) or how wide its range is (cooling). That is why correcting
        these gates needs no entity registry migration, and it is why the
        two gates of a pair have to stay complementary: overlapping ones
        would have two descriptions claiming one id.

        This asserts the version gate only. Whether an entity is actually
        created also depends on `entity_active` and on the register being
        present (number.py:66-69), so a passing case here does not by
        itself prove exactly one entity is built.

        Unlike the tests above, this one also passes before the firmware
        minor fix - the absolute gates were complementary too. It guards
        the shared-id property against future gate edits, not the bug.
        """
        coord = _coord_on_firmware(firmware)
        for key in (
            SensorKey.DHW_TARGET_TEMPERATURE,
            SensorKey.COOLING_OUTDOOR_TEMP_THRESHOLD,
        ):
            variants = [d for d in NUMBER_SENSORS if d.key == key]
            assert len(variants) == 2, f"{key} is no longer a gated pair"
            active = [d for d in variants if not coord._is_version_not_compatible(d)]
            assert len(active) == 1, (
                f"{key} on {firmware}: {len(active)} active variants, expected 1"
            )

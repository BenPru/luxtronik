"""Tests for LuxtronikCopSensorEntity (instantaneous COP)."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT

from conftest import make_coordinator_data
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxCalculation as LC,
    LuxOperationMode,
    SensorKey,
)
from custom_components.luxtronik2.model import LuxtronikCopSensorDescription
from custom_components.luxtronik2.sensor import LuxtronikCopSensorEntity

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


def _mock_coordinator(data):
    coord = MagicMock()
    coord.data = data
    coord.last_update_success = True
    coord.entity_active.return_value = True
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    return coord


def _heating_cop_description() -> LuxtronikCopSensorDescription:
    return LuxtronikCopSensorDescription(
        key=SensorKey.COP_HEATING,
        device_key=DeviceKey.heating,
        numerator_key=LC.C0257_CURRENT_HEAT_OUTPUT,
        denominator_key=LC.C0268_CURRENT_POWER_CONSUMPTION,
        required_status=LuxOperationMode.heating,
    )


def _make_entity(data, description=None):
    hass = MagicMock()
    entry = _mock_entry()
    coord = _mock_coordinator(data)
    description = description or _heating_cop_description()
    entity = LuxtronikCopSensorEntity(
        hass, entry, coord, description, DeviceKey.heating
    )
    entity.hass = hass
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    return entity


class TestCopSensorHandleCoordinatorUpdate:
    def test_computes_ratio_when_status_matches(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,  # compressor running
                "Heat_Output": 6000,
                "Unknown_Calculation_268": 1500,
            }
        )
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 4.0
        assert entity._attr_available is True

    def test_unavailable_when_status_does_not_match(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.domestic_water,
                "Heat_Output": 6000,
                "Unknown_Calculation_268": 1500,
            }
        )
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None
        assert entity._attr_available is False

    def test_unavailable_when_denominator_zero(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,
                "Heat_Output": 6000,
                "Unknown_Calculation_268": 0,
            }
        )
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None
        assert entity._attr_available is False

    def test_unavailable_when_values_missing(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,
                "Heat_Output": None,
                "Unknown_Calculation_268": None,
            }
        )
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None
        assert entity._attr_available is False

    def test_uses_external_power_sensor_when_configured(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,
                "Heat_Output": 6000,
                # Deliberately different from the external value below, to
                # prove the external sensor takes priority, not just that
                # it's "also read".
                "Unknown_Calculation_268": 999999,
            }
        )
        entry = _mock_entry()
        entry.options = {
            CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION: "sensor.shelly_power"
        }
        hass = MagicMock()
        external_state = MagicMock()
        external_state.state = "1500"
        hass.states.get.return_value = external_state
        coord = _mock_coordinator(data)
        description = _heating_cop_description()
        entity = LuxtronikCopSensorEntity(
            hass, entry, coord, description, DeviceKey.heating
        )
        entity.hass = hass
        entity.hass.config.time_zone = "UTC"
        entity.async_write_ha_state = MagicMock()

        entity._handle_coordinator_update(data)

        hass.states.get.assert_called_with("sensor.shelly_power")
        assert entity._attr_native_value == 4.0
        assert entity._attr_available is True

    def test_external_power_sensor_unavailable_makes_entity_unavailable(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,
                "Heat_Output": 6000,
                "Unknown_Calculation_268": 1500,
            }
        )
        entry = _mock_entry()
        entry.options = {
            CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION: "sensor.shelly_power"
        }
        hass = MagicMock()
        hass.states.get.return_value = None
        coord = _mock_coordinator(data)
        description = _heating_cop_description()
        entity = LuxtronikCopSensorEntity(
            hass, entry, coord, description, DeviceKey.heating
        )
        entity.hass = hass
        entity.hass.config.time_zone = "UTC"
        entity.async_write_ha_state = MagicMock()

        entity._handle_coordinator_update(data)

        assert entity._attr_native_value is None
        assert entity._attr_available is False

    def test_no_external_sensor_configured_uses_internal_value(self):
        # Regression guard: entry.options == {} (the _mock_entry() default)
        # must still take the internal C0268 path, unchanged from before
        # this feature existed.
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,
                "Heat_Output": 6000,
                "Unknown_Calculation_268": 1500,
            }
        )
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 4.0
        assert entity._attr_available is True

    def test_none_data_returns_early(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,
                "Heat_Output": 6000,
                "Unknown_Calculation_268": 1500,
            }
        )
        entity = _make_entity(data)
        entity.coordinator.data = None
        entity._handle_coordinator_update(None)
        entity.async_write_ha_state.assert_not_called()

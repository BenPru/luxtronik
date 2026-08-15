"""Tests for LuxtronikSumSensorEntity (registers totalled into one quantity).

The concrete case is the additional heat generator's lifetime energy, which
the controller splits across parameters 1059 and 1140 at a firmware change
(#733). The three firmware eras a unit can be in are covered below.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, UnitOfEnergy

from conftest import make_coordinator_data
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxParameter as LP,
    SensorKey,
)
from custom_components.luxtronik2.model import LuxtronikSumSensorDescription
from custom_components.luxtronik2.sensor import LuxtronikSumSensorEntity
from custom_components.luxtronik2.sensor_entities_predefined import SENSORS_SUM

_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
    CONF_HA_SENSOR_PREFIX: DOMAIN,
}

# Raw register names as the upstream library exposes them.
_P1059 = "ID_Waermemenge_ZWE"
_P1140 = "SECOND_HEAT_GENERATOR_AMOUNT_COUNTER"


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


def _aux_energy_description() -> LuxtronikSumSensorDescription:
    return LuxtronikSumSensorDescription(
        key=SensorKey.ADDITIONAL_HEAT_GENERATOR_ENERGY,
        device_key=DeviceKey.heatpump,
        summand_keys=(
            LP.P1059_ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER,
            LP.P1140_SECOND_HEAT_GENERATOR_AMOUNT_COUNTER,
        ),
        native_precision=1,
    )


def _make_entity(data, description=None):
    hass = MagicMock()
    entry = _mock_entry()
    coord = _mock_coordinator(data)
    description = description or _aux_energy_description()
    entity = LuxtronikSumSensorEntity(
        hass, entry, coord, description, DeviceKey.heatpump
    )
    entity.hass = hass
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    return entity


class TestSumSensorHandleCoordinatorUpdate:
    def test_adds_both_registers_when_both_present(self):
        """A unit that spans the handover: 1059 frozen, 1140 counting on."""
        data = make_coordinator_data(parameters={_P1059: 3760.4, _P1140: 87.2})
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 3847.6
        assert entity._attr_available is True

    def test_uses_single_register_when_the_other_is_absent(self):
        """Firmware predating 1140 still has a correct total from 1059."""
        data = make_coordinator_data(parameters={_P1059: 3753.9})
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 3753.9
        assert entity._attr_available is True

    def test_counts_a_zero_register_rather_than_skipping_it(self):
        """1059 reads a real 0 on units that never ran the aux heater pre-.88.

        Zero is a value, not an absence, so the total is just the other
        register - and the entity stays available.
        """
        data = make_coordinator_data(parameters={_P1059: 0, _P1140: 257.2})
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 257.2
        assert entity._attr_available is True

    def test_unavailable_when_no_register_is_present(self):
        data = make_coordinator_data(parameters={})
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None
        assert entity._attr_available is False

    def test_rounds_to_the_declared_precision(self):
        data = make_coordinator_data(parameters={_P1059: 1.05, _P1140: 2.02})
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 3.1

    def test_applies_factor_when_set(self):
        descr = LuxtronikSumSensorDescription(
            key=SensorKey.ADDITIONAL_HEAT_GENERATOR_ENERGY,
            device_key=DeviceKey.heatpump,
            summand_keys=(
                LP.P1059_ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER,
                LP.P1140_SECOND_HEAT_GENERATOR_AMOUNT_COUNTER,
            ),
            factor=0.5,
            native_precision=1,
        )
        data = make_coordinator_data(parameters={_P1059: 10, _P1140: 4})
        entity = _make_entity(data, descr)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 7.0

    def test_no_write_without_data(self):
        entity = _make_entity(make_coordinator_data(parameters={_P1059: 1.0}))
        entity.coordinator.data = None
        entity._handle_coordinator_update(None)
        entity.async_write_ha_state.assert_not_called()


class TestAuxHeaterEnergyTotalDescription:
    """The predefined description, as opposed to the generic entity."""

    def test_totals_the_two_aux_heater_registers(self):
        descr = next(
            d
            for d in SENSORS_SUM
            if d.key == SensorKey.ADDITIONAL_HEAT_GENERATOR_ENERGY
        )
        assert descr.summand_keys == (
            LP.P1059_ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER,
            LP.P1140_SECOND_HEAT_GENERATOR_AMOUNT_COUNTER,
        )
        assert descr.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR

    def test_is_selectable_in_the_energy_dashboard(self):
        """Diagnostic entities cannot be added there, so it must not be one."""
        descr = next(
            d
            for d in SENSORS_SUM
            if d.key == SensorKey.ADDITIONAL_HEAT_GENERATOR_ENERGY
        )
        assert descr.entity_category is None
        assert descr.entity_registry_enabled_default is not False

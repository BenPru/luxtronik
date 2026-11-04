"""Regression coverage for opt-in rated-power energy estimates."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfPower
import pytest

from conftest import make_coordinator_data
from custom_components.luxtronik2.const import LuxCalculation as LC, LuxStatus3Option
from custom_components.luxtronik2.estimated_energy import (
    CONF_ESTIMATED_ENERGY,
    CONF_RATED_ELECTRICAL_POWER,
    CONF_RATED_THERMAL_POWER,
    EnergyEstimate,
    EstimatedSensor,
    async_setup_estimates,
    estimated_power,
    positive_power,
)


def data(**values):
    """Build data using readable enum member names."""
    return make_coordinator_data(
        calculations={
            getattr(LC, key).value.split(".")[1]: value for key, value in values.items()
        }
    )


def runtimes(heating=0, dhw=0, compressor=0, second=None):
    values = {
        "C0064_OPERATION_HOURS_HEATING": heating,
        "C0065_OPERATION_HOURS_DHW": dhw,
        "C0056_COMPRESSOR1_OPERATION_HOURS": compressor,
    }
    if second is not None:
        values["C0058_COMPRESSOR2_OPERATION_HOURS"] = second
    return data(**values)


@pytest.mark.parametrize(
    "value", [None, "unknown", 0, -1, float("nan"), float("inf"), True]
)
def test_invalid_rating(value):
    assert positive_power(value) is None


def test_runtime_deltas_are_not_double_counted():
    tracker = EnergyEstimate(2, 8)
    tracker.update(runtimes(36000, 7200, 43200))
    assert sum(tracker.electrical.values()) == 0
    reading = runtimes(39600, 9000, 48600)
    tracker.update(reading)
    tracker.update(reading)
    assert tracker.electrical == {
        "heating": 2,
        "dhw": 1,
        "compressor1": 3,
        "compressor2": 0,
    }
    assert tracker.thermal == {"heating": 8, "dhw": 4}


def test_restart_outage_and_rating_change():
    tracker = EnergyEstimate(2, 8)
    tracker.update(runtimes())
    tracker.update(runtimes(3600, 1800, 5400))
    saved = tracker.snapshot()
    restarted = EnergyEstimate(3, 10)
    restarted.restore(saved)
    restarted.update(runtimes(None, None, None))
    assert not restarted.valid
    restarted.update(runtimes(7200, 3600, 10800))
    assert restarted.electrical["heating"] == 5
    assert restarted.electrical["dhw"] == 2.5
    assert restarted.electrical["compressor1"] == 7.5
    assert restarted.thermal == {"heating": 18, "dhw": 9}
    # Saved baselines and totals are copied rather than mutated by later polls.
    assert saved["baselines"]["heating"] == 3600


def test_reset_keeps_totals_and_establishes_new_baseline():
    tracker = EnergyEstimate(2, None)
    tracker.update(runtimes())
    tracker.update(runtimes(3600, 3600, 7200))
    tracker.update(runtimes(100, 100, 200))
    assert tracker.electrical["compressor1"] == 4
    tracker.update(runtimes(1900, 1900, 3800))
    assert tracker.electrical["compressor1"] == 6
    assert tracker.electrical["heating"] == 3


@pytest.mark.parametrize("bad", [None, "unknown", -1, float("nan"), float("inf"), True])
def test_bad_counter_preserves_baseline(bad):
    tracker = EnergyEstimate(2, None)
    tracker.update(runtimes())
    tracker.update(runtimes(bad, bad, bad))
    assert not tracker.valid
    tracker.update(runtimes(3600, 3600, 7200))
    assert tracker.electrical["compressor1"] == 4


def sensor(reading, circuit="total", quantity="power", tracker=None):
    coordinator = MagicMock()
    coordinator.data = reading
    coordinator.last_update_success = True
    entry = MagicMock(unique_id="pump-serial", entry_id="entry")
    return EstimatedSensor(
        coordinator, entry, tracker or EnergyEstimate(2, 8), circuit, quantity
    )


@pytest.mark.parametrize(
    "mode,circuit,expected",
    [
        ("heating", "heating", 2000),
        ("hot_water", "heating", 0),
        ("hot_water", "dhw", 2000),
        ("heating", "dhw", 0),
        ("defrost", "total", 2000),
        ("no_request", "total", 2000),
        (None, "heating", None),
        ("new_mode", "dhw", None),
    ],
)
def test_power_uses_compressor_and_controller_mode(mode, circuit, expected):
    reading = data(C0044_COMPRESSOR=True, C0080_STATUS=mode)
    assert sensor(reading, circuit).native_value == expected


def test_startup_and_off_ignore_demand():
    reading = data(C0044_COMPRESSOR=False, C0080_STATUS="hot_water")
    assert sensor(reading, "dhw").native_value == 0
    assert sensor(reading).native_value == 0
    assert estimated_power(data(C0044_COMPRESSOR=None))[0] is None
    assert estimated_power(data())[0] is None
    assert (
        estimated_power(data(C0044_COMPRESSOR=True, C0045_COMPRESSOR2=None))[0] is None
    )


def test_two_compressors_total_and_energy_metadata():
    assert (
        sensor(data(C0044_COMPRESSOR=True, C0045_COMPRESSOR2=True)).native_value == 4000
    )
    tracker = EnergyEstimate(2, 8)
    tracker.update(runtimes(second=0))
    tracker.update(runtimes(3600, 0, 3600, 1800))
    total = sensor(runtimes(second=1800), quantity="energy", tracker=tracker)
    assert total.native_value == 3
    assert total.device_class == SensorDeviceClass.ENERGY
    assert total.state_class == SensorStateClass.TOTAL_INCREASING
    assert total.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
    assert total.unique_id == "pump-serial_estimated_total_energy"
    assert (
        sensor(runtimes(second=1800), "heating", "energy", tracker).native_value is None
    )
    thermal = sensor(runtimes(), quantity="thermal_energy", tracker=tracker)
    assert thermal.native_value == 8
    power = sensor(data(C0044_COMPRESSOR=False))
    assert power.state_class == SensorStateClass.MEASUREMENT
    assert power.native_unit_of_measurement == UnitOfPower.WATT
    power.coordinator.last_update_success = False
    assert not power.available


def test_missing_mode_counter_does_not_report_partial_thermal_total():
    tracker = EnergyEstimate(2, 8)
    tracker.update(runtimes(dhw=None))
    entity = sensor(runtimes(dhw=None), quantity="thermal_energy", tracker=tracker)
    assert entity.native_value is None
    assert not entity.available


def test_second_compressor_support_is_not_inferred_away_after_reset():
    tracker = EnergyEstimate(2, 8)
    tracker.update(runtimes(second=1800))
    tracker.update(runtimes(second=0))
    restored = EnergyEstimate(2, 8)
    restored.restore(tracker.snapshot())
    restored.update(runtimes(second=0))
    assert (
        sensor(runtimes(second=0), "heating", "energy", restored).native_value is None
    )


@pytest.mark.parametrize("options", [{}, {CONF_ESTIMATED_ENERGY: True}])
async def test_default_creates_no_estimates(hass, options):
    entry = MagicMock(data={}, options=options)
    assert await async_setup_estimates(hass, entry, MagicMock()) == []


async def test_storage_and_listener_lifecycle(hass):
    entry = MagicMock(
        data={},
        entry_id="test-estimate",
        options={
            CONF_ESTIMATED_ENERGY: True,
            CONF_RATED_ELECTRICAL_POWER: 2,
            CONF_RATED_THERMAL_POWER: 8,
        },
    )
    coordinator = MagicMock(data=runtimes(), last_update_success=True)
    with patch("custom_components.luxtronik2.estimated_energy.Store") as store_class:
        store = store_class.return_value
        store_class.__getitem__.return_value.return_value = store
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        entities = await async_setup_estimates(hass, entry, coordinator)
        assert len(entities) == 9
        store.async_save.assert_awaited_once()
        listener = coordinator.async_add_listener.call_args.args[0]
        coordinator.data = runtimes(3600, 0, 3600)
        listener()
        energy = next(
            e for e in entities if e.circuit == "total" and e.quantity == "energy"
        )
        assert energy.native_value == 2
        snapshot = store.async_delay_save.call_args.args[0]()
        restored = EnergyEstimate(2, 8)
        restored.restore(snapshot)
        restored.update(runtimes(7200, 0, 7200))
        assert restored.electrical["compressor1"] == 4
        coordinator.last_update_success = False
        coordinator.data = runtimes(10800, 0, 10800)
        listener()
        assert energy.native_value == 2
        entry.async_on_unload.assert_called_once_with(
            coordinator.async_add_listener.return_value
        )


async def test_real_storage_survives_reload_and_rating_change(hass):
    """Exercise actual HA storage, including the flush used during reload."""
    entry = MagicMock(
        data={},
        entry_id="durable-estimate",
        unique_id="durable-pump",
        options={CONF_ESTIMATED_ENERGY: True, CONF_RATED_ELECTRICAL_POWER: 2},
    )
    first = MagicMock(data=runtimes(), last_update_success=True)
    entities = await async_setup_estimates(hass, entry, first)
    assert len(entities) == 6  # No thermal rating, no thermal entities.
    first.data = runtimes(3600, 0, 3600)
    first.async_add_listener.call_args.args[0]()
    await first.estimated_energy_save()
    entry.options[CONF_RATED_ELECTRICAL_POWER] = 3
    second = MagicMock(data=runtimes(7200, 0, 7200), last_update_success=True)
    restored = await async_setup_estimates(hass, entry, second)
    total = next(e for e in restored if e.circuit == "total" and e.quantity == "energy")
    assert total.native_value == 5
    assert {e.unique_id for e in entities} == {e.unique_id for e in restored}
    # Identical first successful snapshots after recovery cannot count twice.
    second.async_add_listener.call_args.args[0]()
    assert total.native_value == 5
    await second.estimated_energy_save()


def test_heating_dhw_transitions_do_not_reclassify_runtime():
    tracker = EnergyEstimate(2, 8)
    tracker.update(runtimes())
    tracker.update(runtimes(3600, 0, 3600))
    tracker.update(runtimes(3600, 1800, 5400))
    # Re-reading or changing mode has no side effects on cumulative energy.
    reading = data(C0044_COMPRESSOR=True, C0080_STATUS="hot_water")
    assert sensor(reading, "dhw", tracker=tracker).native_value == 2000
    assert sensor(reading, "heating", tracker=tracker).native_value == 0
    assert tracker.electrical["heating"] == 2
    assert tracker.electrical["dhw"] == 1
    assert tracker.electrical["compressor1"] == 3


def test_second_compressor_alone_and_thermal_disinfection():
    reading = data(
        C0044_COMPRESSOR=False, C0045_COMPRESSOR2=True, C0080_STATUS="heating"
    )
    assert sensor(reading, "heating").native_value == 2000
    reading = data(
        C0044_COMPRESSOR=True,
        C0080_STATUS="heating",
        C0119_STATUS_LINE_3=LuxStatus3Option.thermal_desinfection,
    )
    assert sensor(reading, "dhw").native_value == 2000
    assert sensor(reading, "heating").native_value == 0


@pytest.mark.parametrize("source", ["runtime", "output"])
@pytest.mark.parametrize("restored", [False, True])
def test_known_second_compressor_requires_complete_power(source, restored):
    tracker = EnergyEstimate(2, None)
    reading = (
        runtimes(second=1800)
        if source == "runtime"
        else data(C0044_COMPRESSOR=False, C0045_COMPRESSOR2=True)
    )
    tracker.update(reading)
    if restored:
        saved = tracker.snapshot()
        tracker = EnergyEstimate(2, None)
        tracker.restore(saved)
    tracker.update(runtimes(second=0))
    for circuit in ("total", "heating", "dhw"):
        for first in (False, True):
            incomplete = data(C0044_COMPRESSOR=first, C0080_STATUS="heating")
            entity = sensor(incomplete, circuit, tracker=tracker)
            assert entity.native_value is None
            assert not entity.available
    recovered = data(
        C0044_COMPRESSOR=True, C0045_COMPRESSOR2=True, C0080_STATUS="heating"
    )
    assert sensor(recovered, tracker=tracker).native_value == 4000


@pytest.mark.parametrize("restored", [False, True])
def test_known_second_compressor_missing_runtime_recovers_once(restored):
    tracker = EnergyEstimate(2, 8)
    tracker.update(runtimes(second=0))
    tracker.update(runtimes(3600, 0, 3600, 1800))
    if restored:
        saved = tracker.snapshot()
        tracker = EnergyEstimate(2, 8)
        tracker.restore(saved)
    incomplete = runtimes(5400, 0, 5400)
    tracker.update(incomplete)
    entity = sensor(incomplete, quantity="energy", tracker=tracker)
    assert entity.native_value is None
    assert not entity.available
    # Thermal totals do not require compressor runtime readings.
    assert (
        sensor(incomplete, quantity="thermal_energy", tracker=tracker).native_value
        == 12
    )
    recovered = runtimes(7200, 0, 7200, 3600)
    tracker.update(recovered)
    entity.coordinator.data = recovered
    assert entity.available
    assert entity.native_value == 6
    tracker.update(recovered)
    assert entity.native_value == 6


def test_single_compressor_without_second_registers_remains_available():
    tracker = EnergyEstimate(2, None)
    tracker.update(runtimes())
    reading = runtimes(3600, 0, 3600)
    tracker.update(reading)
    entity = sensor(reading, quantity="energy", tracker=tracker)
    assert entity.available
    assert entity.native_value == 2
    assert sensor(data(C0044_COMPRESSOR=True), tracker=tracker).native_value == 2000

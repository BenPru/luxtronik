"""Tests for the SCOP / 30-day COP sensor entities and their setup."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import make_coordinator_data
from custom_components.luxtronik2.base import LuxtronikEntity
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    DeviceKey,
    LuxParameter as LP,
    SensorKey,
)
from custom_components.luxtronik2.coordinator import LuxtronikCoordinator
from custom_components.luxtronik2.scop import (
    SCOP_WINDOWS,
    ScopCircuit,
    ScopResult,
)
from custom_components.luxtronik2.sensor import LuxtronikScopSensorEntity
from custom_components.luxtronik2.sensor_entities_predefined import (
    SENSORS_COP,
    SENSORS_SCOP,
)

_RESULT = ScopResult(
    value=5.9,
    coverage_days=364.958,
    heat_kwh=16000.04,
    electricity_kwh=2711.93,
    electricity_source="external",
    window_start=datetime(2025, 11, 15, 13, tzinfo=UTC),
)


def _description(key: SensorKey):
    return next(d for d in SENSORS_SCOP if d.key == key)


def _tracker(results=None) -> MagicMock:
    tracker = MagicMock()
    tracker.results = results or {}
    tracker.async_add_listener.return_value = MagicMock(name="remove")
    return tracker


def _entity(key: SensorKey = SensorKey.SCOP, tracker=None):
    entry = MagicMock()
    entry.data = {CONF_HA_SENSOR_PREFIX: DOMAIN}
    entry.options = {}
    coord = MagicMock()
    coord.data = make_coordinator_data()
    coord.entity_visible.return_value = True
    tracker = tracker or _tracker()
    description = _description(key)
    entity = LuxtronikScopSensorEntity(
        MagicMock(), entry, coord, description, description.device_key, tracker
    )
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()
    return entity, tracker


class TestScopSensorEntity:
    def test_value_and_attributes_from_tracker_result(self):
        entity, _ = _entity(tracker=_tracker({(ScopCircuit.total, 365): _RESULT}))
        entity._handle_scop_update()
        assert entity.native_value == 5.9
        attrs = entity.extra_state_attributes
        assert attrs["coverage_days"] == 365.0
        assert attrs["heat_kwh"] == 16000.0
        assert attrs["electricity_kwh"] == 2711.9
        assert attrs["electricity_source"] == "external"
        assert attrs["window_start"] == "2025-11-15T13:00:00+00:00"
        entity.async_write_ha_state.assert_called()

    def test_reads_its_own_circuit_and_window(self):
        other = ScopResult(4.1, 30.0, 41.0, 10.0, "controller", None)
        entity, _ = _entity(
            SensorKey.COP_30D_DHW,
            _tracker(
                {
                    (ScopCircuit.total, 365): _RESULT,
                    (ScopCircuit.domestic_water, 30): other,
                }
            ),
        )
        entity._handle_scop_update()
        assert entity.native_value == 4.1
        assert entity.extra_state_attributes["window_start"] is None

    def test_unknown_before_first_refresh(self):
        entity, _ = _entity()
        entity._handle_scop_update()
        assert entity.native_value is None
        assert "coverage_days" not in entity.extra_state_attributes

    def test_unknown_below_min_coverage_keeps_coverage_attribute(self):
        short = ScopResult(None, 3.0, 12.0, 3.0, "controller", None)
        entity, _ = _entity(tracker=_tracker({(ScopCircuit.total, 365): short}))
        entity._handle_scop_update()
        assert entity.native_value is None
        assert entity.extra_state_attributes["coverage_days"] == 3.0

    def test_coordinator_poll_does_not_change_value(self):
        entity, _ = _entity(tracker=_tracker({(ScopCircuit.total, 365): _RESULT}))
        entity._handle_scop_update()
        entity._handle_coordinator_update()
        assert entity.native_value == 5.9
        entity.async_write_ha_state.assert_called()

    async def test_listener_registered_and_removed_with_entity(self):
        entity, tracker = _entity()
        entity.async_on_remove = MagicMock()
        with patch.object(LuxtronikEntity, "async_added_to_hass", AsyncMock()):
            await entity.async_added_to_hass()
        tracker.async_add_listener.assert_called_once_with(entity._handle_scop_update)
        entity.async_on_remove.assert_called_once_with(
            tracker.async_add_listener.return_value
        )


class TestScopDescriptions:
    def test_one_description_per_circuit_and_window(self):
        pairs = [(d.circuit, d.window_days) for d in SENSORS_SCOP]
        assert len(pairs) == len(set(pairs))
        assert set(pairs) == {(c, w) for c in ScopCircuit for w in SCOP_WINDOWS}

    def test_every_description_excludes_twin_units(self):
        for descr in SENSORS_SCOP:
            assert (LP.P1010_IS_TWIN, "== 0") in descr.entity_active, descr.key

    def test_devices_follow_the_circuit(self):
        device = {
            ScopCircuit.heating: DeviceKey.heating,
            ScopCircuit.domestic_water: DeviceKey.domestic_water,
            ScopCircuit.total: DeviceKey.heatpump,
        }
        for descr in SENSORS_SCOP:
            assert descr.device_key == device[descr.circuit], descr.key

    def test_cop_and_scop_display_two_decimals(self):
        """A ratio of 4.0 shows as "4.00", like 3.87 next to it."""
        for descr in (*SENSORS_COP, *SENSORS_SCOP):
            assert descr.suggested_display_precision == 2, descr.key


def _gate_coordinator(**parameters) -> LuxtronikCoordinator:
    coord = object.__new__(LuxtronikCoordinator)
    coord.data = make_coordinator_data(
        parameters={
            "ID_Einst_isTwin": 0,
            "HEAT_ENERGY_INPUT": 2700.0,
            "DHW_ENERGY_INPUT": 710.0,
            **parameters,
        }
    )
    return coord


def _active_keys(coord: LuxtronikCoordinator) -> set[SensorKey]:
    with (
        patch.object(
            LuxtronikCoordinator, "_is_version_not_compatible", return_value=False
        ),
        patch.object(LuxtronikCoordinator, "device_key_active", return_value=True),
    ):
        return {d.key for d in SENSORS_SCOP if coord.entity_active(d)}


class TestScopGates:
    def test_all_six_on_a_single_compressor_unit(self):
        assert _active_keys(_gate_coordinator()) == {d.key for d in SENSORS_SCOP}

    def test_none_on_twin_units(self):
        assert _active_keys(_gate_coordinator(ID_Einst_isTwin=1)) == set()

    def test_dhw_and_whole_unit_skipped_when_p1137_zero(self):
        assert _active_keys(_gate_coordinator(DHW_ENERGY_INPUT=0.0)) == {
            SensorKey.SCOP_HEATING,
            SensorKey.COP_30D_HEATING,
        }

    def test_none_when_p1136_zero(self):
        # Series 1 reads 0 here despite years of runtime.
        assert (
            _active_keys(_gate_coordinator(HEAT_ENERGY_INPUT=0.0, DHW_ENERGY_INPUT=0.0))
            == set()
        )


def _setup_entry() -> MagicMock:
    coord = MagicMock()
    coord.data = make_coordinator_data()
    coord.last_update_success = True
    coord.entity_visible.return_value = True
    entry = MagicMock()
    entry.data = {CONF_HA_SENSOR_PREFIX: DOMAIN}
    entry.options = {}
    entry.runtime_data = coord
    return entry


def _scop_entities(add: MagicMock) -> list[LuxtronikScopSensorEntity]:
    return [
        e
        for call in add.call_args_list
        for e in call.args[0]
        if isinstance(e, LuxtronikScopSensorEntity)
    ]


class TestScopSetup:
    @pytest.fixture
    def tracker_cls(self):
        with patch("custom_components.luxtronik2.sensor.ScopTracker") as cls:
            yield cls

    async def _run(self, components: set[str], active: bool = True):
        from custom_components.luxtronik2.sensor import async_setup_entry

        hass = MagicMock()
        hass.config.components = components
        entry = _setup_entry()
        entry.runtime_data.entity_active.side_effect = lambda d: (
            active or d not in SENSORS_SCOP
        )
        add = MagicMock()
        with (
            patch("homeassistant.helpers.frame.report_usage"),
            patch(
                "custom_components.luxtronik2.sensor.entity_platform.async_get_current_platform"
            ),
        ):
            await async_setup_entry(hass, entry, add)
        return add

    async def test_creates_six_entities_with_recorder(self, tracker_cls):
        add = await self._run({"recorder"})
        assert len(_scop_entities(add)) == 6
        tracker_cls.assert_called_once()
        tracker_cls.return_value.async_start.assert_called_once_with()

    async def test_creates_none_without_recorder(self, tracker_cls):
        add = await self._run(set())
        assert _scop_entities(add) == []
        tracker_cls.assert_not_called()

    async def test_tracker_not_started_when_no_entity_is_active(self, tracker_cls):
        add = await self._run({"recorder"}, active=False)
        assert _scop_entities(add) == []
        tracker_cls.return_value.async_start.assert_not_called()

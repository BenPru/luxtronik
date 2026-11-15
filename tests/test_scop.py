"""Tests for custom_components.luxtronik2.scop (windowed SCOP from statistics)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.luxtronik2 import scop
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    SensorKey,
)
from custom_components.luxtronik2.scop import (
    SCOP_WINDOWS,
    ScopCircuit,
    ScopInputs,
    ScopTracker,
    compute_scop,
    compute_windows,
)

NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)
HOUR = 3600.0

HEAT_H = "sensor.heat_heating"
HEAT_DHW = "sensor.heat_dhw"
ELEC_H = "sensor.elec_heating"
ELEC_DHW = "sensor.elec_dhw"
COOL = "sensor.elec_cooling"
EXT = "sensor.ext_power"

INPUTS = ScopInputs(
    heat_heating=HEAT_H, heat_dhw=HEAT_DHW, elec_heating=ELEC_H, elec_dhw=ELEC_DHW
)

NORMAL = {HEAT_H: 2.0, ELEC_H: 0.5, HEAT_DHW: 1.0, ELEC_DHW: 0.25}


def _starts(hours: int) -> list[float]:
    """Start timestamps of `hours` consecutive complete hours ending at NOW."""
    first = NOW.timestamp() - hours * HOUR
    return [first + i * HOUR for i in range(hours)]


def _rows(hours: int, changes: dict[str, float]) -> dict[str, list[dict[str, Any]]]:
    """Counter rows with a constant change per hour and a growing state."""
    rows: dict[str, list[dict[str, Any]]] = {}
    for stat_id, change in changes.items():
        state = 100.0
        rows[stat_id] = []
        for start in _starts(hours):
            state += change
            rows[stat_id].append({"start": start, "change": change, "state": state})
    return rows


def _power_rows(hours: int, mean_kw: float) -> list[dict[str, Any]]:
    return [{"start": s, "mean": mean_kw} for s in _starts(hours)]


class TestComputeScopController:
    def test_ratio_of_sums_without_external(self):
        r = compute_scop(_rows(48, NORMAL), INPUTS, NOW, 30, 1)
        assert r[ScopCircuit.heating].value == 4.0
        assert r[ScopCircuit.domestic_water].value == 4.0
        assert r[ScopCircuit.total].value == 4.0
        assert r[ScopCircuit.heating].coverage_days == 2.0
        assert r[ScopCircuit.heating].heat_kwh == 96.0
        assert r[ScopCircuit.heating].electricity_kwh == 24.0
        assert r[ScopCircuit.heating].electricity_source == "controller"
        assert r[ScopCircuit.heating].window_start == NOW - timedelta(hours=48)

    def test_ratio_weights_by_energy_not_by_hour(self):
        rows = _rows(2, NORMAL)
        # hour 1: COP 4 on 0.5 kWh; hour 2: COP 2 on 1.5 kWh -> 5 / 2.0 = 2.5
        rows[HEAT_H][1]["change"] = 3.0
        rows[ELEC_H][1]["change"] = 1.5
        r = compute_scop(rows, INPUTS, NOW, 30, 0)
        assert r[ScopCircuit.heating].value == 2.5

    def test_glitch_hour_dropped_for_all_counters(self):
        rows = _rows(48, NORMAL)
        rows[HEAT_H][10].update(change=1000.0, state=1000.0)
        r = compute_scop(rows, INPUTS, NOW, 30, 1)
        assert r[ScopCircuit.heating].value == 4.0
        assert r[ScopCircuit.domestic_water].electricity_kwh == 47 * 0.25
        assert r[ScopCircuit.heating].coverage_days == 47 / 24

    def test_negative_change_is_a_glitch(self):
        rows = _rows(48, NORMAL)
        rows[ELEC_DHW][5]["change"] = -5.0
        r = compute_scop(rows, INPUTS, NOW, 30, 1)
        assert r[ScopCircuit.heating].coverage_days == 47 / 24

    def test_small_counter_jump_is_not_a_glitch(self):
        rows = _rows(48, NORMAL)
        rows[HEAT_DHW][5].update(change=0.9, state=1.0)
        r = compute_scop(rows, INPUTS, NOW, 30, 1)
        assert r[ScopCircuit.heating].coverage_days == 2.0

    def test_hours_before_first_electricity_change_ignored(self):
        rows = _rows(48, NORMAL)
        for i in range(24):
            rows[ELEC_H][i]["change"] = 0.0
            rows[ELEC_DHW][i]["change"] = 0.0
        r = compute_scop(rows, INPUTS, NOW, 30, 1)
        assert r[ScopCircuit.heating].coverage_days == 1.0
        assert r[ScopCircuit.heating].value == 4.0
        assert r[ScopCircuit.heating].window_start == NOW - timedelta(hours=24)

    def test_idle_hours_after_first_electricity_change_are_kept(self):
        rows = _rows(48, NORMAL)
        for i in range(30, 40):
            for stat_id in NORMAL:
                rows[stat_id][i]["change"] = 0.0
        r = compute_scop(rows, INPUTS, NOW, 30, 1)
        assert r[ScopCircuit.heating].coverage_days == 2.0

    def test_hour_missing_a_core_counter_is_dropped(self):
        rows = _rows(48, NORMAL)
        del rows[HEAT_DHW][7]
        r = compute_scop(rows, INPUTS, NOW, 30, 1)
        assert r[ScopCircuit.heating].coverage_days == 47 / 24

    def test_core_counter_with_none_change_drops_hour(self):
        rows = _rows(48, NORMAL)
        rows[ELEC_H][7]["change"] = None
        r = compute_scop(rows, INPUTS, NOW, 30, 1)
        assert r[ScopCircuit.heating].coverage_days == 47 / 24

    def test_missing_other_counter_hour_counts_as_zero(self):
        inputs = ScopInputs(
            heat_heating=HEAT_H,
            heat_dhw=HEAT_DHW,
            elec_heating=ELEC_H,
            elec_dhw=ELEC_DHW,
            elec_other=(COOL,),
        )
        rows = _rows(48, {**NORMAL, COOL: 0.1})
        del rows[COOL][3]
        r = compute_scop(rows, inputs, NOW, 30, 1)
        assert r[ScopCircuit.heating].coverage_days == 2.0
        # Without an external meter the other counters do not enter the ratio.
        assert r[ScopCircuit.heating].value == 4.0

    def test_window_excludes_older_hours(self):
        r = compute_scop(_rows(40 * 24, NORMAL), INPUTS, NOW, 30, 1)
        assert r[ScopCircuit.heating].coverage_days == 30.0
        assert r[ScopCircuit.heating].window_start == NOW - timedelta(days=30)

    def test_below_min_coverage_returns_none_but_reports_coverage(self):
        r = compute_scop(_rows(48, NORMAL), INPUTS, NOW, 365, 30)
        assert r[ScopCircuit.heating].value is None
        assert r[ScopCircuit.heating].coverage_days == 2.0

    def test_zero_electricity_returns_none(self):
        rows = _rows(48, {**NORMAL, HEAT_DHW: 0.0, ELEC_DHW: 0.0})
        r = compute_scop(rows, INPUTS, NOW, 30, 1)
        assert r[ScopCircuit.domestic_water].value is None
        assert r[ScopCircuit.heating].value == 4.0

    def test_no_rows_at_all_returns_none_with_zero_coverage(self):
        r = compute_scop({}, INPUTS, NOW, 30, 1)
        for circuit in ScopCircuit:
            assert r[circuit].value is None
            assert r[circuit].coverage_days == 0.0
            assert r[circuit].window_start is None


class TestComputeScopExternal:
    def _inputs(self, kind, other=()):
        return ScopInputs(
            heat_heating=HEAT_H,
            heat_dhw=HEAT_DHW,
            elec_heating=ELEC_H,
            elec_dhw=ELEC_DHW,
            elec_other=other,
            external=EXT,
            external_kind=kind,
        )

    def _split_rows(self, extra=None):
        changes = {HEAT_H: 2.0, HEAT_DHW: 0.4, ELEC_H: 0.3, ELEC_DHW: 0.1}
        return _rows(24, {**changes, **(extra or {})})

    def test_external_power_split_by_controller_share(self):
        rows = self._split_rows()
        rows[EXT] = _power_rows(24, 1.0)
        r = compute_scop(rows, self._inputs("power"), NOW, 30, 1)
        assert r[ScopCircuit.heating].electricity_kwh == pytest.approx(18.0)
        assert r[ScopCircuit.heating].value == round(48 / 18, 2)
        assert r[ScopCircuit.domestic_water].electricity_kwh == pytest.approx(6.0)
        assert r[ScopCircuit.total].electricity_kwh == pytest.approx(24.0)
        assert r[ScopCircuit.total].value == round(57.6 / 24, 2)
        assert r[ScopCircuit.heating].electricity_source == "external"

    def test_external_energy_uses_change(self):
        rows = self._split_rows()
        rows[EXT] = _rows(24, {EXT: 1.0})[EXT]
        r = compute_scop(rows, self._inputs("energy"), NOW, 30, 1)
        assert r[ScopCircuit.heating].electricity_kwh == pytest.approx(18.0)
        assert r[ScopCircuit.total].electricity_kwh == pytest.approx(24.0)

    def test_external_split_excludes_cooling_and_pool(self):
        rows = self._split_rows({COOL: 0.1})
        rows[EXT] = _power_rows(24, 1.0)
        r = compute_scop(rows, self._inputs("power", (COOL,)), NOW, 30, 1)
        assert r[ScopCircuit.heating].electricity_kwh == pytest.approx(24 * 0.6)
        assert r[ScopCircuit.total].electricity_kwh == pytest.approx(24 * 0.8)

    def test_external_hour_missing_drops_hour(self):
        rows = self._split_rows()
        rows[EXT] = _power_rows(24, 1.0)
        rows[EXT][4]["mean"] = None
        r = compute_scop(rows, self._inputs("power"), NOW, 30, 0)
        assert r[ScopCircuit.heating].coverage_days == 23 / 24

    def test_external_row_absent_drops_hour(self):
        rows = self._split_rows()
        rows[EXT] = _power_rows(24, 1.0)
        del rows[EXT][4]
        r = compute_scop(rows, self._inputs("power"), NOW, 30, 0)
        assert r[ScopCircuit.heating].coverage_days == 23 / 24
        assert r[ScopCircuit.total].electricity_kwh == pytest.approx(23.0)

    def test_external_energy_glitch_drops_hour(self):
        rows = self._split_rows()
        rows[EXT] = _rows(24, {EXT: 1.0})[EXT]
        rows[EXT][4].update(change=500.0, state=500.0)
        r = compute_scop(rows, self._inputs("energy"), NOW, 30, 0)
        assert r[ScopCircuit.heating].coverage_days == 23 / 24

    def test_external_with_no_controller_electricity_returns_none(self):
        rows = _rows(24, {HEAT_H: 2.0, HEAT_DHW: 0.4, ELEC_H: 0.0, ELEC_DHW: 0.0})
        rows[EXT] = _power_rows(24, 1.0)
        r = compute_scop(rows, self._inputs("power"), NOW, 30, 0)
        assert r[ScopCircuit.heating].value is None


class TestScopInputs:
    def test_statistic_ids_skips_none(self):
        assert INPUTS.statistic_ids == {HEAT_H, HEAT_DHW, ELEC_H, ELEC_DHW}

    def test_statistic_ids_include_other_and_external(self):
        inputs = ScopInputs(
            heat_heating=HEAT_H,
            heat_dhw=HEAT_DHW,
            elec_heating=ELEC_H,
            elec_dhw=ELEC_DHW,
            elec_other=(COOL,),
            external=EXT,
            external_kind="power",
        )
        assert inputs.statistic_ids == {HEAT_H, HEAT_DHW, ELEC_H, ELEC_DHW, COOL, EXT}


# region ScopTracker


class _FakeRecorder:
    """Runs recorder executor jobs inline."""

    async def async_add_executor_job(self, target, *args):
        return target(*args)


_PREFIX = "luxtronik"


def _tracker_entry(options: dict[str, Any] | None = None) -> MagicMock:
    entry = MagicMock()
    entry.data = {CONF_HA_SENSOR_PREFIX: _PREFIX}
    entry.options = options or {}
    return entry


def _register(hass: HomeAssistant, key: SensorKey, object_id: str) -> str:
    return (
        er.async_get(hass)
        .async_get_or_create(
            "sensor",
            DOMAIN,
            f"sensor.{_PREFIX}_{key}",
            suggested_object_id=object_id,
        )
        .entity_id
    )


def _register_core(hass: HomeAssistant) -> ScopInputs:
    return ScopInputs(
        heat_heating=_register(hass, SensorKey.HEAT_AMOUNT_HEATING, "wp_heat"),
        heat_dhw=_register(hass, SensorKey.DHW_HEAT_AMOUNT, "wp_heat_dhw"),
        elec_heating=_register(hass, SensorKey.HEAT_ENERGY_INPUT, "wp_kwh"),
        elec_dhw=_register(hass, SensorKey.DHW_ENERGY_INPUT, "wp_kwh_dhw"),
    )


def _core_rows(inputs: ScopInputs, hours: int) -> dict[str, list[dict[str, Any]]]:
    return _rows(
        hours,
        {
            inputs.heat_heating: 2.0,
            inputs.elec_heating: 0.5,
            inputs.heat_dhw: 1.0,
            inputs.elec_dhw: 0.25,
        },
    )


@pytest.fixture
def recorder_api(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch the recorder functions scop.py calls; returns the mocks."""
    api = MagicMock()
    api.statistics_during_period.return_value = {}
    api.get_metadata.return_value = {}
    monkeypatch.setattr(scop, "get_instance", lambda hass: _FakeRecorder())
    monkeypatch.setattr(scop, "statistics_during_period", api.statistics_during_period)
    monkeypatch.setattr(scop, "get_metadata", api.get_metadata)
    return api


def _meta(*, has_sum: bool, mean_type: StatisticMeanType) -> dict[str, Any]:
    return {"has_sum": has_sum, "mean_type": mean_type}


class TestScopTracker:
    async def test_refresh_resolves_renamed_counter_entities(
        self, hass: HomeAssistant, recorder_api: MagicMock
    ):
        inputs = _register_core(hass)
        await ScopTracker(hass, _tracker_entry()).async_refresh()
        args = recorder_api.statistics_during_period.call_args.args
        assert args[3] == {
            "sensor.wp_heat",
            "sensor.wp_heat_dhw",
            "sensor.wp_kwh",
            "sensor.wp_kwh_dhw",
        }
        assert args[3] == inputs.statistic_ids
        assert args[4] == "hour"
        assert args[5] == {"energy": "kWh", "power": "kW"}
        assert args[6] == {"change", "state", "mean"}
        assert args[2] is None
        assert args[1] <= dt_util.utcnow() - timedelta(days=365)

    async def test_refresh_fills_results_for_both_windows_and_notifies(
        self, hass: HomeAssistant, recorder_api: MagicMock
    ):
        inputs = _register_core(hass)
        recorder_api.statistics_during_period.return_value = _core_rows(inputs, 10 * 24)
        tracker = ScopTracker(hass, _tracker_entry())
        listener = MagicMock()
        tracker.async_add_listener(listener)
        await tracker.async_refresh()
        assert set(tracker.results) == {
            (circuit, window) for circuit in ScopCircuit for window in (365, 30)
        }
        # 10 days: enough for the 30-day window (min 7), not for 1 year (min 30).
        assert tracker.results[(ScopCircuit.heating, 30)].value == 4.0
        assert tracker.results[(ScopCircuit.heating, 365)].value is None
        assert tracker.results[(ScopCircuit.heating, 365)].coverage_days == 10.0
        listener.assert_called_once_with()

    async def test_missing_required_counter_leaves_results_empty(
        self, hass: HomeAssistant, recorder_api: MagicMock
    ):
        _register(hass, SensorKey.HEAT_AMOUNT_HEATING, "wp_heat")
        tracker = ScopTracker(hass, _tracker_entry())
        listener = MagicMock()
        tracker.async_add_listener(listener)
        await tracker.async_refresh()
        assert tracker.results == {}
        recorder_api.statistics_during_period.assert_not_called()
        listener.assert_not_called()

    async def test_optional_cooling_and_pool_counters_are_queried(
        self, hass: HomeAssistant, recorder_api: MagicMock
    ):
        _register_core(hass)
        cooling = _register(hass, SensorKey.COOLING_ENERGY_INPUT, "wp_cool")
        pool = _register(hass, SensorKey.POOL_ENERGY_INPUT, "wp_pool")
        await ScopTracker(hass, _tracker_entry()).async_refresh()
        queried = recorder_api.statistics_during_period.call_args.args[3]
        assert {cooling, pool} <= queried

    async def test_external_power_sensor_detected_from_metadata(
        self, hass: HomeAssistant, recorder_api: MagicMock
    ):
        inputs = _register_core(hass)
        rows = _core_rows(inputs, 10 * 24)
        rows["sensor.meter"] = _power_rows(10 * 24, 1.0)
        recorder_api.statistics_during_period.return_value = rows
        recorder_api.get_metadata.return_value = {
            "sensor.meter": (
                1,
                _meta(has_sum=False, mean_type=StatisticMeanType.ARITHMETIC),
            )
        }
        entry = _tracker_entry(
            {CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION: "sensor.meter"}
        )
        tracker = ScopTracker(hass, entry)
        await tracker.async_refresh()
        result = tracker.results[(ScopCircuit.total, 30)]
        assert result.electricity_source == "external"
        assert result.electricity_kwh == pytest.approx(240.0)
        queried = recorder_api.statistics_during_period.call_args.args[3]
        assert "sensor.meter" in queried

    async def test_external_energy_sensor_detected_from_metadata(
        self, hass: HomeAssistant, recorder_api: MagicMock
    ):
        inputs = _register_core(hass)
        rows = _core_rows(inputs, 10 * 24)
        rows["sensor.meter"] = _rows(10 * 24, {"sensor.meter": 1.0})["sensor.meter"]
        recorder_api.statistics_during_period.return_value = rows
        recorder_api.get_metadata.return_value = {
            "sensor.meter": (1, _meta(has_sum=True, mean_type=StatisticMeanType.NONE))
        }
        entry = _tracker_entry()
        entry.data[CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION] = "sensor.meter"
        tracker = ScopTracker(hass, entry)
        await tracker.async_refresh()
        result = tracker.results[(ScopCircuit.total, 30)]
        assert result.electricity_source == "external"
        assert result.electricity_kwh == pytest.approx(240.0)

    async def test_external_without_statistics_falls_back_and_warns_once(
        self,
        hass: HomeAssistant,
        recorder_api: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ):
        inputs = _register_core(hass)
        recorder_api.statistics_during_period.return_value = _core_rows(inputs, 10 * 24)
        entry = _tracker_entry(
            {CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION: "sensor.plug"}
        )
        tracker = ScopTracker(hass, entry)
        await tracker.async_refresh()
        await tracker.async_refresh()
        warnings = [r for r in caplog.records if "sensor.plug" in r.getMessage()]
        assert len(warnings) == 1
        assert warnings[0].levelname == "WARNING"
        result = tracker.results[(ScopCircuit.heating, 30)]
        assert result.electricity_source == "controller"
        assert result.value == 4.0
        queried = recorder_api.statistics_during_period.call_args.args[3]
        assert "sensor.plug" not in queried

    async def test_recorder_error_keeps_previous_results(
        self,
        hass: HomeAssistant,
        recorder_api: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ):
        inputs = _register_core(hass)
        recorder_api.statistics_during_period.return_value = _core_rows(inputs, 10 * 24)
        tracker = ScopTracker(hass, _tracker_entry())
        await tracker.async_refresh()
        before = dict(tracker.results)
        listener = MagicMock()
        tracker.async_add_listener(listener)
        recorder_api.statistics_during_period.side_effect = RuntimeError("db locked")
        await tracker.async_refresh()
        assert tracker.results == before
        listener.assert_not_called()
        assert "db locked" in caplog.text

    async def test_listener_remover_stops_notifications(
        self, hass: HomeAssistant, recorder_api: MagicMock
    ):
        _register_core(hass)
        tracker = ScopTracker(hass, _tracker_entry())
        listener = MagicMock()
        remove = tracker.async_add_listener(listener)
        remove()
        await tracker.async_refresh()
        listener.assert_not_called()

    async def test_first_refresh_waits_55_s_after_start_then_hourly(
        self, hass: HomeAssistant, recorder_api: MagicMock
    ):
        # Right at "started" every integration hits the database at once; the
        # same query took 17.9 s there on the Pi and 1.3 s 25 s later.
        _register_core(hass)
        entry = _tracker_entry()
        unloaders: list[Any] = []
        entry.async_on_unload.side_effect = unloaders.append
        start = dt_util.utcnow()
        ScopTracker(hass, entry).async_start()
        await hass.async_block_till_done()
        assert recorder_api.statistics_during_period.call_count == 0

        async_fire_time_changed(hass, start + timedelta(seconds=54))
        await hass.async_block_till_done()
        assert recorder_api.statistics_during_period.call_count == 0

        async_fire_time_changed(hass, start + timedelta(seconds=56))
        await hass.async_block_till_done()
        assert recorder_api.statistics_during_period.call_count == 1

        async_fire_time_changed(hass, start + timedelta(hours=1, seconds=1))
        await hass.async_block_till_done()
        assert recorder_api.statistics_during_period.call_count == 2

        for unload in unloaders:
            unload()
        async_fire_time_changed(hass, start + timedelta(hours=3))
        await hass.async_block_till_done()
        assert recorder_api.statistics_during_period.call_count == 2

    async def test_unload_before_the_delay_cancels_the_first_refresh(
        self, hass: HomeAssistant, recorder_api: MagicMock
    ):
        _register_core(hass)
        entry = _tracker_entry()
        unloaders: list[Any] = []
        entry.async_on_unload.side_effect = unloaders.append
        start = dt_util.utcnow()
        ScopTracker(hass, entry).async_start()
        await hass.async_block_till_done()
        for unload in unloaders:
            unload()
        async_fire_time_changed(hass, start + timedelta(seconds=56))
        await hass.async_block_till_done()
        recorder_api.statistics_during_period.assert_not_called()


class TestScopHeatingOnly:
    """Heating-only units never create the DHW counter entities (#review-1)."""

    HEATING_ONLY = ScopInputs(
        heat_heating=HEAT_H, heat_dhw=None, elec_heating=ELEC_H, elec_dhw=None
    )

    def test_dhw_counters_absent(self):
        rows = _rows(48, {HEAT_H: 2.0, ELEC_H: 0.5})
        r = compute_scop(rows, self.HEATING_ONLY, NOW, 30, 1)
        assert r[ScopCircuit.heating].value == 4.0
        assert r[ScopCircuit.heating].coverage_days == 2.0
        assert r[ScopCircuit.domestic_water].value is None
        assert r[ScopCircuit.total].value == 4.0

    def test_statistic_ids_skip_absent_dhw(self):
        assert self.HEATING_ONLY.statistic_ids == {HEAT_H, ELEC_H}

    async def test_heating_only_unit_uses_heating_counters(
        self, hass: HomeAssistant, recorder_api: MagicMock
    ):
        heat = _register(hass, SensorKey.HEAT_AMOUNT_HEATING, "wp_heat")
        elec = _register(hass, SensorKey.HEAT_ENERGY_INPUT, "wp_kwh")
        recorder_api.statistics_during_period.return_value = _rows(
            10 * 24, {heat: 2.0, elec: 0.5}
        )
        tracker = ScopTracker(hass, _tracker_entry())
        await tracker.async_refresh()
        assert recorder_api.statistics_during_period.call_args.args[3] == {heat, elec}
        assert tracker.results[(ScopCircuit.heating, 30)].value == 4.0

    async def test_disabled_dhw_counter_is_ignored(
        self, hass: HomeAssistant, recorder_api: MagicMock
    ):
        inputs = _register_core(hass)
        er.async_get(hass).async_update_entity(
            inputs.elec_dhw, disabled_by=er.RegistryEntryDisabler.USER
        )
        recorder_api.statistics_during_period.return_value = _core_rows(inputs, 10 * 24)
        tracker = ScopTracker(hass, _tracker_entry())
        await tracker.async_refresh()
        queried = recorder_api.statistics_during_period.call_args.args[3]
        assert queried == {inputs.heat_heating, inputs.elec_heating}
        assert tracker.results[(ScopCircuit.heating, 30)].value == 4.0

    async def test_disabled_heating_counter_skips_refresh(
        self, hass: HomeAssistant, recorder_api: MagicMock
    ):
        inputs = _register_core(hass)
        er.async_get(hass).async_update_entity(
            inputs.heat_heating, disabled_by=er.RegistryEntryDisabler.USER
        )
        await ScopTracker(hass, _tracker_entry()).async_refresh()
        recorder_api.statistics_during_period.assert_not_called()


class TestScopOffLoop:
    """The year of rows is crunched in the executor, not the loop (#review-2)."""

    def test_compute_windows_matches_compute_scop(self):
        rows = _rows(10 * 24, NORMAL)
        windows = compute_windows(rows, INPUTS, NOW, SCOP_WINDOWS)
        for window, min_coverage in SCOP_WINDOWS.items():
            for circuit, result in compute_scop(
                rows, INPUTS, NOW, window, min_coverage
            ).items():
                assert windows[(circuit, window)] == result

    async def test_computation_runs_in_the_executor(
        self, hass: HomeAssistant, recorder_api: MagicMock, monkeypatch
    ):
        inputs = _register_core(hass)
        recorder_api.statistics_during_period.return_value = _core_rows(inputs, 10 * 24)
        in_executor = False

        class _TrackingRecorder:
            async def async_add_executor_job(self, target, *args):
                nonlocal in_executor
                in_executor = True
                try:
                    return target(*args)
                finally:
                    in_executor = False

        real = scop.compute_windows
        seen: list[bool] = []

        def _spy(*args):
            seen.append(in_executor)
            return real(*args)

        monkeypatch.setattr(scop, "get_instance", lambda hass: _TrackingRecorder())
        monkeypatch.setattr(scop, "compute_windows", _spy)
        tracker = ScopTracker(hass, _tracker_entry())
        await tracker.async_refresh()
        assert seen == [True]
        assert tracker.results[(ScopCircuit.heating, 30)].value == 4.0


async def test_refresh_logs_query_and_compute_timing(
    hass: HomeAssistant, recorder_api: MagicMock, caplog: pytest.LogCaptureFixture
):
    inputs = _register_core(hass)
    recorder_api.statistics_during_period.return_value = _core_rows(inputs, 48)
    caplog.set_level(logging.DEBUG, logger="custom_components.luxtronik2")
    await ScopTracker(hass, _tracker_entry()).async_refresh()
    timing = [r for r in caplog.records if "SCOP refresh" in r.getMessage()]
    assert len(timing) == 1
    message = timing[0].getMessage()
    assert timing[0].levelname == "DEBUG"
    assert "4 statistics" in message
    assert "192 rows" in message
    assert "query" in message
    assert "compute" in message


def test_manifest_after_dependencies_include_recorder():
    manifest_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "luxtronik2"
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "recorder" in manifest["after_dependencies"]


# endregion ScopTracker

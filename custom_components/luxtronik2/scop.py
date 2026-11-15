"""Windowed SCOP from Home Assistant's long-term statistics.

SCOP is a ratio of totals - heat delivered over electricity consumed in a
window - not the average of the instantaneous COP, which overstates it
because the pump draws most power exactly when its COP is lowest. Dividing
the controller's lifetime counters does not work either: the electricity
counters (P1136/P1137) start from zero at a firmware upgrade years after the
heat counters (C0151/C0152). Summing each counter's hourly change over the
window sidesteps both. Design: docs/superpowers/specs/
2026-08-06-true-scop-sensors-design.md (approach D).

Hourly rows, not daily: the hourly statistics table is never purged, and
hours need no alignment to the local-midnight day buckets.

A counter that dips to 0 and recovers makes HA book its whole lifetime value
as that hour's change (#856). Such an hour - change above half the counter's
state, or negative - is dropped for every counter, so heat and electricity
stay paired. The rule was validated on the luxtronik-heatpump-card SPF tile
(Gifford47/luxtronik-heatpump-card#2): it flagged exactly the firmware
upgrade, the P1136/P1137 rescale and two zeroed calculation blocks.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
import time
from typing import Any, Literal

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import (
    get_metadata,
    statistics_during_period,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    LOGGER,
    ScopCircuit,
    SensorKey,
)

__all__ = [
    "SCOP_WINDOWS",
    "ScopCircuit",
    "ScopInputs",
    "ScopResult",
    "ScopTracker",
    "compute_scop",
    "compute_windows",
]

# window_days -> min_coverage_days
SCOP_WINDOWS: dict[int, float] = {365: 30, 30: 7}

type ScopKey = tuple[ScopCircuit, int]

_REFRESH_INTERVAL = timedelta(hours=1)
_STARTUP_DELAY = timedelta(seconds=55)
_UNITS = {"energy": "kWh", "power": "kW"}

# Only a jump bigger than this (kWh) can be a glitch: a young counter's
# state is small, and its first real increments would otherwise trip the
# half-the-state rule.
_GLITCH_MIN_CHANGE = 1.0
_GLITCH_STATE_FRACTION = 0.5


@dataclass(frozen=True)
class ScopInputs:
    """Statistic IDs the calculation reads.

    `elec_other` holds the electricity counters of circuits without a SCOP
    (pool, cooling); they only matter for splitting an external meter. The
    DHW pair is None on a heating-only unit, where those entities never
    exist; DHW then counts as zero.
    """

    heat_heating: str
    heat_dhw: str | None
    elec_heating: str
    elec_dhw: str | None
    elec_other: tuple[str, ...] = ()
    external: str | None = None
    external_kind: Literal["energy", "power"] | None = None

    @property
    def core(self) -> tuple[str, ...]:
        """The counters every kept hour needs."""
        return tuple(
            stat_id
            for stat_id in (
                self.heat_heating,
                self.heat_dhw,
                self.elec_heating,
                self.elec_dhw,
            )
            if stat_id is not None
        )

    @property
    def statistic_ids(self) -> set[str]:
        """Every statistic ID to query."""
        ids = {*self.core, *self.elec_other}
        if self.external is not None:
            ids.add(self.external)
        return ids


@dataclass(frozen=True)
class ScopResult:
    """One circuit's figure over one window."""

    value: float | None
    coverage_days: float
    heat_kwh: float
    electricity_kwh: float
    electricity_source: Literal["controller", "external"]
    window_start: datetime | None


def _is_glitch(row: Mapping[str, Any]) -> bool:
    change = row.get("change")
    if change is None:
        return False
    if change < 0:
        return True
    state = row.get("state")
    return (
        state is not None
        and change > _GLITCH_MIN_CHANGE
        and change > _GLITCH_STATE_FRACTION * state
    )


def _external_energy(row: Mapping[str, Any] | None, kind: str | None) -> float | None:
    """The external meter's kWh in one hour, or None when unknown."""
    if row is None:
        return None
    if kind == "energy":
        return row.get("change")
    # Mean power in kW over a one-hour row is that hour's energy in kWh.
    return row.get("mean")


def compute_scop(
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
    inputs: ScopInputs,
    now: datetime,
    window_days: int,
    min_coverage_days: float,
) -> dict[ScopCircuit, ScopResult]:
    """Heat over electricity per circuit for the window ending at `now`.

    `rows` is what `statistics_during_period` returns for period "hour":
    statistic ID -> rows with `start` (epoch seconds), `change`, `state`
    and `mean`.
    """
    return _compute(_index(rows), inputs, now, window_days, min_coverage_days)


def compute_windows(
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
    inputs: ScopInputs,
    now: datetime,
    windows: Mapping[int, float],
) -> dict[ScopKey, ScopResult]:
    """compute_scop for every window (days -> min coverage), indexing once."""
    by_hour = _index(rows)
    return {
        (circuit, window): result
        for window, min_coverage in windows.items()
        for circuit, result in _compute(
            by_hour, inputs, now, window, min_coverage
        ).items()
    }


type _HourIndex = dict[str, dict[float, Mapping[str, Any]]]


def _index(rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> _HourIndex:
    return {
        stat_id: {row["start"]: row for row in stat_rows}
        for stat_id, stat_rows in rows.items()
    }


def _compute(
    by_hour: _HourIndex,
    inputs: ScopInputs,
    now: datetime,
    window_days: int,
    min_coverage_days: float,
) -> dict[ScopCircuit, ScopResult]:
    def row(stat_id: str | None, start: float) -> Mapping[str, Any] | None:
        return None if stat_id is None else by_hour.get(stat_id, {}).get(start)

    def change(stat_id: str | None, start: float) -> float:
        hour_row = row(stat_id, start)
        value = None if hour_row is None else hour_row.get("change")
        return 0.0 if value is None else value

    use_external = inputs.external is not None
    window_floor = (now - timedelta(days=window_days)).timestamp()
    candidates = sorted(by_hour.get(inputs.heat_heating, {}))

    kept: list[float] = []
    started = False
    for start in candidates:
        hour_rows = [row(stat_id, start) for stat_id in inputs.core]
        if any(r is None or r.get("change") is None for r in hour_rows):
            continue
        if use_external:
            ext_row = row(inputs.external, start)  # pyright: ignore[reportArgumentType]
            if _external_energy(ext_row, inputs.external_kind) is None:
                continue
            hour_rows.append(ext_row)
        hour_rows.extend(row(stat_id, start) for stat_id in inputs.elec_other)
        if any(r is not None and _is_glitch(r) for r in hour_rows):
            continue
        if not started:
            if change(inputs.elec_heating, start) + change(inputs.elec_dhw, start) <= 0:
                continue
            started = True
        if start >= window_floor:
            kept.append(start)

    def total(stat_id: str | None) -> float:
        return sum(change(stat_id, start) for start in kept)

    heat = {
        ScopCircuit.heating: total(inputs.heat_heating),
        ScopCircuit.domestic_water: total(inputs.heat_dhw),
    }
    heat[ScopCircuit.total] = (
        heat[ScopCircuit.heating] + heat[ScopCircuit.domestic_water]
    )

    elec_heating = total(inputs.elec_heating)
    elec_dhw = total(inputs.elec_dhw)
    elec = {
        ScopCircuit.heating: elec_heating,
        ScopCircuit.domestic_water: elec_dhw,
        ScopCircuit.total: elec_heating + elec_dhw,
    }
    if use_external:
        external = sum(
            _external_energy(row(inputs.external, start), inputs.external_kind) or 0.0  # pyright: ignore[reportArgumentType]
            for start in kept
        )
        core = elec_heating + elec_dhw + sum(total(s) for s in inputs.elec_other)
        elec = {
            circuit: (external * share / core if core > 0 else 0.0)
            for circuit, share in elec.items()
        }

    coverage_days = len(kept) / 24
    window_start = datetime.fromtimestamp(kept[0], tz=UTC) if kept else None
    source: Literal["controller", "external"] = (
        "external" if use_external else "controller"
    )
    return {
        circuit: ScopResult(
            value=(
                round(heat[circuit] / elec[circuit], 2)
                if coverage_days >= min_coverage_days and elec[circuit] > 0
                else None
            ),
            coverage_days=coverage_days,
            heat_kwh=heat[circuit],
            electricity_kwh=elec[circuit],
            electricity_source=source,
            window_start=window_start,
        )
        for circuit in ScopCircuit
    }


class ScopTracker:
    """Queries the recorder once an hour and holds every window's results.

    One tracker serves all SCOP entities of a config entry, so the year of
    hourly rows is read once per refresh, not once per entity.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Init the tracker; nothing runs until async_start."""
        self.hass = hass
        self._prefix: str = entry.data[CONF_HA_SENSOR_PREFIX]
        self._entry = entry
        self._external: str | None = entry.options.get(
            CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
            entry.data.get(CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION),
        )
        self._external_warned = False
        self._listeners: list[Callable[[], None]] = []
        self.results: dict[ScopKey, ScopResult] = {}

    @callback
    def async_add_listener(
        self, update_callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Call update_callback after each successful refresh; returns a remover."""
        self._listeners.append(update_callback)

        @callback
        def remove() -> None:
            self._listeners.remove(update_callback)

        return remove

    @callback
    def async_start(self) -> None:
        """Refresh shortly after HA has started, then every hour until unload.

        Not at "started" itself: every integration hits the database then,
        and the year of hourly rows took 17.9 s on a Pi at that moment
        against 1.3 s half a minute later.
        """

        async def _delayed(_now: datetime) -> None:
            await self.async_refresh()

        @callback
        def _at_started(_hass: HomeAssistant) -> None:
            self._entry.async_on_unload(
                async_call_later(self.hass, _STARTUP_DELAY, _delayed)
            )

        async def _interval(_now: datetime) -> None:
            await self.async_refresh()

        self._entry.async_on_unload(async_at_started(self.hass, _at_started))
        self._entry.async_on_unload(
            async_track_time_interval(self.hass, _interval, _REFRESH_INTERVAL)
        )

    def _entity_id(self, key: SensorKey) -> str | None:
        """An enabled counter's entity_id; a disabled one records nothing."""
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"sensor.{self._prefix}_{key}"
        )
        if entity_id is None:
            return None
        entry = registry.async_get(entity_id)
        return None if entry is None or entry.disabled else entity_id

    def _resolve_counters(self) -> ScopInputs | None:
        """Look the counters up by unique_id, so renamed entities still match.

        The heating pair is required. The DHW pair is used only when both
        exist: a heating-only unit never creates those entities.
        """
        heat_heating = self._entity_id(SensorKey.HEAT_AMOUNT_HEATING)
        elec_heating = self._entity_id(SensorKey.HEAT_ENERGY_INPUT)
        if heat_heating is None or elec_heating is None:
            return None
        heat_dhw = self._entity_id(SensorKey.DHW_HEAT_AMOUNT)
        elec_dhw = self._entity_id(SensorKey.DHW_ENERGY_INPUT)
        if heat_dhw is None or elec_dhw is None:
            heat_dhw = elec_dhw = None
        other = tuple(
            entity_id
            for key in (SensorKey.POOL_ENERGY_INPUT, SensorKey.COOLING_ENERGY_INPUT)
            if (entity_id := self._entity_id(key)) is not None
        )
        return ScopInputs(
            heat_heating=heat_heating,
            heat_dhw=heat_dhw,
            elec_heating=elec_heating,
            elec_dhw=elec_dhw,
            elec_other=other,
        )

    async def _async_external_kind(self) -> Literal["energy", "power"] | None:
        """Energy meter (has a sum) or power sensor (has a mean), else None."""
        assert self._external is not None
        metadata = await get_instance(self.hass).async_add_executor_job(
            lambda: get_metadata(self.hass, statistic_ids={self._external})  # pyright: ignore[reportArgumentType]
        )
        meta = metadata.get(self._external)
        if meta is not None:
            if meta[1]["has_sum"]:
                return "energy"
            if meta[1]["mean_type"] != StatisticMeanType.NONE:
                return "power"
        if not self._external_warned:
            LOGGER.warning(
                "SCOP: %s has no long-term statistics (does it have a state_class?);"
                " using the heat pump's own electricity counters instead",
                self._external,
            )
            self._external_warned = True
        return None

    def _query_and_compute(
        self, inputs: ScopInputs, now: datetime
    ) -> dict[ScopKey, ScopResult]:
        """Read the hourly rows and compute every window (executor thread)."""
        started = time.perf_counter()
        rows = statistics_during_period(
            self.hass,
            now - timedelta(days=max(SCOP_WINDOWS)),
            None,
            inputs.statistic_ids,
            "hour",
            _UNITS,
            {"change", "state", "mean"},
        )
        queried = time.perf_counter()
        results = compute_windows(rows, inputs, now, SCOP_WINDOWS)
        LOGGER.debug(
            "SCOP refresh: %d statistics, %d rows, query %.3f s, compute %.3f s",
            len(inputs.statistic_ids),
            sum(len(stat_rows) for stat_rows in rows.values()),
            queried - started,
            time.perf_counter() - queried,
        )
        return results

    async def async_refresh(self) -> None:
        """Re-read the statistics and recompute every window."""
        inputs = self._resolve_counters()
        if inputs is None:
            LOGGER.debug("SCOP: energy counter entities not registered; skipping")
            return
        now = dt_util.utcnow()
        try:
            if self._external is not None:
                kind = await self._async_external_kind()
                if kind is not None:
                    inputs = replace(
                        inputs, external=self._external, external_kind=kind
                    )
            # A year of hourly rows takes ~0.2 s to crunch on a desktop, so
            # the computation runs with the query, off the event loop.
            self.results = await get_instance(self.hass).async_add_executor_job(
                self._query_and_compute, inputs, now
            )
        except Exception:  # a timer must never raise; retried next hour
            LOGGER.warning("SCOP: reading long-term statistics failed", exc_info=True)
            return
        for listener in list(self._listeners):
            listener()

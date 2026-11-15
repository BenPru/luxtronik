"""ScopTracker against a real (in-memory) recorder.

Every other SCOP test patches the recorder API, so the row shape the
calculation rests on - `change` derived from the sum, `start` as epoch
seconds, the unit conversion - is only assumed there. This test imports
hourly statistics into a real recorder and reads them back through
ScopTracker, so a change in HA's statistics API fails here first (the CI
3.14 leg tracks the HA beta for exactly that).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.luxtronik2.const import CONF_HA_SENSOR_PREFIX, DOMAIN, SensorKey
from custom_components.luxtronik2.scop import ScopCircuit, ScopTracker

_PREFIX = "luxtronik"


@pytest.fixture
async def mock_recorder_before_hass(async_setup_recorder_instance: Any) -> None:
    """Set up the recorder before hass, as HA's own recorder tests do."""


def _register(hass: HomeAssistant, key: SensorKey) -> str:
    return (
        er.async_get(hass)
        .async_get_or_create("sensor", DOMAIN, f"sensor.{_PREFIX}_{key}")
        .entity_id
    )


def _import_counter(
    hass: HomeAssistant,
    entity_id: str,
    hours: list,
    change: float,
    glitch_hour: int,
) -> None:
    """Hourly sums of a lifetime counter; one hour books the whole state."""
    state = 1000.0
    total = 0.0
    stats: list[StatisticData] = []
    for i, start in enumerate(hours):
        state += change
        total += state if i == glitch_hour else change
        stats.append({"start": start, "state": state, "sum": total})
    metadata: StatisticMetaData = {
        "has_sum": True,
        "mean_type": StatisticMeanType.NONE,
        "name": None,
        "source": "recorder",
        "statistic_id": entity_id,
        "unit_class": "energy",
        "unit_of_measurement": "kWh",
    }
    async_import_statistics(hass, metadata, stats)


async def test_refresh_reads_real_hourly_statistics(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    hours_back = 10 * 24
    last = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(
        hours=1
    )
    hours = [last - timedelta(hours=hours_back - 1 - i) for i in range(hours_back)]
    counters = {
        SensorKey.HEAT_AMOUNT_HEATING: 2.0,
        SensorKey.HEAT_ENERGY_INPUT: 0.5,
        SensorKey.DHW_HEAT_AMOUNT: 1.0,
        SensorKey.DHW_ENERGY_INPUT: 0.25,
    }
    for key, change in counters.items():
        _import_counter(hass, _register(hass, key), hours, change, glitch_hour=100)
    await async_wait_recording_done(hass)

    entry = MagicMock()
    entry.data = {CONF_HA_SENSOR_PREFIX: _PREFIX}
    entry.options = {}
    tracker = ScopTracker(hass, entry)
    await tracker.async_refresh()

    heating = tracker.results[(ScopCircuit.heating, 30)]
    assert heating.value == 4.0
    assert tracker.results[(ScopCircuit.domestic_water, 30)].value == 4.0
    # Only the hour that booked the whole lifetime value is dropped.
    assert heating.coverage_days * 24 == pytest.approx(hours_back - 1)
    assert heating.electricity_source == "controller"

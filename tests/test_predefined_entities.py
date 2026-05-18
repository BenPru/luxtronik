"""Tests for predefined entity lists."""

from __future__ import annotations

from custom_components.luxtronik.binary_sensor_entities_predefined import (
    BINARY_SENSORS,
)
from custom_components.luxtronik.date_entities_predefined import CALENDAR_ENTITIES
from custom_components.luxtronik.number_entities_predefined import NUMBER_SENSORS
from custom_components.luxtronik.sensor_entities_predefined import SENSORS
from custom_components.luxtronik.switch_entities_predefined import SWITCHES


class TestBinarySensorPredefined:
    def test_has_entries(self):
        assert len(BINARY_SENSORS) > 0

    def test_all_have_key(self):
        for bs in BINARY_SENSORS:
            assert bs.key is not None
            assert bs.luxtronik_key is not None

    def test_unique_keys(self):
        keys = [bs.key for bs in BINARY_SENSORS]
        assert len(keys) == len(set(keys))


class TestSwitchPredefined:
    def test_has_entries(self):
        assert len(SWITCHES) > 0

    def test_all_have_key(self):
        for sw in SWITCHES:
            assert sw.key is not None
            assert sw.luxtronik_key is not None


class TestSensorPredefined:
    def test_has_entries(self):
        assert len(SENSORS) > 0

    def test_all_have_key(self):
        for s in SENSORS:
            assert s.key is not None
            assert s.luxtronik_key is not None


class TestNumberPredefined:
    def test_has_entries(self):
        assert len(NUMBER_SENSORS) > 0

    def test_all_have_key(self):
        for n in NUMBER_SENSORS:
            assert n.key is not None
            assert n.luxtronik_key is not None


class TestDatePredefined:
    def test_has_entries(self):
        assert len(CALENDAR_ENTITIES) > 0

    def test_all_have_key(self):
        for d in CALENDAR_ENTITIES:
            assert d.key is not None
            assert d.luxtronik_key is not None

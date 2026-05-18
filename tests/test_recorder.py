"""Tests for custom_components.luxtronik.recorder."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.luxtronik.const import SensorAttrKey
from custom_components.luxtronik.recorder import exclude_attributes


class TestExcludeAttributes:
    def test_returns_set(self):
        hass = MagicMock()
        result = exclude_attributes(hass)
        assert isinstance(result, set)

    def test_contains_all_sensor_attr_keys(self):
        hass = MagicMock()
        result = exclude_attributes(hass)
        for attr in SensorAttrKey:
            assert attr.value in result

    def test_not_empty(self):
        hass = MagicMock()
        result = exclude_attributes(hass)
        assert len(result) > 0

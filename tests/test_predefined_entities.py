"""Tests for predefined entity lists."""

from __future__ import annotations

from collections.abc import Iterator
import importlib
import pkgutil

from packaging.version import Version

import custom_components.luxtronik2 as luxtronik2
from custom_components.luxtronik2.binary_sensor_entities_predefined import (
    BINARY_SENSORS,
)
from custom_components.luxtronik2.date_entities_predefined import CALENDAR_ENTITIES
from custom_components.luxtronik2.model import LuxtronikEntityDescription
from custom_components.luxtronik2.number_entities_predefined import NUMBER_SENSORS
from custom_components.luxtronik2.sensor_entities_predefined import SENSORS
from custom_components.luxtronik2.switch_entities_predefined import SWITCHES


def _is_luxtronik_description(item: object) -> bool:
    """Whether item is one of our entity descriptions.

    Deliberately not isinstance(): HA's `frozen_or_thawed=True` metaclass
    builds distinct frozen and thawed class objects, so the
    LuxtronikEntityDescription appearing in a description's MRO is a
    different object from the imported one and isinstance is always False.
    Matching on the MRO by name sidesteps that.
    """
    return any(
        base.__name__ == LuxtronikEntityDescription.__name__
        for base in type(item).__mro__
    )


def _all_descriptions() -> Iterator[LuxtronikEntityDescription]:
    """Yield every entity description defined anywhere in the package.

    Descriptions live in the *_entities_predefined modules for most
    platforms, but water_heater and climate declare theirs inline, so this
    walks every module rather than a fixed list of imports.
    """
    for module_info in pkgutil.iter_modules(luxtronik2.__path__):
        module = importlib.import_module(f"{luxtronik2.__name__}.{module_info.name}")
        for attr_name in dir(module):
            if attr_name.startswith("__"):
                continue
            value = getattr(module, attr_name)
            if isinstance(value, (list, tuple)):
                for item in value:
                    if _is_luxtronik_description(item):
                        yield item


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


class TestFirmwareVersionFields:
    """Every firmware gate must hold a Version, on every platform.

    The four firmware fields are compared against a Version with `<` / `>`.
    A bare int or an Enum member raises TypeError at entity setup, because
    Version.__lt__ returns NotImplemented and neither int nor Enum defines
    the reflected operator against it - so the failure surfaces as entities
    silently missing from a user's installation, not as a test failure.

    This walks every description the package defines rather than a
    hand-listed set, so a new platform or a new predefined list is covered
    the moment it exists.
    """

    FIELDS = (
        "min_firmware_version",
        "max_firmware_version",
        "min_firmware_version_minor",
        "max_firmware_version_minor",
    )

    def test_all_descriptions_use_version_or_none(self):
        descriptions = list(_all_descriptions())
        # Guard the guard: an import that silently yielded nothing would
        # make every assertion below vacuous.
        assert len(descriptions) > 100

        offenders = [
            (type(descr).__name__, descr.key, name, repr(value))
            for descr in descriptions
            for name in self.FIELDS
            if not isinstance(
                (value := getattr(descr, name, None)), (Version, type(None))
            )
        ]
        assert offenders == []

    def test_at_least_one_gate_is_actually_in_use(self):
        """Otherwise the check above passes trivially forever."""
        assert any(
            getattr(descr, name, None) is not None
            for descr in _all_descriptions()
            for name in self.FIELDS
        )

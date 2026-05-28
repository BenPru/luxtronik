"""Tests for entity platform module imports and constants."""

from __future__ import annotations


class TestBinarySensorModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik2.binary_sensor import (
            LuxtronikBinarySensorEntity,
            async_setup_entry,
        )

        assert LuxtronikBinarySensorEntity is not None
        assert callable(async_setup_entry)


class TestSwitchModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik2.switch import (
            LuxtronikSwitchEntity,
            async_setup_entry,
        )

        assert LuxtronikSwitchEntity is not None
        assert callable(async_setup_entry)


class TestSensorModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik2.sensor import async_setup_entry

        assert callable(async_setup_entry)


class TestNumberModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik2.number import async_setup_entry

        assert callable(async_setup_entry)


class TestSelectModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik2.select import async_setup_entry

        assert callable(async_setup_entry)


class TestDateModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik2.date import async_setup_entry

        assert callable(async_setup_entry)


class TestConfigFlowModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik2.config_flow import LuxtronikFlowHandler

        assert LuxtronikFlowHandler is not None


class TestParallelUpdates:
    """PARALLEL_UPDATES must be defined on every platform module.

    Read-only platforms (sensor, binary_sensor, update) use 0 (unlimited)
    because they only read from the coordinator's cached data.

    Writable platforms (number, switch, select, climate, water_heater, date)
    use 1 (serialized) because writes go through a single TCP socket.
    """

    def test_read_only_platforms_have_parallel_updates_0(self):
        from custom_components.luxtronik2.binary_sensor import PARALLEL_UPDATES as bs
        from custom_components.luxtronik2.sensor import PARALLEL_UPDATES as s
        from custom_components.luxtronik2.update import PARALLEL_UPDATES as u

        assert s == 0
        assert bs == 0
        assert u == 0

    def test_writable_platforms_have_parallel_updates_1(self):
        from custom_components.luxtronik2.climate import PARALLEL_UPDATES as cl
        from custom_components.luxtronik2.date import PARALLEL_UPDATES as d
        from custom_components.luxtronik2.number import PARALLEL_UPDATES as n
        from custom_components.luxtronik2.select import PARALLEL_UPDATES as sel
        from custom_components.luxtronik2.switch import PARALLEL_UPDATES as sw
        from custom_components.luxtronik2.water_heater import PARALLEL_UPDATES as wh

        assert n == 1
        assert sw == 1
        assert sel == 1
        assert cl == 1
        assert wh == 1
        assert d == 1

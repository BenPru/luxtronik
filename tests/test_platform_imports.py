"""Tests for entity platform module imports and constants."""

from __future__ import annotations


class TestBinarySensorModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik.binary_sensor import (
            LuxtronikBinarySensorEntity,
            async_setup_entry,
        )

        assert LuxtronikBinarySensorEntity is not None
        assert callable(async_setup_entry)


class TestSwitchModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik.switch import (
            LuxtronikSwitchEntity,
            async_setup_entry,
        )

        assert LuxtronikSwitchEntity is not None
        assert callable(async_setup_entry)


class TestSensorModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik.sensor import async_setup_entry

        assert callable(async_setup_entry)


class TestNumberModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik.number import async_setup_entry

        assert callable(async_setup_entry)


class TestSelectModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik.select import async_setup_entry

        assert callable(async_setup_entry)


class TestDateModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik.date import async_setup_entry

        assert callable(async_setup_entry)


class TestConfigFlowModuleImport:
    def test_module_imports(self):
        from custom_components.luxtronik.config_flow import LuxtronikFlowHandler

        assert LuxtronikFlowHandler is not None

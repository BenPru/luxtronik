"""Tests for custom_components.luxtronik2.model."""

from __future__ import annotations

from homeassistant.const import Platform

from conftest import make_coordinator_data
from custom_components.luxtronik2.const import (
    DeviceKey,
    LuxParameter,
    LuxVisibility,
)
from custom_components.luxtronik2.model import (
    LuxtronikBinarySensorEntityDescription,
    LuxtronikClimateDescription,
    LuxtronikDateEntityDescription,
    LuxtronikEntityAttributeDescription,
    LuxtronikEntityDescription,
    LuxtronikNumberDescription,
    LuxtronikSensorDescription,
    LuxtronikSwitchDescription,
    LuxtronikUpdateEntityDescription,
    LuxtronikWaterHeaterDescription,
    metaclass_resolver,
)


class TestLuxtronikCoordinatorData:
    def test_coordinator_data_creation(self):
        data = make_coordinator_data(
            parameters={"key1": "val1"},
            calculations={"key2": "val2"},
            visibilities={"key3": "val3"},
        )
        assert data.parameters.get("key1") is not None
        assert data.calculations.get("key2") is not None
        assert data.visibilities.get("key3") is not None


class TestLuxtronikEntityDescription:
    def test_defaults(self):
        desc = LuxtronikEntityDescription(key="test_entity")
        assert desc.has_entity_name is True
        assert desc.device_key == DeviceKey.heatpump
        assert desc.luxtronik_key == LuxParameter.UNSET
        assert desc.visibility == LuxVisibility.UNSET
        assert desc.update_interval is None
        assert desc.icon_by_state is None
        assert desc.extra_attributes == ()
        assert desc.min_firmware_version is None
        assert desc.max_firmware_version is None

    def test_custom_values(self):
        desc = LuxtronikEntityDescription(
            key="test_entity",
            device_key=DeviceKey.heating,
            luxtronik_key=LuxParameter.P0003_MODE_HEATING,
            translation_key="custom_key",
        )
        assert desc.device_key == DeviceKey.heating
        assert desc.luxtronik_key == LuxParameter.P0003_MODE_HEATING
        assert desc.translation_key == "custom_key"


class TestLuxtronikSensorDescription:
    def test_defaults(self):
        desc = LuxtronikSensorDescription(key="sensor_test")
        assert LuxtronikSensorDescription.platform == Platform.SENSOR
        assert desc.factor is None
        assert desc.native_precision is None

    def test_with_factor(self):
        desc = LuxtronikSensorDescription(
            key="sensor_test", factor=0.1, native_precision=1
        )
        assert desc.factor == 0.1
        assert desc.native_precision == 1


class TestLuxtronikNumberDescription:
    def test_defaults(self):
        desc = LuxtronikNumberDescription(key="number_test")
        assert LuxtronikNumberDescription.platform == Platform.NUMBER
        assert desc.factor is None
        assert desc.native_precision is None


class TestLuxtronikBinarySensorDescription:
    def test_defaults(self):
        desc = LuxtronikBinarySensorEntityDescription(key="bs_test")
        assert LuxtronikBinarySensorEntityDescription.platform == Platform.BINARY_SENSOR
        assert desc.on_state is True
        assert desc.off_state is False
        assert desc.inverted is False
        assert desc.on_states is None

    def test_custom_states(self):
        desc = LuxtronikBinarySensorEntityDescription(
            key="bs_test",
            on_state="active",
            on_states=["active", "running"],
            off_state="inactive",
            inverted=True,
        )
        assert desc.on_state == "active"
        assert desc.on_states == ["active", "running"]


# ===========================================================================
# metaclass_resolver (model.py lines 182-188)
# ===========================================================================


class TestMetaclassResolver:
    def test_single_metaclass(self):
        class A:
            pass

        result = metaclass_resolver(A)
        assert isinstance(result, type)
        assert issubclass(type(result), type)

    def test_multiple_same_metaclass(self):
        class A:
            pass

        class B:
            pass

        result = metaclass_resolver(A, B)
        assert isinstance(result, type)

    def test_different_metaclasses(self):
        class MetaA(type):
            pass

        class MetaB(type):
            pass

        class A(metaclass=MetaA):
            pass

        class B(metaclass=MetaB):
            pass

        result = metaclass_resolver(A, B)
        assert isinstance(result, type)
        assert issubclass(type(type(result)), type)


class TestLuxtronikSwitchDescription:
    def test_defaults(self):
        desc = LuxtronikSwitchDescription(key="switch_test")
        assert LuxtronikSwitchDescription.platform == Platform.SWITCH
        assert desc.on_state is True
        assert desc.off_state is False
        assert desc.inverted is False


class TestLuxtronikClimateDescription:
    def test_defaults(self):
        desc = LuxtronikClimateDescription(key="climate_test")
        assert LuxtronikClimateDescription.platform == Platform.CLIMATE
        assert desc.hvac_modes == []
        assert desc.hvac_mode_mapping == {}
        assert desc.preset_modes is None


class TestLuxtronikWaterHeaterDescription:
    def test_defaults(self):
        desc = LuxtronikWaterHeaterDescription(key="wh_test")
        assert LuxtronikWaterHeaterDescription.platform == Platform.WATER_HEATER
        assert desc.operation_list == []


class TestLuxtronikUpdateEntityDescription:
    def test_defaults(self):
        LuxtronikUpdateEntityDescription(key="update_test")
        assert LuxtronikUpdateEntityDescription.platform == Platform.UPDATE


class TestLuxtronikDateEntityDescription:
    def test_defaults(self):
        LuxtronikDateEntityDescription(key="date_test")
        assert LuxtronikDateEntityDescription.platform == Platform.DATE


class TestLuxtronikEntityAttributeDescription:
    def test_defaults(self):
        from custom_components.luxtronik2.const import SensorAttrKey

        desc = LuxtronikEntityAttributeDescription(
            key=SensorAttrKey.LUXTRONIK_KEY,
        )
        assert desc.luxtronik_key == LuxParameter.UNSET
        assert desc.format is None
        assert desc.restore_on_startup is False

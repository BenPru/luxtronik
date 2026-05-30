"""The Luxtronik models."""

# region Imports
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.climate import (
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.date import DateEntityDescription
from homeassistant.components.number import NumberEntityDescription, NumberMode
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.components.update import UpdateDeviceClass, UpdateEntityDescription
from homeassistant.components.water_heater import (
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.typing import StateType
from luxtronik import Calculations, Parameters, Visibilities
from packaging.version import Version

from .const import (
    UPDATE_INTERVAL_VERY_SLOW,
    DeviceKey,
    # FirmwareVersionMinor,
    LuxCalculation,
    LuxOperationMode,
    LuxParameter,
    LuxVisibility,
    SensorAttrFormat,
    SensorAttrKey,
)

# endregion Imports


@dataclass
class LuxtronikCoordinatorData:
    """Data Type of LuxtronikCoordinator's data."""

    parameters: Parameters
    calculations: Calculations
    visibilities: Visibilities


@dataclass
class LuxtronikEntityAttributeDescription:
    """A class that describes Home Assistant Luxtronik entity attributes."""

    # This is the key identifier for this entity
    key: SensorAttrKey
    luxtronik_key: LuxParameter | LuxCalculation = LuxParameter.UNSET
    format: SensorAttrFormat | None = None
    restore_on_startup: bool = False


class LuxtronikEntityDescription(EntityDescription, frozen_or_thawed=True):
    """Class describing Luxtronik entities."""

    has_entity_name: bool = True

    # Bug in python: Have to assign a value:
    platform = Platform.AIR_QUALITY

    update_interval: timedelta | None = None
    icon_by_state: dict[StateType | date | datetime | Decimal, str] | None = None
    device_key: DeviceKey = DeviceKey.heatpump
    luxtronik_key: LuxParameter | LuxCalculation = LuxParameter.UNSET
    translation_key: str | None = None
    translation_key_name: str | None = None
    visibility: LuxVisibility | LuxParameter = LuxVisibility.UNSET
    invisible_if_value: Any | None = None
    min_firmware_version_minor: Version | None = None
    max_firmware_version_minor: Version | None = None
    min_firmware_version: Version | None = None
    max_firmware_version: Version | None = None

    extra_attributes: tuple[LuxtronikEntityAttributeDescription, ...] = ()
    entity_registry_enabled_default: bool = True
    state_class: str | None = None


class LuxtronikSensorDescription(  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    LuxtronikEntityDescription,
    SensorEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik sensor entities."""

    platform = Platform.SENSOR
    factor: float | None = None
    native_precision: int | None = None


class LuxtronikIndexSensorDescription(  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    LuxtronikSensorDescription,
    SensorEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik index sensor entities."""

    luxtronik_key_timestamp: LuxParameter | LuxCalculation = LuxParameter.UNSET


class LuxtronikNumberDescription(
    LuxtronikEntityDescription,
    NumberEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik number sensor entities."""

    platform = Platform.NUMBER
    update_interval: timedelta | None = UPDATE_INTERVAL_VERY_SLOW
    factor: float | None = None
    native_precision: int | None = None
    mode: NumberMode = NumberMode.AUTO


class LuxtronikBinarySensorEntityDescription(
    LuxtronikEntityDescription,
    BinarySensorEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik binary sensor entities."""

    platform = Platform.BINARY_SENSOR
    on_state: str | bool = True
    on_states: list[str] | None = None
    off_state: str | bool = False
    inverted: bool = False


class LuxtronikSwitchDescription(
    LuxtronikEntityDescription,
    SwitchEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik switch entities."""

    platform = Platform.SWITCH
    update_interval: timedelta = UPDATE_INTERVAL_VERY_SLOW
    on_state: str | bool = True
    on_states: list[str] | None = None
    off_state: str | bool = False
    inverted: bool = False


class LuxtronikClimateDescription(
    LuxtronikEntityDescription,
    ClimateEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik climate entities."""

    platform = Platform.CLIMATE
    hvac_modes: list[HVACMode] = field(default_factory=list)
    hvac_mode_mapping: dict[str, str] = field(default_factory=dict[str, str])
    hvac_action_mapping: dict[str, str] = field(default_factory=dict[str, str])
    preset_modes: list[str] | None = None
    supported_features: ClimateEntityFeature = ClimateEntityFeature(0)
    luxtronik_key_current_temperature: LuxCalculation | str = LuxCalculation.UNSET
    luxtronik_key_current_action: LuxCalculation = LuxCalculation.UNSET
    luxtronik_action_active: str | None = None
    luxtronik_key_target_temperature: LuxParameter | LuxCalculation = LuxParameter.UNSET
    luxtronik_key_correction_factor: LuxParameter = LuxParameter.UNSET
    luxtronik_key_correction_target: LuxParameter = LuxParameter.UNSET
    min_temp: float | None = None
    max_temp: float | None = None
    temperature_unit: str = UnitOfTemperature.CELSIUS


def metaclass_resolver(*classes):
    metaclass = tuple(set(type(cls) for cls in classes))
    metaclass = (
        metaclass[0]
        if len(metaclass) == 1
        else type("_".join(mcls.__name__ for mcls in metaclass), metaclass, {})
    )  # class M_C
    return metaclass("_".join(cls.__name__ for cls in classes), classes, {})


class LuxtronikWaterHeaterDescription(
    LuxtronikEntityDescription,
    WaterHeaterEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik water heater entities."""

    platform = Platform.WATER_HEATER
    operation_list: list[str] = field(default_factory=list)
    supported_features: WaterHeaterEntityFeature = WaterHeaterEntityFeature(0)
    luxtronik_key_current_temperature: LuxCalculation = LuxCalculation.UNSET
    luxtronik_key_current_action: LuxCalculation = LuxCalculation.UNSET
    luxtronik_action_heating: LuxOperationMode | None = None
    luxtronik_key_target_temperature: LuxParameter = LuxParameter.UNSET
    luxtronik_key_target_temperature_high: LuxParameter = LuxParameter.UNSET
    luxtronik_key_target_temperature_low: LuxParameter = LuxParameter.UNSET
    temperature_unit: str = UnitOfTemperature.CELSIUS


class LuxtronikUpdateEntityDescription(
    LuxtronikEntityDescription,
    UpdateEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik update entities."""

    device_class = UpdateDeviceClass.FIRMWARE
    platform = Platform.UPDATE


class LuxtronikDateEntityDescription(
    LuxtronikEntityDescription,
    DateEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik date entities."""

    platform = Platform.DATE


class LuxtronikSelectEntityDescription(
    LuxtronikEntityDescription,
    SelectEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik date entities."""

    platform = Platform.SELECT

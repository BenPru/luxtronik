"""The Luxtronik models."""
# region Imports
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from luxtronik import Calculations, Parameters, Visibilities

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.climate import (
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.number import NumberEntityDescription, NumberMode
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.components.update import UpdateEntityDescription, UpdateDeviceClass
from homeassistant.components.water_heater import (
    WaterHeaterEntityEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.typing import StateType

from .const import (
    UPDATE_INTERVAL_VERY_SLOW,
    DeviceKey,
    FirmwareVersionMinor,
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


@dataclass
class LuxtronikEntityDescription(EntityDescription):
    """Class describing Luxtronik entities."""

    has_entity_name = True

    # Bug in python: Have to assign a value:
    platform = Platform.AIR_QUALITY

    update_interval: timedelta | None = None
    icon_by_state: dict[StateType | date | datetime | Decimal, str] | None = None
    device_key: DeviceKey = DeviceKey.heatpump
    luxtronik_key: LuxParameter | LuxCalculation = LuxParameter.UNSET
    translation_key_name: str | None = None
    visibility: LuxVisibility = LuxVisibility.UNSET
    invisible_if_value: Any | None = None
    min_firmware_version_minor: FirmwareVersionMinor | None = None

    extra_attributes: tuple(LuxtronikEntityAttributeDescription) = ()
    state_class: str | None = None


@dataclass
class LuxtronikSensorDescription(
    LuxtronikEntityDescription,
    SensorEntityDescription,
):
    """Class describing Luxtronik sensor entities."""

    platform = Platform.SENSOR
    factor: float | None = None
    native_precision: int | None = None


@dataclass
class LuxtronikIndexSensorDescription(
    LuxtronikSensorDescription,
    SensorEntityDescription,
):
    """Class describing Luxtronik index sensor entities."""

    luxtronik_key_timestamp: LuxParameter | LuxCalculation = LuxParameter.UNSET


@dataclass
class LuxtronikNumberDescription(
    LuxtronikEntityDescription,
    NumberEntityDescription,
):
    """Class describing Luxtronik number sensor entities."""

    platform = Platform.NUMBER
    update_interval = UPDATE_INTERVAL_VERY_SLOW
    factor: float | None = None
    native_precision: int | None = None
    mode: NumberMode = NumberMode.AUTO


@dataclass
class LuxtronikBinarySensorEntityDescription(
    LuxtronikEntityDescription,
    BinarySensorEntityDescription,
):
    """Class describing Luxtronik binary sensor entities."""

    platform = Platform.BINARY_SENSOR
    on_state: str | bool = True
    on_states: list[str] | None = None
    off_state: str | bool = False
    inverted = False


@dataclass
class LuxtronikSwitchDescription(
    LuxtronikEntityDescription,
    SwitchEntityDescription,
):
    """Class describing Luxtronik switch entities."""

    platform = Platform.SWITCH
    update_interval = UPDATE_INTERVAL_VERY_SLOW
    on_state: str | bool = True
    on_states: list[str] | None = None
    off_state: str | bool = False
    inverted = False


@dataclass
class LuxtronikClimateDescription(
    LuxtronikEntityDescription,
    ClimateEntityDescription,
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
    temperature_unit: str = UnitOfTemperature.CELSIUS


@dataclass
class LuxtronikWaterHeaterDescription(
    LuxtronikEntityDescription,
    WaterHeaterEntityEntityDescription,
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


@dataclass
class LuxtronikUpdateEntityDescription(
    LuxtronikEntityDescription,
    UpdateEntityDescription,
):
    """Class describing Luxtronik update entities."""

    device_class = UpdateDeviceClass.FIRMWARE
    platform = Platform.UPDATE
    

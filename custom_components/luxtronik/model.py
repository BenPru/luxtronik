"""The Luxtronik models."""
# region Imports
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.climate import (
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.number import NumberEntityDescription, NumberMode
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.components.update import UpdateEntityDescription
from homeassistant.components.water_heater import (
    WaterHeaterEntityEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import EntityDescription

from .const import (
    DeviceKey,
    FirmwareVersionMinor,
    LuxCalculation,
    LuxOperationMode,
    LuxParameter,
    LuxVisibility,
)

# endregion Imports


@dataclass
class LuxtronikEntityDescription(EntityDescription):
    """Class describing Luxtronik entities."""

    icon_by_state: dict[str, str] | None = None

    has_entity_name = True

    device_key: DeviceKey = DeviceKey.heatpump
    luxtronik_key: LuxParameter | LuxCalculation = LuxParameter.UNSET
    translation_key_name: str | None = None
    visibility: LuxVisibility = LuxVisibility.UNSET
    invisible_if_value: Any | None = None
    min_firmware_version_minor: FirmwareVersionMinor | None = None


@dataclass
class LuxtronikSensorDescription(
    LuxtronikEntityDescription,
    SensorEntityDescription,
):
    """Class describing Luxtronik sensor entities."""

    factor: float | None = None
    decimal_places: int | None = None


@dataclass
class LuxtronikNumberDescription(
    LuxtronikEntityDescription,
    NumberEntityDescription,
):
    """Class describing Luxtronik number sensor entities."""

    factor: float | None = None
    decimal_places: int | None = None
    mode: NumberMode = NumberMode.AUTO


@dataclass
class LuxtronikSwitchDescription(
    LuxtronikEntityDescription,
    SwitchEntityDescription,
):
    """Class describing Luxtronik switch entities."""

    on_state: str | bool = True
    on_states: list[str] | None = None
    off_state: str | bool = False
    icon_on: str | None = None
    icon_off: str | None = None
    inverted = False


@dataclass
class LuxtronikClimateDescription(
    LuxtronikEntityDescription,
    ClimateEntityDescription,
):
    """Class describing Luxtronik climate entities."""

    hvac_modes: list[HVACMode] = field(default_factory=list)
    preset_modes: list[str] | None = None
    supported_features: ClimateEntityFeature = ClimateEntityFeature(0)
    luxtronik_key_current_temperature: LuxCalculation | str = LuxCalculation.UNSET
    luxtronik_key_current_action: LuxCalculation = LuxCalculation.UNSET
    luxtronik_action_heating: str | None = None
    luxtronik_key_target_temperature: LuxParameter | LuxCalculation = LuxParameter.UNSET
    luxtronik_key_correction_factor: LuxParameter = LuxParameter.UNSET
    luxtronik_key_correction_target: LuxParameter = LuxParameter.UNSET
    unit_of_measurement: str = UnitOfTemperature.CELSIUS


@dataclass
class LuxtronikWaterHeaterDescription(
    LuxtronikEntityDescription,
    WaterHeaterEntityEntityDescription,
):
    """Class describing Luxtronik water heater entities."""

    operation_list: list[str] = field(default_factory=list)
    supported_features: WaterHeaterEntityFeature = WaterHeaterEntityFeature(0)
    luxtronik_key_current_temperature: LuxCalculation = LuxCalculation.UNSET
    luxtronik_key_current_action: LuxCalculation = LuxCalculation.UNSET
    luxtronik_action_heating: LuxOperationMode | None = None
    luxtronik_key_target_temperature: LuxParameter = LuxParameter.UNSET
    luxtronik_key_target_temperature_high: LuxParameter = LuxParameter.UNSET
    luxtronik_key_target_temperature_low: LuxParameter = LuxParameter.UNSET


@dataclass
class LuxtronikUpdateDescription(
    LuxtronikEntityDescription,
    UpdateEntityDescription,
):
    """Class describing Luxtronik update entities."""

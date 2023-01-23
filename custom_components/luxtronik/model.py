"""The Luxtronik models."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.climate import (
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.number import NumberEntityDescription, NumberMode
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.components.water_heater import (
    WaterHeaterEntityEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.helpers.entity import EntityDescription

from .const import (
    DeviceKey,
    FirmwareVersionMinor,
    LuxCalculation,
    LuxParameter,
    LuxVisibility,
)


@dataclass
class LuxtronikEntityDescription(EntityDescription):
    """Class describing Luxtronik entities."""

    # def __post_init__(self):

    icon: str | dict[str, str] | None = None
    has_entity_name = True

    device_key: DeviceKey = DeviceKey.heatpump
    luxtronik_key: LuxParameter | LuxCalculation = None
    translation_key_name: str = None
    visibility: LuxVisibility = None
    invisibly_if_value = None
    min_firmware_version_minor: FirmwareVersionMinor = None


@dataclass
class LuxtronikSensorDescription(
    LuxtronikEntityDescription,
    SensorEntityDescription,
):
    """Class describing Luxtronik sensor entities."""

    factor: float = None
    decimal_places: int = None


@dataclass
class LuxtronikNumberDescription(
    LuxtronikSensorDescription,
    NumberEntityDescription,
):
    """Class describing Luxtronik number sensor entities."""

    mode: NumberMode = NumberMode.AUTO


@dataclass
class LuxtronikSwitchDescription(
    LuxtronikEntityDescription,
    SwitchEntityDescription,
):
    """Class describing Luxtronik switch entities."""

    on_state: str | bool = True
    on_states: list[str] = None
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

    hvac_modes: list[HVACMode] | None = None
    preset_modes: list[str] | None = None
    supported_features: ClimateEntityFeature = ClimateEntityFeature(0)
    luxtronik_key_current_temperature: LuxCalculation | str = None
    luxtronik_key_current_action: LuxCalculation = None
    luxtronik_action_heating: str = None
    luxtronik_key_target_temperature: LuxParameter | LuxCalculation = None
    luxtronik_key_correction_factor: LuxParameter = None
    luxtronik_key_correction_target: LuxParameter = None


@dataclass
class LuxtronikWaterHeaterDescription(
    LuxtronikEntityDescription,
    WaterHeaterEntityEntityDescription,
):
    """Class describing Luxtronik water heater entities."""

    operation_list: list[str] | None = None
    supported_features: WaterHeaterEntityFeature = WaterHeaterEntityFeature(0)
    luxtronik_key_current_temperature: LuxCalculation = None
    luxtronik_key_current_action: LuxCalculation = None
    luxtronik_action_heating: str = None
    luxtronik_key_target_temperature: LuxParameter = None
    luxtronik_key_target_temperature_high: LuxParameter = None
    luxtronik_key_target_temperature_low: LuxParameter = None

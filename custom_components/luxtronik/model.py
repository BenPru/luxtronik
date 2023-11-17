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
    Calculation_SensorKey,
    DeviceKey,
    FirmwareVersionMinor,
    LuxOperationMode,
    Parameter_All_SensorKey,
    Parameter_SensorKey,
    SensorAttrFormat,
    SensorAttrKey,
    Visibility_SensorKey,
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
    luxtronik_key: Calculation_SensorKey | Parameter_SensorKey = Parameter_SensorKey.UNSET
    format: SensorAttrFormat | None = None
    restore_on_startup: bool = False
    default_value: Any | None = None


ATTR_DESCRIPTION = LuxtronikEntityAttributeDescription(
    key=SensorAttrKey.DESCRIPTION, default_value="_"
)


@dataclass
class LuxtronikEntityDescription(EntityDescription):
    """Class describing Luxtronik entities."""

    key: str = 'PLACEHOLDER'

    has_entity_name = True
    state_mapping: enumerate|None = None

    # Bug in python: Have to assign a value:
    platform = Platform.AIR_QUALITY

    luxtronik_key: Calculation_SensorKey | Parameter_All_SensorKey = (
        Parameter_SensorKey.UNSET
    )

    update_interval: timedelta | None = None
    icon_by_state: dict[StateType | date | datetime | Decimal, str] | None = None
    device_key: DeviceKey = DeviceKey.heatpump
    translation_key_name: str | None = None
    visibility: Visibility_SensorKey = Visibility_SensorKey.UNSET
    invisible_if_value: Any | None = None
    min_firmware_version_minor: FirmwareVersionMinor | None = None

    extra_attributes: list[LuxtronikEntityAttributeDescription] = field(
        default_factory=list
    )
    state_class: str | None = None
    event_id_on_change: str | None = None


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
class LuxtronikPeriodStatSensorDescription(
    LuxtronikSensorDescription,
    SensorEntityDescription,
):
    """Class describing Luxtronik PeriodStat sensor entities."""

    event_id_impulse_active: str | None = "IMPULSE_START"
    event_id_impulse_inactive: str | None = "IMPULSE_END"


@dataclass
class LuxtronikIndexSensorDescription(
    LuxtronikSensorDescription,
    SensorEntityDescription,
):
    """Class describing Luxtronik index sensor entities."""

    luxtronik_key_timestamp: Parameter_All_SensorKey | Calculation_SensorKey = Parameter_SensorKey.UNSET


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
    event_id_on_true: str | None = None
    event_id_on_false: str | None = None


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
    luxtronik_key_current_temperature: Calculation_SensorKey | str = Calculation_SensorKey.UNSET
    luxtronik_key_current_action: Calculation_SensorKey = Calculation_SensorKey.UNSET
    luxtronik_action_active: str | None = None
    luxtronik_key_target_temperature: Parameter_SensorKey | Calculation_SensorKey = Parameter_SensorKey.UNSET
    luxtronik_key_correction_factor: Parameter_SensorKey = Parameter_SensorKey.UNSET
    luxtronik_key_correction_target: Parameter_SensorKey = Parameter_SensorKey.UNSET
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
    luxtronik_key_current_temperature: Calculation_SensorKey = Calculation_SensorKey.UNSET
    luxtronik_key_current_action: Calculation_SensorKey = Calculation_SensorKey.UNSET
    luxtronik_action_heating: LuxOperationMode | None = None
    luxtronik_key_target_temperature: Parameter_SensorKey = Parameter_SensorKey.UNSET
    luxtronik_key_target_temperature_high: Parameter_SensorKey = Parameter_SensorKey.UNSET
    luxtronik_key_target_temperature_low: Parameter_SensorKey = Parameter_SensorKey.UNSET
    temperature_unit: str = UnitOfTemperature.CELSIUS


@dataclass
class LuxtronikUpdateEntityDescription(
    LuxtronikEntityDescription,
    UpdateEntityDescription,
):
    """Class describing Luxtronik update entities."""

    device_class = UpdateDeviceClass.FIRMWARE
    platform = Platform.UPDATE


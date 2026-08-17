"""The Luxtronik models."""

# region Imports
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

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
from homeassistant.components.text import TextEntityDescription
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
    DeviceKey,
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

    # Derived once per poll by LuxtronikCoordinator._update_dhw_transition_hold().
    # Defaulted so every other construction site (tests, diagnostics) is unaffected.
    dhw_transition_hold: bool = False


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

    icon_by_state: dict[StateType | date | datetime | Decimal, str] | None = None
    device_key: DeviceKey = DeviceKey.heatpump
    luxtronik_key: LuxParameter | LuxCalculation = LuxParameter.UNSET
    translation_key: str | None = None
    translation_key_name: str | None = None
    visibility: LuxVisibility | LuxParameter = LuxVisibility.UNSET
    visibility_formula: str | None = None
    entity_active_formula: str | None = None
    # All four are compared against a Version with `<` / `>`, so they must be
    # Version instances - a bare int or an Enum member raises TypeError at
    # entity setup, because Version.__lt__ returns NotImplemented and neither
    # int nor Enum defines the reflected operator against it.
    #
    # The `_minor` pair carries <minor>.<patch> (V3.90.1 -> Version("90.1")),
    # which is why a whole-number type cannot express the thresholds actually
    # in use - see water_heater.py, where 88.2 and 88.3 split the DHW target
    # parameter pair. Prefer testing whether the register is present at all
    # (`.value is None`) over any version gate; reserve these for registers
    # present on both sides of a change whose *meaning* moves.
    min_firmware_version_minor: Version | None = None
    max_firmware_version_minor: Version | None = None
    min_firmware_version: Version | None = None
    max_firmware_version: Version | None = None

    extra_attributes: tuple[LuxtronikEntityAttributeDescription, ...] = ()
    entity_registry_enabled_default: bool | None = (  # pyright: ignore[reportIncompatibleVariableOverride]
        None
    )
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
    factor_by_firmware_series: dict[int, float] | None = None
    """Per-controller-generation override of `factor`, keyed by firmware major.

    For the few registers whose *unit* differs between controller
    generations rather than their presence - see the auxiliary heater energy
    counters, 0.1 kWh on a series-3 controller and 0.01 kWh on a series-2 one
    (#752). A series absent from the mapping falls back to `factor`.

    This cannot live in the datatype the register is registered with: the
    library overrides are applied once per process, while one process can
    serve two config entries whose heat pumps are different generations.
    """


class LuxtronikIndexSensorDescription(  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    LuxtronikSensorDescription,
    SensorEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik index sensor entities."""

    luxtronik_key_timestamp: LuxParameter | LuxCalculation = LuxParameter.UNSET


class LuxtronikCopSensorDescription(  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    LuxtronikSensorDescription,
    SensorEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik instantaneous COP sensor entities.

    Unlike a plain sensor, the displayed value is a ratio of two other
    coordinator values (numerator_key / denominator_key), only considered
    valid while the heat pump's live operating status equals
    required_status. luxtronik_key is intentionally left at its UNSET
    default, same convention as LuxtronikTimerScheduleTextDescription.
    """

    numerator_key: LuxCalculation = LuxCalculation.UNSET
    denominator_key: LuxCalculation = LuxCalculation.UNSET
    required_status: LuxOperationMode | None = None


class LuxtronikSumSensorDescription(  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    LuxtronikSensorDescription,
    SensorEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik sensor entities that total several registers.

    The displayed value is the sum of the coordinator values behind
    summand_keys. It exists for quantities the controller splits across
    more than one register over its firmware history, where no single
    register holds the whole total on every unit - see the additional heat
    generator energy counters (1059 / 1140, #733).

    Summands absent from this controller contribute nothing rather than
    invalidating the total, so a unit exposing only one of them still gets
    a correct figure. luxtronik_key is intentionally left at its UNSET
    default, same convention as LuxtronikCopSensorDescription.
    """

    summand_keys: tuple[LuxParameter | LuxCalculation, ...] = ()


class LuxtronikNumberDescription(
    LuxtronikEntityDescription,
    NumberEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik number sensor entities."""

    platform = Platform.NUMBER
    factor: float | None = None
    native_precision: int | None = None
    mode: NumberMode = NumberMode.AUTO
    min_value_luxtronik_key: LuxParameter | None = None
    max_value_luxtronik_key: LuxParameter | None = None
    entity_active_formula: str | None = None


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
    """Class describing Luxtronik select entities."""

    platform = Platform.SELECT
    #: Maps the HA-facing option name to the raw value the device expects,
    #: for parameters whose raw values are not usable as HA options (e.g.
    #: the timer program's "5+2"). When unset, options are derived from the
    #: raw values as before.
    raw_option_map: dict[str, str] | None = None


class LuxtronikTimerScheduleTextDescription(
    LuxtronikEntityDescription,
    TextEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing a single timer-program schedule block as an editable text entity.

    Reads/writes multiple raw Luxtronik parameters (one pair per row) as a
    delimited "start-end/start-end/..." string, so ``luxtronik_key`` is left
    unused (stays at its ``LuxParameter.UNSET`` default).
    """

    platform = Platform.TEXT
    mode_selector_name: str = ""
    active_mode: str = ""
    row_names: tuple[tuple[str, str], ...] = ()

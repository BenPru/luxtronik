"""Support for ait Luxtronik thermostat devices."""

# region Imports
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import math
from time import monotonic
from typing import Any

from homeassistant.components.climate import (
    ENTITY_ID_FORMAT,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    # PRECISION_HALVES,
    PRECISION_TENTHS,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData

from . import LuxtronikConfigEntry
from .base import LuxtronikEntity
from .common import get_sensor_data, key_exists, state_as_number_or_none
from .const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
    CONF_RBE_CALCULATED_ROOM_TARGET,
    LOGGER,
    LUX_STATE_ICON_MAP,
    LUX_STATE_ICON_MAP_COOL,
    DeviceKey,
    LuxCalculation,
    LuxMode,
    LuxOperationMode,
    LuxParameter,
    LuxRoomThermostatType,
    SensorKey,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikClimateDescription

# endregion Imports

PARALLEL_UPDATES = 1

# region Const
MIN_TEMPERATURE = 8
MAX_TEMPERATURE = 28

# Plain RBE room target (#684): P0001 is written in 0.5 steps within +/-5 K.
RBE_CORRECTION_LIMIT = 5.0
RBE_CORRECTION_STEP = 0.5
# A refused write is retried only when its inputs change or after this long.
RBE_WRITE_RETRY_BACKOFF = 600.0

HVAC_ACTION_MAPPING_HEAT: dict[str, str] = {
    LuxOperationMode.heating: HVACAction.HEATING.value,
    LuxOperationMode.domestic_water: HVACAction.IDLE.value,
    LuxOperationMode.swimming_pool_solar: STATE_UNKNOWN,
    LuxOperationMode.evu: HVACAction.IDLE.value,
    LuxOperationMode.defrost: HVACAction.IDLE.value,
    LuxOperationMode.no_request: HVACAction.IDLE.value,
    LuxOperationMode.heating_external_source: HVACAction.HEATING.value,
    LuxOperationMode.cooling: HVACAction.IDLE.value,
}

HVAC_ACTION_MAPPING_COOL: dict[str, str] = {
    LuxOperationMode.heating: HVACAction.IDLE.value,
    LuxOperationMode.domestic_water: HVACAction.IDLE.value,
    LuxOperationMode.swimming_pool_solar: STATE_UNKNOWN,
    LuxOperationMode.evu: HVACAction.IDLE.value,
    LuxOperationMode.defrost: HVACAction.IDLE.value,
    LuxOperationMode.no_request: HVACAction.IDLE.value,
    LuxOperationMode.heating_external_source: HVACAction.IDLE.value,
    LuxOperationMode.cooling: HVACAction.COOLING.value,
}

HVAC_MODE_MAPPING_HEAT: dict[str, str] = {
    LuxMode.off: HVACMode.OFF.value,
    LuxMode.automatic: HVACMode.HEAT.value,
    LuxMode.second_heatsource: HVACMode.HEAT.value,
    LuxMode.party: HVACMode.HEAT.value,
    LuxMode.holidays: HVACMode.HEAT.value,
}

HVAC_MODE_MAPPING_COOL: dict[str, str] = {
    LuxMode.off: HVACMode.OFF.value,
    LuxMode.automatic: HVACMode.COOL.value,
}

HVAC_PRESET_MAPPING: dict[str, str] = {
    LuxMode.off: PRESET_NONE,
    LuxMode.automatic: PRESET_NONE,
    LuxMode.party: PRESET_COMFORT,
    LuxMode.second_heatsource: PRESET_BOOST,
    LuxMode.holidays: PRESET_AWAY,
}

THERMOSTATS_SMART: list[LuxtronikClimateDescription] = [
    LuxtronikClimateDescription(
        key=SensorKey.HEATING,
        hvac_modes=[HVACMode.HEAT, HVACMode.OFF],
        hvac_mode_mapping=HVAC_MODE_MAPPING_HEAT,
        hvac_action_mapping=HVAC_ACTION_MAPPING_HEAT,
        preset_modes=[PRESET_NONE, PRESET_AWAY, PRESET_BOOST],
        supported_features=ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TARGET_TEMPERATURE,
        luxtronik_key=LuxParameter.P0003_MODE_HEATING,
        luxtronik_key_target_temperature=LuxParameter.P1148_HEATING_TARGET_TEMP_ROOM_THERMOSTAT,
        luxtronik_key_current_action=LuxCalculation.C0080_STATUS,
        luxtronik_action_active=LuxOperationMode.heating,
        icon_by_state=LUX_STATE_ICON_MAP,
        temperature_unit=UnitOfTemperature.CELSIUS,
        translation_key_name="heating_controller",
        device_key=DeviceKey.heating,
    ),
    LuxtronikClimateDescription(
        key=SensorKey.COOLING,
        hvac_modes=[HVACMode.COOL, HVACMode.OFF],
        hvac_mode_mapping=HVAC_MODE_MAPPING_COOL,
        hvac_action_mapping=HVAC_ACTION_MAPPING_COOL,
        preset_modes=[PRESET_NONE],
        supported_features=ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TARGET_TEMPERATURE,
        luxtronik_key=LuxParameter.P0108_MODE_COOLING,
        luxtronik_key_target_temperature=LuxParameter.P1148_HEATING_TARGET_TEMP_ROOM_THERMOSTAT,
        luxtronik_key_current_action=LuxCalculation.C0080_STATUS,
        luxtronik_action_active=LuxOperationMode.cooling,
        icon_by_state=LUX_STATE_ICON_MAP_COOL,
        temperature_unit=UnitOfTemperature.CELSIUS,
        translation_key_name="cooling_controller",
        device_key=DeviceKey.cooling,
    ),
]

THERMOSTATS_OTHER: list[LuxtronikClimateDescription] = [
    LuxtronikClimateDescription(
        key=SensorKey.HEATING,
        hvac_modes=[HVACMode.HEAT, HVACMode.OFF],
        hvac_mode_mapping=HVAC_MODE_MAPPING_HEAT,
        hvac_action_mapping=HVAC_ACTION_MAPPING_HEAT,
        preset_modes=[PRESET_NONE, PRESET_AWAY, PRESET_BOOST],
        supported_features=ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TARGET_TEMPERATURE,
        luxtronik_key=LuxParameter.P0003_MODE_HEATING,
        luxtronik_key_target_temperature=LuxParameter.P0001_HEATING_TARGET_CORRECTION,
        luxtronik_key_current_action=LuxCalculation.C0080_STATUS,
        luxtronik_action_active=LuxOperationMode.heating,
        luxtronik_key_correction_factor=LuxParameter.P0980_HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR,
        luxtronik_key_correction_target=LuxParameter.P0001_HEATING_TARGET_CORRECTION,
        icon_by_state=LUX_STATE_ICON_MAP,
        temperature_unit=UnitOfTemperature.CELSIUS,
        min_temp=-5.0,
        max_temp=5.0,
        translation_key_name="heating_controller",
        device_key=DeviceKey.heating,
    ),
    LuxtronikClimateDescription(
        key=SensorKey.COOLING,
        hvac_modes=[HVACMode.COOL, HVACMode.OFF],
        hvac_mode_mapping=HVAC_MODE_MAPPING_COOL,
        hvac_action_mapping=HVAC_ACTION_MAPPING_COOL,
        preset_modes=[PRESET_NONE],
        supported_features=ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TARGET_TEMPERATURE,
        luxtronik_key=LuxParameter.P0108_MODE_COOLING,
        luxtronik_key_target_temperature=LuxParameter.P0110_COOLING_OUTDOOR_TEMP_THRESHOLD,
        luxtronik_key_current_action=LuxCalculation.C0080_STATUS,
        luxtronik_action_active=LuxOperationMode.cooling,
        icon_by_state=LUX_STATE_ICON_MAP_COOL,
        temperature_unit=UnitOfTemperature.CELSIUS,
        translation_key_name="cooling_controller",
        device_key=DeviceKey.cooling,
    ),
]

THERMOSTAT_RBE_CALCULATED_HEATING = replace(
    THERMOSTATS_OTHER[0],
    luxtronik_key_target_temperature=LuxParameter.UNSET,
    luxtronik_key_room_target=LuxCalculation.C0228_ROOM_THERMOSTAT_TEMPERATURE_TARGET,
    min_temp=None,
    max_temp=None,
)

# Plain RBE with the room target option on: heating gets a room temperature
# target, cooling is unchanged.
THERMOSTATS_RBE_CALCULATED: list[LuxtronikClimateDescription] = [
    THERMOSTAT_RBE_CALCULATED_HEATING,
    THERMOSTATS_OTHER[1],
]

THERMOSTATS: list[LuxtronikClimateDescription] = THERMOSTATS_SMART + THERMOSTATS_OTHER
# endregion Const


def round_correction(value: float) -> float:
    """Round to the 0.5 K step, half away from zero (`round` rounds half to even)."""
    steps = math.floor(abs(value) / RBE_CORRECTION_STEP + 0.5)
    return math.copysign(steps * RBE_CORRECTION_STEP, value) + 0.0  # no -0.0


def rbe_correction_for_target(
    target: float, room_target: float, factor: float
) -> float:
    """P0001 that makes the controller regulate toward `target` instead of C0228."""
    raw = (target - room_target) * factor
    return round_correction(max(-RBE_CORRECTION_LIMIT, min(RBE_CORRECTION_LIMIT, raw)))


def rbe_target_for_correction(
    correction: float, room_target: float, factor: float
) -> float:
    """Room target that a given P0001 corresponds to."""
    return room_target + correction / factor


def rbe_target_bounds(room_target: float, factor: float) -> tuple[float, float]:
    """Targets reachable with P0001 in +/-5 K; the range moves with C0228."""
    span = RBE_CORRECTION_LIMIT / factor
    return room_target - span, room_target + span


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuxtronikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Luxtronik climate entities dynamically through Luxtronik discovery."""

    coordinator = entry.runtime_data

    # Determine room thermostat type from coordinator (enum or raw int)
    rt = getattr(coordinator, "room_thermostat_type", None)
    is_smart_thermostat = False
    if isinstance(rt, LuxRoomThermostatType):
        is_smart_thermostat = rt in (
            LuxRoomThermostatType.smart,
            LuxRoomThermostatType.rbe_plus,
        )

    LOGGER.info(
        "Detected room thermostat type: %s (smart=%s)",
        rt,
        is_smart_thermostat,
    )

    rbe_calculated = rt is LuxRoomThermostatType.rbe and bool(
        entry.options.get(CONF_RBE_CALCULATED_ROOM_TARGET, False)
    )
    if is_smart_thermostat:
        thermostats = THERMOSTATS_SMART
    elif rbe_calculated:
        thermostats = THERMOSTATS_RBE_CALCULATED
    else:
        thermostats = THERMOSTATS_OTHER

    unavailable_keys = [
        i.luxtronik_key
        for i in thermostats
        if not key_exists(coordinator.data, i.luxtronik_key)
    ]
    if unavailable_keys:
        # Not all models/firmware versions support every parameter;
        # missing keys are expected and not an error.
        LOGGER.debug("Not present in Luxtronik data, skipping: %s", unavailable_keys)

    async_add_entities(
        [
            (
                LuxtronikRbeCalculatedThermostat
                if description.luxtronik_key_room_target != LuxCalculation.UNSET
                else LuxtronikThermostat
            )(hass, entry, coordinator, description)
            for description in thermostats
            if (
                coordinator.entity_active(description)
                and key_exists(coordinator.data, description.luxtronik_key)
            )
        ]
    )


@dataclass
class LuxtronikClimateExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    _attr_target_temperature: float | None = None
    _attr_hvac_mode: HVACMode | str | None = None
    _attr_preset_mode: str | None = None
    last_hvac_mode_before_preset: str | None = None
    # Calculated RBE room target (#684): the P0001 last written or adopted.
    _last_written_correction: float | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the text data."""
        return asdict(self)


class LuxtronikThermostat(LuxtronikEntity[LuxtronikClimateDescription], ClimateEntity):  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    """The thermostat class for Luxtronik thermostats."""

    # region Attributes

    _last_hvac_mode_before_preset: str | None = None

    _attr_precision = PRECISION_TENTHS
    _attr_target_temperature = 21.0
    _attr_target_temperature_high = 28.0
    _attr_target_temperature_low = 18.0
    _attr_target_temperature_step = 0.5

    _attr_hvac_mode: HVACMode | str | None = None
    _attr_preset_mode: str | None = None

    _attr_current_lux_operation = LuxOperationMode.no_request
    # endregion Attributes

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikClimateDescription,
    ) -> None:
        """Init Luxtronik Switch."""
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=description.device_key,
        )

        # ✅ IMPORTANT: start from base-processed description (has translation_key set)
        description = self.entity_description

        domain = description.key.value  # pyright: ignore[reportAttributeAccessIssue]
        configured_indoor_temp_sensor = entry.options.get(
            CONF_HA_SENSOR_INDOOR_TEMPERATURE,
            entry.data.get(CONF_HA_SENSOR_INDOOR_TEMPERATURE),
        )

        if configured_indoor_temp_sensor is not None:
            description = replace(
                description,
                luxtronik_key_current_temperature=configured_indoor_temp_sensor,
            )
            LOGGER.debug(
                "[INIT,%s] Using configured indoor temp sensor: %s",
                domain,
                description.luxtronik_key_current_temperature,
            )
        elif description.luxtronik_key_current_temperature == LuxCalculation.UNSET:
            if (
                getattr(coordinator, "room_thermostat_type", None)
                is LuxRoomThermostatType.none
            ):
                # Without a room thermostat C0227 reads a permanent 0.0 (24
                # of the 29 units in the diagnostics corpus). Leaving the key
                # UNSET keeps current_temperature at None, which the climate
                # card renders as "no reading" rather than "0 °C".
                LOGGER.debug(
                    "[INIT,%s] No room thermostat fitted, current temperature not reported",
                    domain,
                )
            else:
                description = replace(
                    description,
                    luxtronik_key_current_temperature=LuxCalculation.C0227_ROOM_THERMOSTAT_TEMPERATURE,
                )
                LOGGER.debug(
                    "[INIT,%s] Using default indoor temp sensor: %s",
                    domain,
                    description.luxtronik_key_current_temperature,
                )

        # ✅ Set the final description ONCE
        self.entity_description = description
        # Base built these from the description before the swap above.
        self._set_luxtronik_key_attributes()

        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key.value}")  # pyright: ignore[reportAttributeAccessIssue]
        self._attr_unique_id = self.entity_id

        self._attr_temperature_unit = description.temperature_unit
        self._attr_hvac_modes = description.hvac_modes
        self._attr_preset_modes = description.preset_modes
        min_temp = getattr(description, "min_temp", None)
        if min_temp is not None:
            self._attr_min_temp = min_temp
        max_temp = getattr(description, "max_temp", None)
        if max_temp is not None:
            self._attr_max_temp = max_temp
        self._enable_turn_on_off_backwards_compatibility = False
        self._attr_supported_features = description.supported_features

        self._debouncer_set_temp = Debouncer(
            hass,
            LOGGER,
            cooldown=0.5,
            immediate=False,
            function=self._async_write_temperature,
        )
        self.async_on_remove(self._debouncer_set_temp.async_shutdown)

        self._pending_temperature: float | None = None

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data if data is None else data
        if data is None:
            return

        mode = get_sensor_data(data, self.entity_description.luxtronik_key.value)
        if mode is None:
            self._attr_hvac_mode = None
            self._attr_preset_mode = None
        else:
            hvac_mode = self.entity_description.hvac_mode_mapping.get(mode)
            if hvac_mode is None:
                LOGGER.warning("Unknown hvac mode %s, unable to map", mode)
            self._attr_hvac_mode = hvac_mode

            preset_mode = HVAC_PRESET_MAPPING.get(mode)
            if preset_mode is None:
                LOGGER.warning("Unknown preset mode %s, unable to map", mode)
            self._attr_preset_mode = preset_mode
        self._attr_current_lux_operation = lux_action = get_sensor_data(
            data, self.entity_description.luxtronik_key_current_action.value
        )
        self._attr_hvac_action = (  # pyright: ignore[reportAttributeAccessIssue]
            None
            if lux_action is None
            else self.entity_description.hvac_action_mapping[lux_action]
        )
        if self._attr_preset_mode == PRESET_NONE:
            self._last_hvac_mode_before_preset = None

        key = self.entity_description.luxtronik_key_current_temperature
        if key is None or key == "" or key == LuxCalculation.UNSET:
            self._attr_current_temperature = None
        elif key.startswith("sensor."):
            temp = self.hass.states.get(key)
            self._attr_current_temperature = (
                state_as_number_or_none(temp, 0.0) if temp is not None else None
            )
        else:
            self._attr_current_temperature = get_sensor_data(data, key)

        key_tar = self.entity_description.luxtronik_key_target_temperature

        if key_tar != LuxParameter.UNSET:
            self._attr_target_temperature = get_sensor_data(data, key_tar)

        super()._handle_coordinator_update()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature with debounce."""
        self._pending_temperature = kwargs[ATTR_TEMPERATURE]
        await self._debouncer_set_temp.async_call()

    async def _async_write_temperature(self):
        """Write the pending temperature to the device."""
        if self._pending_temperature is None:
            return

        key_tar = self.entity_description.luxtronik_key_target_temperature
        LOGGER.debug(
            f"Debounced temperature write: {key_tar} = {self._pending_temperature}"
        )

        if key_tar != LuxCalculation.C0228_ROOM_THERMOSTAT_TEMPERATURE_TARGET:
            try:
                data: (
                    LuxtronikCoordinatorData | None
                ) = await self.coordinator.async_write(
                    key_tar.split(".")[1], self._pending_temperature
                )
            except HomeAssistantError as err:
                # Debounced write, so no caller is left to surface this to;
                # re-sync the entity to the device's actual value immediately
                # instead of leaving the frontend showing the rejected value
                # until the next poll (I3b).
                LOGGER.error(
                    "Debounced temperature write of %s failed, reverting to device value: %s",
                    key_tar,
                    err,
                )
                self._handle_coordinator_update(self.coordinator.data)
                return
            self._handle_coordinator_update(data)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(
            HVACMode[
                self.entity_description.hvac_mode_mapping[LuxMode.automatic].upper()
            ]
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._attr_hvac_mode = hvac_mode  # pyright: ignore[reportIncompatibleVariableOverride]
        lux_mode = next(
            k
            for k, v in self.entity_description.hvac_mode_mapping.items()
            if v == hvac_mode.value
        )
        await self._async_set_lux_mode(lux_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        self._attr_preset_mode = preset_mode
        if preset_mode in [PRESET_COMFORT]:
            lux_mode = LuxMode.automatic
        elif preset_mode != PRESET_NONE:
            lux_mode = next(
                k for k, v in HVAC_PRESET_MAPPING.items() if v == preset_mode
            )
            if self._last_hvac_mode_before_preset is None:
                # The Luxtronik mode, not the HA hvac mode: it is written back
                # to P0003 when the preset ends, which cannot take "heat".
                self._last_hvac_mode_before_preset = get_sensor_data(
                    self.coordinator.data, self.entity_description.luxtronik_key
                )
        elif self._last_hvac_mode_before_preset is not None:
            lux_mode = self._last_hvac_mode_before_preset
            self._last_hvac_mode_before_preset = None
        else:
            lux_mode = LuxMode.off
        await self._async_set_lux_mode(lux_mode)

    async def _async_set_lux_mode(self, lux_mode: str) -> None:
        lux_key = self.entity_description.luxtronik_key.value
        data = await self.coordinator.async_write(lux_key.split(".")[1], lux_mode)
        self._handle_coordinator_update(data)

    @property
    def extra_restore_state_data(self) -> LuxtronikClimateExtraStoredData:
        """Return luxtronik climate specific state data to be restored."""
        return LuxtronikClimateExtraStoredData(
            self._attr_target_temperature,
            self._attr_hvac_mode,
            self._attr_preset_mode,
            self._last_hvac_mode_before_preset,
        )


def _same(a: float, b: float) -> bool:
    return abs(a - b) < 0.01


class LuxtronikRbeCalculatedThermostat(LuxtronikThermostat):
    """Heating thermostat for a plain RBE with a room target set in HA (#684).

    The controller already shifts the heating curve by f * (C0228 - room).
    Writing P0001 = f * (T - C0228) turns that into f * (T - room), so the heat
    pump regulates as if the RBE dial were set to T. P0001 only changes when T,
    C0228 or f change - there is no control loop on the room temperature. See
    docs/superpowers/specs/2026-09-27-rbe-calculated-room-target-design.md.
    """

    _last_written_correction: float | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikClimateDescription,
    ) -> None:
        super().__init__(hass, entry, coordinator, description)
        self._bounds: tuple[float, float] | None = None
        self._write_in_flight = False
        self._write_inputs: tuple[float, float, float] | None = None
        self._write_failed_at: float | None = None
        self._write_failed_inputs: tuple[float, float, float] | None = None
        # Guard (D8) active: T is hidden, not discarded, so a one-poll gap
        # neither drifts T nor lets a dial change it missed win over HA (D4).
        self._room_target_unavailable = False

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        data = self.coordinator.data if data is None else data
        if data is None:
            return
        self._sync_room_target(data)
        super()._handle_coordinator_update(data)

    def _sync_room_target(self, data: LuxtronikCoordinatorData) -> None:
        descr = self.entity_description
        correction = get_sensor_data(data, descr.luxtronik_key_correction_target)
        room_target = get_sensor_data(data, descr.luxtronik_key_room_target)
        factor_pct = get_sensor_data(data, descr.luxtronik_key_correction_factor)
        # f == 0: no room influence, so no room target can work (D8).
        # C0228 == 0.0 is the no-RBE sentinel.
        if correction is None or not room_target or not factor_pct:
            self._set_room_target_unavailable(correction, room_target, factor_pct)
            return
        self._room_target_unavailable = False
        self._attr_supported_features = descr.supported_features
        factor = factor_pct / 100

        low, high = rbe_target_bounds(room_target, factor)
        self._bounds = (low, high)
        self._attr_min_temp = (
            math.floor(low / RBE_CORRECTION_STEP) * RBE_CORRECTION_STEP
        )
        self._attr_max_temp = (
            math.ceil(high / RBE_CORRECTION_STEP) * RBE_CORRECTION_STEP
        )
        attrs = self._attr_extra_state_attributes
        attrs["room_target_rbe"] = room_target
        attrs["correction"] = correction
        attrs["effective_room_target"] = round(
            rbe_target_for_correction(correction, room_target, factor), 2
        )

        if self._write_in_flight:
            # The refresh triggered by our own write; the write task finishes it.
            return

        target = self._attr_target_temperature
        if (
            target is None
            or self._last_written_correction is None
            or not _same(correction, self._last_written_correction)
        ):
            # First run (D6) or P0001 changed elsewhere (D5): adopt, write nothing.
            self._attr_target_temperature = self._clamp(
                rbe_target_for_correction(correction, room_target, factor)
            )
            self._last_written_correction = correction
            return

        target = self._clamp(target)
        self._attr_target_temperature = target
        desired = rbe_correction_for_target(target, room_target, factor)
        # Against the rounded P0001: an off-grid value set elsewhere (0.3) was
        # adopted above and must not be "corrected" to 0.5 on the next poll.
        if _same(desired, round_correction(correction)):
            return
        inputs = (target, room_target, factor)
        if self._write_backing_off(inputs):
            return
        self._write_in_flight = True
        self._write_inputs = inputs
        self.hass.async_create_task(
            self._async_write_correction(desired), eager_start=False
        )

    def _set_room_target_unavailable(
        self, correction: Any, room_target: Any, factor_pct: Any
    ) -> None:
        self._attr_supported_features = (
            self.entity_description.supported_features
            & ~ClimateEntityFeature.TARGET_TEMPERATURE
        )
        if not self._room_target_unavailable:
            self._room_target_unavailable = True
            LOGGER.info(
                "Room target unavailable for %s (P0001=%s, C0228=%s, P0980=%s); "
                "not adjusting the heating curve correction",
                self.entity_id,
                correction,
                room_target,
                factor_pct,
            )

    @property
    def target_temperature(self) -> float | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """The room target, hidden while it cannot be applied."""
        if self._room_target_unavailable:
            return None
        return self._attr_target_temperature

    def _clamp(self, target: float) -> float:
        if self._bounds is None:
            return target
        low, high = self._bounds
        return min(max(target, low), high)

    def _write_backing_off(self, inputs: tuple[float, float, float]) -> bool:
        if self._write_failed_at is None or inputs != self._write_failed_inputs:
            return False
        return monotonic() - self._write_failed_at < RBE_WRITE_RETRY_BACKOFF

    async def _async_write_correction(self, correction: float) -> None:
        key = self.entity_description.luxtronik_key_correction_target
        try:
            data = await self.coordinator.async_write(key.split(".")[1], correction)
        except HomeAssistantError as err:
            self._write_failed_at = monotonic()
            self._write_failed_inputs = self._write_inputs
            LOGGER.warning(
                "Writing heating curve correction %s for room target %s failed; "
                "retrying when the target changes or in %d minutes: %s",
                correction,
                self._attr_target_temperature,
                RBE_WRITE_RETRY_BACKOFF // 60,
                err,
            )
            return
        finally:
            self._write_in_flight = False
        # async_write has confirmed the read-back.
        self._last_written_correction = correction
        self._write_failed_at = None
        self._handle_coordinator_update(data)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the room target; the P0001 write is debounced."""
        self._attr_target_temperature = self._clamp(float(kwargs[ATTR_TEMPERATURE]))
        self.async_write_ha_state()
        await self._debouncer_set_temp.async_call()

    async def _async_write_temperature(self) -> None:
        """Debounced: let the sync step decide whether P0001 must change."""
        self._handle_coordinator_update(self.coordinator.data)

    @property
    def extra_restore_state_data(self) -> LuxtronikClimateExtraStoredData:
        return LuxtronikClimateExtraStoredData(
            self._attr_target_temperature,
            self._attr_hvac_mode,
            self._attr_preset_mode,
            self._last_hvac_mode_before_preset,
            self._last_written_correction,
        )

"""Support for ait Luxtronik thermostat devices."""

# region Imports
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
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
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData

from . import LuxtronikConfigEntry
from .base import LuxtronikEntity
from .common import get_sensor_data, key_exists, state_as_number_or_none
from .const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
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
        # visibility=LuxVisibility.V0023_FLOW_IN_TEMPERATURE,
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
        # visibility=LuxVisibility.V0005_COOLING,
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
        # visibility=LuxVisibility.V0023_FLOW_IN_TEMPERATURE,
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
        # visibility=LuxVisibility.V0005_COOLING,
        device_key=DeviceKey.cooling,
    ),
]

THERMOSTATS: list[LuxtronikClimateDescription] = THERMOSTATS_SMART + THERMOSTATS_OTHER
# endregion Const


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

    THERMOSTATS = THERMOSTATS_SMART if is_smart_thermostat else THERMOSTATS_OTHER

    unavailable_keys = [
        i.luxtronik_key
        for i in THERMOSTATS
        if not key_exists(coordinator.data, i.luxtronik_key)
    ]
    if unavailable_keys:
        # Not all models/firmware versions support every parameter;
        # missing keys are expected and not an error.
        LOGGER.debug("Not present in Luxtronik data, skipping: %s", unavailable_keys)

    async_add_entities(
        [
            LuxtronikThermostat(hass, entry, coordinator, description)
            for description in THERMOSTATS
            if (
                coordinator.entity_active(description)
                and key_exists(coordinator.data, description.luxtronik_key)
            )
        ],
        True,
    )


@dataclass
class LuxtronikClimateExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    _attr_target_temperature: float | None = None
    _attr_hvac_mode: HVACMode | str | None = None
    _attr_preset_mode: str | None = None
    # _attr_is_aux_heat: bool | None = None
    last_hvac_mode_before_preset: str | None = None

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

    # _attr_is_aux_heat: bool | None = None
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
        self._attr_hvac_mode = (
            None if mode is None else self.entity_description.hvac_mode_mapping[mode]
        )
        self._attr_preset_mode = None if mode is None else HVAC_PRESET_MAPPING[mode]
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
        if key is None or key == "":
            self._attr_current_temperature = None
        elif key.startswith("sensor."):
            temp = self.hass.states.get(key)
            self._attr_current_temperature = (
                state_as_number_or_none(temp, 0.0) if temp is not None else None
            )
        elif key != LuxCalculation.UNSET:
            self._attr_current_temperature = get_sensor_data(data, key)

        key_tar = self.entity_description.luxtronik_key_target_temperature

        if key_tar != LuxParameter.UNSET:
            self._attr_target_temperature = get_sensor_data(data, key_tar)

        self.async_write_ha_state()
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
            data: LuxtronikCoordinatorData | None = await self.coordinator.async_write(
                key_tar.split(".")[1], self._pending_temperature
            )
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
                self._last_hvac_mode_before_preset = self._attr_hvac_mode
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

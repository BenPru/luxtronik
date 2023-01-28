"""Support for ait Luxtronik thermostat devices."""
# region Imports
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ENTITY_ID_FORMAT,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    STATE_UNKNOWN,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import LuxtronikEntity
from .common import get_sensor_data
from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    DeviceKey,
    LuxCalculation,
    LuxMode,
    LuxOperationMode,
    LuxParameter,
    LuxVisibility,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikClimateDescription

# endregion Imports

# region Const
MIN_TEMPERATURE = 8
MAX_TEMPERATURE = 28

HVAC_ACTION_MAPPING: dict[str, str] = {
    LuxOperationMode.heating.value: HVACAction.HEATING.value,
    LuxOperationMode.domestic_water.value: HVACAction.HEATING.value,
    LuxOperationMode.swimming_pool_solar.value: STATE_UNKNOWN,
    LuxOperationMode.evu.value: HVACAction.IDLE.value,
    LuxOperationMode.defrost.value: HVACAction.IDLE.value,
    LuxOperationMode.no_request.value: HVACAction.IDLE.value,
    LuxOperationMode.heating_external_source.value: HVACAction.HEATING.value,
    LuxOperationMode.cooling.value: HVACAction.COOLING.value,
}

HVAC_MODE_MAPPING: dict[str, str] = {
    LuxMode.off.value: HVACMode.OFF.value,
    LuxMode.automatic.value: HVACMode.HEAT.value,
    LuxMode.second_heatsource.value: HVACMode.HEAT.value,
    LuxMode.party.value: HVACMode.HEAT.value,
    LuxMode.holidays.value: HVACMode.HEAT.value,
}

HVAC_PRESET_MAPPING: dict[str, str] = {
    LuxMode.off.value: PRESET_NONE,
    LuxMode.automatic.value: PRESET_NONE,
    LuxMode.party.value: PRESET_BOOST,
    LuxMode.holidays.value: PRESET_AWAY,
}

THERMOSTATS: list[LuxtronikClimateDescription] = [
    LuxtronikClimateDescription(
        key="heating",
        hvac_modes=[HVACMode.HEAT, HVACMode.OFF],
        preset_modes=[PRESET_NONE, PRESET_AWAY, PRESET_BOOST],
        supported_features=ClimateEntityFeature.AUX_HEAT
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE,
        luxtronik_key=LuxParameter.P0003_MODE_HEATING,
        # luxtronik_key_current_temperature=LuxCalculation.C0227_ROOM_THERMOSTAT_TEMPERATURE,
        # luxtronik_key_target_temperature=LuxCalculation.C0228_ROOM_THERMOSTAT_TEMPERATURE_TARGET,
        # luxtronik_key_has_target_temperature=LuxParameter
        luxtronik_key_current_action=LuxCalculation.C0080_STATUS,
        luxtronik_action_heating=LuxOperationMode.heating.value,
        # luxtronik_key_target_temperature_high=LuxParameter,
        # luxtronik_key_target_temperature_low=LuxParameter,
        luxtronik_key_correction_factor=LuxParameter.P0980_HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR,
        luxtronik_key_correction_target=LuxParameter.P0001_HEATING_TARGET_CORRECTION,
        icon="mdi:radiator",
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        visibility=LuxVisibility.V0023_FLOW_IN_TEMPERATURE,
    )
]
# endregion Const


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Luxtronik thermostat from ConfigEntry."""
    data: dict = hass.data[DOMAIN][entry.entry_id]
    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        LuxtronikThermostat(hass, entry, coordinator, description)
        for description in THERMOSTATS
        if coordinator.entity_active(description)
    )


class LuxtronikThermostat(LuxtronikEntity, ClimateEntity):
    """The thermostat class for Luxtronik thermostats."""

    entity_description: LuxtronikClimateDescription

    _last_hvac_mode_before_preset: str | None = None

    _attr_precision = PRECISION_HALVES
    _attr_target_temperature = 21.0
    _attr_target_temperature_high = 28.0
    _attr_target_temperature_low = 18.0
    _attr_target_temperature_step = 0.5

    _attr_is_aux_heat: bool | None = None
    _attr_hvac_mode: HVACMode | str | None = None
    _attr_preset_mode: str | None = None

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
            device_info_ident=DeviceKey.heating,
            platform=Platform.CLIMATE,
        )
        if description.luxtronik_key_current_temperature is None:
            description.luxtronik_key_current_temperature = entry.data.get(
                CONF_HA_SENSOR_INDOOR_TEMPERATURE
            )
        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id
        self._attr_temperature_unit = description.unit_of_measurement
        self._attr_hvac_modes = description.hvac_modes
        self._attr_preset_modes = description.preset_modes
        self._attr_supported_features = description.supported_features

        self._sensor_data = get_sensor_data(
            coordinator.data, description.luxtronik_key.value
        )

    async def _data_update(self, event):
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data if data is None else data
        if data is None:
            return
        mode = get_sensor_data(data, self.entity_description.luxtronik_key.value)
        self._attr_hvac_mode = None if mode is None else HVAC_MODE_MAPPING[mode]
        self._attr_preset_mode = None if mode is None else HVAC_PRESET_MAPPING[mode]
        lux_action = get_sensor_data(
            data, self.entity_description.luxtronik_key_current_action.value
        )
        self._attr_hvac_action = (
            None if lux_action is None else HVAC_ACTION_MAPPING[lux_action]
        )
        self._attr_is_aux_heat = (
            None if mode is None else mode == LuxMode.second_heatsource.value
        )
        if self._attr_preset_mode == PRESET_NONE or self._attr_is_aux_heat:
            self._last_hvac_mode_before_preset = None
        if isinstance(self.entity_description.luxtronik_key_current_temperature, str):
            temp = self.hass.states.get(
                self.entity_description.luxtronik_key_current_temperature
            )
            self._attr_current_temperature = None if temp is None else float(temp.state)
        elif (
            self.entity_description.luxtronik_key_current_temperature.value is not None
        ):
            self._attr_current_temperature = get_sensor_data(
                data, self.entity_description.luxtronik_key_current_temperature.value
            )
        if self.entity_description.luxtronik_key_target_temperature.value is not None:
            self._attr_target_temperature = get_sensor_data(
                data, self.entity_description.luxtronik_key_target_temperature.value
            )
        correction_factor = get_sensor_data(
            data, self.entity_description.luxtronik_key_correction_factor.value
        )
        if (
            self._attr_target_temperature is not None
            and self._attr_current_temperature is not None
            and correction_factor is not None
        ):
            delta_temp = self._attr_target_temperature - self._attr_current_temperature
            correction = delta_temp * correction_factor
            key_correction_target = (
                self.entity_description.luxtronik_key_correction_target.value
            )
            correction_current = get_sensor_data(data, key_correction_target)
            if correction_current is None or correction_current != correction:
                self.coordinator.async_write(
                    key_correction_target.split(".")[1], correction
                )

        super()._handle_coordinator_update()

    async def _async_set_lux_mode(self, lux_mode: str) -> None:
        lux_key = self.entity_description.luxtronik_key.value
        data = await self.coordinator.async_write(lux_key.split(".")[1], lux_mode)
        self._handle_coordinator_update(data)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        # TODO: Check RBE
        self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
        super()._handle_coordinator_update()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        lux_mode = [k for k, v in HVAC_MODE_MAPPING.items() if v == hvac_mode.value][0]
        await self._async_set_lux_mode(lux_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode != PRESET_NONE:
            lux_mode = [k for k, v in HVAC_PRESET_MAPPING.items() if v == preset_mode][
                0
            ]
            if self._last_hvac_mode_before_preset is None:
                self._last_hvac_mode_before_preset = self._attr_hvac_mode
        elif self._last_hvac_mode_before_preset is not None:
            lux_mode = self._last_hvac_mode_before_preset
            self._last_hvac_mode_before_preset = None
        else:
            lux_mode = LuxMode.off.value
        await self._async_set_lux_mode(lux_mode)

    async def async_turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        if self._last_hvac_mode_before_preset is None:
            self._last_hvac_mode_before_preset = self._attr_hvac_mode
        await self._async_set_lux_mode(LuxMode.second_heatsource.value)

    async def async_turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        if (self._last_hvac_mode_before_preset is None) or (
            not self._last_hvac_mode_before_preset in HVAC_PRESET_MAPPING
        ):
            await self._async_set_lux_mode(LuxMode.automatic.value)
        else:
            lux_mode = [
                k
                for k, v in HVAC_PRESET_MAPPING.items()
                if v == self._last_hvac_mode_before_preset
            ][0]
            await self._async_set_lux_mode(lux_mode)

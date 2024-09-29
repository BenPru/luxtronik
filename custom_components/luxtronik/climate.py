"""Support for ait Luxtronik thermostat devices."""
# region Imports
from __future__ import annotations

from dataclasses import asdict, dataclass
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
    PRECISION_HALVES,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .base import LuxtronikEntity
from .common import get_sensor_data, state_as_number_or_none
from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    LUX_STATE_ICON_MAP,
    LUX_STATE_ICON_MAP_COOL,
    DeviceKey,
    LuxCalculation,
    LuxMode,
    LuxOperationMode,
    LuxParameter,
    LuxVisibility,
    SensorKey,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikClimateDescription

# endregion Imports

# region Const
MIN_TEMPERATURE = 8
MAX_TEMPERATURE = 28

HVAC_ACTION_MAPPING_HEAT: dict[str, str] = {
    LuxOperationMode.heating.value: HVACAction.HEATING.value,
    LuxOperationMode.domestic_water.value: HVACAction.IDLE.value,
    LuxOperationMode.swimming_pool_solar.value: STATE_UNKNOWN,
    LuxOperationMode.evu.value: HVACAction.IDLE.value,
    LuxOperationMode.defrost.value: HVACAction.IDLE.value,
    LuxOperationMode.no_request.value: HVACAction.IDLE.value,
    LuxOperationMode.heating_external_source.value: HVACAction.HEATING.value,
    LuxOperationMode.cooling.value: HVACAction.IDLE.value,
}

HVAC_ACTION_MAPPING_COOL: dict[str, str] = {
    LuxOperationMode.heating.value: HVACAction.IDLE.value,
    LuxOperationMode.domestic_water.value: HVACAction.IDLE.value,
    LuxOperationMode.swimming_pool_solar.value: STATE_UNKNOWN,
    LuxOperationMode.evu.value: HVACAction.IDLE.value,
    LuxOperationMode.defrost.value: HVACAction.IDLE.value,
    LuxOperationMode.no_request.value: HVACAction.IDLE.value,
    LuxOperationMode.heating_external_source.value: HVACAction.IDLE.value,
    LuxOperationMode.cooling.value: HVACAction.COOLING.value,
}

HVAC_MODE_MAPPING_HEAT: dict[str, str] = {
    LuxMode.off.value: HVACMode.OFF.value,
    LuxMode.automatic.value: HVACMode.HEAT.value,
    LuxMode.second_heatsource.value: HVACMode.HEAT.value,
    LuxMode.party.value: HVACMode.HEAT.value,
    LuxMode.holidays.value: HVACMode.HEAT.value,
}

HVAC_MODE_MAPPING_COOL: dict[str, str] = {
    LuxMode.off.value: HVACMode.OFF.value,
    LuxMode.automatic.value: HVACMode.COOL.value,
}

HVAC_PRESET_MAPPING: dict[str, str] = {
    LuxMode.off.value: PRESET_NONE,
    LuxMode.automatic.value: PRESET_NONE,
    LuxMode.party.value: PRESET_COMFORT,
    LuxMode.second_heatsource.value: PRESET_BOOST,
    LuxMode.holidays.value: PRESET_AWAY,
}

THERMOSTATS: list[LuxtronikClimateDescription] = [
    LuxtronikClimateDescription(
        key=SensorKey.HEATING,
        hvac_modes=[HVACMode.HEAT, HVACMode.OFF],
        hvac_mode_mapping=HVAC_MODE_MAPPING_HEAT,
        hvac_action_mapping=HVAC_ACTION_MAPPING_HEAT,
        preset_modes=[PRESET_NONE, PRESET_AWAY, PRESET_BOOST],
        supported_features=ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF  # noqa: W503
        | ClimateEntityFeature.TURN_ON  # noqa: W503
        | ClimateEntityFeature.TARGET_TEMPERATURE,  # noqa: W503
        luxtronik_key=LuxParameter.P0003_MODE_HEATING,
        # luxtronik_key_current_temperature=LuxCalculation.C0227_ROOM_THERMOSTAT_TEMPERATURE,
        # luxtronik_key_target_temperature=LuxCalculation.C0228_ROOM_THERMOSTAT_TEMPERATURE_TARGET,
        # luxtronik_key_has_target_temperature=LuxParameter
        luxtronik_key_current_action=LuxCalculation.C0080_STATUS,
        luxtronik_action_active=LuxOperationMode.heating.value,
        # luxtronik_key_target_temperature_high=LuxParameter,
        # luxtronik_key_target_temperature_low=LuxParameter,
        luxtronik_key_correction_factor=LuxParameter.P0980_HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR,
        luxtronik_key_correction_target=LuxParameter.P0001_HEATING_TARGET_CORRECTION,
        icon_by_state=LUX_STATE_ICON_MAP,
        temperature_unit=UnitOfTemperature.CELSIUS,
        visibility=LuxVisibility.V0023_FLOW_IN_TEMPERATURE,
        device_key=DeviceKey.heating,
    ),
    LuxtronikClimateDescription(
        key=SensorKey.COOLING,
        hvac_modes=[HVACMode.COOL, HVACMode.OFF],
        hvac_mode_mapping=HVAC_MODE_MAPPING_COOL,
        hvac_action_mapping=HVAC_ACTION_MAPPING_COOL,
        preset_modes=[PRESET_NONE],
        supported_features=ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON  # noqa: W503
        | ClimateEntityFeature.TARGET_TEMPERATURE,  # noqa: W503
        luxtronik_key=LuxParameter.P0108_MODE_COOLING,
        # luxtronik_key_current_temperature=LuxCalculation.C0227_ROOM_THERMOSTAT_TEMPERATURE,
        luxtronik_key_target_temperature=LuxParameter.P0110_COOLING_OUTDOOR_TEMP_THRESHOLD,
        # luxtronik_key_has_target_temperature=LuxParameter
        luxtronik_key_current_action=LuxCalculation.C0080_STATUS,
        luxtronik_action_active=LuxOperationMode.cooling.value,
        # luxtronik_key_target_temperature_high=LuxParameter,
        # luxtronik_key_target_temperature_low=LuxParameter,
        # luxtronik_key_correction_factor=LuxParameter.P0980_HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR,
        # luxtronik_key_correction_target=LuxParameter.P0001_HEATING_TARGET_CORRECTION,
        icon_by_state=LUX_STATE_ICON_MAP_COOL,
        temperature_unit=UnitOfTemperature.CELSIUS,
        visibility=LuxVisibility.V0005_COOLING,
        device_key=DeviceKey.cooling,
    ),
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
        (
            LuxtronikThermostat(hass, entry, coordinator, description)
            for description in THERMOSTATS
            if coordinator.entity_active(description)
        ),
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


class LuxtronikThermostat(LuxtronikEntity, ClimateEntity, RestoreEntity):
    """The thermostat class for Luxtronik thermostats."""

    # region Attributes
    entity_description: LuxtronikClimateDescription

    _last_hvac_mode_before_preset: str | None = None

    _attr_precision = PRECISION_HALVES
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
        if description.luxtronik_key_current_temperature == LuxCalculation.UNSET:
            description.luxtronik_key_current_temperature = entry.data.get(
                CONF_HA_SENSOR_INDOOR_TEMPERATURE
            )
        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id
        self._attr_temperature_unit = description.temperature_unit
        self._attr_hvac_modes = description.hvac_modes
        self._attr_preset_modes = description.preset_modes
        self._enable_turn_on_off_backwards_compatibility = False
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
        self._attr_hvac_mode = (
            None if mode is None else self.entity_description.hvac_mode_mapping[mode]
        )
        self._attr_preset_mode = None if mode is None else HVAC_PRESET_MAPPING[mode]
        self._attr_current_lux_operation = lux_action = get_sensor_data(
            data, self.entity_description.luxtronik_key_current_action.value
        )
        self._attr_hvac_action = (
            None
            if lux_action is None
            else self.entity_description.hvac_action_mapping[lux_action]
        )
        # self._attr_is_aux_heat = (
        #     None if mode is None else mode == LuxMode.second_heatsource.value
        # )
        if self._attr_preset_mode == PRESET_NONE:  # or self._attr_is_aux_heat:
            self._last_hvac_mode_before_preset = None
        key = self.entity_description.luxtronik_key_current_temperature
        if isinstance(key, str):
            temp = self.hass.states.get(key)
            self._attr_current_temperature = state_as_number_or_none(temp, 0.0)
        elif key != LuxCalculation.UNSET:
            self._attr_current_temperature = get_sensor_data(data, key)
        key_tar = self.entity_description.luxtronik_key_target_temperature
        if key_tar != LuxParameter.UNSET:
            self._attr_target_temperature = get_sensor_data(data, key_tar)
        correction_factor = get_sensor_data(
            data, self.entity_description.luxtronik_key_correction_factor.value, False
        )
        # LOGGER.info(f"self._attr_target_temperature={self._attr_target_temperature}")
        # LOGGER.info(f"self._attr_current_temperature={self._attr_current_temperature}")
        # LOGGER.info(f"correction_factor={correction_factor}")
        # LOGGER.info(f"lux_action={lux_action}")
        # LOGGER.info(f"_attr_hvac_action={self._attr_hvac_action}")
        if (
            self._attr_target_temperature is not None
            and self._attr_current_temperature is not None  # noqa: W503
            and self._attr_current_temperature > 0.0
            and correction_factor is not None  # noqa: W503
        ):
            delta_temp = self._attr_target_temperature - self._attr_current_temperature
            correction = round(
                delta_temp * (correction_factor / 100.0), 1
            )  # correction_factor is in %, so need to divide by 100
            key_correction_target = (
                self.entity_description.luxtronik_key_correction_target.value
            )
            correction_current = get_sensor_data(data, key_correction_target)
            # LOGGER.info(f"correction_current={correction_current}")
            # LOGGER.info(f"correction={correction}")
            if correction_current is None or correction_current != correction:
                # LOGGER.info(f'key_correction_target={key_correction_target.split(".")[1]}')
                _ = self.coordinator.write(
                    key_correction_target.split(".")[1], correction
                )  # mypy: allow-unused-coroutine

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

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)
    
    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode[self.entity_description.hvac_mode_mapping[LuxMode.automatic.value].upper()])
        
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._attr_hvac_mode = hvac_mode
        lux_mode = [
            k
            for k, v in self.entity_description.hvac_mode_mapping.items()
            if v == hvac_mode.value
        ][0]
        await self._async_set_lux_mode(lux_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        self._attr_preset_mode = preset_mode
        if preset_mode in [PRESET_COMFORT]:
            lux_mode = LuxMode.automatic
        elif preset_mode != PRESET_NONE:
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

    # async def async_turn_aux_heat_on(self) -> None:
    #     """Turn auxiliary heater on."""
    #     self._attr_is_aux_heat = True
    #     if self._last_hvac_mode_before_preset is None:
    #         self._last_hvac_mode_before_preset = self._attr_hvac_mode
    #     await self._async_set_lux_mode(LuxMode.second_heatsource.value)

    # async def async_turn_aux_heat_off(self) -> None:
    #     """Turn auxiliary heater off."""
    #     self._attr_is_aux_heat = False
    #     if (self._last_hvac_mode_before_preset is None) or (
    #         not self._last_hvac_mode_before_preset in HVAC_PRESET_MAPPING
    #     ):
    #         await self._async_set_lux_mode(LuxMode.automatic.value)
    #     else:
    #         lux_mode = [
    #             k
    #             for k, v in HVAC_PRESET_MAPPING.items()
    #             if v == self._last_hvac_mode_before_preset
    #         ][0]
    #         await self._async_set_lux_mode(lux_mode)

    @property
    def extra_restore_state_data(self) -> LuxtronikClimateExtraStoredData:
        """Return luxtronik climate specific state data to be restored."""
        return LuxtronikClimateExtraStoredData(
            self._attr_target_temperature,
            self._attr_hvac_mode,
            self._attr_preset_mode,
            # self._attr_is_aux_heat,
            self._last_hvac_mode_before_preset,
        )

"""Luxtronik water heater component."""

# region Imports
from __future__ import annotations

from typing import Any
from packaging.version import Version

from typing_extensions import override

from homeassistant.components.climate.const import HVACAction
from homeassistant.components.water_heater import (
    ENTITY_ID_FORMAT,
    STATE_ELECTRIC,
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import LuxtronikEntity
from .common import get_sensor_data, key_exists
from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_PREFIX,
    DEFAULT_DHW_MIN_TEMPERATURE,
    DOMAIN,
    LOGGER,
    DeviceKey,
    LuxCalculation as LC,
    LuxMode,
    LuxOperationMode,
    LuxParameter as LP,
    LuxVisibility as LV,
    SensorKey,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikWaterHeaterDescription

# endregion Imports

# region Const
OPERATION_MAPPING: dict[str, str] = {
    LuxMode.off.value: STATE_OFF,
    LuxMode.automatic.value: STATE_HEAT_PUMP,
    LuxMode.second_heatsource.value: STATE_ELECTRIC,
    LuxMode.party.value: STATE_PERFORMANCE,
    LuxMode.holidays.value: STATE_HEAT_PUMP,
}

WATER_HEATERS: list[LuxtronikWaterHeaterDescription] = [
    LuxtronikWaterHeaterDescription(
        key=SensorKey.DOMESTIC_WATER,
        operation_list=[STATE_OFF, STATE_HEAT_PUMP, STATE_ELECTRIC, STATE_PERFORMANCE],
        supported_features=WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.AWAY_MODE,
        luxtronik_key=LP.P0004_MODE_DHW,
        luxtronik_key_current_temperature=LC.C0017_DHW_TEMPERATURE,
        luxtronik_key_target_temperature=LP.P0002_DHW_TARGET_TEMPERATURE,
        luxtronik_key_current_action=LC.C0080_STATUS,
        luxtronik_action_heating=LuxOperationMode.domestic_water,
        # luxtronik_key_target_temperature_high=LuxParameter,
        # luxtronik_key_target_temperature_low=LuxParameter,
        icon="mdi:water-boiler",
        temperature_unit=UnitOfTemperature.CELSIUS,
        visibility=LV.V0029_DHW_TEMPERATURE,
        max_firmware_version=Version("3.90.0"),
    ),
    LuxtronikWaterHeaterDescription(
        key=SensorKey.DOMESTIC_WATER,
        operation_list=[STATE_OFF, STATE_HEAT_PUMP, STATE_ELECTRIC, STATE_PERFORMANCE],
        supported_features=WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.AWAY_MODE,
        luxtronik_key=LP.P0004_MODE_DHW,
        luxtronik_key_current_temperature=LC.C0017_DHW_TEMPERATURE,
        luxtronik_key_target_temperature=LP.P0105_DHW_TARGET_TEMPERATURE,
        luxtronik_key_current_action=LC.C0080_STATUS,
        luxtronik_action_heating=LuxOperationMode.domestic_water,
        # luxtronik_key_target_temperature_high=LuxParameter,
        # luxtronik_key_target_temperature_low=LuxParameter,
        icon="mdi:water-boiler",
        temperature_unit=UnitOfTemperature.CELSIUS,
        visibility=LV.V0029_DHW_TEMPERATURE,
        min_firmware_version=Version("3.90.1"),
    ),
]
# endregion Const


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize DHW device from config entry."""

    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not data or CONF_COORDINATOR not in data:
        raise ConfigEntryNotReady

    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]

    # Ensure coordinator has valid data before adding entities
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    unavailable_keys = [
        i.luxtronik_key
        for i in WATER_HEATERS
        if not key_exists(coordinator.data, i.luxtronik_key)
    ]
    if unavailable_keys:
        LOGGER.warning("Not present in Luxtronik data, skipping: %s", unavailable_keys)

    async_add_entities(
        [
            LuxtronikWaterHeater(hass, entry, coordinator, description)
            for description in WATER_HEATERS
            if (
                coordinator.entity_active(description)
                and key_exists(coordinator.data, description.luxtronik_key)
            )
        ],
        True,
    )


class LuxtronikWaterHeater(LuxtronikEntity, WaterHeaterEntity):
    """Representation of an Luxtronik water heater."""

    entity_description: LuxtronikWaterHeaterDescription

    _attr_min_temp = DEFAULT_DHW_MIN_TEMPERATURE
    _attr_target_temperature_step = 0.5

    _last_operation_mode_before_away: str | None = None
    _current_action: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikWaterHeaterDescription,
    ) -> None:
        """Init Luxtronik Switch."""
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=DeviceKey.domestic_water,
        )

        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id

        self._attr_temperature_unit = description.temperature_unit
        self._attr_operation_list = description.operation_list
        self._attr_supported_features = description.supported_features

        self._debouncer_set_temp = Debouncer(
            hass,
            LOGGER,
            cooldown=0.5,
            immediate=False,
            function=self._async_write_temperature,
        )
        self._pending_temperature: float | None = None

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature allowed."""
        try:
            if key_exists(self.coordinator.data, LP.P0973_MAX_DHW_TEMPERATURE):
                value = get_sensor_data(
                    self.coordinator.data, LP.P0973_MAX_DHW_TEMPERATURE
                )
                return float(value)
        except (TypeError, ValueError):
            return 60.0  # fallback default

    @property
    def hvac_action(self) -> HVACAction | str | None:
        """Return the current running hvac operation."""
        if (
            self.entity_description.luxtronik_action_heating is not None
            and self._current_action
            == self.entity_description.luxtronik_action_heating.value
        ):
            return HVACAction.HEATING
        return HVACAction.OFF

    @override
    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data if data is None else data
        if data is None:
            return
        descr = self.entity_description
        mode = get_sensor_data(data, descr.luxtronik_key.value)
        self._attr_current_operation = None if mode is None else OPERATION_MAPPING[mode]
        self._current_action = get_sensor_data(
            data, descr.luxtronik_key_current_action.value
        )
        self._attr_is_away_mode_on = (
            None if mode is None else mode == LuxMode.holidays.value
        )
        if not self._attr_is_away_mode_on:
            self._last_operation_mode_before_away = None

        self._attr_current_temperature = get_sensor_data(
            data, descr.luxtronik_key_current_temperature.value
        )
        self._attr_target_temperature = get_sensor_data(
            data, descr.luxtronik_key_target_temperature.value
        )

        self.async_write_ha_state()
        super()._handle_coordinator_update()

    async def _async_set_lux_mode(self, lux_mode: str) -> None:
        lux_key = self.entity_description.luxtronik_key.value
        data = await self.coordinator.async_write(lux_key.split(".")[1], lux_mode)
        self._handle_coordinator_update(data)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        self._pending_temperature = kwargs.get(ATTR_TEMPERATURE)
        await self._debouncer_set_temp.async_call()

    async def _async_write_temperature(self) -> None:
        """Set new target temperature."""
        if self._pending_temperature is None:
            return
        lux_key = self.entity_description.luxtronik_key_target_temperature.value
        data = await self.coordinator.async_write(
            lux_key.split(".")[1], self._pending_temperature
        )
        self._handle_coordinator_update(data)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        lux_mode = [k for k, v in OPERATION_MAPPING.items() if v == operation_mode][0]
        await self._async_set_lux_mode(lux_mode)

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        self._last_operation_mode_before_away = self._attr_current_operation
        await self._async_set_lux_mode(LuxMode.holidays.value)

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        if self._last_operation_mode_before_away is None or (
            self._attr_operation_list is not None
            and self._last_operation_mode_before_away not in self._attr_operation_list
        ):
            await self._async_set_lux_mode(LuxMode.automatic.value)
        else:
            await self.async_set_operation_mode(self._last_operation_mode_before_away)

"""Support for Luxtronik selectors"""

from homeassistant.components.select import ENTITY_ID_FORMAT, SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LuxtronikConfigEntry
from .base import LuxtronikEntity
from .common import get_sensor_data
from .const import (
    CONF_HA_SENSOR_PREFIX,
    DAY_NAME_TO_PARAM,
    DAY_SELECTOR_OPTIONS,
    LOGGER,
    DeviceKey,
    LuxDaySelectorParameter,
    LuxMode,
    LuxParameter,
    SensorKey as SK,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikEntityDescription


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuxtronikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Luxtronik Select entities"""

    coordinator = entry.runtime_data

    # Ensure coordinator has valid data before adding entities
    if not coordinator.last_update_success:
        return

    thermal_desinfection_description = LuxtronikEntityDescription(
        key=SK.THERMAL_DESINFECTION_DAY,
        device_key=DeviceKey.domestic_water,
        luxtronik_key=LuxDaySelectorParameter.MONDAY,
    )

    dhw_description = LuxtronikEntityDescription(
        key=SK.DOMESTIC_WATER,
        device_key=DeviceKey.domestic_water,
        luxtronik_key=LuxParameter.P0004_MODE_DHW,
        name="DHW mode",
    )

    heating_mode_description = LuxtronikEntityDescription(
        key=SK.HEATING,
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0003_MODE_HEATING,
        name="Heating mode",
    )

    heating_mk1_mode_description = LuxtronikEntityDescription(
        key=SK.HEATING,
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0695_MODE_HZ_MK1,
        name="Heating mode MK1",
        entity_registry_enabled_default=False,
    )

    heating_mk2_mode_description = LuxtronikEntityDescription(
        key=SK.HEATING,
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0696_MODE_HZ_MK2,
        name="Heating mode MK2",
        entity_registry_enabled_default=False,
    )

    heating_mk3_mode_description = LuxtronikEntityDescription(
        key=SK.HEATING,
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0779_MODE_HZ_MK3,
        name="Heating mode MK3",
        entity_registry_enabled_default=False,
    )

    mode_options = [
        LuxMode.off,
        LuxMode.automatic,
        LuxMode.second_heatsource,
        LuxMode.party,
        LuxMode.holidays,
    ]

    mode_mk_options = [
        LuxMode.off,
        LuxMode.automatic,
        LuxMode.second_heatsource,
        LuxMode.party,
        LuxMode.holidays,
    ]

    entities: list[LuxtronikEntity[LuxtronikEntityDescription]] = [
        LuxtronikThermalDesinfectionDaySelector(
            entry,
            coordinator,
            thermal_desinfection_description,
            thermal_desinfection_description.device_key,
        ),

        LuxtronikModeSelector(
            entry=entry,
            coordinator=coordinator,
            description=dhw_description,
            device_info_ident=DeviceKey.domestic_water,
            lux_parameter=LuxParameter.P0004_MODE_DHW,
            options=mode_options,
            entity_suffix="dhw_mode",
        ),

        LuxtronikModeSelector(
            entry=entry,
            coordinator=coordinator,
            description=heating_mode_description,
            device_info_ident=DeviceKey.heating,
            lux_parameter=LuxParameter.P0003_MODE_HEATING,
            options=mode_options,
            entity_suffix="heating_mode",
        ),

        LuxtronikModeSelector(
            entry=entry,
            coordinator=coordinator,
            description=heating_mk1_mode_description,
            device_info_ident=DeviceKey.heating,
            lux_parameter=LuxParameter.P0695_MODE_HZ_MK1,
            options=mode_mk_options,
            entity_suffix="heating_mode_mk1",
        ),

        LuxtronikModeSelector(
            entry=entry,
            coordinator=coordinator,
            description=heating_mk2_mode_description,
            device_info_ident=DeviceKey.heating,
            lux_parameter=LuxParameter.P0696_MODE_HZ_MK2,
            options=mode_mk_options,
            entity_suffix="heating_mode_mk2",
        ),

        LuxtronikModeSelector(
            entry=entry,
            coordinator=coordinator,
            description=heating_mk3_mode_description,
            device_info_ident=DeviceKey.heating,
            lux_parameter=LuxParameter.P0779_MODE_HZ_MK3,
            options=mode_mk_options,
            entity_suffix="heating_mode_mk3",
        ),
    ]

    async_add_entities(entities, True)


class LuxtronikThermalDesinfectionDaySelector(  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    LuxtronikEntity[LuxtronikEntityDescription], SelectEntity
):
    """Luxtronik Thermal Desinfection Day Selector Entity."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikEntityDescription,
        device_info_ident: DeviceKey,
    ):
        # No description needed for this custom entity

        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
        )

        self._attr_options = DAY_SELECTOR_OPTIONS
        self._attr_current_option = "None"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = "mdi:calendar"
        self.coordinator = coordinator

        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_thermal_desinfection_day")
        self._attr_unique_id = self.entity_id

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        # if not self.should_update():
        #    return

        super()._handle_coordinator_update()
        data = self.coordinator.data if data is None else data
        if data is None:
            return

        selected_day = "None"
        for day, param_enum in DAY_NAME_TO_PARAM.items():
            param = param_enum.value
            value = get_sensor_data(data, param)
            if str(value) == "1":
                selected_day = day
                break

        if self._attr_current_option != selected_day:
            self._attr_current_option = selected_day
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Handle selection of a new day."""
        self._attr_current_option = option
        data = self.coordinator.data
        if data is None:
            return

        for day, param_enum in DAY_NAME_TO_PARAM.items():
            param = param_enum.value
            desired_value = 1 if day == option else 0
            current_value = int(get_sensor_data(data, param))

            if current_value != desired_value:
                updated_data = await self.coordinator.async_write(
                    param.split(".")[1], desired_value
                )
                self._handle_coordinator_update(updated_data)

    async def async_update(self) -> None:
        """Read current day from heat pump and update selected option."""
        data = self.coordinator.data
        selected_day = "None"

        for day, param_enum in DAY_NAME_TO_PARAM.items():
            param = param_enum.value
            value = get_sensor_data(data, param)
            if str(value) == "1":
                selected_day = day
                break

        self._attr_current_option = selected_day


class LuxtronikModeSelector(LuxtronikEntity, SelectEntity):
    """Generic Luxtronik Mode Selector."""

    def __init__(
        self,
        *,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikEntityDescription,
        device_info_ident: DeviceKey,
        lux_parameter: LuxParameter,
        options: list[str],
        entity_suffix: str,
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
        )

        self._lux_parameter = lux_parameter
        self._attr_options = options
        self._attr_current_option = None

        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{entity_suffix}")
        self._attr_unique_id = self.entity_id

    # ---------------------------------------------------------------------

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        super()._handle_coordinator_update()

        data = self.coordinator.data if data is None else data
        if data is None:
            return

        value = get_sensor_data(data, self._lux_parameter)
        current = str(value)

        LOGGER.debug(
            "%s raw value from coordinator: %r",
            self.entity_id,
            current,
        )

        if current not in self._attr_options:
            LOGGER.warning(
                "%s value %r not in options %r",
                self.entity_id,
                current,
                self._attr_options,
            )
            return

        if self._attr_current_option != current:
            self._attr_current_option = current
            self.async_write_ha_state()

    # ---------------------------------------------------------------------

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            LOGGER.warning(
                "Selected value %r not in options %r",
                option,
                self._attr_options,
            )
            return

        LOGGER.debug("Setting %s to %r", self.entity_id, option)

        self._attr_current_option = option

        updated_data = await self.coordinator.async_write(
            self._lux_parameter.split(".")[1],
            option,
        )
        self._handle_coordinator_update(updated_data)

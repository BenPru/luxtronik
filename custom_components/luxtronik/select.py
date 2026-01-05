"""Support for Luxtronik selectors"""

from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback


from .base import LuxtronikEntity
from .common import get_sensor_data
from .const import (
    DAY_SELECTOR_OPTIONS,
    DOMAIN,
    LOGGER,
    CONF_COORDINATOR,
    CONF_HA_SENSOR_PREFIX,
    LuxDaySelectorParameter,
    DAY_NAME_TO_PARAM,
    DeviceKey,
    LuxMode,
    LuxParameter,
    SensorKey as SK,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikEntityDescription


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Luxtronik Select entities"""

    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not data or CONF_COORDINATOR not in data:
        raise ConfigEntryNotReady

    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]

    # Ensure coordinator has valid data before adding entities
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

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

    entities: list[LuxtronikEntity] = [
        LuxtronikThermalDesinfectionDaySelector(
            entry,
            coordinator,
            thermal_desinfection_description,
            thermal_desinfection_description.device_key,
        ),
        LuxtronikDhwModeSelector(
            entry, coordinator, dhw_description, dhw_description.device_key
        ),
        LuxtronikHeatingModeSelector(
            entry,
            coordinator,
            heating_mode_description,
            heating_mode_description.device_key,
        ),
    ]

    async_add_entities(entities, True)


class LuxtronikThermalDesinfectionDaySelector(LuxtronikEntity, SelectEntity):
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


class LuxtronikDhwModeSelector(LuxtronikEntity, SelectEntity):
    """Luxtronik Domestic Hot Water Mode Selector."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikEntityDescription,
        device_info_ident: DeviceKey,
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
        )
        self._attr_options = [
            LuxMode.off.value,
            LuxMode.automatic.value,
            LuxMode.second_heatsource.value,
            LuxMode.party.value,
            LuxMode.holidays.value,
        ]
        self._attr_current_option = LuxMode.off.value

        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_dhw_mode")
        self._attr_unique_id = self.entity_id

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        super()._handle_coordinator_update()
        data = self.coordinator.data if data is None else data
        if data is None:
            return

        param = LuxParameter.P0004_MODE_DHW.value
        value = get_sensor_data(data, param)
        LOGGER.debug("DHW mode raw value from coordinator: %r", value)

        current = str(value)

        if current not in self._attr_options:
            LOGGER.warning(
                "DHW mode value %r not in options %r", current, self._attr_options
            )
            return

        if self._attr_current_option != current:
            LOGGER.debug(
                "DHW mode changed: %r -> %r", self._attr_current_option, current
            )
            self._attr_current_option = current
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            LOGGER.warning(
                "DHW mode value %r not in options %r", option, self._attr_options
            )
            return

        self._attr_current_option = option
        param = LuxParameter.P0004_MODE_DHW.value

        LOGGER.debug("Setting DHW mode to %r", option)

        updated_data = await self.coordinator.async_write(
            param.split(".")[1],
            option,
        )
        self._handle_coordinator_update(updated_data)


class LuxtronikHeatingModeSelector(LuxtronikEntity, SelectEntity):
    """Luxtronik Heating Mode Selector."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikEntityDescription,
        device_info_ident: DeviceKey,
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
        )
        self._attr_options = [
            LuxMode.off.value,
            LuxMode.automatic.value,
            LuxMode.second_heatsource.value,
            LuxMode.party.value,
            LuxMode.holidays.value,
        ]
        self._attr_current_option = LuxMode.off.value

        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_heating_mode")
        self._attr_unique_id = self.entity_id

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        super()._handle_coordinator_update()
        data = self.coordinator.data if data is None else data
        if data is None:
            return

        param = LuxParameter.P0003_MODE_HEATING.value
        value = get_sensor_data(data, param)
        LOGGER.debug("Heating mode raw value from coordinator: %r", value)

        current = str(value)

        if current not in self._attr_options:
            LOGGER.warning(
                "Heating mode value %r not in options %r", current, self._attr_options
            )
            return

        if self._attr_current_option != current:
            LOGGER.debug(
                "Heating mode changed: %r -> %r", self._attr_current_option, current
            )
            self._attr_current_option = current
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            LOGGER.warning(
                "Selected heating mode %r not in options %r", option, self._attr_options
            )
            return

        self._attr_current_option = option
        param = LuxParameter.P0003_MODE_HEATING.value

        LOGGER.debug("Setting heating mode to %r", option)

        updated_data = await self.coordinator.async_write(
            param.split(".")[1],
            option,
        )
        self._handle_coordinator_update(updated_data)

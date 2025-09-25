"""Support for Luxtronik binary sensors."""

# region Imports
from __future__ import annotations

from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .base import LuxtronikEntity
from .binary_sensor_entities_predefined import BINARY_SENSORS
from .common import get_sensor_data
from .const import CONF_COORDINATOR, CONF_HA_SENSOR_PREFIX, DOMAIN, DeviceKey
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikBinarySensorEntityDescription

import asyncio
# endregion Imports


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Luxtronik binary sensors dynamically through Luxtronik discovery."""

    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not data or CONF_COORDINATOR not in data:
        raise ConfigEntryNotReady

    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]

    async_add_entities(
        (
            LuxtronikBinarySensorEntity(
                hass, entry, coordinator, description, description.device_key
            )
            for description in BINARY_SENSORS
            if coordinator.entity_active(description)
        ),
        True,
    )


class LuxtronikBinarySensorEntity(LuxtronikEntity, BinarySensorEntity):
    """Luxtronik Binary Sensor Entity."""

    entity_description: LuxtronikBinarySensorEntityDescription
    _coordinator: LuxtronikCoordinator

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikBinarySensorEntityDescription,
        device_info_ident: DeviceKey,
    ) -> None:
        """Initialize Luxtronik Binary Sensor Entity."""
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
        )
        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id
        # self._sensor_data = get_sensor_data(
        #     coordinator.data, description.luxtronik_key.value
        # )


        self.async_on_remove(
            hass.bus.async_listen(f"{DOMAIN}_data_update", self._handle_data_update_event)
        )

    @callback
    def _handle_data_update_event(self, event) -> None:
        """Handle Luxtronik data update event."""
        self.hass.async_create_task(self._async_handle_coordinator_update())

    @callback
    def _handle_coordinator_update(self) -> None:
        """Sync callback registered with DataUpdateCoordinator."""
        self.hass.async_create_task(self._async_handle_coordinator_update())

    async def _async_handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        if not self.should_update():
            return

        data = self.coordinator.data if data is None else data
        if data is None:
            return

        self._attr_state = get_sensor_data(
            data, self.entity_description.luxtronik_key.value
        )

        if isinstance(self.entity_description.on_state, bool) and self._attr_state is not None:
            self._attr_state = bool(self._attr_state)

        if self.entity_description.inverted:
            self._attr_is_on = self._attr_state != self.entity_description.on_state
        else:
            self._attr_is_on = (
                self._attr_state == self.entity_description.on_state
                or (
                    self.entity_description.on_states is not None
                    and self._attr_state in self.entity_description.on_states
                )
            )

        await super()._async_handle_coordinator_update()
        self.async_write_ha_state()


"""Support for Luxtronik switches."""

# region Imports
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import LuxtronikEntity
from .common import get_sensor_data, key_exists
from .const import CONF_COORDINATOR, CONF_HA_SENSOR_PREFIX, DOMAIN, DeviceKey, LOGGER

from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikSwitchDescription
from .switch_entities_predefined import SWITCHES

# endregion Imports


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Luxtronik switches dynamically through Luxtronik discovery."""

    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not data or CONF_COORDINATOR not in data:
        raise ConfigEntryNotReady

    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]

    # Ensure coordinator has valid data before adding entities
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    unavailable_keys = [
        i.luxtronik_key
        for i in SWITCHES
        if not key_exists(coordinator.data, i.luxtronik_key)
    ]
    if unavailable_keys:
        LOGGER.warning("Not present in Luxtronik data, skipping: %s", unavailable_keys)

    async_add_entities(
        [
            LuxtronikSwitchEntity(
                hass, entry, coordinator, description, description.device_key
            )
            for description in SWITCHES
            if (
                coordinator.entity_active(description)
                and key_exists(coordinator.data, description.luxtronik_key)
            )
        ],
        True,
    )


class LuxtronikSwitchEntity(LuxtronikEntity, SwitchEntity):
    """Luxtronik Switch Entity."""

    entity_description: LuxtronikSwitchDescription
    _coordinator: LuxtronikCoordinator

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikSwitchDescription,
        device_info_ident: DeviceKey,
    ) -> None:
        """Initialize Luxtronik Switch."""
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
        )

        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        # if not self.should_update():
        #    return

        data = self.coordinator.data if data is None else data
        if data is None:
            return

        descr = self.entity_description
        state = get_sensor_data(data, descr.luxtronik_key.value)
        self._attr_is_on = self.compute_is_on(state)

        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._set_state(self.entity_description.on_state)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._set_state(self.entity_description.off_state)

    async def _set_state(self, state):
        LOGGER.debug("Setting switch %s to %s", self.entity_id, state)
        data = await self.coordinator.async_write(
            self.entity_description.luxtronik_key.value.split(".")[1], state
        )

        self._handle_coordinator_update(data)

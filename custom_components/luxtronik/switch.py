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

    async_add_entities(
        (
            LuxtronikSwitchEntity(
                hass, entry, coordinator, description, description.device_key
            )
            for description in SWITCHES
            if coordinator.entity_active(description)
        ),
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
    def _handle_coordinator_update(self) -> None:
        """Sync callback registered with DataUpdateCoordinator."""
        self.hass.async_create_task(self._async_handle_coordinator_update())

    async def _async_handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data if data is None else data
        if data is None:
            return

        descr = self.entity_description
        state = self._get_value(descr.luxtronik_key)

        if isinstance(descr.on_state, bool) and state is not None:
            state = bool(state)

        if descr.inverted:
            self._attr_is_on = state != descr.on_state
        else:
            self._attr_is_on = state == descr.on_state or (
                descr.on_states is not None and state in descr.on_states
            )

        await super()._async_handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._set_state(self.entity_description.on_state)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._set_state(self.entity_description.off_state)

    async def _set_state(self, state: Any) -> None:
        LOGGER.debug("Setting switch %s to %s", self.entity_id, state)

        await self.coordinator.async_write(
            self.entity_description.luxtronik_key.value.split(".")[1], state
        )

        # Coordinator will refresh and trigger update callback

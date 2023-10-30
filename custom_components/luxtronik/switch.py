"""Support for Luxtronik switches."""
# region Imports
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .base import LuxtronikEntity
from .common import get_sensor_data
from .const import CONF_COORDINATOR, CONF_HA_SENSOR_PREFIX, DOMAIN, DeviceKey
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikSwitchDescription
from .switch_entities_predefined import SWITCHES

# endregion Imports


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up luxtronik sensors dynamically through luxtronik discovery."""
    data: dict = hass.data[DOMAIN][entry.entry_id]
    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]
    await coordinator.async_config_entry_first_refresh()

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
        """Init Luxtronik Switch."""
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
        )
        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id
        self._sensor_data = get_sensor_data(
            coordinator.data, description.luxtronik_key.value
        )

        hass.bus.async_listen(f"{DOMAIN}_data_update", self._data_update)

    async def _data_update(self, event):
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        if (
            not self.coordinator.update_reason_write
            and self.next_update is not None
            and self.next_update > utcnow()
        ):
            return
        data = self.coordinator.data if data is None else data
        if data is None:
            return
        descr = self.entity_description
        self._attr_state = get_sensor_data(data, descr.luxtronik_key.value)
        if descr.on_state is True or descr.on_state is False:
            if self._attr_state is not None:
                self._attr_state = bool(self._attr_state)
        if descr.inverted:
            self._attr_is_on = self._attr_state != descr.on_state
        else:
            self._attr_is_on = self._attr_state == descr.on_state or (
                descr.on_states is not None and self._attr_state in descr.on_states
            )

        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._set_state(self.entity_description.on_state)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._set_state(self.entity_description.off_state)

    async def _set_state(self, state):
        data = await self.coordinator.async_write(
            self.entity_description.luxtronik_key.value.split(".")[1], state
        )
        value = get_sensor_data(data, self.entity_description.luxtronik_key.value)
        if (
            self.entity_description.on_state is True
            or self.entity_description.on_state is False
        ):
            value = bool(value)
        self._attr_is_on = (
            value != self.entity_description.on_state
            if self.entity_description.inverted
            else value == self.entity_description.on_state
        )
        self._handle_coordinator_update()

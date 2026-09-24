"""Support for Luxtronik switches."""

# region Imports
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LuxtronikConfigEntry
from .base import LuxtronikEntity
from .common import evu2_manual_input_required, get_sensor_data, key_exists
from .const import CONF_HA_SENSOR_PREFIX, LOGGER, DeviceKey
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikSwitchDescription
from .switch_entities_predefined import EVU2_MANUAL_SWITCH, SWITCHES

# endregion Imports

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuxtronikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Luxtronik switches dynamically through Luxtronik discovery."""

    coordinator = entry.runtime_data

    # Ensure coordinator has valid data before adding entities
    if not coordinator.last_update_success:
        return

    unavailable_keys = [
        i.luxtronik_key
        for i in SWITCHES
        if not key_exists(coordinator.data, i.luxtronik_key)
    ]
    if unavailable_keys:
        # Not all models/firmware versions support every parameter;
        # missing keys are expected and not an error.
        LOGGER.debug("Not present in Luxtronik data, skipping: %s", unavailable_keys)

    entities: list[LuxtronikSwitchEntity] = [
        LuxtronikSwitchEntity(
            hass, entry, coordinator, description, description.device_key
        )
        for description in SWITCHES
        if (
            coordinator.entity_active(description)
            and key_exists(coordinator.data, description.luxtronik_key)
        )
    ]

    if evu2_manual_input_required(coordinator.data):
        # Only while SmartGrid is on, like the SG offset numbers: turning SG on
        # later makes it appear after a reload.
        entities.append(
            LuxtronikEvu2ManualSwitch(
                hass,
                entry,
                coordinator,
                EVU2_MANUAL_SWITCH,
                EVU2_MANUAL_SWITCH.device_key,
            )
        )

    async_add_entities(entities)


class LuxtronikSwitchEntity(LuxtronikEntity[LuxtronikSwitchDescription], SwitchEntity):  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    """Luxtronik Switch Entity."""

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


class LuxtronikEvu2ManualSwitch(LuxtronikSwitchEntity):
    """The SG2 contact, set by hand where the controller does not report it (#500).

    On the models in EVU2_MANUAL_INPUT_MODELS no register follows the SG2
    contact, so the SmartGrid status cannot tell state 2 from state 3 (or 1
    from 4) on its own. This switch stands in for the contact: set it once if
    SG2 is wired permanently, or drive it from an automation that follows
    whatever switches the contact.

    Nothing is written to the heat pump. The value lives on the coordinator,
    which feeds it to the SmartGrid status sensor and the EVU2 binary sensor.
    The coordinator also restores it across restarts, from this switch's last
    state, before any platform is set up - see async_restore_evu2_manual.
    """

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Show the setting the coordinator holds; there is no register.

        The setting rather than `data.evu2_manual`, which is None while
        SmartGrid is off: showing off then would be stored as the last state
        on the next reload and lose the setting.
        """
        data = self.coordinator.data if data is None else data
        if data is None:
            return
        self._attr_is_on = self.coordinator.evu2_manual
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Mark the SG2 contact as closed."""
        self.coordinator.set_evu2_manual(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Mark the SG2 contact as open."""
        self.coordinator.set_evu2_manual(False)

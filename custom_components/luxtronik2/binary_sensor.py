"""Support for Luxtronik binary sensors."""

# region Imports
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LuxtronikConfigEntry
from .base import LuxtronikEntity
from .binary_sensor_entities_predefined import BINARY_SENSORS
from .common import get_sensor_data, key_exists
from .const import CONF_HA_SENSOR_PREFIX, LOGGER, DeviceKey, SensorKey
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikBinarySensorEntityDescription

# endregion Imports

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuxtronikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Luxtronik binary sensors dynamically through Luxtronik discovery."""

    coordinator = entry.runtime_data

    unavailable_keys = [
        i.luxtronik_key
        for i in BINARY_SENSORS
        if not key_exists(coordinator.data, i.luxtronik_key)
    ]
    if unavailable_keys:
        # Not all models/firmware versions support every parameter;
        # missing keys are expected and not an error.
        LOGGER.debug("Not present in Luxtronik data, skipping: %s", unavailable_keys)

    async_add_entities(
        [
            LuxtronikBinarySensorEntity(
                hass, entry, coordinator, description, description.device_key
            )
            for description in BINARY_SENSORS
            if (
                coordinator.entity_active(description)
                and key_exists(coordinator.data, description.luxtronik_key)
            )
        ],
        True,
    )


class LuxtronikBinarySensorEntity(  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    LuxtronikEntity[LuxtronikBinarySensorEntityDescription], BinarySensorEntity
):
    """Luxtronik Binary Sensor Entity."""

    _coordinator: LuxtronikCoordinator

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikBinarySensorEntityDescription,
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

        # if descr.luxtronik_key == LC.C0146_APPROVAL_COOLING:
        #    LOGGER.info('Cooling Approval=%s',self._attr_state)
        #    LOGGER.info('on_state=%s',descr.on_state)

        super()._handle_coordinator_update()

    def compute_is_on(self, state: Any) -> bool:  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
        """Compute the is_on state, with special handling for shared registers.

        Special handling for DISTURBANCE_OUTPUT (C0049 / ID_WEB_ZW2SSTout):
        This register is shared between ZWE2 (Additional Heat Generator 2) activation
        and SST (Collective Fault Signal). To disambiguate:
        - If disturbance_output is ON and error_reason changed at the same time or after,
          it's a real fault
        - If disturbance_output is ON but error_reason hasn't changed, it's just ZWE2
          activation noise (e.g., during thermal disinfection cycles)

        See: https://github.com/BenPru/luxtronik/issues/532
        """
        descr = self.entity_description

        # Special handling for DISTURBANCE_OUTPUT (C0049 / ID_WEB_ZW2SSTout)
        if descr.key == SensorKey.DISTURBANCE_OUTPUT and state is True:
            LOGGER.debug("Entering special handling for DISTURBANCE_OUTPUT")
            # Get entity IDs for cross-reference checks
            disturbance_entity_id = self.entity_id
            # Construct error_reason entity ID using same prefix pattern
            error_reason_entity_id = disturbance_entity_id.replace(
                f"_{SensorKey.DISTURBANCE_OUTPUT.value}",
                f"_{SensorKey.ERROR_REASON.value}",
            )

            # Get state objects to check last_changed timestamps
            disturbance_state = self.hass.states.get(disturbance_entity_id)
            error_state = self.hass.states.get(error_reason_entity_id)
            LOGGER.debug(
                "Disturbance state: %s, Error state: %s", disturbance_state, error_state
            )

            if disturbance_state and error_state:
                LOGGER.debug("Both states are available for DISTURBANCE_OUTPUT")
                try:
                    disturbance_changed = disturbance_state.last_changed
                    error_changed = error_state.last_changed
                    LOGGER.debug(
                        "Disturbance changed: %s, Error changed: %s",
                        disturbance_changed,
                        error_changed,
                    )

                    # If error_reason changed BEFORE disturbance_output,
                    # then the disturbance output is just ZWE2 noise, not a fault
                    if (
                        disturbance_changed
                        and error_changed
                        and error_changed < disturbance_changed
                    ):
                        LOGGER.debug(
                            "DISTURBANCE_OUTPUT active but error_reason hasn't changed "
                            "since output activation (error: %s, disturbance: %s), "
                            "treating as ZWE2 operation, not a fault",
                            error_changed,
                            disturbance_changed,
                        )
                        return False
                except (AttributeError, TypeError) as e:
                    LOGGER.debug(
                        "Could not compare timestamps for DISTURBANCE_OUTPUT fault detection: %s",
                        e,
                    )

        # Default computation
        if isinstance(descr.on_state, bool) and state is not None:  # pyright: ignore[reportAttributeAccessIssue]
            state = bool(state)

        is_on = bool(
            state == descr.on_state or (descr.on_states and state in descr.on_states)  # pyright: ignore[reportAttributeAccessIssue]
        )

        return not is_on if getattr(descr, "inverted", False) else is_on

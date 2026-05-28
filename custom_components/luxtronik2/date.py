from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.date import (
    ENTITY_ID_FORMAT,  # pyright: ignore[reportAttributeAccessIssue]
    DateEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LuxtronikConfigEntry
from .base import LuxtronikEntity
from .common import get_sensor_data, key_exists
from .const import (
    CONF_HA_SENSOR_PREFIX,
    LOGGER,
    DeviceKey,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .date_entities_predefined import CALENDAR_ENTITIES
from .model import LuxtronikDateEntityDescription

PARALLEL_UPDATES = 1


async def async_setup_entry(  # pragma: no cover
    hass: HomeAssistant,
    entry: LuxtronikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    if not coordinator.last_update_success:
        return

    unavailable_keys = [
        i.luxtronik_key
        for i in CALENDAR_ENTITIES
        if not key_exists(coordinator.data, i.luxtronik_key)
    ]
    if unavailable_keys:
        # Not all models/firmware versions support every parameter;
        # missing keys are expected and not an error.
        LOGGER.debug("Not present in Luxtronik data, skipping: %s", unavailable_keys)

    async_add_entities(
        [
            LuxtronikDateEntity(
                hass, entry, coordinator, description, description.device_key
            )
            for description in CALENDAR_ENTITIES
            if (
                coordinator.entity_active(description)
                and key_exists(coordinator.data, description.luxtronik_key)
            )
        ],
        True,
    )


class LuxtronikDateEntity(LuxtronikEntity[LuxtronikDateEntityDescription], DateEntity):  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    """Luxtronik Date Entity that supports user-editable dates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikDateEntityDescription,
        device_info_ident: DeviceKey,
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
        )

        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id
        self._attr_native_value = None

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        data = self.coordinator.data if data is None else data
        if data is None:
            return

        value = get_sensor_data(data, self.entity_description.luxtronik_key.value)

        if isinstance(value, int | float):
            try:
                dt_value = datetime.fromtimestamp(value)
                self._attr_native_value = dt_value.date()
            except (ValueError, OSError):
                self._attr_native_value = None
        elif isinstance(value, date):
            self._attr_native_value = value
        else:
            self._attr_native_value = None

        self.async_write_ha_state()
        super()._handle_coordinator_update()

    async def async_set_value(self, value: date) -> None:
        """Handle user-set date from the UI."""
        self._attr_native_value = value
        dt = datetime.combine(value, datetime.min.time())  # datetime object
        await self.coordinator.async_write(
            self.entity_description.luxtronik_key.value.split(".")[1], dt
        )
        self.async_write_ha_state()

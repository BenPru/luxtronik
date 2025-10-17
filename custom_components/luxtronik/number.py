"""Support for Luxtronik number sensors."""

# flake8: noqa: W503
# region Imports
from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.number import ENTITY_ID_FORMAT, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .base import LuxtronikEntity
from .common import get_sensor_data, key_exists
from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    LOGGER,
    DeviceKey,
    SensorAttrFormat,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikEntityAttributeDescription, LuxtronikNumberDescription
from .number_entities_predefined import NUMBER_SENSORS

# endregion Imports


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Luxtronik binary sensors dynamically through Luxtronik discovery."""

    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not data or CONF_COORDINATOR not in data:
        raise ConfigEntryNotReady

    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]

    # Ensure coordinator has valid data before adding entities
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    unavailable_keys = [
        i.luxtronik_key
        for i in NUMBER_SENSORS
        if not key_exists(coordinator.data, i.luxtronik_key)
    ]
    if unavailable_keys:
        LOGGER.warning("Not present in Luxtronik data, skipping: %s", unavailable_keys)

    async_add_entities(
        [
            LuxtronikNumberEntity(
                hass, entry, coordinator, description, description.device_key
            )
            for description in NUMBER_SENSORS
            if (
                coordinator.entity_active(description)
                and key_exists(coordinator.data, description.luxtronik_key)
            )
        ],
        True,
    )


class LuxtronikNumberEntity(LuxtronikEntity, NumberEntity):
    """Luxtronik Number Entity."""

    entity_description: LuxtronikNumberDescription
    _coordinator: LuxtronikCoordinator

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikNumberDescription,
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

        self._attr_mode = description.mode

        # Debouncer for rate-limiting value updates
        self._debouncer = Debouncer(
            hass,
            LOGGER,
            cooldown=0.5,
            immediate=False,
            function=self._async_set_native_value,
        )

        # Store pending value for debounced write
        self._pending_value: float | None = None

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

        value = get_sensor_data(data, self.entity_description.luxtronik_key.value)

        if value is None:
            self._attr_native_value = None
        elif isinstance(value, (float, int)):
            factor = self.entity_description.factor or 1
            precision = self.entity_description.native_precision
            value = float(value) * factor
            if precision is not None:
                value = round(value, precision)
            self._attr_native_value = value
        else:
            self._attr_native_value = value

        self.async_write_ha_state()
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        self._pending_value = value
        await self._debouncer.async_call()

    async def _async_set_native_value(self):
        if self._pending_value is None:
            return
        value = self._pending_value

        if self.entity_description.factor is not None:
            value = int(value / self.entity_description.factor)
        data = await self.coordinator.async_write(
            self.entity_description.luxtronik_key.value.split(".")[1], value
        )
        self._handle_coordinator_update(data)

    def formatted_data(self, attr: LuxtronikEntityAttributeDescription) -> str:
        """Calculate the attribute value."""
        if attr.format != SensorAttrFormat.TIMESTAMP_LAST_OVER:
            return super().formatted_data(attr)
        value = self._get_value(attr.luxtronik_key)
        if value is None:
            return ""
        if attr.format is None:
            return str(value)
        if (
            self._attr_state is not None
            and float(value)
            >= float(self._attr_state) * float(self.entity_description.factor)
            and (
                attr.key not in self._attr_cache
                or self._is_past(self._attr_cache[attr.key])
            )
        ):
            self._attr_cache[attr.key] = dt_util.utcnow().date()
        result = self._attr_cache[attr.key] if attr.key in self._attr_cache else ""

        return str(result)

    def _is_past(self, value: str | date) -> bool:
        if value is None or value == "":
            return True
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                return True
        return value < dt_util.utcnow().date()

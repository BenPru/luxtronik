"""Support for Luxtronik number sensors."""

# flake8: noqa: W503
# region Imports
from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.number import ENTITY_ID_FORMAT, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .base import LuxtronikEntity
from .common import get_sensor_data
from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
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
    """Set up luxtronik number sensors dynamically through luxtronik discovery."""
    data: dict = hass.data[DOMAIN][entry.entry_id]
    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        (
            LuxtronikNumberEntity(
                hass, entry, coordinator, description, description.device_key
            )
            for description in NUMBER_SENSORS
            if coordinator.entity_active(description)
        ),
        True,
    )


class LuxtronikNumberEntity(LuxtronikEntity, NumberEntity):
    """Luxtronik Sensor Entity."""

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
        self._sensor_data = get_sensor_data(
            coordinator.data, description.luxtronik_key.value
        )

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
        self._attr_native_value = get_sensor_data(
            data, self.entity_description.luxtronik_key.value
        )
        if self._attr_native_value is not None:
            if self.entity_description.factor is not None:
                self._attr_native_value *= self.entity_description.factor
            if self.entity_description.native_precision is not None:
                self._attr_native_value = round(
                    self._attr_native_value, self.entity_description.native_precision
                )
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        #     self._async_set_native_value(value)

        # TODO: Debounce number input
        # @debounce(0.5)
        # async def _async_set_native_value(self, value: float) -> None:
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
            self._attr_cache[attr.key] = datetime.now().date()
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
        return value < datetime.now().date()

"""Support for Luxtronik sensors."""
# region Imports
from __future__ import annotations

from homeassistant.components.sensor import ENTITY_ID_FORMAT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import LuxtronikEntity
from .common import get_sensor_data
from .const import CONF_COORDINATOR, CONF_HA_SENSOR_PREFIX, DOMAIN, DeviceKey
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikSensorDescription
from .sensor_entities_predefined import SENSORS

# endregion Imports


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up luxtronik sensors dynamically through luxtronik discovery."""
    data: dict = hass.data[DOMAIN][entry.entry_id]
    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        LuxtronikSensorEntity(
            hass, entry, coordinator, description, description.device_key
        )
        for description in SENSORS
        if coordinator.entity_active(description)
    )


class LuxtronikSensorEntity(LuxtronikEntity, SensorEntity):
    """Luxtronik Sensor Entity."""

    entity_description: LuxtronikSensorDescription
    _coordinator: LuxtronikCoordinator

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikSensorDescription,
        device_info_ident: DeviceKey,
    ) -> None:
        """Init Luxtronik Switch."""
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
            platform=Platform.SENSOR,
        )
        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id
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
        data = self.coordinator.data if data is None else data
        if data is None:
            return
        self._attr_native_value = get_sensor_data(
            data, self.entity_description.luxtronik_key.value
        )
        if self._attr_native_value is not None and isinstance(
            self._attr_native_value, float
        ):
            float_value = float(self._attr_native_value)
            if self.entity_description.factor is not None:
                float_value *= self.entity_description.factor
            if self.entity_description.decimal_places is not None:
                float_value = round(float_value, self.entity_description.decimal_places)
            self._attr_native_value = float_value
        super()._handle_coordinator_update()

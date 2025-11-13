"""Luxtronik select sensors definitions."""
# region Imports
from homeassistant.helpers.entity import EntityCategory

from .const import (
    DeviceKey,
    LuxParameter as LP,
    SensorKey,
)
from .model import LuxtronikSelectDescription

# endregion Imports

INPUT_SELECT = [
    LuxtronikSelectDescription(
        key=SensorKey.HEATING_CONTROL_CIRCUIT_MODE,
        luxtronik_key=LP.P0103_HEATING_CONTROL_CIRCUIT_MODE,
        device_key=DeviceKey.heating,
        # key="zoneselect",
        # name="Current zone",
        entity_category=EntityCategory.CONFIG,
        device_class=None,
        entity_registry_enabled_default=False,
        unit_of_measurement=None,
        options=["0", "1", "2"],
        # value_fn=lambda device: device.zone.current,
        # command_fn=lambda api, value: api.cloud.setzone(
        #     api.device.serial_number, value
        # ),
        icon="mdi:map-clock",
    ),
]

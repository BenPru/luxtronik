"""Support for Luxtronik heatpump binary states."""
# region Imports
import logging
from typing import Any, Final

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (DEVICE_CLASS_HEAT,
                                                    PLATFORM_SCHEMA,
                                                    BinarySensorEntity)
from homeassistant.components.sensor import (ENTITY_ID_FORMAT,
                                             STATE_CLASS_MEASUREMENT,
                                             SensorEntity)
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_FRIENDLY_NAME, CONF_ICON, CONF_ID,
                                 CONF_SENSORS)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import ENTITY_CATEGORIES, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from . import LuxtronikDevice
from .binary_sensor import LuxtronikBinarySensor
from .const import *
from .helpers.helper import get_sensor_text

# endregion Imports

# region Constants
# endregion Constants

# region Setup


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Luxtronik sensor from ConfigEntry."""
    LOGGER.info(
        "luxtronik2.switch.async_setup_entry ConfigType: %s", config_entry)
    luxtronik: LuxtronikDevice = hass.data.get(DOMAIN)
    if not luxtronik:
        LOGGER.warning("switch.async_setup_entry no luxtronik!")
        return False

    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]
    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]

    # Build Sensor names with local language:
    lang = config_entry.options.get(CONF_LANGUAGE_SENSOR_NAMES)
    entities = []

    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    if deviceInfoHeating is not None:
        text_heating_mode = get_sensor_text(lang, 'heating_mode_auto')
        entities += [
            LuxtronikSwitch(on_state=LuxMode.automatic.value, off_state=LuxMode.off.value, hass=hass, luxtronik=luxtronik,
                            deviceInfo=deviceInfoHeating, sensor_key=LUX_SENSOR_MODE_HEATING, unique_id='heating',
                            name=text_heating_mode, icon='mdi:radiator', device_class=DEVICE_CLASS_HEAT)
        ]

    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    if deviceInfoDomesticWater is not None:
        text_domestic_water_mode_auto = get_sensor_text(
            lang, 'domestic_water_mode_auto')
        entities += [
            LuxtronikSwitch(on_state=LuxMode.automatic.value, off_state=LuxMode.off.value, hass=hass, luxtronik=luxtronik,
                            deviceInfo=deviceInfoDomesticWater, sensor_key=LUX_SENSOR_MODE_DOMESTIC_WATER, unique_id='domestic_water',
                            name=text_domestic_water_mode_auto, icon='mdi:water-boiler', device_class=DEVICE_CLASS_HEAT)
        ]

    async_add_entities(entities)
# endregion Setup


class LuxtronikSwitch(LuxtronikBinarySensor, SwitchEntity):
    """Representation of a Luxtronik switch."""

    def __init__(
        self,
        on_state: str = True,
        off_state: str = False,
        **kwargs: Any
    ) -> None:
        """Initialize a new Luxtronik switch."""
        super().__init__(**kwargs)
        self._on_state = on_state
        self._off_state = off_state

    @property
    def is_on(self):
        """Return true if switch is on."""
        value = self._luxtronik.get_value(self._sensor_key) == self._on_state
        return not value if self._invert else value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._luxtronik.write(self._sensor_key.split(
            '.')[1], self._on_state, debounce=False, update_immediately_after_write=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._luxtronik.write(self._sensor_key.split(
            '.')[1], self._off_state, debounce=False, update_immediately_after_write=True)

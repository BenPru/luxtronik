"""Support for Luxtronik heatpump binary states."""
# region Imports
import logging
from typing import Any, Final

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (DEVICE_CLASS_LOCK,
                                                    DEVICE_CLASS_RUNNING,
                                                    PLATFORM_SCHEMA,
                                                    BinarySensorEntity)
from homeassistant.components.sensor import (ENTITY_ID_FORMAT,
                                             STATE_CLASS_MEASUREMENT,
                                             SensorEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_FRIENDLY_NAME, CONF_ICON, CONF_ID,
                                 CONF_SENSORS)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import ENTITY_CATEGORIES, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from . import LuxtronikDevice
from .const import *
from .helpers.helper import get_sensor_text

# endregion Imports

# region Constants
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSORS): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_GROUP): vol.All(
                        cv.string,
                        vol.In(
                            [CONF_PARAMETERS, CONF_CALCULATIONS, CONF_VISIBILITIES]),
                    ),
                    vol.Required(CONF_ID): cv.string,
                    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
                    vol.Optional(CONF_ICON): cv.string,
                    vol.Optional(CONF_INVERT_STATE, default=False): cv.boolean,
                }
            ],
        )
    }
)
# endregion Constants

# region Setup


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities: AddEntitiesCallback, discovery_info: dict[str, Any] = None,
) -> None:
    """Set up a Luxtronik binary sensor from yaml config."""
    LOGGER.info(f"{DOMAIN}.binary_sensor.async_setup_platform ConfigType: %s - discovery_info: %s",
                config, discovery_info)
    luxtronik: LuxtronikDevice = hass.data.get(DOMAIN)
    if not luxtronik:
        LOGGER.warning("binary_sensor.async_setup_platform no luxtronik!")
        return False

    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]
    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]

    sensors = config.get(CONF_SENSORS)
    entities = []
    if sensors:
        # region Legacy part:
        for sensor_cfg in sensors:
            sensor_id = sensor_cfg[CONF_ID]
            if '.' in sensor_id:
                group = sensor_id.split('.')[0]
                sensor_id = sensor_id.split('.')[1]
            else:
                group = sensor_cfg[CONF_GROUP]
            sensor = luxtronik.get_sensor(group, sensor_id)
            if sensor:
                name = sensor.name if not sensor_cfg.get(
                    CONF_FRIENDLY_NAME) else sensor_cfg.get(CONF_FRIENDLY_NAME)
                entities += [
                    LuxtronikBinarySensor(hass, luxtronik, deviceInfo=deviceInfo, sensor_key=f"{group}.{sensor_id}",
                                          unique_id=sensor_id, name=name, icon=sensor_cfg.get(CONF_ICON), device_class=DEVICE_CLASSES.get(
                                              sensor.measurement_type, DEFAULT_DEVICE_CLASS),
                                          state_class=None, invert_state=sensor_cfg.get(CONF_INVERT_STATE))
                ]
            else:
                LOGGER.warning(
                    "Invalid Luxtronik ID %s in group %s",
                    sensor_id,
                    group,
                )
        # endregion Legacy part:

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Luxtronik sensor from ConfigEntry."""
    LOGGER.info(
        f"{DOMAIN}.binary_sensor.async_setup_entry ConfigType: %s", config_entry)
    luxtronik: LuxtronikDevice = hass.data.get(DOMAIN)
    if not luxtronik:
        LOGGER.warning("binary_sensor.async_setup_entry no luxtronik!")
        return False

    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]
    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]

    # Build Sensor names with local language:
    lang = config_entry.options.get(CONF_LANGUAGE_SENSOR_NAMES)
    text_evu_unlocked = get_sensor_text(lang, 'evu_unlocked')
    entities = [
        LuxtronikBinarySensor(hass=hass, luxtronik=luxtronik, deviceInfo=deviceInfo, sensor_key=LUX_BINARY_SENSOR_EVU_UNLOCKED,
                              unique_id='evu_unlocked', name=text_evu_unlocked, icon='mdi:lock',
                              device_class=DEVICE_CLASS_LOCK)
    ]

    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    if deviceInfoDomesticWater is not None:
        text_solar_pump = get_sensor_text(lang, 'solar_pump')
        entities += [
            LuxtronikBinarySensor(hass=hass, luxtronik=luxtronik, deviceInfo=deviceInfoDomesticWater, sensor_key=LUX_BINARY_SENSOR_SOLAR_PUMP,
                                  unique_id='solar_pump', name=text_solar_pump, icon='mdi:pump',
                                  device_class=DEVICE_CLASS_RUNNING)
        ]

    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]
    if deviceInfoCooling is not None:
        text_approval_cooling = get_sensor_text(lang, 'approval_cooling')
        entities += [
            LuxtronikBinarySensor(hass=hass, luxtronik=luxtronik, deviceInfo=deviceInfoCooling, sensor_key='calculations.ID_WEB_FreigabKuehl',
                                  unique_id='approval_cooling', name=text_approval_cooling, icon='mdi:lock',
                                  device_class=DEVICE_CLASS_LOCK)
        ]

    async_add_entities(entities)
# endregion Setup


class LuxtronikBinarySensor(BinarySensorEntity):
    """Representation of a Luxtronik binary sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        luxtronik: LuxtronikDevice,
        deviceInfo: DeviceInfo,
        sensor_key: str,
        unique_id: str,
        name: str,
        icon: str,
        device_class: str,
        state_class: str = None,
        entity_category: ENTITY_CATEGORIES = None,
        invert_state: bool = False
    ) -> None:
        """Initialize a new Luxtronik binary sensor."""
        self.hass = hass
        self._luxtronik = luxtronik

        self._sensor_key = sensor_key
        self.entity_id = ENTITY_ID_FORMAT.format(f"{DOMAIN}_{unique_id}")
        self._attr_unique_id = self.entity_id
        self._attr_device_info = deviceInfo
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category
        self._invert = invert_state

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        value = self._luxtronik.get_value(self._sensor_key)
        return not value if self._invert else value

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        self._luxtronik.update()

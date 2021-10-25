"""Luxtronik heatpump sensor."""
# region Imports
import logging
from typing import Any, Final

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_SENSORS, PRECISION_HALVES, DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_TIMESTAMP,
                                 PRECISION_TENTHS, TEMP_CELSIUS, TIME_SECONDS)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN as LUXTRONIK_DOMAIN
from . import LuxtronikDevice
from .const import *

# endregion Imports

# region Constants
# endregion Constants


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Luxtronik sensor from ConfigEntry."""
    luxtronik: LuxtronikDevice = hass.data.get(LUXTRONIK_DOMAIN)
    if not luxtronik:
        LOGGER.warning("sensor.async_setup_entry no luxtronik!")
        return False

    deviceInfo = DeviceInfo(
                identifiers={(LUXTRONIK_DOMAIN)},
                name='Luxtronik'
            )
    entities = [
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_WP_BZ_akt', 'status', 'Status', 'mdi:text-short', 'status', None, None),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeit', 'status time', 'Status Time', 'mdi:timer-sand', DEVICE_CLASS_TIMESTAMP, 'status_time', TIME_SECONDS),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile1', 'status line 1', 'Status Line 1', 'numeric-1-circle', 'status_line_1', None, None),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile2', 'status line 2', 'Status Line 2', 'numeric-2-circle', 'status_line_2', None, None),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile3', 'status line 3', 'Status Line 3', 'numeric-3-circle', 'status_line_3', None, None),

        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TVL', 'flow in temperature', 'Flow In Temperature', 'mdi:waves-arrow-left'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TRL', 'flow out temperature', 'Flow Out Temperature', 'mdi:waves-arrow-right'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Sollwert_TRL_HZ', 'flow out temperature target', 'Flow Out Temperature Target'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TWA', 'output temperature', 'Output Temperature'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TA', 'outdoor temperature', 'Outdoor Temperature',),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Mitteltemperatur', 'average outdoor temperature', 'Average Outdoor Temperature'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TSK', 'solar collector temperature', 'Solar Collector Temperature', 'mdi:solar-panel-large'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TSS', 'solar buffer temperature', 'Solar Buffer Temperature', 'mdi:propane-tank-outline')
    ]

    async_add_entities(entities)

class LuxtronikSensor(SensorEntity):
    """Representation of a Luxtronik Sensor."""
    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        luxtronik: LuxtronikDevice,
        deviceInfo: DeviceInfo,
        sensor_key: str,
        unique_id: str,
        name: str,
        icon: str = 'mdi:thermometer',
        device_class: str = DEVICE_CLASS_TEMPERATURE,
        state_class: str = STATE_CLASS_MEASUREMENT,
        unit_of_measurement: str = TEMP_CELSIUS,
    ) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._luxtronik = luxtronik
        self._attr_device_class = device_class
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._sensor_key = sensor_key
        self._attr_state_class = state_class
        self._attr_unique_id = f"{LUXTRONIK_DOMAIN}_{unique_id}"

        self._attr_device_info = deviceInfo

        # status = self._luxtronik.get_value(self._status_sensor)

        # self._luxtronik.write(
        #     self._target_temperature_sensor_write, self._attr_target_temperature, True)

    @property
    def native_value(self): # -> float | int | None:
        """Return the state of the sensor."""
        return self._luxtronik.get_value(self._sensor_key)

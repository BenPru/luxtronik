"""Luxtronik heatpump sensor."""
# region Imports
import logging
from typing import Any, Final

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_SENSORS, PRECISION_HALVES,
                                 PRECISION_TENTHS, TEMP_CELSIUS)
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
                name='Luxtronik',
            )
    entities = [
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_WP_BZ_akt', 'status', 'Status', 'status', 'mdi:text-short'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeit', 'status time', 'Status Time', 'status_time', 'mdi:timer-sand'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile1', 'status line 1', 'Status Line 1', 'status_line_1', 'numeric-1-circle'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile2', 'status line 2', 'Status Line 2', 'status_line_2', 'numeric-2-circle'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile3', 'status line 3', 'Status Line 3', 'status_line_3', 'numeric-3-circle'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TVL', 'flow in temperature', 'Flow In Temperature', 'flow_in_temperature', 'mdi:waves-arrow-left'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TRL', 'flow out temperature', 'Flow Out Temperature', 'flow_out_temperature', 'mdi:waves-arrow-right'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Sollwert_TRL_HZ', 'flow out target temperature', 'Flow Out Target Temperature', 'flow_out_target_temperature', 'mdi:temperature'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TWA', 'output temperature', 'Output Temperature', 'output_temperature', 'mdi:temperature'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TA', 'outdoor temperature', 'Outdoor Temperature', 'outdoor_temperature', 'mdi:home-thermometer'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Mitteltemperatur', 'average outdoor temperature', 'Average Outdoor Temperature', 'average_outdoor_temperature', 'mdi:temperature'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TSK', 'solar collector temperature', 'Solar collector Temperature', 'solar_collector_temperature', 'mdi:solar-panel-large'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TSS', 'solar buffer temperature', 'Solar Buffer Temperature', 'solar_buffer_temperature', 'mdi:propane-tank-outline')
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
        device_class: str,
        icon: str,
        state_class: str = None,
        unit_of_measurement: str = None,
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

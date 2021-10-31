"""Luxtronik heatpump sensor."""
# region Imports
import logging
from typing import Any, Final

from homeassistant.components.sensor import (ENTITY_ID_FORMAT,
                                             STATE_CLASS_MEASUREMENT,
                                             SensorEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_SENSORS, DEVICE_CLASS_TEMPERATURE,
                                 DEVICE_CLASS_TIMESTAMP, PRECISION_HALVES,
                                 PRECISION_TENTHS, TEMP_CELSIUS, TIME_SECONDS)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN as LUXTRONIK_DOMAIN
from . import LuxtronikDevice
from .const import *

# endregion Imports

# region Constants
# endregion Constants

# EVU active
# ID_WEB_EVUin


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities: AddEntitiesCallback, discovery_info: dict[str, Any] = None,
) -> None:
    luxtronik: LuxtronikDevice = hass.data.get(LUXTRONIK_DOMAIN)
    if not luxtronik:
        LOGGER.warning("sensor.async_setup_platform no luxtronik!")
        return False

    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]
    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    entities = [
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_WP_BZ_akt',
                        'status', 'Status', 'mdi:text-short', 'status', None, None),
        # LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_WP_BZ_akt',
        #                 'status', 'Status', LUX_STATE_ICON_MAP, 'status', None, None),  # 'mdi:text-short'
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeit', 'status_time',
                        'Status Time', 'mdi:timer-sand', DEVICE_CLASS_TIMESTAMP, 'status_time', TIME_SECONDS),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile1',
                        'status_line_1', 'Status Line 1', 'mdi:numeric-1-circle', 'status_line_1', None, None),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile2',
                        'status_line_2', 'Status Line 2', 'mdi:numeric-2-circle', 'status_line_2', None, None),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile3',
                        'status_line_3', 'Status Line 3', 'mdi:numeric-3-circle', 'status_line_3', None, None),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TWA',
                        'output_temperature', 'Output Temperature'),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TA',
                        'outdoor_temperature', 'Outdoor Temperature',),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Mitteltemperatur',
                        'outdoor_temperature_average', 'Average Outdoor Temperature'),

        LuxtronikSensor(hass, luxtronik, deviceInfoHeating, 'calculations.ID_WEB_Temperatur_TVL',
                        'flow_in_temperature', 'Flow In Temperature', 'mdi:waves-arrow-left'),
        LuxtronikSensor(hass, luxtronik, deviceInfoHeating, 'calculations.ID_WEB_Temperatur_TRL',
                        'flow_out_temperature', 'Flow Out Temperature', 'mdi:waves-arrow-right'),
        LuxtronikSensor(hass, luxtronik, deviceInfoHeating, 'calculations.ID_WEB_Sollwert_TRL_HZ',
                        'flow_out_temperature_target', 'Flow Out Temperature Target'),
        LuxtronikSensor(hass, luxtronik, deviceInfoHeating, 'calculations.ID_WEB_Temperatur_TSK',
                        'solar_collector_temperature', 'Solar Collector Temperature', 'mdi:solar-panel-large'),
        LuxtronikSensor(hass, luxtronik, deviceInfoHeating, 'calculations.ID_WEB_Temperatur_TSS',
                        'solar_buffer_temperature', 'Solar Buffer Temperature', 'mdi:propane-tank-outline')
    ]
    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Luxtronik sensor from ConfigEntry."""
    await async_setup_platform(hass, {}, async_add_entities)


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
        self.hass = hass
        self._luxtronik = luxtronik

        self.entity_id = ENTITY_ID_FORMAT.format(
            f"{LUXTRONIK_DOMAIN}_{unique_id}")
        self._attr_unique_id = self.entity_id
        self._attr_device_class = device_class
        self._attr_name = name
        self._icon = icon
        # self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._sensor_key = sensor_key
        self._attr_state_class = state_class

        self._attr_device_info = deviceInfo

        # self._luxtronik.write(
        #     self._target_temperature_sensor_write, self._attr_target_temperature, True)

    @property
    def icon(self):  # -> str | None:
        """Return the icon to be used for this entity."""
        # if type(self._icon) is dict and not isinstance(self._icon, str):
        #     return self._icon[self.native_value()]
        return self._icon

    @property
    def native_value(self):  # -> float | int | None:
        """Return the state of the sensor."""
        return self._luxtronik.get_value(self._sensor_key)

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        self._luxtronik.update()

    # @callback
    # def _update_and_write_state(self, *_):
    #     """Update the sensor and write state."""
    #     self._update()
    #     self.async_write_ha_state()

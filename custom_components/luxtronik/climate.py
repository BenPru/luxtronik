"""Luxtronik heatpump climate thermostat."""
# region Imports
import logging
from typing import Any, Final

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (ATTR_HVAC_MODE,
                                                    CURRENT_HVAC_HEAT,
                                                    CURRENT_HVAC_IDLE,
                                                    CURRENT_HVAC_OFF,
                                                    HVAC_MODE_AUTO,
                                                    HVAC_MODE_HEAT,
                                                    HVAC_MODE_OFF, PRESET_AWAY,
                                                    PRESET_BOOST, PRESET_NONE,
                                                    SUPPORT_PRESET_MODE,
                                                    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.components.water_heater import ATTR_TEMPERATURE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_SENSORS, PRECISION_HALVES,
                                 PRECISION_TENTHS, TEMP_CELSIUS)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN as LUXTRONIK_DOMAIN
from . import LuxtronikDevice
from .const import *

# endregion Imports

# region Constants
SUPPORT_FLAGS: Final = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
OPERATION_LIST: Final = [HVAC_MODE_AUTO, HVAC_MODE_OFF]

MIN_TEMPERATURE: Final = 40
MAX_TEMPERATURE: Final = 48
# endregion Constants


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities: AddEntitiesCallback, discovery_info: dict[str, Any] = None,
) -> None:
    luxtronik: LuxtronikDevice = hass.data.get(LUXTRONIK_DOMAIN)
    if not luxtronik:
        LOGGER.warning("climate.async_setup_platform no luxtronik!")
        return False

    # build_device_info(luxtronik)
    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]
    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    entities = [
        LuxtronikDomesticWaterThermostat(
            hass, luxtronik, deviceInfoDomesticWater)
        # , LuxtronikHeatingThermostat(hass, luxtronik, deviceInfoHeating)
        ]

    if luxtronik.get_value(LUX_SENSOR_DETECT_COOLING):
        deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]
        entities.append(LuxtronikCoolingThermostat(
            hass, luxtronik, deviceInfoCooling))
    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Luxtronik thermostat from ConfigEntry."""
    LOGGER.info("climate.async_setup_entry entry: '%s'", entry)
    await async_setup_platform(hass, {}, async_add_entities)


# class LuxtronikThermostat(CoordinatorEntity, ClimateEntity):
class LuxtronikThermostat(ClimateEntity):
    """Representation of a Luxtronik Thermostat device."""

    _attr_target_temperature = None
    _attr_supported_features = SUPPORT_FLAGS
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_hvac_modes = OPERATION_LIST
    _attr_preset_modes = [PRESET_NONE,
                          PRESET_SECOND_HEATSOURCE, PRESET_BOOST, PRESET_AWAY]
    _attr_min_temp = MIN_TEMPERATURE
    _attr_max_temp = MAX_TEMPERATURE

    _status_sensor: Final = LUX_SENSOR_STATUS
    _current_temperature_sensor = None
    _target_temperature_sensor_write = None

    _heat_status = LUX_STATUS_HEATING

    def __init__(self, hass: HomeAssistant, luxtronik: LuxtronikDevice, deviceInfo: DeviceInfo):
        self._hass = hass
        self._luxtronik = luxtronik
        self._attr_device_info = deviceInfo
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"{LUXTRONIK_DOMAIN}_{self._attr_unique_id}")

    @property
    def hvac_action(self):
        """Return the current mode."""
        status = self._luxtronik.get_value(self._status_sensor)
        if status == self._heat_status:
            return CURRENT_HVAC_HEAT
        if status == HVAC_MODE_OFF:
            return CURRENT_HVAC_OFF
        return CURRENT_HVAC_IDLE

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        if self._current_temperature_sensor is None:
            return None
        elif self._current_temperature_sensor.startswith('sensor.'):
            return self._hass.states.get(self._current_temperature_sensor)
        return self._luxtronik.get_value(self._current_temperature_sensor)

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        if not self._target_temperature_sensor_write is None:
            self._attr_target_temperature = self._luxtronik.get_value(
                self._target_temperature_sensor)
        elif not self._target_temperature_sensor is None:
            self._attr_target_temperature = self._hass.states.get(
                self._target_temperature_sensor)
        return self._attr_target_temperature

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        # if kwargs.get(ATTR_HVAC_MODE) is not None:
        #     hvac_mode = kwargs[ATTR_HVAC_MODE]
        #     await self.async_set_hvac_mode(hvac_mode)
        # elif kwargs.get(ATTR_TEMPERATURE) is not None:
        self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
        if not self._target_temperature_sensor_write is None:
            self._luxtronik.write(
                self._target_temperature_sensor_write, self._attr_target_temperature, True)
        elif not self._target_temperature_sensor is None:
            self._hass.states.set(
                self._target_temperature_sensor, self._attr_target_temperature)

    @property
    def hvac_mode(self) -> str:
        """Return the current operation mode."""
        luxmode = self._luxtronik.get_value(self._heater_sensor)
        if luxmode == LUX_MODE_OFF:
            return HVAC_MODE_OFF
        return HVAC_MODE_AUTO

    def __get_luxmode(self, hvac_mode: str, preset_mode: str) -> str:
        if hvac_mode == HVAC_MODE_OFF:
            return LUX_MODE_OFF
        elif preset_mode == PRESET_AWAY:
            return LUX_MODE_HOLIDAYS
        elif preset_mode == PRESET_BOOST:
            return LUX_MODE_PARTY
        elif preset_mode == PRESET_SECOND_HEATSOURCE:
            return LUX_MODE_SECOND_HEATSOURCE
        elif hvac_mode == HVAC_MODE_AUTO:
            return LUX_MODE_AUTOMATIC
        return LUX_MODE_OFF


    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new operation mode."""
        self._luxtronik.write(self._heater_sensor.split('.')[1],
                              self.__get_luxmode(hvac_mode, self.preset_mode), True)

    @property
    def preset_mode(self): # -> str | None:
        """Return current preset mode."""
        luxmode = self._luxtronik.get_value(self._heater_sensor)
        if luxmode in [LUX_MODE_OFF, LUX_MODE_AUTOMATIC]:
            return PRESET_NONE
        if luxmode == LUX_MODE_SECOND_HEATSOURCE:
            return PRESET_SECOND_HEATSOURCE
        if luxmode == LUX_MODE_PARTY:
            return PRESET_BOOST
        if luxmode == LUX_MODE_HOLIDAYS:
            return PRESET_AWAY
        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        self._luxtronik.write(self._heater_sensor.split('.')[1],
                              self.__get_luxmode(self.hvac_mode, preset_mode), True)

    # @property
    # def extra_state_attributes(self) -> ClimateExtraAttributes:
    #     """Return the device specific state attributes."""
    #     attrs: ClimateExtraAttributes = {
    #         ATTR_STATE_BATTERY_LOW: self.device.battery_low,
    #         ATTR_STATE_DEVICE_LOCKED: self.device.device_lock,
    #         ATTR_STATE_LOCKED: self.device.lock,
    #     }

    #     # the following attributes are available since fritzos 7
    #     if self.device.battery_level is not None:
    #         attrs[ATTR_BATTERY_LEVEL] = self.device.battery_level
    #     if self.device.holiday_active is not None:
    #         attrs[ATTR_STATE_HOLIDAY_MODE] = self.device.holiday_active
    #     if self.device.summer_active is not None:
    #         attrs[ATTR_STATE_SUMMER_MODE] = self.device.summer_active
    #     if ATTR_STATE_WINDOW_OPEN is not None:
    #         attrs[ATTR_STATE_WINDOW_OPEN] = self.device.window_open

    #     return attrs

    # WP: luxtronik.Brauchwassermodus
    #  -> 'Automatic', 'Second heatsource', 'Party', 'Holidays', 'Off'
    # Automatic = HVAC_MODE_AUTO + PRESET_NONE
    # Off = HVAC_MODE_OFF + PRESET_NONE
    # Second heatsource = HVAC_MODE_AUTO + PRESET_SECOND_HEATSOURCE
    # Party = HVAC_MODE_AUTO + PRESET_BOOST
    # Holidays = HVAC_MODE_AUTO + PRESET_AWAY

    # hvac_action: idle, heat, off

    #  / HVAC_MODE_HEAT ?
    # Automatic, Off


class LuxtronikDomesticWaterThermostat(LuxtronikThermostat):
    _attr_unique_id: Final = 'domestic_water'
    _attr_name = "Domestic Water"
    _attr_icon = 'mdi:water-boiler'
    _attr_device_class: Final = f"{LUXTRONIK_DOMAIN}__{_attr_unique_id}"

    _attr_target_temperature_step = 2.5

    _current_temperature_sensor: Final = LUX_SENSOR_DOMESTIC_WATER_CURRENT_TEMPERATURE
    _target_temperature_sensor: Final = LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE
    _target_temperature_sensor_write: Final = LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE_WRITE
    _heater_sensor: Final = LUX_SENSOR_DOMESTIC_WATER_HEATER
    _heat_status: Final = LUX_STATUS_DOMESTIC_WATER


class LuxtronikHeatingThermostat(LuxtronikThermostat):
    _unique_id = 'heating'
    _name = "Heizung"
    _icon = 'mdi:radiator'
    _device_class = _unique_id

    _current_temperature_sensor = 'sensor.innentemperatur'
    _heater_sensor = 'parameters.ID_Ba_Hz_akt'


class LuxtronikHeatingCorrectionThermostat(LuxtronikThermostat):
    _unique_id = 'heating_temperature_correction'
    _name = "Heizung Temperatur Korrektur"
    _icon = 'mdi:thermometer'
    _device_class = _unique_id

    _current_temperature_sensor = 'sensor.innentemperatur'
    _heater_sensor = 'parameters.ID_Ba_Hz_akt'


class LuxtronikCoolingThermostat(LuxtronikThermostat):
    _unique_id = 'cooling'
    _name = "Kühlung"
    _icon = 'far:snowflake'
    _device_class = _unique_id

    _current_temperature_sensor = 'sensor.innentemperatur'
    _heater_sensor = 'calculations.ID_WEB_FreigabKuehl'
    _heat_status = 'cooling'

# def setup_platform(
#     hass: HomeAssistant,
#     config: ConfigType,
#     add_entities_callback: AddEntitiesCallback,
#     discovery_info # : dict[str, Any] | None = None,
# ) -> None:
#     """Set up the Luxtronik climate sensor."""
#     luxtronik: LuxtronikDevice = hass.data.get(LUXTRONIK_DOMAIN)
#     _LOGGER.info("Set up the Luxtronik climate sensor.")
#     if not luxtronik:
#         _LOGGER.warning("climate.setup_platform no luxtronik!")
#         return False

#     # input_boolean.brauchwasser
#     _LOGGER.info("climate.setup_platform 1")
#     heater_sensor = luxtronik.get_sensor("parameters", "ID_Ba_Bw_akt")

#     # luxtronik.brauchwasser_soll
#     target_sensor = luxtronik.get_sensor(
#         "calculations", "ID_WEB_Einst_BWS_akt")
#     _LOGGER.info("climate.setup_platform 2")
#     source_sensor = luxtronik.get_sensor(
#         "calculations", "ID_WEB_Temperatur_TBW")

#     sensors = config.get(CONF_SENSORS)
#     _LOGGER.info("climate.setup_platform 2")

#     entities = [LuxtronikThermostat(
#         luxtronik, 'calculations.ID_WEB_WP_BZ_akt', 'calculations.ID_WEB_Temperatur_TBW', 'calculations.ID_Einst_BWS_akt', 'parameters.ID_Ba_Bw_akt', 'hot water')]
#         # luxtronik, 'calculations.ID_WEB_WP_BZ_akt', 'calculations.ID_WEB_Temperatur_TBW', 'calculations.ID_WEB_Einst_BWS_akt', 'hot water')]
#     _LOGGER.info("climate.setup_platform 4")
#     # for sensor_cfg in sensors:
#     #     sensor = luxtronik.get_sensor(sensor_cfg[CONF_GROUP], sensor_cfg[CONF_ID])
#     #     if sensor:
#     #         entities.append(
#     #             LuxtronikBinarySensor(
#     #                 luxtronik,
#     #                 sensor,
#     #                 sensor_cfg.get(CONF_FRIENDLY_NAME),
#     #                 sensor_cfg.get(CONF_ICON),
#     #                 sensor_cfg.get(CONF_INVERT_STATE),
#     #             )
#     #         )
#     #     else:
#     #         _LOGGER.warning(
#     #             "Invalid Luxtronik ID %s in group %s",
#     #             sensor_cfg[CONF_ID],
#     #             sensor_cfg[CONF_GROUP],
#     #         )

#     _LOGGER.info("climate.setup_platform 5")
#     add_entities_callback(entities, True)
#     _LOGGER.info("climate.setup_platform 6")


# async def async_setup_entry(
#     hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
# ) -> None:
#     """Set up the Luxtronik thermostat from ConfigEntry."""
#     luxtronik = hass.data.get(LUXTRONIK_DOMAIN)
#     if not luxtronik:
#         return False

#     coordinator = hass.data[LUXTRONIK_DOMAIN][entry.entry_id][CONF_COORDINATOR]

#     async_add_entities(
#         [
#             LuxtronikThermostat(coordinator, ain)
#             for ain, device in coordinator.data.items()
#             if device.has_thermostat
#         ]
#     )


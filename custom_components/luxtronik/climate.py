"""Luxtronik heatpump climate thermostat."""
# region Imports
import logging
from typing import Any

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
from homeassistant.components.water_heater import ATTR_TEMPERATURE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SENSORS, PRECISION_HALVES, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN as LUXTRONIK_DOMAIN
from . import LuxtronikDevice
from .const import (CONF_COORDINATOR, LUX_MODE_AUTOMATIC, LUX_MODE_HOLIDAYS,
                    LUX_MODE_OFF, LUX_MODE_PARTY, LUX_MODE_SECOND_HEATSOURCE,
                    PRESET_SECOND_HEATSOURCE)

# endregion Imports

# region Constants
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
OPERATION_LIST = [HVAC_MODE_AUTO, HVAC_MODE_OFF]

MIN_TEMPERATURE = 40
MAX_TEMPERATURE = 48

_LOGGER = logging.getLogger(__name__)

# DomesticWater
# - id: ID_WEB_Temperatur_TBW
#   group: calculations
# endregion Constants


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Luxtronik thermostat from ConfigEntry."""
    _LOGGER.info("climate.async_setup_entry 1")
    # coordinator = hass.data[LUXTRONIK_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    luxtronik: LuxtronikDevice = hass.data.get(LUXTRONIK_DOMAIN)
    _LOGGER.info("climate.async_setup_entry 2")
    if not luxtronik:
        _LOGGER.warning("climate.async_setup_entry no luxtronik!")
        return False

    async_add_entities(
        [
            LuxtronikDomesticWaterThermostat(luxtronik)
            # FritzboxThermostat(coordinator, ain)
            # for ain, device in coordinator.data.items()
            # if device.has_thermostat
        ]
    )


# class LuxtronikThermostat(CoordinatorEntity, ClimateEntity):
class LuxtronikThermostat(ClimateEntity):
    """Representation of a Luxtronik Thermostat device."""

    _heater_sensor = 'parameters.ID_Ba_Bw_akt'

    def __init__(self, luxtronik: LuxtronikDevice):
        self._luxtronik = luxtronik
        # def set_hvac_mode(self, hvac_mode):
        #     """Set new target hvac mode."""

        # async def async_set_hvac_mode(self, hvac_mode):
        #     """Set new target hvac mode."""

    @property
    def name(self):
        """Name of the entity."""
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def icon(self):
        """Icon of the entity."""
        return self._icon

    @property
    def device_class(self):
        return self._device_class

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
        return self._luxtronik.get_value(self._current_temperature_sensor)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def precision(self) -> float:
        """Return precision 0.5."""
        return PRECISION_HALVES

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._luxtronik.get_value(self._target_temperature_sensor)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if kwargs.get(ATTR_HVAC_MODE) is not None:
            hvac_mode = kwargs[ATTR_HVAC_MODE]
            await self.async_set_hvac_mode(hvac_mode)
        elif kwargs.get(ATTR_TEMPERATURE) is not None:
            temperature = kwargs[ATTR_TEMPERATURE]
            self._luxtronik.write(self._target_temperature_sensor_write, temperature, False)

    @property
    def hvac_mode(self) -> str:
        """Return the current operation mode."""
        luxmode = self._luxtronik.get_value(self._heater_sensor)
        if luxmode == LUX_MODE_OFF:
            return HVAC_MODE_OFF
        return HVAC_MODE_AUTO

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

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available operation modes."""
        return OPERATION_LIST

    def __get_luxmode(self, hvac_mode: str, preset_mode: str) -> str:
        if preset_mode == PRESET_AWAY:
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
            self.__get_luxmode(hvac_mode, self.preset_mode), False)

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

    @property
    def preset_modes(self) -> list[str]:
        """Return supported preset modes."""
        return [PRESET_NONE, PRESET_SECOND_HEATSOURCE, PRESET_BOOST, PRESET_AWAY]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        self._luxtronik.write(self._heater_sensor.split('.')[1],
            self.__get_luxmode(self.hvac_mode, preset_mode), False)

    @property
    def min_temp(self) -> int:
        """Return the minimum temperature."""
        return MIN_TEMPERATURE

    @property
    def max_temp(self) -> int:
        """Return the maximum temperature."""
        return MAX_TEMPERATURE

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

class LuxtronikDomesticWaterThermostat(LuxtronikThermostat):
    _unique_id = 'domestic_water'
    _name = "Brauchwasser"
    _icon = 'mdi:water-boiler'
    _device_class = 'domestic_water'

    _status_sensor = 'calculations.ID_WEB_WP_BZ_akt'
    _current_temperature_sensor = 'calculations.ID_WEB_Temperatur_TBW'
    _target_temperature_sensor = 'calculations.ID_WEB_Einst_BWS_akt'
    _target_temperature_sensor_write = 'ID_Einst_BWS_akt'
    _heat_status = 'hot water'

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


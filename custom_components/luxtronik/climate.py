"""Luxtronik heatpump climate thermostat."""
# region Imports
import math
from typing import Any, Final

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (CURRENT_HVAC_COOL,
                                                    CURRENT_HVAC_HEAT,
                                                    CURRENT_HVAC_IDLE,
                                                    CURRENT_HVAC_OFF,
                                                    HVAC_MODE_AUTO,
                                                    HVAC_MODE_OFF, PRESET_AWAY,
                                                    PRESET_BOOST, PRESET_NONE,
                                                    SUPPORT_PRESET_MODE,
                                                    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.components.water_heater import ATTR_TEMPERATURE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import LuxtronikDevice
from .const import *
from .helpers.helper import get_sensor_text

# endregion Imports

# region Constants
SUPPORT_FLAGS: Final = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
OPERATION_LIST: Final = [HVAC_MODE_AUTO, HVAC_MODE_OFF]

MIN_TEMPERATURE: Final = 40
MAX_TEMPERATURE: Final = 48
# endregion Constants

# region Setup


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities: AddEntitiesCallback, discovery_info: dict[str, Any] = None,
) -> None:
    pass


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Luxtronik thermostat from ConfigEntry."""
    LOGGER.info("climate.async_setup_entry entry: '%s'", config_entry)
    control_mode_home_assistant = config_entry.options.get(
        CONF_CONTROL_MODE_HOME_ASSISTANT)
    ha_sensor_indoor_temperature = config_entry.options.get(
        CONF_HA_SENSOR_INDOOR_TEMPERATURE)

    luxtronik: LuxtronikDevice = hass.data.get(DOMAIN)
    if not luxtronik:
        LOGGER.warning("climate.async_setup_platform no luxtronik!")
        return False

    # build_device_info(luxtronik)
    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]
    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]

    # Build Sensor names with local language:
    lang = config_entry.options.get(CONF_LANGUAGE_SENSOR_NAMES)
    text_domestic_water = get_sensor_text(lang, 'domestic_water')
    text_heating = get_sensor_text(lang, 'heating')
    entities = [
        LuxtronikDomesticWaterThermostat(
            hass, luxtronik, deviceInfoDomesticWater, name=text_domestic_water, control_mode_home_assistant=control_mode_home_assistant,
            current_temperature_sensor=LUX_SENSOR_DOMESTIC_WATER_CURRENT_TEMPERATURE),
        LuxtronikHeatingThermostat(
            hass, luxtronik, deviceInfoHeating, name=text_heating, control_mode_home_assistant=control_mode_home_assistant,
            current_temperature_sensor=ha_sensor_indoor_temperature)
    ]

    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]
    if deviceInfoCooling is not None:
        entities.append(LuxtronikCoolingThermostat(
            hass, luxtronik, deviceInfoCooling))
    async_add_entities(entities)
# endregion Setup


class LuxtronikThermostat(ClimateEntity, RestoreEntity):
    """Representation of a Luxtronik Thermostat device."""
    # region Properties / Init
    _active = False

    _attr_target_temperature = None
    _attr_current_temperature = None
    _attr_supported_features = SUPPORT_FLAGS
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_hvac_mode = HVAC_MODE_OFF
    _attr_hvac_modes = OPERATION_LIST
    _attr_hvac_action = CURRENT_HVAC_IDLE
    _attr_preset_mode = PRESET_NONE
    _attr_preset_modes = [PRESET_NONE,
                          PRESET_SECOND_HEATSOURCE, PRESET_BOOST, PRESET_AWAY]
    _attr_min_temp = MIN_TEMPERATURE
    _attr_max_temp = MAX_TEMPERATURE

    _status_sensor: Final = LUX_SENSOR_STATUS
    _target_temperature_sensor = None

    _heat_status = [LUX_STATUS_HEATING, LUX_STATUS_DOMESTIC_WATER]

    _cold_tolerance = DEFAULT_TOLERANCE
    _hot_tolerance = DEFAULT_TOLERANCE

    def __init__(self, hass: HomeAssistant, luxtronik: LuxtronikDevice, deviceInfo: DeviceInfo, name: str, control_mode_home_assistant: bool, current_temperature_sensor: str):
        self._hass = hass
        self._luxtronik = luxtronik
        self._attr_device_info = deviceInfo
        self._attr_name = name
        self._control_mode_home_assistant = control_mode_home_assistant
        self._current_temperature_sensor = current_temperature_sensor
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"{DOMAIN}_{self._attr_unique_id}")
    # endregion Properties / Init

    # region Temperatures

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        if self._current_temperature_sensor is None:
            self._attr_current_temperature = None
        elif self.__is_luxtronik_sensor(self._current_temperature_sensor):
            self._attr_current_temperature = self._luxtronik.get_value(
                self._current_temperature_sensor)
        else:
            current_temperature_sensor = self._hass.states.get(
                self._current_temperature_sensor)
            self._attr_current_temperature = None if current_temperature_sensor is None else float(
                current_temperature_sensor.state)
        return self._attr_current_temperature

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        if self._target_temperature_sensor is None:
            return self._attr_target_temperature
        elif self.__is_luxtronik_sensor(self._target_temperature_sensor):
            self._attr_target_temperature = self._luxtronik.get_value(
                self._target_temperature_sensor)
        else:
            self._attr_target_temperature = float(self._hass.states.get(
                self._target_temperature_sensor).state)
        return self._attr_target_temperature

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            cur_temp = float(state.state)
            if math.isnan(cur_temp) or math.isinf(cur_temp):
                raise ValueError(f"Sensor has illegal state {state.state}")
            self._attr_current_temperature = cur_temp
        except ValueError as ex:
            LOGGER.error("Unable to update from sensor: %s", ex)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
        if not self._target_temperature_sensor is None:
            self._luxtronik.write(self._target_temperature_sensor.split('.')[
                                  1], self._attr_target_temperature, debounce=False, update_immediately_after_write=True)
        await self._async_control_heating()
    # endregion Temperatures

    def _is_heating_on(self) -> bool:
        status = self._luxtronik.get_value(self._status_sensor)
        # region Workaround Luxtronik Bug: Status shows heating but status 3 = no request!
        if LUX_STATUS_HEATING in self._heat_status and status == LUX_STATUS_HEATING:
            status3 = self._luxtronik.get_value(LUX_SENSOR_STATUS3)
            LOGGER.info("climate._is_heating_on %s self._heat_status: %s status: %s status3: %s result: %s",
                        self._attr_unique_id, self._heat_status, status, status3, not status3 is None and not status3 in LUX_STATUS3_WORKAROUND)
            return not status3 is None and not status3 in [None, LUX_STATUS_UNKNOWN, LUX_STATUS_NONE, LUX_STATUS_NO_REQUEST]
        # endregion Workaround Luxtronik Bug: Status shows heating but status 3 = no request!
        return status in self._heat_status or status in [LUX_STATUS_DEFROST, LUX_STATUS_SWIMMING_POOL_SOLAR, LUX_STATUS_HEATING_EXTERNAL_SOURCE]

    @property
    def hvac_action(self):
        """Return the current mode."""
        new_hvac_action = self._attr_hvac_action
        status = self._luxtronik.get_value(self._status_sensor)
        if self._is_heating_on():
            new_hvac_action = CURRENT_HVAC_HEAT
        elif status == LUX_STATUS_COOLING:
            new_hvac_action = CURRENT_HVAC_COOL
        elif status in [LUX_STATUS_HEATING, LUX_STATUS_NO_REQUEST, LUX_STATUS_EVU] and self.__get_hvac_mode(CURRENT_HVAC_IDLE) != HVAC_MODE_OFF:
            new_hvac_action = CURRENT_HVAC_IDLE
        else:
            new_hvac_action = CURRENT_HVAC_OFF
        if new_hvac_action != self._attr_hvac_action:
            self._attr_hvac_action = new_hvac_action
            self._async_control_heating()
        LOGGER.info("climate.hvac_action %s hvac_action: %s",
                    self._attr_unique_id, new_hvac_action)
        return new_hvac_action

    async def _async_control_heating(self) -> bool:
        if not self._control_mode_home_assistant or self._attr_target_temperature is None or self._attr_current_temperature is None:  # Nothing Todo!
            LOGGER.info("climate._async_control_heating %s break!",
                        self._attr_unique_id)
            return False
        too_cold = self._attr_target_temperature >= self._attr_current_temperature + \
            self._cold_tolerance
        too_hot = self._attr_current_temperature >= self._attr_target_temperature + \
            self._hot_tolerance
        status = self._luxtronik.get_value(self._status_sensor)
        if too_hot and status != LUX_MODE_OFF and self._attr_hvac_action != CURRENT_HVAC_HEAT:
            # Turn off heating
            LOGGER.info(
                "climate._async_control_heating %s Turn OFF heating", self._attr_unique_id)
            self._luxtronik.write(self._heater_sensor.split(
                '.')[1], LUX_MODE_OFF, debounce=False, update_immediately_after_write=True)
        elif too_cold and status == LUX_MODE_OFF and self._attr_hvac_action == CURRENT_HVAC_HEAT:
            # Turn on heating
            LOGGER.info(
                "climate._async_control_heating %s Turn ON heating", self._attr_unique_id)
            self._luxtronik.write(self._heater_sensor.split(
                '.')[1], LUX_MODE_AUTOMATIC, debounce=False, update_immediately_after_write=True)
        else:
            LOGGER.info("climate._async_control_heating %s Nothing! too_hot: %s too_cold: %s status: %s _attr_hvac_action: %s",
                        self._attr_unique_id, too_hot, too_cold, status, self._attr_hvac_action)
            return False
        return True

    @property
    def hvac_mode(self) -> str:
        """Return the current operation mode."""
        self._attr_hvac_mode = self.__get_hvac_mode(self.hvac_action)
        return self._attr_hvac_mode

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new operation mode."""
        if self._attr_hvac_mode == hvac_mode:
            return
        LOGGER.info("climate.async_set_hvac_mode %s hvac_mode: %s",
                    self._attr_unique_id, hvac_mode)
        self._attr_hvac_mode = hvac_mode
        if not await self._async_control_heating():
            self._luxtronik.write(self._heater_sensor.split('.')[1],
                                  self.__get_luxmode(hvac_mode, self.preset_mode), debounce=False, update_immediately_after_write=True)

    def __get_hvac_mode(self, hvac_action):
        luxmode = self._luxtronik.get_value(self._heater_sensor)
        if luxmode in [LUX_MODE_HOLIDAYS, LUX_MODE_PARTY, LUX_MODE_SECOND_HEATSOURCE]:
            return self._attr_hvac_mode
        elif luxmode == LUX_MODE_OFF and self._control_mode_home_assistant and hvac_action == CURRENT_HVAC_IDLE:
            return self._attr_hvac_mode
        elif luxmode == LUX_MODE_OFF:
            return HVAC_MODE_OFF
        return HVAC_MODE_AUTO

    def __get_luxmode(self, hvac_mode: str, preset_mode: str) -> str:
        if hvac_mode == HVAC_MODE_OFF:
            return LUX_MODE_OFF
        # elif self._control_mode_home_assistant and self.hvac_action in [CURRENT_HVAC_OFF, CURRENT_HVAC_IDLE]:
        #     return LUX_MODE_OFF
        elif preset_mode == PRESET_AWAY:
            return LUX_MODE_HOLIDAYS
        elif preset_mode == PRESET_BOOST:
            return LUX_MODE_PARTY
        elif preset_mode == PRESET_SECOND_HEATSOURCE:
            return LUX_MODE_SECOND_HEATSOURCE
        elif hvac_mode == HVAC_MODE_AUTO:
            return LUX_MODE_AUTOMATIC
        return LUX_MODE_AUTOMATIC

    @property
    def preset_mode(self) -> str:  # | None:
        """Return current preset mode."""
        luxmode = self._luxtronik.get_value(self._heater_sensor)
        if luxmode == LUX_MODE_OFF and self._control_mode_home_assistant and self.hvac_action == CURRENT_HVAC_IDLE:
            return self._attr_preset_mode
        elif luxmode in [LUX_MODE_OFF, LUX_MODE_AUTOMATIC]:
            return PRESET_NONE
        elif luxmode == LUX_MODE_SECOND_HEATSOURCE:
            return PRESET_SECOND_HEATSOURCE
        elif luxmode == LUX_MODE_PARTY:
            return PRESET_BOOST
        elif luxmode == LUX_MODE_HOLIDAYS:
            return PRESET_AWAY
        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        self._attr_preset_mode = preset_mode
        self._luxtronik.write(self._heater_sensor.split('.')[1],
                              self.__get_luxmode(self.hvac_mode, preset_mode), debounce=False, update_immediately_after_write=True)

    # region Helper
    def __is_luxtronik_sensor(self, sensor: str) -> bool:
        return sensor.startswith(CONF_PARAMETERS + '.') or sensor.startswith(CONF_CALCULATIONS + '.') or sensor.startswith(CONF_VISIBILITIES + '.')

    async def _async_sensor_changed(self, event):
        """Handle temperature changes."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        self._async_update_temp(new_state)
        await self._async_control_heating()
        self.async_write_ha_state()
    # endregion Helper


class LuxtronikDomesticWaterThermostat(LuxtronikThermostat):
    _attr_unique_id: Final = 'domestic_water'
    _attr_icon = 'mdi:water-boiler'
    _attr_device_class: Final = f"{DOMAIN}__{_attr_unique_id}"

    _attr_target_temperature_step = 2.5

    _target_temperature_sensor: Final = LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE
    _heater_sensor: Final = LUX_SENSOR_MODE_DOMESTIC_WATER
    _heat_status: Final = [LUX_STATUS_DOMESTIC_WATER]


class LuxtronikHeatingThermostat(LuxtronikThermostat):
    _attr_unique_id = 'heating'
    _attr_icon = 'mdi:radiator'
    _attr_device_class: Final = f"{DOMAIN}__{_attr_unique_id}"

    _attr_target_temperature = 20.5
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 18.0
    _attr_max_temp = 23.0

    _heater_sensor: Final = LUX_SENSOR_MODE_HEATING

# class LuxtronikHeatingCorrectionThermostat(LuxtronikThermostat):
#     _unique_id = 'heating_temperature_correction'
#     _name = "Heizung Temperatur Korrektur"
#     _icon = 'mdi:thermometer'
#     _device_class = _unique_id

#     _current_temperature_sensor = 'sensor.innentemperatur'
#     _heater_sensor = 'parameters.ID_Ba_Hz_akt'


class LuxtronikCoolingThermostat(LuxtronikThermostat):
    _unique_id = 'cooling'
    _name = "Kühlung"
    _icon = 'far:snowflake'
    _device_class = _unique_id

    _heater_sensor = 'calculations.ID_WEB_FreigabKuehl'
    _heat_status = ['cooling']

# def setup_platform(
#     hass: HomeAssistant,
#     config: ConfigType,
#     add_entities_callback: AddEntitiesCallback,
#     discovery_info # : dict[str, Any] | None = None,
# ) -> None:
#     """Set up the Luxtronik climate sensor."""
#     luxtronik: LuxtronikDevice = hass.data.get(DOMAIN)
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
#     luxtronik = hass.data.get(DOMAIN)
#     if not luxtronik:
#         return False

#     coordinator = hass.data[DOMAIN][entry.entry_id][CONF_COORDINATOR]

#     async_add_entities(
#         [
#             LuxtronikThermostat(coordinator, ain)
#             for ain, device in coordinator.data.items()
#             if device.has_thermostat
#         ]
#     )

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
from homeassistant.const import ENTITY_CATEGORIES, STATE_UNAVAILABLE, STATE_UNKNOWN, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import LuxtronikDevice
from .const import (CONF_CALCULATIONS, CONF_CONTROL_MODE_HOME_ASSISTANT,
                    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
                    CONF_LANGUAGE_SENSOR_NAMES, CONF_PARAMETERS,
                    CONF_VISIBILITIES, DEFAULT_TOLERANCE, DOMAIN, LOGGER,
                    
                    LUX_SENSOR_DOMESTIC_WATER_CURRENT_TEMPERATURE,
                    LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE,
                    LUX_SENSOR_HEATING_TARGET_CORRECTION,
                    LUX_SENSOR_COOLING_TARGET,
                    LUX_SENSOR_COOLING_THRESHOLD,
                    LUX_SENSOR_OUTDOOR_TEMPERATURE,
                    
                    LUX_SENSOR_MODE_DOMESTIC_WATER,
                    LUX_SENSOR_MODE_HEATING,
                    LUX_SENSOR_MODE_COOLING,
                    
                    LUX_SENSOR_STATUS, LUX_SENSOR_STATUS1, LUX_SENSOR_STATUS3,
                    LUX_STATUS1_WORKAROUND, LUX_STATUS3_WORKAROUND,
                    LUX_STATUS_COOLING, LUX_STATUS_DEFROST,
                    LUX_STATUS_DOMESTIC_WATER,
                    LUX_STATUS_EVU,
                    LUX_STATUS_HEATING,
                    LUX_STATUS_HEATING_EXTERNAL_SOURCE,
                    LUX_STATUS_NO_REQUEST, LUX_STATUS_SWIMMING_POOL_SOLAR,
                    PRESET_SECOND_HEATSOURCE, PRESET_AUTO,
                    LuxMode)
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

    # Build Sensor names with local language:
    lang = config_entry.options.get(CONF_LANGUAGE_SENSOR_NAMES)
    entities = []

    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    if deviceInfoHeating is not None:
        text_heating = get_sensor_text(lang, 'heating')
        entities += [
            LuxtronikHeatingThermostat(
                hass, luxtronik, deviceInfoHeating, name=text_heating, control_mode_home_assistant=control_mode_home_assistant,
                current_temperature_sensor=ha_sensor_indoor_temperature, entity_category=None)
        ]

    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    if deviceInfoDomesticWater is not None:
        text_domestic_water = get_sensor_text(lang, 'domestic_water')
        entities += [
            LuxtronikDomesticWaterThermostat(
                hass, luxtronik, deviceInfoDomesticWater, name=text_domestic_water, control_mode_home_assistant=control_mode_home_assistant,
                current_temperature_sensor=LUX_SENSOR_DOMESTIC_WATER_CURRENT_TEMPERATURE, entity_category=None)
        ]

    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]
    if deviceInfoCooling is not None:
        text_cooling = get_sensor_text(lang, 'cooling')
        entities += [
            LuxtronikCoolingThermostat(
                hass, luxtronik, deviceInfoCooling, name=text_cooling, control_mode_home_assistant=control_mode_home_assistant,
                current_temperature_sensor=LUX_SENSOR_OUTDOOR_TEMPERATURE, entity_category=None)
        ]

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
    _target_temperature_sensor: str = None

    _heat_status = [LUX_STATUS_HEATING, LUX_STATUS_DOMESTIC_WATER, LUX_STATUS_COOLING]

    _cold_tolerance = DEFAULT_TOLERANCE
    _hot_tolerance = DEFAULT_TOLERANCE

    _last_lux_mode: LuxMode = None

    def __init__(self, hass: HomeAssistant, luxtronik: LuxtronikDevice, deviceInfo: DeviceInfo, name: str, control_mode_home_assistant: bool, current_temperature_sensor: str, entity_category: ENTITY_CATEGORIES = None):
        self._hass = hass
        self._luxtronik = luxtronik
        self._attr_device_info = deviceInfo
        self._attr_name = name
        self._control_mode_home_assistant = control_mode_home_assistant
        self._current_temperature_sensor = current_temperature_sensor
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"{DOMAIN}_{self._attr_unique_id}")
        self._attr_entity_category = entity_category
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
        changed = False
        self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
        if self._target_temperature_sensor is not None:
            self._luxtronik.write(self._target_temperature_sensor.split('.')[
                                  1], self._attr_target_temperature, use_debounce=False, update_immediately_after_write=True)
            changed = True
        if not await self._async_control_heating() and changed:
            self.schedule_update_ha_state(force_refresh=True)
    # endregion Temperatures

    def _is_heating_on(self) -> bool:
        status = self._luxtronik.get_value(self._status_sensor)
        # region Workaround Luxtronik Bug: Status shows heating but status 3 = no request!
        if status == LUX_STATUS_HEATING:
            status1 = self._luxtronik.get_value(LUX_SENSOR_STATUS1)
            status3 = self._luxtronik.get_value(LUX_SENSOR_STATUS3)
            if status1 in LUX_STATUS1_WORKAROUND and status3 in LUX_STATUS3_WORKAROUND:
                # pump forerun
                # 211123 LOGGER.info("climate._is_heating_on1 %s self._heat_status: %s status: %s status1: %s status3: %s result: %s",
                #             self._attr_unique_id, self._heat_status, status, status1, status3, False)
                return False
            # return not status3 is None and not status3 in [None, LUX_STATUS_UNKNOWN, LUX_STATUS_NONE, LUX_STATUS_NO_REQUEST]
            # 211123 LOGGER.info("climate._is_heating_on1 %s self._heat_status: %s status: %s status1: %s status3: %s result: %s",
            #             self._attr_unique_id, self._heat_status, status, status1, status3, LUX_STATUS_HEATING in self._heat_status)
            return LUX_STATUS_HEATING in self._heat_status
            # endregion Workaround Luxtronik Bug: Status shows heating but status 3 = no request!
        # 211123 LOGGER.info("climate._is_heating_on2 %s self._heat_status: %s status: %s result: %s",
        #             self._attr_unique_id, self._heat_status, status, status in self._heat_status or status in [LUX_STATUS_DEFROST, LUX_STATUS_SWIMMING_POOL_SOLAR, LUX_STATUS_HEATING_EXTERNAL_SOURCE])
        return status in self._heat_status or (status in [LUX_STATUS_DEFROST, LUX_STATUS_SWIMMING_POOL_SOLAR, LUX_STATUS_HEATING_EXTERNAL_SOURCE] and self._attr_hvac_mode != HVAC_MODE_OFF)

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
        LOGGER.info("climate.hvac_action %s status: %s hvac_action: %s",
                    self._attr_unique_id, status, new_hvac_action)
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
        if too_hot and status != LuxMode.off.value and self._attr_hvac_action != CURRENT_HVAC_HEAT:
            # Turn off heating
            LOGGER.info(
                "climate._async_control_heating %s Turn OFF heating", self._attr_unique_id)
            self._luxtronik.write(self._heater_sensor.split(
                '.')[1], LuxMode.off.value, use_debounce=False, update_immediately_after_write=True)
            self.schedule_update_ha_state(force_refresh=True)
        elif too_cold and status == LuxMode.off.value and self._attr_hvac_action == CURRENT_HVAC_HEAT:
            # Turn on heating
            LOGGER.info(
                "climate._async_control_heating %s Turn ON heating", self._attr_unique_id)
            self._luxtronik.write(self._heater_sensor.split(
                '.')[1], LuxMode.automatic.value, use_debounce=False, update_immediately_after_write=True)
            self.schedule_update_ha_state(force_refresh=True)
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
            self._last_lux_mode = self.__get_luxmode(
                hvac_mode, self.preset_mode)
            self._luxtronik.write(self._heater_sensor.split('.')[1],
                                  self._last_lux_mode.value, use_debounce=False, update_immediately_after_write=True)
            self.schedule_update_ha_state(force_refresh=True)

    def __get_hvac_mode(self, hvac_action):
        luxmode = LuxMode[self._luxtronik.get_value(
            self._heater_sensor).lower().replace(' ', '_')]
        if luxmode != self._last_lux_mode:
            self._last_lux_mode = luxmode
        if luxmode in [LuxMode.holidays, LuxMode.party, LuxMode.second_heatsource]:
            return self._attr_hvac_mode
        elif luxmode == LuxMode.off and self._control_mode_home_assistant and hvac_action == CURRENT_HVAC_IDLE:
            return self._attr_hvac_mode
        elif luxmode == LuxMode.off:
            return HVAC_MODE_OFF
        return HVAC_MODE_AUTO

    def __get_luxmode(self, hvac_mode: str, preset_mode: str) -> LuxMode:
        if hvac_mode == HVAC_MODE_OFF:
            return LuxMode.off
        # elif self._control_mode_home_assistant and self.hvac_action in [CURRENT_HVAC_OFF, CURRENT_HVAC_IDLE]:
        #     return LuxMode.off.value
        elif preset_mode == PRESET_AWAY:
            return LuxMode.holidays
        elif preset_mode == PRESET_BOOST:
            return LuxMode.party
        elif preset_mode == PRESET_SECOND_HEATSOURCE:
            return LuxMode.second_heatsource
        elif hvac_mode == HVAC_MODE_AUTO:
            return LuxMode.automatic
        return LuxMode.automatic

    @property
    def preset_mode(self) -> str:  # | None:
        """Return current preset mode."""
        luxmode = LuxMode[self._luxtronik.get_value(
            self._heater_sensor).lower().replace(' ', '_')]
        if luxmode == LuxMode.off and self._control_mode_home_assistant and self.hvac_action == CURRENT_HVAC_IDLE:
            return self._attr_preset_mode
        elif luxmode in [LuxMode.off, LuxMode.automatic]:
            return PRESET_NONE
        elif luxmode == LuxMode.second_heatsource:
            return PRESET_SECOND_HEATSOURCE
        elif luxmode == LuxMode.party:
            return PRESET_BOOST
        elif luxmode == LuxMode.holidays:
            return PRESET_AWAY
        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        self._attr_preset_mode = preset_mode
        self._last_lux_mode = self.__get_luxmode(self.hvac_mode, preset_mode)
        self._luxtronik.write(self._heater_sensor.split('.')[1],
                              self._last_lux_mode.value, use_debounce=False, update_immediately_after_write=True)
        self.schedule_update_ha_state(force_refresh=True)

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

    _attr_target_temperature_step = 1.0
    _attr_min_temp = 40.0
    _attr_max_temp = 58.0

    _target_temperature_sensor: Final = LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE
    _heater_sensor: Final = LUX_SENSOR_MODE_DOMESTIC_WATER
    _heat_status: Final = [LUX_STATUS_DOMESTIC_WATER]


class LuxtronikHeatingThermostat(LuxtronikThermostat):
    _attr_unique_id = 'heating'
    _attr_icon = 'mdi:radiator'
    _attr_device_class: Final = f"{DOMAIN}__{_attr_unique_id}"

    #_attr_target_temperature = 20.5
    _attr_target_temperature_step = 0.5
    _attr_min_temp = -5.0
    _attr_max_temp = +5.0

    _target_temperature_sensor: Final = LUX_SENSOR_HEATING_TARGET_CORRECTION
    _heater_sensor: Final = LUX_SENSOR_MODE_HEATING
    _heat_status: Final = [LUX_STATUS_HEATING]

class LuxtronikCoolingThermostat(LuxtronikThermostat):
    _attr_unique_id = 'cooling'
    _attr_icon = 'mdi:snowflake'
    _attr_device_class: Final = f"{DOMAIN}__{_attr_unique_id}"

    _target_temperature_sensor = LUX_SENSOR_COOLING_THRESHOLD
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 18.0
    _attr_max_temp = 30.0
    _attr_preset_modes = [PRESET_NONE]

    # _heater_sensor: Final = LUX_SENSOR_MODE_HEATING

# temperature setpoint for cooling
# parameters.ID_Sollwert_KuCft2_akt
# 20.0

# parameters.ID_Einst_Kuhl_Zeit_Ein_akt
# start cooling after this timeout
# 12.0

# parameters.ID_Einst_Kuhl_Zeit_Aus_akt
# stop cooling after this timeout
# 12.0
    _heater_sensor = LUX_SENSOR_MODE_COOLING
    _heat_status = [LUX_STATUS_COOLING]

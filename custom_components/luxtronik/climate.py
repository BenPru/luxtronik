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
from .const import (
    CONF_CALCULATIONS,
    CONF_CONTROL_MODE_HOME_ASSISTANT,
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_LANGUAGE_SENSOR_NAMES,
    CONF_PARAMETERS,
    CONF_VISIBILITIES,
    DEFAULT_TOLERANCE,
    DOMAIN,
    LOGGER,
    LUX_BINARY_SENSOR_DOMESTIC_WATER_RECIRCULATION_PUMP,
    LUX_BINARY_SENSOR_CIRCULATION_PUMP_HEATING,
    LUX_SENSOR_DOMESTIC_WATER_CURRENT_TEMPERATURE,
    LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE,
    LUX_SENSOR_HEATING_TARGET_CORRECTION,
    LUX_SENSOR_COOLING_THRESHOLD,
    LUX_SENSOR_OUTDOOR_TEMPERATURE,
    LUX_SENSOR_MODE_DOMESTIC_WATER,
    LUX_SENSOR_MODE_HEATING,
    LUX_SENSOR_MODE_COOLING,
    LUX_SENSOR_STATUS,
    LUX_SENSOR_STATUS1,
    LUX_SENSOR_STATUS3,
    LUX_STATUS1_WORKAROUND,
    LUX_STATUS3_WORKAROUND,
    LUX_STATUS_COOLING,
    LUX_STATUS_DEFROST,
    LUX_STATUS_DOMESTIC_WATER,
    LUX_STATUS_EVU,
    LUX_STATUS_HEATING,
    LUX_STATUS_HEATING_EXTERNAL_SOURCE,
    LUX_STATUS_NO_REQUEST,
    LUX_STATUS_SWIMMING_POOL_SOLAR,
    PRESET_SECOND_HEATSOURCE,
    LuxMode,
    )
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
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] = None,
) -> None:
    pass


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
    lang = hass.config.language
    entities = []

    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    if deviceInfoHeating is not None:
        text_heating = get_sensor_text(lang, 'heating')
        entities += [
            LuxtronikHeatingThermostat(
                luxtronik,
                deviceInfoHeating,
                name=text_heating,
                control_mode_home_assistant=control_mode_home_assistant,
                current_temperature_sensor=ha_sensor_indoor_temperature,
                entity_category=None,
            )
        ]

    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    if deviceInfoDomesticWater is not None:
        text_domestic_water = get_sensor_text(lang, 'domestic_water')
        entities += [
            LuxtronikDomesticWaterThermostat(
                luxtronik,
                deviceInfoDomesticWater,
                name=text_domestic_water,
                control_mode_home_assistant=control_mode_home_assistant,
                current_temperature_sensor=LUX_SENSOR_DOMESTIC_WATER_CURRENT_TEMPERATURE,
                entity_category=None,)
        ]

    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]
    if deviceInfoCooling is not None:
        text_cooling = get_sensor_text(lang, 'cooling')
        entities += [
            LuxtronikCoolingThermostat(
                luxtronik,
                deviceInfoCooling,
                name=text_cooling,
                control_mode_home_assistant=control_mode_home_assistant,
                current_temperature_sensor=LUX_SENSOR_OUTDOOR_TEMPERATURE,
                entity_category=None,
            )
        ]

    async_add_entities(entities)

# endregion Setup


class LuxtronikThermostat(ClimateEntity, RestoreEntity):
    """Representation of a Luxtronik Thermostat device."""
    # region Properties / Init
    _active = False

    _attr_target_temperature = None
    _attr_current_temperature = None
    _attr_current_target_correction = None
    _attr_supported_features = SUPPORT_FLAGS
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_hvac_mode = HVAC_MODE_OFF
    _attr_hvac_modes = OPERATION_LIST
    _attr_hvac_action = CURRENT_HVAC_IDLE
    _attr_preset_mode = PRESET_NONE
    _attr_preset_modes = [
        PRESET_NONE,
        PRESET_SECOND_HEATSOURCE,
        PRESET_BOOST,
        PRESET_AWAY,
    ]
    _attr_min_temp = MIN_TEMPERATURE
    _attr_max_temp = MAX_TEMPERATURE

    _status_sensor: Final = LUX_SENSOR_STATUS
    _target_temperature_sensor: str = None

    _heat_status = [LUX_STATUS_HEATING,
                    LUX_STATUS_DOMESTIC_WATER,
                    LUX_STATUS_COOLING]

    _last_lux_mode: LuxMode = None
    _last_hvac_action = None


    def __init__(
        self,
        luxtronik: LuxtronikDevice,
        deviceInfo: DeviceInfo,
        name: str,
        control_mode_home_assistant: bool,
        current_temperature_sensor: str,
        entity_category: ENTITY_CATEGORIES = None,
        ):
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
        # This routine runs every 60 seconds...     
        #LOGGER.info(f"{self}: def current_temperature")

        # Get the current temperature and update self._attr_current_temperature
        if self._current_temperature_sensor is None:
            self._attr_current_temperature = None
        elif self.__is_luxtronik_sensor(self._current_temperature_sensor):
            self._attr_current_temperature = self._luxtronik.get_value(
                self._current_temperature_sensor
            )
        else:
            current_temperature_sensor = self.hass.states.get(
                self._current_temperature_sensor
            )
            if (
                current_temperature_sensor is None
                or current_temperature_sensor.state is None
                or current_temperature_sensor.state == "unknown"
            ):
                self._attr_current_temperature = None
            else:
                self._attr_current_temperature = \
                    float(current_temperature_sensor.state)
        
        #LOGGER.info(f"self._current_temperature_sensor={self._current_temperature_sensor}")
        #LOGGER.info(f"self._attr_current_temperature={self._attr_current_temperature}")

        if self._control_mode_home_assistant == False:
            return self._attr_current_temperature

        # If Heating: (re-)calculate (and if needed:update) the target correction.
        if self._target_temperature_sensor == LUX_SENSOR_HEATING_TARGET_CORRECTION:
            new_target_correction = self.convert_target_temp_into_target_correction()

        return self._attr_current_temperature

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        # This routine runs every 60 seconds...
        #LOGGER.info(f"{self}: def target_temperature")
        
        # If no _target_temperature_sensor defined, do nothing
        if self._target_temperature_sensor is None:
            return self._attr_target_temperature

        # HEATING
        if self._target_temperature_sensor == LUX_SENSOR_HEATING_TARGET_CORRECTION:
        
            if self._control_mode_home_assistant == False:
                #LOGGER.info("self._control_mode_home_assistant == False:")
                self._attr_target_temperature = None
            
            # If HEATING, and _attr_target_temperature = None (on Startup), calculate target_temp
            elif (self._attr_target_temperature is None):
                # on startup, when value= None, set heating target_temp based on current correction value
                target_temp = self.convert_target_correction_into_target_temp()
                self._attr_target_temperature = target_temp
                
            # IF HEATING, and user changed the target_correction [-5;+5] value
            elif (self._attr_target_temperature is not None):
                # handle case where user changed correction value
                current_target_correction = self._luxtronik.get_value(
                    self._target_temperature_sensor
                )
                if self._attr_current_target_correction != current_target_correction:
                    target_temp = self.convert_target_correction_into_target_temp()
                    self._attr_target_temperature = target_temp
                
        # COOLING OR DOMESTIC WATER, and Luxtronik sensor
        elif self.__is_luxtronik_sensor(self._target_temperature_sensor):
            # cooling or domestic water, not heating
            self._attr_target_temperature = self._luxtronik.get_value(
                self._target_temperature_sensor
            )
            
        # COOLING OR DOMESTIC WATER, and NOT Luxtronik sensor
        else:
            # cooling or domestic water, not heating
            self._attr_target_temperature = float(
                self.hass.states.get(self._target_temperature_sensor).state
            )
            
        return self._attr_target_temperature

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        LOGGER.info("def _async_update_temp")
        try:
            cur_temp = float(state.state)
            if math.isnan(cur_temp) or math.isinf(cur_temp):
                raise ValueError(f"Sensor has illegal state {state.state}")
            if cur_temp != self._attr_current_temperature:
                self._attr_current_temperature = cur_temp
            else:
                LOGGER.info(f"Room temp unchanged ({cur_temp})")
        except ValueError as ex:
            LOGGER.error("Unable to update from sensor: %s", ex)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        LOGGER.info("def async_set_temperature")
        changed = False
        self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
        
        if self._target_temperature_sensor == LUX_SENSOR_HEATING_TARGET_CORRECTION:
            changed = False
        elif self._target_temperature_sensor is None:
            changed = False
        else:
            changed = True         

        if changed:
            LOGGER.info(f"Changed: {self._target_temperature_sensor.split('.')[1]}={self._attr_target_temperature}")
            self._luxtronik.write(
                self._target_temperature_sensor.split(".")[1],
                self._attr_target_temperature,
                use_debounce=False,
                update_immediately_after_write=True,
            )
            self.schedule_update_ha_state(force_refresh=True)

    def convert_target_correction_into_target_temp(self):
        room_temp = self._attr_current_temperature
        if (room_temp is  None): 
            return None
        if (room_temp > 25) | (room_temp < 12):
            LOGGER.info("=== BETA Luxtronik Thermostat ===")
            LOGGER.info(f"current room temperature: {room_temp} outside expected range [+12.0 ; +25.0] C.")
            LOGGER.info(f"--> Luxtronik Heating Thermostat disabled until this is resolved ")
            return None        
            
        LOGGER.info("=== BETA Luxtronik Thermostat ===")
        LOGGER.info("== Correction --> Target Temp  ==")

        # current_target_correction = self._luxtronik.get_value(
        #        self._target_temperature_sensor)
        current_target_correction = self._get_sensor_value(
            f"number.{DOMAIN}_heating_target_correction"
        )

        self._attr_current_target_correction = current_target_correction
        LOGGER.info(f"current correct: {current_target_correction}")
        if current_target_correction == None:
            return None
        else:
            influence_factor = 100.0
            LOGGER.info(f"influence_factor: {influence_factor}")
            deltaT = current_target_correction * (100.0 / influence_factor)
            LOGGER.info(f"current room temperature: {room_temp}")

            has_RBE = self._luxtronik.get_value("parameters.ID_Einst_RFVEinb_akt") != 0
            if has_RBE:
                LOGGER.info("RBE detected!")
                # RBE_target_temp = self._luxtronik.get_value("calculations.ID_WEB_RBE_RT_Soll")
                RBE_target_temp = self._get_sensor_value(
                    f"sensor.{DOMAIN}_room_target_temperature"
                )
                LOGGER.info(f"RBE_target_temp: {RBE_target_temp}")
                target_temp = round(RBE_target_temp + deltaT, 2)
            else:
                LOGGER.info("No RBE detected")
                target_temp = round(room_temp + deltaT, 2)

            LOGGER.info(
                f"based on current correction: {current_target_correction}, \
                  --> target room temperature: {target_temp}"
            )
            LOGGER.info("====================================")

            return target_temp

    def convert_target_temp_into_target_correction(self):
        #LOGGER.info(f"{self}: convert_target_temp_into_target_correction")
        if self._attr_current_temperature is None:
            return None
        if self._attr_target_temperature is None:
            return None
        room_temp = self._attr_current_temperature
        if (room_temp == None) | (room_temp > 25) | (room_temp < 12):
            LOGGER.info("=== BETA Luxtronik Thermostat ===")
            LOGGER.info(f"current room temperature: {room_temp} outside expected range [+12.0 ; +25.0] C.")
            LOGGER.info(f"--> Luxtronik Heating Thermostat disabled until this is resolved ")
            return None
            
        LOGGER.info("====================================")
        LOGGER.info("=== BETA Luxtronik Thermostat ===")
        LOGGER.info("== Target Temp --> Correction  ==")
        LOGGER.info(f"current room temperature: {room_temp}")
        target_temp = round(self._attr_target_temperature, 2)
        LOGGER.info(f"current target room temperature: {target_temp}")

        has_RBE = self._luxtronik.get_value("parameters.ID_Einst_RFVEinb_akt") != 0
        if has_RBE:
            LOGGER.info("RBE detected!")
            # RBE_target_temp = self._luxtronik.get_value("calculations.ID_WEB_RBE_RT_Soll")
            RBE_target_temp = self._get_sensor_value(
                f"sensor.{DOMAIN}_room_target_temperature"
            )
            LOGGER.info(f"RBE_target_temp: {RBE_target_temp}")
            deltaT = round(target_temp - RBE_target_temp, 2)
            LOGGER.info(f"current deltaT to T_RBEtarget: {deltaT}")
        else:
            LOGGER.info("No RBE detected")
            deltaT = round(target_temp - room_temp, 2)
            LOGGER.info(f"current deltaT to T_room: {deltaT}")
        
        influence_factor = 100.0
        LOGGER.info(f"influence_factor: {influence_factor}")
        new_target_correction = max(
            -5.0, min(+5.0, (influence_factor / 100.0) * deltaT)
        )
        LOGGER.info(f"new_target_correction: {new_target_correction}")

        # round target to nearest 0.5
        new_target_correction = round(new_target_correction * 2) / 2
        LOGGER.info(f"rounded new_target_correction: {new_target_correction}")

        ####################################################
        # Write target correction if value is changed
        ####################################################
        if (new_target_correction is not None):
            current_correction = self._attr_current_target_correction
            if new_target_correction != current_correction:
                LOGGER.info("Luxtronik TargetTemp correction needs to change!")
                LOGGER.info(f"old --> new: \
                              {current_correction} \
                              --> {new_target_correction} ")

                self._luxtronik.write(
                    self._target_temperature_sensor.split(".")[1],
                    new_target_correction,
                    use_debounce=False,
                    update_immediately_after_write=True,)
                    
                self.schedule_update_ha_state(force_refresh=True)    
            else:
                LOGGER.info(f"Luxtronik TargetTemp correction \
                              {self._attr_current_target_correction} \
                              can remain unchanged ")

            LOGGER.info("====================================")
        ####################################################

        self._attr_current_target_correction = new_target_correction

        return new_target_correction
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
        if status in self._heat_status or (status in [LUX_STATUS_SWIMMING_POOL_SOLAR, LUX_STATUS_HEATING_EXTERNAL_SOURCE] and self._attr_hvac_mode != HVAC_MODE_OFF):
            return True
        # if not result and status == LUX_STATUS_DEFROST and self._attr_hvac_mode != HVAC_MODE_OFF and self._last_status == self._heat_status:
        #     result = True
        return self._is__heating_on_special()

    def _is__heating_on_special(self) -> bool:
        return False

    @property
    def hvac_action(self):
        """Return the current mode."""
        new_hvac_action = self._attr_hvac_action
        status = self._luxtronik.get_value(self._status_sensor)
        if self._is_heating_on():
            new_hvac_action = CURRENT_HVAC_HEAT
        elif status == LUX_STATUS_COOLING:
            new_hvac_action = CURRENT_HVAC_COOL
        elif self.__get_hvac_mode(CURRENT_HVAC_IDLE) == HVAC_MODE_OFF:
            new_hvac_action = CURRENT_HVAC_OFF
        else:
            new_hvac_action = CURRENT_HVAC_IDLE
        if new_hvac_action != self._attr_hvac_action:
            self._attr_hvac_action = new_hvac_action
            
        if self._last_hvac_action != new_hvac_action:
            self._last_hvac_action = new_hvac_action
            LOGGER.info("climate.hvac_action changed %s status: %s hvac_action: %s",
                        self._attr_unique_id, status, new_hvac_action)
        return new_hvac_action

    @property
    def hvac_mode(self) -> str:
        """Return the current operation mode."""
        self._attr_hvac_mode = self.__get_hvac_mode(self.hvac_action)
        return self._attr_hvac_mode

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new operation mode."""
        if self._attr_hvac_mode == hvac_mode:
            return
        LOGGER.info(
            "climate.async_set_hvac_mode %s hvac_mode: %s",
            self._attr_unique_id,
            hvac_mode,
        )
        self._attr_hvac_mode = hvac_mode
        if not await self._async_control_heating():
            self._last_lux_mode = self.__get_luxmode(hvac_mode, self.preset_mode)
            self._luxtronik.write(
                self._heater_sensor.split(".")[1],
                self._last_lux_mode.value,
                use_debounce=False,
                update_immediately_after_write=True,
            )
            self.schedule_update_ha_state(force_refresh=True)

    def __get_hvac_mode(self, hvac_action):
        luxmode = LuxMode[
            self._luxtronik
            .get_value(self._heater_sensor)
            .lower().replace(" ", "_")]
        if luxmode != self._last_lux_mode:
            self._last_lux_mode = luxmode
        if luxmode in [LuxMode.holidays,
                       LuxMode.party,
                       LuxMode.second_heatsource]:
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
        luxmode = LuxMode[
            self._luxtronik.get_value(self._heater_sensor).lower().replace(" ", "_")
        ]
        if (
            luxmode == LuxMode.off
            and self._control_mode_home_assistant
            and self.hvac_action == CURRENT_HVAC_IDLE
        ):
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
        self._luxtronik.write(
            self._heater_sensor.split(".")[1],
            self._last_lux_mode.value,
            use_debounce=False,
            update_immediately_after_write=True,
        )
        self.schedule_update_ha_state(force_refresh=True)

    # region Helper
    def __is_luxtronik_sensor(self, sensor: str) -> bool:
        return (
            sensor.startswith(CONF_PARAMETERS + ".")
            or sensor.startswith(CONF_CALCULATIONS + ".")
            or sensor.startswith(CONF_VISIBILITIES + ".")
        )

    def _get_sensor_value(self, sensor_name: str) -> float:
        sensor = self.hass.states.get(sensor_name)
        if sensor is not None:
            return float(sensor.state)
        return None

    async def _async_sensor_changed(self, event):
        """Handle temperature changes."""
        new_state = event.data.get("new_state")
        LOGGER.info(f"_async_sensor_changed {event} --> {new_state}")
        if (new_state is None) or \
           (new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)):
            return

        self._async_update_temp(new_state)
        #await self._async_control_heating()
        #self.convert_target_correction_into_target_temp()
        self.async_write_ha_state()

    # endregion Helper


class LuxtronikDomesticWaterThermostat(LuxtronikThermostat):
    _attr_unique_id: Final = 'domestic_water'
    _attr_device_class: Final = f"{DOMAIN}__{_attr_unique_id}"

    _attr_target_temperature_step = 1.0
    _attr_min_temp = 40.0
    _attr_max_temp = 58.0

    _target_temperature_sensor: Final = LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE
    _heater_sensor: Final = LUX_SENSOR_MODE_DOMESTIC_WATER
    _heat_status: Final = [LUX_STATUS_DOMESTIC_WATER]

    @property
    def icon(self):  # -> str | None:
        result_icon = 'mdi:water-boiler'
        if self.hvac_mode == HVAC_MODE_OFF:
            result_icon += '-off'
        elif self.hvac_mode == HVAC_MODE_AUTO:
            result_icon += '-auto'
        return result_icon

    def _is__heating_on_special(self) -> bool:
        return self._luxtronik.get_value(self._status_sensor) == LUX_STATUS_DEFROST and self._attr_hvac_mode != HVAC_MODE_OFF and self._luxtronik.get_value(LUX_BINARY_SENSOR_DOMESTIC_WATER_RECIRCULATION_PUMP)


class LuxtronikHeatingThermostat(LuxtronikThermostat):
    _attr_unique_id = 'heating'
    _attr_device_class: Final = f"{DOMAIN}__{_attr_unique_id}"

    _attr_target_temperature = None
    _attr_target_temperature_step = 0.5
    _attr_min_temp = +15.0
    _attr_max_temp = +25.0

    _target_temperature_sensor: Final = LUX_SENSOR_HEATING_TARGET_CORRECTION

    _heater_sensor: Final = LUX_SENSOR_MODE_HEATING
    _heat_status: Final = [LUX_STATUS_HEATING]
    
    @property
    def icon(self):  # -> str | None:
        result_icon = 'mdi:radiator'
        if self.hvac_mode == HVAC_MODE_OFF:
            result_icon += '-off'
        return result_icon

    def _is__heating_on_special(self) -> bool:
        return self._luxtronik.get_value(self._status_sensor) in [LUX_STATUS_DEFROST] and self._attr_hvac_mode != HVAC_MODE_OFF and self._luxtronik.get_value(LUX_BINARY_SENSOR_CIRCULATION_PUMP_HEATING)

class LuxtronikCoolingThermostat(LuxtronikThermostat):
    _attr_unique_id = 'cooling'
    _attr_icon = 'mdi:snowflake'
    _attr_device_class: Final = f"{DOMAIN}__{_attr_unique_id}"

    _target_temperature_sensor = LUX_SENSOR_COOLING_THRESHOLD
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 18.0
    _attr_max_temp = 30.0
    _attr_preset_modes = [PRESET_NONE]

    _heater_sensor = LUX_SENSOR_MODE_COOLING
    _heat_status = [LUX_STATUS_COOLING]

"""Luxtronik heatpump number."""
# region Imports
from datetime import date, datetime
from typing import Any, Literal, cast

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import (ENTITY_ID_FORMAT,
                                             STATE_CLASS_MEASUREMENT)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (DEVICE_CLASS_TEMPERATURE, ENTITY_CATEGORIES,
                                 PERCENTAGE, TEMP_CELSIUS, TEMP_KELVIN,
                                 TIME_HOURS, TIME_MINUTES)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import LuxtronikDevice
from .const import (ATTR_EXTRA_STATE_ATTRIBUTE_LAST_THERMAL_DESINFECTION,
                    ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY,
                    CONF_LANGUAGE_SENSOR_NAMES, DOMAIN, LOGGER,
                    LUX_SENSOR_COOLING_START_DELAY,
                    LUX_SENSOR_COOLING_STOP_DELAY,
                    LUX_SENSOR_COOLING_THRESHOLD,
                    LUX_SENSOR_DOMESTIC_WATER_CURRENT_TEMPERATURE,
                    LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE,
                    LUX_SENSOR_HEATING_CIRCUIT_CURVE1_TEMPERATURE,
                    LUX_SENSOR_HEATING_CIRCUIT_CURVE2_TEMPERATURE,
                    LUX_SENSOR_HEATING_CIRCUIT_CURVE_NIGHT_TEMPERATURE,
                    LUX_SENSOR_HEATING_MAXIMUM_CIRCULATION_PUMP_SPEED,
                    LUX_SENSOR_HEATING_MIN_FLOW_OUT_TEMPERATURE,
                    LUX_SENSOR_HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR,
                    LUX_SENSOR_HEATING_TARGET_CORRECTION,
                    LUX_SENSOR_HEATING_THRESHOLD_TEMPERATURE,
                    LUX_SENSOR_PUMP_OPTIMIZATION_TIME)
from .helpers.helper import get_sensor_text

# endregion Imports

# region Constants
# endregion Constants

# region Setup


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] = None,
) -> None:
    pass


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Luxtronik number from ConfigEntry."""
    luxtronik: LuxtronikDevice = hass.data.get(DOMAIN)
    if not luxtronik:
        LOGGER.warning("number.async_setup_entry no luxtronik!")
        return False

    # Build Sensor names with local language:
    lang = hass.config.language
    text_temp = get_sensor_text(lang, 'temperature')

    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]
    entities = [
    ]
    if luxtronik.has_second_heat_generator or True:
        text_release_second_heat_generator = get_sensor_text(lang, 'release_second_heat_generator')
        entities = [
            LuxtronikNumber(
                luxtronik, deviceInfo,
                number_key='parameters.ID_Einst_ZWEFreig_akt',
                unique_id='release_second_heat_generator', name=text_release_second_heat_generator,
                icon='mdi:download-lock', unit_of_measurement=TEMP_CELSIUS, min_value=-20.0, max_value=20.0, step=0.1,
                mode=NumberMode.AUTO, entity_category=EntityCategory.CONFIG, factor=0.1),
            LuxtronikNumber(
                luxtronik, deviceInfo,
                number_key='parameters.ID_Einst_Freigabe_Zeit_ZWE',
                unique_id='release_time_second_heat_generator', name=text_release_second_heat_generator,
                icon='mdi:timer-play', unit_of_measurement=TIME_MINUTES, min_value=20, max_value=120, step=5,
                mode=NumberMode.AUTO, entity_category=EntityCategory.CONFIG, factor=1),
        ]

    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    if deviceInfoHeating is not None:
        text_heating_threshold = get_sensor_text(lang, 'heating_threshold')
        text_correction = get_sensor_text(lang, 'correction')
        text_pump_optimization_time = get_sensor_text(lang, 'pump_optimization_time')
        text_min_flow_out_temperature = get_sensor_text(lang, 'min_flow_out_temperature')
        text_heating_circuit_curve1_temperature = get_sensor_text(lang, 'circuit_curve1_temperature')
        text_heating_circuit_curve2_temperature = get_sensor_text(lang, 'circuit_curve2_temperature')
        text_heating_circuit_curve_night_temperature = get_sensor_text(lang, 'circuit_curve_night_temperature')
        text_heating_night_lowering_to_temperature = get_sensor_text(lang, 'heating_night_lowering_to_temperature')
        text_heating_hysteresis = get_sensor_text(lang, 'heating_hysteresis')
        text_heating_max_flow_out_increase_temperature = get_sensor_text(lang, 'heating_max_flow_out_increase_temperature')
        text_heating_maximum_circulation_pump_speed = get_sensor_text(lang, 'heating_maximum_circulation_pump_speed')
        entities += [
            LuxtronikNumber(
                luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_TARGET_CORRECTION,
                unique_id='heating_target_correction', name=f"{text_correction}",
                icon='mdi:plus-minus-variant', unit_of_measurement=TEMP_CELSIUS, min_value=-5.0, max_value=5.0, step=0.1, mode=NumberMode.BOX, entity_category=None),
            LuxtronikNumber(
                luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_PUMP_OPTIMIZATION_TIME,
                unique_id='pump_optimization_time', name=text_pump_optimization_time,
                icon='mdi:timer-settings', unit_of_measurement=TIME_MINUTES, min_value=5, max_value=180, step=5,
                mode=NumberMode.AUTO, entity_category=EntityCategory.CONFIG, factor=1),
            LuxtronikNumber(
                luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_THRESHOLD_TEMPERATURE,
                unique_id='heating_threshold_temperature', name=f"{text_heating_threshold}",
                icon='mdi:download-outline', unit_of_measurement=TEMP_CELSIUS, min_value=5.0, max_value=30.0, step=0.5, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
            LuxtronikNumber(
                luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_MIN_FLOW_OUT_TEMPERATURE,
                unique_id='heating_min_flow_out_temperature', name=f"{text_min_flow_out_temperature}",
                icon='mdi:waves-arrow-left', unit_of_measurement=TEMP_CELSIUS, min_value=5.0, max_value=30.0, step=0.5, factor=0.1, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
            LuxtronikNumber(
                luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_CIRCUIT_CURVE1_TEMPERATURE,
                unique_id='heating_circuit_curve1_temperature', name=f"{text_heating_circuit_curve1_temperature}",
                icon='mdi:chart-bell-curve', unit_of_measurement=TEMP_CELSIUS, min_value=20.0, max_value=70.0, step=0.5, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
            LuxtronikNumber(
                luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_CIRCUIT_CURVE2_TEMPERATURE,
                unique_id='heating_circuit_curve2_temperature', name=f"{text_heating_circuit_curve2_temperature}",
                icon='mdi:chart-bell-curve', unit_of_measurement=TEMP_CELSIUS, min_value=5.0, max_value=35.0, step=0.5, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
            LuxtronikNumber(
                luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_CIRCUIT_CURVE_NIGHT_TEMPERATURE,
                unique_id='heating_circuit_curve_night_temperature', name=f"{text_heating_circuit_curve_night_temperature}",
                icon='mdi:chart-bell-curve', unit_of_measurement=TEMP_CELSIUS, min_value=-15.0, max_value=10.0, step=0.5, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
            LuxtronikNumber(
                luxtronik, deviceInfoHeating,
                number_key='parameters.ID_Einst_TAbsMin_akt',
                unique_id='heating_night_lowering_to_temperature', name=f"{text_heating_night_lowering_to_temperature}",
                icon='mdi:thermometer-low', unit_of_measurement=TEMP_CELSIUS, min_value=-20.0, max_value=10.0, step=0.5, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG, factor=0.1),
            LuxtronikNumber(
                luxtronik, deviceInfoHeating,
                number_key='parameters.ID_Einst_HRHyst_akt',
                unique_id='heating_hysteresis', name=text_heating_hysteresis,
                icon='mdi:thermometer', unit_of_measurement=TEMP_KELVIN, min_value=0.5, max_value=6.0, step=0.1, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG, factor=0.1),
            LuxtronikNumber(
                luxtronik, deviceInfoHeating,
                number_key='parameters.ID_Einst_TRErhmax_akt',
                unique_id='heating_max_flow_out_increase_temperature', name=text_heating_max_flow_out_increase_temperature,
                icon='mdi:thermometer', unit_of_measurement=TEMP_KELVIN, min_value=1.0, max_value=7.0, step=0.1, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG, factor=0.1),
            LuxtronikNumber(
                luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_MAXIMUM_CIRCULATION_PUMP_SPEED,
                unique_id='heating_maximum_circulation_pump_speed', name=text_heating_maximum_circulation_pump_speed,
                icon='mdi:speedometer', unit_of_measurement=PERCENTAGE, min_value=0, max_value=100, step=10,
                mode=NumberMode.AUTO, entity_category=EntityCategory.CONFIG, entity_registry_enabled_default=False),
            # ID_Einst_HysHzExEn_akt TEE Heizung    2 1-15
            # ID_Einst_HysBwExEn_akt TEE Warmw.     5 1-15
            # T-Diff. Speicher max 70 20-95
            # T-Diff. Koll. max 110 90-120
        ]

        has_room_temp = luxtronik.get_value("parameters.ID_Einst_RFVEinb_akt") != 0
        if has_room_temp:
            text_heating_room_temperature_impact_factor = get_sensor_text(lang, 'heating_room_temperature_impact_factor')
            entities += [
                LuxtronikNumber(
                    luxtronik, deviceInfoHeating,
                    number_key=LUX_SENSOR_HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR,
                    unique_id='heating_room_temperature_impact_factor', name=f"{text_heating_room_temperature_impact_factor}",
                    icon='mdi:thermometer-chevron-up', unit_of_measurement=PERCENTAGE, min_value=0, max_value=200, step=10, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
            ]

    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    if deviceInfoDomesticWater is not None:
        text_target = get_sensor_text(lang, 'target')
        text_domestic_water = get_sensor_text(lang, 'domestic_water')
        text_thermal_desinfection = get_sensor_text(lang, 'thermal_desinfection')
        text_domestic_water_hysteresis = get_sensor_text(lang, 'domestic_water_hysteresis')
        entities += [
            LuxtronikNumber(
                luxtronik, deviceInfoDomesticWater,
                number_key=LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE,
                unique_id='domestic_water_target_temperature', name=f"{text_domestic_water} {text_target}",
                icon='mdi:thermometer-water', unit_of_measurement=TEMP_CELSIUS, min_value=40.0, max_value=60.0, step=1.0, mode=NumberMode.BOX),
            LuxtronikNumber(
                luxtronik, deviceInfoDomesticWater,
                number_key='parameters.ID_Einst_BWS_Hyst_akt',
                unique_id='domestic_water_hysteresis', name=text_domestic_water_hysteresis,
                icon='mdi:thermometer', unit_of_measurement=TEMP_KELVIN, min_value=1.0, max_value=30.0, step=0.1, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
            LuxtronikNumberThermalDesinfection(
                luxtronik, deviceInfoDomesticWater,
                number_key='parameters.ID_Einst_LGST_akt',
                unique_id='domestic_water_thermal_desinfection_target', name=f"{text_thermal_desinfection} {text_target} {text_domestic_water}",
                icon='mdi:thermometer-high', unit_of_measurement=TEMP_CELSIUS, min_value=50.0, max_value=70.0, step=1.0, mode=NumberMode.BOX, factor=0.1, entity_category=EntityCategory.CONFIG),
        ]

        solar_present = luxtronik.detect_solar_present()
        if solar_present:
            text_solar_pump_on_difference_temperature = get_sensor_text(lang, 'solar_pump_on_difference_temperature')
            text_solar_pump_off_difference_temperature = get_sensor_text(lang, 'solar_pump_off_difference_temperature')
            text_solar_pump_off_max_difference_temperature_boiler = get_sensor_text(lang, 'solar_pump_off_max_difference_temperature_boiler')
            text_solar_pump_max_temperature_collector = get_sensor_text(lang, 'solar_pump_max_temperature_collector')
            entities += [
                LuxtronikNumber(
                    luxtronik, deviceInfoDomesticWater,
                    number_key='parameters.ID_Einst_TDC_Ein_akt',
                    unique_id='solar_pump_on_difference_temperature', name=text_solar_pump_on_difference_temperature,
                    icon='mdi:pump', unit_of_measurement=TEMP_KELVIN, min_value=2.0, max_value=15.0, step=0.5,
                    mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
                LuxtronikNumber(
                    luxtronik, deviceInfoDomesticWater,
                    number_key='parameters.ID_Einst_TDC_Aus_akt',
                    unique_id='solar_pump_off_difference_temperature', name=text_solar_pump_off_difference_temperature,
                    icon='mdi:pump-off', unit_of_measurement=TEMP_KELVIN, min_value=0.5, max_value=10.0, step=0.5,
                    mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
                LuxtronikNumber(
                    luxtronik, deviceInfoDomesticWater,
                    number_key='parameters.ID_Einst_TDC_Max_akt',
                    unique_id='solar_pump_off_max_difference_temperature_boiler', name=text_solar_pump_off_max_difference_temperature_boiler,
                    icon='mdi:water-boiler-alert', unit_of_measurement=TEMP_CELSIUS, min_value=20, max_value=95, step=1,
                    mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
                LuxtronikNumber(
                    luxtronik, deviceInfoDomesticWater,
                    number_key='parameters.ID_Einst_TDC_Koll_Max_akt',
                    unique_id='solar_pump_max_temperature_collector', name=text_solar_pump_max_temperature_collector,
                    icon='mdi:solar-panel-large', unit_of_measurement=TEMP_CELSIUS, min_value=90, max_value=120, step=1,
                    mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
            ]

    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]
    if deviceInfoCooling is not None:
        text_cooling_threshold_temperature = get_sensor_text(
            lang, 'cooling_threshold_temperature')
        text_cooling_start_delay_hours = get_sensor_text(
            lang, 'cooling_start_delay_hours')
        text_cooling_stop_delay_hours = get_sensor_text(
            lang, 'cooling_stop_delay_hours')
        text_cooling_target_temperature = get_sensor_text(
            lang, 'cooling_target_temperature')
            
        entities += [
            LuxtronikNumber(luxtronik, deviceInfoCooling,
                            number_key=LUX_SENSOR_COOLING_THRESHOLD,
                            unique_id='cooling_threshold_temperature',
                            name=f"{text_cooling_threshold_temperature}",
                            icon='mdi:sun-thermometer',
                            unit_of_measurement=TEMP_CELSIUS,
                            min_value=18.0, max_value=30.0, step=0.5, mode=NumberMode.BOX),
            LuxtronikNumber(luxtronik, deviceInfoCooling,
                            number_key=LUX_SENSOR_COOLING_START_DELAY,
                            unique_id='cooling_start_delay_hours',
                            name=f"{text_cooling_start_delay_hours}",
                            icon='mdi:clock-start',
                            unit_of_measurement=TIME_HOURS,
                            min_value=0.0, max_value=12.0, step=0.5, mode=NumberMode.BOX),
            LuxtronikNumber(luxtronik, deviceInfoCooling,
                            number_key=LUX_SENSOR_COOLING_STOP_DELAY,
                            unique_id='cooling_stop_delay_hours',
                            name=f"{text_cooling_stop_delay_hours}",
                            icon='mdi:clock-end',
                            unit_of_measurement=TIME_HOURS,
                            min_value=0.0, max_value=12.0, step=0.5, mode=NumberMode.BOX),
        ]
        LUX_SENSOR_COOLING_TARGET = luxtronik.detect_cooling_target_temperature_sensor()
        entities += [
            LuxtronikNumber(luxtronik, deviceInfoCooling,
                number_key=LUX_SENSOR_COOLING_TARGET,
                unique_id='cooling_target_temperature',
                name=f"{text_cooling_target_temperature}",
                icon='mdi:snowflake-thermometer',
                unit_of_measurement=TEMP_CELSIUS,
                min_value=18.0, max_value=25.0, step=1.0, mode=NumberMode.BOX) 
        ] if LUX_SENSOR_COOLING_TARGET != None else []

    async_add_entities(entities)
# endregion Setup


class LuxtronikNumber(NumberEntity, RestoreEntity):
    """Representation of a Luxtronik number."""

    _use_value = None

    def __init__(
        self,
        luxtronik: LuxtronikDevice,
        deviceInfo: DeviceInfo,
        number_key: str,
        unique_id: str,
        name: str,
        icon: str = 'mdi:thermometer',
        device_class: str = DEVICE_CLASS_TEMPERATURE,
        state_class: str = STATE_CLASS_MEASUREMENT,
        unit_of_measurement: str = TEMP_CELSIUS,

        min_value: float = None,  # | None = None,
        max_value: float = None,  # | None = None,
        step: float = None,  # | None = None,
        mode: Literal["auto", "box", "slider"] = NumberMode.AUTO,
        entity_category: ENTITY_CATEGORIES = None,
        factor: float = None,
        entity_registry_enabled_default = True,
        # *args: Any,
        # **kwargs: Any
    ) -> None:
        """Initialize the number."""
        # super.__init__()
        # NumberEntity.__init__(*args, **kwargs)
        # super().__init__(*args)
        self._luxtronik = luxtronik
        self._number_key = number_key

        self.entity_id = ENTITY_ID_FORMAT.format(f"{DOMAIN}_{unique_id}")
        self._attr_unique_id = self.entity_id
        self._attr_device_class = device_class
        self._attr_name = name
        self._icon = icon
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_state_class = state_class

        self._attr_device_info = deviceInfo
        self._attr_mode = mode

        if min_value is not None:
            self._attr_native_min_value = min_value
        if max_value is not None:
            self._attr_native_max_value = max_value
        if step is not None:
            self._attr_native_step = step
        self._attr_entity_category = entity_category
        self._factor = factor
        self._attr_entity_registry_enabled_default = entity_registry_enabled_default
        self._attr_extra_state_attributes = { ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY: number_key }

    @property
    def icon(self):  # -> str | None:
        """Return the icon to be used for this entity."""
        return self._icon

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        self._use_value = None
        self._luxtronik.update()

    @property
    def native_value(self):
        """Return the current value."""
        if self._use_value is not None:
            return self._use_value
        value = self._luxtronik.get_value(self._number_key)
        if value is None:
            return None
        elif self._factor is None:
            return value
        return value * self._factor

#    @property
#    def value(self) -> float:
#        """Return the state of the entity."""
#        return self._luxtronik.get_value(self._number_key) * self._factor

    async def async_set_native_value(self, value):
        """Update the current value."""
        # self._use_value = value
        if self._factor is not None:
            value = int(value / self._factor)
        self._luxtronik.write(self._number_key.split('.')[1], value)
        # self.schedule_update_ha_state(force_refresh=True)
        self.async_write_ha_state()
        
#    def set_value(self, value: float) -> None:
#        """Update the current value."""
#        if self._factor != 1.0:
#            value = int(value / self._factor)
#        self._luxtronik.write(self._number_key.split('.')[1], value)
#        self.schedule_update_ha_state(force_refresh=True)

class LuxtronikNumberThermalDesinfection(LuxtronikNumber, RestoreEntity):
    _last_thermal_desinfection: datetime.date = None

    def __init__(self, *args, **kwargs):
        super(LuxtronikNumberThermalDesinfection, self).__init__(*args, **kwargs)
        default_timestamp: datetime = None
        self._attr_extra_state_attributes = {
            ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY: self._number_key,
            ATTR_EXTRA_STATE_ATTRIBUTE_LAST_THERMAL_DESINFECTION: default_timestamp
        }

    def update(self):
        LuxtronikNumber.update(self)
        domesticWaterCurrent = float(self._luxtronik.get_value(LUX_SENSOR_DOMESTIC_WATER_CURRENT_TEMPERATURE))
        if domesticWaterCurrent >= float(self.native_value) and (self._last_thermal_desinfection is None or self._last_thermal_desinfection == "" or (isinstance(self._last_thermal_desinfection, date) and cast(date, self._last_thermal_desinfection) < datetime.now().date())):
            self._last_thermal_desinfection = datetime.now().date
            self._attr_extra_state_attributes = {
                ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY: self._number_key,
                ATTR_EXTRA_STATE_ATTRIBUTE_LAST_THERMAL_DESINFECTION: datetime.now()
            }

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            return
        self._state = state.state

        if ATTR_EXTRA_STATE_ATTRIBUTE_LAST_THERMAL_DESINFECTION in state.attributes:
            self._last_thermal_desinfection = state.attributes[ATTR_EXTRA_STATE_ATTRIBUTE_LAST_THERMAL_DESINFECTION]
            self._attr_extra_state_attributes = {
                ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY: self._number_key,
                ATTR_EXTRA_STATE_ATTRIBUTE_LAST_THERMAL_DESINFECTION: self._last_thermal_desinfection
            }

        DATA_UPDATED = f"{DOMAIN}_data_updated"
        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

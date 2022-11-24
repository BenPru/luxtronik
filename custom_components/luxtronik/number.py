"""Luxtronik heatpump number."""
# region Imports
from typing import Any, Literal

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import (ENTITY_ID_FORMAT,
                                             STATE_CLASS_MEASUREMENT)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (DEVICE_CLASS_TEMPERATURE, ENTITY_CATEGORIES,
                                 PERCENTAGE, TEMP_CELSIUS, TIME_HOURS,
                                 TIME_MINUTES)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import LuxtronikDevice
from .const import (ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY,
                    CONF_LANGUAGE_SENSOR_NAMES, DOMAIN, LOGGER,
                    LUX_SENSOR_COOLING_START_DELAY,
                    LUX_SENSOR_COOLING_STOP_DELAY,
                    LUX_SENSOR_COOLING_THRESHOLD,
                    LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE,
                    LUX_SENSOR_HEATING_CIRCUIT_CURVE1_TEMPERATURE,
                    LUX_SENSOR_HEATING_CIRCUIT_CURVE2_TEMPERATURE,
                    LUX_SENSOR_HEATING_CIRCUIT_CURVE_NIGHT_TEMPERATURE,
                    LUX_SENSOR_HEATING_MIN_FLOW_OUT_TEMPERATURE,
                    LUX_SENSOR_HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR,
                    LUX_SENSOR_HEATING_TARGET_CORRECTION,
                    LUX_SENSOR_HEATING_THRESHOLD_TEMPERATURE,
                    LUX_SENSOR_MAXIMUM_CIRCULATION_PUMP_SPEED,
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
    lang = config_entry.options.get(CONF_LANGUAGE_SENSOR_NAMES)
    text_temp = get_sensor_text(lang, 'temperature')

    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]
    text_pump_optimization_time = get_sensor_text(lang, 'pump_optimization_time')
    text_maximum_circulation_pump_speed = get_sensor_text(lang, 'maximum_circulation_pump_speed')
    entities = [
        LuxtronikNumber(
            hass, luxtronik, deviceInfo,
            number_key=LUX_SENSOR_PUMP_OPTIMIZATION_TIME,
            unique_id='pump_optimization_time', name=f"{text_pump_optimization_time}",
            icon='mdi:timer-settings', unit_of_measurement=TIME_MINUTES, min_value=5, max_value=180, step=5, mode=NumberMode.AUTO, entity_category=EntityCategory.CONFIG),
        LuxtronikNumber(
            hass, luxtronik, deviceInfo,
            number_key=LUX_SENSOR_MAXIMUM_CIRCULATION_PUMP_SPEED,
            unique_id='maximum_circulation_pump_speed', name=f"{text_maximum_circulation_pump_speed}",
            icon='mdi:speedometer', unit_of_measurement=PERCENTAGE, min_value=0, max_value=100, step=10, mode=NumberMode.AUTO, entity_category=EntityCategory.CONFIG)
    ]

    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    if deviceInfoHeating is not None:
        text_heating_threshold = get_sensor_text(lang, 'heating_threshold')
        text_correction = get_sensor_text(lang, 'correction')
        text_min_flow_out_temperature = get_sensor_text(lang, 'min_flow_out_temperature')
        text_heating_circuit_curve1_temperature = get_sensor_text(lang, 'circuit_curve1_temperature')
        text_heating_circuit_curve2_temperature = get_sensor_text(lang, 'circuit_curve2_temperature')
        text_heating_circuit_curve_night_temperature = get_sensor_text(lang, 'circuit_curve_night_temperature')
        has_room_temp = luxtronik.get_value("parameters.ID_Einst_RFVEinb_akt") != 0
        entities += [
            LuxtronikNumber(
                hass, luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_TARGET_CORRECTION,
                unique_id='heating_target_correction', name=f"{text_correction}",
                icon='mdi:plus-minus-variant', unit_of_measurement=TEMP_CELSIUS, min_value=-2.0, max_value=2.0, step=0.1, mode=NumberMode.SLIDER, entity_category=None),
            LuxtronikNumber(
                hass, luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_THRESHOLD_TEMPERATURE,
                unique_id='heating_threshold_temperature', name=f"{text_heating_threshold}",
                icon='mdi:download-outline', unit_of_measurement=TEMP_CELSIUS, min_value=5.0, max_value=12.0, step=0.5, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
            LuxtronikNumber(
                hass, luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_MIN_FLOW_OUT_TEMPERATURE,
                unique_id='heating_min_flow_out_temperature', name=f"{text_min_flow_out_temperature}",
                icon='mdi:waves-arrow-left', unit_of_measurement=TEMP_CELSIUS, min_value=5.0, max_value=30.0, step=0.5, factor=0.1, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
            LuxtronikNumber(
                hass, luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_CIRCUIT_CURVE1_TEMPERATURE,
                unique_id='heating_circuit_curve1_temperature', name=f"{text_heating_circuit_curve1_temperature}",
                icon='mdi:chart-bell-curve', unit_of_measurement=TEMP_CELSIUS, min_value=20.0, max_value=70.0, step=0.5, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
            LuxtronikNumber(
                hass, luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_CIRCUIT_CURVE2_TEMPERATURE,
                unique_id='heating_circuit_curve2_temperature', name=f"{text_heating_circuit_curve2_temperature}",
                icon='mdi:chart-bell-curve', unit_of_measurement=TEMP_CELSIUS, min_value=5.0, max_value=35.0, step=0.5, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG),
            LuxtronikNumber(
                hass, luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_CIRCUIT_CURVE_NIGHT_TEMPERATURE,
                unique_id='heating_circuit_curve_night_temperature', name=f"{text_heating_circuit_curve_night_temperature}",
                icon='mdi:chart-bell-curve', unit_of_measurement=TEMP_CELSIUS, min_value=-15.0, max_value=10.0, step=0.5, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG)
        ]

        if has_room_temp:
            text_heating_room_temperature_impact_factor = get_sensor_text(lang, 'heating_room_temperature_impact_factor')
            entities += [
                    LuxtronikNumber(
                hass, luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR,
                unique_id='heating_room_temperature_impact_factor', name=f"{text_heating_room_temperature_impact_factor}",
                icon='mdi:thermometer-chevron-up', unit_of_measurement=PERCENTAGE, min_value=100, max_value=200, step=10, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG)
            ]

    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    if deviceInfoDomesticWater is not None:
        text_target = get_sensor_text(lang, 'target')
        text_domestic_water = get_sensor_text(lang, 'domestic_water')
        entities += [
            LuxtronikNumber(
                hass, luxtronik, deviceInfoDomesticWater,
                number_key=LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE,
                unique_id='domestic_water_target_temperature', name=f"{text_domestic_water} {text_target}",
                icon='mdi:water-boiler', unit_of_measurement=TEMP_CELSIUS, min_value=40.0, max_value=60.0, step=1.0, mode=NumberMode.BOX)
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
            LuxtronikNumber(hass, luxtronik, deviceInfoCooling,
                            number_key=LUX_SENSOR_COOLING_THRESHOLD,
                            unique_id='cooling_threshold_temperature',
                            name=f"{text_cooling_threshold_temperature}",
                            icon='mdi:sun-thermometer',
                            unit_of_measurement=TEMP_CELSIUS,
                            min_value=18.0, max_value=30.0, step=0.5, mode=NumberMode.BOX),
            LuxtronikNumber(hass, luxtronik, deviceInfoCooling,
                            number_key=LUX_SENSOR_COOLING_START_DELAY,
                            unique_id='cooling_start_delay_hours',
                            name=f"{text_cooling_start_delay_hours}",
                            icon='mdi:clock-start',
                            unit_of_measurement=TIME_HOURS,
                            min_value=0.0, max_value=12.0, step=0.5, mode=NumberMode.BOX),
            LuxtronikNumber(hass, luxtronik, deviceInfoCooling,
                            number_key=LUX_SENSOR_COOLING_STOP_DELAY,
                            unique_id='cooling_stop_delay_hours',
                            name=f"{text_cooling_stop_delay_hours}",
                            icon='mdi:clock-end',
                            unit_of_measurement=TIME_HOURS,
                            min_value=0.0, max_value=12.0, step=0.5, mode=NumberMode.BOX),
        ]
        LUX_SENSOR_COOLING_TARGET = luxtronik.detect_cooling_target_temperature_sensor()
        entities += [
                    LuxtronikNumber(hass, luxtronik, deviceInfoCooling,
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

    def __init__(
        self,
        hass: HomeAssistant,
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
        factor: float = 1.0,
    ) -> None:
        """Initialize the number."""
        self._hass = hass
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
        self._attr_extra_state_attributes = { ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY: number_key }

    @property
    def icon(self):  # -> str | None:
        """Return the icon to be used for this entity."""
        return self._icon

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        self._luxtronik.update()

    @property
    def native_value(self):
        """Return the current value."""
        return self._luxtronik.get_value(self._number_key) * self._factor

#    @property
#    def value(self) -> float:
#        """Return the state of the entity."""
#        return self._luxtronik.get_value(self._number_key) * self._factor

    async def async_set_native_value(self, value):
        """Update the current value."""
        if self._factor != 1.0:
            value = int(value / self._factor)
        self._luxtronik.write(self._number_key.split('.')[1], value)
        self.schedule_update_ha_state(force_refresh=True)

#    def set_value(self, value: float) -> None:
#        """Update the current value."""
#        if self._factor != 1.0:
#            value = int(value / self._factor)
#        self._luxtronik.write(self._number_key.split('.')[1], value)
#        self.schedule_update_ha_state(force_refresh=True)

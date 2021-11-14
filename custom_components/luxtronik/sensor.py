"""Luxtronik heatpump sensor."""
# region Imports
import logging
from typing import Any, Final

from homeassistant.components.sensor import (ENTITY_ID_FORMAT,
                                             STATE_CLASS_MEASUREMENT,
                                             STATE_CLASS_TOTAL_INCREASING,
                                             SensorEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_FRIENDLY_NAME, CONF_ICON, CONF_ID,
                                 CONF_SENSORS, DEVICE_CLASS_TEMPERATURE,
                                 DEVICE_CLASS_TIMESTAMP, ENERGY_KILO_WATT_HOUR,
                                 ENTITY_CATEGORY_CONFIG,
                                 ENTITY_CATEGORY_DIAGNOSTIC, STATE_ON,
                                 STATE_UNAVAILABLE, TEMP_CELSIUS, TIME_HOURS,
                                 TIME_SECONDS, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import (ENTITY_CATEGORIES, DeviceInfo,
                                          ToggleEntity)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN as LUXTRONIK_DOMAIN
from . import LuxtronikDevice
from .const import *
from .helpers.helper import get_sensor_text, get_sensor_value_text
from .model import LuxtronikStatusExtraAttributes

# endregion Imports

# region Constants
SECOUND_TO_HOUR_FACTOR: Final = 0.000277777777778
# endregion Constants

# EVU active
# ID_WEB_EVUin


# region Setup
async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities: AddEntitiesCallback, discovery_info: dict[str, Any] = None,
) -> None:
    """Set up a Luxtronik sensor from yaml config."""
    LOGGER.info(f"{DOMAIN}.sensor.async_setup_platform ConfigType: %s - discovery_info: %s",
                config, discovery_info)
    luxtronik: LuxtronikDevice = hass.data.get(LUXTRONIK_DOMAIN)
    if not luxtronik:
        LOGGER.warning("sensor.async_setup_platform no luxtronik!")
        return False

    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]
    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]

    sensors = config.get(CONF_SENSORS)
    entities = []
    if sensors:
        # region Legacy part:
        for sensor_cfg in sensors:
            sensor_id = sensor_cfg[CONF_ID]
            if '.' in sensor_id:
                group = sensor_id.split('.')[0]
                sensor_id = sensor_id.split('.')[1]
            else:
                group = sensor_cfg[CONF_GROUP]
            sensor = luxtronik.get_sensor(group, sensor_id)
            if sensor:
                name = sensor.name if not sensor_cfg.get(
                    CONF_FRIENDLY_NAME) else sensor_cfg.get(CONF_FRIENDLY_NAME)
                icon = ICONS.get(sensor.measurement_type) if not sensor_cfg.get(
                    CONF_ICON) else sensor_cfg.get(CONF_ICON)
                entities += [
                    LuxtronikSensor(hass, luxtronik, deviceInfo=deviceInfo, sensor_key=f"{group}.{sensor_id}",
                                    unique_id=sensor_id, name=name, icon=icon, device_class=DEVICE_CLASSES.get(
                                        sensor.measurement_type, DEFAULT_DEVICE_CLASS),
                                    state_class=None, unit_of_measurement=UNITS.get(sensor.measurement_type))
                ]
            else:
                LOGGER.warning(
                    "Invalid Luxtronik ID %s in group %s",
                    sensor_id,
                    group,
                )
        # endregion Legacy part:

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Luxtronik sensor from ConfigEntry."""
    LOGGER.info(
        f"{DOMAIN}.sensor.async_setup_entry ConfigType: %s", config_entry)
    luxtronik: LuxtronikDevice = hass.data.get(LUXTRONIK_DOMAIN)
    if not luxtronik:
        LOGGER.warning("sensor.async_setup_entry no luxtronik!")
        return False

    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]

    # Build Sensor names with local language:
    lang = config_entry.options.get(CONF_LANGUAGE_SENSOR_NAMES)
    hass.data[f"{DOMAIN}_language"] = lang
    text_time = get_sensor_text(lang, 'time')
    text_temp = get_sensor_text(lang, 'temperature')
    text_heat_source_output = get_sensor_text(lang, 'heat_source_output')
    text_heat_source_input = get_sensor_text(lang, 'heat_source_input')
    text_outdoor = get_sensor_text(lang, 'outdoor')
    text_average = get_sensor_text(lang, 'average')
    text_compressor_impulses = get_sensor_text(lang, 'compressor_impulses')
    text_operation_hours = get_sensor_text(lang, 'operation_hours')
    text_heat_amount_counter = get_sensor_text(lang, 'heat_amount_counter')
    entities = [
        # LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_WP_BZ_akt',
        #                 'status', 'Status', 'mdi:text-short', f"{DOMAIN}__status", None, None),
        LuxtronikStatusSensor(hass, luxtronik, deviceInfo, LUX_SENSOR_STATUS,
                              'status', 'Status', LUX_STATE_ICON_MAP, f"{DOMAIN}__status", None, None, entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
        # LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_WP_BZ_akt',
        #                 'status', 'Status', LUX_STATE_ICON_MAP, 'status', None, None),  # 'mdi:text-short'
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeit', 'status_time',
                        f"Status {text_time}", 'mdi:timer-sand', device_class=None, state_class=None, unit_of_measurement=TIME_SECONDS,
                        entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile1',
                        'status_line_1', 'Status 1', 'mdi:numeric-1-circle', f"{DOMAIN}__status_line_1", None, None, entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile2',
                        'status_line_2', 'Status 2', 'mdi:numeric-2-circle', f"{DOMAIN}__status_line_2", None, None, entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile3',
                        'status_line_3', 'Status 3', 'mdi:numeric-3-circle', f"{DOMAIN}__status_line_3", None, None, entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TWA',
                        'heat_source_output_temperature', f"{text_heat_source_output} {text_temp}", entity_category=None),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TWE',
                        'heat_source_input_temperature', f"{text_heat_source_input} {text_temp}", entity_category=None),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TA',
                        'outdoor_temperature', f"{text_outdoor} {text_temp}", entity_category=None),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Mitteltemperatur',
                        'outdoor_temperature_average', f"{text_average} {text_outdoor} {text_temp}", entity_category=None),

        LuxtronikSensor(hass, luxtronik, deviceInfo, sensor_key='calculations.ID_WEB_Zaehler_BetrZeitImpVD1',
                        unique_id='compressor_impulses', name=f"{text_compressor_impulses}",
                        icon='mdi:pulse', state_class=STATE_CLASS_TOTAL_INCREASING,
                        unit_of_measurement='Anzahl', entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
        LuxtronikSensor(hass, luxtronik, deviceInfo, sensor_key='calculations.ID_WEB_Zaehler_BetrZeitWP',
                        unique_id='operation_hours', name=f"{text_operation_hours}",
                        icon='mdi:timer-sand', state_class=STATE_CLASS_TOTAL_INCREASING,
                        unit_of_measurement=TIME_HOURS, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, factor=SECOUND_TO_HOUR_FACTOR),
        LuxtronikSensor(hass, luxtronik, deviceInfo, sensor_key='calculations.ID_WEB_WMZ_Seit',
                        unique_id='heat_amount_counter', name=f"{text_heat_amount_counter}",
                        icon='mdi:lightning-bolt-circle', state_class=STATE_CLASS_TOTAL_INCREASING,
                        unit_of_measurement=ENERGY_KILO_WATT_HOUR, entity_category=ENTITY_CATEGORY_DIAGNOSTIC)
    ]

    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    if deviceInfoHeating is not None:
        text_flow_in = get_sensor_text(lang, 'flow_in')
        text_flow_out = get_sensor_text(lang, 'flow_out')
        text_target = get_sensor_text(lang, 'target')
        text_operation_hours_heating = get_sensor_text(
            lang, 'operation_hours_heating')
        text_heat_amount_heating = get_sensor_text(lang, 'heat_amount_heating')
        entities += [
            LuxtronikSensor(hass, luxtronik, deviceInfoHeating, 'calculations.ID_WEB_Temperatur_TVL',
                            'flow_in_temperature', f"{text_flow_in} {text_temp}", 'mdi:waves-arrow-left', entity_category=None),
            LuxtronikSensor(hass, luxtronik, deviceInfoHeating, 'calculations.ID_WEB_Temperatur_TRL',
                            'flow_out_temperature', f"{text_flow_out} {text_temp}", 'mdi:waves-arrow-right', entity_category=None),
            LuxtronikSensor(hass, luxtronik, deviceInfoHeating, 'calculations.ID_WEB_Sollwert_TRL_HZ',
                            'flow_out_temperature_target', f"{text_flow_out} {text_temp} {text_target}", entity_category=None),

            LuxtronikSensor(hass, luxtronik, deviceInfoHeating, sensor_key='calculations.ID_WEB_Zaehler_BetrZeitHz',
                            unique_id='operation_hours_heating', name=f"{text_operation_hours_heating}",
                            icon='mdi:timer-sand', state_class=STATE_CLASS_TOTAL_INCREASING,
                            unit_of_measurement=TIME_HOURS, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, factor=SECOUND_TO_HOUR_FACTOR),
            LuxtronikSensor(hass, luxtronik, deviceInfoHeating, sensor_key='calculations.ID_WEB_WMZ_Heizung',
                            unique_id='heat_amount_heating', name=f"{text_heat_amount_heating}",
                            icon='mdi:lightning-bolt-circle', state_class=STATE_CLASS_TOTAL_INCREASING,
                            unit_of_measurement=ENERGY_KILO_WATT_HOUR, entity_category=ENTITY_CATEGORY_DIAGNOSTIC)
        ]

    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    if deviceInfoDomesticWater is not None:
        text_collector = get_sensor_text(lang, 'collector')
        text_buffer = get_sensor_text(lang, 'buffer')
        text_domestic_water = get_sensor_text(lang, 'domestic_water')
        text_operation_hours_domestic_water = get_sensor_text(
            lang, 'operation_hours_domestic_water')
        text_operation_hours_solar = get_sensor_text(
            lang, 'operation_hours_solar')
        text_heat_amount_domestic_water = get_sensor_text(
            lang, 'heat_amount_domestic_water')
        entities += [
            LuxtronikSensor(hass, luxtronik, deviceInfoDomesticWater, 'calculations.ID_WEB_Temperatur_TSK',
                            'solar_collector_temperature', f"Solar {text_collector} {text_temp}", 'mdi:solar-panel-large', entity_category=None),
            LuxtronikSensor(hass, luxtronik, deviceInfoDomesticWater, 'calculations.ID_WEB_Temperatur_TSS',
                            'solar_buffer_temperature', f"Solar {text_buffer} {text_temp}", 'mdi:propane-tank-outline', entity_category=None),
            LuxtronikSensor(hass, luxtronik, deviceInfoDomesticWater, 'calculations.ID_WEB_Temperatur_TBW',
                            'domestic_water_temperature', f"{text_domestic_water} {text_temp}", 'mdi:coolant-temperature', entity_category=None),

            LuxtronikSensor(hass, luxtronik, deviceInfoDomesticWater, sensor_key='calculations.ID_WEB_Zaehler_BetrZeitBW',
                            unique_id='operation_hours_domestic_water', name=f"{text_operation_hours_domestic_water}",
                            icon='mdi:timer-sand', state_class=STATE_CLASS_TOTAL_INCREASING,
                            unit_of_measurement=TIME_HOURS, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, factor=SECOUND_TO_HOUR_FACTOR),
            LuxtronikSensor(hass, luxtronik, deviceInfoDomesticWater, sensor_key='parameters.ID_BSTD_Solar',
                            unique_id='operation_hours_solar', name=f"{text_operation_hours_solar}",
                            icon='mdi:timer-sand', state_class=STATE_CLASS_TOTAL_INCREASING,
                            unit_of_measurement=TIME_HOURS, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, factor=SECOUND_TO_HOUR_FACTOR),
            LuxtronikSensor(hass, luxtronik, deviceInfoDomesticWater, sensor_key='calculations.ID_WEB_WMZ_Brauchwasser',
                            unique_id='heat_amount_domestic_water', name=f"{text_heat_amount_domestic_water}",
                            icon='mdi:lightning-bolt-circle', state_class=STATE_CLASS_TOTAL_INCREASING,
                            unit_of_measurement=ENERGY_KILO_WATT_HOUR, entity_category=ENTITY_CATEGORY_DIAGNOSTIC)
        ]

    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]
    if deviceInfoCooling is not None:
        text_operation_hours_cooling = get_sensor_text(
            lang, 'operation_hours_cooling')
        entities += [
            LuxtronikSensor(hass, luxtronik, deviceInfoCooling, sensor_key='calculations.ID_WEB_Zaehler_BetrZeitKue',
                            unique_id='operation_hours_cooling', name=f"{text_operation_hours_cooling}",
                            icon='mdi:timer-sand', state_class=STATE_CLASS_TOTAL_INCREASING,
                            unit_of_measurement=TIME_HOURS, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, factor=SECOUND_TO_HOUR_FACTOR)
        ]

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, luxtronik.async_will_remove_from_hass()
    )

    async_add_entities(entities)
# endregion Setup


class LuxtronikSensor(SensorEntity, RestoreEntity):
    """Representation of a Luxtronik Sensor."""
    _attr_is_on = True

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
        entity_category: ENTITY_CATEGORIES = None,
        factor: float = None,
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
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._sensor_key = sensor_key
        self._attr_state_class = state_class

        self._attr_device_info = deviceInfo
        self._attr_entity_category = entity_category
        self._factor = factor

    @property
    def icon(self):  # -> str | None:
        """Return the icon to be used for this entity."""
        if not self._icon is None and type(self._icon) is dict and not isinstance(self._icon, str):
            if self.native_value in self._icon:
                return self._icon[self.native_value]
            return None
        return self._icon

    @property
    def native_value(self):  # -> float | int | None:
        """Return the state of the sensor."""
        value = self._luxtronik.get_value(self._sensor_key)

        # region Workaround Luxtronik Bug: Status shows heating but status 3 = no request!
        if self._sensor_key == LUX_SENSOR_STATUS and value == LUX_STATUS_HEATING:
            status1 = self._luxtronik.get_value(LUX_SENSOR_STATUS1)
            status3 = self._luxtronik.get_value(LUX_SENSOR_STATUS3)
            if status1 in LUX_STATUS1_WORKAROUND and status3 in LUX_STATUS3_WORKAROUND:
                # pump forerun
                return LUX_STATUS_NO_REQUEST
        # endregion Workaround Luxtronik Bug: Status shows heating but status 3 = no request!

        return value if self._factor is None else round(value * self._factor, 2)

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return self.native_value in LUX_STATES_ON

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        self._luxtronik.update()

        if self._sensor_key == 'calculations.ID_WEB_HauptMenuStatus_Zeit':
            v = self.native_value
            if v is None:
                time_str = None
            else:
                m, s = divmod(int(v), 60)
                h, m = divmod(m, 60)
                time_str = '{:01.0f}:{:02.0f} h'.format(h, m)
            self._attr_extra_state_attributes = {
                ATTR_STATUS_TEXT: time_str
            }


class LuxtronikStatusSensor(LuxtronikSensor):
    @property
    def is_on(self) -> bool:  # | None:
        return self.native_value in LUX_STATES_ON

    def _get_sensor_value(self, sensor_name: str):
        sensor = self.hass.states.get(sensor_name)
        if not sensor is None:
            return sensor.state
        return None

    def _get_sensor_attr(self, sensor_name: str, attr: str):
        sensor = self.hass.states.get(sensor_name)
        if not sensor is None and attr in sensor.attributes:
            return sensor.attributes[attr]
        return None
    def _build_status_text(self) -> str:
        status_time = self._get_sensor_attr(
            f"sensor.{DOMAIN}_status_time", ATTR_STATUS_TEXT)
        l1 = self._get_sensor_value(f"sensor.{DOMAIN}_status_line_1")
        l2 = self._get_sensor_value(f"sensor.{DOMAIN}_status_line_2")
        if status_time is None or status_time == STATE_UNAVAILABLE or l1 is None or l1 == STATE_UNAVAILABLE or l2 is None or l2 == STATE_UNAVAILABLE:
            return ''
        lang = self.hass.data[f"{DOMAIN}_language"]
        l1 = get_sensor_value_text(lang, f"{DOMAIN}__status_line_1", l1)
        l2 = get_sensor_value_text(lang, f"{DOMAIN}__status_line_2", l2)
        return f"{l1} {l2} {status_time}."

    @property
    def extra_state_attributes(self) -> LuxtronikStatusExtraAttributes:
        """Return the state attributes of the device."""
        return {
            ATTR_STATUS_TEXT: self._build_status_text(),
        }

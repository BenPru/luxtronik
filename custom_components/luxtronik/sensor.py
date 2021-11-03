"""Luxtronik heatpump sensor."""
# region Imports
import logging
from typing import Any, Final

from homeassistant.components.sensor import (ENTITY_ID_FORMAT,
                                             STATE_CLASS_MEASUREMENT,
                                             SensorEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_FRIENDLY_NAME, CONF_ICON, CONF_ID,
                                 CONF_SENSORS, DEVICE_CLASS_TEMPERATURE,
                                 DEVICE_CLASS_TIMESTAMP, PRECISION_HALVES,
                                 PRECISION_TENTHS, STATE_UNAVAILABLE,
                                 TEMP_CELSIUS, TIME_SECONDS)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN as LUXTRONIK_DOMAIN
from . import LuxtronikDevice
from .const import *
from .helpers.helper import get_sensor_text
from .model import LuxtronikStatusExtraAttributes

# endregion Imports

# region Constants
# endregion Constants

# EVU active
# ID_WEB_EVUin


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities: AddEntitiesCallback, discovery_info: dict[str, Any] = None,
) -> None:
    """Set up a Luxtronik sensor from yaml config."""
    LOGGER.info("luxtronik2.sensor.async_setup_platform ConfigType: %s - discovery_info: %s",
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
                entities.append(
                    LuxtronikSensor(hass, luxtronik, deviceInfo=deviceInfo, sensor_key=f"{group}.{sensor_id}",
                                    unique_id=sensor_id, name=name, icon=icon, device_class=DEVICE_CLASSES.get(
                                        sensor.measurement_type, DEFAULT_DEVICE_CLASS),
                                    state_class=None, unit_of_measurement=UNITS.get(sensor.measurement_type))
                )
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
        "luxtronik2.sensor.async_setup_entry ConfigType: %s", config_entry)
    luxtronik: LuxtronikDevice = hass.data.get(LUXTRONIK_DOMAIN)
    if not luxtronik:
        LOGGER.warning("sensor.async_setup_entry no luxtronik!")
        return False

    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]
    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]

    # Build Sensor names with local language:
    lang = config_entry.options.get(CONF_LANGUAGE_SENSOR_NAMES)
    text_time = get_sensor_text(lang, 'time')
    text_temp = get_sensor_text(lang, 'temperature')
    text_output = get_sensor_text(lang, 'output')
    text_outdoor = get_sensor_text(lang, 'outdoor')
    text_average = get_sensor_text(lang, 'average')
    text_flow_in = get_sensor_text(lang, 'flow_in')
    text_flow_out = get_sensor_text(lang, 'flow_out')
    text_target = get_sensor_text(lang, 'target')
    text_collector = get_sensor_text(lang, 'collector')
    text_buffer = get_sensor_text(lang, 'buffer')
    text_domestic_water = get_sensor_text(lang, 'domestic_water')
    entities = [
        # LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_WP_BZ_akt',
        #                 'status', 'Status', 'mdi:text-short', f"{DOMAIN}__status", None, None),
        LuxtronikStatusSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_WP_BZ_akt',
                              'status', 'Status', LUX_STATE_ICON_MAP, f"{DOMAIN}__status", None, None),
        # LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_WP_BZ_akt',
        #                 'status', 'Status', LUX_STATE_ICON_MAP, 'status', None, None),  # 'mdi:text-short'
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeit', 'status_time',
                        f"Status {text_time}", 'mdi:timer-sand', DEVICE_CLASS_TIMESTAMP, 'status_time', TIME_SECONDS),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile1',
                        'status_line_1', 'Status 1', 'mdi:numeric-1-circle', f"{DOMAIN}__status_line_1", None, None),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile2',
                        'status_line_2', 'Status 2', 'mdi:numeric-2-circle', f"{DOMAIN}__status_line_2", None, None),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_HauptMenuStatus_Zeile3',
                        'status_line_3', 'Status 3', 'mdi:numeric-3-circle', f"{DOMAIN}__status_line_3", None, None),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TWA',
                        'output_temperature', f"{text_output} {text_temp}"),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Temperatur_TA',
                        'outdoor_temperature', f"{text_outdoor} {text_temp}",),
        LuxtronikSensor(hass, luxtronik, deviceInfo, 'calculations.ID_WEB_Mitteltemperatur',
                        'outdoor_temperature_average', f"{text_average} {text_outdoor} {text_temp}"),

        LuxtronikSensor(hass, luxtronik, deviceInfoHeating, 'calculations.ID_WEB_Temperatur_TVL',
                        'flow_in_temperature', f"{text_flow_in} {text_temp}", 'mdi:waves-arrow-left'),
        LuxtronikSensor(hass, luxtronik, deviceInfoHeating, 'calculations.ID_WEB_Temperatur_TRL',
                        'flow_out_temperature', f"{text_flow_out} {text_temp}", 'mdi:waves-arrow-right'),
        LuxtronikSensor(hass, luxtronik, deviceInfoHeating, 'calculations.ID_WEB_Sollwert_TRL_HZ',
                        'flow_out_temperature_target', f"{text_flow_out} {text_temp} {text_target}"),

        LuxtronikSensor(hass, luxtronik, deviceInfoDomesticWater, 'calculations.ID_WEB_Temperatur_TSK',
                        'solar_collector_temperature', f"Solar {text_collector} {text_temp}", 'mdi:solar-panel-large'),
        LuxtronikSensor(hass, luxtronik, deviceInfoDomesticWater, 'calculations.ID_WEB_Temperatur_TSS',
                        'solar_buffer_temperature', f"Solar {text_buffer} {text_temp}", 'mdi:propane-tank-outline'),
        LuxtronikSensor(hass, luxtronik, deviceInfoDomesticWater, 'calculations.ID_WEB_Temperatur_TBW',
                        'domestic_water_temperature', f"{text_domestic_water} {text_temp}", 'mdi:coolant-temperature')
    ]

    async_add_entities(entities)


class LuxtronikSensor(SensorEntity, RestoreEntity):
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
        if not self._icon is None and type(self._icon) is dict and not isinstance(self._icon, str):
            if self.native_value in self._icon:
                return self._icon[self.native_value]
            return None
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


class LuxtronikStatusSensor(LuxtronikSensor):
    @property
    def is_on(self) -> bool:  # | None:
        return self.native_value in LUX_STATES_ON

    def _get_sensor_value(self, sensor_name: str):
        sensor = self.hass.states.get(sensor_name)
        if not sensor is None:
            return sensor.state
        return None

    def _build_status_text(self) -> str:
        status_time = self._get_sensor_value('sensor.luxtronik2_status_time')
        l1 = self._get_sensor_value('sensor.luxtronik2_status_line_1')
        l2 = self._get_sensor_value('sensor.luxtronik2_status_line_2')
        if status_time is None or status_time == STATE_UNAVAILABLE or l1 is None or l1 == STATE_UNAVAILABLE or l2 is None or l2 == STATE_UNAVAILABLE:
            return ''
        status_time = int(status_time)
        time_str = '{:01.0f}:{:02.0f}'.format(
            int(status_time / 3600), int(status_time / 60) % 60)
        return f"{l1} {l2} {time_str}"

    @property
    def extra_state_attributes(self) -> LuxtronikStatusExtraAttributes:
        """Return the state attributes of the device."""
        return {
            # ATTR_STATUS_TEXT: self._build_status_text(),
        }

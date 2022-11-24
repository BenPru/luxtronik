"""Luxtronik heatpump sensor."""
# region Imports
from datetime import datetime, time

from homeassistant.components.sensor import (ENTITY_ID_FORMAT,
                                             STATE_CLASS_MEASUREMENT,
                                             STATE_CLASS_TOTAL_INCREASING,
                                             SensorEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_FRIENDLY_NAME, CONF_ICON, CONF_ID,
                                 CONF_SENSORS, DEVICE_CLASS_ENERGY,
                                 DEVICE_CLASS_POWER, DEVICE_CLASS_TEMPERATURE,
                                 ENERGY_KILO_WATT_HOUR, ENTITY_CATEGORIES,
                                 EVENT_HOMEASSISTANT_STOP, POWER_WATT,
                                 STATE_UNAVAILABLE, TEMP_CELSIUS, TEMP_KELVIN,
                                 TIME_HOURS, TIME_SECONDS, UnitOfPressure)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY, ATTR_STATUS_TEXT, CONF_GROUP,
                                               CONF_LANGUAGE_SENSOR_NAMES,
                                               DEFAULT_DEVICE_CLASS,
                                               DEVICE_CLASSES, DOMAIN, ICONS,
                                               LOGGER, LUX_SENSOR_STATUS,
                                               LUX_SENSOR_STATUS1,
                                               LUX_SENSOR_STATUS3,
                                               LUX_STATE_ICON_MAP,
                                               LUX_STATES_ON,
                                               LUX_STATUS_DOMESTIC_WATER,
                                               LUX_STATUS_EVU,
                                               LUX_STATUS1_WORKAROUND,
                                               LUX_STATUS3_WORKAROUND,
                                               LUX_STATUS_HEATING,
                                               LUX_STATUS_NO_REQUEST,
                                               LUX_STATUS_THERMAL_DESINFECTION,
                                               SECOUND_TO_HOUR_FACTOR, UNITS)
from .helpers.helper import (get_sensor_text, get_sensor_value_text)
from .luxtronik_device import LuxtronikDevice
from .model import LuxtronikStatusExtraAttributes

# endregion Imports

# region Constants
# endregion Constants

# region Setup


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up a Luxtronik sensor from yaml config."""
    LOGGER.info(
        f"{DOMAIN}.sensor.async_setup_platform ConfigType: %s - discovery_info: %s",
        config,
        discovery_info,
    )
    luxtronik: LuxtronikDevice = hass.data.get(DOMAIN)
    if not luxtronik:
        LOGGER.warning("%s.sensor.async_setup_platform no luxtronik!", DOMAIN)
        return False

    # use_legacy_sensor_ids = hass.data[f"{DOMAIN}_{CONF_USE_LEGACY_SENSOR_IDS}"]
    # LOGGER.info("sensor.async_setup_platform use_legacy_sensor_ids: '%s'",
    #             use_legacy_sensor_ids)
    device_info = hass.data[f"{DOMAIN}_DeviceInfo"]

    sensors = config.get(CONF_SENSORS)
    entities = []
    if sensors:
        # region yaml sensors part:
        for sensor_cfg in sensors:
            sensor_id = sensor_cfg[CONF_ID]
            if "." in sensor_id:
                group = sensor_id.split(".")[0]
                sensor_id = sensor_id.split(".")[1]
            else:
                group = sensor_cfg[CONF_GROUP]
            sensor = luxtronik.get_sensor(group, sensor_id)
            if sensor:
                name = (
                    sensor.name
                    if not sensor_cfg.get(CONF_FRIENDLY_NAME)
                    else sensor_cfg.get(CONF_FRIENDLY_NAME)
                )
                icon = (
                    ICONS.get(sensor.measurement_type)
                    if not sensor_cfg.get(CONF_ICON)
                    else sensor_cfg.get(CONF_ICON)
                )
                entities += [
                    LuxtronikSensor(
                        hass=hass,
                        luxtronik=luxtronik,
                        deviceInfo=device_info,
                        sensor_key=f"{group}.{sensor_id}",
                        unique_id=sensor_id,
                        name=name,
                        icon=icon,
                        device_class=DEVICE_CLASSES.get(
                            sensor.measurement_type, DEFAULT_DEVICE_CLASS
                        ),
                        state_class=None,
                        unit_of_measurement=UNITS.get(sensor.measurement_type),
                    )
                ]
            else:
                LOGGER.warning(
                    "%s.sensor.async_setup_platform: Invalid Luxtronik ID %s in group %s",
                    DOMAIN,
                    sensor_id,
                    group,
                )
        # endregion yaml sensors part

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Luxtronik sensor from ConfigEntry."""
    LOGGER.info(f"{DOMAIN}.sensor.async_setup_entry ConfigType: %s", config_entry)
    luxtronik: LuxtronikDevice = hass.data.get(DOMAIN)
    if not luxtronik:
        LOGGER.warning("%s.sensor.async_setup_entry no luxtronik!", DOMAIN)
        return False

    device_info = hass.data[f"{DOMAIN}_DeviceInfo"]

    # Build Sensor names with local language:
    lang = config_entry.options.get(CONF_LANGUAGE_SENSOR_NAMES)
    hass.data[f"{DOMAIN}_language"] = lang
    text_time = get_sensor_text(lang, "time")
    text_temp = get_sensor_text(lang, "temperature")
    text_external = get_sensor_text(lang, "external")
    text_pump = get_sensor_text(lang, "pump")
    text_heat_source_output = get_sensor_text(lang, "heat_source_output")
    text_heat_source_input = get_sensor_text(lang, "heat_source_input")
    text_outdoor = get_sensor_text(lang, "outdoor")
    text_average = get_sensor_text(lang, "average")
    text_compressor_impulses = get_sensor_text(lang, "compressor_impulses")
    text_operation_hours = get_sensor_text(lang, "operation_hours")
    text_heat_amount_counter = get_sensor_text(lang, "heat_amount_counter")
    text_current_heat_output = get_sensor_text(lang, "current_heat_output")
    text_hot_gas = get_sensor_text(lang, "hot_gas")
    text_suction_compressor = get_sensor_text(lang, "suction_compressor")
    text_suction_evaporator = get_sensor_text(lang, "suction_evaporator")
    text_compressor_heating = get_sensor_text(lang, "compressor_heating")
    text_overheating = get_sensor_text(lang, "overheating")
    text_overheating_target = get_sensor_text(lang, "overheating_target")
    text_high_pressure = get_sensor_text(lang, "high_pressure")
    text_low_pressure = get_sensor_text(lang, "low_pressure")
    text_operation_hours_additional_heat_generator = get_sensor_text(lang, "operation_hours_additional_heat_generator")
    # entities: list[LuxtronikSensor] = [
    #     LuxtronikStatusSensor(hass, luxtronik, device_info, description)
    #     for description in GLOBAL_STATUS_SENSOR_TYPES
    #     # if description.key in MONITORED_CONDITIONS
    # ]
    # entities.extend(
    #     [
    #         LuxtronikSensor(hass, luxtronik, device_info, description)
    #         for description in GLOBAL_SENSOR_TYPES
    #     ]
    # )

    entities = [
        LuxtronikStatusSensor(
            hass,
            luxtronik,
            device_info,
            LUX_SENSOR_STATUS,
            "status",
            "Status",
            LUX_STATE_ICON_MAP,
            f"{DOMAIN}__status",
            None,
            None,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_HauptMenuStatus_Zeit",
            "status_time",
            f"Status {text_time}",
            "mdi:timer-sand",
            device_class=None,
            state_class=None,
            unit_of_measurement=TIME_SECONDS,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_HauptMenuStatus_Zeile1",
            "status_line_1",
            "Status 1",
            "mdi:numeric-1-circle",
            f"{DOMAIN}__status_line_1",
            None,
            None,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_HauptMenuStatus_Zeile2",
            "status_line_2",
            "Status 2",
            "mdi:numeric-2-circle",
            f"{DOMAIN}__status_line_2",
            None,
            None,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_HauptMenuStatus_Zeile3",
            "status_line_3",
            "Status 3",
            "mdi:numeric-3-circle",
            f"{DOMAIN}__status_line_3",
            None,
            None,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_Temperatur_TWE",
            "heat_source_input_temperature",
            f"{text_heat_source_input}",
            entity_category=None,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_Temperatur_TA",
            "outdoor_temperature",
            f"{text_outdoor} {text_temp}",
            entity_category=None,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_Mitteltemperatur",
            "outdoor_temperature_average",
            f"{text_average} {text_outdoor} {text_temp}",
            entity_category=None,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            sensor_key="calculations.ID_WEB_Zaehler_BetrZeitImpVD1",
            unique_id="compressor_impulses",
            name=f"{text_compressor_impulses}",
            icon="mdi:pulse",
            device_class=None,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            unit_of_measurement="Anzahl",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            sensor_key="calculations.ID_WEB_Zaehler_BetrZeitWP",
            unique_id="operation_hours",
            name=f"{text_operation_hours}",
            icon="mdi:timer-sand",
            device_class=None,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            unit_of_measurement=TIME_HOURS,
            entity_category=EntityCategory.DIAGNOSTIC,
            factor=SECOUND_TO_HOUR_FACTOR,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            sensor_key="calculations.ID_WEB_WMZ_Seit",
            unique_id="heat_amount_counter",
            name=f"{text_heat_amount_counter}",
            icon="mdi:lightning-bolt-circle",
            device_class=DEVICE_CLASS_ENERGY,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_Temperatur_THG",
            "hot_gas_temperature",
            f"{text_hot_gas}",
            entity_category=None,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_LIN_ANSAUG_VERDICHTER",
            "suction_compressor_temperature",
            f"{text_suction_compressor}",
            entity_category=None,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_LIN_ANSAUG_VERDAMPFER",
            "suction_evaporator_temperature",
            f"{text_suction_evaporator}",
            entity_category=None,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_LIN_VDH",
            "compressor_heating_temperature",
            f"{text_compressor_heating}",
            entity_category=None,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_LIN_UH",
            "overheating_temperature",
            f"{text_overheating}",
            entity_category=None,
            unit_of_measurement=TEMP_KELVIN,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_LIN_UH_Soll",
            "overheating_target_temperature",
            f"{text_overheating_target}",
            entity_category=None,
            unit_of_measurement=TEMP_KELVIN,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_LIN_HD",
            "high_pressure",
            f"{text_high_pressure}",
            entity_category=None,
            unit_of_measurement=UnitOfPressure.BAR,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            "calculations.ID_WEB_LIN_ND",
            "low_pressure",
            f"{text_low_pressure}",
            entity_category=None,
            unit_of_measurement=UnitOfPressure.BAR,
        ),
        LuxtronikSensor(
            hass,
            luxtronik,
            device_info,
            sensor_key="calculations.ID_WEB_Zaehler_BetrZeitZWE1",
            unique_id="operation_hours_additional_heat_generator",
            name=text_operation_hours_additional_heat_generator,
            icon="mdi:timer-sand",
            device_class=None,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            unit_of_measurement=TIME_HOURS,
            entity_category=EntityCategory.DIAGNOSTIC,
            factor=SECOUND_TO_HOUR_FACTOR,
        ),
    ]
    if luxtronik.get_value("calculations.Heat_Output") is not None:
        entities += [
            LuxtronikSensor(
                hass,
                luxtronik,
                device_info,
                sensor_key="calculations.Heat_Output",
                unique_id="current_heat_output",
                name=f"{text_current_heat_output}",
                icon="mdi:lightning-bolt-circle",
                device_class=DEVICE_CLASS_POWER,
                state_class=STATE_CLASS_MEASUREMENT,
                unit_of_measurement=POWER_WATT,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ]
    if luxtronik.get_value("parameters.ID_Waermemenge_ZWE") > 0:
        text_additional_heat_generator_amount_counter = get_sensor_text(lang, "additional_heat_generator_amount_counter")
        entities += [
            LuxtronikSensor(
                hass,
                luxtronik,
                device_info,
                sensor_key="parameters.ID_Waermemenge_ZWE",
                unique_id="additional_heat_generator_amount_counter",
                name=text_additional_heat_generator_amount_counter,
                icon="mdi:lightning-bolt-circle",
                device_class=DEVICE_CLASS_ENERGY,
                state_class=STATE_CLASS_TOTAL_INCREASING,
                unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                entity_category=EntityCategory.DIAGNOSTIC,
                factor=0.1
            ),
        ]
        
    if device_info.get('model') != 'LD7':
        entities += [
          LuxtronikSensor(
                      hass,
                      luxtronik,
                      device_info,
                      "calculations.ID_WEB_Freq_VD",
                      "pump frequency",
                      f"{text_pump} Frequency",
                      entity_category=None,
                      icon="mdi:sine-wave",
                      unit_of_measurement='Hz'
                  ),
            LuxtronikSensor(
                hass,
                luxtronik,
                device_info,
                "calculations.ID_WEB_Temperatur_TWA",
                "heat_source_output_temperature",
                f"{text_heat_source_output}",
                entity_category=None,
            ),
        ]

    device_info_heating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    if device_info_heating is not None:
        text_flow_in = get_sensor_text(lang, "flow_in")
        text_flow_out = get_sensor_text(lang, "flow_out")
        text_target = get_sensor_text(lang, "target")
        text_operation_hours_heating = get_sensor_text(lang, "operation_hours_heating")
        text_heat_amount_heating = get_sensor_text(lang, "heat_amount_heating")
        has_room_temp = luxtronik.get_value("parameters.ID_Einst_RFVEinb_akt") != 0
        if has_room_temp:
            text_room = get_sensor_text(lang, "room")
            entities += [
                LuxtronikSensor(
                    hass,
                    luxtronik,
                    device_info_heating,
                    "calculations.ID_WEB_RBE_RT_Ist",
                    "room_temperature",
                    f"{text_room}",
                    entity_category=None,
                ),
                LuxtronikSensor(
                    hass,
                    luxtronik,
                    device_info_heating,
                    "calculations.ID_WEB_RBE_RT_Soll",
                    "room_target_temperature",
                    f"{text_room} {text_target}",
                    entity_category=None,
                )
            ]

        entities += [
            LuxtronikSensor(
                hass,
                luxtronik,
                device_info_heating,
                "calculations.ID_WEB_Temperatur_TVL",
                "flow_in_temperature",
                f"{text_flow_in}",
                "mdi:waves-arrow-left",
                entity_category=None,
            ),
            LuxtronikSensor(
                hass,
                luxtronik,
                device_info_heating,
                "calculations.ID_WEB_Temperatur_TRL",
                "flow_out_temperature",
                f"{text_flow_out}",
                "mdi:waves-arrow-right",
                entity_category=None,
            ),
            LuxtronikSensor(
                hass,
                luxtronik,
                device_info_heating,
                "calculations.ID_WEB_Temperatur_TRL_ext",
                "flow_out_temperature_external",
                f"{text_flow_out} ({text_external})",
                "mdi:waves-arrow-right",
                entity_category=None,
            ),
            LuxtronikSensor(
                hass,
                luxtronik,
                device_info_heating,
                "calculations.ID_WEB_Sollwert_TRL_HZ",
                "flow_out_temperature_target",
                f"{text_flow_out} {text_target}",
                entity_category=None,
            ),
            LuxtronikSensor(
                hass,
                luxtronik,
                device_info_heating,
                sensor_key="calculations.ID_WEB_Zaehler_BetrZeitHz",
                unique_id="operation_hours_heating",
                name=f"{text_operation_hours_heating}",
                icon="mdi:timer-sand",
                device_class=None,
                state_class=STATE_CLASS_TOTAL_INCREASING,
                unit_of_measurement=TIME_HOURS,
                entity_category=EntityCategory.DIAGNOSTIC,
                factor=SECOUND_TO_HOUR_FACTOR,
            ),
            LuxtronikSensor(
                hass,
                luxtronik,
                device_info_heating,
                sensor_key="calculations.ID_WEB_WMZ_Heizung",
                unique_id="heat_amount_heating",
                name=f"{text_heat_amount_heating}",
                icon="mdi:lightning-bolt-circle",
                device_class=DEVICE_CLASS_ENERGY,
                state_class=STATE_CLASS_TOTAL_INCREASING,
                unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ]

    device_info_domestic_water = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    if device_info_domestic_water is not None:
        text_collector = get_sensor_text(lang, "collector")
        text_buffer = get_sensor_text(lang, "buffer")
        text_domestic_water = get_sensor_text(lang, "domestic_water")
        text_operation_hours_domestic_water = get_sensor_text(
            lang, "operation_hours_domestic_water"
        )
        text_operation_hours_solar = get_sensor_text(lang, "operation_hours_solar")
        text_heat_amount_domestic_water = get_sensor_text(
            lang, "heat_amount_domestic_water"
        )
        solar_present = luxtronik.detect_solar_present()

        entities += [
            LuxtronikSensor(
                hass,
                luxtronik,
                device_info_domestic_water,
                "calculations.ID_WEB_Temperatur_TBW",
                "domestic_water_temperature",
                f"{text_domestic_water}",
                "mdi:coolant-temperature",
                entity_category=None,
            ),
            LuxtronikSensor(
                hass,
                luxtronik,
                device_info_domestic_water,
                sensor_key="calculations.ID_WEB_Zaehler_BetrZeitBW",
                unique_id="operation_hours_domestic_water",
                name=f"{text_operation_hours_domestic_water}",
                icon="mdi:timer-sand",
                device_class=None,
                state_class=STATE_CLASS_TOTAL_INCREASING,
                unit_of_measurement=TIME_HOURS,
                entity_category=EntityCategory.DIAGNOSTIC,
                factor=SECOUND_TO_HOUR_FACTOR,
            ),
            LuxtronikSensor(
                hass,
                luxtronik,
                device_info_domestic_water,
                sensor_key="calculations.ID_WEB_WMZ_Brauchwasser",
                unique_id="heat_amount_domestic_water",
                name=f"{text_heat_amount_domestic_water}",
                icon="mdi:lightning-bolt-circle",
                device_class=DEVICE_CLASS_ENERGY,
                state_class=STATE_CLASS_TOTAL_INCREASING,
                unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ]
        if solar_present:
            entities += [
                LuxtronikSensor(
                    hass,
                    luxtronik,
                    device_info_domestic_water,
                    "calculations.ID_WEB_Temperatur_TSK",
                    "solar_collector_temperature",
                    f"Solar {text_collector}",
                    "mdi:solar-panel-large",
                    entity_category=None,
                ),
                LuxtronikSensor(
                    hass,
                    luxtronik,
                    device_info_domestic_water,
                    "calculations.ID_WEB_Temperatur_TSS",
                    "solar_buffer_temperature",
                    f"Solar {text_buffer}",
                    "mdi:propane-tank-outline",
                    entity_category=None,
                ),
                LuxtronikSensor(
                    hass,
                    luxtronik,
                    device_info_domestic_water,
                    sensor_key="parameters.ID_BSTD_Solar",
                    unique_id="operation_hours_solar",
                    name=f"{text_operation_hours_solar}",
                    icon="mdi:timer-sand",
                    device_class=None,
                    state_class=STATE_CLASS_TOTAL_INCREASING,
                    unit_of_measurement=TIME_HOURS,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    factor=SECOUND_TO_HOUR_FACTOR,
                ),

            ]

    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]
    if deviceInfoCooling is not None:
        text_operation_hours_cooling = get_sensor_text(lang, "operation_hours_cooling")
        entities += [
            LuxtronikSensor(
                hass,
                luxtronik,
                deviceInfoCooling,
                sensor_key="calculations.ID_WEB_Zaehler_BetrZeitKue",
                unique_id="operation_hours_cooling",
                name=f"{text_operation_hours_cooling}",
                icon="mdi:timer-sand",
                device_class=None,
                state_class=STATE_CLASS_TOTAL_INCREASING,
                unit_of_measurement=TIME_HOURS,
                entity_category=EntityCategory.DIAGNOSTIC,
                factor=SECOUND_TO_HOUR_FACTOR,
            )
        ]

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, luxtronik.async_will_remove_from_hass()
    )

    async_add_entities(entities)


# async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Unloading the Luxtronik platforms."""
#     luxtronik = hass.data[DOMAIN]
#     if luxtronik is None:
#         return

#     await hass.async_add_executor_job(luxtronik.disconnect)

#     unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
#     if unload_ok:
#         hass.data[DOMAIN] = None

#     return unload_ok


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
        icon: str = "mdi:thermometer",
        device_class: str = DEVICE_CLASS_TEMPERATURE,
        state_class: str = STATE_CLASS_MEASUREMENT,
        unit_of_measurement: str = TEMP_CELSIUS,
        entity_category: ENTITY_CATEGORIES = None,
        factor: float = None,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._luxtronik = luxtronik

        self.entity_id = ENTITY_ID_FORMAT.format(f"{DOMAIN}_{unique_id}")
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
        self._attr_extra_state_attributes = { ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY: sensor_key }

    @property
    def icon(self):  # -> str | None:
        """Return the icon to be used for this entity."""
        if (
            self._icon is not None
            and isinstance(self._icon, dict)
            and not isinstance(self._icon, str)
        ):
            if self.native_value in self._icon:
                return self._icon[self.native_value]
            return None
        return self._icon

    @property
    def native_value(self):  # -> float | int | None:
        """Return the state of the sensor."""
        value = self._luxtronik.get_value(self._sensor_key)

        if self._sensor_key == LUX_SENSOR_STATUS:
            status3 = self._luxtronik.get_value(LUX_SENSOR_STATUS3)
            if status3 == LUX_STATUS_THERMAL_DESINFECTION:
                # map thermal desinfection to Domestic Water iso Heating
                return LUX_STATUS_DOMESTIC_WATER

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
        if self._sensor_key == "calculations.ID_WEB_HauptMenuStatus_Zeit":
            value = self.native_value
            if value is None:
                time_str = None
            else:
                (minutes, seconds) = divmod(int(value), 60)
                hours, minutes = divmod(minutes, 60)
                time_str = f"{hours:01.0f}:{minutes:02.0f} h"
            self._attr_extra_state_attributes[ATTR_STATUS_TEXT] = time_str
            # self._attr_extra_state_attributes = {ATTR_STATUS_TEXT: time_str}


class LuxtronikLegacySensor(LuxtronikSensor):
    def __init__(self, set_entity_id: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # self._set_entity_id = set_entity_id
        # self.entity_id = set_entity_id
        self._attr_unique_id = set_entity_id
        # self.unique_id = set_entity_id
        # self._attr_entity_id = set_entity_id

        # self.domain = "luxtronik"
        # self.platform_name = "luxtronik"
        self.entity_namespace = "luxtronik"

    # @property
    # def entity_id(self):
    #     """Return the entity_id of the sensor."""
    #     return self._set_entity_id

    # @entity_id.setter
    # def set_entity_id(self, x):
    #     pass

class LuxtronikStatusSensor(LuxtronikSensor, RestoreEntity):
    """Luxtronik Status Sensor with extended attr."""

    _last_state: str = None

    _first_evu_start_time: time = None
    _first_evu_end_time: time = None
    _second_evu_start_time: time = None
    _second_evu_end_time: time = None

    def update(self):
        LuxtronikSensor.update(self)
        time_now = time(datetime.utcnow().hour, datetime.utcnow().minute)
        if self.native_value == LUX_STATUS_EVU and self._last_state != LUX_STATUS_EVU:
            # evu start
            if self._first_evu_start_time is None or time_now.hour <= self._first_evu_start_time.hour:
                self._first_evu_start_time = time_now
            else:
                self._second_evu_start_time = time_now
        elif self.native_value != LUX_STATUS_EVU and self._last_state == LUX_STATUS_EVU:
            # evu end
            if self._first_evu_end_time is None or time_now.hour <= self._first_evu_end_time.hour:
                self._first_evu_end_time = time_now
            else:
                self._second_evu_end_time = time_now

        self._last_state = self.native_value

    def _get_sensor_value(self, sensor_name: str):
        sensor = self.hass.states.get(sensor_name)
        if sensor is not None:
            return sensor.state
        return None

    def _get_sensor_attr(self, sensor_name: str, attr: str):
        sensor = self.hass.states.get(sensor_name)
        if sensor is not None and attr in sensor.attributes:
            return sensor.attributes[attr]
        return None

    def _build_status_text(self) -> str:
        status_time = self._get_sensor_attr(
            f"sensor.{DOMAIN}_status_time", ATTR_STATUS_TEXT
        )
        line_1 = self._get_sensor_value(f"sensor.{DOMAIN}_status_line_1")
        line_2 = self._get_sensor_value(f"sensor.{DOMAIN}_status_line_2")
        if (
            status_time is None
            or status_time == STATE_UNAVAILABLE
            or line_1 is None
            or line_1 == STATE_UNAVAILABLE
            or line_2 is None
            or line_2 == STATE_UNAVAILABLE
        ):
            return ""
        lang = self.hass.data[f"{DOMAIN}_language"]
        line_1 = get_sensor_value_text(lang, f"{DOMAIN}__status_line_1", line_1)
        line_2 = get_sensor_value_text(lang, f"{DOMAIN}__status_line_2", line_2)
        # TODO: Show evu end time if available
        # if 
        return f"{line_1} {line_2} {status_time}."

    def _calc_next_evu_event_minutes_text(self) -> str:
        minutes = self._calc_next_evu_event_minutes()
        return '' if minutes is None else str(minutes)

    def _calc_next_evu_event_minutes(self) -> int:
        evu_time = self._get_next_evu_event_time()
        time_now = time(datetime.utcnow().hour, datetime.utcnow().minute)
        if evu_time is None:
            return None
        evu_hours = (24 if evu_time < time_now else 0) + evu_time.hour
        return (evu_hours - time_now.hour) * 60 + evu_time.minute - time_now.minute

    def _get_next_evu_event_time(self) -> time:
        event: time = None
        time_now = time(datetime.utcnow().hour, datetime.utcnow().minute)
        for evu_time in [self._first_evu_start_time, self._first_evu_end_time, self._second_evu_start_time, self._second_evu_end_time]:
            if evu_time is None:
                continue
            if evu_time > time_now and (event is None or evu_time < event):
                event = evu_time
        if event is None:
            for evu_time in [self._first_evu_start_time, self._first_evu_end_time, self._second_evu_start_time, self._second_evu_end_time]:
                if evu_time is None:
                    continue
                if event is None or evu_time < event:
                    event = evu_time
        return event


    @property
    def extra_state_attributes(self) -> LuxtronikStatusExtraAttributes:
        """Return the state attributes of the device."""
        return {
            ATTR_STATUS_TEXT: self._build_status_text(),
            ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY: self._sensor_key,
            'status raw': self._luxtronik.get_value(self._sensor_key),
            'EVU first start time': '' if self._first_evu_start_time is None else self._first_evu_start_time.strftime('%H:%M'),
            'EVU first end time': '' if self._first_evu_end_time is None else self._first_evu_end_time.strftime('%H:%M'),
            'EVU second start time': '' if self._second_evu_start_time is None else self._second_evu_start_time.strftime('%H:%M'),
            'EVU second end time': '' if self._second_evu_end_time is None else self._second_evu_end_time.strftime('%H:%M'),
            'EVU minutes until next event': self._calc_next_evu_event_minutes_text(),
        }

    def _restore_value(self, value: str) -> time:
        if value is None or not ':' in value:
            return None
        vals = value.split(':')
        return time(int(vals[0]), int(vals[1]))

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            return
        self._state = state.state

        # ADDED CODE HERE
        if 'EVU first start time' in state.attributes:
            self._first_evu_start_time = self._restore_value(state.attributes['EVU first start time'])
            self._first_evu_end_time = self._restore_value(state.attributes['EVU first end time'])
            self._second_evu_start_time = self._restore_value(state.attributes['EVU second start time'])
            self._second_evu_end_time = self._restore_value(state.attributes['EVU second end time'])

        DATA_UPDATED = f"{DOMAIN}_data_updated"
        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

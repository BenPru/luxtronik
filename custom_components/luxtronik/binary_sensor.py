"""Support for Luxtronik heatpump binary states."""
# region Imports
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.binary_sensor import (DEVICE_CLASS_LOCK,
                                                    DEVICE_CLASS_OPENING,
                                                    DEVICE_CLASS_RUNNING,
                                                    PLATFORM_SCHEMA,
                                                    BinarySensorEntity)
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_FRIENDLY_NAME, CONF_ICON, CONF_ID,
                                 CONF_SENSORS, ENTITY_CATEGORIES)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import (ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY,
                    CONF_CALCULATIONS, CONF_GROUP, CONF_INVERT_STATE,
                    CONF_LANGUAGE_SENSOR_NAMES, CONF_PARAMETERS,
                    CONF_VISIBILITIES, DEFAULT_DEVICE_CLASS, DEVICE_CLASSES,
                    DOMAIN, LOGGER,
                    LUX_BINARY_SENSOR_ADDITIONAL_CIRCULATION_PUMP,
                    LUX_BINARY_SENSOR_CIRCULATION_PUMP_HEATING,
                    LUX_BINARY_SENSOR_DOMESTIC_WATER_RECIRCULATION_PUMP,
                    LUX_BINARY_SENSOR_EVU_UNLOCKED,
                    LUX_BINARY_SENSOR_SOLAR_PUMP)
from .helpers.helper import get_sensor_text
from .luxtronik_device import LuxtronikDevice

# endregion Imports

# region Constants
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSORS): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Optional(CONF_GROUP): vol.All(
                        cv.string,
                        vol.In([CONF_PARAMETERS, CONF_CALCULATIONS, CONF_VISIBILITIES]),
                    ),
                    vol.Required(CONF_ID): cv.string,
                    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
                    vol.Optional(CONF_ICON): cv.string,
                    vol.Optional(CONF_INVERT_STATE, default=False): cv.boolean,
                }
            ],
        )
    }
)
# endregion Constants

# region Setup


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] = None,
) -> None:
    """Set up a Luxtronik binary sensor from yaml config."""
    LOGGER.info(
        f"{DOMAIN}.binary_sensor.async_setup_platform ConfigType: %s - discovery_info: %s",
        config,
        discovery_info,
    )
    luxtronik: LuxtronikDevice = hass.data.get(DOMAIN)
    if not luxtronik:
        LOGGER.warning("binary_sensor.async_setup_platform no luxtronik!")
        return False

    # use_legacy_sensor_ids = hass.data[f"{DOMAIN}_{CONF_USE_LEGACY_SENSOR_IDS}"]
    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]

    sensors = config.get(CONF_SENSORS)
    entities = []
    if sensors:
        # region Legacy part:
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
                # if use_legacy_sensor_ids else None
                entity_id = "luxtronik.{}".format(slugify(name))
                LOGGER.info(
                    "binary_sensor.async_setup_platform create entity_id: '%s'",
                    entity_id,
                )
                entities += [
                    LuxtronikBinarySensor(
                        luxtronik,
                        deviceInfo=deviceInfo,
                        sensor_key=f"{group}.{sensor_id}",
                        unique_id=sensor_id,
                        name=name,
                        icon=sensor_cfg.get(CONF_ICON),
                        device_class=DEVICE_CLASSES.get(
                            sensor.measurement_type, DEFAULT_DEVICE_CLASS
                        ),
                        state_class=None,
                        invert_state=sensor_cfg.get(CONF_INVERT_STATE),
                    )
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
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Luxtronik sensor from ConfigEntry."""
    LOGGER.info(
        f"{DOMAIN}.binary_sensor.async_setup_entry ConfigType: %s", config_entry
    )
    luxtronik: LuxtronikDevice = hass.data.get(DOMAIN)
    if not luxtronik:
        LOGGER.warning("binary_sensor.async_setup_entry no luxtronik!")
        return False

    deviceInfo = hass.data[f"{DOMAIN}_DeviceInfo"]

    # Build Sensor names with local language:
    lang = hass.config.language
    text_evu_unlocked = get_sensor_text(lang, "evu_unlocked")
    text_compressor = get_sensor_text(lang, "compressor")
    text_circulation_pump = get_sensor_text(lang, "circulation_pump")
    text_additional_circulation_pump = get_sensor_text(lang, "additional_circulation_pump")
    text_domestic_water_recirculation_pump = get_sensor_text(lang, "domestic_water_recirculation_pump")
    text_circulation_pump_heating = get_sensor_text(lang, "circulation_pump_heating")
    text_pump_flow = get_sensor_text(lang, "pump_flow")
    text_compressor_heater = get_sensor_text(lang, "compressor_heater")
    text_additional_heat_generator = get_sensor_text(lang, "additional_heat_generator")
    text_defrost_valve = get_sensor_text(lang, "defrost_valve")

    entities = [
        LuxtronikBinarySensor(
            luxtronik=luxtronik,
            deviceInfo=deviceInfo,
            sensor_key=LUX_BINARY_SENSOR_EVU_UNLOCKED,
            unique_id="evu_unlocked",
            name=text_evu_unlocked,
            icon="mdi:lock",
            device_class=DEVICE_CLASS_LOCK,
        ),
        LuxtronikBinarySensor(
            luxtronik=luxtronik,
            deviceInfo=deviceInfo,
            sensor_key='calculations.ID_WEB_VD1out',
            unique_id="compressor",
            name=text_compressor,
            icon="mdi:arrow-collapse-all",
            device_class=DEVICE_CLASS_RUNNING,
        ),
        # Soleumwälzpumpe
        # Umwälzpumpe Ventilator, Brunnen- oder Sole
        LuxtronikBinarySensor(
            luxtronik=luxtronik,
            deviceInfo=deviceInfo,
            sensor_key='calculations.ID_WEB_VBOout',
            unique_id="pump_flow",
            name=text_pump_flow,
            icon="mdi:pump",
            device_class=DEVICE_CLASS_RUNNING,
        ),
        LuxtronikBinarySensor(
            luxtronik=luxtronik,
            deviceInfo=deviceInfo,
            sensor_key='calculations.ID_WEB_LIN_VDH_out',
            unique_id="compressor_heater",
            name=text_compressor_heater,
            icon="mdi:heat-wave",
            device_class=DEVICE_CLASS_RUNNING,
        ),
        LuxtronikBinarySensor(
            luxtronik=luxtronik,
            deviceInfo=deviceInfo,
            sensor_key='calculations.ID_WEB_AVout',
            unique_id="defrost_valve",
            name=text_defrost_valve,
            icon="mdi:valve-open",
            icon_off="mdi:valve-closed",
            device_class=DEVICE_CLASS_OPENING,
        ),
        LuxtronikBinarySensor(
            luxtronik=luxtronik,
            deviceInfo=deviceInfo,
            sensor_key='calculations.ID_WEB_ZW1out',
            unique_id="additional_heat_generator",
            name=text_additional_heat_generator,
            icon="mdi:patio-heater",
            device_class=DEVICE_CLASS_RUNNING,
        ),

        # calculations.ID_WEB_ASDin Soledruck ausreichend
        # calculations.ID_WEB_HDin Hochdruck OK
        # calculations.ID_WEB_MOTin Motorschutz OK
        # calculations.ID_WEB_FP2out FBH Umwälzpumpe 2
        # calculations.ID_WEB_MA1out Mischer 1 auf
        # calculations.ID_WEB_MZ1out Mischer 1 zu
        # calculations.ID_WEB_MA2out Mischer 2 auf
        # calculations.ID_WEB_MZ2out Mischer 2 zu
    ]

    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    if deviceInfoHeating is not None:
        entities += [
            LuxtronikBinarySensor(
                luxtronik=luxtronik,
                deviceInfo=deviceInfoHeating,
                sensor_key=LUX_BINARY_SENSOR_CIRCULATION_PUMP_HEATING,
                unique_id="circulation_pump_heating",
                name=text_circulation_pump_heating,
                icon="mdi:car-turbocharger",
                device_class=DEVICE_CLASS_RUNNING,
            ),
            LuxtronikBinarySensor(
                luxtronik=luxtronik,
                deviceInfo=deviceInfoHeating,
                sensor_key=LUX_BINARY_SENSOR_ADDITIONAL_CIRCULATION_PUMP,
                unique_id="additional_circulation_pump",
                name=text_additional_circulation_pump,
                icon="mdi:pump",
                device_class=DEVICE_CLASS_RUNNING,
            ),
        ]

    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    if deviceInfoDomesticWater is not None:
        if luxtronik.has_domestic_water_circulation_pump:
            circulation_pump_unique_id = 'domestic_water_circulation_pump'
            text_domestic_water_circulation_pump = text_circulation_pump
        else:
            circulation_pump_unique_id = 'domestic_water_charging_pump'
            text_domestic_water_circulation_pump = get_sensor_text(lang, "domestic_water_charging_pump")
        entities += [
            LuxtronikBinarySensor(
                luxtronik=luxtronik,
                deviceInfo=deviceInfoDomesticWater,
                sensor_key=LUX_BINARY_SENSOR_DOMESTIC_WATER_RECIRCULATION_PUMP,
                unique_id="domestic_water_recirculation_pump",
                name=text_domestic_water_recirculation_pump,
                icon="mdi:pump",
                device_class=DEVICE_CLASS_RUNNING,
            ),
            LuxtronikBinarySensor(
                luxtronik=luxtronik,
                deviceInfo=deviceInfoDomesticWater,
                sensor_key='calculations.ID_WEB_ZIPout',
                unique_id=circulation_pump_unique_id,
                name=text_domestic_water_circulation_pump,
                icon="mdi:pump",
                device_class=DEVICE_CLASS_RUNNING,
            ),
        ]
        solar_present = luxtronik.detect_solar_present()
        if solar_present:
            text_solar_pump = get_sensor_text(lang, "solar_pump")
            entities += [
                LuxtronikBinarySensor(
                    luxtronik=luxtronik,
                    deviceInfo=deviceInfoDomesticWater,
                    sensor_key=LUX_BINARY_SENSOR_SOLAR_PUMP,
                    unique_id="solar_pump",
                    name=text_solar_pump,
                    icon="mdi:pump",
                    device_class=DEVICE_CLASS_RUNNING,
                ),
            ]

    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]
    if deviceInfoCooling is not None:
        text_approval_cooling = get_sensor_text(lang, "approval_cooling")
        entities += [
            LuxtronikBinarySensor(
                luxtronik=luxtronik,
                deviceInfo=deviceInfoCooling,
                sensor_key="calculations.ID_WEB_FreigabKuehl",
                unique_id="approval_cooling",
                name=text_approval_cooling,
                icon="mdi:lock",
                device_class=DEVICE_CLASS_LOCK,
            )
        ]

    async_add_entities(entities)
# endregion Setup


class LuxtronikBinarySensor(BinarySensorEntity, RestoreEntity):
    """Representation of a Luxtronik binary sensor."""

    _on_state: str = True

    def __init__(
        self,
        luxtronik: LuxtronikDevice,
        deviceInfo: DeviceInfo,
        sensor_key: str,
        unique_id: str,
        name: str,
        icon: str,
        device_class: str,
        state_class: str = None,
        entity_category: ENTITY_CATEGORIES = None,
        invert_state: bool = False,
        icon_off: str = None,
        entity_registry_enabled_default: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize a new Luxtronik binary sensor."""
        # super().__init__(*args)
        # self.hass = hass
        self._luxtronik = luxtronik

        self._sensor_key = sensor_key
        self.entity_id = ENTITY_ID_FORMAT.format(f"{DOMAIN}_{unique_id}")
        self._attr_unique_id = self.entity_id
        self._attr_device_info = deviceInfo
        self._attr_name = name
        self._attr_icon = icon
        self._icon_off = icon_off
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category
        self._invert = invert_state
        self._attr_entity_registry_enabled_default = entity_registry_enabled_default
        self._attr_extra_state_attributes = { ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY: sensor_key }


    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        value = self._luxtronik.get_value(self._sensor_key) == self._on_state
        return not value if self._invert else value

    @property
    def icon(self):  # -> str | None:
        """Return the icon to be used for this entity."""
        if not self.is_on and self._icon_off is not None:
            return self._icon_off
        return self._attr_icon

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        self._luxtronik.update()

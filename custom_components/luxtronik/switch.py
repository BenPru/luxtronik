"""Support for Luxtronik heatpump binary states."""
# region Imports
from typing import Any

from homeassistant.components.binary_sensor import (DEVICE_CLASS_HEAT,
                                                    DEVICE_CLASS_RUNNING)
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import LuxtronikDevice
from .binary_sensor import LuxtronikBinarySensor
from .const import (CONF_LANGUAGE_SENSOR_NAMES, DOMAIN, LOGGER,
                    LUX_SENSOR_EFFICIENCY_PUMP, LUX_SENSOR_HEATING_THRESHOLD,
                    LUX_SENSOR_MODE_COOLING, LUX_SENSOR_MODE_DOMESTIC_WATER,
                    LUX_SENSOR_MODE_HEATING, LUX_SENSOR_PUMP_OPTIMIZATION,
                    LUX_SENSOR_REMOTE_MAINTENANCE, LuxMode)
from .helpers.helper import get_sensor_text

# endregion Imports

# region Constants
# endregion Constants

# region Setup


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Luxtronik sensor from ConfigEntry."""
    LOGGER.info(
        "luxtronik2.switch.async_setup_entry ConfigType: %s", config_entry)
    luxtronik: LuxtronikDevice = hass.data.get(DOMAIN)
    if not luxtronik:
        LOGGER.warning("switch.async_setup_entry no luxtronik!")
        return False

    # Build Sensor names with local language:
    lang = hass.config.language
    entities = []

    device_info = hass.data[f"{DOMAIN}_DeviceInfo"]
    text_remote_maintenance = get_sensor_text(lang, 'remote_maintenance')
    text_pump_optimization = get_sensor_text(lang, 'pump_optimization')
    text_efficiency_pump = get_sensor_text(lang, 'efficiency_pump')
    text_pump_heat_control = get_sensor_text(lang, 'pump_heat_control')
    entities += [
        LuxtronikSwitch(
            hass=hass, luxtronik=luxtronik, deviceInfo=device_info,
            sensor_key=LUX_SENSOR_REMOTE_MAINTENANCE, unique_id='remote_maintenance',
            name=f"{text_remote_maintenance}", icon='mdi:remote-desktop',
            device_class=DEVICE_CLASS_HEAT, entity_category=EntityCategory.CONFIG),
        LuxtronikSwitch(
            hass=hass, luxtronik=luxtronik, deviceInfo=device_info,
            sensor_key=LUX_SENSOR_EFFICIENCY_PUMP, unique_id='efficiency_pump',
            name=f"{text_efficiency_pump}", icon='mdi:leaf-circle',
            device_class=DEVICE_CLASS_HEAT, entity_category=EntityCategory.CONFIG),
        LuxtronikSwitch(
            hass=hass, luxtronik=luxtronik, deviceInfo=device_info,
            sensor_key='parameters.ID_Einst_P155_PumpHeatCtrl', unique_id='pump_heat_control',
            name=text_pump_heat_control, icon='mdi:pump',
            device_class=DEVICE_CLASS_HEAT, entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False),
    ]

    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    if deviceInfoHeating is not None:
        text_heating_mode = get_sensor_text(lang, 'heating_mode_auto')
        text_heating_threshold = get_sensor_text(lang, 'heating_threshold')
        entities += [
            LuxtronikSwitch(
                hass=hass, luxtronik=luxtronik, deviceInfo=deviceInfoHeating,
                sensor_key=LUX_SENSOR_PUMP_OPTIMIZATION, unique_id='pump_optimization',
                name=text_pump_optimization, icon='mdi:tune',
                device_class=DEVICE_CLASS_HEAT, entity_category=EntityCategory.CONFIG),
            LuxtronikSwitch(
                on_state=LuxMode.automatic.value, off_state=LuxMode.off.value,
                hass=hass, luxtronik=luxtronik, deviceInfo=deviceInfoHeating,
                sensor_key=LUX_SENSOR_MODE_HEATING, unique_id='heating',
                name=text_heating_mode, icon='mdi:radiator', icon_off='mdi:radiator-off',
                device_class=DEVICE_CLASS_HEAT),
            LuxtronikSwitch(
                hass=hass, luxtronik=luxtronik, deviceInfo=deviceInfoHeating,
                sensor_key=LUX_SENSOR_HEATING_THRESHOLD, unique_id='heating_threshold',
                name=f"{text_heating_threshold}", icon='mdi:download-outline',
                device_class=DEVICE_CLASS_HEAT, entity_category=EntityCategory.CONFIG)
        ]

    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    if deviceInfoDomesticWater is not None:
        text_domestic_water_mode_auto = get_sensor_text(
            lang, 'domestic_water_mode_auto')
        entities += [
            LuxtronikSwitch(
                on_state=LuxMode.automatic.value, off_state=LuxMode.off.value,
                hass=hass, luxtronik=luxtronik,
                deviceInfo=deviceInfoDomesticWater,
                sensor_key=LUX_SENSOR_MODE_DOMESTIC_WATER,
                unique_id='domestic_water',
                name=text_domestic_water_mode_auto, icon='mdi:water-boiler-auto', icon_off='mdi:water-boiler-off',
                device_class=DEVICE_CLASS_HEAT),
        ]
        
    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]
    if deviceInfoCooling is not None:
        text_cooling_mode_auto = get_sensor_text(
            lang, 'cooling_mode_auto')
        entities += [
            LuxtronikSwitch(
                on_state=LuxMode.automatic.value, off_state=LuxMode.off.value,
                hass=hass, luxtronik=luxtronik,
                deviceInfo=deviceInfoCooling,
                sensor_key=LUX_SENSOR_MODE_COOLING,
                unique_id='cooling',
                name=text_cooling_mode_auto, icon='mdi:snowflake',
                device_class=DEVICE_CLASS_HEAT)
        ]        

    async_add_entities(entities)
# endregion Setup


class LuxtronikSwitch(LuxtronikBinarySensor, SwitchEntity, RestoreEntity):
    """Representation of a Luxtronik switch."""

    def __init__(
        self,
        on_state: str = True,
        off_state: str = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize a new Luxtronik switch."""
        super().__init__(**kwargs)
        self._on_state = on_state
        self._off_state = off_state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._luxtronik.write(self._sensor_key.split(
            '.')[1], self._on_state, use_debounce=False,
            update_immediately_after_write=True)
        self.schedule_update_ha_state(force_refresh=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._luxtronik.write(self._sensor_key.split(
            '.')[1], self._off_state, use_debounce=False,
            update_immediately_after_write=True)
        self.schedule_update_ha_state(force_refresh=True)

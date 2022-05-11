"""Luxtronik heatpump number."""
# region Imports
from typing import Any, Literal

from homeassistant.components.number import NumberEntity
from homeassistant.components.number.const import MODE_AUTO, MODE_BOX
from homeassistant.components.sensor import (ENTITY_ID_FORMAT,
                                             STATE_CLASS_MEASUREMENT)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, ENTITY_CATEGORIES, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import LuxtronikDevice
from .const import (CONF_LANGUAGE_SENSOR_NAMES, DOMAIN, LOGGER,
                    LUX_SENSOR_COOLING_THRESHOLD,
                    LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE,
                    LUX_SENSOR_HEATING_TEMPERATURE_CORRECTION,
                    LUX_SENSOR_HEATING_THRESHOLD)
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
    entities = []

    deviceInfoHeating = hass.data[f"{DOMAIN}_DeviceInfo_Heating"]
    if deviceInfoHeating is not None:
        text_heating_threshold = get_sensor_text(lang, 'heating_threshold')
        text_correction = get_sensor_text(lang, 'correction')
        entities += [
            LuxtronikNumber(
                hass, luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_TEMPERATURE_CORRECTION,
                unique_id='heating_temperature_correction', name=f"{text_temp} {text_correction}",
                icon='mdi:plus-minus-variant', unit_of_measurement=TEMP_CELSIUS, min_value=-5.0, max_value=5.0, step=0.5, mode=MODE_BOX),
            LuxtronikNumber(
                hass, luxtronik, deviceInfoHeating,
                number_key=LUX_SENSOR_HEATING_THRESHOLD,
                unique_id='heating_threshold_temperature', name=f"{text_heating_threshold}",
                icon='mdi:download-outline', unit_of_measurement=TEMP_CELSIUS, min_value=5.0, max_value=12.0, step=0.5, mode=MODE_BOX)
        ]

    deviceInfoDomesticWater = hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"]
    if deviceInfoDomesticWater is not None:
        text_target = get_sensor_text(lang, 'target')
        text_domestic_water = get_sensor_text(lang, 'domestic_water')
        entities += [
            LuxtronikNumber(
                hass, luxtronik, deviceInfoDomesticWater,
                number_key=LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE,
                unique_id='domestic_water_target_temperature', name=f"{text_domestic_water} {text_target} {text_temp}",
                icon='mdi:water-boiler', unit_of_measurement=TEMP_CELSIUS, min_value=40.0, max_value=60.0, step=2.5, mode=MODE_BOX)
        ]

    deviceInfoCooling = hass.data[f"{DOMAIN}_DeviceInfo_Cooling"]
    if deviceInfoCooling is not None:
        text_cooling_threshold_temperature = get_sensor_text(
            lang, 'cooling_threshold_temperature')
        entities += [
            LuxtronikNumber(hass, luxtronik, deviceInfoCooling, number_key=LUX_SENSOR_COOLING_THRESHOLD,
                            unique_id='cooling_threshold_temperature', name=f"{text_cooling_threshold_temperature}",
                            icon='mdi:upload-outline', unit_of_measurement=TEMP_CELSIUS, min_value=18.0, max_value=30.0, step=0.5, mode=MODE_BOX)
        ]

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
        mode: Literal["auto", "box", "slider"] = MODE_AUTO,
        entity_category: ENTITY_CATEGORIES = None,
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
        self._attr_unit_of_measurement = unit_of_measurement
        self._attr_state_class = state_class

        self._attr_device_info = deviceInfo
        self._attr_mode = mode

        if min_value is not None:
            self._attr_min_value = min_value
        if max_value is not None:
            self._attr_max_value = max_value
        if step is not None:
            self._attr_step = step
        self._attr_entity_category = entity_category

    @property
    def icon(self):  # -> str | None:
        """Return the icon to be used for this entity."""
        return self._icon

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        self._luxtronik.update()

    @property
    def value(self) -> float:
        """Return the state of the entity."""
        return self._luxtronik.get_value(self._number_key)

    def set_value(self, value: float) -> None:
        """Update the current value."""
        self._luxtronik.write(self._number_key.split('.')[1], value)
        self.schedule_update_ha_state(force_refresh=True)

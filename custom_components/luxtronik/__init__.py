"""Support for Luxtronik heatpump controllers."""
# region Imports
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from luxtronik import LOGGER as LuxLogger

from .const import (
    ATTR_PARAMETER,
    ATTR_VALUE,
    CONF_LANGUAGE_SENSOR_NAMES,
    CONF_LOCK_TIMEOUT,
    CONF_SAFE,
    CONF_UPDATE_IMMEDIATELY_AFTER_WRITE,
    DOMAIN,
    LANG_DEFAULT,
    LOGGER,
    LUX_SENSOR_DETECT_COOLING,
    PLATFORMS,
    SERVICE_WRITE,
    SERVICE_WRITE_SCHEMA,
)
from .helpers.helper import get_sensor_text
from .helpers.lux_helper import get_manufacturer_by_model
from .luxtronik_device import LuxtronikDevice

# endregion Imports

# region Constants
LuxLogger.setLevel(level="WARNING")
# endregion Constants


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up from config entry."""
    hass.data.setdefault(DOMAIN, {})

    LOGGER.info(
        "%s.async_setup_entry options: '%s' data:'%s'",
        DOMAIN,
        config_entry.options,
        config_entry.data,
    )
    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))

    setup_internal(hass, config_entry.data, config_entry.options)

    luxtronik = hass.data[DOMAIN]

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    def logout_luxtronik(event: Event) -> None:
        """Close connections to this heatpump."""
        luxtronik.disconnect()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, logout_luxtronik)
    )
    await hass.async_add_executor_job(setup_hass_services, hass)
    return True


def setup_hass_services(hass):
    """Home Assistant services."""

    def write_parameter(service):
        """Write a parameter to the Luxtronik heatpump."""
        parameter = service.data.get(ATTR_PARAMETER)
        value = service.data.get(ATTR_VALUE)
        luxtronik = hass.data[DOMAIN]
        update_immediately_after_write = hass.data[f"{DOMAIN}_conf"][
            CONF_UPDATE_IMMEDIATELY_AFTER_WRITE
        ]
        luxtronik.write(
            parameter,
            value,
            use_debounce=True,
            update_immediately_after_write=update_immediately_after_write,
        )

    hass.services.register(
        DOMAIN, SERVICE_WRITE, write_parameter, schema=SERVICE_WRITE_SCHEMA
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the luxtronik component."""
    if DOMAIN not in config:
        # Setup via UI. No need to continue yaml-based setup
        return True
    conf = config[DOMAIN]
    return setup_internal(hass, conf, conf)


def setup_internal(hass, data, conf):
    """Set up the Luxtronik component."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    safe = data[CONF_SAFE]
    lock_timeout = data[CONF_LOCK_TIMEOUT]
    # update_immediately_after_write = data[CONF_UPDATE_IMMEDIATELY_AFTER_WRITE]
    # use_legacy_sensor_ids = data[CONF_USE_LEGACY_SENSOR_IDS] if CONF_USE_LEGACY_SENSOR_IDS in data else False
    # LOGGER.info("setup_internal use_legacy_sensor_ids: '%s'",
    #             use_legacy_sensor_ids)

    # Build Sensor names with local language:
    lang = (
        conf[CONF_LANGUAGE_SENSOR_NAMES]
        if CONF_LANGUAGE_SENSOR_NAMES in conf
        else LANG_DEFAULT
    )
    text_domestic_water = get_sensor_text(lang, "domestic_water")
    text_heating = get_sensor_text(lang, "heating")
    text_heatpump = get_sensor_text(lang, "heatpump")
    text_cooling = get_sensor_text(lang, "cooling")

    luxtronik = LuxtronikDevice(host, port, safe, lock_timeout)
    luxtronik.read()
    
    hass.data[DOMAIN] = luxtronik
    hass.data[f"{DOMAIN}_conf"] = conf
    
    # Create DeviceInfos:
    serial_number = luxtronik.get_value("parameters.ID_WP_SerienNummer_DATUM")
    model = luxtronik.get_value("calculations.ID_WEB_Code_WP_akt")
    
    hass.data[f"{DOMAIN}_DeviceInfo"] = build_device_info(
        luxtronik, serial_number, text_heatpump
    )
    hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"] = DeviceInfo(
        identifiers={(DOMAIN, "Domestic_Water", serial_number)},
        default_name=text_domestic_water,
        name=text_domestic_water,
        manufacturer=get_manufacturer_by_model(model),
        model=model,
    )
    hass.data[f"{DOMAIN}_DeviceInfo_Heating"] = DeviceInfo(
        identifiers={(DOMAIN, "Heating", serial_number)},
        default_name=text_heating,
        name=text_heating,
        manufacturer=get_manufacturer_by_model(model),
        model=model,
    )
    hass.data[f"{DOMAIN}_DeviceInfo_Cooling"] = (
        DeviceInfo(
            identifiers={(DOMAIN, "Cooling", serial_number)},
            default_name=text_cooling,
            name=text_cooling,
            manufacturer=get_manufacturer_by_model(model),
            model=model,
        )
        if luxtronik.get_value(LUX_SENSOR_DETECT_COOLING) > 0
        else None
    )
    return True


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the HACS config entry."""
    LOGGER.info("async_reload_entry '%s'", config_entry)
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unloading the Luxtronik platforms."""
    LOGGER.info("async_unload_entry '%s' - %s", config_entry, hass.data[DOMAIN])
    luxtronik = hass.data[DOMAIN]
    if luxtronik is None:
        return True

    try:
        await hass.async_add_executor_job(luxtronik.disconnect)

        await hass.services.async_remove(DOMAIN, SERVICE_WRITE)
    except Exception as e:
        LOGGER.critical("Remove service!", e, exc_info=True)

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN] = None
        hass.data.pop(DOMAIN)

    return unload_ok


def build_device_info(luxtronik: LuxtronikDevice, sn: str, name: str) -> DeviceInfo:
    """Build luxtronik device info."""
    model = luxtronik.get_value("calculations.ID_WEB_Code_WP_akt")
    device_info = DeviceInfo(
        identifiers={(DOMAIN, "Heatpump", sn)},  # type: ignore
        name=f"{name} S/N {sn}",
        default_name=name,
        default_manufacturer="Alpha Innotec",
        manufacturer=get_manufacturer_by_model(model),
        default_model="",
        model=model,
        sw_version=luxtronik.get_value("calculations.ID_WEB_SoftStand"),
    )
    LOGGER.debug("build_device_info '%s'", device_info)
    return device_info

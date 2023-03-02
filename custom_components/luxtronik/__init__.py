"""Support for Luxtronik heatpump controllers."""
# region Imports

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.typing import ConfigType
from luxtronik import LOGGER as LuxLogger

from .const import (
    ATTR_PARAMETER,
    ATTR_VALUE,
    CONF_LOCK_TIMEOUT,
    CONF_SAFE,
    CONF_UPDATE_IMMEDIATELY_AFTER_WRITE,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SERVICE_WRITE,
    SERVICE_WRITE_SCHEMA,
)
from .helpers.helper import get_sensor_text
from .helpers.lux_helper import (
    get_manufacturer_by_model,
    get_manufacturer_firmware_url_by_model,
)
from .luxtronik_device import LuxtronikDevice

# endregion Imports

# region Constants
LuxLogger.setLevel(level="WARNING")
# endregion Constants

@dataclass
class LuxtronikEntityDescription(EntityDescription):
    """Class describing Luxtronik entities."""

    luxtronik_key: str = ""


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

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    def logout_luxtronik(event: Event) -> None:
        """Close connections to this heatpump."""
        luxtronik.disconnect()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, logout_luxtronik)
    )
    await hass.async_add_executor_job(setup_hass_services, hass, config_entry)
    return True


def setup_hass_services(hass: HomeAssistant, config_entry: ConfigEntry):
    """Home Assistant services."""

    def write_parameter(service):
        """Write a parameter to the Luxtronik heatpump."""
        parameter = service.data.get(ATTR_PARAMETER)
        value = service.data.get(ATTR_VALUE)
        luxtronik = hass.data[DOMAIN]
        update_immediately_after_write = config_entry.data[
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
    if CONF_UPDATE_IMMEDIATELY_AFTER_WRITE not in data:
        data[CONF_UPDATE_IMMEDIATELY_AFTER_WRITE] = True
    # update_immediately_after_write = data[CONF_UPDATE_IMMEDIATELY_AFTER_WRITE]
    # use_legacy_sensor_ids = data[CONF_USE_LEGACY_SENSOR_IDS] if CONF_USE_LEGACY_SENSOR_IDS in data else False
    # LOGGER.info("setup_internal use_legacy_sensor_ids: '%s'",
    #             use_legacy_sensor_ids)

    # Build Sensor names with local language:
    lang = hass.config.language
    text_domestic_water = get_sensor_text(lang, "domestic_water")
    text_heating = get_sensor_text(lang, "heating")
    text_heatpump = get_sensor_text(lang, "heatpump")
    text_cooling = get_sensor_text(lang, "cooling")

    luxtronik = LuxtronikDevice(host, port, safe, lock_timeout)
    luxtronik.read()

    hass.data[DOMAIN] = luxtronik
    hass.data[f"{DOMAIN}_conf"] = conf

    # Create DeviceInfos:
    hass.data[f"{DOMAIN}_DeviceInfo"] = build_device_info(
        luxtronik, text_heatpump, data[CONF_HOST]
    )
    hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"] = DeviceInfo(
        identifiers={(DOMAIN, f"{luxtronik.unique_id}_domestic_water")},
        configuration_url="https://www.heatpump24.com/",
        default_name=text_domestic_water,
        name=text_domestic_water,
        manufacturer=luxtronik.manufacturer,
        model=luxtronik.model,
    )
    hass.data[f"{DOMAIN}_DeviceInfo_Heating"] = DeviceInfo(
        identifiers={(DOMAIN, f"{luxtronik.unique_id}_heating")},
        configuration_url=get_manufacturer_firmware_url_by_model(luxtronik.model),
        default_name=text_heating,
        name=text_heating,
        manufacturer=luxtronik.manufacturer,
        model=luxtronik.model,
    )
    hass.data[f"{DOMAIN}_DeviceInfo_Cooling"] = (
        DeviceInfo(
            identifiers={(DOMAIN, f"{luxtronik.unique_id}_cooling")},
            default_name=text_cooling,
            name=text_cooling,
            manufacturer=luxtronik.manufacturer,
            model=luxtronik.model,
        )
        if luxtronik.detect_cooling_present()
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

    unload_ok = False
    try:
        await hass.async_add_executor_job(luxtronik.disconnect)

        await hass.services.async_remove(DOMAIN, SERVICE_WRITE)

        unload_ok = await hass.config_entries.async_unload_platforms(
            config_entry, PLATFORMS
        )
        if unload_ok:
            hass.data[DOMAIN] = None
            hass.data.pop(DOMAIN)

    except Exception as e:
        LOGGER.critical("Remove service!", e, exc_info=True)

    return unload_ok


def build_device_info(
    luxtronik: LuxtronikDevice, name: str, ip_host: str
) -> DeviceInfo:
    """Build luxtronik device info."""
    device_info = DeviceInfo(
        identifiers={
            (
                DOMAIN,
                f"{luxtronik.unique_id}_heatpump",
            )
        },
        configuration_url=f"http://{ip_host}/",
        name=f"{name} {luxtronik.serial_number}",
        default_name=name,
        default_manufacturer="Alpha Innotec",
        manufacturer=luxtronik.manufacturer,
        default_model="",
        model=luxtronik.model,
        suggested_area="Utility room",
        sw_version=luxtronik.get_value("calculations.ID_WEB_SoftStand"),
    )
    LOGGER.debug("build_device_info '%s'", device_info)
    return device_info


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new = {**config_entry.data}
        luxtronik = LuxtronikDevice.connect(new[CONF_HOST], new[CONF_PORT])

        _delete_legacy_devices(hass, config_entry, luxtronik.unique_id)
        config_entry.unique_id = luxtronik.unique_id
        config_entry.title = f"{luxtronik.manufacturer} {luxtronik.model} {luxtronik.serial_number}"
        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new)

    LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


def _identifiers_exists(
    identifiers_list: list[set[tuple[str, str]]], identifiers: set[tuple[str, str]]
) -> bool:
    for ident in identifiers_list:
        if ident == identifiers:
            return True
    return False


def _delete_legacy_devices(hass: HomeAssistant, config_entry: ConfigEntry, unique_id: str):
    dr_instance = dr.async_get(hass)
    devices: list[dr.DeviceEntry] = dr.async_entries_for_config_entry(
        dr_instance, config_entry.entry_id
    )
    identifiers_list = list()
    identifiers_list.append({(DOMAIN, f"{unique_id}_heatpump")})
    identifiers_list.append({(DOMAIN, f"{unique_id}_domestic_water")})
    identifiers_list.append({(DOMAIN, f"{unique_id}_heating")})
    identifiers_list.append({(DOMAIN, f"{unique_id}_cooling")})
    for device in devices:
        if not _identifiers_exists(identifiers_list, device.identifiers):
            dr_instance.async_remove_device(device.id)

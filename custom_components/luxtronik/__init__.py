"""Support for Luxtronik heatpump controllers."""
# region Imports
import threading
import time
from datetime import timedelta
from typing import Optional

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (CoordinatorEntity,
                                                      DataUpdateCoordinator)
from homeassistant.util import Throttle
from luxtronik import LOGGER as LuxLogger
from luxtronik import Luxtronik as Lux

# from . import LuxtronikThermostat
from .const import (ATTR_PARAMETER, ATTR_VALUE, CONF_CALCULATIONS,
                    CONF_COORDINATOR, CONF_LOCK_TIMEOUT, CONF_PARAMETERS,
                    CONF_SAFE, CONF_UPDATE_IMMEDIATELY_AFTER_WRITE,
                    CONF_VISIBILITIES, DEFAULT_PORT, DOMAIN, LOGGER,
                    LUX_SENSOR_DETECT_COOLING, PLATFORMS)

# endregion Imports

# region Constants
LuxLogger.setLevel(level="WARNING")


SERVICE_WRITE = "write"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_SAFE, default=True): cv.boolean,
                vol.Optional(CONF_LOCK_TIMEOUT, default=30): cv.positive_int,
                vol.Optional(
                    CONF_UPDATE_IMMEDIATELY_AFTER_WRITE, default=False
                ): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_WRITE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PARAMETER): cv.string,
        vol.Required(ATTR_VALUE): vol.Any(cv.Number, cv.string),
    }
)
# endregion Constants

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from config entry."""
    hass.data.setdefault(DOMAIN, {})

    LOGGER.info("async_setup_entry '%s'", entry)

    setup_internal(hass, entry.data)

    luxtronik = hass.data[DOMAIN]

    # def _update_luxtronik_devices() -> dict[str, LuxtronikThermostat]:
    #     """Update all luxtronik device data."""
    #     data = {}
    #     luxtronik.update()

    #     data[device.ain] = device
    #     return data
        
    # async def async_update_coordinator() -> dict[str, LuxtronikThermostat]:
    #     """Fetch all device data."""
    #     return await hass.async_add_executor_job(_update_luxtronik_devices)
        
    # hass.data[DOMAIN][entry.entry_id][
    #     CONF_COORDINATOR
    # ] = coordinator = DataUpdateCoordinator(
    #     hass,
    #     LOGGER,
    #     name=f"{entry.entry_id}",
    #     update_method=async_update_coordinator,
    #     update_interval=timedelta(seconds=30),
    # )

    # await coordinator.async_config_entry_first_refresh()
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    def logout_luxtronik(event: Event) -> None:
        """Close connections to this heatpump."""
        luxtronik.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, logout_luxtronik)
    )
    return True

# async def async_setup(hass, config):


def setup(hass, config):
    if DOMAIN not in config:
        # Setup via UI. No need to continue yaml-based setup
        return True
    # LOGGER.info("async_setup '%s'", config)
    conf = config[DOMAIN]
    return setup_internal(hass, conf)


def setup_internal(hass, conf):
    """Set up the Luxtronik component."""
    host = conf[CONF_HOST]
    port = conf[CONF_PORT]
    safe = conf[CONF_SAFE]
    lock_timeout = conf[CONF_LOCK_TIMEOUT]
    update_immediately_after_write = conf[CONF_UPDATE_IMMEDIATELY_AFTER_WRITE]

    luxtronik = LuxtronikDevice(host, port, safe, lock_timeout)
    luxtronik.read()

    hass.data[DOMAIN] = luxtronik
    # Create DeviceInfos:
    sn = luxtronik.get_value('parameters.ID_WP_SerienNummer_DATUM')
    hass.data[f"{DOMAIN}_DeviceInfo"] = build_device_info(luxtronik, sn)
    hass.data[f"{DOMAIN}_DeviceInfo_Domestic_Water"] = DeviceInfo(
        identifiers={(DOMAIN, 'Domestic_Water', sn)},
        default_name='Domestic Water')
    hass.data[f"{DOMAIN}_DeviceInfo_Heating"] = DeviceInfo(
        identifiers={(DOMAIN, 'Heating', sn)},
        default_name='Heating')
    if luxtronik.get_value(LUX_SENSOR_DETECT_COOLING):
        hass.data[f"{DOMAIN}_DeviceInfo_Cooling"] = DeviceInfo(
            identifiers={(DOMAIN, 'Cooling', sn)},
            default_name='Cooling')

    def write_parameter(service):
        """Write a parameter to the Luxtronik heatpump."""
        parameter = service.data.get(ATTR_PARAMETER)
        value = service.data.get(ATTR_VALUE)
        luxtronik.write(parameter, value, update_immediately_after_write)

    # hass.services.register(
    #     DOMAIN, SERVICE_WRITE, write_parameter, schema=SERVICE_WRITE_SCHEMA
    # )

    return True


class LuxtronikDevice:
    """Handle all communication with Luxtronik."""

    def __init__(self, host, port, safe, lock_timeout_sec):
        """Initialize the Luxtronik connection."""
        self.lock = threading.Lock()

        self._host = host
        self._port = port
        self._lock_timeout_sec = lock_timeout_sec
        self._luxtronik = Lux(host, port, safe)
        self.update()

    def disconnect(self):
        self._luxtronik._disconnect()

    def get_value(self, group_sensor_id: str):
        sensor = self.get_sensor_by_id(group_sensor_id)
        if sensor is None:
            return None
        return sensor.value

    def get_sensor_by_id(self, group_sensor_id: str):
        try:
	        group = group_sensor_id.split('.')[0]
	        sensor_id = group_sensor_id.split('.')[1]
	        return self.get_sensor(group, sensor_id)
        except Exception as e:
            LOGGER.critical(group_sensor_id, e, exc_info=True)

    def get_sensor(self, group, sensor_id):
        """Get sensor by configured sensor ID."""
        sensor = None
        if group == CONF_PARAMETERS:
            sensor = self._luxtronik.parameters.get(sensor_id)
        if group == CONF_CALCULATIONS:
            sensor = self._luxtronik.calculations.get(sensor_id)
        if group == CONF_VISIBILITIES:
            sensor = self._luxtronik.visibilities.get(sensor_id)
        return sensor

    def write(self, parameter, value, update_immediately_after_write):
        """Write a parameter to the Luxtronik heatpump."""
        try:
            if self.lock.acquire(blocking=True, timeout=self._lock_timeout_sec):
                self._luxtronik.parameters.set(parameter, value)
                self._luxtronik.write()
            else:
                LOGGER.warning(
                    "Couldn't write luxtronik parameter %s with value %s because of lock timeout %s",
                    parameter,
                    value,
                    self._lock_timeout_sec,
                )
        finally:
            self.lock.release()
            if update_immediately_after_write:
                time.sleep(3)
                self._luxtronik.read()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        self.read()

    def read(self):
        """Get the data from Luxtronik."""
        try:
            if self.lock.acquire(blocking=True, timeout=self._lock_timeout_sec):
                self._luxtronik.read()
            else:
                LOGGER.warning(
                    "Couldn't read luxtronik data because of lock timeout %s",
                    self._lock_timeout_sec,
                )
        finally:
            self.lock.release()


def build_device_info(luxtronik: LuxtronikDevice, sn: str) -> DeviceInfo:
    model = luxtronik.get_value('calculations.ID_WEB_Code_WP_akt')
    deviceInfo = DeviceInfo(
        identifiers={(DOMAIN, 'Heatpump', sn)},
        name=f"Heatpump S/N {sn}",
        default_name='Heatpump',
        default_manufacturer='Alpha Innotec',
        manufacturer=get_manufacturer_by_model(model),
        default_model='',
        model=model,
        sw_version=luxtronik.get_value('calculations.ID_WEB_SoftStand')
    )
    LOGGER.info("build_device_info '%s'", deviceInfo)
    return deviceInfo


def get_manufacturer_by_model(model: str) -> str:
    if model is None:
        return None
    if model.startswith('LD'):
        return 'Novelan'
    return None


async def async_unload_entry(hass, config_entry):
    """Unloading the luxtronik platforms."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    # hass.data[DOMAIN][config_entry.entry_id][UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].disconnect()
        # hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok

"""Luxtronik device."""
# region Imports
import threading
import time

from luxtronik import Luxtronik as Lux
from homeassistant.util import Throttle

from .const import (
    CONF_CALCULATIONS,
    CONF_PARAMETERS,
    CONF_VISIBILITIES,
    LOGGER,
    MIN_TIME_BETWEEN_UPDATES,
)
from .helpers.debounce import debounce

# endregion Imports


class LuxtronikDevice:
    """Handle all communication with Luxtronik."""
    __ignore_update = False

    def __init__(self, host: str, port: int, safe: bool, lock_timeout_sec: int) -> None:
        """Initialize the Luxtronik connection."""
        self.lock = threading.Lock()

        self._host = host
        self._port = port
        self._lock_timeout_sec = lock_timeout_sec
        self._luxtronik = Lux(host, port, safe)
        self.update()

    async def async_will_remove_from_hass(self):
        """Disconnect from Luxtronik by stopping monitor."""
        self.disconnect()

    def disconnect(self):
        """Disconnect from Luxtronik. - Nothing todo - disconnected after every read!"""
        pass

    def get_value(self, group_sensor_id: str):
        """Get a sensor value from Luxtronik."""
        sensor = self.get_sensor_by_id(group_sensor_id)
        if sensor is None:
            return None
        return sensor.value

    def get_sensor_by_id(self, group_sensor_id: str):
        """Get a sensor object by id from Luxtronik."""
        try:
            group = group_sensor_id.split(".")[0]
            sensor_id = group_sensor_id.split(".")[1]
            return self.get_sensor(group, sensor_id)
        except IndexError as error:
            LOGGER.critical(group_sensor_id, error, exc_info=True)

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

    def write(
        self, parameter, value, use_debounce=True, update_immediately_after_write=False
    ):
        """Write a parameter to the Luxtronik heatpump."""
        self.__ignore_update = True
        if use_debounce:
            self.__write_debounced(parameter, value, update_immediately_after_write)
        else:
            self.__write(parameter, value, update_immediately_after_write)

    @debounce(3)
    def __write_debounced(self, parameter, value, update_immediately_after_write):
        self.__write(parameter, value, update_immediately_after_write)

    def __write(self, parameter, value, update_immediately_after_write):
        try:
            # TODO: change to "with"
            # with self.lock.acquire_timeout(self._lock_timeout_sec) as lock_result:
            if self.lock.acquire(blocking=True, timeout=self._lock_timeout_sec):
                LOGGER.info(
                    'LuxtronikDevice.write %s value: "%s" - %s',
                    parameter,
                    value,
                    update_immediately_after_write,
                )
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
                self.read()
            self.__ignore_update = False
            LOGGER.info(
                'LuxtronikDevice.write finished %s value: "%s" - %s',
                parameter,
                value,
                update_immediately_after_write,
            )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update sensor values."""
        if self.__ignore_update:
            return
        self.read()

    def read(self):
        """Get the data from Luxtronik."""
        try:
            # TODO: change to "with"
            if self.lock.acquire(blocking=True, timeout=self._lock_timeout_sec):
                self._luxtronik.read()
            else:
                LOGGER.warning(
                    "Couldn't read luxtronik data because of lock timeout %s",
                    self._lock_timeout_sec,
                )
        finally:
            self.lock.release()

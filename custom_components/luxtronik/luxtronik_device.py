"""Luxtronik device."""
# region Imports
import re
import threading
import time

from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle
from luxtronik import Luxtronik as Lux

from .const import (
    CONF_CALCULATIONS,
    CONF_PARAMETERS,
    CONF_VISIBILITIES,
    DOMAIN,
    LOGGER,
    LUX_DETECT_SOLAR_SENSOR,
    LUX_MK_SENSORS,
    LuxMkTypes,
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
 
    @property
    def has_second_heat_generator(self) -> bool:
        """Is second heat generator activated 1=electrical heater"""
        try:
            self.read()
            return int(self.get_value('parameters.ID_Einst_ZWE1Art_akt')) > 0
            # ID_Einst_ZWE1Fkt_akt = 1 --> Heating and domestic water
        except Exception:
            return False

    @property
    def has_domestic_water_circulation_pump(self) -> bool:
        """Exists a domestic water circulation pump. If not it is a domestic water charging pump"""
        try:
            self.read()
            return int(self.get_value('parameters.ID_Einst_BWZIP_akt')) != 1
        except Exception:
            return False

    def detect_cooling_Mk(self):
        """ returns list of parameters that are may show cooling is enabled """
        coolingMk = []
        for Mk in LUX_MK_SENSORS:
            sensor_value = self.get_value(Mk)
            #LOGGER.info(f"{Mk} = {sensor_value}")
            if sensor_value in [LuxMkTypes.cooling.value,
                                LuxMkTypes.heating_cooling.value]:
                coolingMk = coolingMk + [Mk]
        
        LOGGER.info(f"CoolingMk = {coolingMk}")        
        return coolingMk
        
    def detect_solar_present(self):
        sensor_value = self.get_value(LUX_DETECT_SOLAR_SENSOR)
        SolarPresent = (sensor_value > 0.01)
        LOGGER.info(f"SolarPresent = {SolarPresent}") 
        return SolarPresent

        
    def detect_cooling_present(self):  
        """ returns True if Cooling is present """
        CoolingPresent = (len(self.detect_cooling_Mk()) > 0)
        LOGGER.info(f"CoolingPresent = {CoolingPresent}") 
        return CoolingPresent
        

    def detect_cooling_target_temperature_sensor(self):
        """ if only 1 MK parameter related to cooling is returned
            return the corresponding colloing_target_temperature sensor"""
        Mk_param = self.detect_cooling_Mk()
        if len(Mk_param) == 1:
            Mk = re.findall('[0-9]+', Mk_param[0])[0]
            cooling_target_temperature_sensor = f"parameters.ID_Sollwert_KuCft{Mk}_akt"
        else:
            cooling_target_temperature_sensor = None
        LOGGER.info(f"cooling_target_temperature_sensor = '{cooling_target_temperature_sensor}' ")
        return cooling_target_temperature_sensor

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

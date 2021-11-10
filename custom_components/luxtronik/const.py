"""Constants for the Paul Novus 300 Bus integration."""
# region Imports
import logging
from datetime import timedelta
from enum import Enum
from typing import Dict, Final

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import (CONF_HOST, CONF_PORT, DEVICE_CLASS_ENERGY,
                                 DEVICE_CLASS_PRESSURE,
                                 DEVICE_CLASS_TEMPERATURE,
                                 DEVICE_CLASS_TIMESTAMP,
                                 ELECTRIC_POTENTIAL_VOLT,
                                 ENERGY_KILO_WATT_HOUR, PERCENTAGE,
                                 PRESSURE_BAR, TEMP_CELSIUS, TEMP_KELVIN,
                                 TIME_HOURS, TIME_SECONDS)

# endregion Imports

# region Constants Main
DOMAIN: Final = "luxtronik2"

LOGGER: Final[logging.Logger] = logging.getLogger(__package__)

PLATFORMS: Final[list[str]] = [
    "sensor", "binary_sensor", "climate", "number", "switch"]
# endregion Constants Main

# region Conf
CONF_SAFE: Final = "safe"
CONF_LOCK_TIMEOUT: Final = "lock_timeout"
CONF_UPDATE_IMMEDIATELY_AFTER_WRITE: Final = "update_immediately_after_write"

CONF_PARAMETERS: Final = "parameters"
CONF_CALCULATIONS: Final = "calculations"
CONF_VISIBILITIES: Final = "visibilities"

CONF_COORDINATOR: Final = "coordinator"

CONF_CONTROL_MODE_HOME_ASSISTANT: Final = "control_mode_home_assistant"
CONF_HA_SENSOR_INDOOR_TEMPERATURE: Final = "ha_sensor_indoor_temperature"
CONF_LANGUAGE_SENSOR_NAMES: Final = "language_sensor_names"

DEFAULT_PORT: Final = 8888

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

SERVICE_WRITE: Final = "write"
ATTR_PARAMETER: Final = "parameter"
ATTR_VALUE: Final = "value"

SERVICE_WRITE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PARAMETER): cv.string,
        vol.Required(ATTR_VALUE): vol.Any(cv.Number, cv.string),
    }
)

LANG_EN: Final = 'en'
LANG_DE: Final = 'de'
LANG_DEFAULT: Final = LANG_EN
LANGUAGES: Final = Enum(LANG_EN, LANG_DE)
# endregion Conf


DEFAULT_TOLERANCE: Final = 0.3


ATTR_STATUS_TEXT: Final = "status_text"


MIN_TIME_BETWEEN_UPDATES: Final = timedelta(seconds=10)


PRESET_SECOND_HEATSOURCE: Final = 'second_heatsource'

# region Lux Modes
class LuxMode(Enum):
    off: Final = 'Off'
    automatic: Final = 'Automatic'
    second_heatsource: Final = 'Second heatsource'
    party: Final = 'Party'
    holidays: Final = 'Holidays'
# endregion Lux Modes

# region Lux Status
LUX_STATUS_HEATING: Final = 'heating'                                   # 0
LUX_STATUS_DOMESTIC_WATER: Final = 'hot water'                          # 1
LUX_STATUS_SWIMMING_POOL_SOLAR: Final = 'swimming pool/solar'           # 2
LUX_STATUS_EVU: Final = 'evu'                                           # 3
LUX_STATUS_DEFROST: Final = 'defrost'                                   # 4
LUX_STATUS_NO_REQUEST: Final = 'no request'                             # 5
LUX_STATUS_HEATING_EXTERNAL_SOURCE: Final = 'heating external source'   # 6
LUX_STATUS_COOLING: Final = 'cooling'                                   # 7

LUX_STATUS_NONE: Final = 'None'
LUX_STATUS_UNKNOWN: Final = 'unknown'

LUX_STATUS1_HEATPUMP_IDLE: Final = 'heatpump idle'
LUX_STATUS1_PUMP_FORERUN: Final = 'pump forerun'
LUX_STATUS1_HEATPUMP_COMING: Final = 'heatpump coming'

LUX_STATUS3_GRID_SWITCH_ON_DELAY: Final = 'grid switch on delay'

LUX_STATES_ON: Final[list[str]] = [LUX_STATUS_HEATING, LUX_STATUS_DOMESTIC_WATER, LUX_STATUS_SWIMMING_POOL_SOLAR,
                                   LUX_STATUS_DEFROST, LUX_STATUS_HEATING_EXTERNAL_SOURCE, LUX_STATUS_COOLING]

LUX_STATUS1_WORKAROUND: Final[list[str]] = [
    LUX_STATUS1_HEATPUMP_IDLE, LUX_STATUS1_PUMP_FORERUN, LUX_STATUS1_HEATPUMP_COMING]
# LUX_STATUS_UNKNOWN, LUX_STATUS_NONE,
LUX_STATUS3_WORKAROUND: Final[list] = [
    LUX_STATUS_NO_REQUEST, LUX_STATUS_UNKNOWN, LUX_STATUS_NONE, LUX_STATUS3_GRID_SWITCH_ON_DELAY, None]
# endregion Lux Status

# region Lux Icons
LUX_STATE_ICON_MAP: Final[Dict[str, str]] = {
    LUX_STATUS_HEATING: 'mdi:radiator',
    LUX_STATUS_DOMESTIC_WATER: 'mdi:waves',
    LUX_STATUS_SWIMMING_POOL_SOLAR: None,
    LUX_STATUS_EVU: 'mdi:power-plug-off',
    LUX_STATUS_DEFROST: 'mdi:car-defrost-rear',
    LUX_STATUS_NO_REQUEST: 'mdi:radiator-disabled',
    LUX_STATUS_HEATING_EXTERNAL_SOURCE: None,
    LUX_STATUS_COOLING: 'mdi:air-conditioner'
}

ICON_ON = "mdi:check-circle-outline"
ICON_OFF = "mdi:circle-outline"
# endregion Lux Icons


# region Luxtronik Sensor ids
LUX_SENSOR_DETECT_COOLING: Final = 'calculations.ID_WEB_FreigabKuehl'
LUX_SENSOR_STATUS: Final = 'calculations.ID_WEB_WP_BZ_akt'
LUX_SENSOR_STATUS1: Final = 'calculations.ID_WEB_HauptMenuStatus_Zeile1'
LUX_SENSOR_STATUS3: Final = 'calculations.ID_WEB_HauptMenuStatus_Zeile3'

LUX_SENSOR_HEATING_TEMPERATURE_CORRECTION: Final = 'parameters.ID_Einst_WK_akt'
LUX_SENSOR_HEATING_THRESHOLD: Final = 'parameters.ID_Einst_Heizgrenze_Temp'
LUX_SENSOR_MODE_HEATING: Final = 'parameters.ID_Ba_Hz_akt'

LUX_SENSOR_DOMESTIC_WATER_CURRENT_TEMPERATURE: Final = 'calculations.ID_WEB_Temperatur_TBW'
LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE: Final = 'parameters.ID_Einst_BWS_akt'
# LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE: Final = 'calculations.ID_WEB_Einst_BWS_akt'
# LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE_WRITE: Final = 'ID_Einst_BWS_akt'
LUX_SENSOR_MODE_DOMESTIC_WATER: Final = 'parameters.ID_Ba_Bw_akt'

LUX_SENSOR_MODE_COOLING: Final = 'parameters.ID_Einst_BA_Kuehl_akt'
LUX_SENSOR_MODE_FAN: Final = 'parameters.ID_Einst_BA_Lueftung_akt'
LUX_BINARY_SENSOR_EVU_UNLOCKED: Final = 'calculations.ID_WEB_EVUin'
LUX_BINARY_SENSOR_SOLAR_PUMP: Final = 'calculations.ID_WEB_SLPout'
# LUX_SENSOR_MODE_???: Final = 'parameters.ID_Ba_Sw_akt'
LUX_SENSORS_MODE: Final[list[str]] = [LUX_SENSOR_MODE_HEATING, LUX_SENSOR_MODE_DOMESTIC_WATER,
                                      LUX_SENSOR_MODE_COOLING, LUX_SENSOR_MODE_FAN]
# endregion Luxtronik Sensor ids

# region Legacy consts
CONF_GROUP: Final = "group"
CONF_INVERT_STATE: Final = "invert"

CONF_CELSIUS: Final = "celsius"
CONF_SECONDS: Final = "seconds"
CONF_TIMESTAMP: Final = "timestamp"
CONF_KELVIN: Final = "kelvin"
CONF_BAR: Final = "bar"
CONF_PERCENT: Final = "percent"
CONF_ENERGY: Final = "energy"
CONF_HOURS: Final = "hours"
CONF_VOLTAGE: Final = "voltage"
CONF_FLOW: Final = "flow"

DEFAULT_DEVICE_CLASS: Final = None

ICONS: Final = {
    CONF_CELSIUS: "mdi:thermometer",
    CONF_SECONDS: "mdi:timer-sand",
    "pulses": "mdi:pulse",
    "ipaddress": "mdi:ip-network-outline",
    CONF_TIMESTAMP: "mdi:calendar-range",
    "errorcode": "mdi:alert-circle-outline",
    CONF_KELVIN: "mdi:thermometer",
    CONF_BAR: "mdi:arrow-collapse-all",
    CONF_PERCENT: "mdi:percent",
    "rpm": "mdi:rotate-right",
    CONF_ENERGY: "mdi:lightning-bolt-circle",
    CONF_VOLTAGE: "mdi:flash-outline",
    CONF_HOURS: "mdi:clock-outline",
    CONF_FLOW: "mdi:chart-bell-curve",
    "level": "mdi:format-list-numbered",
    "count": "mdi:counter",
    "version": "mdi:information-outline",
}

DEVICE_CLASSES: Final = {
    CONF_CELSIUS: DEVICE_CLASS_TEMPERATURE,
    CONF_KELVIN: DEVICE_CLASS_TEMPERATURE,
    CONF_BAR: DEVICE_CLASS_PRESSURE,
    CONF_SECONDS: DEVICE_CLASS_TIMESTAMP,
    CONF_HOURS: DEVICE_CLASS_TIMESTAMP,
    CONF_TIMESTAMP: DEVICE_CLASS_TIMESTAMP,
    CONF_ENERGY: DEVICE_CLASS_ENERGY,
}

UNITS: Final = {
    CONF_CELSIUS: TEMP_CELSIUS,
    CONF_SECONDS: TIME_SECONDS,
    CONF_KELVIN: TEMP_KELVIN,
    CONF_BAR: PRESSURE_BAR,
    CONF_PERCENT: PERCENTAGE,
    CONF_ENERGY: ENERGY_KILO_WATT_HOUR,
    CONF_VOLTAGE: ELECTRIC_POTENTIAL_VOLT,
    CONF_HOURS: TIME_HOURS,
    CONF_FLOW: "l/h",
}
# endregion Legacy consts

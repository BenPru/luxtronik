"""Constants for the Paul Novus 300 Bus integration."""
import logging
from typing import Dict, Final

DOMAIN: Final = "luxtronik2"

DEFAULT_PORT: Final = 8888

ATTR_PARAMETER: Final = "parameter"
ATTR_VALUE: Final = "value"

CONF_SAFE: Final = "safe"
CONF_LOCK_TIMEOUT: Final = "lock_timeout"
CONF_UPDATE_IMMEDIATELY_AFTER_WRITE: Final = "update_immediately_after_write"

CONF_PARAMETERS: Final = "parameters"
CONF_CALCULATIONS: Final = "calculations"
CONF_VISIBILITIES: Final = "visibilities"

CONF_COORDINATOR: Final = "coordinator"

LOGGER: Final[logging.Logger] = logging.getLogger(__package__)

# "binary_sensor"
PLATFORMS: Final[list[str]] = ["climate", "sensor"]

PRESET_SECOND_HEATSOURCE: Final = 'second_heatsource'

LUX_MODE_OFF: Final = 'Off'
LUX_MODE_AUTOMATIC: Final = 'Automatic'
LUX_MODE_SECOND_HEATSOURCE: Final = 'Second heatsource'
LUX_MODE_PARTY: Final = 'Party'
LUX_MODE_HOLIDAYS: Final = 'Holidays'

LUX_STATUS_HEATING: Final = 'heating'                                   # 0
LUX_STATUS_DOMESTIC_WATER: Final = 'hot water'                          # 1
LUX_STATUS_SWIMMING_POOL_SOLAR: Final = 'swimming pool/solar'           # 2
LUX_STATUS_EVU: Final = 'evu'                                           # 3
LUX_STATUS_DEFROST: Final = 'defrost'                                   # 4
LUX_STATUS_NO_REQUEST: Final = 'no request'                             # 5
LUX_STATUS_HEATING_EXTERNAL_SOURCE: Final = 'heating external source'   # 6
LUX_STATUS_COOLING: Final = 'cooling'                                   # 7

LUX_STATE_ICON_MAP: Dict[str, str] = {
    LUX_STATUS_HEATING: 'mdi:radiator',
    LUX_STATUS_DOMESTIC_WATER: 'mdi:waves',
    LUX_STATUS_SWIMMING_POOL_SOLAR: None,
    LUX_STATUS_EVU: 'mdi:power-plug-off',
    LUX_STATUS_DEFROST: 'mdi:car-defrost-rear',
    LUX_STATUS_NO_REQUEST: 'mdi:radiator-disabled',
    LUX_STATUS_HEATING_EXTERNAL_SOURCE: None,
    LUX_STATUS_COOLING: 'mdi:air-conditioner'
}

# region Luxtronik Sensor ids
LUX_SENSOR_DETECT_COOLING: Final = 'calculations.ID_WEB_FreigabKuehl'
LUX_SENSOR_STATUS: Final = 'calculations.ID_WEB_WP_BZ_akt'

LUX_SENSOR_DOMESTIC_WATER_CURRENT_TEMPERATURE: Final = 'calculations.ID_WEB_Temperatur_TBW'
LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE: Final = 'calculations.ID_WEB_Einst_BWS_akt'
LUX_SENSOR_DOMESTIC_WATER_TARGET_TEMPERATURE_WRITE: Final = 'ID_Einst_BWS_akt'
LUX_SENSOR_DOMESTIC_WATER_HEATER: Final = 'parameters.ID_Ba_Bw_akt'
# endregion Luxtronik Sensor ids

"""Constants for the Paul Novus 300 Bus integration."""
import logging
from typing import Final

DOMAIN = "luxtronik2"

DEFAULT_PORT = 8888

ATTR_PARAMETER = "parameter"
ATTR_VALUE = "value"

CONF_SAFE = "safe"
CONF_LOCK_TIMEOUT = "lock_timeout"
CONF_UPDATE_IMMEDIATELY_AFTER_WRITE = "update_immediately_after_write"

CONF_PARAMETERS = "parameters"
CONF_CALCULATIONS = "calculations"
CONF_VISIBILITIES = "visibilities"

CONF_COORDINATOR: Final = "coordinator"

LOGGER: Final[logging.Logger] = logging.getLogger(__package__)

# "binary_sensor", "sensor"
PLATFORMS: Final[list[str]] = ["climate"]

PRESET_SECOND_HEATSOURCE = 'second_heatsource'

LUX_MODE_OFF = 'Off'
LUX_MODE_AUTOMATIC = 'Automatic'
LUX_MODE_SECOND_HEATSOURCE = 'Second heatsource'
LUX_MODE_PARTY = 'Party'
LUX_MODE_HOLIDAYS = 'Holidays'

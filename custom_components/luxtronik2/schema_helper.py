from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_HOST,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
)


def build_user_data_schema(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = DEFAULT_TIMEOUT,
    max_data_length: int = DEFAULT_MAX_DATA_LENGTH,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): int,
            vol.Optional(CONF_TIMEOUT, default=timeout): vol.Coerce(float),
            vol.Optional(CONF_MAX_DATA_LENGTH, default=max_data_length): int,
        }
    )


def build_options_schema(
    current_value: str | None = None,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_HA_SENSOR_INDOOR_TEMPERATURE,
                default=current_value,
                description={"suggested_value": current_value},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="temperature"
                )
            ),
        }
    )

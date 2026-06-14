from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_MAX_DATA_LENGTH,
    CONF_UPDATE_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL,
    UPDATE_INTERVAL_OPTIONS,
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
    current_indoor_temp: str | None = None,
    current_interval: str | None = None,
) -> vol.Schema:
    interval_options = [
        selector.SelectOptionDict(value=k, label=k) for k in UPDATE_INTERVAL_OPTIONS
    ]
    return vol.Schema(
        {
            vol.Optional(
                CONF_HA_SENSOR_INDOOR_TEMPERATURE,
                default=current_indoor_temp,
                description={"suggested_value": current_indoor_temp},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="temperature"
                )
            ),
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=current_interval or DEFAULT_UPDATE_INTERVAL,
                description={
                    "suggested_value": current_interval or DEFAULT_UPDATE_INTERVAL
                },
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=interval_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )

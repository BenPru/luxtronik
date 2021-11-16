"""Config flow to configure the Luxtronik heatpump controller integration."""
# region Imports
from __future__ import annotations

from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.dhcp import HOSTNAME, IP_ADDRESS
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (CONF_CONTROL_MODE_HOME_ASSISTANT,
                    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
                    CONF_LANGUAGE_SENSOR_NAMES, CONF_LOCK_TIMEOUT, CONF_SAFE,
                    CONF_UPDATE_IMMEDIATELY_AFTER_WRITE,
                    DEFAULT_PORT, DOMAIN,
                    LANG_DEFAULT, LANGUAGES_SENSOR_NAMES, LOGGER)
from .helpers.lux_helper import discover

# endregion Imports


class LuxtronikFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Luxtronik heatpump controller config flow."""

    VERSION = 1
    _hassio_discovery = None
    _discovery_host = None
    _discovery_port = None

    def _get_schema(self):
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._discovery_host): str,
                vol.Required(CONF_PORT, default=self._discovery_port): int,
                vol.Optional(CONF_CONTROL_MODE_HOME_ASSISTANT, default=False): bool,
                # vol.Optional(CONF_USE_LEGACY_SENSOR_IDS, default=False): bool,
                vol.Optional(CONF_HA_SENSOR_INDOOR_TEMPERATURE, default=''): str,
                vol.Optional(CONF_LANGUAGE_SENSOR_NAMES, default=LANG_DEFAULT): vol.In(LANGUAGES_SENSOR_NAMES),
            }
        )

    async def async_step_dhcp(self, discovery_info: dict):
        """Prepare configuration for a DHCP discovered Luxtronik heatpump."""
        LOGGER.info("Found device with hostname '%s' IP '%s'",
                    discovery_info.get(HOSTNAME), discovery_info[IP_ADDRESS])
        # Validate dhcp result with socket broadcast:
        broadcast_discover_ip, broadcast_discover_port = discover()
        if broadcast_discover_ip != discovery_info[IP_ADDRESS]:
            return
        await self.async_set_unique_id(discovery_info.get(HOSTNAME))
        self._abort_if_unique_id_configured()

        self._discovery_host = discovery_info[IP_ADDRESS]
        self._discovery_port = DEFAULT_PORT if broadcast_discover_port is None else broadcast_discover_port
        self.discovery_schema = self._get_schema()
        return await self.async_step_user()

    async def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema(),
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        data = {
            CONF_HOST: user_input[CONF_HOST],
            CONF_PORT: user_input[CONF_PORT],
            CONF_SAFE: False,
            CONF_LOCK_TIMEOUT: 30,
            CONF_UPDATE_IMMEDIATELY_AFTER_WRITE: True,
            CONF_CONTROL_MODE_HOME_ASSISTANT: user_input[CONF_CONTROL_MODE_HOME_ASSISTANT],
            # CONF_USE_LEGACY_SENSOR_IDS: user_input[CONF_USE_LEGACY_SENSOR_IDS],
            CONF_HA_SENSOR_INDOOR_TEMPERATURE: user_input[CONF_HA_SENSOR_INDOOR_TEMPERATURE],
            CONF_LANGUAGE_SENSOR_NAMES: user_input[CONF_LANGUAGE_SENSOR_NAMES]
        }
        self._async_abort_entries_match(data)

        errors = {}
        return self.async_create_entry(title=user_input[CONF_HOST], data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return LuxtronikOptionsFlowHandler(config_entry)


class LuxtronikOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a Luxtronik options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry

    def _get_value(self, key: str, default=None):
        return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

    def _get_options_schema(self):
        """Return a schema for Luxtronik configuration options."""
        return vol.Schema(
            {
                vol.Optional(CONF_CONTROL_MODE_HOME_ASSISTANT, default=self._get_value(CONF_CONTROL_MODE_HOME_ASSISTANT, False)): bool,
                # vol.Optional(CONF_USE_LEGACY_SENSOR_IDS, default=self._get_value(CONF_USE_LEGACY_SENSOR_IDS, False)): bool,
                vol.Optional(CONF_HA_SENSOR_INDOOR_TEMPERATURE, default=self._get_value(CONF_HA_SENSOR_INDOOR_TEMPERATURE, '')): str,
                vol.Optional(CONF_LANGUAGE_SENSOR_NAMES, default=self._get_value(CONF_LANGUAGE_SENSOR_NAMES, LANG_DEFAULT)): vol.In(LANGUAGES_SENSOR_NAMES),
            }
        )

    async def async_step_init(self, _user_input=None):
        """Manage the options."""
        return await self.async_step_user(_user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="user", data_schema=self._get_options_schema())

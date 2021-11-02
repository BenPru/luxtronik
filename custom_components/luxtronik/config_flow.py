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
                    CONF_HA_SENSOR_INDOOR_TEMPERATURE, CONF_LOCK_TIMEOUT,
                    CONF_SAFE, CONF_UPDATE_IMMEDIATELY_AFTER_WRITE,
                    DEFAULT_PORT, DOMAIN, LOGGER)
from .helpers.lux_helper import discover

# endregion Imports


class LuxtronikFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Luxtronik heatpump controller config flow."""

    VERSION = 1
    _hassio_discovery = None
    _discovery_host = None
    _discovery_port = None

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
        self.discovery_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._discovery_host): str,
                vol.Required(CONF_PORT, default=self._discovery_port): int,
            }
        )
        return await self.async_step_user()

    async def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._discovery_host): cv.string,
                    vol.Required(CONF_PORT, default=self._discovery_port): vol.Coerce(int),
                }
            ),
            errors=errors or {},
        )

    async def _show_hassio_form(
        self, errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the Hass.io confirmation form to the user."""
        assert self._hassio_discovery
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={
                "addon": self._hassio_discovery["addon"]},
            data_schema=vol.Schema({}),
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        self._async_abort_entries_match(
            {CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT]}
        )

        errors = {}

        return self.async_create_entry(
            # title="Luxtronik",
            title=user_input[CONF_HOST],
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_SAFE: False,
                CONF_LOCK_TIMEOUT: 30,
                CONF_UPDATE_IMMEDIATELY_AFTER_WRITE: True
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return LuxtronikOptionsFlowHandler(config_entry)

class LuxtronikOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a Luxtronik options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry

    def luxtronik_config_option_schema(self, options: dict = {}) -> dict:
        """Return a schema for Luxtronik configuration options."""
        if not options:
            options = {
                CONF_CONTROL_MODE_HOME_ASSISTANT: False,
                CONF_HA_SENSOR_INDOOR_TEMPERATURE: ''
            }
        return {
            vol.Optional(CONF_CONTROL_MODE_HOME_ASSISTANT, default=options.get(CONF_CONTROL_MODE_HOME_ASSISTANT)): bool,
            vol.Optional(CONF_HA_SENSOR_INDOOR_TEMPERATURE, default=options.get(CONF_HA_SENSOR_INDOOR_TEMPERATURE)): str,
        }

    async def async_step_init(self, _user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # if self.hacs.configuration is None:
        #     return self.async_abort(reason="not_setup")

        schema = self.luxtronik_config_option_schema(self.config_entry.options)
        return self.async_show_form(step_id="user", data_schema=vol.Schema(schema))

        # option_schema_control_mode_luxtronik = self._get_option_schema_control_mode_luxtronik()

        # if user_input is None:
        #     return self.async_show_form(
        #         step_id="init",
        #         data_schema=option_schema_control_mode_luxtronik,
        #         errors={},
        #     )

        # control_mode_luxtronik = user_input.get(CONF_CONTROL_MODE_LUXTRONIK)

        # if not self._are_prefixes_valid(control_mode_luxtronik):
        #     return self.async_show_form(
        #         step_id="init",
        #         data_schema=option_schema_control_mode_luxtronik,
        #         errors={"base": RESULT_MALFORMED_PREFIXES},
        #     )

        # return self.async_create_entry(
        #     title="", data={CONF_PREFIXES: self._get_list_of_prefixes(control_mode_luxtronik)}
        # )

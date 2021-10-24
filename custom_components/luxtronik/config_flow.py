"""Config flow to configure the Luxtronik heatpump controller integration."""
# region Imports
from __future__ import annotations
import logging

from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.components.dhcp import HOSTNAME, IP_ADDRESS

from .const import DEFAULT_PORT, DOMAIN, CONF_SAFE, CONF_LOCK_TIMEOUT, CONF_UPDATE_IMMEDIATELY_AFTER_WRITE


_LOGGER = logging.getLogger(__name__)
# endregion Imports


class LuxtronikFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Luxtronik heatpump controller config flow."""

    VERSION = 1
    _hassio_discovery = None
    discovery_host = None

    async def async_step_dhcp(self, discovery_info: dict):
        """Prepare configuration for a DHCP discovered Luxtronik heatpump."""
        _LOGGER.info("Found device with hostname '%s' IP '%s'", discovery_info.get(HOSTNAME), discovery_info[IP_ADDRESS])
        await self.async_set_unique_id(discovery_info.get(HOSTNAME))
        self._abort_if_unique_id_configured()

        self.discovery_host = discovery_info[IP_ADDRESS]
        self.discovery_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=discovery_info[IP_ADDRESS]): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
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
                    vol.Required(CONF_HOST, default=self.discovery_host): cv.string,
                    # vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
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
            description_placeholders={"addon": self._hassio_discovery["addon"]},
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
            {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
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

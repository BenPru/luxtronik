"""Config flow to configure the Luxtronik heatpump controller integration."""
# region Imports
from __future__ import annotations
from typing import Any
import socket

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.components.dhcp import HOSTNAME, IP_ADDRESS

from .const import LOGGER, DEFAULT_PORT, DOMAIN, CONF_SAFE, CONF_LOCK_TIMEOUT, CONF_UPDATE_IMMEDIATELY_AFTER_WRITE
# endregion Imports


class LuxtronikFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Luxtronik heatpump controller config flow."""

    VERSION = 1
    _hassio_discovery = None
    _discovery_host = None
    _discovery_port = None

    def discover(self):
        """Broadcast discovery for luxtronik heatpumps."""

        for p in (4444, 47808):
            LOGGER.debug(f"Send discovery packets to port {p}")
            server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            server.bind(("", p))
            server.settimeout(2)

            # send AIT magic brodcast packet
            data = "2000;111;1;\x00"
            server.sendto(data.encode(), ("<broadcast>", p))
            LOGGER.debug(f"Sending broadcast request \"{data.encode()}\"")

            while True:
                try:
                    res, con = server.recvfrom(1024)
                    res = res.decode("ascii", errors="ignore")
                    # if we receive what we just sent, continue
                    if res == data:
                        continue
                    ip = con[0]
                    # if the response starts with the magic nonsense
                    if res.startswith("2500;111;"):
                        res = res.split(";")
                        LOGGER.debug(f"Received answer from {ip} \"{res}\"")
                        try:
                            port = int(res[2])
                        except ValueError:
                            LOGGER.debug("Response did not contain a valid port number, an old Luxtronic software version might be the reason.")
                            port = None
                        return (ip, port)
                    # if not, continue
                    else:
                        LOGGER.debug(f"Received answer, but with wrong magic bytes, from {ip} skip this one")
                        continue
                # if the timout triggers, go on an use the other broadcast port
                except socket.timeout:
                    break

    async def async_step_dhcp(self, discovery_info: dict):
        """Prepare configuration for a DHCP discovered Luxtronik heatpump."""
        LOGGER.info("Found device with hostname '%s' IP '%s'", discovery_info.get(HOSTNAME), discovery_info[IP_ADDRESS])
        # Validate dhcp result with socket broadcast:
        broadcast_discover_ip, broadcast_discover_port = self.discover()
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
                    # vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
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

"""Config flow to configure the Luxtronik heatpump controller integration."""

# region Imports
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector
from homeassistant import config_entries
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult, AbortFlow
from homeassistant.helpers import selector

from .const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_HOST,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGGER,
)
from .coordinator import LuxtronikCoordinator
from .lux_helper import discover
from .schema_helper import build_user_data_schema, build_options_schema

# endregion Imports

async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    # Check if there are any devices that can be discovered in the network.
    device_list = await hass.async_add_executor_job(discover)
    return device_list is not None and len(device_list) > 0


class LuxtronikFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Luxtronik heatpump controller config flow."""

    VERSION = 8
    _discovery_host = None
    _discovery_port = None

    _sensor_prefix = DOMAIN
    _title = "Luxtronik"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        try:
            LOGGER.info("Starting async_step_user")

            device_list = await self.hass.async_add_executor_job(discover)
            LOGGER.info("Discovered devices: %s", device_list)

            configured_hosts_ports = {
                (entry.data.get(CONF_HOST), entry.data.get(CONF_PORT))
                for entry in self._async_current_entries()
            }
            LOGGER.info("Already configured devices: %s", configured_hosts_ports)

            self._all_devices = [
                {
                    "host": host,
                    "port": port,
                    "configured": (host, port) in configured_hosts_ports
                }
                for host, port in device_list
            ]
            LOGGER.info("All devices with config status: %s", self._all_devices)

            self._available_devices = [
                d for d in self._all_devices #if not d["configured"]
            ]
            LOGGER.info("Available (unconfigured) devices: %s", self._available_devices)

            if self._available_devices:
                device_options = {
                    f"{d['host']}:{d['port']}": f"{d['host']}:{d['port']}"
                    for d in self._available_devices
                }
                LOGGER.info("Presenting selection form for available devices")
                LOGGER.info(f"device_options={device_options}")

                device_options_list = list(device_options.values())

                return self.async_show_form(
                    step_id="select_devices",
                    data_schema=vol.Schema({
                        vol.Required("selected_devices", default=[]): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=device_options_list,
                                multiple=True,
                                mode=selector.SelectSelectorMode.DROPDOWN
                            )
                        )
                    }),
                    description_placeholders={
                        "configured": ", ".join(
                            f"{d['host']}:{d['port']}" for d in self._all_devices if d["configured"]
                        )
                    }
                )
            else:
                LOGGER.info("All discovered devices are already configured. Showing manual entry form.")
                return self.async_show_form(
                    step_id="manual_entry",
                    data_schema = build_user_data_schema(),
                    title_placeholders={
                        "host": user_input.get(CONF_HOST, "unknown"),
                        "port": user_input.get(CONF_PORT, DEFAULT_PORT),
                    }                    
                )

        except Exception as err:
            LOGGER.error(
                "Could not handle config_flow.async_step_user",
                exc_info=err,
            )
            return self.async_abort(reason="unknown")

    async def async_step_select_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user selection of discovered devices."""
        if user_input is None:
            return await self.async_step_user()

        selected = user_input.get("selected_devices", [])

        for device_str in selected:
            host, port = device_str.split(":")
            config = {
                CONF_HOST: host,
                CONF_PORT: int(port),
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
                CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
            }

            try:
                coordinator = LuxtronikCoordinator.connect(self.hass, config)
                await self.async_set_unique_id(coordinator.unique_id)
                self._abort_if_unique_id_configured()

                self.hass.async_create_task(
                    self.async_create_entry(
                        title=f"{host}:{port}",
                        data=config,
                    )
                )

            except AbortFlow:
                LOGGER.debug("Device already configured: %s", config[CONF_HOST])
                continue  # Skip this device

            except Exception as err:
                LOGGER.error("Failed to connect to %s:%s during selection: %s", host, port, err)
                continue  # Skip this device

        return self.async_abort(reason="devices_configured")

    async def async_step_manual_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual entry of host and port."""
        if user_input is None:
            LOGGER.info("Showing manual entry form")
            return self.async_show_form(
                step_id="manual_entry",
                data_schema=build_user_data_schema()
            )

        try:
            coordinator = LuxtronikCoordinator.connect(self.hass, user_input)
            await self.async_set_unique_id(coordinator.unique_id)
            self._abort_if_unique_id_configured()

        except AbortFlow:
            LOGGER.debug("Device already configured: %s", user_input[CONF_HOST])
            return self.async_abort(reason="already_configured")

        except Exception as err:
            LOGGER.error("Failed to connect during manual entry: %s", err)
            return self.async_abort(reason="cannot_connect")

        LOGGER.info("Creating entry from manual input: %s", user_input)
        return self.async_create_entry(
            title=f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
            data=user_input,
        )

    async def _async_migrate_data_from_custom_component_luxtronik2(self):
        """
        Migrate custom_components/luxtronik2 to components/luxtronik.

            - If serial number matches
            1. Set CONF_HA_SENSOR_PREFIX = "luxtronik2"
            2. Disable custom_components/luxtronik2
        """
        # Check if custom_component_luxtronik2 exists:
        try:
            for legacy_entry in self.hass.config_entries.async_entries("luxtronik2"):
                if (
                    CONF_HOST not in legacy_entry.data
                    or CONF_PORT not in legacy_entry.data
                ):
                    continue
                try:
                    # Try to connect and lookup serial number:
                    coord_legacy = LuxtronikCoordinator.connect(self.hass, legacy_entry)
                    if self.context["unique_id"] == coord_legacy.unique_id:
                        # Match Found! --> Migrate
                        # How to use .INTEGRATION or other instead of .USER?
                        legacy_entry.disabled_by = (
                            config_entries.ConfigEntryDisabler.USER
                        )
                        self.hass.config_entries.async_update_entry(legacy_entry)
                        await self.hass.config_entries.async_reload(
                            legacy_entry.entry_id
                        )
                        self.context["data"][CONF_HA_SENSOR_PREFIX] = "luxtronik2"
                        if (
                            hasattr(legacy_entry, "data")
                            and CONF_HA_SENSOR_INDOOR_TEMPERATURE in legacy_entry.data
                        ):
                            self.context["data"][CONF_HA_SENSOR_INDOOR_TEMPERATURE] = (
                                legacy_entry.data[CONF_HA_SENSOR_INDOOR_TEMPERATURE]
                            )
                        return
                except Exception:  # pylint: disable=broad-except
                    continue
        except Exception as err:
            LOGGER.error(
                "Could not handle config_flow._async_migrate_data_from_custom_component_luxtronik2",
                exc_info=err,
            )

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> FlowResult:
        """Prepare configuration for a DHCP discovered Luxtronik heatpump."""
        try:
            LOGGER.info(
                "DHCP discovery: hostname='%s', IP='%s'",
                discovery_info.hostname,
                discovery_info.ip,
            )

            # Run discover in executor to avoid blocking
            heatpump_list = await self.hass.async_add_executor_job(discover)

            # Match discovered IP
            matched = next(
                ((host, port) for host, port in heatpump_list if host == discovery_info.ip),
                None
            )

            if not matched:
                LOGGER.warning("No matching device found for DHCP IP: %s", discovery_info.ip)
                return self.async_abort(reason="no_devices_found")

            host, port = matched
            config = {
                CONF_HOST: host,
                CONF_PORT: port or DEFAULT_PORT,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
                CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
            }

            try:
                coordinator = LuxtronikCoordinator.connect(self.hass, config)
            except Exception as err:
                LOGGER.error("DHCP connection failed: %s", err)
                return self.async_abort(reason="cannot_connect")

            await self.async_set_unique_id(coordinator.unique_id)
            self._abort_if_unique_id_configured()

            # Store for use in user step
            self._discovery_host = host
            self._discovery_port = port or DEFAULT_PORT

            return await self.async_step_user()

        except Exception as err:
            LOGGER.error("Unhandled DHCP discovery error", exc_info=err)
            return self.async_abort(reason="unknown")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get default options flow."""
        from .config_flow import LuxtronikOptionsFlowHandler
        return LuxtronikOptionsFlowHandler(config_entry)


class LuxtronikOptionsFlowHandler(config_entries.OptionsFlowWithConfigEntry):
    """Handle a Luxtronik options flow."""

    _sensor_prefix = DOMAIN

    def _get_value(self, key: str, default=None):
        """Return a value from Luxtronik."""
        return self.options.get(key, self.config_entry.data.get(key, default))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start the options flow."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the user options step."""
        try:
            LOGGER.info(f'user_input={user_input}')        
            if user_input is not None:
                # Update options with new values, handling removal
                new_options = dict(self.options)
                for key in [CONF_HA_SENSOR_INDOOR_TEMPERATURE]:
                    value = user_input.get(key)
                    if value:
                        new_options[key] = value
                    elif key in new_options:
                        del new_options[key]
                LOGGER.info(f'new_options={new_options}')
                # Save updated options
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    options=new_options,
                )

                # Reload the config entry to apply changes immediately
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                return self.async_create_entry(title="", data={})

            try:
                coordinator = LuxtronikCoordinator.connect(self.hass, self.config_entry)
            except Exception as err:
                LOGGER.error("Failed to connect during options flow: %s", err)
                return self.async_abort(reason="cannot_connect")

            # Show form with current value
            title = f"{coordinator.manufacturer} {coordinator.model} {coordinator.serial_number}"
            name = f"{title} ({self.config_entry.data[CONF_HOST]}:{self.config_entry.data[CONF_PORT]})"

            return self.async_show_form(
                step_id="user",
                data_schema=build_options_schema(
                    current_value=self._get_value(CONF_HA_SENSOR_INDOOR_TEMPERATURE)
                ),
                description_placeholders={"name": name},
            )

        except Exception as err:
            LOGGER.error(
                "Could not handle LuxtronikOptionsFlowHandler.async_step_user: %s",
                user_input,
                exc_info=err,
            )
            return self.async_abort(reason="options_error")

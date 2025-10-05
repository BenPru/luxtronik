"""Config flow to configure the Luxtronik heatpump controller integration."""

# region Imports
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult, AbortFlow
from homeassistant.helpers import selector

from .const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    CONFIG_ENTRY_VERSION,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGGER,
)
from .coordinator import (
    LuxtronikCoordinator,
    connect_and_get_coordinator,
    LuxtronikConnectionError,
)
from .lux_helper import discover
from .schema_helper import build_user_data_schema, build_options_schema

# endregion Imports

SELECT_DEVICE_LABEL = "select_device_to_configure"


class LuxtronikFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Luxtronik heatpump controller config flow."""

    VERSION = CONFIG_ENTRY_VERSION
    _discovery_host = None
    _discovery_port = None

    _sensor_prefix = DOMAIN
    _title = "Luxtronik"

    def _build_config(self, host: str, port: int) -> dict[str, Any]:
        return {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
        }

    async def _discover_devices(self) -> list[tuple[str, int]]:
        """Run device discovery in executor."""
        return await self.hass.async_add_executor_job(discover)

    async def _set_unique_id_or_abort(
        self, coordinator: LuxtronikCoordinator, config: dict[str, Any]
    ) -> bool:
        """Set unique ID and abort if already configured."""
        try:
            await self.async_set_unique_id(coordinator.unique_id)
            self._abort_if_unique_id_configured()

            return True
        except AbortFlow:
            LOGGER.debug("Device already configured: %s", config[CONF_HOST])
            return False

    def _create_entry(
        self, config: dict[str, Any], coordinator: LuxtronikCoordinator
    ) -> FlowResult:
        if CONF_HA_SENSOR_PREFIX not in config:
            config[CONF_HA_SENSOR_PREFIX] = f"luxtronik_{coordinator.unique_id}"

        if coordinator.manufacturer is not None:
            title = (
                f"{coordinator.manufacturer} @ {config[CONF_HOST]}:{config[CONF_PORT]}"
            )
        else:
            title = f"Luxtronik @ {config[CONF_HOST]}:{config[CONF_PORT]}"

        return self.async_create_entry(
            title=title,
            data=config,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        try:
            LOGGER.info("Starting async_step_user")
            await self._async_migrate_data_from_custom_component_luxtronik2()

            LOGGER.info("Starting discovery of Luxtronik devices on network")
            device_list = await self._discover_devices()

            configured_hosts_ports = {
                (entry.data.get(CONF_HOST), entry.data.get(CONF_PORT))
                for entry in self._async_current_entries()
            }

            self._all_devices = [
                {
                    "host": host,
                    "port": port,
                    "configured": (host, port) in configured_hosts_ports,
                }
                for host, port in device_list
            ]
            LOGGER.info(
                "All discovered devices with config status: %s", self._all_devices
            )

            self._available_devices = [
                d for d in self._all_devices if not d["configured"]
            ]
            LOGGER.info("Available (unconfigured) devices: %s", self._available_devices)

            if self._available_devices:
                device_options_list = [
                    f"{d['host']}:{d['port']}" for d in self._available_devices
                ]

                LOGGER.info("Presenting selection form for available devices")
                LOGGER.info(f"device_options_list={device_options_list}")

                return self.async_show_form(
                    step_id="select_devices",
                    data_schema=vol.Schema(
                        {
                            vol.Required(SELECT_DEVICE_LABEL): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=device_options_list,
                                    multiple=False,  # ✅ Only one device selectable
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            )
                        }
                    ),
                    description_placeholders={
                        "configured": ", ".join(
                            f"{d['host']}:{d['port']}"
                            for d in self._all_devices
                            if d["configured"]
                        )
                    },
                )

            else:
                LOGGER.info(
                    "All discovered devices are already configured. Showing manual entry form."
                )
                return self.async_show_form(
                    step_id="manual_entry", data_schema=build_user_data_schema()
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
        """Handle user selection of a discovered device."""
        if user_input is None:
            return await self.async_step_user()

        device_str = user_input.get(SELECT_DEVICE_LABEL)
        host, port = device_str.split(":")
        config = self._build_config(host, int(port))

        try:
            coordinator = await connect_and_get_coordinator(self.hass, config)
        except LuxtronikConnectionError as err:
            return self.async_abort(
                reason="cannot_connect",
                description_placeholders={
                    "host": err.host,
                    "connect_error": str(err.original),
                },
            )

        if not await self._set_unique_id_or_abort(coordinator, config):
            return self.async_abort(reason="already_configured")

        return self._create_entry(config, coordinator)

    async def async_step_manual_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual entry of host and port."""
        if user_input is None:
            LOGGER.info("Showing manual entry form")
            return self.async_show_form(
                step_id="manual_entry", data_schema=build_user_data_schema()
            )

        config = self._build_config(user_input[CONF_HOST], int(user_input[CONF_PORT]))

        try:
            coordinator = await connect_and_get_coordinator(self.hass, config)
        except LuxtronikConnectionError as err:
            return self.async_abort(
                reason="cannot_connect",
                description_placeholders={
                    "host": err.host,
                    "connect_error": str(err.original),
                },
            )

        if not await self._set_unique_id_or_abort(coordinator, config):
            return self.async_abort(reason="already_configured")

        return self._create_entry(config, coordinator)

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
                    coord_legacy = await connect_and_get_coordinator(
                        self.hass, legacy_entry
                    )
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
                "DHCP discovered a possible Luxtronik device '%s' @ '%s'",
                discovery_info.hostname,
                discovery_info.ip,
            )

            configured_hosts = {
                entry.data.get(CONF_HOST) for entry in self._async_current_entries()
            }

            # Check if IP is already configured
            if discovery_info.ip in configured_hosts:
                LOGGER.info(
                    "DHCP IP '%s' is already configured as Luxtronik device, aborting.",
                    discovery_info.ip,
                )
                return self.async_abort(reason="already_configured")

            heatpump_list = await self._discover_devices()

            # Check if DHCP device was also discovered as Luxtronik device
            matched = next(
                (
                    (host, port)
                    for host, port in heatpump_list
                    if host == discovery_info.ip
                ),
                None,
            )

            host, port = matched if matched else (discovery_info.ip, DEFAULT_PORT)

            if matched:
                LOGGER.info(
                    "DHCP device '%s:%s' not yet configured, and recognized as Luxtronik device!",
                    host,
                    port,
                )
            else:
                LOGGER.warning(
                    "DHCP IP: %s was not discovered as being a Luxtronik device. Will try to connect anyway, using default port %s",
                    discovery_info.ip,
                    DEFAULT_PORT,
                )

            config = self._build_config(host, int(port))

            try:
                coordinator = await connect_and_get_coordinator(self.hass, config)
            except LuxtronikConnectionError as err:
                return self.async_abort(
                    reason="cannot_connect",
                    description_placeholders={
                        "host": err.host,
                        "connect_error": str(err.original),
                    },
                )

            if not await self._set_unique_id_or_abort(coordinator, config):
                return self.async_abort(reason="already_configured")

            return self._create_entry(config, coordinator)

        except Exception as err:
            LOGGER.error("Unhandled DHCP discovery error", exc_info=err)
            return self.async_abort(reason="unknown")

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user options step."""
        try:
            LOGGER.info("user_input: %s", user_input)

            new_options = dict(self.options)

            if user_input is not None:
                # User submitted the form
                value = user_input.get(CONF_HA_SENSOR_INDOOR_TEMPERATURE)
                if value:
                    new_options[CONF_HA_SENSOR_INDOOR_TEMPERATURE] = value
                elif CONF_HA_SENSOR_INDOOR_TEMPERATURE in new_options:
                    new_options[CONF_HA_SENSOR_INDOOR_TEMPERATURE] = None

                LOGGER.info("new_options: %s", new_options)

                # Merge options from user_input into data
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=self.config_entry.data | user_input,
                    options=new_options,
                )

                # Reload the config entry to apply changes immediately
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                return self.async_create_entry(title="", data={})

            # User opened the form but didn't submit anything

            config = {
                CONF_HOST: self.config_entry.data.get(CONF_HOST),
                CONF_PORT: self.config_entry.data.get(CONF_PORT, DEFAULT_PORT),
                CONF_TIMEOUT: self.config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                CONF_MAX_DATA_LENGTH: self.config_entry.data.get(
                    CONF_MAX_DATA_LENGTH, DEFAULT_MAX_DATA_LENGTH
                ),
            }

            try:
                coordinator = await connect_and_get_coordinator(self.hass, config)
            except LuxtronikConnectionError as err:
                return self.async_abort(
                    reason="cannot_connect",
                    description_placeholders={
                        "host": err.host,
                        "connect_error": str(err.original),
                    },
                )

            # Show form with current value
            title = f"{coordinator.manufacturer} {coordinator.model} {coordinator.serial_number}"
            name = f"{title} ({self.config_entry.data[CONF_HOST]}:{self.config_entry.data[CONF_PORT]})"
            current_value = self._get_value(CONF_HA_SENSOR_INDOOR_TEMPERATURE)

            return self.async_show_form(
                step_id="user",
                data_schema=build_options_schema(current_value=current_value),
                description_placeholders={"name": name},
            )

        except Exception as err:
            LOGGER.error(
                "Could not handle LuxtronikOptionsFlowHandler.async_step_user: %s",
                user_input,
                exc_info=err,
            )
            return self.async_abort(reason="options_error")

"""Config flow to configure the Luxtronik heatpump controller integration."""

# region Imports
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import selector
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
import voluptuous as vol

from .const import (
    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    CONF_UPDATE_INTERVAL,
    CONFIG_ENTRY_VERSION,
    DEFAULT_HOST,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL_OPTION,
    DOMAIN,
    LOGGER,
)
from .coordinator import (
    LuxtronikConnectionError,
    LuxtronikCoordinator,
    LuxtronikSerialNumberError,
    connect_and_get_coordinator,
)
from .lux_helper import discover
from .schema_helper import build_options_schema, build_user_data_schema

# endregion Imports

SELECT_DEVICE_LABEL = "select_device_to_configure"
MANUAL_ENTRY_VALUE = "__manual_entry__"


class LuxtronikFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Luxtronik heatpump controller config flow."""

    VERSION = CONFIG_ENTRY_VERSION

    def __init__(self) -> None:
        """Initialize the config flow with per-instance discovery state.

        Must not be class-level: two flows running concurrently (e.g. two
        users, or discovery + manual entry at the same time) would otherwise
        share the same discovered-device lists.
        """
        super().__init__()
        self._all_devices: list[dict[str, Any]] = []
        self._available_devices: list[dict[str, Any]] = []

    def _build_config(
        self,
        host: str,
        port: int,
        timeout: float = DEFAULT_TIMEOUT,
        max_data_length: int = DEFAULT_MAX_DATA_LENGTH,
    ) -> dict[str, Any]:
        return {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_TIMEOUT: timeout,
            CONF_MAX_DATA_LENGTH: max_data_length,
        }

    async def _discover_devices(self) -> list[tuple[str, int | None]]:
        """Run device discovery in executor.

        Enumerates every enabled IPv4 adapter via HA's network helper, vs
        just the default adapter we'd get if we passed ``255.255.255.255``.
        """
        broadcasts = await network.async_get_ipv4_broadcast_addresses(self.hass)
        broadcast_addresses = [str(addr) for addr in broadcasts]
        return await self.hass.async_add_executor_job(discover, broadcast_addresses)

    async def _set_unique_id_or_abort(
        self, coordinator: LuxtronikCoordinator, config: dict[str, Any]
    ) -> ConfigFlowResult | None:
        """Set unique ID, returning an abort result if the flow should stop.

        Returns None if the flow should proceed to create/update the entry.
        """
        try:
            await self.async_set_unique_id(coordinator.unique_id)
            self._abort_if_unique_id_configured()
            return None
        except AbortFlow:
            LOGGER.debug("Device already configured: %s", config[CONF_HOST])
            return self.async_abort(reason="already_configured")
        except LuxtronikSerialNumberError as err:
            LOGGER.error("Could not identify device at %s: %s", config[CONF_HOST], err)
            return self.async_abort(
                reason="cannot_identify",
                description_placeholders={
                    "host": config[CONF_HOST],
                    "error": str(err),
                },
            )

    def _create_entry(
        self, config: dict[str, Any], coordinator: LuxtronikCoordinator
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        try:
            LOGGER.debug("Starting async_step_user")

            LOGGER.debug("Starting discovery of Luxtronik devices on network")
            device_list = await self._discover_devices()
        except OSError as err:
            LOGGER.warning("Device discovery failed due to a network error: %s", err)
            return self.async_show_form(
                step_id="manual_entry",
                data_schema=build_user_data_schema(),
                errors={"base": "cannot_connect"},
            )
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Could not handle config_flow.async_step_user")
            return self.async_show_form(
                step_id="manual_entry",
                data_schema=build_user_data_schema(),
                errors={"base": "unknown"},
            )

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
        LOGGER.debug("All discovered devices with config status: %s", self._all_devices)

        self._available_devices = [d for d in self._all_devices if not d["configured"]]
        LOGGER.debug("Available (unconfigured) devices: %s", self._available_devices)

        if self._available_devices:
            device_options_list: list[selector.SelectOptionDict] = [
                selector.SelectOptionDict(
                    value=f"{d['host']}:{d['port']}",
                    label=f"{d['host']}:{d['port']}",
                )
                for d in self._available_devices
            ]
            # Manual entry must always be reachable, even while discovered
            # devices are pending selection - a pump on another subnet
            # can't be added otherwise.
            device_options_list.append(
                selector.SelectOptionDict(
                    value=MANUAL_ENTRY_VALUE, label="Enter host manually"
                )
            )

            LOGGER.debug("Presenting selection form for available devices")
            LOGGER.debug("device_options_list=%s", device_options_list)

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

        LOGGER.debug(
            "All discovered devices are already configured. Showing manual entry form."
        )
        return self.async_show_form(
            step_id="manual_entry", data_schema=build_user_data_schema()
        )

    async def async_step_select_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user selection of a discovered device."""
        if user_input is None:
            return await self.async_step_user()

        device_str = user_input.get(SELECT_DEVICE_LABEL)
        if device_str is None:
            return self.async_abort(reason="unknown")
        if device_str == MANUAL_ENTRY_VALUE:
            return await self.async_step_manual_entry()
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

        if abort_result := await self._set_unique_id_or_abort(coordinator, config):
            return abort_result

        return self._create_entry(config, coordinator)

    async def async_step_manual_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual entry of host and port."""
        if user_input is None:
            LOGGER.debug("Showing manual entry form")
            return self.async_show_form(
                step_id="manual_entry", data_schema=build_user_data_schema()
            )

        config = self._build_config(
            user_input[CONF_HOST],
            int(user_input[CONF_PORT]),
            float(user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            int(user_input.get(CONF_MAX_DATA_LENGTH, DEFAULT_MAX_DATA_LENGTH)),
        )

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

        if abort_result := await self._set_unique_id_or_abort(  # pragma: no cover
            coordinator, config
        ):
            return abort_result

        return self._create_entry(config, coordinator)

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a DHCP discovered Luxtronik heatpump."""
        try:
            LOGGER.debug(
                "DHCP discovered a possible Luxtronik device '%s' @ '%s'",
                discovery_info.hostname,
                discovery_info.ip,
            )

            configured_hosts = {
                entry.data.get(CONF_HOST) for entry in self._async_current_entries()
            }

            # Check if IP is already configured
            if discovery_info.ip in configured_hosts:
                LOGGER.debug(
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
                LOGGER.debug(
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

            config = self._build_config(host, int(port or DEFAULT_PORT))

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

            try:
                await self.async_set_unique_id(coordinator.unique_id)
            except LuxtronikSerialNumberError as err:
                LOGGER.error(
                    "Could not identify DHCP-discovered device at %s: %s", host, err
                )
                return self.async_abort(
                    reason="cannot_identify",
                    description_placeholders={"host": host, "error": str(err)},
                )
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: host, CONF_PORT: int(port or DEFAULT_PORT)},
                # Our own update listener (see __init__.py) already reloads the
                # entry on any data/options change, so core scheduling its own
                # reload here as well is redundant and triggers a deprecation
                # warning ("has an update listener and should use it for
                # scheduling a reload"), which will start failing in 2026.12.
                reload_on_update=False,
            )

            return self._create_entry(config, coordinator)

        except AbortFlow:
            raise
        except Exception as err:
            LOGGER.error("Unhandled DHCP discovery error", exc_info=err)
            return self.async_abort(reason="unknown")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            entry_data = reconfigure_entry.data
            LOGGER.debug(
                "Reconfigure submitted with user_input=%s and existing entry_data=%s",
                user_input,
                entry_data,
            )
            config = self._build_config(
                user_input[CONF_HOST],
                int(user_input[CONF_PORT]),
                float(
                    user_input.get(
                        CONF_TIMEOUT,
                        entry_data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    )
                ),
                int(
                    user_input.get(
                        CONF_MAX_DATA_LENGTH,
                        entry_data.get(CONF_MAX_DATA_LENGTH, DEFAULT_MAX_DATA_LENGTH),
                    )
                ),
            )
            LOGGER.debug("Reconfigure built config=%s", config)

            try:
                coordinator = await connect_and_get_coordinator(self.hass, config)
            except LuxtronikConnectionError as err:
                LOGGER.warning(
                    "Reconfigure connection failed for host=%s port=%s: %s",
                    config[CONF_HOST],
                    config[CONF_PORT],
                    err,
                )
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception during reconfigure connect")
                errors["base"] = "unknown"
            else:
                try:
                    LOGGER.debug(
                        "Reconfigure connected and refreshed successfully; entry unique_id=%s, coordinator unique_id=%s",
                        reconfigure_entry.unique_id,
                        coordinator.unique_id,
                    )
                    await self.async_set_unique_id(coordinator.unique_id)
                    if reconfigure_entry.unique_id is None:
                        LOGGER.debug(
                            "Reconfigure updating entry without existing unique_id"
                        )
                        return self.async_update_reload_and_abort(
                            reconfigure_entry,
                            unique_id=coordinator.unique_id,
                            data_updates=config,
                        )
                    self._abort_if_unique_id_mismatch()
                    LOGGER.debug("Reconfigure unique_id matches; updating entry")
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        unique_id=coordinator.unique_id,
                        data_updates=config,
                    )
                except AbortFlow as err:
                    LOGGER.warning(
                        "Reconfigure aborted during unique_id check: %s",
                        err,
                    )
                    raise
                except LuxtronikSerialNumberError as err:
                    LOGGER.error(
                        "Reconfigure could not identify device at %s: %s",
                        config[CONF_HOST],
                        err,
                    )
                    errors["base"] = "cannot_identify"
                except Exception:  # pylint: disable=broad-except
                    LOGGER.exception("Unexpected exception during reconfigure update")
                    errors["base"] = "unknown"

        form_defaults = {**reconfigure_entry.data, **(user_input or {})}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=build_user_data_schema(
                host=form_defaults.get(CONF_HOST, DEFAULT_HOST),
                port=form_defaults.get(CONF_PORT, DEFAULT_PORT),
                timeout=form_defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                max_data_length=form_defaults.get(
                    CONF_MAX_DATA_LENGTH, DEFAULT_MAX_DATA_LENGTH
                ),
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(  # pragma: no cover
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get default options flow."""
        return LuxtronikOptionsFlowHandler()


class LuxtronikOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a Luxtronik options flow."""

    def _get_value(self, key: str, default=None):
        """Return a value from Luxtronik."""
        return self.config_entry.options.get(
            key, self.config_entry.data.get(key, default)
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start the options flow."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user options step."""
        try:
            if user_input is not None:
                new_options = dict(self.config_entry.options)
                value = user_input.get(CONF_HA_SENSOR_INDOOR_TEMPERATURE)
                if value:
                    new_options[CONF_HA_SENSOR_INDOOR_TEMPERATURE] = value
                elif (
                    CONF_HA_SENSOR_INDOOR_TEMPERATURE in new_options
                    or CONF_HA_SENSOR_INDOOR_TEMPERATURE in self.config_entry.data
                ):
                    new_options[CONF_HA_SENSOR_INDOOR_TEMPERATURE] = None

                power_value = user_input.get(CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION)
                if power_value:
                    new_options[CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION] = power_value
                elif (
                    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION in new_options
                    or CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION
                    in self.config_entry.data
                ):
                    new_options[CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION] = None

                update_interval = user_input.get(
                    CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_OPTION
                )
                new_options[CONF_UPDATE_INTERVAL] = update_interval

                return self.async_create_entry(title="", data=new_options)

            current_indoor_temp = self._get_value(CONF_HA_SENSOR_INDOOR_TEMPERATURE)
            current_power_consumption_sensor = self._get_value(
                CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION
            )
            current_interval = self._get_value(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_OPTION
            )

            return self.async_show_form(
                step_id="user",
                data_schema=build_options_schema(
                    current_indoor_temp=current_indoor_temp,
                    current_power_consumption_sensor=current_power_consumption_sensor,
                    current_interval=current_interval,
                ),
                description_placeholders={"name": self.config_entry.title},
            )

        except Exception as err:
            LOGGER.error(
                "Could not handle LuxtronikOptionsFlowHandler.async_step_user: %s",
                user_input,
                exc_info=err,
            )
            return self.async_abort(reason="options_error")

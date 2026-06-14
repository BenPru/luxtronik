"""Update coordinator for Luxtronik integration."""

# region Imports
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from datetime import timedelta
from functools import wraps
import re
from types import MappingProxyType
from typing import Any, Concatenate, ParamSpec, TypeVar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from packaging.version import InvalidVersion, Version

from .common import normalize_sensor_value
from .const import (
    CONF_CALCULATIONS,
    CONF_MAX_DATA_LENGTH,
    CONF_PARAMETERS,
    CONF_UPDATE_INTERVAL,
    CONF_VISIBILITIES,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
    LUX_PARAMETER_MK_SENSORS,
    UPDATE_INTERVAL_OPTIONS,
    DeviceKey,
    LuxCalculation as LC,
    LuxMkTypes,
    LuxParameter as LP,
    LuxRoomThermostatType,
    LuxVisibility as LV,
)
from .lux_helper import Luxtronik, get_manufacturer_by_model
from .lux_overrides import (
    isolate_instance_data,
    update_Luxtronik_HeatpumpCodes,
    update_Luxtronik_Parameters,
)
from .model import LuxtronikCoordinatorData, LuxtronikEntityDescription

# endregion Imports

_LuxtronikCoordinatorT = TypeVar("_LuxtronikCoordinatorT", bound="LuxtronikCoordinator")
_P = ParamSpec("_P")


def catch_luxtronik_errors(
    func: Callable[Concatenate[_LuxtronikCoordinatorT, _P], Awaitable[None]],
) -> Callable[Concatenate[_LuxtronikCoordinatorT, _P], Coroutine[Any, Any, None]]:
    """Catch Luxtronik errors."""

    @wraps(func)
    async def wrapper(
        self: _LuxtronikCoordinatorT,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        """Catch Luxtronik errors and log message."""
        try:
            await func(self, *args, **kwargs)
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.error("Command error: %s", err)
        await self.async_request_refresh()

    return wrapper


class LuxtronikCoordinator(DataUpdateCoordinator[LuxtronikCoordinatorData]):
    """Representation of a Luxtronik Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Luxtronik,
        config: Mapping[str, Any],
    ) -> None:
        """Initialize Luxtronik Client."""

        self._lock = asyncio.Lock()
        self.client = client
        self._config = config
        self.device_infos = dict[str, DeviceInfo]()
        self.update_reason_write = False

        update_interval: timedelta = DEFAULT_UPDATE_INTERVAL
        raw = config.get(CONF_UPDATE_INTERVAL)
        if isinstance(raw, str) and raw in UPDATE_INTERVAL_OPTIONS:
            update_interval = UPDATE_INTERVAL_OPTIONS[raw]

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_method=self._async_update_data,
            update_interval=update_interval,
        )

        LOGGER.info(
            "Coordinator update interval=%s s",
            self.update_interval.total_seconds()
            if self.update_interval is not None
            else None,
        )

    async def _async_update_data(self) -> LuxtronikCoordinatorData:
        async with self._lock:
            try:
                await self.hass.async_add_executor_job(self.client.read)
                LOGGER.debug(
                    "Update coordinator data  (Async, interval=%s s)",
                    self.update_interval.total_seconds()
                    if self.update_interval is not None
                    else None,
                )
                self.data = LuxtronikCoordinatorData(
                    parameters=self.client.parameters,
                    calculations=self.client.calculations,
                    visibilities=self.client.visibilities,
                )

                return self.data
            except Exception as err:
                raise UpdateFailed(f"Error fetching data: {err}") from err

    async def async_write(self, parameter: str, value: Any) -> LuxtronikCoordinatorData:
        try:
            async with self._lock:
                await self.hass.async_add_executor_job(
                    self.client.parameters.set, parameter, value
                )
                LOGGER.debug("Done: self.client.parameters.set")
                await self.hass.async_add_executor_job(self.client.write)
                LOGGER.debug("Done: self.client.write")

            # Refresh after write
            await self.async_refresh()
            LOGGER.debug("Coordinator data refreshed!")

            # Confirm the value after the read
            confirmed_value = self.get_value(f"{CONF_PARAMETERS}.{parameter}")
            LOGGER.info(
                'LuxtronikDevice.write finished %s value: "%s" (confirmed: "%s")',
                parameter,
                value,
                confirmed_value,
            )

            return self.data
        except Exception as err:
            raise UpdateFailed(f"Write error: {err}") from err

    @staticmethod
    async def connect(  # pragma: no cover
        hass: HomeAssistant, config_entry: ConfigEntry | dict[str, Any]
    ) -> LuxtronikCoordinator:
        """Connect to heatpump."""
        config: dict[Any, Any] | MappingProxyType[str, Any] | None = None
        if isinstance(config_entry, ConfigEntry):
            config = config_entry.data
        else:
            config = config_entry

        host = config[CONF_HOST]
        port = config[CONF_PORT]
        timeout = config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        max_data_length = config.get(CONF_MAX_DATA_LENGTH, DEFAULT_MAX_DATA_LENGTH)

        client = Luxtronik(
            host=host,
            port=port,
            socket_timeout=timeout,
            max_data_length=max_data_length,
            safe=False,
        )

        # Test connection
        try:
            await hass.async_add_executor_job(client.connect)
        except Exception as err:
            LOGGER.error("Luxtronik connection failed: %s", err)
            raise ConfigEntryNotReady from err

        return LuxtronikCoordinator(
            hass=hass,
            client=client,
            config=config,
        )

    def get_device(
        self,
        key: DeviceKey = DeviceKey.heatpump,
        platform: EntityPlatform | None = None,
    ) -> DeviceInfo:
        if key not in self.device_infos:
            self._create_device_infos(self.hass, self._config, platform)
        device_info = self.device_infos.get(key)
        if device_info is None:
            return DeviceInfo(
                identifiers={(DOMAIN, f"{self.unique_id}_{key.value}".lower())}
            )
        if device_info.get("name") == key:
            device_info["name"] = self._build_device_name(key, platform)
        return device_info

    def _create_device_infos(
        self,
        hass: HomeAssistant,
        config: Mapping[str, Any],
        platform: EntityPlatform | None = None,
    ):
        host = config[CONF_HOST]
        self.device_infos[DeviceKey.heatpump] = self._build_device_info(
            DeviceKey.heatpump, host, platform
        )
        via = (
            DOMAIN,
            f"{self.unique_id}_{DeviceKey.heatpump}".lower(),
        )
        self.device_infos[DeviceKey.heating] = self._build_device_info(
            DeviceKey.heating, host, platform, via
        )
        self.device_infos[DeviceKey.domestic_water] = self._build_device_info(
            DeviceKey.domestic_water, host, platform, via
        )
        self.device_infos[DeviceKey.cooling] = self._build_device_info(
            DeviceKey.cooling, host, platform, via
        )

    def _build_device_name(
        self, key: DeviceKey, platform: EntityPlatform | None = None
    ) -> str:
        if platform is None:
            return str(key.value)
        return platform.platform_data.platform_translations.get(
            f"component.{DOMAIN}.entity.device.{key.value}.name"
        ) or str(key.value)

    def _build_device_info(
        self,
        key: DeviceKey,
        host: str,
        platform: EntityPlatform | None = None,
        via_device: tuple[str, str] | None = None,
    ) -> DeviceInfo:
        device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.unique_id}_{key.value}".lower(),
                )
            },
            entry_type=None,
            name=self._build_device_name(key, platform),
            configuration_url=f"http://{host}/",
            connections={
                (
                    DOMAIN,
                    f"{self.unique_id}_{key.value}".lower(),
                )
            },
            sw_version=self.firmware_version,
            model=self.model,
            suggested_area="",  # was "Utility room",
            hw_version=None,
            manufacturer=self.manufacturer,
            # default_name=f"{text}",
            # default_manufacturer=self.manufacturer,
            # default_model=self.model,
        )
        if via_device is not None:
            device_info["via_device"] = via_device
        return device_info

    def _is_version_not_compatible(
        self, description: LuxtronikEntityDescription
    ) -> bool:
        """Check if the current firmware version is NOT compatible with the entity description."""

        # Check minimum version if specified
        if (
            description.min_firmware_version is not None
            and self.firmware_package_version < description.min_firmware_version
        ):
            return True

        # Check maximum version if specified
        if (
            description.max_firmware_version is not None
            and self.firmware_package_version > description.max_firmware_version
        ):
            return True

        # Check minimum minor version if specified
        if (
            description.min_firmware_version_minor is not None
            and self.firmware_version_minor < description.min_firmware_version_minor
        ):
            return True

        # Check maximum minor version if specified
        return (
            description.max_firmware_version_minor is not None
            and self.firmware_version_minor > description.max_firmware_version_minor
        )

    @property
    def serial_number(self) -> str:
        """Return the serial number."""
        serial_number_date = self.get_value(LP.P0874_SERIAL_NUMBER)
        serial_number_model = self.get_value(LP.P0875_SERIAL_NUMBER_MODEL)
        serial_number_hex = (
            hex(int(serial_number_model)) if serial_number_model is not None else "0"
        )
        return f"{serial_number_date}-{serial_number_hex}".replace("x", "")

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self.serial_number.lower().replace("-", "_")

    @property
    def model(self) -> str:
        """Return the heatpump model."""
        return str(self.get_value(LC.C0078_MODEL_CODE) or "")

    @property
    def manufacturer(self) -> str | None:
        """Return the heatpump manufacturer."""
        return get_manufacturer_by_model(self.model)

    @property
    def firmware_version(self) -> str:
        """Return the heatpump firmware version."""
        return str(self.get_value(LC.C0081_FIRMWARE_VERSION))

    @property
    def firmware_package_version(self) -> Version:
        """Return the heatpump firmware version as a packaging Version."""
        ver = self.firmware_version
        cleaned_version = re.sub(r"^[^\d]+", "", ver or "")
        try:
            return Version(cleaned_version)
        except InvalidVersion:
            LOGGER.warning(
                "Invalid firmware version '%s' (cleaned: '%s')", ver, cleaned_version
            )
            return Version("0")

    @property
    def firmware_version_minor(self) -> Version:
        """Return firmware 'minor' version as <minor>.<patch>.
        Example:
            - 3.90.1 -> 90.1
            - 3.90   -> 90.0
            - 3      -> 0.0
        """
        ver = self.firmware_package_version
        rel = ver.release  # e.g. (3, 90) or (3, 90, 1)
        minor = rel[1] if len(rel) > 1 else 0
        patch = rel[2] if len(rel) > 2 else 0
        return Version(f"{minor}.{patch}")

    @property
    def room_thermostat_type(self) -> LuxRoomThermostatType | int | None:
        """Derived runtime room thermostat type from parameter P0033.

        Returns LuxRoomThermostatType enum when recognized, raw int when
        unknown numeric, or None when not set or on error.
        """
        try:
            raw = self.get_value(LP.P0033_ROOM_THERMOSTAT_TYPE)
            if raw is None:
                return None
            try:
                num = int(raw)
            except Exception:
                return None
            if num == LuxRoomThermostatType.rbe.value:
                rbe_version = Version(self.get_value(LC.C0258_RBE_VERSION) or "0")
                if rbe_version >= Version("2.0.0"):
                    return LuxRoomThermostatType.rbe_plus
                else:
                    return LuxRoomThermostatType.rbe

            try:
                return LuxRoomThermostatType(num)
            except Exception:
                return num
        except Exception:
            return None

    def entity_visible(self, description: LuxtronikEntityDescription) -> bool:
        """Is description visible."""
        if description.visibility == LV.UNSET:
            return True
        # Detecting some options based on visibilities doesn't work reliably.
        # Use special functions
        if description.visibility in [
            LV.V0038_SOLAR_COLLECTOR,
            LV.V0039_SOLAR_BUFFER,
            LV.V0250_SOLAR,
        ]:
            return self._detect_solar_present()
        if description.visibility == LV.V0059_DHW_CIRCULATION_PUMP:
            return self._detect_dhw_circulation_pump_present()
        if description.visibility == LV.V0059A_DHW_CHARGING_PUMP:
            return not self._detect_dhw_circulation_pump_present()
        if description.visibility == LV.V0005_COOLING:
            return self.detect_cooling_present()
        visibility_result = self.get_value(description.visibility)
        if visibility_result is None:
            LOGGER.warning("Could not load visibility %s", description.visibility)
            return True
        return visibility_result > 0

    def entity_active(self, description: LuxtronikEntityDescription) -> bool:
        """Is description activated."""
        if self._is_version_not_compatible(description):
            return False
        if description.visibility in [
            LP.P0042_MIXING_CIRCUIT1_TYPE,
            LP.P0130_MIXING_CIRCUIT2_TYPE,
            LP.P0780_MIXING_CIRCUIT3_TYPE,
        ]:
            sensor_value = self.get_value(description.visibility)
            return sensor_value in [
                LuxMkTypes.cooling.value,
                LuxMkTypes.heating_cooling.value,
            ]
        if description.visibility in [
            LV.V0038_SOLAR_COLLECTOR,
            LV.V0039_SOLAR_BUFFER,
            LV.V0250_SOLAR,
        ]:
            return self._detect_solar_present()

        if not self.device_key_active(description.device_key):
            return False
        if description.invisible_if_value is not None:
            return description.invisible_if_value != self.get_value(
                description.luxtronik_key
            )
        return True

    def device_key_active(self, device_key: DeviceKey) -> bool:
        """Is device key activated."""
        if device_key == DeviceKey.heatpump:
            return True
        if device_key == DeviceKey.heating:
            return self.has_heating
        if device_key == DeviceKey.domestic_water:
            return self.has_domestic_water
        if device_key == DeviceKey.cooling:
            return self.has_cooling
        raise NotImplementedError

    @property
    def has_heating(self) -> bool:
        """Is heating activated."""
        val = self.get_value(LC.C0064_OPERATION_HOURS_HEATING)
        return val is not None and val > 0

    @property
    def has_domestic_water(self) -> bool:
        """Is domestic water activated."""
        val = self.get_value(LC.C0065_OPERATION_HOURS_DHW)
        return val is not None and val > 0

    @property
    def has_cooling(self) -> bool:
        """Is cooling activated."""
        val = self.get_value(LC.C0066_OPERATION_HOURS_COOLING)
        return val is not None and val > 0

    def get_value(self, group_sensor_id: str | LP | LC | LV):
        """Get a sensor value from Luxtronik."""
        sensor = self.get_sensor_by_id(str(group_sensor_id))
        if sensor is None:
            return None
        value = sensor[1] if isinstance(sensor, tuple) else sensor.value
        return normalize_sensor_value(value, self.data, group_sensor_id)

    def get_sensor_by_id(self, group_sensor_id: str):
        """Get a sensor object by id from Luxtronik."""
        try:
            group, sensor_id = group_sensor_id.split(".", 1)
            return self.get_sensor(group, sensor_id)
        except (IndexError, ValueError) as error:
            LOGGER.error(
                "Invalid group_sensor_id format: %s (%s)", group_sensor_id, error
            )
            return None

    def get_sensor(self, group: str, sensor_id: str):
        """Get sensor by configured sensor ID from coordinator data."""
        if group == CONF_PARAMETERS:
            return self.data.parameters.get(sensor_id)
        if group == CONF_CALCULATIONS:
            return self.data.calculations.get(sensor_id)
        if group == CONF_VISIBILITIES:
            return self.data.visibilities.get(sensor_id)
        return None

    def _detect_cooling_mk(self):
        """We iterate over the mk sensors, detect cooling and return a list of parameters that are may show cooling is enabled."""
        cooling_mk = []
        for mk_sensor in LUX_PARAMETER_MK_SENSORS:
            sensor_value = self.get_value(mk_sensor)
            if sensor_value in [
                LuxMkTypes.cooling.value,
                LuxMkTypes.heating_cooling.value,
            ]:
                cooling_mk = cooling_mk + [mk_sensor]

        return cooling_mk

    def _detect_solar_present(self) -> bool:
        """Detect and returns True if solar is present."""
        if bool(self.get_value(LV.V0250_SOLAR)):
            return True
        if (self.get_value(LP.P0882_SOLAR_OPERATION_HOURS) or 0) > 0.01:
            return True
        collector_temp = self.get_value(LC.C0026_SOLAR_COLLECTOR_TEMPERATURE)
        if (
            bool(self.get_value(LV.V0038_SOLAR_COLLECTOR))
            and collector_temp is not None
            and float(collector_temp) != 5.0
        ):
            return True
        buffer_temp = self.get_value(LC.C0027_SOLAR_BUFFER_TEMPERATURE)
        return (
            bool(self.get_value(LV.V0039_SOLAR_BUFFER))
            and buffer_temp is not None
            and float(buffer_temp) != 150.0
        )

    def _detect_dhw_circulation_pump_present(self) -> bool:
        """Detect and returns True if DHW circulation pump is present."""
        try:
            value = self.get_value(LP.P0085_DHW_CHARGING_PUMP)
            if value is None:
                return False
            return int(value) != 1
        except Exception:  # pylint: disable=broad-except
            return False

    def detect_cooling_present(self) -> bool:
        """Detect and returns True if Cooling is present."""
        cooling_present = len(self._detect_cooling_mk()) > 0
        return cooling_present

    async def async_shutdown(self) -> None:
        """Make sure a coordinator is shut down as well as its connection."""
        await super().async_shutdown()
        if hasattr(self, "client") and self.client is not None:
            del self.client


class LuxtronikConnectionError(HomeAssistantError):
    """Raised when connection to Luxtronik fails."""

    def __init__(self, host: str, port: int, original: Exception):
        super().__init__(
            f"Failed to connect to {host}:{port} - {type(original).__name__}: {original}"
        )
        self.host = host
        self.port = port
        self.original = original


_OVERRIDES_APPLIED = False


async def connect_and_get_coordinator(
    hass: HomeAssistant, config: ConfigEntry | dict[str, Any]
) -> LuxtronikCoordinator:
    """Try to connect to a Luxtronik device and return coordinator."""
    global _OVERRIDES_APPLIED
    # No lock needed: all override calls are synchronous (no await),
    # so the event loop cannot preempt between the guard check and flag set.
    if not _OVERRIDES_APPLIED:
        update_Luxtronik_HeatpumpCodes()
        update_Luxtronik_Parameters()
        isolate_instance_data()
        _OVERRIDES_APPLIED = True
        LOGGER.info(
            "Library overrides applied (HeatpumpCodes, Parameters, instance data isolation)."
        )

    config_data: dict[str, Any] = dict(
        config.data if isinstance(config, ConfigEntry) else config
    )
    if isinstance(config, ConfigEntry):
        config_data.update(dict(config.options))

    host: str = config_data.get(CONF_HOST, "")
    port = config_data.get(CONF_PORT, DEFAULT_PORT)

    try:  # pragma: no cover
        coordinator = await LuxtronikCoordinator.connect(hass, config_data)
        LOGGER.info("Luxtronik connect to device %s:%s successful!", host, port)

        # no need to fetch first data manually here,
        # already done by async_config_entry_first_refresh() in __init.py:47__

        return coordinator
    except Exception as err:
        LOGGER.error("Luxtronik connect to device %s:%s failed: %s", host, port, err)
        raise LuxtronikConnectionError(host, port, err) from err

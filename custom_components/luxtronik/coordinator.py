"""Update coordinator for Luxtronik integration."""

# region Imports
from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from functools import wraps
from packaging.version import Version
import threading
from types import MappingProxyType
from typing import Any, Concatenate, TypeVar

from typing_extensions import ParamSpec

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .common import correct_key_value
from .const import (
    CONF_CALCULATIONS,
    CONF_MAX_DATA_LENGTH,
    CONF_PARAMETERS,
    CONF_VISIBILITIES,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGGER,
    LUX_PARAMETER_MK_SENSORS,
    UPDATE_INTERVAL_FAST,
    UPDATE_INTERVAL_NORMAL,
    DeviceKey,
    LuxCalculation as LC,
    LuxMkTypes,
    LuxParameter as LP,
    LuxVisibility as LV,
)
from .lux_helper import Luxtronik, get_manufacturer_by_model
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

    device_infos = dict[str, DeviceInfo]()
    update_reason_write = False
    client: Luxtronik = None

    def __init__(
        self,
        hass: HomeAssistant,
        client: Luxtronik,
        config: Mapping[str, Any],
    ) -> None:
        """Initialize Luxtronik Client."""

        self.lock = threading.Lock()
        self.client = client
        self._config = config
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_method=self._async_update_data,
            update_interval=UPDATE_INTERVAL_FAST,
        )

    async def _async_update_data(self) -> LuxtronikCoordinatorData:
        """Connect and fetch data."""
        self.data = await self._async_read_data()
        return self.data

    async def _async_read_data(self) -> LuxtronikCoordinatorData:
        return await self._async_read_or_write(False, None, None)

    async def write(self, parameter, value) -> LuxtronikCoordinatorData:
        """Write a parameter to the Luxtronik heatpump."""
        return asyncio.run_coroutine_threadsafe(
            self.async_write(parameter, value), self.hass.loop
        ).result()

    async def async_write(self, parameter, value) -> LuxtronikCoordinatorData:
        """Write a parameter to the Luxtronik heatpump."""
        return await self._async_read_or_write(True, parameter, value)

    async def _async_read_or_write(
        self, write, parameter, value
    ) -> LuxtronikCoordinatorData:
        if write:
            data = self._write(parameter, value)
            self.async_set_updated_data(data)
            self.async_request_refresh()
            self.update_interval = UPDATE_INTERVAL_FAST
            self.update_reason_write = True
        else:
            data = self._read()
            self.async_set_updated_data(data)
            self.update_interval = (
                UPDATE_INTERVAL_FAST
                if bool(self.get_value(LC.C0044_COMPRESSOR))
                else UPDATE_INTERVAL_NORMAL
            )
            self.update_reason_write = False
        return data

    def _read(self) -> LuxtronikCoordinatorData:
        try:
            with self.lock:
                self.client.read()
        except (OSError, ConnectionRefusedError, ConnectionResetError) as err:
            raise UpdateFailed("Read: Error communicating with device") from err
        except UpdateFailed:
            pass
        except Exception as err:
            raise UpdateFailed("Read: Error communicating with device") from err
        self.data = LuxtronikCoordinatorData(
            parameters=self.client.parameters,
            calculations=self.client.calculations,
            visibilities=self.client.visibilities,
        )
        return self.data

    def _write(self, parameter, value) -> LuxtronikCoordinatorData:
        try:
            self.client.parameters.set(parameter, value)
            with self.lock:
                self.client.write()
        except (ConnectionRefusedError, ConnectionResetError) as err:
            LOGGER.exception(err)
            raise UpdateFailed("Read: Error communicating with device") from err
        except UpdateFailed as err:
            LOGGER.exception(err)
        except Exception as err:
            LOGGER.exception(err)
            raise UpdateFailed("Write: Error communicating with device") from err
        finally:
            self.data = LuxtronikCoordinatorData(
                parameters=self.client.parameters,
                calculations=self.client.calculations,
                visibilities=self.client.visibilities,
            )
            LOGGER.info(
                'LuxtronikDevice.write finished %s value: "%s"',
                parameter,
                value,
            )
        return self.data

    @staticmethod
    def connect(
        hass: HomeAssistant, config_entry: ConfigEntry | dict
    ) -> LuxtronikCoordinator:
        """Connect to heatpump."""
        config: dict[Any, Any] | MappingProxyType[str, Any] | None = None
        if isinstance(config_entry, ConfigEntry):
            config = config_entry.data
        else:
            config = config_entry

        host = config[CONF_HOST]
        port = config[CONF_PORT]
        timeout = config[CONF_TIMEOUT] if CONF_TIMEOUT in config else DEFAULT_TIMEOUT
        max_data_length = (
            config[CONF_MAX_DATA_LENGTH]
            if CONF_MAX_DATA_LENGTH in config
            else DEFAULT_MAX_DATA_LENGTH
        )

        client = Luxtronik(
            host=host,
            port=port,
            socket_timeout=timeout,
            max_data_length=max_data_length,
            safe=False,
        )
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
        device_info: DeviceInfo = self.device_infos.get(key)
        if device_info["name"] == key:
            device_info["name"] = self._build_device_name(key, platform)
        return device_info

    def _create_device_infos(
        self,
        hass: HomeAssistant,
        config: Mapping[str, Any],
        platform: EntityPlatform | None = None,
    ):
        host = config[CONF_HOST]
        dev = self.device_infos[DeviceKey.heatpump.value] = self._build_device_info(
            DeviceKey.heatpump, host, platform
        )
        via = (
            DOMAIN,
            f"{self.unique_id}_{DeviceKey.heatpump.value}".lower(),
        )
        self.device_infos[DeviceKey.heating.value] = self._build_device_info(
            DeviceKey.heating, host, platform, via
        )
        self.device_infos[DeviceKey.domestic_water.value] = self._build_device_info(
            DeviceKey.domestic_water, host, platform, via
        )
        self.device_infos[DeviceKey.cooling.value] = self._build_device_info(
            DeviceKey.cooling, host, platform, via
        )

    def _build_device_name(
        self, key: DeviceKey, platform: EntityPlatform | None = None
    ) -> str:
        if platform is None:
            return str(key.value)
        return platform.platform_translations.get(
            f"component.{DOMAIN}.entity.device.{key.value}.name"
        )

    def _build_device_info(
        self,
        key: DeviceKey,
        host: str,
        platform: EntityPlatform | None = None,
        via_device=None,
    ) -> DeviceInfo:
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.unique_id}_{key.value}".lower(),
                )
            },
            entry_type=None,
            name=self._build_device_name(key, platform),
            via_device=via_device,
            configuration_url=f"http://{host}/",
            connections={
                (
                    DOMAIN,
                    f"{self.unique_id}_{key.value}".lower(),
                )
            },
            sw_version=self.firmware_version,
            model=self.model,
            suggested_area="Utility room",
            hw_version=None,
            manufacturer=self.manufacturer,
            # default_name=f"{text}",
            # default_manufacturer=self.manufacturer,
            # default_model=self.model,
        )

    def _is_version_not_compatible(
        self, description: LuxtronikEntityDescription
    ) -> bool:
        """Check if the current firmware version is NOT compatible with the entity description."""

        # Check minor version if specified
        if (
            description.min_firmware_version_minor is not None
            and self.firmware_version_minor
            < description.min_firmware_version_minor.value
        ):
            return True

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

        # If all checks pass or no version restrictions are specified
        return False

    @property
    def serial_number(self) -> str:
        """Return the serial number."""
        serial_number_date = self.get_value(LP.P0874_SERIAL_NUMBER)
        serial_number_hex = hex(int(self.get_value(LP.P0875_SERIAL_NUMBER_MODEL)))
        return f"{serial_number_date}-{serial_number_hex}".replace("x", "")

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self.serial_number.lower().replace("-", "_")

    @property
    def model(self) -> str:
        """Return the heatpump model."""
        return self.get_value(LC.C0078_MODEL_CODE)

    @property
    def manufacturer(self) -> str | None:
        """Return the heatpump manufacturer."""
        return get_manufacturer_by_model(self.model)

    @property
    def firmware_version(self) -> str:
        """Return the heatpump firmware version."""
        return str(self.get_value(LC.C0081_FIRMWARE_VERSION))

    @property
    def firmware_version_minor(self) -> int:
        """Return the heatpump firmware minor version."""
        ver = self.firmware_version
        if ver is None:
            return 0
        return int(re.sub("[^0-9]", "", ver.split(".")[1]))

    @property
    def firmware_package_version(self) -> Version:
        """Return the heatpump firmware version."""
        return Version(str(self.get_value(LC.C0081_FIRMWARE_VERSION)))

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
            return self.detect_cooling_present()
        raise NotImplementedError

    @property
    def has_heating(self) -> bool:
        """Is heating activated."""
        return bool(self.get_value(LV.V0023_FLOW_IN_TEMPERATURE))

    @property
    def has_domestic_water(self) -> bool:
        """Is domestic water activated."""
        return bool(self.get_value(LV.V0029_DHW_TEMPERATURE))

    def get_value(self, group_sensor_id: str | LP | LC | LV):
        """Get a sensor value from Luxtronik."""
        sensor = self.get_sensor_by_id(str(group_sensor_id))
        if sensor is None:
            return None
        return correct_key_value(sensor.value, self.data, group_sensor_id)

    def get_sensor_by_id(self, group_sensor_id: str):
        """Get a sensor object by id from Luxtronik."""
        try:
            group = group_sensor_id.split(".")[0]
            sensor_id = group_sensor_id.split(".")[1]
            return self.get_sensor(group, sensor_id)
        except IndexError as error:
            LOGGER.critical(group_sensor_id, error, exc_info=True)

    def get_sensor(self, group, sensor_id):
        """Get sensor by configured sensor ID."""
        sensor = None
        if group == CONF_PARAMETERS:
            sensor = self.client.parameters.get(sensor_id)
        if group == CONF_CALCULATIONS:
            sensor = self.client.calculations.get(sensor_id)
        if group == CONF_VISIBILITIES:
            sensor = self.client.visibilities.get(sensor_id)
        return sensor

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
        return (
            bool(self.get_value(LV.V0250_SOLAR))
            or self.get_value(LP.P0882_SOLAR_OPERATION_HOURS) > 0.01  # noqa: W503
            or (
                bool(self.get_value(LV.V0038_SOLAR_COLLECTOR))  # noqa: W503
                and float(self.get_value(LC.C0026_SOLAR_COLLECTOR_TEMPERATURE))  # noqa: W503
                != 5.0  # noqa: W503
            )
            or (
                bool(self.get_value(LV.V0039_SOLAR_BUFFER))  # noqa: W503
                and float(self.get_value(LC.C0027_SOLAR_BUFFER_TEMPERATURE))  # noqa: W503
                != 150.0  # noqa: W503
            )
        )

    def _detect_dhw_circulation_pump_present(self) -> bool:
        """Detect and returns True if solar is present."""
        try:
            return int(self.get_value(LP.P0085_DHW_CHARGING_PUMP)) != 1
        except Exception:  # pylint: disable=broad-except
            return False

    def detect_cooling_present(self) -> bool:
        """Detect and returns True if Cooling is present."""
        cooling_present = len(self._detect_cooling_mk()) > 0
        return cooling_present

    async def async_shutdown(self) -> None:
        """Make sure a coordinator is shut down as well as it's connection."""
        await super().async_shutdown()
        if self.client is not None:
            # await self.client.disconnect()
            del self.client

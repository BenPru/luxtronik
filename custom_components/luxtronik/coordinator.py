"""Update coordinator for Luxtronik integration."""
# region Imports
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from functools import wraps
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
    HEATPUMP_CODE_TYPE_MAP,
    LOGGER,
    LUX_PARAMETER_MK_SENSORS,
    UPDATE_INTERVAL_FAST,
    UPDATE_INTERVAL_NORMAL,
    DeviceKey,
    Calculation_SensorKey as LC,
    LuxMkTypes,
    Parameter_All_SensorKey as LPA,
    Parameter_Static_SensorKey as LPS,
    Parameter_Calc_SensorKey as LPCalc,
    Parameter_Config_SensorKey as LPC,
    Parameter_SensorKey as LP,
    Visibility_SensorKey as LV,
)
from .lux_helper import Luxtronik, get_manufacturer_by_model
from .model import LuxtronikCoordinatorData, LuxtronikEntityDescription

# endregion Imports

_LuxtronikCoordinatorT = TypeVar("_LuxtronikCoordinatorT", bound="LuxtronikCoordinator")
_P = ParamSpec("_P")


def catch_luxtronik_errors(
    func: Callable[Concatenate[_LuxtronikCoordinatorT, _P], Awaitable[None]]
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

    def write(
        self, parameter: int | str | dict[str, Any], value: Any = None
    ) -> LuxtronikCoordinatorData:
        """Write a parameter to the Luxtronik heatpump."""
        return asyncio.run_coroutine_threadsafe(
            self.async_write(parameter, value), self.hass.loop
        ).result()

    async def async_write(
        self, parameter: int | str | dict[str, Any], value: Any = None
    ) -> LuxtronikCoordinatorData:
        """Write a parameter to the Luxtronik heatpump."""
        return await self._async_read_or_write(True, parameter, value)

    async def _async_read_or_write(
        self,
        write: bool,
        parameter: int | str | dict[str, Any] | None,
        value: any = None,
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
                if bool(self.get_value(LC.COMPRESSOR))
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

    def _write(
        self, parameter: int | str | dict[str, Any] | None, value: any = None
    ) -> LuxtronikCoordinatorData:
        try:
            if isinstance(parameter, dict):
                for k, v in parameter.items():
                    self.client.parameters.set(k, v)
            else:
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

    @property
    def serial_number(self) -> str:
        """Return the serial number."""
        serial_number_date = self.get_value(LPS.SERIAL_NUMBER)
        serial_number_hex = hex(int(self.get_value(LPS.SERIAL_NUMBER_MODEL)))
        return f"{serial_number_date}-{serial_number_hex}".replace("x", "")

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self.serial_number.lower().replace("-", "_")

    @property
    def model(self) -> str:
        """Return the heatpump model."""
        # return self.get_value(LC.MODEL_CODE)
        return HEATPUMP_CODE_TYPE_MAP.get(self.get_value(LC.MODEL_CODE))

    @property
    def manufacturer(self) -> str | None:
        """Return the heatpump manufacturer."""
        return get_manufacturer_by_model(self.model)

    @property
    def firmware_version(self) -> str:
        """Return the heatpump firmware version."""
        return str(self.get_value(LC.FIRMWARE_VERSION))
        # value = []
        # for i in range(LC.FIRMWARE_VERSION.value, LC.FIRMWARE_VERSION.value + 9):
        #     value.append(self.get_value(i))
        # return "".join([chr(c) for c in value]).strip("\x00")

    @property
    def firmware_version_minor(self) -> int:
        """Return the heatpump firmware minor version."""
        ver = self.firmware_version
        if ver is None:
            return 0
        return int(ver.split(".")[1])

    def entity_visible(self, description: LuxtronikEntityDescription) -> bool:
        """Is description visible."""
        if description.visibility == LV.UNSET:
            return True
        # Detecting some options based on visibilities doesn't work reliably.
        # Use special functions
        if description.visibility in [
            LV.SOLAR_COLLECTOR,
            LV.SOLAR_BUFFER,
            LV.SOLAR,
        ]:
            return self._detect_solar_present()
        if description.visibility == LV.DHW_CIRCULATION_PUMP:
            return self._detect_dhw_circulation_pump_present()
        if description.visibility == LV.DHW_CHARGING_PUMP:
            return not self._detect_dhw_circulation_pump_present()
        if description.visibility == LV.COOLING:
            return self.detect_cooling_present()
        visibility_result = self.get_value(description.visibility)
        if visibility_result is None:
            LOGGER.warning("Could not load visibility %s", description.visibility)
            return True
        return visibility_result > 0

    def entity_active(self, description: LuxtronikEntityDescription) -> bool:
        """Is description activated."""
        if (
            description.min_firmware_version_minor is not None
            and description.min_firmware_version_minor.value  # noqa: W503
            > self.firmware_version_minor  # noqa: W503
        ):
            return False
        if description.visibility in [
            LV.MK1,
            LV.MK2,
            LV.MK3
        ]:
            sensor_value = self.get_value(description.visibility)
            return sensor_value in [
                LuxMkTypes.cooling.value,
                LuxMkTypes.heating_cooling.value,
            ]
        if description.visibility in [
            LV.SOLAR_COLLECTOR,
            LV.SOLAR_BUFFER,
            LV.SOLAR,
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
        return bool(self.get_value(LV.FLOW_IN_TEMPERATURE))

    @property
    def has_domestic_water(self) -> bool:
        """Is domestic water activated."""
        return bool(self.get_value(LV.DHW_TEMPERATURE))

    def get_value(self, sensor_id: LPA | LC | LV | int):
        """Get a sensor value from Luxtronik."""
        # sensor = self.get_sensor_by_id(str(group_sensor_id))
        sensor = self.get_sensor_by_id(sensor_id)
        if sensor is None:
             return None
        return correct_key_value(sensor.value, self.data, sensor_id)
        # return correct_key_value(sensor.value, self.data, group_sensor_id)

    # def get_sensor_by_id(self, group_sensor_id: str):
    def get_sensor_by_id(self, sensor_id: LPA | LC | LV | int):
        """Get a sensor object by id from Luxtronik."""
    #     try:
    #         group = group_sensor_id.split(".")[0]
    #         sensor_id = group_sensor_id.split(".")[1]
    #         return self.get_sensor(group, sensor_id)
    #     except IndexError as error:
    #         LOGGER.critical(group_sensor_id, error, exc_info=True)

    # def get_sensor(self, group, sensor_id):
        """Get sensor by configured sensor ID."""
        if isinstance(sensor_id, LPA) or isinstance(sensor_id, LPS) or isinstance(sensor_id, LP) or isinstance(sensor_id, LPC) or isinstance(sensor_id, LPCalc): # == CONF_PARAMETERS:
            # sensor = self.client.parameters[sensor_id.value]
            return self.client.parameters.get(sensor_id.value)
        elif isinstance(sensor_id, LV): #group == CONF_VISIBILITIES:
            # sensor = self.client.visibilities[sensor_id.value]
            return self.client.calculations.get(sensor_id.value)
        elif isinstance(sensor_id, LC): #group == CONF_CALCULATIONS:
            # sensor = self.client.calculations[sensor_id.value]
            return self.client.visibilities.get(sensor_id.value)
        elif isinstance(sensor_id, int):
            # sensor = self.client.calculations[sensor_id]
            return self.client.calculations.get(sensor_id)

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
            bool(self.get_value(LV.SOLAR))
            or self.get_value(LPCalc.SOLAR_OPERATION_HOURS) > 0.01  # noqa: W503
            or (
                bool(self.get_value(LV.SOLAR_COLLECTOR))  # noqa: W503
                and float(
                    self.get_value(LC.SOLAR_COLLECTOR_TEMPERATURE)
                )  # noqa: W503
                != 5.0  # noqa: W503
            )
            or (
                bool(self.get_value(LV.SOLAR_BUFFER))  # noqa: W503
                and float(
                    self.get_value(LC.SOLAR_BUFFER_TEMPERATURE)
                )  # noqa: W503
                != 150.0  # noqa: W503
            )
        )

    def _detect_dhw_circulation_pump_present(self) -> bool:
        """Detect and returns True if solar is present."""
        try:
            return int(self.get_value(LPCalc.DHW_CHARGING_PUMP)) != 1
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

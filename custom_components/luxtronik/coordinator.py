"""Update coordinator for Luxtronik integration."""
# region Imports
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from datetime import timedelta
from functools import wraps
import json
import os.path
import re
import threading
from types import MappingProxyType
from typing import Any, Concatenate, Final, TypeVar, cast

from typing_extensions import ParamSpec

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
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
    LANG_DEFAULT,
    LOGGER,
    LUX_PARAMETER_MK_SENSORS,
    PLATFORMS,
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
    __content_locale__ = dict[Any, Any]()
    __content_locale_texts__ = dict[Any, Any]()
    __content_sensors_locale__ = dict[Any, Any]()

    def __init__(
        self,
        hass: HomeAssistant,
        client: Luxtronik,
        config: Mapping[str, Any],
    ) -> None:
        """Initialize Luxtronik Client."""

        self.lock = threading.Lock()
        self.client = client
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_method=self._async_update_data,
            update_interval=UPDATE_INTERVAL_FAST,
        )
        self._load_translations(hass)
        self._create_device_infos(hass, config)

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

    def _load_translations(self, hass: HomeAssistant):
        """Load translations from file for device and entity names."""
        lang = self._normalize_lang(hass.config.language)
        self.__content_locale__ = self._load_lang_from_file(f"translations/{lang}.json")
        self.__content_locale_texts__ = self._load_lang_from_file(
            f"translations/texts.{lang}.json"
        )
        for platform in PLATFORMS:
            fname = f"translations/{platform}.{LANG_DEFAULT}.json"
            if self._exists_locale_file(self._build_filepath(fname)):
                self.__content_sensors_locale__[platform] = self._load_lang_from_file(
                    fname
                )

    def _normalize_lang(self, lang: str) -> str:
        if lang is None:
            return LANG_DEFAULT
        lang = lang.lower()
        if "-" in lang:
            lang = lang.split("-")[0]
        fname = self._build_filepath(f"translations/{lang}.json")
        if not self._exists_locale_file(fname):
            return LANG_DEFAULT
        return lang

    def _build_filepath(self, fname: str) -> str:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        return os.path.join(dir_path, fname)

    def _exists_locale_file(self, fname: str) -> bool:
        return os.path.isfile(fname)

    def _load_lang_from_file(self, fname: str, log_warning=True) -> dict:
        fname = self._build_filepath(fname)
        if not self._exists_locale_file(fname):
            if log_warning:
                LOGGER.warning("_load_lang_from_file - file not found %s", fname)
            return {}
        with open(fname, encoding="utf8") as locale_file:
            return json.load(locale_file)

    def _create_device_infos(
        self,
        hass: HomeAssistant,
        config: Mapping[str, Any],
    ):
        host = config[CONF_HOST]
        dev = self.device_infos[DeviceKey.heatpump.value] = self._build_device_info(
            DeviceKey.heatpump, host
        )
        via = (
            DOMAIN,
            f"{self.unique_id}_{DeviceKey.heatpump.value}".lower(),
        )
        self.device_infos[DeviceKey.heating.value] = self._build_device_info(
            DeviceKey.heating, host, via
        )
        self.device_infos[DeviceKey.domestic_water.value] = self._build_device_info(
            DeviceKey.domestic_water, host, via
        )
        self.device_infos[DeviceKey.cooling.value] = self._build_device_info(
            DeviceKey.cooling, host, via
        )

    def _build_device_info(
        self, key: DeviceKey, host: str, via_device=None
    ) -> DeviceInfo:
        text = self.get_device_entity_title(key.value, "device")
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.unique_id}_{key.value}".lower(),
                )
            },
            entry_type=None,
            name=f"{text}",
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

    def get_text(self, key: str) -> str:
        """Get a text in locale language."""
        result = self._get_value_recursive(self.__content_locale_texts__, [key])
        if result is not None:
            return result
        LOGGER.warning(
            "Get_text key %s not found in",
            key,
        )
        return key.replace("_", " ").title()

    def get_device_entity_title(self, key: str, platform: Platform | str) -> str:
        """Get a device or entity title text in locale language."""
        result = self._get_value_recursive(
            self.__content_locale__, ["entity", platform, key, "name"]
        )
        if result is not None:
            return result
        LOGGER.warning(
            "Get_device_entity_title key %s.%s not found in",
            platform,
            key,
        )
        return key.replace("_", " ").title()

    def get_sensor_value_text(
        self, key: str, value: str, platform: Platform = Platform.SENSOR
    ) -> str:
        """Get a sensor value text."""
        result = self._get_value_recursive(
            self.__content_locale__, ["entity", platform, key, "state", value]
        )
        if result is not None:
            return result
        LOGGER.warning(
            "Get_sensor_value_text key %s / value %s not found",
            key,
            value,
        )
        return key.replace("_", " ").title()

    def _get_value_recursive(self, content: dict, keys: list[str]) -> str | None:
        key = keys.pop(0)
        if key not in content.keys():
            return None
        if len(keys) > 0:
            return self._get_value_recursive(cast(dict, content.get(key)), keys)
        return str(content.get(key))

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
        return int(ver.split(".")[1])

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
            return  self.detect_cooling_present()
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
            LP.P0042_MK1_TYPE,
            LP.P0130_MK2_TYPE,
            LP.P0780_MK3_TYPE,
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
            or 
            ( bool(self.get_value(LV.V0038_SOLAR_COLLECTOR))  # noqa: W503
              and 
              float(self.get_value(LC.C0026_SOLAR_COLLECTOR_TEMPERATURE))  # noqa: W503
              != 5.0  # noqa: W503
            )
            or 
            ( bool(self.get_value(LV.V0039_SOLAR_BUFFER))  # noqa: W503
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

"""Tests for custom_components.luxtronik2.coordinator."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from conftest import make_coordinator_data
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.update_coordinator import UpdateFailed
from packaging.version import Version
import pytest

from custom_components.luxtronik2.const import (
    DEFAULT_PORT,
    DeviceKey,
    LuxCalculation as LC,
    LuxMkTypes,
    LuxParameter as LP,
    LuxRoomThermostatType,
    LuxVisibility as LV,
)
from custom_components.luxtronik2.coordinator import (
    LuxtronikConnectionError,
    LuxtronikCoordinator,
    catch_luxtronik_errors,
)
from custom_components.luxtronik2.model import (
    LuxtronikCoordinatorData,
    LuxtronikEntityDescription,
)

# ===========================================================================
# Helpers
# ===========================================================================


def _make_coordinator(
    hass=None,
    parameters: dict[str, Any] | None = None,
    calculations: dict[str, Any] | None = None,
    visibilities: dict[str, Any] | None = None,
) -> LuxtronikCoordinator:
    """Build a coordinator with fake data for unit tests."""
    if hass is None:
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(
            side_effect=lambda fn, *a, **kw: fn(*a, **kw)
        )

    client = MagicMock()
    data = make_coordinator_data(
        parameters=parameters or {},
        calculations=calculations or {},
        visibilities=visibilities or {},
    )
    client.parameters = data.parameters
    client.calculations = data.calculations
    client.visibilities = data.visibilities

    config = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: DEFAULT_PORT,
    }

    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = LuxtronikCoordinator(hass=hass, client=client, config=config)
    coordinator.data = data
    return coordinator


def _make_coordinator_direct(data=None):
    """Create a coordinator via object.__new__ with mocked internals."""
    coord = object.__new__(LuxtronikCoordinator)
    coord._lock = asyncio.Lock()
    coord.hass = MagicMock()
    coord.client = MagicMock()
    coord._config = {"host": "1.2.3.4", "port": 8889}
    coord.device_infos = {}
    coord.update_reason_write = False
    coord.async_request_refresh = AsyncMock()
    coord.async_refresh = AsyncMock()
    if data is None:
        data = LuxtronikCoordinatorData(
            parameters={"ID_WEB_WP_BZ_akt": (0, 0)},
            calculations={"ID_WEB_WP_BZ_akt": (0, 0)},
            visibilities={"ID_WEB_Sichtbar_Solar": (0, 1)},
        )
    coord.data = data
    return coord


# ===========================================================================
# LuxtronikCoordinator properties
# ===========================================================================


class TestCoordinatorProperties:
    def test_unique_id(self):
        coord = _make_coordinator(
            parameters={
                "ID_WP_SerienNummer_DATUM": 20230101,
                "ID_WP_SerienNummer_HEX": 255,
            }
        )
        uid = coord.unique_id
        assert isinstance(uid, str)
        assert "_" in uid  # serial_number_date-serial_number_hex

    def test_model(self):
        coord = _make_coordinator(calculations={"ID_WEB_Code_WP_akt": 27})
        assert coord.model == "27"

    def test_model_none(self):
        coord = _make_coordinator()
        # No model data → empty string
        assert coord.model == ""

    def test_manufacturer_novelan(self):
        coord = _make_coordinator(calculations={"ID_WEB_Code_WP_akt": "BW something"})
        assert coord.manufacturer == "Novelan"

    def test_manufacturer_alpha_innotec(self):
        coord = _make_coordinator(calculations={"ID_WEB_Code_WP_akt": "LWP 10"})
        assert coord.manufacturer == "Alpha Innotec"

    def test_manufacturer_unknown(self):
        coord = _make_coordinator(calculations={"ID_WEB_Code_WP_akt": "UNKNOWN"})
        assert coord.manufacturer is None

    def test_firmware_version(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        assert coord.firmware_version == "V3.90.1"

    def test_firmware_package_version(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        ver = coord.firmware_package_version
        assert isinstance(ver, Version)
        assert ver == Version("3.90.1")

    def test_firmware_package_version_invalid(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "invalid_firmware"})
        ver = coord.firmware_package_version
        assert ver == Version("0")

    def test_firmware_version_minor(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        minor = coord.firmware_version_minor
        assert minor == Version("90.1")

    def test_firmware_version_minor_short(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90"})
        minor = coord.firmware_version_minor
        assert minor == Version("90.0")

    def test_serial_number(self):
        coord = _make_coordinator(
            parameters={
                "ID_WP_SerienNummer_DATUM": 20230101,
                "ID_WP_SerienNummer_HEX": 255,
            }
        )
        sn = coord.serial_number
        assert "20230101" in sn
        assert "ff" in sn.lower()  # hex(255) = 0xff

    def test_room_thermostat_type(self):
        coord = _make_coordinator(parameters={"ID_Einst_RFVEinb_akt": 4})
        thermostat_type = coord.room_thermostat_type
        assert thermostat_type == LuxRoomThermostatType.rbe

        coord = _make_coordinator(parameters={"ID_Einst_RFVEinb_akt": 5})
        thermostat_type = coord.room_thermostat_type
        assert thermostat_type == LuxRoomThermostatType.smart

        coord = _make_coordinator(parameters={"ID_Einst_RFVEinb_akt": 99})
        thermostat_type = coord.room_thermostat_type
        assert thermostat_type == 99  # Unknown but returned as int

        coord = _make_coordinator(parameters={"ID_Einst_RFVEinb_akt": "unknown"})
        thermostat_type = coord.room_thermostat_type
        assert thermostat_type is None


# ===========================================================================
# device_key_active
# ===========================================================================


class TestDeviceKeyActive:
    def test_heatpump_always_active(self):
        coord = _make_coordinator()
        assert coord.device_key_active(DeviceKey.heatpump) is True

    def test_heating_active(self):
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitHz": 100})
        assert coord.device_key_active(DeviceKey.heating) is True

    def test_heating_inactive(self):
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitHz": 0})
        assert coord.device_key_active(DeviceKey.heating) is False

    def test_domestic_water_active(self):
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitBW": 100})
        assert coord.device_key_active(DeviceKey.domestic_water) is True

    def test_domestic_water_inactive(self):
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitBW": 0})
        assert coord.device_key_active(DeviceKey.domestic_water) is False

    def test_cooling_active(self):
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitKue": 100})
        assert coord.device_key_active(DeviceKey.cooling) is True

    def test_cooling_inactive(self):
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitKue": 0})
        assert coord.device_key_active(DeviceKey.cooling) is False

    def test_unknown_device_key_raises(self):
        coord = _make_coordinator()
        with pytest.raises(NotImplementedError):
            coord.device_key_active("unknown_key")


# ===========================================================================
# entity_visible
# ===========================================================================


class TestEntityVisible:
    def test_unset_visibility_always_visible(self):
        coord = _make_coordinator()
        desc = LuxtronikEntityDescription(key="test")
        assert coord.entity_visible(desc) is True

    def test_visibility_value_positive(self):
        coord = _make_coordinator(visibilities={"ID_Visi_Zirkulationspumpe": 1})
        desc = LuxtronikEntityDescription(
            key="test",
            visibility=LV.V0059_DHW_CIRCULATION_PUMP,
        )
        # This uses special detection logic for DHW pump
        result = coord.entity_visible(desc)
        assert isinstance(result, bool)

    def test_solar_visibility_no_solar(self):
        coord = _make_coordinator(
            visibilities={
                "ID_Visi_Solar": 0,
                "ID_Visi_Solar_Kollektor": 0,
                "ID_Visi_Solar_Puffer": 0,
            },
            parameters={"ID_Einst_SolBW_akt": 0},
        )
        desc = LuxtronikEntityDescription(
            key="test",
            visibility=LV.V0250_SOLAR,
        )
        assert coord.entity_visible(desc) is False

    def test_cooling_visibility(self):
        coord = _make_coordinator(
            visibilities={"ID_Visi_Kuhlung": 0},
            parameters={
                "ID_Einst_HzMKE1_akt": 0,
                "ID_Einst_HzMKE2_akt": 0,
                "ID_Einst_HzMKE3_akt": 0,
            },
        )
        desc = LuxtronikEntityDescription(
            key="test",
            visibility=LV.V0005_COOLING,
        )
        assert coord.entity_visible(desc) is False

    def test_solar_collector_visibility(self):
        coord = _make_coordinator_direct()
        coord._detect_solar_present = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0038_SOLAR_COLLECTOR
        assert coord.entity_visible(desc) is True

    def test_solar_buffer_visibility(self):
        coord = _make_coordinator_direct()
        coord._detect_solar_present = MagicMock(return_value=False)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0039_SOLAR_BUFFER
        assert coord.entity_visible(desc) is False

    def test_solar_250_visibility(self):
        coord = _make_coordinator_direct()
        coord._detect_solar_present = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0250_SOLAR
        assert coord.entity_visible(desc) is True

    def test_dhw_circulation_pump(self):
        coord = _make_coordinator_direct()
        coord._detect_dhw_circulation_pump_present = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0059_DHW_CIRCULATION_PUMP
        assert coord.entity_visible(desc) is True

    def test_dhw_charging_pump(self):
        coord = _make_coordinator_direct()
        coord._detect_dhw_circulation_pump_present = MagicMock(return_value=False)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0059A_DHW_CHARGING_PUMP
        assert coord.entity_visible(desc) is True

    def test_visibility_none_returns_true(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=None)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        assert coord.entity_visible(desc) is True

    def test_visibility_value_zero(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=0)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        assert coord.entity_visible(desc) is False


# ===========================================================================
# entity_active
# ===========================================================================


class TestEntityActive:
    def test_version_incompatible(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test",
            min_firmware_version=Version("4.0.0"),
        )
        assert coord.entity_active(desc) is False

    def test_version_compatible(self):
        coord = _make_coordinator(
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Zaehler_BetrZeitHz": 100,
            },
        )
        desc = LuxtronikEntityDescription(
            key="test",
            min_firmware_version=Version("3.0.0"),
        )
        assert coord.entity_active(desc) is True

    def test_max_version_exceeded(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test",
            max_firmware_version=Version("3.0.0"),
        )
        assert coord.entity_active(desc) is False

    def test_device_key_inactive_disables_entity(self):
        coord = _make_coordinator(
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Zaehler_BetrZeitKue": 0,
            },
        )
        desc = LuxtronikEntityDescription(
            key="test",
            device_key=DeviceKey.cooling,
        )
        assert coord.entity_active(desc) is False

    def test_invisible_if_value_match(self):
        coord = _make_coordinator(
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Zaehler_BetrZeitHz": 100,
            },
            parameters={"ID_Ba_Hz_akt": "Off"},
        )
        desc = LuxtronikEntityDescription(
            key="test",
            luxtronik_key=LP.P0003_MODE_HEATING,
            invisible_if_value="Off",
        )
        assert coord.entity_active(desc) is False

    def test_version_not_compatible(self):
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        assert coord.entity_active(desc) is False

    def test_mixing_circuit_cooling(self):
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.get_value = MagicMock(return_value=LuxMkTypes.cooling.value)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LP.P0042_MIXING_CIRCUIT1_TYPE
        desc.device_key = DeviceKey.heatpump
        assert coord.entity_active(desc) is True

    def test_mixing_circuit_not_cooling(self):
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.get_value = MagicMock(return_value=0)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LP.P0042_MIXING_CIRCUIT1_TYPE
        desc.device_key = DeviceKey.heatpump
        assert coord.entity_active(desc) is False

    def test_solar_visibility_active(self):
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord._detect_solar_present = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0038_SOLAR_COLLECTOR
        assert coord.entity_active(desc) is True

    def test_device_key_not_active(self):
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.device_key_active = MagicMock(return_value=False)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.device_key = DeviceKey.heating
        assert coord.entity_active(desc) is False

    def test_invisible_if_value_matches(self):
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.device_key_active = MagicMock(return_value=True)
        coord.get_value = MagicMock(return_value=42)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.device_key = DeviceKey.heatpump
        desc.invisible_if_value = 42
        desc.luxtronik_key = LP.P0001_HEATING_TARGET_CORRECTION
        assert coord.entity_active(desc) is False

    def test_invisible_if_value_no_match(self):
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.device_key_active = MagicMock(return_value=True)
        coord.get_value = MagicMock(return_value=99)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.device_key = DeviceKey.heatpump
        desc.invisible_if_value = 42
        desc.luxtronik_key = LP.P0001_HEATING_TARGET_CORRECTION
        assert coord.entity_active(desc) is True


# ===========================================================================
# get_value / get_sensor
# ===========================================================================


class TestCoordinatorGetValue:
    def test_get_value_existing(self):
        coord = _make_coordinator(calculations={"ID_WEB_Temperatur_TVL": 30.0})
        assert coord.get_value(LC.C0010_FLOW_IN_TEMPERATURE) == 30.0

    def test_get_value_missing(self):
        coord = _make_coordinator()
        assert coord.get_value("parameters.nonexistent") is None

    def test_get_sensor_by_id_invalid_format(self):
        coord = _make_coordinator()
        assert coord.get_sensor_by_id("no_dot_here") is None

    def test_get_sensor_existing(self):
        coord = _make_coordinator(parameters={"ID_Ba_Hz_akt": "Automatic"})
        sensor = coord.get_sensor("parameters", "ID_Ba_Hz_akt")
        assert sensor is not None
        assert sensor.value == "Automatic"

    def test_get_sensor_unknown_group(self):
        coord = _make_coordinator()
        assert coord.get_sensor("unknown_group", "some_key") is None


# ===========================================================================
# async operations
# ===========================================================================


class TestCoordinatorAsync:
    @pytest.mark.asyncio
    async def test_async_update_data(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(
            side_effect=lambda fn, *a, **kw: fn(*a, **kw)
        )

        client = MagicMock()
        from conftest import FakeSensorGroup

        client.parameters = FakeSensorGroup({"key1": "val1"})
        client.calculations = FakeSensorGroup({"key2": "val2"})
        client.visibilities = FakeSensorGroup({"key3": "val3"})

        with patch("homeassistant.helpers.frame.report_usage"):
            coord = LuxtronikCoordinator(
                hass=hass,
                client=client,
                config={CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT},
            )

        data = await coord._async_update_data()
        assert data is not None
        client.read.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_data_error(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(side_effect=OSError("connection lost"))

        client = MagicMock()
        with patch("homeassistant.helpers.frame.report_usage"):
            coord = LuxtronikCoordinator(
                hass=hass,
                client=client,
                config={CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT},
            )

        with pytest.raises(UpdateFailed):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_async_shutdown(self):
        coord = _make_coordinator()
        coord.client = MagicMock()
        # Patch parent shutdown
        with patch.object(
            LuxtronikCoordinator.__bases__[0], "async_shutdown", new_callable=AsyncMock
        ):
            await coord.async_shutdown()
            # client should be deleted
            assert not hasattr(coord, "client") or coord.client is None


# ===========================================================================
# catch_luxtronik_errors decorator
# ===========================================================================


class TestCatchLuxtronikErrors:
    @pytest.mark.asyncio
    async def test_catches_exception_and_refreshes(self):
        @catch_luxtronik_errors
        async def failing_method(self):
            raise ValueError("test error")

        coord = _make_coordinator_direct()
        await failing_method(coord)
        coord.async_request_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calls_refresh_on_success(self):
        @catch_luxtronik_errors
        async def success_method(self):
            pass

        coord = _make_coordinator_direct()
        await success_method(coord)
        coord.async_request_refresh.assert_awaited_once()


# ===========================================================================
# _async_update_data (direct coordinator)
# ===========================================================================


class TestAsyncUpdateDataDirect:
    @pytest.mark.asyncio
    async def test_successful_update(self):
        coord = _make_coordinator_direct()
        coord.client.parameters = {"p1": 1}
        coord.client.calculations = {"c1": 2}
        coord.client.visibilities = {"v1": 3}
        coord.hass.async_add_executor_job = AsyncMock()
        result = await coord._async_update_data()
        assert result.parameters == {"p1": 1}

    @pytest.mark.asyncio
    async def test_update_raises_update_failed(self):
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock(
            side_effect=Exception("read fail")
        )
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()


# ===========================================================================
# async_write
# ===========================================================================


class TestAsyncWrite:
    @pytest.mark.asyncio
    async def test_successful_write(self):
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()

        # Make async_refresh update data
        async def fake_refresh():
            coord.data = LuxtronikCoordinatorData(
                parameters={"test_param": (0, 42)},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh
        result = await coord.async_write("test_param", 42)
        assert result is not None

    @pytest.mark.asyncio
    async def test_write_error(self):
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock(
            side_effect=Exception("write fail")
        )
        with pytest.raises(UpdateFailed):
            await coord.async_write("param", 1)


# ===========================================================================
# async_shutdown (direct coordinator)
# ===========================================================================


class TestAsyncShutdownDirect:
    @pytest.mark.asyncio
    async def test_shutdown_with_client(self):
        coord = _make_coordinator_direct()
        with patch(
            "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_shutdown",
            new_callable=AsyncMock,
        ):
            await coord.async_shutdown()
        assert not hasattr(coord, "client")

    @pytest.mark.asyncio
    async def test_shutdown_without_client(self):
        coord = _make_coordinator_direct()
        del coord.client
        with patch(
            "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_shutdown",
            new_callable=AsyncMock,
        ):
            await coord.async_shutdown()


# ===========================================================================
# _is_version_not_compatible
# ===========================================================================


class TestIsVersionNotCompatible:
    def test_no_constraints(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(key="test")
        assert coord._is_version_not_compatible(desc) is False

    def test_min_version_met(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", min_firmware_version=Version("3.0.0")
        )
        assert coord._is_version_not_compatible(desc) is False

    def test_min_version_not_met(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", min_firmware_version=Version("4.0.0")
        )
        assert coord._is_version_not_compatible(desc) is True

    def test_max_version_met(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", max_firmware_version=Version("4.0.0")
        )
        assert coord._is_version_not_compatible(desc) is False

    def test_max_version_exceeded(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", max_firmware_version=Version("3.0.0")
        )
        assert coord._is_version_not_compatible(desc) is True

    def test_min_minor_version_met(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", min_firmware_version_minor=Version("80.0")
        )
        assert coord._is_version_not_compatible(desc) is False

    def test_min_minor_version_not_met(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", min_firmware_version_minor=Version("91.0")
        )
        assert coord._is_version_not_compatible(desc) is True

    def test_max_minor_version_exceeded(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", max_firmware_version_minor=Version("89.0")
        )
        assert coord._is_version_not_compatible(desc) is True


# ===========================================================================
# Detection methods
# ===========================================================================


class TestDetectionMethods:
    def test_detect_solar_not_present(self):
        coord = _make_coordinator(
            visibilities={
                "ID_Visi_Solar": 0,
                "ID_Visi_Solar_Kollektor": 0,
                "ID_Visi_Solar_Puffer": 0,
            },
            parameters={"ID_BSTD_Solar": 0},
        )
        assert coord._detect_solar_present() is False

    def test_detect_solar_by_visibility(self):
        coord = _make_coordinator(
            visibilities={"ID_Visi_Solar": 1},
        )
        assert coord._detect_solar_present() is True

    def test_detect_solar_by_operation_hours(self):
        coord = _make_coordinator(
            visibilities={"ID_Visi_Solar": 0},
            parameters={"ID_BSTD_Solar": 100.0},
        )
        assert coord._detect_solar_present() is True

    def test_detect_solar_by_collector_temp(self):
        coord = _make_coordinator(
            visibilities={
                "ID_Visi_Solar": 0,
                "ID_Visi_Temp_Solarkoll": 1,
            },
            parameters={"ID_BSTD_Solar": 0},
            calculations={"ID_WEB_Temperatur_TSK": 25.0},
        )
        assert coord._detect_solar_present() is True

    def test_detect_solar_by_buffer_temp(self):
        coord = _make_coordinator(
            visibilities={
                "ID_Visi_Solar": 0,
                "ID_Visi_Temp_Solarkoll": 0,
                "ID_Visi_Temp_Solarsp": 1,
            },
            parameters={"ID_BSTD_Solar": 0},
            calculations={
                "ID_WEB_Temperatur_TSK": 5.0,
                "ID_WEB_Temperatur_TSS": 50.0,
            },
        )
        assert coord._detect_solar_present() is True

    def test_detect_dhw_circulation_pump_present(self):
        coord = _make_coordinator(
            parameters={"ID_Einst_BWZIP_akt": 0},
        )
        assert coord._detect_dhw_circulation_pump_present() is True

    def test_detect_dhw_circulation_pump_not_present(self):
        coord = _make_coordinator(
            parameters={"ID_Einst_BWZIP_akt": 1},
        )
        assert coord._detect_dhw_circulation_pump_present() is False

    def test_detect_dhw_circulation_pump_none(self):
        coord = _make_coordinator()
        assert coord._detect_dhw_circulation_pump_present() is False

    def test_detect_cooling_present(self):
        coord = _make_coordinator(
            parameters={
                "ID_Einst_MK1Typ_akt": 3,  # LuxMkTypes.cooling.value
            },
        )
        assert coord.detect_cooling_present() is True

    def test_detect_cooling_not_present(self):
        coord = _make_coordinator(
            parameters={
                "ID_Einst_MK1Typ_akt": 0,
                "ID_Einst_MK2Typ_akt": 0,
                "ID_Einst_HzMKE3_akt": 0,
            },
        )
        assert coord.detect_cooling_present() is False

    def test_get_device_creates_info(self):
        coord = _make_coordinator(
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Code_WP_akt": "LWP 10",
            },
            parameters={
                "ID_WP_SerienNummer_DATUM": 20230101,
                "ID_WP_SerienNummer_HEX": 255,
            },
        )
        device = coord.get_device(DeviceKey.heatpump)
        assert device is not None

    def test_detect_cooling_present_false(self):
        coord = _make_coordinator_direct()
        coord._detect_cooling_mk = MagicMock(return_value=[])
        assert coord.detect_cooling_present() is False

    def test_detect_cooling_present_true(self):
        coord = _make_coordinator_direct()
        coord._detect_cooling_mk = MagicMock(
            return_value=[LP.P0042_MIXING_CIRCUIT1_TYPE]
        )
        assert coord.detect_cooling_present() is True

    def test_detect_dhw_circulation_pump_is_1(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=1)
        assert coord._detect_dhw_circulation_pump_present() is False

    def test_detect_dhw_circulation_pump_not_1(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=0)
        assert coord._detect_dhw_circulation_pump_present() is True

    def test_detect_dhw_circulation_pump_exception(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(side_effect=Exception("err"))
        assert coord._detect_dhw_circulation_pump_present() is False


class TestCoordinatorGetDeviceFallback:
    def test_device_info_none_returns_fallback(self):
        coord = MagicMock()
        coord.device_infos = {}
        coord._create_device_infos = MagicMock()
        coord.unique_id = "test_uid"
        result = LuxtronikCoordinator.get_device(coord, DeviceKey.heatpump)
        assert "identifiers" in result

    def test_build_device_name_with_platform(self):
        coord = MagicMock()
        platform = MagicMock()
        platform.platform_data.platform_translations.get.return_value = "My Heatpump"
        result = LuxtronikCoordinator._build_device_name(
            coord, DeviceKey.heatpump, platform
        )
        assert result == "My Heatpump"


# ===========================================================================
# LuxtronikConnectionError
# ===========================================================================


class TestLuxtronikConnectionError:
    def test_message_format(self):
        orig = ConnectionRefusedError("refused")
        err = LuxtronikConnectionError("192.168.1.100", DEFAULT_PORT, orig)
        assert "192.168.1.100" in str(err)
        assert str(DEFAULT_PORT) in str(err)
        assert "ConnectionRefusedError" in str(err)
        assert err.host == "192.168.1.100"
        assert err.port == DEFAULT_PORT
        assert err.original is orig


# ===========================================================================
# connect_and_get_coordinator
# ===========================================================================


class TestConnectAndGetCoordinator:
    @pytest.fixture(autouse=True)
    def _reset_overrides_flag(self):
        """Reset the global _OVERRIDES_APPLIED flag before each test."""
        import custom_components.luxtronik2.coordinator as coord_mod

        coord_mod._OVERRIDES_APPLIED = False
        yield
        coord_mod._OVERRIDES_APPLIED = False

    @pytest.mark.asyncio
    async def test_connect_failure_raises_connection_error(self):
        from custom_components.luxtronik2.coordinator import connect_and_get_coordinator

        config = {CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT}

        with patch(
            "custom_components.luxtronik2.coordinator.LuxtronikCoordinator.connect",
            side_effect=ConnectionRefusedError("refused"),
        ):
            with pytest.raises(LuxtronikConnectionError) as exc_info:
                await connect_and_get_coordinator(MagicMock(), config)
            assert exc_info.value.host == "192.168.1.100"
            assert exc_info.value.port == DEFAULT_PORT

    @pytest.mark.asyncio
    async def test_overrides_applied_once(self):
        from custom_components.luxtronik2.coordinator import connect_and_get_coordinator

        config = {CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT}

        with (
            patch(
                "custom_components.luxtronik2.coordinator.LuxtronikCoordinator.connect",
                side_effect=ConnectionRefusedError("refused"),
            ),
            patch(
                "custom_components.luxtronik2.coordinator.update_Luxtronik_HeatpumpCodes"
            ) as mock_hpc,
            patch(
                "custom_components.luxtronik2.coordinator.update_Luxtronik_Parameters"
            ) as mock_params,
            patch(
                "custom_components.luxtronik2.coordinator.isolate_instance_data"
            ) as mock_iso,
        ):
            # First call applies overrides
            with pytest.raises(LuxtronikConnectionError):
                await connect_and_get_coordinator(MagicMock(), config)
            assert mock_hpc.call_count == 1
            assert mock_params.call_count == 1
            assert mock_iso.call_count == 1

            # Second call skips overrides
            with pytest.raises(LuxtronikConnectionError):
                await connect_and_get_coordinator(MagicMock(), config)
            assert mock_hpc.call_count == 1  # not called again

"""Tests for custom_components.luxtronik2.coordinator."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed
from packaging.version import Version
import pytest

from conftest import make_coordinator_data
from custom_components.luxtronik2.const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_UPDATE_INTERVAL,
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
    LuxtronikSerialNumberError,
    LuxtronikWriteError,
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
    coord.update_interval = DEFAULT_UPDATE_INTERVAL
    coord.last_update_success = True
    if data is None:
        data = LuxtronikCoordinatorData(
            parameters={"ID_WEB_WP_BZ_akt": (0, 0)},
            calculations={"ID_WEB_WP_BZ_akt": (0, 0)},
            visibilities={"ID_WEB_Sichtbar_Solar": (0, 1)},
        )
    coord.data = data
    return coord


class TestUpdateIntervalConfig:
    def test_default_update_interval_when_missing(self):
        coord = _make_coordinator()
        with patch.object(coord, "_async_update_data", new_callable=AsyncMock):
            pass
        assert coord.update_interval is not None
        assert coord.update_interval == DEFAULT_UPDATE_INTERVAL

    def test_custom_update_interval_from_config(self):
        config = {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_UPDATE_INTERVAL: "1 minute (default)",
        }
        with patch("homeassistant.helpers.frame.report_usage"):
            coord = LuxtronikCoordinator(
                hass=MagicMock(), client=MagicMock(), config=config
            )
        assert coord.update_interval is not None
        assert coord.update_interval.total_seconds() == 60

    def test_unknown_update_interval_falls_back_to_default(self):
        config = {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_UPDATE_INTERVAL: "not_a_real_option",
        }
        with patch("homeassistant.helpers.frame.report_usage"):
            coord = LuxtronikCoordinator(
                hass=MagicMock(), client=MagicMock(), config=config
            )
        assert coord.update_interval is not None
        assert coord.update_interval.total_seconds() == 60

    def test_all_known_intervals_map_correctly(self):
        expected = {
            "10 seconds": 10,
            "30 seconds": 30,
            "1 minute (default)": 60,
            "5 minutes": 300,
        }
        for label, seconds in expected.items():
            config = {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: DEFAULT_PORT,
                CONF_UPDATE_INTERVAL: label,
            }
            with patch("homeassistant.helpers.frame.report_usage"):
                coord = LuxtronikCoordinator(
                    hass=MagicMock(), client=MagicMock(), config=config
                )
            assert coord.update_interval is not None
            assert coord.update_interval.total_seconds() == seconds


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

    def test_serial_number_missing_date_raises(self):
        coord = _make_coordinator()
        with pytest.raises(LuxtronikSerialNumberError):
            _ = coord.serial_number

    def test_room_thermostat_type(self):
        coord = _make_coordinator(parameters={"ID_Einst_RFVEinb_akt": 4})
        thermostat_type = coord.room_thermostat_type
        assert thermostat_type == LuxRoomThermostatType.rbe

        coord = _make_coordinator(
            parameters={"ID_Einst_RFVEinb_akt": 4}, calculations={"RBE_Version": "4.03"}
        )
        thermostat_type = coord.room_thermostat_type
        assert thermostat_type == LuxRoomThermostatType.rbe_plus

        coord = _make_coordinator(parameters={"ID_Einst_RFVEinb_akt": 5})
        thermostat_type = coord.room_thermostat_type
        assert thermostat_type == LuxRoomThermostatType.smart

        coord = _make_coordinator(parameters={"ID_Einst_RFVEinb_akt": 99})
        thermostat_type = coord.room_thermostat_type
        assert thermostat_type == 99  # Unknown but returned as int

        coord = _make_coordinator(parameters={"ID_Einst_RFVEinb_akt": "unknown"})
        thermostat_type = coord.room_thermostat_type
        assert thermostat_type is None

    def test_room_thermostat_type_missing_param(self):
        coord = _make_coordinator()  # No P0033 parameter
        assert coord.room_thermostat_type is None

    def test_room_thermostat_type_get_value_raises(self):
        coord = _make_coordinator()
        with patch.object(coord, "get_value", side_effect=Exception("boom")):
            assert coord.room_thermostat_type is None


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

    def test_heating_always_active_without_usage_hours(self):
        """Heating device should show up even if heating has never run yet (#655)."""
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitHz": 0})
        assert coord.device_key_active(DeviceKey.heating) is True

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

    def test_cooling_active_without_usage_hours_when_configured(self):
        """Cooling device should show up even if cooling has never run yet (#655)."""
        coord = _make_coordinator(
            calculations={"ID_WEB_Zaehler_BetrZeitKue": 0},
            parameters={"ID_Einst_MK1Typ_akt": 3},  # LuxMkTypes.cooling.value
        )
        assert coord.device_key_active(DeviceKey.cooling) is True

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

    def test_visibility_formula_numeric_greater_than(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=11)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.visibility_formula = "> 10"
        assert coord.entity_visible(desc) is True

    def test_visibility_formula_numeric_less_than(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=9)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.visibility_formula = "> 10"
        assert coord.entity_visible(desc) is False

    def test_visibility_formula_boolean_true(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.visibility_formula = "== True"
        assert coord.entity_visible(desc) is True

    def test_visibility_formula_boolean_false(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=False)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.visibility_formula = "== True"
        assert coord.entity_visible(desc) is False

    def test_visibility_formula_none_value_falls_back(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=None)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.visibility_formula = "> 10"
        assert coord.entity_visible(desc) is True

    def test_visibility_formula_unsupported_operator(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=15)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.visibility_formula = "~ 10"
        assert coord.entity_visible(desc) is True

    def test_visibility_formula_boolean_false_threshold(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=False)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.visibility_formula = "== False"
        assert coord.entity_visible(desc) is True

    def test_visibility_formula_string_value_boolean(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value="true")
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.visibility_formula = "== True"
        assert coord.entity_visible(desc) is True

    def test_visibility_formula_operator_raises_exception(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=10)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.visibility_formula = "== something"

        def _raise(*_args, **_kwargs):
            raise RuntimeError("operator failed")

        with patch.object(coord, "_VISIBILITY_FORMULA_OPERATORS", {"==": _raise}):
            assert coord.entity_visible(desc) is True

    def test_visibility_formula_invalid_falls_back(self):
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value=11)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.visibility_formula = "invalid"
        assert coord.entity_visible(desc) is True


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

    def test_entity_active_formula_match(self):
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
            entity_active_formula="== Off",
        )
        assert coord.entity_active(desc) is True

    def test_entity_active_formula_no_match(self):
        coord = _make_coordinator(
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Zaehler_BetrZeitHz": 100,
            },
            parameters={"ID_Ba_Hz_akt": "On"},
        )
        desc = LuxtronikEntityDescription(
            key="test",
            luxtronik_key=LP.P0003_MODE_HEATING,
            entity_active_formula="== Off",
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

    def test_entity_active_formula_value_matches(self):
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.device_key_active = MagicMock(return_value=True)
        coord.get_value = MagicMock(return_value=42)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.device_key = DeviceKey.heatpump
        desc.entity_active_formula = "== 42"
        desc.luxtronik_key = LP.P0001_HEATING_TARGET_CORRECTION
        assert coord.entity_active(desc) is True

    def test_entity_active_formula_value_no_match(self):
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.device_key_active = MagicMock(return_value=True)
        coord.get_value = MagicMock(return_value=99)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.device_key = DeviceKey.heatpump
        desc.entity_active_formula = "== 42"
        desc.luxtronik_key = LP.P0001_HEATING_TARGET_CORRECTION
        assert coord.entity_active(desc) is False


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
        value = sensor[1] if isinstance(sensor, tuple) else sensor.value
        assert value == "Automatic"

    def test_get_sensor_unknown_group(self):
        coord = _make_coordinator()
        assert coord.get_sensor("unknown_group", "some_key") is None

    def test_get_sensor_no_data_yet(self):
        coord = _make_coordinator()
        coord.data = None
        assert coord.get_sensor("parameters", "some_key") is None


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
        with pytest.raises(LuxtronikWriteError):
            await coord.async_write("param", 1)

    @pytest.mark.asyncio
    async def test_write_mismatch_raises(self):
        """If the device rejects/clamps a write, the read-back after refresh
        will differ from what was written - this must surface as an error,
        not just a debug log, so the UI re-syncs instead of showing a stale
        optimistic value."""
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()

        async def fake_refresh():
            # Device clamped the write: asked for 42, device kept 40.
            coord.data = LuxtronikCoordinatorData(
                parameters={"test_param": (0, 40)},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh

        with pytest.raises(HomeAssistantError) as exc_info:
            await coord.async_write("test_param", 42)
        assert not isinstance(exc_info.value, LuxtronikWriteError)
        assert exc_info.value.translation_key == "write_confirmation_mismatch"

    @pytest.mark.asyncio
    async def test_write_match_with_float_rounding_does_not_raise(self):
        """Confirmation must tolerate float noise from 0.1-step datatypes
        (e.g. Celsius: raw/10) instead of raising on a spurious mismatch."""
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()

        async def fake_refresh():
            coord.data = LuxtronikCoordinatorData(
                parameters={"test_param": (0, 21.500000000000004)},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh

        result = await coord.async_write("test_param", 21.5)
        assert result is not None


class TestAsyncWriteMany:
    @pytest.mark.asyncio
    async def test_queues_all_pairs_before_single_write_call(self):
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()

        async def fake_refresh():
            coord.data = LuxtronikCoordinatorData(
                parameters={"p1": (0, "06:00"), "p2": (0, "22:00")},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh

        await coord.async_write_many([("p1", "06:00"), ("p2", "22:00")])

        calls = coord.hass.async_add_executor_job.await_args_list
        # Two parameters.set calls followed by exactly one client.write call.
        assert calls[0].args[0] == coord.client.parameters.set
        assert calls[0].args[1:] == ("p1", "06:00")
        assert calls[1].args[0] == coord.client.parameters.set
        assert calls[1].args[1:] == ("p2", "22:00")
        assert calls[2].args == (coord.client.write,)
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_issues_single_refresh(self):
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()
        coord.async_refresh = AsyncMock(
            side_effect=lambda: setattr(
                coord,
                "data",
                LuxtronikCoordinatorData(
                    parameters={"p1": (0, "06:00"), "p2": (0, "22:00")},
                    calculations={},
                    visibilities={},
                ),
            )
        )

        await coord.async_write_many([("p1", "06:00"), ("p2", "22:00")])

        coord.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_single_pair_matches_async_write_behavior(self):
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()

        async def fake_refresh():
            coord.data = LuxtronikCoordinatorData(
                parameters={"test_param": (0, 42)},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh
        result = await coord.async_write_many([("test_param", 42)])
        assert result is not None

    @pytest.mark.asyncio
    async def test_mismatch_reports_offending_parameter(self):
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()

        async def fake_refresh():
            coord.data = LuxtronikCoordinatorData(
                parameters={"p1": (0, "06:00"), "p2": (0, "00:00")},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh

        with pytest.raises(HomeAssistantError) as exc_info:
            await coord.async_write_many([("p1", "06:00"), ("p2", "22:00")])
        assert exc_info.value.translation_key == "write_confirmation_mismatch"
        details = exc_info.value.translation_placeholders["details"]
        assert "p2" in details
        assert "p1" not in details

    @pytest.mark.asyncio
    async def test_refresh_failure_raises_distinct_error_not_mismatch(self):
        """DataUpdateCoordinator.async_refresh() swallows failures internally
        (logs, does not raise) rather than propagating them. If the post-write
        refresh fails, self.data stays at its stale pre-write value, and
        comparing the newly-written value against stale data would almost
        always look like a mismatch - misleadingly claiming the device
        rejected the write when only the confirming read failed. This must
        surface as a distinct error, not write_confirmation_mismatch, and the
        mismatch comparison must not run against stale data at all."""
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()

        async def fake_refresh():
            # async_refresh() "succeeds" (returns normally, no exception) but
            # leaves last_update_success False and self.data untouched/stale,
            # exactly like a real transient socket hiccup during the read.
            coord.last_update_success = False

        coord.async_refresh = fake_refresh

        with pytest.raises(HomeAssistantError) as exc_info:
            await coord.async_write_many([("p1", "06:00")])

        assert exc_info.value.translation_key == "write_confirmation_unavailable"
        assert exc_info.value.translation_key != "write_confirmation_mismatch"

    @pytest.mark.asyncio
    async def test_refresh_success_with_flag_true_still_confirms_normally(self):
        """Sanity check: when last_update_success is True (the normal case)
        and the written value matches, async_write_many must still return
        normally - no regression from the new check."""
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()

        async def fake_refresh():
            coord.last_update_success = True
            coord.data = LuxtronikCoordinatorData(
                parameters={"p1": (0, "06:00")},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh

        result = await coord.async_write_many([("p1", "06:00")])
        assert result is not None


class TestWriteConfirmed:
    """Unit tests for the read-back comparison helper used by async_write /
    async_write_many."""

    def test_exact_match(self):
        from custom_components.luxtronik2.coordinator import _write_confirmed

        assert _write_confirmed("06:00", "06:00") is True

    def test_exact_mismatch(self):
        from custom_components.luxtronik2.coordinator import _write_confirmed

        assert _write_confirmed("06:00", "07:00") is False

    def test_int_vs_float_numeric_match(self):
        from custom_components.luxtronik2.coordinator import _write_confirmed

        assert _write_confirmed(42, 42.0) is True

    def test_rounds_to_one_decimal_for_float_noise(self):
        from custom_components.luxtronik2.coordinator import _write_confirmed

        assert _write_confirmed(21.5, 21.500000000000004) is True

    def test_numeric_mismatch_beyond_tolerance(self):
        from custom_components.luxtronik2.coordinator import _write_confirmed

        assert _write_confirmed(21.5, 21.7) is False

    def test_bool_and_int_equivalence(self):
        from custom_components.luxtronik2.coordinator import _write_confirmed

        assert _write_confirmed(True, 1) is True
        assert _write_confirmed(False, 0) is True

    def test_type_mismatch_no_coercion(self):
        from custom_components.luxtronik2.coordinator import _write_confirmed

        assert _write_confirmed("42", 42) is False


# ===========================================================================
# async_shutdown (direct coordinator)
# ===========================================================================


class TestAsyncShutdownDirect:
    @pytest.mark.asyncio
    async def test_shutdown_with_client(self):
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock(
            side_effect=lambda fn, *a, **kw: fn(*a, **kw)
        )
        client = coord.client
        with patch(
            "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_shutdown",
            new_callable=AsyncMock,
        ):
            await coord.async_shutdown()
        assert not hasattr(coord, "client")
        client.disconnect.assert_called_once()

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

    @pytest.mark.asyncio
    async def test_initial_refresh_uses_async_refresh_for_dict_config(self):
        from custom_components.luxtronik2.coordinator import connect_and_get_coordinator

        config = {CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT}
        coordinator = MagicMock()
        coordinator.async_refresh = AsyncMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()

        with patch(
            "custom_components.luxtronik2.coordinator.LuxtronikCoordinator.connect",
            new_callable=AsyncMock,
            return_value=coordinator,
        ):
            result = await connect_and_get_coordinator(MagicMock(), config)

        assert result is coordinator
        coordinator.async_refresh.assert_awaited_once()
        coordinator.async_config_entry_first_refresh.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_initial_refresh_failure_raises_connection_error(self):
        """async_refresh() swallows failures; connect_and_get_coordinator must not."""
        from custom_components.luxtronik2.coordinator import connect_and_get_coordinator

        config = {CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT}
        coordinator = MagicMock()
        coordinator.async_refresh = AsyncMock()
        coordinator.last_update_success = False

        with (
            patch(
                "custom_components.luxtronik2.coordinator.LuxtronikCoordinator.connect",
                new_callable=AsyncMock,
                return_value=coordinator,
            ),
            pytest.raises(LuxtronikConnectionError),
        ):
            await connect_and_get_coordinator(MagicMock(), config)

    @pytest.mark.asyncio
    async def test_initial_refresh_uses_config_entry_first_refresh_for_config_entry(
        self,
    ):
        from custom_components.luxtronik2.coordinator import connect_and_get_coordinator

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.data = {CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT}
        config_entry.options = {}
        coordinator = MagicMock()
        coordinator.async_refresh = AsyncMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()

        with patch(
            "custom_components.luxtronik2.coordinator.LuxtronikCoordinator.connect",
            new_callable=AsyncMock,
            return_value=coordinator,
        ):
            result = await connect_and_get_coordinator(MagicMock(), config_entry)

        assert result is coordinator
        coordinator.async_config_entry_first_refresh.assert_awaited_once()
        coordinator.async_refresh.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_config_entry_options_merged(self):
        from custom_components.luxtronik2.coordinator import connect_and_get_coordinator

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.data = {CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT}
        config_entry.options = {"update_interval": "5 minutes"}

        with (
            patch(
                "custom_components.luxtronik2.coordinator.LuxtronikCoordinator.connect",
                side_effect=ConnectionRefusedError("refused"),
            ),
            pytest.raises(LuxtronikConnectionError),
        ):
            await connect_and_get_coordinator(MagicMock(), config_entry)

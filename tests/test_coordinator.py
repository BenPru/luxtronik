"""Tests for custom_components.luxtronik2.coordinator."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed
from packaging.version import Version
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from conftest import make_coordinator_data
from custom_components.luxtronik2.const import (
    CONF_SUPPORTS_TIME_24_00,
    CONF_UPDATE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    DeviceKey,
    LuxCalculation as LC,
    LuxMkTypes,
    LuxOperationMode,
    LuxParameter as LP,
    LuxRoomThermostatType,
    LuxStatus3Option,
    LuxVisibility as LV,
    SensorKey,
)
from custom_components.luxtronik2.coordinator import (
    WRITE_CONFIRM_INITIAL_DELAY,
    WRITE_CONFIRM_MAX_ATTEMPTS,
    WRITE_CONFIRM_MAX_DELAY,
    WRITE_FOLLOWUP_DELAY,
    LuxtronikConnectionError,
    LuxtronikCoordinator,
    LuxtronikSerialNumberError,
    LuxtronikWriteError,
)
from custom_components.luxtronik2.lux_overrides import TimeOfDay
from custom_components.luxtronik2.model import (
    LuxtronikCoordinatorData,
    LuxtronikEntityDescription,
)
from custom_components.luxtronik2.number_entities_predefined import NUMBER_SENSORS
from custom_components.luxtronik2.sensor_entities_predefined import SENSORS

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
    coord._dhw_hold_until = None
    coord._evu2_manual = False
    coord._write_followup_unsub = None
    # Real coordinators always have one; `object.__new__` skips the base
    # class __init__ that would set it.
    coord.config_entry = None
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

    def test_firmware_series(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        assert coord.firmware_series == 3

    def test_firmware_series_of_a_luxtronik_2_0(self):
        """The generation that counts aux heater energy in 0.01 kWh (#752)."""
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V2.88.3"})
        assert coord.firmware_series == 2

    def test_firmware_series_unparseable(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "invalid"})
        assert coord.firmware_series == 0

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

    def test_ventilation_active_when_both_air_temperatures_report(self):
        """A ventilation module reports real supply and exhaust air
        temperatures; units without one report 0.0 for both (issue #729)."""
        coord = _make_coordinator(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 17.4,
                "ID_WEB_Temp_Lueftung_Abluft": 21.2,
            }
        )
        assert coord.device_key_active(DeviceKey.ventilation) is True

    def test_ventilation_inactive_when_both_air_temperatures_are_zero(self):
        """The no-module signal: both channels flat at 0.0 (measured on an
        Alpha Innotec MSW4-16, which has no ventilation module)."""
        coord = _make_coordinator(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 0.0,
                "ID_WEB_Temp_Lueftung_Abluft": 0.0,
            }
        )
        assert coord.device_key_active(DeviceKey.ventilation) is False

    def test_ventilation_active_when_only_one_air_temperature_reports(self):
        """One live channel is enough. #729's reporter runs a working module
        whose exhaust channel has no sensor, so requiring both would hide the
        device from the installation that asked for it."""
        coord = _make_coordinator(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 0.0,
                "ID_WEB_Temp_Lueftung_Abluft": 21.2,
            }
        )
        assert coord.device_key_active(DeviceKey.ventilation) is True

    def test_ventilation_active_when_other_channel_is_a_sentinel(self):
        """5.0 is the unwired-sensor placeholder, not a reading: #729's
        exhaust channel held it for 18 h without a single state change while
        supply drifted through 229. The live supply channel decides."""
        coord = _make_coordinator(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 24.1,
                "ID_WEB_Temp_Lueftung_Abluft": 5.0,
            }
        )
        assert coord.device_key_active(DeviceKey.ventilation) is True

    def test_ventilation_inactive_when_both_channels_are_sentinels(self):
        """5.0 / 75.0 are the same placeholders unconnected TRL_ext, TEE and
        TFB1-3 channels report, so two of them are no evidence of a module."""
        coord = _make_coordinator(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 75.0,
                "ID_WEB_Temp_Lueftung_Abluft": 5.0,
            }
        )
        assert coord.device_key_active(DeviceKey.ventilation) is False

    def test_ventilation_inactive_when_air_temperatures_are_not_numeric(self):
        """A non-numeric reading is not evidence of a ventilation module, and
        must not raise out of a device-gating check either."""
        coord = _make_coordinator(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": "n/a",
                "ID_WEB_Temp_Lueftung_Abluft": "n/a",
            }
        )
        assert coord.device_key_active(DeviceKey.ventilation) is False

    def test_ventilation_inactive_when_air_temperatures_missing(self):
        """Firmware that does not expose these calculations at all must not
        produce a ventilation device."""
        coord = _make_coordinator(calculations={})
        assert coord.device_key_active(DeviceKey.ventilation) is False

    def test_ventilation_stays_active_once_detected(self):
        """The detection latches on, because the evidence is a live reading.

        A supply-air channel genuinely passing through 0.0 or 5.0 C - while
        the exhaust channel sits on the unwired 5.0 sentinel - makes both
        channels look absent for that poll. Without the latch the device
        would disappear and come back, and `text.py` (the only per-poll
        caller of `entity_active`) would tear its schedule entities down and
        rebuild them each time.
        """
        coord = _make_coordinator(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 17.4,
                "ID_WEB_Temp_Lueftung_Abluft": 5.0,
            }
        )
        assert coord.device_key_active(DeviceKey.ventilation) is True

        # The supply air drifts down onto a sentinel: both channels now look
        # absent, but the module has not gone anywhere.
        coord.data = make_coordinator_data(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 5.0,
                "ID_WEB_Temp_Lueftung_Abluft": 5.0,
            }
        )
        assert coord.device_key_active(DeviceKey.ventilation) is True

    def test_ventilation_detected_on_a_later_poll(self):
        """A first poll landing on a sentinel must not be final.

        This is why the gate latches on rather than being evaluated once at
        setup: a restart during a cold spell would otherwise hide the module
        for the whole session.
        """
        coord = _make_coordinator(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 0.0,
                "ID_WEB_Temp_Lueftung_Abluft": 0.0,
            }
        )
        assert coord.device_key_active(DeviceKey.ventilation) is False

        coord.data = make_coordinator_data(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 17.4,
                "ID_WEB_Temp_Lueftung_Abluft": 0.0,
            }
        )
        assert coord.device_key_active(DeviceKey.ventilation) is True

    def test_ventilation_latch_is_per_coordinator(self):
        """The latch lives in memory, so a fresh entry re-detects."""
        detected = _make_coordinator(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 17.4,
                "ID_WEB_Temp_Lueftung_Abluft": 21.2,
            }
        )
        assert detected.device_key_active(DeviceKey.ventilation) is True

        fresh = _make_coordinator(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 0.0,
                "ID_WEB_Temp_Lueftung_Abluft": 0.0,
            }
        )
        assert fresh.device_key_active(DeviceKey.ventilation) is False

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

    def test_non_numeric_visibility_value_is_visible(self):
        """A visibility register a datatype decodes to a name must not raise.

        Nothing knows what such a value means, so it falls open the same way
        an unreadable register does - an entity enabled by default is a far
        smaller failure than a platform that does not load at all. #773
        """
        coord = _make_coordinator_direct()
        coord.get_value = MagicMock(return_value="plus_minus")
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.visibility_formula = None
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

    def test_last_defrost_needs_a_populated_register(self):
        """P1119 is 0 on every V1/V2 and brine unit in the corpus and absent
        on old firmware; only V3 air units hold a timestamp. The datatype
        maps 0 to None, so the generic formula path (which treats None as
        "not returned") is the whole gate - no special case needed.
        """
        from datetime import UTC, datetime

        description = next(d for d in SENSORS if d.key == SensorKey.LAST_DEFROST)
        assert description.entity_active_formula is not None

        never = _make_coordinator(parameters={"LAST_DEFROST_TIMESTAMP": None})
        assert never.entity_active(description) is False
        absent = _make_coordinator(parameters={})
        assert absent.entity_active(description) is False
        defrosted = _make_coordinator(
            parameters={
                "LAST_DEFROST_TIMESTAMP": datetime(2025, 7, 22, 13, 29, tzinfo=UTC)
            }
        )
        assert defrosted.entity_active(description) is True

    def test_last_defrost_raw_zero_through_the_real_datatype(self):
        """Pins the two halves together: a raw 0 really decodes to the None
        the gate acts on, and a raw epoch really passes it."""
        from luxtronik.parameters import Parameters

        from custom_components.luxtronik2.lux_overrides import (
            update_Luxtronik_Parameters,
        )

        update_Luxtronik_Parameters()
        datatype = Parameters.parameters[1119]
        description = next(d for d in SENSORS if d.key == SensorKey.LAST_DEFROST)
        for raw, expected in ((0, False), (1753190960, True)):
            coord = _make_coordinator(
                parameters={"LAST_DEFROST_TIMESTAMP": datatype.from_heatpump(raw)}
            )
            assert coord.entity_active(description) is expected, raw

    def test_exhaust_air_temperature_needs_a_wired_sensor(self):
        """Two LWC407s (#729, #807) run a ventilation module whose exhaust
        channel is not wired: the register sits on the controller's 5.0
        placeholder for days while supply air drifts. The ventilation device
        still exists on the live supply channel, but the exhaust sensor must
        not - a flat 5 C the controller's own display never shows is not a
        reading. Supply air is deliberately not gated: it can genuinely pass
        through 5.0 after heat recovery on a cold morning, and no unwired
        supply channel has been reported.
        """
        exhaust = next(
            d for d in SENSORS if d.key == SensorKey.VENTILATION_EXHAUST_AIR_TEMPERATURE
        )
        supply = next(
            d for d in SENSORS if d.key == SensorKey.VENTILATION_SUPPLY_AIR_TEMPERATURE
        )
        unwired = _make_coordinator(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 22.4,
                "ID_WEB_Temp_Lueftung_Abluft": 5.0,
            }
        )
        assert unwired.device_key_active(DeviceKey.ventilation) is True
        assert unwired.entity_active(exhaust) is False
        assert unwired.entity_active(supply) is True

        wired = _make_coordinator(
            calculations={
                "ID_WEB_Temp_Lueftung_Zuluft": 5.0,
                "ID_WEB_Temp_Lueftung_Abluft": 21.2,
            }
        )
        assert wired.entity_active(exhaust) is True
        assert wired.entity_active(supply) is True

    def test_version_not_compatible(self):
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        assert coord.entity_active(desc) is False

    @staticmethod
    def _twin_description() -> LuxtronikEntityDescription:
        return LuxtronikEntityDescription(
            key="test",
            luxtronik_key=LP.P1015_HEAT_AMOUNT_HEATING_2,
            device_key=DeviceKey.heating,
            entity_active_key=LP.P1010_IS_TWIN,
            entity_active_formula="!= 0",
        )

    def test_entity_active_key_reads_another_register(self):
        """The formula judges `entity_active_key` rather than the entity's own
        register, so a description can declare "exists only if some other
        register says so" without a gate of its own in this class. Here the
        own register counts, but P1010 says single unit - the entity must not
        exist (#815).
        """
        coord = _make_coordinator(
            calculations={"ID_WEB_Zaehler_BetrZeitHz": 100},
            parameters={"ID_Einst_isTwin": False, "ID_Waermemenge_Hz_2": 5.0},
        )
        assert coord.entity_active(self._twin_description()) is False

    def test_compressor_2_counters_inactive_on_single_unit(self):
        """Every non-twin pump in the diagnostics corpus returns the whole
        compressor-2 block, reading 0, so presence alone would give each of
        them four dead energy sensors. P1010 decides instead (#815).
        """
        coord = _make_coordinator(
            calculations={"ID_WEB_Zaehler_BetrZeitHz": 100},
            parameters={"ID_Einst_isTwin": False, "ID_Waermemenge_Hz_2": 0.0},
        )
        assert coord.entity_active(self._twin_description()) is False

    def test_compressor_2_counters_active_on_twin_unit(self):
        """The #782 LD7 reads isTwin = 1 and counts on 1015-1018."""
        coord = _make_coordinator(
            calculations={"ID_WEB_Zaehler_BetrZeitHz": 100},
            parameters={"ID_Einst_isTwin": True, "ID_Waermemenge_Hz_2": 108029.76},
        )
        assert coord.entity_active(self._twin_description()) is True

    def test_entity_active_key_ignores_own_register_value(self):
        """A twin whose compressor-2 counter still reads 0 (fresh install, no
        DHW cycle yet) must still get the entity: the gate is P1010, not the
        counter moving.
        """
        coord = _make_coordinator(
            calculations={"ID_WEB_Zaehler_BetrZeitHz": 100},
            parameters={"ID_Einst_isTwin": True, "ID_Waermemenge_Hz_2": 0.0},
        )
        assert coord.entity_active(self._twin_description()) is True

    def test_compressor_2_counters_inactive_when_p1010_is_absent(self):
        """A controller that never returns P1010 is not a twin: fall closed."""
        coord = _make_coordinator(
            calculations={"ID_WEB_Zaehler_BetrZeitHz": 100},
            parameters={"ID_Waermemenge_Hz_2": 0.0},
        )
        assert coord.entity_active(self._twin_description()) is False

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

    def test_entity_active_formula_absent_register(self):
        """A register the controller does not expose must not get an entity."""
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.device_key_active = MagicMock(return_value=True)
        coord.get_value = MagicMock(return_value=None)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.device_key = DeviceKey.heatpump
        desc.entity_active_formula = "!= 0.0"
        desc.luxtronik_key = LP.P0001_HEATING_TARGET_CORRECTION
        assert coord.entity_active(desc) is False

    def test_entity_active_formula_zero_is_not_absent(self):
        """A register reading 0.0 is present - the formula decides, not the None check.

        A formula that 0.0 satisfies is the only way to tell the two apart: an
        active entity here is reachable only if 0.0 reached the evaluator rather
        than short-circuiting on the absent-register check.
        """
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.device_key_active = MagicMock(return_value=True)
        coord.get_value = MagicMock(return_value=0.0)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.device_key = DeviceKey.heatpump
        desc.entity_active_formula = "== 0.0"
        desc.luxtronik_key = LP.P0001_HEATING_TARGET_CORRECTION
        assert coord.entity_active(desc) is True

    def test_entity_active_formula_nonzero_creates_entity(self):
        """A register with a real reading passes the formula and gets an entity."""
        coord = _make_coordinator_direct()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.device_key_active = MagicMock(return_value=True)
        coord.get_value = MagicMock(return_value=12.3)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.device_key = DeviceKey.heatpump
        desc.entity_active_formula = "!= 0.0"
        desc.luxtronik_key = LP.P0001_HEATING_TARGET_CORRECTION
        assert coord.entity_active(desc) is True


# ===========================================================================
# get_value / get_sensor
# ===========================================================================


class TestFormulaInOperator:
    """`in a,b,...` is `==` against each item, with the same coercions."""

    def test_matches_a_raw_code(self):
        coord = _make_coordinator_direct()
        assert coord._evaluate_visibility_formula(3, "in 3,4,cooling") is True

    def test_matches_a_decoded_name(self):
        coord = _make_coordinator_direct()
        assert coord._evaluate_visibility_formula("cooling", "in 3,4,cooling") is True

    def test_matches_a_float_code(self):
        coord = _make_coordinator_direct()
        assert coord._evaluate_visibility_formula(4.0, "in 3,4") is True

    def test_misses(self):
        coord = _make_coordinator_direct()
        assert coord._evaluate_visibility_formula(2, "in 3,4,cooling") is False
        assert coord._evaluate_visibility_formula("load", "in 3,4,cooling") is False


def _number(key: SensorKey):
    return next(d for d in NUMBER_SENSORS if d.key == key)


def _sensor(key: SensorKey):
    return next(d for d in SENSORS if d.key == key)


class TestDeclaredActiveGates:
    """Gates declared on the predefined descriptions through
    `entity_active_key`, exercised on the real descriptions so a test fails
    if the declaration is dropped, not only if the coordinator breaks.
    """

    # region Room thermostat - P0033, not V0122
    # V0122 is the menu entry, not the device: it reads 1 on every unit in the
    # diagnostics corpus, including the 24 with P0033 = 0 whose room-
    # thermostat registers then sit at 0.0 forever. P0033 decides.
    ROOM_THERMOSTAT = (
        (SENSORS, SensorKey.ROOM_THERMOSTAT_TEMPERATURE),
        (SENSORS, SensorKey.ROOM_THERMOSTAT_TEMPERATURE_TARGET),
        (NUMBER_SENSORS, SensorKey.HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR),
    )

    @staticmethod
    def _room_thermostat_coord(p0033: Any = None) -> LuxtronikCoordinator:
        parameters: dict[str, Any] = {"ID_RBE_Einflussfaktor_RT_akt": 100}
        if p0033 is not None:
            parameters["ID_Einst_RFVEinb_akt"] = p0033
        return _make_coordinator(
            visibilities={"ID_Visi_SysEin_Raumstation": 1},
            parameters=parameters,
            calculations={"ID_WEB_RBE_RT_Ist": 21.0, "ID_WEB_RBE_RT_Soll": 21.5},
        )

    def _room_thermostat_active(self, p0033: Any) -> list[bool]:
        coord = self._room_thermostat_coord(p0033)
        return [
            coord.entity_active(next(d for d in group if d.key == key))
            for group, key in self.ROOM_THERMOSTAT
        ]

    def test_room_thermostat_entities_not_created_without_thermostat(self):
        assert self._room_thermostat_active(0) == [False, False, False]

    def test_room_thermostat_entities_created_with_thermostat(self):
        assert self._room_thermostat_active(4) == [True, True, True]

    def test_room_thermostat_unknown_type_counts_as_present(self):
        """A code the enum does not know is still a fitted thermostat."""
        assert self._room_thermostat_active(99) == [True, True, True]

    def test_room_thermostat_entities_not_created_without_p0033(self):
        """A controller that never returns P0033 cannot report a thermostat,
        so the gate falls closed - the #738 rule every declared gate follows.
        """
        assert self._room_thermostat_active(None) == [False, False, False]

    # endregion Room thermostat
    # region Mixing-circuit cooling targets

    @staticmethod
    def _mk1_cooling_active(mk1_type: Any) -> bool:
        coord = _make_coordinator(
            parameters={
                "ID_Einst_MK1Typ_akt": mk1_type,
                "ID_Sollwert_KuCft1_akt": 20.0,
            },
        )
        return coord.entity_active(_number(SensorKey.COOLING_TARGET_TEMPERATURE_MK1))

    def test_mixing_circuit_cooling(self):
        assert self._mk1_cooling_active(3) is True

    def test_mixing_circuit_heating_cooling(self):
        assert self._mk1_cooling_active(4) is True

    def test_mixing_circuit_not_cooling(self):
        assert self._mk1_cooling_active(0) is False
        assert self._mk1_cooling_active(2) is False

    def test_mixing_circuit_cooling_as_a_decoded_name(self):
        """The type register may gain a datatype and decode to a name. A
        formula that only knew the codes would quietly evaluate False and take
        the cooling targets away from every affected user, with nothing in
        the log - worse than the crash of #773.
        """
        assert self._mk1_cooling_active("cooling") is True
        assert self._mk1_cooling_active("heating_cooling") is True

    def test_every_mixing_circuit_declares_its_own_type(self):
        for key, type_register in (
            (SensorKey.COOLING_TARGET_TEMPERATURE_MK1, LP.P0042_MIXING_CIRCUIT1_TYPE),
            (SensorKey.COOLING_TARGET_TEMPERATURE_MK2, LP.P0130_MIXING_CIRCUIT2_TYPE),
            (SensorKey.COOLING_TARGET_TEMPERATURE_MK3, LP.P0780_MIXING_CIRCUIT3_TYPE),
        ):
            assert _number(key).entity_active_key == type_register, key

    # endregion Mixing-circuit cooling targets
    # region Smart Grid offsets - P1030

    SMART_GRID_OFFSETS = (
        SensorKey.SMART_GRID_HEATING_REDUCTION,
        SensorKey.SMART_GRID_HEATING_INCREASE,
        SensorKey.SMART_GRID_DHW_INCREASE,
    )

    @staticmethod
    def _smart_grid_coord(
        smart_grid: Any = None, *, offsets: bool = True, dhw: bool = True
    ) -> LuxtronikCoordinator:
        parameters: dict[str, Any] = {}
        if smart_grid is not None:
            parameters["ID_Einst_SmartGrid"] = smart_grid
        if offsets:
            parameters |= {
                "SMART_GRID_HEATING_REDUCTION": -2.0,
                "SMART_GRID_HEATING_INCREASE": 2.0,
                "SMART_GRID_DHW_INCREASE": 2.0,
            }
        return _make_coordinator(
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Zaehler_BetrZeitHz": 100,
                "ID_WEB_Zaehler_BetrZeitBW": 100 if dhw else 0,
            },
            parameters=parameters,
        )

    def _smart_grid_active(self, coord: LuxtronikCoordinator) -> list[bool]:
        return [coord.entity_active(_number(key)) for key in self.SMART_GRID_OFFSETS]

    def test_smart_grid_offsets_not_created_when_switched_off(self):
        """P1030 off means the Smart Grid submenu does not exist on the
        controller either (#765). 25 of the 29 pumps in the corpus are here.
        The SmartGridMode datatype decodes it, so off reads "off".
        """
        coord = self._smart_grid_coord("off")
        assert self._smart_grid_active(coord) == [False, False, False]

    def test_smart_grid_offsets_created_when_switched_on(self):
        for mode in ("plus_minus", "sg_1_0", "sg_1_1"):
            coord = self._smart_grid_coord(mode)
            assert self._smart_grid_active(coord) == [True, True, True], mode

    def test_smart_grid_offsets_created_for_an_unknown_mode(self):
        """An undocumented code passes the SmartGridMode datatype through as
        an int. smart_grid_enabled counts that as on, and so must the gate.
        """
        coord = self._smart_grid_coord(5)
        assert self._smart_grid_active(coord) == [True, True, True]

    def test_smart_grid_offsets_not_created_when_p1030_is_absent(self):
        coord = self._smart_grid_coord(None)
        assert self._smart_grid_active(coord) == [False, False, False]

    def test_smart_grid_offsets_need_their_own_register(self):
        """The controller in diagnostics/200927_014f returns P1030 but stops
        its parameter block before 1120. With Smart Grid on it would get three
        permanently unknown, unwritable entities - the failure #738 fixed.
        """
        coord = self._smart_grid_coord("plus_minus", offsets=False)
        assert self._smart_grid_active(coord) == [False, False, False]

    def test_smart_grid_dhw_offset_needs_a_dhw_circuit(self):
        """The declared gate must not overrule the device gate."""
        coord = self._smart_grid_coord("plus_minus", dhw=False)
        assert self._smart_grid_active(coord) == [True, True, False]

    # endregion Smart Grid offsets

    def test_twin_counter_needs_its_own_register(self):
        """A twin whose parameter block ends before 1015 gets no entity."""
        coord = _make_coordinator(parameters={"ID_Einst_isTwin": True})
        assert (
            coord.entity_active(_sensor(SensorKey.HEAT_AMOUNT_HEATING_COMPRESSOR_2))
            is False
        )


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
    async def test_batch_does_not_inherit_entries_left_by_an_earlier_failure(self):
        """A batch owns the queue: whatever an earlier failed write left
        behind must not ride along on this one.

        `_write`'s own `finally` cannot cover every case - a `connect()`
        failure (the common one when the controller is rebooting) raises
        before `_write` is ever entered, so the previous batch's entries are
        still queued when this one starts.
        """
        coord = _make_coordinator_direct()

        queue: dict[Any, Any] = {"stale_param": 500}
        coord.client.parameters.queue = queue
        coord.client.parameters.set = lambda target, value: queue.__setitem__(
            target, value
        )
        written_batches: list[dict[Any, Any]] = []
        coord.client.write = lambda: written_batches.append(dict(queue))

        async def run(fn, *args):
            return fn(*args)

        coord.hass.async_add_executor_job = AsyncMock(side_effect=run)

        async def fake_refresh():
            coord.data = LuxtronikCoordinatorData(
                parameters={"p1": (0, "06:00")},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh

        await coord.async_write_many([("p1", "06:00")])

        assert written_batches == [{"p1": "06:00"}]

    @pytest.mark.asyncio
    async def test_concurrent_batches_do_not_clear_each_other(self):
        """An automation touching several entities fires several overlapping
        writes. Clearing the queue at the start of a batch must never discard
        a *different* batch's pending parameters - the clear, the queueing and
        the flush are one critical section under `self._lock`.
        """
        coord = _make_coordinator_direct()

        queue: dict[Any, Any] = {}
        coord.client.parameters.queue = queue
        coord.client.parameters.set = lambda target, value: queue.__setitem__(
            target, value
        )
        written_batches: list[dict[Any, Any]] = []
        coord.client.write = lambda: written_batches.append(dict(queue))

        async def run(fn, *args):
            # Yield control so the two batches genuinely interleave; without
            # the lock this is where one would clear the other's queue.
            await asyncio.sleep(0)
            return fn(*args)

        coord.hass.async_add_executor_job = AsyncMock(side_effect=run)

        async def fake_refresh():
            coord.data = LuxtronikCoordinatorData(
                parameters={"p1": (0, "06:00"), "p2": (0, "22:00")},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh

        await asyncio.gather(
            coord.async_write_many([("p1", "06:00")]),
            coord.async_write_many([("p2", "22:00")]),
        )

        # Each batch flushed exactly its own parameter, and neither was lost.
        assert sorted(written_batches, key=lambda batch: sorted(batch)) == [
            {"p1": "06:00"},
            {"p2": "22:00"},
        ]

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


class TestWriteConfirmRetry:
    """Some controllers (e.g. LWC407 / firmware V1.88.3, issue #729) do not
    reflect a freshly written parameter in their readable register block for
    a few hundred ms, so the first confirming read still returns the old
    value. The write itself succeeded, so confirmation must be retried before
    the mismatch is reported as a failure."""

    @pytest.mark.asyncio
    async def test_stale_first_readback_confirms_on_retry(self):
        """A controller that needs a moment to apply the write must not be
        reported as having rejected it."""
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()
        refreshes = 0

        async def fake_refresh():
            nonlocal refreshes
            refreshes += 1
            # First read-back is still the pre-write value; second has applied.
            value = "Holidays" if refreshes == 1 else "Automatic"
            coord.data = LuxtronikCoordinatorData(
                parameters={"ID_Einst_BA_Lueftung_akt": (0, value)},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh

        with patch(
            "custom_components.luxtronik2.coordinator.asyncio.sleep", new=AsyncMock()
        ):
            result = await coord.async_write("ID_Einst_BA_Lueftung_akt", "Automatic")

        assert result is not None
        assert refreshes == 2

    @pytest.mark.asyncio
    async def test_retry_delay_is_awaited_not_blocking(self):
        """The retry wait must yield to the event loop (await asyncio.sleep),
        never block it - this runs inside Home Assistant's loop."""
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()
        refreshes = 0

        async def fake_refresh():
            nonlocal refreshes
            refreshes += 1
            coord.data = LuxtronikCoordinatorData(
                parameters={"p1": (0, 40 if refreshes == 1 else 42)},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh
        sleep_mock = AsyncMock()

        with patch(
            "custom_components.luxtronik2.coordinator.asyncio.sleep", new=sleep_mock
        ):
            await coord.async_write("p1", 42)

        sleep_mock.assert_awaited_once_with(WRITE_CONFIRM_INITIAL_DELAY)

    @pytest.mark.asyncio
    async def test_immediate_confirmation_never_sleeps(self):
        """Controllers that apply the write instantly (~3ms measured) must pay
        no delay penalty: exactly one refresh, no wait."""
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()
        refreshes = 0

        async def fake_refresh():
            nonlocal refreshes
            refreshes += 1
            coord.data = LuxtronikCoordinatorData(
                parameters={"p1": (0, 42)},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh
        sleep_mock = AsyncMock()

        with patch(
            "custom_components.luxtronik2.coordinator.asyncio.sleep", new=sleep_mock
        ):
            await coord.async_write("p1", 42)

        assert refreshes == 1
        sleep_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retry_delays_back_off_and_stay_capped(self):
        """Each retry is a full read (~1900 values), so repeated probing is
        expensive: the delay doubles to stop hammering a value that is not
        converging, but stays capped so the final wait cannot overshoot the
        retry budget."""
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()

        async def fake_refresh():
            # Never converges, so every retry is used.
            coord.data = LuxtronikCoordinatorData(
                parameters={"p1": (0, 40)},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh
        sleep_mock = AsyncMock()

        with (
            patch(
                "custom_components.luxtronik2.coordinator.asyncio.sleep",
                new=sleep_mock,
            ),
            pytest.raises(HomeAssistantError),
        ):
            await coord.async_write("p1", 42)

        delays = [call.args[0] for call in sleep_mock.await_args_list]
        assert delays == [0.1, 0.2, 0.4, 0.8, 1.0]
        assert max(delays) == WRITE_CONFIRM_MAX_DELAY
        assert delays[0] == WRITE_CONFIRM_INITIAL_DELAY

    @pytest.mark.asyncio
    async def test_genuinely_rejected_write_still_raises_after_retries(self):
        """A clamped/rejected write never converges, so it must still surface
        as write_confirmation_mismatch once the retry budget is spent."""
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()
        refreshes = 0

        async def fake_refresh():
            nonlocal refreshes
            refreshes += 1
            # Device clamped the write and will never report 42.
            coord.data = LuxtronikCoordinatorData(
                parameters={"p1": (0, 40)},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh

        with (
            patch(
                "custom_components.luxtronik2.coordinator.asyncio.sleep",
                new=AsyncMock(),
            ),
            pytest.raises(HomeAssistantError) as exc_info,
        ):
            await coord.async_write("p1", 42)

        assert exc_info.value.translation_key == "write_confirmation_mismatch"
        assert refreshes == WRITE_CONFIRM_MAX_ATTEMPTS


class TestWriteFollowUpRefresh:
    """A confirmed write arms one delayed follow-up read.

    The controller applies the written value immediately, but any behaviour
    the value triggers (a DHW run starting after a setpoint change, say) takes
    the controller a few seconds to compute. Without a follow-up read, Home
    Assistant shows that reaction only on the next regular poll.
    """

    @staticmethod
    def _confirming_coordinator(parameter: str, value: Any):
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock()

        async def fake_refresh():
            coord.data = LuxtronikCoordinatorData(
                parameters={parameter: (0, value)}, calculations={}, visibilities={}
            )

        coord.async_refresh = fake_refresh
        coord.async_request_refresh = AsyncMock()
        return coord

    @pytest.mark.asyncio
    async def test_confirmed_write_schedules_follow_up_refresh(self):
        coord = self._confirming_coordinator("p1", 42)
        with patch(
            "custom_components.luxtronik2.coordinator.async_call_later"
        ) as call_later:
            await coord.async_write("p1", 42)

        call_later.assert_called_once()
        hass, delay, action = call_later.call_args.args
        assert hass is coord.hass
        assert delay == WRITE_FOLLOWUP_DELAY

        coord.async_request_refresh.assert_not_called()
        await action(None)
        coord.async_request_refresh.assert_awaited_once()
        assert coord._write_followup_unsub is None

    @pytest.mark.asyncio
    async def test_burst_of_writes_keeps_only_last_follow_up(self):
        coord = self._confirming_coordinator("p1", 42)
        first_unsub = MagicMock()
        second_unsub = MagicMock()
        with patch(
            "custom_components.luxtronik2.coordinator.async_call_later",
            side_effect=[first_unsub, second_unsub],
        ):
            await coord.async_write("p1", 42)
            await coord.async_write("p1", 42)

        first_unsub.assert_called_once()
        second_unsub.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_write_schedules_no_follow_up(self):
        coord = _make_coordinator_direct()
        coord.hass.async_add_executor_job = AsyncMock(
            side_effect=Exception("write fail")
        )
        with (
            patch(
                "custom_components.luxtronik2.coordinator.async_call_later"
            ) as call_later,
            pytest.raises(LuxtronikWriteError),
        ):
            await coord.async_write("p1", 1)

        call_later.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_write_cancels_stale_follow_up_before_writing(self):
        """The pending timer goes before the next write starts, not after it
        confirms - so a follow-up armed by write A cannot fire in the middle
        of write B's (possibly seconds-long) confirmation loop."""
        coord = self._confirming_coordinator("p1", 42)
        stale_unsub = MagicMock()
        with patch(
            "custom_components.luxtronik2.coordinator.async_call_later",
            return_value=stale_unsub,
        ):
            await coord.async_write("p1", 42)

        coord.hass.async_add_executor_job = AsyncMock(
            side_effect=Exception("write fail")
        )
        with (
            patch("custom_components.luxtronik2.coordinator.async_call_later"),
            pytest.raises(LuxtronikWriteError),
        ):
            await coord.async_write("p1", 43)

        stale_unsub.assert_called_once()
        assert coord._write_followup_unsub is None

    @pytest.mark.asyncio
    async def test_shutdown_cancels_pending_follow_up(self):
        coord = self._confirming_coordinator("p1", 42)
        unsub = MagicMock()
        with patch(
            "custom_components.luxtronik2.coordinator.async_call_later",
            return_value=unsub,
        ):
            await coord.async_write("p1", 42)

        with patch.object(
            LuxtronikCoordinator.__bases__[0], "async_shutdown", new_callable=AsyncMock
        ):
            await coord.async_shutdown()

        unsub.assert_called_once()


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

    def test_detect_cooling_present_from_a_decoded_name(self):
        """Same register, bigger blast radius: this one gates has_cooling,
        so a silently False comparison removes the whole cooling device.
        """
        coord = _make_coordinator(
            parameters={"ID_Einst_MK1Typ_akt": LuxMkTypes.heating_cooling.name},
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

    def test_build_device_info_sets_translation_key(self):
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
        device_info = coord._build_device_info(DeviceKey.heatpump, "192.168.1.1")
        assert device_info["translation_key"] == DeviceKey.heatpump.value
        assert device_info["name"] == DeviceKey.heatpump.value


class TestDeviceInfoSerialNumber:
    """The serial number decides device identity, so it must be discoverable."""

    @staticmethod
    def _coordinator():
        return _make_coordinator(
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Code_WP_akt": "LWP 10",
            },
            parameters={
                "ID_WP_SerienNummer_DATUM": 230924,
                "ID_WP_SerienNummer_HEX": 625,
            },
        )

    def test_heatpump_device_exposes_serial_number(self):
        """The physical unit carries the serial in its device info."""
        coord = self._coordinator()

        device_info = coord._build_device_info(DeviceKey.heatpump, "192.168.1.1")

        assert device_info["serial_number"] == "230924_0271"

    def test_serial_number_matches_unique_id_rendering(self):
        """Device page and the duplicate-serial abort message must agree.

        `config_flow` reports collisions using the `unique_id` form, so a user
        comparing that message against the device page has to see the same
        string.
        """
        coord = self._coordinator()

        device_info = coord._build_device_info(DeviceKey.heatpump, "192.168.1.1")

        assert device_info["serial_number"] == coord.unique_id

    @pytest.mark.parametrize(
        "key",
        [DeviceKey.heating, DeviceKey.domestic_water, DeviceKey.cooling],
    )
    def test_logical_subdevices_omit_serial_number(self, key: DeviceKey):
        """Only the physical unit owns the serial.

        Heating/DHW/cooling are logical sub-devices of the same heat pump;
        repeating the serial on each would read as several distinct units
        sharing one serial - the exact confusion reported in #724.
        """
        coord = self._coordinator()

        device_info = coord._build_device_info(
            key, "192.168.1.1", (DOMAIN, "some_heatpump")
        )

        assert "serial_number" not in device_info


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


# ===========================================================================
# DHW transition hold (issue #519)
# ===========================================================================


class TestDhwTransitionHold:
    """Cross-poll lifecycle of the DHW transition hold (issue #519)."""

    def _coord(self) -> LuxtronikCoordinator:
        return _make_coordinator()

    def _data(self, status: str, recirculation: bool) -> LuxtronikCoordinatorData:
        return make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": status,
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.no_request,
                "ID_WEB_BUPout": recirculation,
                "ID_WEB_ZW1out": False,
            }
        )

    def test_dhw_poll_arms_the_hold_but_does_not_flag_it(self):
        """While DHW is genuinely reported there is nothing to hold."""
        coord = self._coord()
        data = self._data(LuxOperationMode.domestic_water, recirculation=True)
        coord._update_dhw_transition_hold(data)
        assert data.dhw_transition_hold is False
        assert coord._dhw_hold_until is not None

    def test_next_poll_holds_when_pump_still_running(self, freezer):
        """The transition poll right after DHW must be flagged as held."""
        coord = self._coord()
        freezer.move_to("2026-08-08 12:00:00+00:00")
        coord._update_dhw_transition_hold(
            self._data(LuxOperationMode.domestic_water, recirculation=True)
        )
        freezer.move_to("2026-08-08 12:01:00+00:00")
        data = self._data(LuxOperationMode.no_request, recirculation=True)
        coord._update_dhw_transition_hold(data)
        assert data.dhw_transition_hold is True

    def test_no_hold_when_pump_stopped(self, freezer):
        """Pump off means the DHW cycle really ended - report no_request."""
        coord = self._coord()
        freezer.move_to("2026-08-08 12:00:00+00:00")
        coord._update_dhw_transition_hold(
            self._data(LuxOperationMode.domestic_water, recirculation=True)
        )
        freezer.move_to("2026-08-08 12:01:00+00:00")
        data = self._data(LuxOperationMode.no_request, recirculation=False)
        coord._update_dhw_transition_hold(data)
        assert data.dhw_transition_hold is False
        assert coord._dhw_hold_until is None

    def test_hold_expires_after_the_configured_window(self, freezer):
        """A permanently running recirculation pump must not latch DHW forever."""
        coord = self._coord()
        freezer.move_to("2026-08-08 12:00:00+00:00")
        coord._update_dhw_transition_hold(
            self._data(LuxOperationMode.domestic_water, recirculation=True)
        )
        freezer.move_to("2026-08-08 12:06:00+00:00")  # > DHW_TRANSITION_HOLD
        data = self._data(LuxOperationMode.no_request, recirculation=True)
        coord._update_dhw_transition_hold(data)
        assert data.dhw_transition_hold is False
        assert coord._dhw_hold_until is None

    def test_hold_does_not_start_from_pump_alone(self):
        """Without a preceding genuine DHW state the pump alone proves nothing."""
        coord = self._coord()
        data = self._data(LuxOperationMode.no_request, recirculation=True)
        coord._update_dhw_transition_hold(data)
        assert data.dhw_transition_hold is False

    def test_hold_does_not_extend_itself(self, freezer):
        """The deadline is anchored to the last genuine DHW poll, not refreshed."""
        coord = self._coord()
        freezer.move_to("2026-08-08 12:00:00+00:00")
        coord._update_dhw_transition_hold(
            self._data(LuxOperationMode.domestic_water, recirculation=True)
        )
        deadline = coord._dhw_hold_until
        freezer.move_to("2026-08-08 12:02:00+00:00")
        coord._update_dhw_transition_hold(
            self._data(LuxOperationMode.no_request, recirculation=True)
        )
        assert coord._dhw_hold_until == deadline


class TestCoordinatorSubDeviceParenting:
    """The four logical sub-devices hang off the physical heat pump device."""

    @staticmethod
    def _coordinator_with_entry(hass) -> tuple[LuxtronikCoordinator, ConfigEntry]:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT},
        )
        entry.add_to_hass(hass)
        coord = _make_coordinator(
            hass=hass,
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Code_WP_akt": "LWP 10",
            },
            parameters={
                "ID_WP_SerienNummer_DATUM": 20230101,
                "ID_WP_SerienNummer_HEX": 255,
            },
        )
        coord.config_entry = entry
        return coord, entry

    async def test_sub_device_links_to_the_heatpump_by_registry_id(
        self, hass: HomeAssistant
    ) -> None:
        """`via_device_id` carries the heat pump's registry id."""
        coord, entry = self._coordinator_with_entry(hass)

        heating = coord.get_device(DeviceKey.heating)

        heatpump = dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, f"{coord.unique_id}_{DeviceKey.heatpump}".lower()),
            entry.entry_id,
        )
        assert heatpump is not None
        assert heating["via_device_id"] == heatpump.id

    async def test_sub_device_does_not_use_the_deprecated_via_device(
        self, hass: HomeAssistant
    ) -> None:
        """The identifier-tuple form was removed from `DeviceInfo` in HA 2026.9."""
        coord, _entry = self._coordinator_with_entry(hass)

        for key in (
            DeviceKey.heating,
            DeviceKey.domestic_water,
            DeviceKey.cooling,
            DeviceKey.ventilation,
        ):
            assert "via_device" not in coord.get_device(key)

    async def test_the_heatpump_itself_is_not_parented(
        self, hass: HomeAssistant
    ) -> None:
        """The physical unit is the root; it carries the serial instead."""
        coord, _entry = self._coordinator_with_entry(hass)

        heatpump = coord.get_device(DeviceKey.heatpump)

        assert "via_device_id" not in heatpump
        assert heatpump["serial_number"] == coord.unique_id

    async def test_an_existing_heatpump_device_is_adopted_not_duplicated(
        self, hass: HomeAssistant
    ) -> None:
        """Upgrades keep the device users already have.

        Before this migration the heat pump device was created by
        `entity_platform` from the identifier tuple. Registering it explicitly
        has to find that same device, not add a second one beside it.
        """
        coord, entry = self._coordinator_with_entry(hass)
        registry = dr.async_get(hass)
        existing = registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{coord.unique_id}_{DeviceKey.heatpump}".lower())},
        )

        heating = coord.get_device(DeviceKey.heating)

        assert heating["via_device_id"] == existing.id
        assert len(dr.async_entries_for_config_entry(registry, entry.entry_id)) == 1

    async def test_sub_devices_survive_without_a_config_entry(
        self, hass: HomeAssistant
    ) -> None:
        """`config_flow` builds entry-less coordinators; that must not raise."""
        coord = _make_coordinator(
            hass=hass,
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Code_WP_akt": "LWP 10",
            },
            parameters={
                "ID_WP_SerienNummer_DATUM": 20230101,
                "ID_WP_SerienNummer_HEX": 255,
            },
        )
        assert coord.config_entry is None

        heating = coord.get_device(DeviceKey.heating)

        assert "via_device_id" not in heating
        assert "serial_number" not in heating


class TestDetectTime2400Support:
    """Latching whether the controller stores "24:00" as a schedule end time.

    See `_detect_time_24_00_support` and issue #787: most controllers cap at
    "23:59", a few accept "24:00" and store 86400. Only the controller can
    put that value in a register, so observing it is the proof.
    """

    @staticmethod
    def _data(**times: str) -> LuxtronikCoordinatorData:
        """Coordinator data whose schedule registers are real TimeOfDay sensors."""
        data = make_coordinator_data()
        sensors = {}
        for name, value in times.items():
            sensor = TimeOfDay(name)
            sensor.value = value
            sensors[name] = sensor
        data.parameters._data = sensors
        return data

    @staticmethod
    def _coordinator(hass, entry_data: dict[str, Any] | None = None):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: DEFAULT_PORT,
                **(entry_data or {}),
            },
        )
        entry.add_to_hass(hass)
        coord = _make_coordinator(hass=hass)
        coord.config_entry = entry
        return coord, entry

    async def test_latches_when_a_schedule_register_holds_24_00(
        self, hass: HomeAssistant
    ) -> None:
        coord, entry = self._coordinator(hass)

        coord._detect_time_24_00_support(
            self._data(ID_Einst_BwWO_zeit_0_0="14:00", ID_Einst_BwWO_zeit_0_1="24:00")
        )
        await hass.async_block_till_done()

        assert entry.data[CONF_SUPPORTS_TIME_24_00] is True

    async def test_does_not_latch_without_a_24_00_anywhere(
        self, hass: HomeAssistant
    ) -> None:
        coord, entry = self._coordinator(hass)

        coord._detect_time_24_00_support(
            self._data(ID_Einst_BwWO_zeit_0_0="14:00", ID_Einst_BwWO_zeit_0_1="23:59")
        )
        await hass.async_block_till_done()

        assert CONF_SUPPORTS_TIME_24_00 not in entry.data

    async def test_ignores_a_non_schedule_sensor_holding_the_string(
        self, hass: HomeAssistant
    ) -> None:
        """Only TimeOfDay registers count - a stray string is not evidence."""
        coord, entry = self._coordinator(hass)
        data = make_coordinator_data(parameters={"ID_Something_Else": "24:00"})

        coord._detect_time_24_00_support(data)
        await hass.async_block_till_done()

        assert CONF_SUPPORTS_TIME_24_00 not in entry.data

    async def test_does_not_update_the_entry_again_once_latched(
        self, hass: HomeAssistant
    ) -> None:
        """The entry update reloads the entry, so it must happen exactly once."""
        coord, _entry = self._coordinator(hass, {CONF_SUPPORTS_TIME_24_00: True})

        with patch.object(hass.config_entries, "async_update_entry") as update_entry:
            coord._detect_time_24_00_support(self._data(ID_Einst_BwWO_zeit_0_1="24:00"))

        update_entry.assert_not_called()

    async def test_latches_from_a_poll(self, hass: HomeAssistant) -> None:
        """The detection has to be wired into `_async_update_data` itself."""
        coord, entry = self._coordinator(hass)
        data = self._data(
            ID_Einst_BwWO_zeit_0_0="14:00", ID_Einst_BwWO_zeit_0_1="24:00"
        )
        coord.client.parameters = data.parameters
        coord.client.calculations = data.calculations
        coord.client.visibilities = data.visibilities

        await coord._async_update_data()
        await hass.async_block_till_done()

        assert entry.data[CONF_SUPPORTS_TIME_24_00] is True

    async def test_is_a_no_op_without_a_config_entry(self) -> None:
        """Diagnostics and tests build coordinators with no entry attached."""
        coord = _make_coordinator()
        coord.config_entry = None

        coord._detect_time_24_00_support(self._data(ID_Einst_BwWO_zeit_0_1="24:00"))


# ===========================================================================
# Manual EVU2 input (#500)
# ===========================================================================


class TestEvu2Manual:
    """The user-supplied SG2 state on units where no register reports it."""

    def _coord(self, model: str = "MSW2-9S") -> LuxtronikCoordinator:
        coord = _make_coordinator(
            parameters={"ID_Einst_SmartGrid": "plus_minus"},
            calculations={"ID_WEB_Code_WP_akt": model},
        )
        coord.async_update_listeners = MagicMock()
        return coord

    def _poll(
        self,
        coord: LuxtronikCoordinator,
        model: str = "MSW2-9S",
        smart_grid: str = "plus_minus",
    ):
        data = make_coordinator_data(
            parameters={"ID_Einst_SmartGrid": smart_grid},
            calculations={"ID_WEB_Code_WP_akt": model},
        )
        coord._apply_evu2_manual(data)
        return data

    def test_is_none_with_smart_grid_off(self):
        """The switch does not exist then, so its value must not steer anything."""
        coord = self._coord()
        coord.set_evu2_manual(True)
        assert self._poll(coord, smart_grid="off").evu2_manual is None

    def test_setting_is_readable_whether_applied_or_not(self):
        """The switch shows this, so it must not vanish while SG is off."""
        coord = self._coord()
        coord.set_evu2_manual(True)
        self._poll(coord, smart_grid="off")
        assert coord.evu2_manual is True

    def test_value_survives_smart_grid_off_and_on(self):
        """Turning SG off and on again within a session keeps the setting."""
        coord = self._coord()
        coord.set_evu2_manual(True)
        self._poll(coord, smart_grid="off")
        assert self._poll(coord).evu2_manual is True

    def test_defaults_to_off_on_a_listed_model(self):
        """Off is what calc 185 reads there today, so nothing moves on upgrade."""
        coord = self._coord()
        assert self._poll(coord).evu2_manual is False

    def test_is_none_on_other_models(self):
        """None tells the resolver to keep reading calc 185."""
        coord = self._coord("MSW4-16")
        coord.set_evu2_manual(True)
        assert self._poll(coord, "MSW4-16").evu2_manual is None

    def test_value_carries_into_every_later_poll(self):
        """Each poll builds fresh data, so the value must live on the coordinator."""
        coord = self._coord()
        coord.set_evu2_manual(True)
        assert self._poll(coord).evu2_manual is True
        assert self._poll(coord).evu2_manual is True

    def test_set_applies_to_current_data_and_notifies(self):
        """The status sensor must follow a toggle now, not at the next poll."""
        coord = self._coord()
        coord._apply_evu2_manual(coord.data)

        coord.set_evu2_manual(True)

        assert coord.data.evu2_manual is True
        coord.async_update_listeners.assert_called_once()

    def test_set_on_other_models_leaves_data_alone(self):
        coord = self._coord("MSW4-16")
        coord.set_evu2_manual(True)
        assert coord.data.evu2_manual is None

    @pytest.mark.asyncio
    async def test_wired_into_async_update_data(self):
        coord = self._coord()
        coord.set_evu2_manual(True)

        data = await coord._async_update_data()

        assert data.evu2_manual is True


class TestEvu2ManualRestore:
    """The manual SG2 value is loaded before any platform computes a state.

    Restoring it in the switch is too late: platforms set up concurrently, so
    the SmartGrid status sensor could publish a state computed from the default
    and flip once the switch arrived - a spurious change on every restart.

    Every test seeds the data the way setup does - the first refresh has run,
    and applied the default, before the restore - and asserts on the data the
    entities read, not on the coordinator's private copy.
    """

    def _coord(self, hass: HomeAssistant, model: str = "MSW2-9S"):
        from custom_components.luxtronik2.const import CONF_HA_SENSOR_PREFIX

        coord = _make_coordinator(
            hass=hass,
            parameters={"ID_Einst_SmartGrid": "plus_minus"},
            calculations={"ID_WEB_Code_WP_akt": model},
        )
        coord._config = {**coord._config, CONF_HA_SENSOR_PREFIX: DOMAIN}
        coord._apply_evu2_manual(coord.data)
        return coord

    def _register(
        self, hass: HomeAssistant, state: str, object_id: str, disabled_by=None
    ):
        from homeassistant.core import State
        from homeassistant.helpers import entity_registry as er
        from pytest_homeassistant_custom_component.common import mock_restore_cache

        entity = er.async_get(hass).async_get_or_create(
            "switch",
            DOMAIN,
            f"switch.{DOMAIN}_{SensorKey.EVU2_MANUAL}",
            suggested_object_id=object_id,
            disabled_by=disabled_by,
        )
        mock_restore_cache(hass, [State(entity.entity_id, state)])

    @pytest.mark.parametrize(("state", "expected"), [("on", True), ("off", False)])
    async def test_restores_last_state(
        self, hass: HomeAssistant, state: str, expected: bool
    ) -> None:
        self._register(hass, state, f"{DOMAIN}_{SensorKey.EVU2_MANUAL}")
        coord = self._coord(hass)

        coord.async_restore_evu2_manual()

        assert coord.data.evu2_manual is expected
        assert coord._evu2_manual is expected

    async def test_restored_value_reaches_the_resolver(
        self, hass: HomeAssistant
    ) -> None:
        """What the SmartGrid status sensor computes its first state from."""
        from custom_components.luxtronik2.common import read_smart_grid_inputs

        self._register(hass, "on", f"{DOMAIN}_{SensorKey.EVU2_MANUAL}")
        coord = self._coord(hass)

        coord.async_restore_evu2_manual()

        assert read_smart_grid_inputs(coord.data)[1] is True

    async def test_follows_a_renamed_entity_id(self, hass: HomeAssistant) -> None:
        """Users rename entity ids; the unique id is what stays put."""
        self._register(hass, "on", "sg2_contact")
        coord = self._coord(hass)

        coord.async_restore_evu2_manual()

        assert coord.data.evu2_manual is True

    async def test_disabled_switch_is_not_restored(self, hass: HomeAssistant) -> None:
        """A disabled switch means open, not its last value.

        Otherwise it would keep steering the status with no visible entity to
        change it, until the restore cache expired it and the status changed
        again on its own.
        """
        from homeassistant.helpers import entity_registry as er

        self._register(
            hass,
            "on",
            f"{DOMAIN}_{SensorKey.EVU2_MANUAL}",
            disabled_by=er.RegistryEntryDisabler.USER,
        )
        coord = self._coord(hass)

        coord.async_restore_evu2_manual()

        assert coord.data.evu2_manual is False

    @pytest.mark.parametrize("state", ["unavailable", "unknown"])
    async def test_ignores_states_without_a_value(
        self, hass: HomeAssistant, state: str
    ) -> None:
        self._register(hass, state, f"{DOMAIN}_{SensorKey.EVU2_MANUAL}")
        coord = self._coord(hass)

        coord.async_restore_evu2_manual()

        assert coord.data.evu2_manual is False

    async def test_first_setup_has_nothing_to_restore(
        self, hass: HomeAssistant
    ) -> None:
        coord = self._coord(hass)
        coord.async_restore_evu2_manual()
        assert coord.data.evu2_manual is False

    async def test_other_models_are_left_alone(self, hass: HomeAssistant) -> None:
        self._register(hass, "on", f"{DOMAIN}_{SensorKey.EVU2_MANUAL}")
        coord = self._coord(hass, "MSW4-16")

        coord.async_restore_evu2_manual()

        assert coord.data.evu2_manual is None

    async def test_without_a_prefix_nothing_is_looked_up(
        self, hass: HomeAssistant
    ) -> None:
        """Entry-less coordinators (config flow) carry no entity prefix."""
        self._register(hass, "on", f"{DOMAIN}_{SensorKey.EVU2_MANUAL}")
        coord = _make_coordinator(
            hass=hass,
            parameters={"ID_Einst_SmartGrid": "plus_minus"},
            calculations={"ID_WEB_Code_WP_akt": "MSW2-9S"},
        )
        coord._apply_evu2_manual(coord.data)

        coord.async_restore_evu2_manual()

        assert coord.data.evu2_manual is False

    async def test_smart_grid_off_at_startup_still_loads_the_setting(
        self, hass: HomeAssistant
    ) -> None:
        """Turning SG on with the select must apply the setting, not the default.

        No reload follows that select change, so the value has to be loaded at
        startup even while SG is off; whether it is applied stays the per-poll
        decision.
        """
        self._register(hass, "on", f"{DOMAIN}_{SensorKey.EVU2_MANUAL}")
        coord = self._coord(hass)
        sg_off = make_coordinator_data(
            parameters={"ID_Einst_SmartGrid": "off"},
            calculations={"ID_WEB_Code_WP_akt": "MSW2-9S"},
        )
        coord.data = sg_off
        coord._apply_evu2_manual(sg_off)

        coord.async_restore_evu2_manual()
        assert coord.data.evu2_manual is None

        sg_on = make_coordinator_data(
            parameters={"ID_Einst_SmartGrid": "plus_minus"},
            calculations={"ID_WEB_Code_WP_akt": "MSW2-9S"},
        )
        coord._apply_evu2_manual(sg_on)
        assert sg_on.evu2_manual is True

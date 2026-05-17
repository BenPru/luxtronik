"""Tests for custom_components.luxtronik2.const."""

from __future__ import annotations

from custom_components.luxtronik2.const import (
    CONFIG_ENTRY_VERSION,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PLATFORMS,
    DeviceKey,
    LuxCalculation,
    LuxMkTypes,
    LuxMode,
    LuxOperationMode,
    LuxParameter,
    LuxSmartGridStatus,
    LuxStatus1Option,
    LuxStatus3Option,
    LuxVisibility,
    SensorKey,
)


class TestConstants:
    def test_domain(self):
        assert DOMAIN == "luxtronik2"

    def test_config_version(self):
        assert CONFIG_ENTRY_VERSION == 9

    def test_default_port(self):
        assert DEFAULT_PORT == 8889

    def test_default_timeout(self):
        assert isinstance(DEFAULT_TIMEOUT, float)

    def test_default_max_data_length(self):
        assert isinstance(DEFAULT_MAX_DATA_LENGTH, int)

    def test_platforms_not_empty(self):
        assert len(PLATFORMS) > 0


class TestDeviceKey:
    def test_heatpump(self):
        assert DeviceKey.heatpump == "heatpump"

    def test_heating(self):
        assert DeviceKey.heating == "heating"

    def test_domestic_water(self):
        assert DeviceKey.domestic_water == "domestic_water"

    def test_cooling(self):
        assert DeviceKey.cooling == "cooling"


class TestLuxOperationMode:
    def test_heating(self):
        assert LuxOperationMode.heating == "heating"

    def test_domestic_water(self):
        assert LuxOperationMode.domestic_water == "hot_water"

    def test_evu(self):
        assert LuxOperationMode.evu == "evu"

    def test_no_request(self):
        assert LuxOperationMode.no_request == "no_request"

    def test_cooling(self):
        assert LuxOperationMode.cooling == "cooling"

    def test_defrost(self):
        assert LuxOperationMode.defrost == "defrost"


class TestLuxMode:
    def test_off(self):
        assert LuxMode.off == "Off"

    def test_automatic(self):
        assert LuxMode.automatic == "Automatic"

    def test_party(self):
        assert LuxMode.party == "Party"

    def test_holidays(self):
        assert LuxMode.holidays == "Holidays"


class TestLuxSmartGridStatus:
    def test_locked(self):
        assert LuxSmartGridStatus.locked == "evu_locked"

    def test_normal(self):
        assert LuxSmartGridStatus.normal == "normal_operation"

    def test_increased(self):
        assert LuxSmartGridStatus.increased == "increased_operation"

    def test_reduced(self):
        assert LuxSmartGridStatus.reduced == "reduced_operation"


class TestLuxStatus1Option:
    def test_heatpump_running(self):
        assert LuxStatus1Option.heatpump_running == "heatpump_running"

    def test_heatpump_shutdown(self):
        assert LuxStatus1Option.heatpump_shutdown == "heatpump_shutdown"

    def test_compressor_heater(self):
        assert LuxStatus1Option.compressor_heater == "compressor_heater"


class TestLuxStatus3Option:
    def test_heating(self):
        assert LuxStatus3Option.heating == "heating"

    def test_cooling(self):
        assert LuxStatus3Option.cooling == "cooling"

    def test_domestic_water(self):
        assert LuxStatus3Option.domestic_water == "domestic_water"


class TestLuxMkTypes:
    def test_off(self):
        assert LuxMkTypes.off.value == 0

    def test_cooling(self):
        assert LuxMkTypes.cooling.value == 3

    def test_heating_cooling(self):
        assert LuxMkTypes.heating_cooling.value == 4


class TestLuxParameter:
    def test_unset(self):
        assert LuxParameter.UNSET is not None

    def test_mode_heating(self):
        assert "parameters" in LuxParameter.P0003_MODE_HEATING.value

    def test_mode_dhw(self):
        assert "parameters" in LuxParameter.P0004_MODE_DHW.value


class TestLuxCalculation:
    def test_unset(self):
        assert LuxCalculation.UNSET is not None

    def test_flow_in_temperature(self):
        assert "calculations" in LuxCalculation.C0010_FLOW_IN_TEMPERATURE.value

    def test_firmware_version(self):
        assert "calculations" in LuxCalculation.C0081_FIRMWARE_VERSION.value


class TestLuxVisibility:
    def test_unset(self):
        assert LuxVisibility.UNSET is not None

    def test_cooling(self):
        assert "visibilities" in LuxVisibility.V0005_COOLING.value


class TestSensorKey:
    def test_firmware(self):
        assert SensorKey.FIRMWARE is not None

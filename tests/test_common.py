"""Tests for custom_components.luxtronik2.common."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from conftest import make_coordinator_data
from custom_components.luxtronik2.common import (
    async_get_mac_address,
    convert_to_int_if_possible,
    get_sensor_data,
    key_exists,
    normalize_sensor_value,
    state_as_number_or_none,
)
from custom_components.luxtronik2.const import (
    LuxCalculation as LC,
    LuxOperationMode,
    LuxStatus1Option,
    LuxStatus3Option,
)

# ===========================================================================
# key_exists
# ===========================================================================


class TestKeyExists:
    def test_existing_parameter(self):
        data = make_coordinator_data(parameters={"ID_Ba_Hz_akt": "Automatic"})
        assert key_exists(data, "parameters.ID_Ba_Hz_akt") is True

    def test_existing_calculation(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TVL": 30.0})
        assert key_exists(data, "calculations.ID_WEB_Temperatur_TVL") is True

    def test_existing_visibility(self):
        data = make_coordinator_data(visibilities={"ID_Visi_Solar": 0})
        assert key_exists(data, "visibilities.ID_Visi_Solar") is True

    def test_missing_key(self):
        data = make_coordinator_data()
        assert key_exists(data, "parameters.nonexistent") is False

    def test_unset_key(self):
        data = make_coordinator_data()
        assert key_exists(data, LC.UNSET) is False

    def test_none_key(self):
        data = make_coordinator_data()
        assert key_exists(data, None) is False

    def test_empty_string_key(self):
        data = make_coordinator_data()
        assert key_exists(data, "") is False

    def test_key_without_dot(self):
        data = make_coordinator_data()
        assert key_exists(data, "nodot") is False

    def test_key_with_brace(self):
        data = make_coordinator_data()
        assert key_exists(data, "parameters.{something}") is False

    def test_unknown_group(self):
        data = make_coordinator_data()
        assert key_exists(data, "unknown_group.some_key") is False

    def test_key_exists_exception_returns_false(self):
        """When the underlying data object raises, key_exists catches and returns False."""
        data = MagicMock()
        data.parameters.parameters.items.side_effect = RuntimeError("boom")
        assert key_exists(data, "parameters.some_key") is False


@pytest.fixture
def tiny_upstream_range(monkeypatch):
    """Pretend upstream defines only index 0, so indices 1+ are 'override-added'.

    FakeSensorGroup indexes items by insertion order, so without this every test
    index would sit inside the real upstream range (0..1125) and never be
    eligible for the absence rule.
    """
    monkeypatch.setattr(
        "custom_components.luxtronik2.common.UPSTREAM_MAX_DEFINED_INDEX",
        {"parameters": 0, "calculations": 0, "visibilities": 0},
    )


class TestRegisterPresence:
    def test_absent_register_returns_false(self, tiny_upstream_range):
        """A definition exists, but the controller returned a shorter block."""
        data = make_coordinator_data(
            parameters={"upstream_a": 1, "added_b": 2, "added_c": None},
            parameters_parsed_count=2,
        )
        assert key_exists(data, "parameters.upstream_a") is True  # index 0
        assert key_exists(data, "parameters.added_b") is True  # index 1 < 2
        assert key_exists(data, "parameters.added_c") is False  # index 2 >= 2

    def test_present_register_reading_none_is_still_present(self, tiny_upstream_range):
        """A SelectionBase register with an unknown code reads None but exists."""
        data = make_coordinator_data(
            parameters={"upstream_a": 1, "unknown_code": None},
            parameters_parsed_count=2,
        )
        assert key_exists(data, "parameters.unknown_code") is True

    def test_upstream_range_is_never_suppressed(self):
        """Even a wildly short block cannot hide a register upstream defines.

        This is what keeps 1.x controllers, which may return fewer values than
        anything in the diagnostics corpus, on the pre-change behaviour.
        """
        data = make_coordinator_data(
            parameters={"a": 1, "b": 2, "c": 3},
            parameters_parsed_count=0,
        )
        assert key_exists(data, "parameters.c") is True

    def test_upstream_max_index_itself_is_inside_the_range(self, monkeypatch):
        """The confinement is ``index <= upstream_max``, not ``<``.

        The highest index upstream defines is upstream's own, so it must stay on
        the pre-change behaviour even when the block stops right before it. This
        is the only case that separates the two operators: everywhere else an
        index at the boundary also satisfies ``index < parsed_count``.
        """
        monkeypatch.setattr(
            "custom_components.luxtronik2.common.UPSTREAM_MAX_DEFINED_INDEX",
            {"parameters": 1, "calculations": 1, "visibilities": 1},
        )
        data = make_coordinator_data(
            parameters={"upstream_a": 1, "upstream_b": 2},
            parameters_parsed_count=1,
        )
        assert key_exists(data, "parameters.upstream_b") is True  # index 1 == max

    def test_without_recorded_count_falls_back_to_definition(self, tiny_upstream_range):
        """Objects built without a parse() (tests, diagnostics) keep old behaviour."""
        data = make_coordinator_data(parameters={"a": 1, "b": 2})
        assert key_exists(data, "parameters.b") is True

    def test_rule_is_generic_across_groups(self, tiny_upstream_range):
        """The check is not parameters-only, even though only parameters can
        currently trigger it (lux_overrides adds nothing above the calculations
        or visibilities range)."""
        data = make_coordinator_data(
            calculations={"upstream_a": 1, "added_b": 2},
            calculations_parsed_count=1,
        )
        assert key_exists(data, "calculations.upstream_a") is True
        assert key_exists(data, "calculations.added_b") is False


# ===========================================================================
# get_sensor_data
# ===========================================================================


class TestGetSensorData:
    def test_none_coordinator(self):
        assert get_sensor_data(None, "parameters.some_key") is None

    def test_unset_key(self):
        data = make_coordinator_data()
        assert get_sensor_data(data, LC.UNSET) is None

    def test_none_key(self):
        data = make_coordinator_data()
        assert get_sensor_data(data, None) is None

    def test_key_without_dot(self):
        data = make_coordinator_data()
        assert get_sensor_data(data, "nodot", warn_unset=False) is None

    def test_key_with_brace(self):
        data = make_coordinator_data()
        assert get_sensor_data(data, "parameters.{template}") is None

    def test_get_parameter_value(self):
        data = make_coordinator_data(parameters={"ID_Ba_Hz_akt": "Automatic"})
        assert get_sensor_data(data, "parameters.ID_Ba_Hz_akt") == "Automatic"

    def test_get_calculation_value_boolean(self):
        data = make_coordinator_data(calculations={"ID_WEB_SH_BWW": True})
        assert get_sensor_data(data, "calculations.ID_WEB_SH_BWW") is True

    def test_get_calculation_value(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TVL": 30.0})
        assert get_sensor_data(data, "calculations.ID_WEB_Temperatur_TVL") == 30.0

    def test_get_visibility_value(self):
        data = make_coordinator_data(visibilities={"ID_Visi_Solar": 0})
        assert get_sensor_data(data, "visibilities.ID_Visi_Solar") == 0

    def test_unknown_group_raises(self):
        data = make_coordinator_data()
        with pytest.raises(NotImplementedError):
            get_sensor_data(data, "unknown_group.some_key")

    def test_missing_sensor_returns_none(self):
        data = make_coordinator_data()
        assert get_sensor_data(data, "parameters.nonexistent") is None

    def test_raw_value_skips_correction(self):
        # C0080_STATUS would normally be corrected, but raw_value=True skips it
        data = make_coordinator_data(calculations={"ID_WEB_WP_BZ_akt": "heating"})
        result = get_sensor_data(data, LC.C0080_STATUS, raw_value=True)
        assert result == "heating"


# ===========================================================================
# normalize_sensor_value
# ===========================================================================


class TestNormalizeSensorValue:
    def test_none_value_passthrough(self):
        assert (
            normalize_sensor_value(None, make_coordinator_data(), LC.C0080_STATUS)
            is None
        )

    def test_none_coordinator_passthrough(self):
        assert normalize_sensor_value("heating", None, LC.C0080_STATUS) == "heating"

    def test_none_sensor_id_passthrough(self):
        assert (
            normalize_sensor_value("heating", make_coordinator_data(), None)
            == "heating"
        )

    def test_unrelated_sensor_passthrough(self):
        data = make_coordinator_data()
        assert normalize_sensor_value(42.0, data, "parameters.ID_Ba_Hz_akt") == 42.0

    def test_status_spaces_replaced(self):
        data = make_coordinator_data()
        result = normalize_sensor_value("some value", data, LC.C0080_STATUS)
        assert " " not in result
        assert result == "some_value"

    def test_status_slashes_replaced(self):
        data = make_coordinator_data()
        result = normalize_sensor_value("a/b", data, LC.C0117_STATUS_LINE_1)
        assert "/" not in result
        assert result == "a_b"

    def test_status_line_lowered(self):
        data = make_coordinator_data()
        result = normalize_sensor_value("HEATING", data, LC.C0119_STATUS_LINE_3)
        assert result == "heating"

    def test_error_reason_minus1_int(self):
        data = make_coordinator_data()
        result = normalize_sensor_value(-1, data, LC.C0100_ERROR_REASON)
        assert result == "minus_1"

    def test_error_reason_minus1_str(self):
        data = make_coordinator_data()
        result = normalize_sensor_value("-1", data, LC.C0100_ERROR_REASON)
        assert result == "minus_1"

    def test_error_reason_normal(self):
        data = make_coordinator_data()
        result = normalize_sensor_value(5, data, LC.C0100_ERROR_REASON)
        assert result == 5

    def test_status_line1_heatpump_coming_workaround(self):
        """If heatpump_coming but timer_scb_on < 10 and timer_scb_off > 0, returns heatpump_shutdown."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_Time_SSPEIN_akt": 5,
                "ID_WEB_Time_SSPAUS_akt": 100,
            }
        )
        result = normalize_sensor_value(
            LuxStatus1Option.heatpump_coming, data, LC.C0117_STATUS_LINE_1
        )
        assert result == LuxStatus1Option.heatpump_shutdown

    def test_status_line1_pump_forerun_compressor_heater_workaround(self):
        """If pump_forerun and compressor heater is active, returns compressor_heater."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_LIN_VDH_out": True,  # C0182_COMPRESSOR_HEATER
            }
        )
        result = normalize_sensor_value(
            LuxStatus1Option.pump_forerun, data, LC.C0117_STATUS_LINE_1
        )
        assert result == LuxStatus1Option.compressor_heater

    def test_status_no_request_passive_cooling(self):
        """If no_request + status_line3 shows cooling → returns cooling."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.cooling,
            }
        )
        result = normalize_sensor_value(
            LuxOperationMode.no_request, data, LC.C0080_STATUS
        )
        assert result == LuxOperationMode.cooling

    def test_status_no_request_active_cooling_detected(self):
        """If no_request + status_line3=heating but temps indicate cooling → returns cooling."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.heating,
                "ID_WEB_Temperatur_TVL": 20.0,  # C0010 flow in
                "ID_WEB_Temperatur_TRL": 25.0,  # C0011 flow out (> in)
                "ID_WEB_Temperatur_TWE": 10.0,  # C0204 heat source in
                "ID_WEB_Temperatur_TWA": 15.0,  # C0024 heat source out (> in)
                "ID_WEB_Durchfluss_WQ": 5.0,  # C0173 flow rate (> 0)
                "ID_WEB_VBOout": True,  # C0043 pump flow (True)
            }
        )
        result = normalize_sensor_value(
            LuxOperationMode.no_request, data, LC.C0080_STATUS
        )
        assert result == LuxOperationMode.cooling

    def test_status_no_request_not_active_cooling(self):
        """If no_request + status_line3=heating but temps don't indicate cooling → stays no_request."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.heating,
                "ID_WEB_Temperatur_TVL": 25.0,  # flow in > out → not cooling
                "ID_WEB_Temperatur_TRL": 20.0,
                "ID_WEB_Temperatur_TWE": 10.0,
                "ID_WEB_Temperatur_TWA": 15.0,
                "ID_WEB_Durchfluss_WQ": 5.0,
                "ID_WEB_VBOout": True,
            }
        )
        result = normalize_sensor_value(
            LuxOperationMode.no_request, data, LC.C0080_STATUS
        )
        assert result == LuxOperationMode.no_request

    def test_status_line3_thermal_desinfection_maps_to_domestic_water(self):
        """If status_line3 is thermal_desinfection, C0080_STATUS becomes domestic_water."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.thermal_desinfection,
            }
        )
        result = normalize_sensor_value(LuxOperationMode.heating, data, LC.C0080_STATUS)
        assert result == LuxOperationMode.domestic_water

    def test_pump_forerun_status_line1_with_no_request_line3_maps_to_no_request(self):
        """If pump forerun and no_request line3 while no add circ pump, C0080_STATUS becomes no_request."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_HauptMenuStatus_Zeile1": LuxStatus1Option.pump_forerun,
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.no_request,
                "ID_WEB_ZUPout": False,
            }
        )
        result = normalize_sensor_value(LuxOperationMode.heating, data, LC.C0080_STATUS)
        assert result == LuxOperationMode.no_request

    def test_thermal_desinfection_on_second_heat_source_maps_to_domestic_water(self):
        """If line3 is no_request/cycle_lock with AddHeat and recirculation, return domestic_water."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.no_request,
                "ID_WEB_BUPout": True,
                "ID_WEB_ZW1out": True,
            }
        )
        result = normalize_sensor_value(
            LuxOperationMode.no_request, data, LC.C0080_STATUS
        )
        assert result == LuxOperationMode.domestic_water

    def test_heating_without_compressor_and_additional_heat(self):
        """If heating mode but compressor & additional heat generator off → no_request."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_VD1out": False,  # C0044_COMPRESSOR -> False
                "ID_WEB_ZW1out": False,  # C0048_ADDITIONAL_HEAT_GENERATOR -> False
            }
        )
        result = normalize_sensor_value(LuxOperationMode.heating, data, LC.C0080_STATUS)
        assert result == LuxOperationMode.no_request

    def test_dhw_hold_converts_no_request_to_domestic_water(self):
        """During the DHW->TDI transition the status must stay domestic_water."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.no_request,
                "ID_WEB_BUPout": True,
                "ID_WEB_ZW1out": False,
            }
        )
        data.dhw_transition_hold = True
        result = normalize_sensor_value(
            LuxOperationMode.no_request, data, LC.C0080_STATUS
        )
        assert result == LuxOperationMode.domestic_water

    def test_no_dhw_hold_leaves_no_request_alone(self):
        """Without an active hold the existing no_request behaviour is unchanged."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.no_request,
                "ID_WEB_BUPout": True,
                "ID_WEB_ZW1out": False,
            }
        )
        result = normalize_sensor_value(
            LuxOperationMode.no_request, data, LC.C0080_STATUS
        )
        assert result == LuxOperationMode.no_request

    def test_dhw_hold_does_not_mask_cooling(self):
        """A hold must never override a mode the heat pump genuinely moved into."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.cooling,
            }
        )
        data.dhw_transition_hold = True
        result = normalize_sensor_value(
            LuxOperationMode.no_request, data, LC.C0080_STATUS
        )
        assert result == LuxOperationMode.cooling

    def test_dhw_hold_does_not_affect_other_sensors(self):
        """The hold is scoped to C0080_STATUS only."""
        data = make_coordinator_data(
            calculations={"ID_WEB_HauptMenuStatus_Zeile1": "Heatpump Idle"}
        )
        data.dhw_transition_hold = True
        result = normalize_sensor_value("Heatpump Idle", data, LC.C0117_STATUS_LINE_1)
        assert result == LuxStatus1Option.heatpump_idle


# ===========================================================================
# state_as_number_or_none
# ===========================================================================


class TestStateAsNumberOrNone:
    def test_none_state(self):
        assert state_as_number_or_none(None) is None

    def test_none_state_with_default(self):
        assert state_as_number_or_none(None, default=42.0) == 42.0

    def test_unavailable_state(self):
        state = MagicMock()
        state.state = "unavailable"
        assert state_as_number_or_none(state) is None

    def test_unavailable_state_with_default(self):
        state = MagicMock()
        state.state = "unavailable"
        assert state_as_number_or_none(state, default=10.0) == 10.0

    def test_numeric_state(self):
        state = MagicMock()
        state.state = "42.5"
        result = state_as_number_or_none(state)
        assert result == 42.5

    def test_non_numeric_garbage_state(self):
        state = MagicMock()
        state.state = "N/A"
        assert state_as_number_or_none(state) is None

    def test_non_numeric_garbage_state_with_default(self):
        state = MagicMock()
        state.state = "N/A"
        assert state_as_number_or_none(state, default=10.0) == 10.0


# ===========================================================================
# convert_to_int_if_possible
# ===========================================================================


class TestConvertToIntIfPossible:
    def test_int_string(self):
        assert convert_to_int_if_possible("42") == 42

    def test_negative_int_string(self):
        assert convert_to_int_if_possible("-5") == -5

    def test_non_numeric_string(self):
        assert convert_to_int_if_possible("hello") == "hello"

    def test_float_string(self):
        # float strings cannot be converted to int directly
        assert convert_to_int_if_possible("3.14") == "3.14"

    def test_empty_string(self):
        assert convert_to_int_if_possible("") == ""


# ===========================================================================
# async_get_mac_address
# ===========================================================================


class TestAsyncGetMacAddress:
    @pytest.mark.asyncio
    async def test_ipv4_address(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value="aa:bb:cc:dd:ee:ff")
        result = await async_get_mac_address(hass, "192.168.1.100")
        assert result == "aa:bb:cc:dd:ee:ff"

    @pytest.mark.asyncio
    async def test_ipv6_address(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value="aa:bb:cc:dd:ee:ff")
        result = await async_get_mac_address(hass, "::1")
        assert result == "aa:bb:cc:dd:ee:ff"

    @pytest.mark.asyncio
    async def test_hostname(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value="aa:bb:cc:dd:ee:ff")
        result = await async_get_mac_address(hass, "heatpump.local")
        assert result == "aa:bb:cc:dd:ee:ff"

    @pytest.mark.asyncio
    async def test_no_mac_returns_none(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)
        result = await async_get_mac_address(hass, "192.168.1.100")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_mac_returns_none(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value="")
        result = await async_get_mac_address(hass, "192.168.1.100")
        assert result is None

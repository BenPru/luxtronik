"""Tests for custom_components.luxtronik2.lux_overrides."""

from __future__ import annotations

from luxtronik.calculations import Calculations
from luxtronik.datatypes import (
    BivalenceLevel,
    Celsius,
    HeatpumpCode,
    SwitchoffFile,
    Unknown,
)
from luxtronik.parameters import Parameters
from luxtronik.visibilities import Visibilities
import pytest

from custom_components.luxtronik2 import lux_overrides
from custom_components.luxtronik2.common import key_exists
from custom_components.luxtronik2.const import (
    CONF_CALCULATIONS,
    CONF_PARAMETERS,
    CONF_VISIBILITIES,
    PARSED_COUNT_ATTR,
)
from custom_components.luxtronik2.model import LuxtronikCoordinatorData


class TestUpdateLuxtronikHeatpumpCodes:
    def test_codes_updated(self):
        from custom_components.luxtronik2.lux_overrides import (
            update_Luxtronik_HeatpumpCodes,
        )

        update_Luxtronik_HeatpumpCodes()
        assert 0 in HeatpumpCode.codes
        assert HeatpumpCode.codes[0] == "ERC"
        assert HeatpumpCode.codes[27] == "L1S"
        assert HeatpumpCode.codes[88] == "LP8V"
        assert len(HeatpumpCode.codes) == 89


class TestUpdateLuxtronikParameters:
    def test_parameters_updated(self):
        from custom_components.luxtronik2.lux_overrides import (
            update_Luxtronik_Parameters,
        )

        update_Luxtronik_Parameters()
        # Check that custom parameters are now in the class-level dict
        assert 1148 in Parameters.parameters
        assert Parameters.parameters[1148].name == "HEATING_TARGET_TEMP_ROOM_THERMOSTAT"

        assert 258 in Calculations.calculations
        assert Calculations.calculations[258].name == "RBE_Version"
        assert Calculations.calculations[258].from_heatpump(205) == "2.05"

    def test_parameters_to_add_update_keeps_explicit_names(self):
        from custom_components.luxtronik2.lux_overrides import (
            update_Luxtronik_Parameters,
        )

        Parameters.parameters[973] = Unknown("Existing_Name", True)

        update_Luxtronik_Parameters()

        updated = Parameters.parameters[973]
        assert isinstance(updated, Celsius)
        assert updated.name == "ID_Einst_BW_max"

    def test_bulk_class_updates_can_target_numeric_ranges(self):
        from custom_components.luxtronik2.lux_overrides import (
            update_Luxtronik_Parameter_Classes,
        )

        Parameters.parameters[973] = Unknown("ID_Einst_BW_max", True)
        Parameters.parameters[980] = Unknown("ID_RBE_Einflussfaktor_RT_akt", True)

        update_Luxtronik_Parameter_Classes(range(973, 981), Celsius)

        assert isinstance(Parameters.parameters[973], Celsius)
        assert Parameters.parameters[973].name == "ID_Einst_BW_max"
        assert isinstance(Parameters.parameters[980], Celsius)
        assert Parameters.parameters[980].name == "ID_RBE_Einflussfaktor_RT_akt"

    def test_bulk_class_updates_skip_unknown_numbers(self):
        """A number with no existing upstream entry is silently skipped, not created."""
        from custom_components.luxtronik2.lux_overrides import (
            update_Luxtronik_Parameter_Classes,
        )

        Parameters.parameters.pop(999999, None)
        Parameters.parameters[973] = Unknown("ID_Einst_BW_max", True)

        update_Luxtronik_Parameter_Classes([999999, 973], Celsius)

        assert 999999 not in Parameters.parameters
        assert isinstance(Parameters.parameters[973], Celsius)

    def test_bulk_class_updates_rejects_non_base_datatype(self):
        from custom_components.luxtronik2.lux_overrides import (
            update_Luxtronik_Parameter_Classes,
        )

        with pytest.raises(TypeError):
            update_Luxtronik_Parameter_Classes([973], str)


class TestIsolateInstanceData:
    def test_instance_data_isolated(self):
        """After isolate_instance_data(), each instance gets its own copy of data dicts."""
        # Reset the guard flag so we can test
        import custom_components.luxtronik2.lux_overrides as overrides_module
        from custom_components.luxtronik2.lux_overrides import isolate_instance_data

        original_flag = overrides_module._INSTANCE_DATA_ISOLATED
        overrides_module._INSTANCE_DATA_ISOLATED = False

        try:
            isolate_instance_data()

            p1 = Parameters()
            p2 = Parameters()
            # They should have separate dicts (not the same object)
            assert p1.parameters is not p2.parameters

            c1 = Calculations()
            c2 = Calculations()
            assert c1.calculations is not c2.calculations

            v1 = Visibilities()
            v2 = Visibilities()
            assert v1.visibilities is not v2.visibilities
        finally:
            overrides_module._INSTANCE_DATA_ISOLATED = original_flag

    def test_idempotent(self):
        """Calling isolate_instance_data() twice is safe."""
        import custom_components.luxtronik2.lux_overrides as overrides_module
        from custom_components.luxtronik2.lux_overrides import isolate_instance_data

        original_flag = overrides_module._INSTANCE_DATA_ISOLATED
        overrides_module._INSTANCE_DATA_ISOLATED = False

        try:
            isolate_instance_data()
            isolate_instance_data()  # second call should be no-op
            assert overrides_module._INSTANCE_DATA_ISOLATED is True
        finally:
            overrides_module._INSTANCE_DATA_ISOLATED = original_flag


class TestSecondsToHours:
    def test_from_heatpump_rounds_to_nearest_half_hour(self):
        from custom_components.luxtronik2.lux_overrides import SecondsToHours

        converter = SecondsToHours("Extra_DHW_duration", True)
        assert converter.from_heatpump(0) == 0.0
        assert converter.from_heatpump(900) == 0.0
        assert converter.from_heatpump(1800) == 0.5
        assert converter.from_heatpump(2700) == 1.0
        assert converter.from_heatpump(3600) == 1.0
        assert converter.from_heatpump(5400) == 1.5

    def test_to_heatpump_preserves_half_hour_steps(self):
        from custom_components.luxtronik2.lux_overrides import SecondsToHours

        converter = SecondsToHours("Extra_DHW_duration", True)
        assert converter.to_heatpump(0.5) == 1800
        assert converter.to_heatpump(1.0) == 3600
        assert converter.to_heatpump(1.5) == 5400


class TestEnergy2:
    """0.01 kWh per count, a hundredth of a kilowatt-hour, against the
    library's own Energy which is a tenth. Which registers belong on which is
    measured, not documented - see TestEnergyInputScaling in test_sensor.py.
    """

    def test_from_heatpump_divides_by_hundred(self):
        from custom_components.luxtronik2.lux_overrides import Energy2

        converter = Energy2("HEAT_ENERGY_INPUT", False)
        assert converter.from_heatpump(0) == 0.0
        assert converter.from_heatpump(269938) == 2699.38

    def test_to_heatpump_round_trips(self):
        from custom_components.luxtronik2.lux_overrides import Energy2

        converter = Energy2("HEAT_ENERGY_INPUT", False)
        assert converter.to_heatpump(2699.38) == 269938
        assert converter.to_heatpump(0.0) == 0


class TestTimeOfDay:
    from custom_components.luxtronik2.lux_overrides import TimeOfDay

    def test_from_heatpump_formats_hours_and_minutes(self):
        assert self.TimeOfDay.from_heatpump(6 * 3600) == "06:00"
        assert self.TimeOfDay.from_heatpump(22 * 3600 + 30 * 60) == "22:30"

    def test_from_heatpump_includes_seconds_when_nonzero(self):
        assert self.TimeOfDay.from_heatpump(6 * 3600 + 15) == "06:00:15"

    def test_from_heatpump_non_int_returns_none(self):
        assert self.TimeOfDay.from_heatpump("06:00") is None
        assert self.TimeOfDay.from_heatpump(None) is None

    def test_to_heatpump_parses_hours_and_minutes(self):
        assert self.TimeOfDay.to_heatpump("06:00") == 6 * 3600
        assert self.TimeOfDay.to_heatpump("22:30") == 22 * 3600 + 30 * 60

    def test_to_heatpump_parses_seconds_when_present(self):
        assert self.TimeOfDay.to_heatpump("06:00:15") == 6 * 3600 + 15

    def test_to_heatpump_passes_through_int_for_backward_compatibility(self):
        assert self.TimeOfDay.to_heatpump(21600) == 21600

    def test_to_heatpump_non_str_non_int_returns_none(self):
        assert self.TimeOfDay.to_heatpump(None) is None
        assert self.TimeOfDay.to_heatpump(1.5) is None

    def test_roundtrip(self):
        raw = self.TimeOfDay.to_heatpump("07:30")
        assert self.TimeOfDay.from_heatpump(raw) == "07:30"


class TestFrequencyAutomatic:
    from custom_components.luxtronik2.lux_overrides import FrequencyAutomatic

    converter = FrequencyAutomatic("ID_Einst_P155_DHW_Freq", True)

    def test_from_heatpump_zero_is_automatic(self):
        assert self.converter.from_heatpump(0) == 0

    def test_from_heatpump_maps_1_to_20hz(self):
        assert self.converter.from_heatpump(1) == 20

    def test_from_heatpump_maps_101_to_120hz(self):
        assert self.converter.from_heatpump(101) == 120

    def test_to_heatpump_zero_stays_zero(self):
        assert self.converter.to_heatpump(0) == 0

    def test_to_heatpump_maps_20hz_to_1(self):
        assert self.converter.to_heatpump(20) == 1

    def test_to_heatpump_maps_120hz_to_101(self):
        assert self.converter.to_heatpump(120) == 101

    def test_roundtrip_45hz(self):
        raw = self.converter.to_heatpump(45)
        assert self.converter.from_heatpump(raw) == 45


@pytest.fixture
def restore_parse():
    """record_parsed_block_lengths patches library classes process-wide."""
    originals = {cls: cls.parse for cls in (Parameters, Calculations, Visibilities)}
    flag = lux_overrides._PARSE_COUNTS_RECORDED
    lux_overrides._PARSE_COUNTS_RECORDED = False
    yield
    for cls, parse in originals.items():
        cls.parse = parse
    lux_overrides._PARSE_COUNTS_RECORDED = flag


class TestRecordParsedBlockLengths:
    def test_records_block_length_for_each_group(self, restore_parse):
        lux_overrides.record_parsed_block_lengths()

        params = Parameters()
        params.parse([0] * 1126)
        assert getattr(params, PARSED_COUNT_ATTR) == 1126

        calcs = Calculations()
        calcs.parse([0] * 260)
        assert getattr(calcs, PARSED_COUNT_ATTR) == 260

        vis = Visibilities()
        vis.parse([0] * 355)
        assert getattr(vis, PARSED_COUNT_ATTR) == 355

    def test_values_still_parse(self, restore_parse):
        """The wrapper must not swallow the original parse behaviour."""
        lux_overrides.record_parsed_block_lengths()
        params = Parameters()
        params.parse([7] * 1126)
        assert params.parameters[0].value is not None

    def test_is_idempotent(self, restore_parse):
        """Calling twice must not double-wrap or change the recorded count."""
        lux_overrides.record_parsed_block_lengths()
        lux_overrides.record_parsed_block_lengths()
        params = Parameters()
        params.parse([0] * 42)
        assert getattr(params, PARSED_COUNT_ATTR) == 42

    def test_attribute_absent_before_parse(self, restore_parse):
        """A freshly built instance has no count until it has parsed."""
        lux_overrides.record_parsed_block_lengths()
        assert getattr(Parameters(), PARSED_COUNT_ATTR, None) is None


class TestUpstreamMaxDefinedIndex:
    def test_pins_the_installed_library_range(self):
        """The absence rule only fires above this index, so an upstream bump must
        be a deliberate, reviewed change - not a silent behaviour shift."""
        assert lux_overrides.UPSTREAM_MAX_DEFINED_INDEX[CONF_PARAMETERS] == 1125
        assert lux_overrides.UPSTREAM_MAX_DEFINED_INDEX[CONF_CALCULATIONS] == 259
        assert lux_overrides.UPSTREAM_MAX_DEFINED_INDEX[CONF_VISIBILITIES] == 354

    def test_short_block_suppresses_only_override_added_indices(self, restore_parse):
        """The presence rule against real library objects, not positional fakes.

        Every other presence test runs on conftest's FakeSensorGroup, whose index
        is positional. A real Parameters carries the sparse override-added keys
        (1136..1179) and the real 1125 threshold, which is the only place the
        confinement clause can actually be exercised.
        """
        lux_overrides.update_Luxtronik_Parameters()
        lux_overrides.isolate_instance_data()
        lux_overrides.record_parsed_block_lengths()
        short = Parameters()
        short.parse([0] * 1126)
        data = LuxtronikCoordinatorData(short, Parameters(), Parameters())
        assert (
            key_exists(data, "parameters.SECOND_HEAT_GENERATOR_AMOUNT_COUNTER") is False
        )
        assert key_exists(data, "parameters.ELECTRICAL_POWER_LIMIT_VALUE") is False
        assert key_exists(data, "parameters.ID_Waermemenge_ZWE") is True
        assert key_exists(data, f"parameters.{short.parameters[1125].name}") is True

    def test_every_override_only_parameter_sits_above_the_range(self):
        """The 13 indices that exist only because of lux_overrides are exactly the
        ones the absence rule must be able to reach."""
        upstream_max = lux_overrides.UPSTREAM_MAX_DEFINED_INDEX[CONF_PARAMETERS]
        override_only = {
            index
            for index in lux_overrides.parameters_to_add_update
            if index > upstream_max
        }
        assert override_only == {
            1136,
            1137,
            1139,
            1140,
            1146,
            1147,
            1148,
            1158,
            1159,
            1175,
            1176,
            1177,
            1179,
        }


@pytest.fixture
def restore_selection_base():
    """warn_on_unknown_selection_codes patches the library class process-wide."""
    from luxtronik.datatypes import SelectionBase

    original = SelectionBase.from_heatpump
    flag = lux_overrides._UNKNOWN_CODE_WARNING_INSTALLED
    reported = set(lux_overrides._REPORTED_UNKNOWN_CODES)
    lux_overrides._UNKNOWN_CODE_WARNING_INSTALLED = False
    lux_overrides._REPORTED_UNKNOWN_CODES.clear()
    yield
    SelectionBase.from_heatpump = original
    lux_overrides._UNKNOWN_CODE_WARNING_INSTALLED = flag
    lux_overrides._REPORTED_UNKNOWN_CODES.clear()
    lux_overrides._REPORTED_UNKNOWN_CODES.update(reported)


class TestUnknownSelectionCodeWarning:
    def test_warns_with_register_name_and_raw_code(
        self, restore_selection_base, caplog
    ):
        lux_overrides.warn_on_unknown_selection_codes()
        item = HeatpumpCode("ID_WEB_Code_WP_akt")
        assert item.from_heatpump(9999) is None
        assert "ID_WEB_Code_WP_akt" in caplog.text
        assert "9999" in caplog.text
        assert "HeatpumpCode" in caplog.text
        assert "github.com/BenPru/luxtronik/issues" in caplog.text

    def test_warns_only_once_per_code(self, restore_selection_base, caplog):
        lux_overrides.warn_on_unknown_selection_codes()
        item = HeatpumpCode("ID_WEB_Code_WP_akt")
        item.from_heatpump(9999)
        item.from_heatpump(9999)
        assert caplog.text.count("9999") == 1

    def test_known_code_does_not_warn(self, restore_selection_base, caplog):
        lux_overrides.warn_on_unknown_selection_codes()
        item = HeatpumpCode("ID_WEB_Code_WP_akt")
        assert item.from_heatpump(0) is not None
        assert caplog.text == ""

    def test_empty_slot_sentinel_does_not_warn(self, restore_selection_base, caplog):
        """SwitchoffFile's table starts at 1, so raw 0 means 'no entry' - not unknown."""
        lux_overrides.warn_on_unknown_selection_codes()
        assert SwitchoffFile("ID_WEB_Switchoff2_file_Nr0").from_heatpump(0) is None
        assert BivalenceLevel("ID_WEB_BIV_Stufe_akt").from_heatpump(0) is None
        assert caplog.text == ""

    def test_nonzero_unknown_on_sentinel_class_still_warns(
        self, restore_selection_base, caplog
    ):
        lux_overrides.warn_on_unknown_selection_codes()
        assert SwitchoffFile("ID_WEB_Switchoff_file_Nr0").from_heatpump(42) is None
        assert "42" in caplog.text

    def test_is_idempotent(self, restore_selection_base, caplog):
        lux_overrides.warn_on_unknown_selection_codes()
        lux_overrides.warn_on_unknown_selection_codes()
        HeatpumpCode("ID_WEB_Code_WP_akt").from_heatpump(9999)
        assert caplog.text.count("9999") == 1


class TestTimerScheduleDatatypeCoverage:
    """Both timer-program parameter blocks must get their datatypes.

    The heating/DHW/pool block is contiguous at 162-667, but the ventilation
    block sits apart at 895-955 and was not covered at all, so every
    ventilation time decoded as a raw seconds integer.
    """

    def _applied(self):
        from luxtronik.parameters import Parameters

        from custom_components.luxtronik2.lux_overrides import (
            update_Luxtronik_Parameters,
        )

        update_Luxtronik_Parameters()
        return Parameters.parameters

    def test_ventilation_selector_is_a_timer_program(self):
        from custom_components.luxtronik2.lux_overrides import TimerProgram

        assert isinstance(self._applied()[895], TimerProgram)

    def test_ventilation_times_are_time_of_day(self):
        from custom_components.luxtronik2.lux_overrides import TimeOfDay

        parameters = self._applied()
        # First and last of both the start block (896-925) and the
        # interleaved end block (926-955).
        for number in (896, 925, 926, 955):
            assert isinstance(parameters[number], TimeOfDay), number

    def test_heating_block_is_still_covered(self):
        from custom_components.luxtronik2.lux_overrides import (
            TimeOfDay,
            TimerProgram,
        )

        parameters = self._applied()
        assert isinstance(parameters[222], TimerProgram)
        for number in (223, 282):
            assert isinstance(parameters[number], TimeOfDay), number

"""Tests for custom_components.luxtronik2.lux_overrides."""

from __future__ import annotations

from luxtronik.calculations import Calculations
from luxtronik.datatypes import (
    BivalenceLevel,
    Celsius,
    HeatpumpCode,
    Kelvin,
    Percent2,
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
    WRITABLE_PARAMETER_PREFIXES,
    LuxCalculation as LC,
    LuxSwitchoffReason,
    LuxVisibility as LV,
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

    def test_from_heatpump_drops_seconds(self):
        """The controller can only set whole minutes, so seconds are noise.

        Rendering them would also widen the value past what the schedule
        text entities allow: `_attr_native_max` there budgets 11 characters
        per "HH:MM-HH:MM" pair.
        """
        assert self.TimeOfDay.from_heatpump(6 * 3600 + 15) == "06:00"
        assert self.TimeOfDay.from_heatpump(6 * 3600 + 59) == "06:00"
        assert self.TimeOfDay.from_heatpump(59) == "00:00"

    def test_from_heatpump_is_always_five_characters(self):
        """The invariant `_attr_native_max` in text.py is sized against."""
        for raw in range(0, 24 * 3600, 617):
            assert len(self.TimeOfDay.from_heatpump(raw)) == 5

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
    """Both parse patches are installed process-wide and guarded by a module
    flag, so the flag has to travel with the function it guards: put parse
    back without resetting the flag and every later call returns at the guard,
    leaving the patch permanently uninstalled."""
    originals = {cls: cls.parse for cls in (Parameters, Calculations, Visibilities)}
    flags = (
        lux_overrides._PARSE_COUNTS_RECORDED,
        lux_overrides._UNKNOWN_VISIBILITY_NAMES_FIXED,
    )
    lux_overrides._PARSE_COUNTS_RECORDED = False
    lux_overrides._UNKNOWN_VISIBILITY_NAMES_FIXED = False
    yield
    for cls, parse in originals.items():
        cls.parse = parse
    (
        lux_overrides._PARSE_COUNTS_RECORDED,
        lux_overrides._UNKNOWN_VISIBILITY_NAMES_FIXED,
    ) = flags


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


class TestInventedParameterNames:
    """Every name invented here has to be reachable by the write service."""

    def test_every_invented_name_is_writable(self):
        """const.py documents this as a rule to be kept by hand, so a new
        override with a custom name silently loses the ability to be written
        until someone remembers the second edit. The names that upstream
        supplies all start with ID_ or Unknown_Parameter_ and are covered by
        prefixes already; only the invented ones need checking.
        """
        invented = {
            datatype.name
            for datatype in lux_overrides.parameters_to_add_update.values()
            if not datatype.name.startswith(("ID_", "Unknown_Parameter_"))
        }
        assert invented
        unreachable = {
            name
            for name in invented
            if not name.startswith(WRITABLE_PARAMETER_PREFIXES)
        }
        assert unreachable == set()


class TestSmartGridTemperatureOffsets:
    """Parameters 1120-1122, the Smart Grid offsets of #765.

    Upstream leaves all three as `Unknown_Parameter_112x` / `Unknown` and
    marks them non-writeable; this integration renames them, types them as
    Kelvin deltas and writes them, so the mapping is pinned here.

    Evidence for the mapping: the reporter's A/B test on an LWC407 moved
    -2.0/+2.0/+2.0 K to -1.5/+2.5/+5.0 K and the registers followed
    (-20/20/20 -> -15/25/50); the HMD2 manual (83055600 rev d, p.43) lists
    exactly these three settings with those defaults; and across 29 pumps in
    the diagnostics corpus every unit at factory default reads -20/20/20
    while every deviation sits on a unit with Smart Grid switched on.
    """

    def test_parameters_are_named_and_kelvin_typed(self):
        lux_overrides.update_Luxtronik_Parameters()

        for index, name in (
            (1120, "SMART_GRID_HEATING_REDUCTION"),
            (1121, "SMART_GRID_HEATING_INCREASE"),
            (1122, "SMART_GRID_DHW_INCREASE"),
        ):
            assert Parameters.parameters[index].name == name
            assert isinstance(Parameters.parameters[index], Kelvin)

    def test_reduction_scales_a_negative_raw_value(self):
        """The reduction is the only negative-valued parameter this
        integration writes, and the manual's range reaches -25 K.
        """
        lux_overrides.update_Luxtronik_Parameters()
        reduction = Parameters.parameters[1120]

        assert reduction.from_heatpump(-20) == -2.0
        assert reduction.from_heatpump(-250) == -25.0
        assert reduction.to_heatpump(-25.0) == -250
        assert reduction.to_heatpump(-0.5) == -5

    def test_increases_scale_by_tenths(self):
        lux_overrides.update_Luxtronik_Parameters()

        assert Parameters.parameters[1121].from_heatpump(50) == 5.0
        assert Parameters.parameters[1121].to_heatpump(5.0) == 50
        assert Parameters.parameters[1122].from_heatpump(100) == 10.0
        assert Parameters.parameters[1122].to_heatpump(10.0) == 100


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
        """The 15 indices that exist only because of lux_overrides are exactly the
        ones the absence rule must be able to reach."""
        upstream_max = lux_overrides.UPSTREAM_MAX_DEFINED_INDEX[CONF_PARAMETERS]
        override_only = {
            index
            for index in lux_overrides.parameters_to_add_update
            if index > upstream_max
        }
        assert override_only == {
            1135,
            1136,
            1137,
            1138,
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
        """BivalenceLevel's table starts at 1, so raw 0 means 'no entry' - not unknown."""
        lux_overrides.warn_on_unknown_selection_codes()
        assert BivalenceLevel("ID_WEB_BIV_Stufe_akt").from_heatpump(0) is None
        assert caplog.text == ""

    def test_ventilation_selector_without_module_does_not_warn(
        self, restore_selection_base, caplog
    ):
        """P895 reads 0 on every unit without a ventilation module (#789)."""
        from custom_components.luxtronik2.lux_overrides import (
            VentilationTimerProgram,
        )

        lux_overrides.warn_on_unknown_selection_codes()
        selector = VentilationTimerProgram("ID_Einst_SuLuf_akt")
        assert selector.from_heatpump(0) is None
        assert caplog.text == ""
        # A module unit on a code outside 3-5 must still ask to be reported.
        assert selector.from_heatpump(6) is None
        assert "ID_Einst_SuLuf_akt" in caplog.text


class TestSwitchoffCodes:
    def test_table_matches_switchoff_reason_translations(self):
        """The library table and the sensor's own translations must agree."""
        lux_overrides.update_Luxtronik_SwitchoffCodes()
        item = SwitchoffFile("ID_WEB_Switchoff_file_Nr0")
        assert item.from_heatpump(0) == "heatpump error"
        assert item.from_heatpump(3) == "evu lock"
        assert item.from_heatpump(11) == "flow rate"
        assert item.from_heatpump(25) == "restart"
        assert item.from_heatpump(26) == "maximum return temperature increase"
        assert item.from_heatpump(27) == "maximum flow temperature"

    def test_every_code_is_named_and_translated(self):
        """The library table, the enum and en.json must describe the same codes."""
        import json
        from pathlib import Path

        lux_overrides.update_Luxtronik_SwitchoffCodes()
        translations = json.loads(
            (
                Path(__file__).resolve().parent.parent
                / "custom_components"
                / "luxtronik2"
                / "translations"
                / "en.json"
            ).read_text(encoding="utf-8")
        )
        states = translations["entity"]["sensor"]["switchoff_reason"]["state"]

        for code in SwitchoffFile("").codes:
            assert code in {e.value for e in LuxSwitchoffReason}, code
            assert str(code) in states, code

    def test_still_reports_codes_outside_the_known_table(
        self, restore_selection_base, caplog
    ):
        """Codes past the observed ones stay undocumented - keep asking for reports."""
        lux_overrides.update_Luxtronik_SwitchoffCodes()
        lux_overrides.warn_on_unknown_selection_codes()
        assert SwitchoffFile("ID_WEB_Switchoff_file_Nr1").from_heatpump(28) is None
        assert "28" in caplog.text

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

    def test_ventilation_selector_has_its_own_code_table(self):
        """P895 is offset by 3 from the other circuits (#789).

        A controller with a ventilation module reports 3 for week, 4 for 5+2
        and 5 for days (read off the Lueftung -> Zeitschaltprogramm menu);
        the heating and DHW selectors report 0, 1 and 2 for the same shapes.
        """
        from custom_components.luxtronik2.lux_overrides import (
            TimerProgram,
            VentilationTimerProgram,
        )

        selector = self._applied()[895]
        assert isinstance(selector, VentilationTimerProgram)
        assert not isinstance(selector, TimerProgram)
        assert selector.from_heatpump(3) == "week"
        assert selector.from_heatpump(4) == "5+2"
        assert selector.from_heatpump(5) == "days"
        assert selector.to_heatpump("week") == 3
        assert selector.to_heatpump("5+2") == 4
        assert selector.to_heatpump("days") == 5

    def test_ventilation_selector_reads_zero_as_no_module(self):
        """Every sampled unit without a module reports 0; that is not a shape.

        0 must decode to None without tripping the unknown-code warning,
        which skips raw 0 only when the table has no entry for it.
        """
        selector = self._applied()[895]
        assert 0 not in selector.codes
        assert selector.from_heatpump(0) is None

    def test_pool_selector_is_a_time_of_day(self):
        """P607 is a time slot, not a mode selector (#789).

        Three units (V3.86.1, V3.90.1, V3.92.3) report 23400/25200/27000
        there - 06:30/07:00/07:30 - each followed by an end time in 608. The
        upstream name ``ID_Einst_SuSwb_akt`` is a guess; nothing reads it.
        """
        from custom_components.luxtronik2.lux_overrides import TimeOfDay

        assert isinstance(self._applied()[607], TimeOfDay)
        assert self._applied()[607].from_heatpump(27000) == "07:30"

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

    def test_mixing_circuit_3_block_is_covered(self):
        """788-848 is the Mk3 circuit, apart from the 162-667 run.

        Same selector + WO/25/TG shape as the others (upstream `main` types
        it that way); two corpus units carry 34200 / 18000 (09:30 / 05:00)
        in 789, the rest hold 0.
        """
        from custom_components.luxtronik2.lux_overrides import (
            TimeOfDay,
            TimerProgram,
        )

        parameters = self._applied()
        selector = parameters[788]
        assert selector.name == "ID_Einst_SuMk3_akt2"
        assert isinstance(selector, TimerProgram)
        assert selector.from_heatpump(0) == "week"
        for number in (789, 848):
            assert isinstance(parameters[number], TimeOfDay), number
        assert parameters[789].name == "ID_Einst_SuMk3Wo_zeit_0_0"
        assert parameters[789].from_heatpump(34200) == "09:30"
        assert parameters[848].name == "ID_Einst_SuMk3Tg_zeit_2_13"
        # The block ends at 848; 849 is not a schedule register.
        assert not isinstance(parameters[849], TimeOfDay)


class TestUpstreamCelsiusParameters:
    """Six limit temperatures upstream `main` types as Celsius (tenths).

    Every unit in the corpus stores them as tenths (700, 560, 350, -200,
    1150, 500), which also matches the setting each one names.
    """

    _EXPECTED = {
        84: ("ID_Sollwert_TLG_max", 700, 70.0),
        87: ("ID_Einst_TRBegr_akt", 560, 56.0),
        91: ("ID_Einst_TAmax_akt", 350, 35.0),
        92: ("ID_Einst_TAmin_akt", -200, -20.0),
        94: ("ID_Einst_THGmax_akt", 1150, 115.0),
        96: ("ID_Einst_TV2VDBW_akt", 500, 50.0),
    }

    def test_are_celsius_in_tenths(self):
        from luxtronik.datatypes import Celsius
        from luxtronik.parameters import Parameters

        from custom_components.luxtronik2.lux_overrides import (
            update_Luxtronik_Parameters,
        )

        update_Luxtronik_Parameters()
        for number, (name, raw, value) in self._EXPECTED.items():
            parameter = Parameters.parameters[number]
            assert parameter.name == name, number
            assert isinstance(parameter, Celsius), number
            assert parameter.from_heatpump(raw) == value, number


class TestUpstreamCounterParameters:
    """Operating-time counters and the heat-quantity date, typed as upstream
    `main` does. Nothing in the integration reads these registers (the
    sensors use the calculation mirrors 56-66); this only makes diagnostics
    dumps readable.
    """

    _SECONDS = {
        668: "ID_Zaehler_BetrZeitWP",
        669: "ID_Zaehler_BetrZeitVD1",
        670: "ID_Zaehler_BetrZeitVD2",
        671: "ID_Zaehler_BetrZeitZWE1",
        672: "ID_Zaehler_BetrZeitZWE2",
        673: "ID_Zaehler_BetrZeitZWE3",
        728: "ID_Zaehler_BetrZeitHz",
        729: "ID_Zaehler_BetrZeitBW",
        730: "ID_Zaehler_BetrZeitKue",
        859: "ID_Zaehler_BetrZeitSW",
    }

    def _applied(self):
        from luxtronik.parameters import Parameters

        from custom_components.luxtronik2.lux_overrides import (
            update_Luxtronik_Parameters,
        )

        update_Luxtronik_Parameters()
        return Parameters.parameters

    def test_operating_time_counters_are_seconds(self):
        from luxtronik.datatypes import Seconds

        parameters = self._applied()
        for number, name in self._SECONDS.items():
            assert parameters[number].name == name, number
            assert isinstance(parameters[number], Seconds), number
        # 60515833 s on one corpus unit, i.e. about 700 days of runtime.
        assert parameters[668].from_heatpump(60515833) == 60515833

    def test_heat_quantity_date_is_a_timestamp(self):
        from datetime import datetime

        from luxtronik.datatypes import Timestamp

        parameter = self._applied()[880]
        assert parameter.name == "ID_Waermemenge_Datum"
        assert isinstance(parameter, Timestamp)
        # Eight corpus units sit on the 2018-01-01 factory default.
        assert isinstance(parameter.from_heatpump(1514768400), datetime)


class TestSmartGridMode:
    """P1030 is a four-option mode selector, so it needs a real datatype.

    Left as Unknown it has no to_heatpump conversion, and Luxtronik.write
    discards every queued value that is not an int - so the select wrote
    nothing at all and then failed its write confirmation.
    """

    def _datatype(self):
        lux_overrides.update_Luxtronik_HeatpumpCodes()
        lux_overrides.update_Luxtronik_Parameters()
        return Parameters.parameters[1030]

    def test_registered_on_parameter_1030(self):
        assert type(self._datatype()).__name__ == "SmartGridMode"

    def test_writes_an_int(self):
        raw = self._datatype().to_heatpump("sg_1_1")
        assert raw == 3
        assert isinstance(raw, int)

    def test_reads_the_menu_entry(self):
        assert self._datatype().from_heatpump(3) == "sg_1_1"
        assert self._datatype().from_heatpump(0) == "off"

    def test_a_raw_code_stays_writable_for_the_write_service(self):
        """luxtronik2.write passes the number the user typed. Before this
        parameter had a datatype it was written as-is; a SelectionBase that
        only knows names would queue None, which Luxtronik.write discards -
        and the write confirmation then raises at the user.
        """
        raw = self._datatype().to_heatpump(3)
        assert raw == 3
        assert isinstance(raw, int)

    def test_an_undocumented_code_passes_through_instead_of_reading_none(self):
        """None already means "the controller never sent this register", and
        for parameter 1030 nothing can tell those two apart afterwards. A
        firmware with a fifth mode must not read as an absent register."""
        assert self._datatype().from_heatpump(4) == 4


class TestHeatingCircuitControlMode:
    """P0103 has the same defect as P1030 had: an Unknown parameter driven by
    a select, so selecting a mode queued a string and wrote nothing."""

    def _datatype(self):
        lux_overrides.update_Luxtronik_HeatpumpCodes()
        lux_overrides.update_Luxtronik_Parameters()
        return Parameters.parameters[103]

    def test_writes_an_int(self):
        raw = self._datatype().to_heatpump("fixed_temperature")
        assert raw == 1
        assert isinstance(raw, int)

    def test_a_raw_code_stays_writable_for_the_write_service(self):
        assert self._datatype().to_heatpump(1) == 1

    def test_reads_the_named_mode(self):
        """The raw digits carried no meaning in the state; the names the
        integration already had in LuxHeatingControlModeTypes do."""
        assert self._datatype().from_heatpump(0) == "heating_curve_control"
        assert self._datatype().from_heatpump(1) == "fixed_temperature"
        assert self._datatype().from_heatpump(2) == "analog_in"


class TestCalculationNamesFollowUpstreamMain:
    """The pinned 0.3.14 leaves calculations 239/240/242/243 unnamed and
    calls 241 Circulation_Pump. Upstream main has since named all five, and
    lists Circulation_Pump only as an alias of HUP_PWM. Renaming them here
    keeps const.py readable and makes the eventual library bump a no-op for
    these registers - two diagnostics dumps in the corpus already came from
    an installation carrying the newer names.

    The rename must not change how a value is read: the datatypes stay the
    ones 0.3.14 ships, so the descriptions keep supplying their own scaling.
    """

    RENAMED = {
        239: "VBO_Temp_Spread_Soll",
        240: "VBO_Temp_Spread_Ist",
        241: "HUP_PWM",
        242: "HUP_Temp_Spread_Soll",
        243: "HUP_Temp_Spread_Ist",
    }

    def test_calculations_carry_the_upstream_names(self):
        lux_overrides.update_Luxtronik_Parameters()
        for index, name in self.RENAMED.items():
            assert Calculations.calculations[index].name == name

    def test_rename_keeps_the_pinned_datatypes(self):
        """Percent2 and Unknown are both pass-throughs - a value read before
        the rename reads the same after it."""
        lux_overrides.update_Luxtronik_Parameters()
        for index in (239, 240, 242, 243):
            assert isinstance(Calculations.calculations[index], Unknown)
        assert isinstance(Calculations.calculations[241], Percent2)
        assert Calculations.calculations[241].from_heatpump(46) == 46
        assert Calculations.calculations[243].from_heatpump(37) == 37

    def test_the_const_keys_resolve_to_a_real_register(self):
        """The names in const.py and the names in the patched library are
        the same string, which is what key_exists() matches on."""
        lux_overrides.update_Luxtronik_Parameters()
        calculations = Calculations()
        for key in (
            LC.C0239_PUMP_FLOW_DELTA_TARGET,
            LC.C0240_PUMP_FLOW_DELTA,
            LC.C0241_CIRCULATION_PUMP_PWM,
            LC.C0242_CIRCULATION_PUMP_DELTA_TARGET,
            LC.C0243_CIRCULATION_PUMP_DELTA,
        ):
            assert calculations.get(str(key).split(".", 1)[1]) is not None


class TestUnknownVisibilityNames:
    """0.3.14's Visibilities.parse() names every index past its table
    `Unknown_Parameter_<index>` - a copy-paste from parameters.py, where that
    prefix is right. Inside the table the same library already uses
    `Unknown_Visibility_<index>` (30 such entries), and upstream main uses it
    for the generated ones too, so the parameter prefix is simply wrong.

    It matters beyond tidiness: controllers routinely return 400 visibilities
    (46 of the 80 diagnostics dumps do), so indices 355+ are generated on most
    units, and a key like V0357 has to spell the placeholder exactly.
    """

    LONG_BLOCK = [0] * 401

    def _parsed(self):
        """Callers take the restore_parse fixture; this installs the patch."""
        lux_overrides.update_Luxtronik_Parameters()
        lux_overrides.isolate_instance_data()
        lux_overrides.name_unknown_visibilities_correctly()
        visibilities = Visibilities()
        visibilities.parse(self.LONG_BLOCK)
        return visibilities

    def test_generated_names_use_the_visibility_prefix(self, restore_parse):
        visibilities = self._parsed()
        assert visibilities.visibilities[357].name == "Unknown_Visibility_357"
        assert visibilities.get("Unknown_Visibility_357") is not None

    def test_no_generated_name_keeps_the_parameter_prefix(self, restore_parse):
        visibilities = self._parsed()
        stale = [
            index
            for index, visibility in visibilities.visibilities.items()
            if visibility.name.startswith("Unknown_Parameter_")
        ]
        assert not stale

    def test_named_and_in_table_placeholders_are_untouched(self, restore_parse):
        """Only the generated names are rewritten - the library's own
        Unknown_Visibility_* entries and every real name stay as they are."""
        visibilities = self._parsed()
        assert visibilities.visibilities[5].name == "ID_Visi_Kuhlung"
        assert visibilities.visibilities[325].name == "Unknown_Visibility_325"

    def test_parameters_keep_their_own_prefix(self, restore_parse):
        """Unknown_Parameter_<index> is correct for parameters; the rename
        must not follow the patch onto the other two classes."""
        lux_overrides.update_Luxtronik_Parameters()
        lux_overrides.isolate_instance_data()
        lux_overrides.name_unknown_visibilities_correctly()
        parameters = Parameters()
        parameters.parse([0] * 1200)
        assert parameters.parameters[1150].name == "Unknown_Parameter_1150"

    def test_applying_twice_installs_one_wrapper(self, restore_parse):
        """Asserted on the patch, not on its output: the rewrite is
        idempotent, so even a stacked wrapper produces the right name and
        would never show up in a parsed value."""
        lux_overrides.name_unknown_visibilities_correctly()
        installed = Visibilities.parse
        lux_overrides.name_unknown_visibilities_correctly()
        assert Visibilities.parse is installed

    def test_the_const_key_matches_what_parse_produces(self, restore_parse):
        """V0357 is the one member naming a generated visibility."""
        visibilities = self._parsed()
        raw_name = LV.V0357_ELECTRICAL_POWER_LIMITATION_SWITCH.removeprefix(
            "visibilities."
        )
        assert visibilities.get(raw_name) is not None

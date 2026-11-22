"""Tests for predefined entity lists."""

from __future__ import annotations

from collections.abc import Iterator
import importlib
import pkgutil
from unittest.mock import patch

from luxtronik.parameters import Parameters
from packaging.version import Version

from conftest import make_coordinator_data
import custom_components.luxtronik2 as luxtronik2
from custom_components.luxtronik2 import lux_overrides
from custom_components.luxtronik2.binary_sensor_entities_predefined import (
    BINARY_SENSORS,
)
from custom_components.luxtronik2.const import (
    AIR_INVERTER_MODELS,
    DeviceKey,
    LuxCalculation,
    LuxParameter,
    LuxVisibility,
    SensorKey,
)
from custom_components.luxtronik2.coordinator import LuxtronikCoordinator
from custom_components.luxtronik2.date_entities_predefined import CALENDAR_ENTITIES
from custom_components.luxtronik2.model import LuxtronikEntityDescription
from custom_components.luxtronik2.number_entities_predefined import NUMBER_SENSORS
from custom_components.luxtronik2.sensor_entities_predefined import SENSORS
from custom_components.luxtronik2.switch_entities_predefined import SWITCHES


def _is_luxtronik_description(item: object) -> bool:
    """Whether item is one of our entity descriptions.

    Deliberately not isinstance(): HA's `frozen_or_thawed=True` metaclass
    builds distinct frozen and thawed class objects, so the
    LuxtronikEntityDescription appearing in a description's MRO is a
    different object from the imported one and isinstance is always False.
    Matching on the MRO by name sidesteps that.
    """
    return any(
        base.__name__ == LuxtronikEntityDescription.__name__
        for base in type(item).__mro__
    )


def _all_descriptions() -> Iterator[LuxtronikEntityDescription]:
    """Yield every entity description defined anywhere in the package.

    Descriptions live in the *_entities_predefined modules for most
    platforms, but water_heater and climate declare theirs inline, so this
    walks every module rather than a fixed list of imports.
    """
    for module_info in pkgutil.iter_modules(luxtronik2.__path__):
        module = importlib.import_module(f"{luxtronik2.__name__}.{module_info.name}")
        for attr_name in dir(module):
            if attr_name.startswith("__"):
                continue
            value = getattr(module, attr_name)
            if isinstance(value, (list, tuple)):
                for item in value:
                    if _is_luxtronik_description(item):
                        yield item


class TestBinarySensorPredefined:
    def test_has_entries(self):
        assert len(BINARY_SENSORS) > 0

    def test_all_have_key(self):
        for bs in BINARY_SENSORS:
            assert bs.key is not None
            assert bs.luxtronik_key is not None

    def test_unique_keys(self):
        keys = [bs.key for bs in BINARY_SENSORS]
        assert len(keys) == len(set(keys))


class TestSwitchPredefined:
    def test_has_entries(self):
        assert len(SWITCHES) > 0

    def test_all_have_key(self):
        for sw in SWITCHES:
            assert sw.key is not None
            assert sw.luxtronik_key is not None

    def test_vent_zup_targets_parameter_679(self):
        """The ZUP venting switch drives ID_Einst_Entl_Typ_1 (P679).

        Only Typ_0 = HUP was known; Typ_1 = ZUP was inferred from the menu
        order and confirmed on hardware in discussion #802. The visibility
        flag ID_Visi_Enlt_ZUP reads 1 on every unit in the corpus, so it
        cannot gate anything - the switch is ungated and off by default.
        """
        from luxtronik.parameters import Parameters

        (zup,) = [sw for sw in SWITCHES if sw.key == SensorKey.PUMP_VENT_ZUP]
        assert zup.luxtronik_key == LuxParameter.P0679_VENTING_ZUP_ACTIVE
        assert Parameters().get(679).name == "ID_Einst_Entl_Typ_1"
        assert zup.luxtronik_key.value == "parameters.ID_Einst_Entl_Typ_1"
        assert zup.visibility == LuxVisibility.UNSET
        assert zup.entity_registry_enabled_default is False
        assert zup.device_key == DeviceKey.heating


class TestEfficiencyPump:
    """P867/P868 are a 0-10 V installer setting on series 1/2 (> 100) but a
    value the controller rewrites itself every ~2 h on series 3 (<= 100), so
    only the voltage form is writable; the percentage form is a read-only
    diagnostic sensor.
    """

    _REGISTERS = (
        LuxParameter.P0867_EFFICIENCY_PUMP_NOMINAL,
        LuxParameter.P0868_EFFICIENCY_PUMP_MINIMAL,
    )

    def test_only_the_voltage_form_is_writable(self):
        numbers = [d for d in NUMBER_SENSORS if d.luxtronik_key in self._REGISTERS]
        assert {d.luxtronik_key for d in numbers} == set(self._REGISTERS)
        for number in numbers:
            assert number.entity_active == ((number.luxtronik_key, "> 100"),)

    def test_percentage_form_is_a_read_only_diagnostic_sensor(self):
        sensors = [d for d in SENSORS if d.luxtronik_key in self._REGISTERS]
        assert {d.luxtronik_key for d in sensors} == set(self._REGISTERS)
        for sensor in sensors:
            assert sensor.entity_active == ((sensor.luxtronik_key, "<= 100"),)
            assert sensor.native_unit_of_measurement == "%"
            assert sensor.entity_category == "diagnostic"
            assert sensor.entity_registry_enabled_default is False


class TestSensorPredefined:
    def test_has_entries(self):
        assert len(SENSORS) > 0

    def test_all_have_key(self):
        for s in SENSORS:
            assert s.key is not None
            assert s.luxtronik_key is not None

    def test_unique_keys(self):
        """A key is the entity's unique_id. Only fan_speed and compressor_speed
        are shared, each by two descriptions whose gates exclude each other
        (test_every_model_gets_at_most_one_fan_sensor,
        test_compressor_speed_gates_are_exclusive)."""
        keys = [s.key for s in SENSORS]
        shared = {key for key in keys if keys.count(key) > 1}
        assert shared == {SensorKey.FAN_SPEED, SensorKey.COMPRESSOR_SPEED}
        assert keys.count(SensorKey.FAN_SPEED) == 2
        assert keys.count(SensorKey.COMPRESSOR_SPEED) == 2


class TestNumberPredefined:
    def test_has_entries(self):
        assert len(NUMBER_SENSORS) > 0

    def test_all_have_key(self):
        for n in NUMBER_SENSORS:
            assert n.key is not None
            assert n.luxtronik_key is not None


class TestDatePredefined:
    def test_has_entries(self):
        assert len(CALENDAR_ENTITIES) > 0

    def test_all_have_key(self):
        for d in CALENDAR_ENTITIES:
            assert d.key is not None
            assert d.luxtronik_key is not None


class TestFirmwareVersionFields:
    """Every firmware gate must hold a Version, on every platform.

    The four firmware fields are compared against a Version with `<` / `>`.
    A bare int or an Enum member raises TypeError at entity setup, because
    Version.__lt__ returns NotImplemented and neither int nor Enum defines
    the reflected operator against it - so the failure surfaces as entities
    silently missing from a user's installation, not as a test failure.

    This walks every description the package defines rather than a
    hand-listed set, so a new platform or a new predefined list is covered
    the moment it exists.
    """

    FIELDS = (
        "min_firmware_version",
        "max_firmware_version",
        "min_firmware_version_minor",
        "max_firmware_version_minor",
    )

    def test_all_descriptions_use_version_or_none(self):
        descriptions = list(_all_descriptions())
        # Guard the guard: an import that silently yielded nothing would
        # make every assertion below vacuous.
        assert len(descriptions) > 100

        offenders = [
            (type(descr).__name__, descr.key, name, repr(value))
            for descr in descriptions
            for name in self.FIELDS
            if not isinstance(
                (value := getattr(descr, name, None)), (Version, type(None))
            )
        ]
        assert offenders == []

    def test_at_least_one_gate_is_actually_in_use(self):
        """Otherwise the check above passes trivially forever."""
        assert any(
            getattr(descr, name, None) is not None
            for descr in _all_descriptions()
            for name in self.FIELDS
        )

    def test_no_description_gates_on_the_absolute_version(self):
        """Register gates must compare the minor version, not the whole one.

        The firmware major digit is the controller *series* - V1.x, V2.x and
        V3.x are different hardware generations - and it never advances on a
        firmware update. Only the minor digit tracks the register layout, so
        `Version("3.90.1")` in a gate reads every V1.x and V2.x controller as
        older than everything and serves those owners the wrong entity set
        regardless of how current their firmware is.

        Use `min/max_firmware_version_minor`. A difference that really is
        per-generation belongs in code, against
        `LuxtronikCoordinator.firmware_series`.
        """
        descriptions = list(_all_descriptions())
        # Guard the guard: a walker that silently yielded nothing would make
        # the assertion below vacuous.
        assert len(descriptions) > 100

        offenders = [
            (type(descr).__name__, descr.key, name, str(value))
            for descr in descriptions
            for name in ("min_firmware_version", "max_firmware_version")
            if (value := getattr(descr, name, None)) is not None
        ]
        assert offenders == []


class TestVisibilityGates:
    """Every gate must survive the value its register actually reports."""

    def test_no_description_gates_on_a_parameter_through_visibility(self):
        """A parameter that decides whether an entity should exist belongs in
        `entity_active`, which decides existence and is declared on the
        description. As a `visibility` it only decides enabled-by-default,
        and a mode-valued one needed its own rule in the coordinator (#773,
        #815). Visibility flags stay in `visibility`.
        """
        offenders = [
            (type(descr).__name__, descr.key)
            for descr in _all_descriptions()
            if isinstance(descr.visibility, LuxParameter)
        ]
        assert offenders == []

    def test_no_declared_gate_breaks_on_a_decoded_value(self):
        """A gate register may decode to a name.

        `lux_overrides` gives selection datatypes to parameters as their codes
        become known, and such a register then reads "plus_minus" rather than
        1. A gate that raised on that would abort `async_setup_entry` for the
        whole platform: that is how #773 lost every number entity, not just
        the three gated ones.
        """
        gated = [descr for descr in _all_descriptions() if descr.entity_active]
        # Guard the guard: nothing gated means nothing was checked.
        assert gated

        coord = object.__new__(LuxtronikCoordinator)
        coord.data = make_coordinator_data()
        with (
            patch.object(LuxtronikCoordinator, "get_value", return_value="plus_minus"),
            patch.object(
                LuxtronikCoordinator, "_is_version_not_compatible", return_value=False
            ),
            patch.object(LuxtronikCoordinator, "device_key_active", return_value=True),
        ):
            for descr in gated:
                assert isinstance(coord.entity_active(descr), bool), descr.key

    def test_every_entity_active_condition_is_a_register_and_a_formula(self):
        """Each condition is a (register, formula) pair. A bare pair written
        without its enclosing tuple - `entity_active=(LP.X, "!= 0")` - would
        be read as two broken conditions instead of one (#815).
        """
        offenders = [
            (type(descr).__name__, descr.key, condition)
            for descr in _all_descriptions()
            for condition in descr.entity_active
            if not (
                isinstance(condition, tuple)
                and len(condition) == 2
                and isinstance(
                    condition[0], LuxParameter | LuxCalculation | LuxVisibility
                )
                and condition[0] != LuxParameter.UNSET
                and isinstance(condition[1], str)
            )
        ]
        assert offenders == []

    def test_every_gated_description_has_a_register_of_its_own(self):
        """A declared gate also requires the entity's own register to be
        returned, so a gated description without one could never exist.
        """
        offenders = [
            (type(descr).__name__, descr.key)
            for descr in _all_descriptions()
            if descr.entity_active and descr.luxtronik_key == LuxParameter.UNSET
        ]
        assert offenders == []

    def test_every_entity_active_formula_parses(self):
        """A formula that does not parse logs a warning and then falls
        through to True - the entity is created on every install. An empty
        list item (`in 3,,4`, a trailing comma) is the easy way to get there.
        """
        offenders = []
        for descr in _all_descriptions():
            for _register, formula in descr.entity_active:
                parts = formula.split(maxsplit=1)
                if (
                    len(parts) != 2
                    or parts[0]
                    not in {"==", "!=", "<", "<=", ">", ">=", "in", "not_in"}
                    or (
                        parts[0] in {"in", "not_in"}
                        and "" in [item.strip() for item in parts[1].split(",")]
                    )
                ):
                    offenders.append((type(descr).__name__, descr.key, formula))
        assert offenders == []

    def test_numeric_gates_read_numeric_registers(self):
        """A numeric threshold on a register that decodes to a name fails
        open: `"none" != 0` compares as strings and is True, so the entity
        comes back on every install with nothing in the log (#773, #777).
        P0033 is the likely next one - `LuxRoomThermostatType` already
        exists. If a register here gains a selection datatype, rewrite its
        gate as an `in` list of codes and names, as the MK gates do. Own-register
        numeric gates (P1059, P1119, P0867, ...) are checked too.
        """
        lux_overrides.update_Luxtronik_Parameters()
        parameters = Parameters()
        checked: set[LuxParameter] = set()
        for descr in _all_descriptions():
            for key, formula in descr.entity_active:
                if not isinstance(key, LuxParameter):
                    continue
                threshold = formula.split()[1]
                try:
                    float(threshold)
                except ValueError:
                    continue
                datatype = parameters.get(key.rsplit(".", 1)[1])
                decoded = datatype.from_heatpump(0)
                assert not isinstance(decoded, str), (descr.key, key, decoded)
                checked.add(key)
        # Guard the guard: the P0033 and P1010 gates must be among them.
        assert {
            LuxParameter.P0033_ROOM_THERMOSTAT_TYPE,
            LuxParameter.P1010_IS_TWIN,
        } <= checked

    def test_no_description_pairs_a_special_gate_with_a_formula(self):
        """`_special_visibility` answers before `visibility_formula` is read.

        That early return is deliberate - the special gates exist precisely
        because their register cannot be read at face value - but it means a
        formula written against one of those keys would be silently ignored.
        Nothing does that today; this fails the moment something starts to.
        """
        offenders = [
            (type(descr).__name__, descr.key)
            for descr in _all_descriptions()
            if descr.visibility_formula is not None
            and descr.visibility
            in (
                LuxVisibility.V0038_SOLAR_COLLECTOR,
                LuxVisibility.V0039_SOLAR_BUFFER,
                LuxVisibility.V0250_SOLAR,
                LuxVisibility.V0059_DHW_CIRCULATION_PUMP,
                LuxVisibility.V0059A_DHW_CHARGING_PUMP,
                LuxVisibility.V0005_COOLING,
            )
        ]
        assert offenders == []


class TestSilentMode:
    """The inverter silent mode (#882): switch P1087, program select P1092
    and the "week" schedule over 1093-1113.

    Every unit with a long enough parameter block returns these registers,
    brine and fixed-speed units included (they read off/week), so all three
    are gated on the air inverter model list rather than on register
    presence.
    """

    _GATE = ((LuxCalculation.C0078_MODEL_CODE, f"in {AIR_INVERTER_MODELS}"),)

    def test_switch(self):
        switch = next(d for d in SWITCHES if d.key == SensorKey.SILENT_MODE)
        assert switch.luxtronik_key == LuxParameter.P1087_SILENT_MODE
        assert (switch.on_state, switch.off_state) == ("on", "off")
        assert switch.entity_active == self._GATE

    def test_program_select(self):
        from custom_components.luxtronik2.select_entities_predefined import (
            SELECT_ENTITIES,
            TIMER_PROGRAM_RAW_OPTIONS,
        )

        select = next(
            d for d in SELECT_ENTITIES if d.key == SensorKey.TIMER_SILENT_MODE_PROGRAM
        )
        assert select.luxtronik_key == LuxParameter.P1092_TIMER_PROGRAM_SILENT_MODE
        assert select.device_key is DeviceKey.heatpump
        assert select.raw_option_map == TIMER_PROGRAM_RAW_OPTIONS
        assert select.entity_active == self._GATE

    def test_schedules(self):
        from custom_components.luxtronik2.timer_schedule_entities_predefined import (
            TIMER_SCHEDULE_ENTITIES,
        )

        schedules = [
            d
            for d in TIMER_SCHEDULE_ENTITIES
            if d.mode_selector_name == "ID_Einst_SuSilence"
        ]
        # week, weekdays, weekend and seven days
        assert len(schedules) == 10
        for schedule in schedules:
            assert str(schedule.key).startswith("timer_silent_mode_schedule_")
            assert schedule.device_key is DeviceKey.heatpump
            # The selector stands in as the entity's own register (#738).
            assert (
                schedule.luxtronik_key == LuxParameter.P1092_TIMER_PROGRAM_SILENT_MODE
            )
            assert schedule.entity_active == self._GATE

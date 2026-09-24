"""Tests for predefined entity lists."""

from __future__ import annotations

from collections.abc import Iterator
import importlib
import pkgutil
from unittest.mock import patch

from packaging.version import Version

from conftest import make_coordinator_data
import custom_components.luxtronik2 as luxtronik2
from custom_components.luxtronik2.binary_sensor_entities_predefined import (
    BINARY_SENSORS,
)
from custom_components.luxtronik2.const import (
    DeviceKey,
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


class TestSensorPredefined:
    def test_has_entries(self):
        assert len(SENSORS) > 0

    def test_all_have_key(self):
        for s in SENSORS:
            assert s.key is not None
            assert s.luxtronik_key is not None


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

    def test_no_parameter_gate_breaks_on_a_decoded_value(self):
        """A parameter used as a visibility gate may decode to a name.

        `lux_overrides` gives selection datatypes to parameters as their codes
        become known, and such a register then reads "plus_minus" rather than
        1. A gate that assumes a number raises `TypeError` from the entity
        constructor, which aborts `async_setup_entry` for the whole platform:
        that is how #773 lost every number entity, not just the three gated
        ones. Visibility flags themselves are always numeric; parameters are
        the ones that can change type under us, so they are what this sweeps.
        """
        gated = [
            descr
            for descr in _all_descriptions()
            if isinstance(descr.visibility, LuxParameter)
        ]
        # Guard the guard: no parameter gates left means nothing was checked.
        assert gated

        coord = object.__new__(LuxtronikCoordinator)
        coord.data = make_coordinator_data(
            parameters={"ID_Einst_SmartGrid": "plus_minus"}
        )
        with patch.object(LuxtronikCoordinator, "get_value", return_value="plus_minus"):
            for descr in gated:
                assert isinstance(coord.entity_visible(descr), bool), descr.key

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
                LuxParameter.P1030_SMART_GRID_SWITCH,
            )
        ]
        assert offenders == []

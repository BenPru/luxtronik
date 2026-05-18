"""Tests for custom_components.luxtronik.lux_overrides."""

from __future__ import annotations

from luxtronik.calculations import Calculations
from luxtronik.datatypes import HeatpumpCode
from luxtronik.parameters import Parameters
from luxtronik.visibilities import Visibilities


class TestUpdateLuxtronikHeatpumpCodes:
    def test_codes_updated(self):
        from custom_components.luxtronik.lux_overrides import (
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
        from custom_components.luxtronik.lux_overrides import (
            update_Luxtronik_Parameters,
        )

        update_Luxtronik_Parameters()
        # Check that custom parameters are now in the class-level dict
        assert 1148 in Parameters.parameters


class TestIsolateInstanceData:
    def test_instance_data_isolated(self):
        """After isolate_instance_data(), each instance gets its own copy of data dicts."""
        # Reset the guard flag so we can test
        import custom_components.luxtronik.lux_overrides as overrides_module
        from custom_components.luxtronik.lux_overrides import isolate_instance_data

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
        import custom_components.luxtronik.lux_overrides as overrides_module
        from custom_components.luxtronik.lux_overrides import isolate_instance_data

        original_flag = overrides_module._INSTANCE_DATA_ISOLATED
        overrides_module._INSTANCE_DATA_ISOLATED = False

        try:
            isolate_instance_data()
            isolate_instance_data()  # second call should be no-op
            assert overrides_module._INSTANCE_DATA_ISOLATED is True
        finally:
            overrides_module._INSTANCE_DATA_ISOLATED = original_flag

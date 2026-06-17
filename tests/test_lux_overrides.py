"""Tests for custom_components.luxtronik2.lux_overrides."""

from __future__ import annotations

from luxtronik.calculations import Calculations
from luxtronik.datatypes import HeatpumpCode
from luxtronik.parameters import Parameters
from luxtronik.visibilities import Visibilities


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


class TestFrequencyAutomatic:
    from custom_components.luxtronik2.lux_overrides import FrequencyAutomatic

    converter = FrequencyAutomatic("ID_Einst_P155_DHW_Freq", True)

    def test_from_heatpump_zero_is_automatic(self):
        assert self.converter.from_heatpump(0) == 0

    def test_from_heatpump_maps_1_to_21hz(self):
        assert self.converter.from_heatpump(1) == 21

    def test_from_heatpump_maps_101_to_121hz(self):
        assert self.converter.from_heatpump(101) == 121

    def test_to_heatpump_zero_stays_zero(self):
        assert self.converter.to_heatpump(0) == 0

    def test_to_heatpump_maps_21hz_to_1(self):
        assert self.converter.to_heatpump(21) == 1

    def test_to_heatpump_maps_121hz_to_101(self):
        assert self.converter.to_heatpump(121) == 101

    def test_roundtrip_45hz(self):
        raw = self.converter.to_heatpump(45)
        assert self.converter.from_heatpump(raw) == 45

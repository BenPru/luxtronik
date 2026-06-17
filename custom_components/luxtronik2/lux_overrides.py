from copy import deepcopy

from luxtronik.calculations import Calculations
from luxtronik.datatypes import (
    Base,
    Celsius,
    HeatpumpCode,
    MixedCircuitMode,
    Percent,
    Percent2,
    SelectionBase,
    Timestamp,
)
from luxtronik.parameters import Parameters
from luxtronik.visibilities import Visibilities


class MajorMinorVersion(Base):
    """MajorMinorVersion datatype, converts from and to a RBEVersion"""

    datatype_class = "version"

    def from_heatpump(self, value):
        major = value // 100
        minor = value % 100
        return f"{major}.{minor:02d}"


class SecondsToHours(Base):
    """Seconds to hours datatype, converts from and to hours."""

    measurement_type = "hours"

    def from_heatpump(self, value):
        # Round to the nearest half hour so UI values stay in 0.5-hour increments.
        return round(value / 1800) / 2

    def to_heatpump(self, value):
        return int(value * 3600)


class FrequencyAutomatic(Base):
    """Frequency with Automatic mode (0=Auto, 1-101=21-121 Hz)."""

    measurement_type = "frequency"

    def from_heatpump(self, value):
        # 0 stays 0 (Automatic), 1-101 maps to 20-120 Hz
        if value == 0:
            return 0
        return value + 20  # 1 → 21 Hz, 2 → 22 Hz, ..., 101 → 121 Hz

    def to_heatpump(self, value):
        # 0 stays 0 (Automatic), 21-121 Hz maps to 1-101
        if value == 0:
            return 0
        return int(value - 20)  # 21 → 1, 22 → 2, ..., 121 → 101


class PoolPVMode(SelectionBase):
    """PoolPVMode datatype, converts from and to a PoolPVMode"""

    measurement_type = "selection"

    codes = {
        0: "Automatic",
        1: "PV_Off",
        2: "Pool_Party",
        3: "Pool_Holidays",
        4: "Pool_Off",
    }


# Define your new/updated custom parameters in a dictionary
parameters_to_add_update = {
    6: Timestamp("ID_SU_FrkdHz", True),
    7: Timestamp("ID_SU_FrkdBw", True),
    119: PoolPVMode("ID_Ba_Sw_akt", True),
    695: MixedCircuitMode("ID_Ba_Hz_MK1_akt", True),
    696: MixedCircuitMode("ID_Ba_Hz_MK2_akt", True),
    731: Timestamp("ID_SU_FstdHz", True),
    732: Timestamp("ID_SU_FstdBw", True),
    973: Celsius("ID_Einst_BW_max", True),
    980: Percent2("ID_RBE_Einflussfaktor_RT_akt", True),
    1045: FrequencyAutomatic("ID_Einst_P155_DHW_Freq", True),
    1146: Celsius("Extra_DHW_target_temp", True),
    1147: SecondsToHours("Extra_DHW_duration", True),
    1148: Celsius("HEATING_TARGET_TEMP_ROOM_THERMOSTAT", True),
    1159: Percent("Unknown_Parameter_1159", True),
    # Add more as needed
}

calculations_to_add_update = {
    258: MajorMinorVersion("RBE_Version", False),
}


def update_Luxtronik_Parameters():
    Parameters.parameters.update(parameters_to_add_update)  # pyright: ignore[reportCallIssue, reportArgumentType]
    Calculations.calculations.update(calculations_to_add_update)  # pyright: ignore[reportCallIssue, reportArgumentType]


_INSTANCE_DATA_ISOLATED = False


def isolate_instance_data():
    """Patch library classes to use instance-level data dicts.

    The upstream luxtronik library stores parameter/calculation/visibility
    data in class-level dicts shared across all instances.  When multiple
    heat pumps are configured, ``parse()`` on one instance overwrites
    values read by another, causing data mixing (see issue #515).

    This patches ``__init__`` so every new instance gets its own deep copy
    of the class-level dict.
    """
    # No lock needed: called only from synchronous code path (no await),
    # so the event loop cannot preempt between the guard check and flag set.
    global _INSTANCE_DATA_ISOLATED
    if _INSTANCE_DATA_ISOLATED:
        return

    _orig_params_init = Parameters.__init__

    def _params_init(self, *args, **kwargs):
        _orig_params_init(self, *args, **kwargs)
        self.parameters = deepcopy(self.parameters)

    Parameters.__init__ = _params_init

    _orig_calcs_init = Calculations.__init__

    def _calcs_init(self, *args, **kwargs):
        _orig_calcs_init(self, *args, **kwargs)
        self.calculations = deepcopy(self.calculations)

    Calculations.__init__ = _calcs_init

    _orig_vis_init = Visibilities.__init__

    def _vis_init(self, *args, **kwargs):
        _orig_vis_init(self, *args, **kwargs)
        self.visibilities = deepcopy(self.visibilities)

    Visibilities.__init__ = _vis_init

    _INSTANCE_DATA_ISOLATED = True


def update_Luxtronik_HeatpumpCodes():
    # Updated list of Heatpump models
    HeatpumpCode.codes = {
        0: "ERC",
        1: "SW1",
        2: "SW2",
        3: "WW1",
        4: "WW2",
        5: "L1I",
        6: "L2I",
        7: "L1A",
        8: "L2A",
        9: "KSW",
        10: "KLW",
        11: "SWC",
        12: "LWC",
        13: "L2G",
        14: "WZS",
        15: "L1I407",
        16: "L2I407",
        17: "L1A407",
        18: "L2A407",
        19: "L2G407",
        20: "LWC407",
        21: "L1AREV",
        22: "L2AREV",
        23: "WWC1",
        24: "WWC2",
        25: "L2G404",
        26: "WZW",
        27: "L1S",
        28: "L1H",
        29: "L2H",
        30: "WZWD",
        31: "ERC",
        32: "ERC",
        33: "ERC",
        34: "ERC",
        35: "ERC",
        36: "ERC",
        37: "ERC",
        38: "ERC",
        39: "ERC",
        40: "WWB_20",
        41: "LD5",
        42: "LD7",
        43: "SW 37_45",
        44: "SW 58_69",
        45: "SW 29_56",
        46: "LD5 (230V)",
        47: "LD7 (230 V)",
        48: "LD9",
        49: "LD5 REV",
        50: "LD7 REV",
        51: "LD5 REV 230V",
        52: "LD7 REV 230V",
        53: "LD9 REV 230V",
        54: "SW 291",
        55: "LW SEC",
        56: "HMD 2",
        57: "MSW 4",
        58: "MSW 6",
        59: "MSW 8",
        60: "MSW 10",
        61: "MSW 12",
        62: "MSW 14",
        63: "MSW 17",
        64: "MSW 19",
        65: "MSW 23",
        66: "MSW 26",
        67: "MSW 30",
        68: "MSW 4S",
        69: "MSW 6S",
        70: "MSW 8S",
        71: "MSW 10S",
        72: "MSW 12S",
        73: "MSW 16S",
        74: "MSW2-6S",
        75: "MSW4-16",
        76: "LD2AG",
        77: "LD9V",
        78: "MSW3-12",
        79: "MSW3-12S",
        80: "MSW2-9S",
        81: "LW 8",
        82: "LW 12",
        83: "HZ_HMD",
        84: "LW V4",
        85: "LW SEC 2",
        86: "MSW1-4S",
        87: "LP5V",
        88: "LP8V",
    }

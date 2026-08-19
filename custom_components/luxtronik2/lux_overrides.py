from copy import deepcopy
from typing import Final

from luxtronik.calculations import Calculations
from luxtronik.datatypes import (
    Base,
    Bool,
    Celsius,
    Energy,
    HeatpumpCode,
    Kelvin,
    MixedCircuitMode,
    Percent,
    Percent2,
    Power,
    SelectionBase,
    SwitchoffFile,
    Timestamp,
)
from luxtronik.parameters import Parameters
from luxtronik.visibilities import Visibilities

from .const import (
    CONF_CALCULATIONS,
    CONF_PARAMETERS,
    CONF_VISIBILITIES,
    LOGGER,
    PARSED_COUNT_ATTR,
)


class MajorMinorVersion(Base):
    """MajorMinorVersion datatype, converts from and to a RBEVersion"""

    datatype_class = "version"

    def from_heatpump(self, value):
        major = value // 100
        minor = value % 100
        return f"{major}.{minor:02d}"


class Energy2(Base):
    """Energy counter stored in 0.01 kWh units, unlike the library's `Energy`.

    Both scales occur on the same controller - see the energy-input parameters
    in `parameters_to_add_update` for which registers were measured onto this
    one, and why upstream's unit annotation cannot be used to tell them apart.
    """

    measurement_type = "energy"

    def from_heatpump(self, value):
        return value / 100

    def to_heatpump(self, value):
        return int(value * 100)


class SecondsToHours(Base):
    """Seconds to hours datatype, converts from and to hours."""

    measurement_type = "hours"

    def from_heatpump(self, value):
        # Round to the nearest half hour so UI values stay in 0.5-hour increments.
        return round(value / 1800) / 2

    def to_heatpump(self, value):
        return int(value * 3600)


class FrequencyAutomatic(Base):
    """Frequency with Automatic mode (0=Auto, 1-101=20-120 Hz)."""

    measurement_type = "frequency"

    def from_heatpump(self, value):
        # 0 stays 0 (Automatic), 1-101 maps to 20-120 Hz
        if value == 0:
            return 0
        return value + 19  # 1 → 20 Hz, 2 → 21 Hz, ..., 101 → 120 Hz

    def to_heatpump(self, value):
        # 0 stays 0 (Automatic), 20-120 maps to 1-101
        if value == 0:
            return 0
        return int(value - 19)  # 20 Hz → 1, 21 Hz → 2, ..., 120 Hz → 101


class TimeOfDay(Base):
    """TimeOfDay datatype, converts from and to TimeOfDay.

    Always renders "HH:MM". The registers this covers are timer-program
    schedule times, and the heat pump's own controller can only set those to
    a whole minute, so a raw value carrying seconds is a register artefact
    rather than a setting anyone made. Rendering it as "HH:MM:SS" would only
    widen the string past what the consuming text entities allow. The seconds
    are dropped on display only: `to_heatpump` still accepts them, and an
    untouched row is never written back, so the raw value on the device is
    left as it is.
    """

    datatype_class = "timeofday"

    @classmethod
    def from_heatpump(cls, value):
        if not isinstance(value, int):
            return None
        hours = value // 3600
        minutes = (value // 60) % 60

        return f"{hours:02d}:{minutes:02d}"

    @classmethod
    def to_heatpump(cls, value):
        if isinstance(value, int):
            return value
        if not isinstance(value, str):
            return None
        d = [int(v) for v in value.split(":")]

        val = d[0] * 3600 + d[1] * 60
        if len(d) == 3:
            val += d[2]

        return val


class TimerProgram(SelectionBase):
    """TimerProgram datatype, converts from and to list of TimerProgram codes"""

    codes = {
        0: "week",
        1: "5+2",
        2: "days",
    }


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


# Highest index the installed luxtronik library defines per block, captured
# before the overrides below extend those dicts.  Everything at or below this
# index is part of upstream's own definition set and is returned by every
# controller observed, so absence is only ever concluded above it - which is
# exactly where the indices this module adds live.  Measured, not guessed:
# parameters 0..1125 (dense), calculations max 259, visibilities 0..354.
UPSTREAM_MAX_DEFINED_INDEX: Final[dict[str, int]] = {
    CONF_PARAMETERS: max(Parameters.parameters),
    CONF_CALCULATIONS: max(Calculations.calculations),
    CONF_VISIBILITIES: max(Visibilities.visibilities),
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
    993: Celsius("ID_Einst_min_VL_Kuehl", True),
    979: Celsius("ID_Einst_Minimale_Ruecklaufsolltemperatur", True),
    1045: FrequencyAutomatic("ID_Einst_P155_DHW_Freq", True),
    1146: Celsius("Extra_DHW_target_temp", True),
    1147: SecondsToHours("Extra_DHW_duration", True),
    1148: Celsius("HEATING_TARGET_TEMP_ROOM_THERMOSTAT", True),
    1159: Percent("ELECTRICAL_POWER_LIMIT_VALUE", True),
    # Read-only energy counters in 0.01 kWh units, hence Energy2 and no factor
    # on their descriptions. Measured in #734 against the heat-quantity
    # calculations: regressing calc 151/152 on these over 19 snapshots of one
    # unit gives a marginal COP of 6.4 (heating) and 3.8 (DHW) at /100, but
    # 0.64 and 0.38 at /10 - below 1, so impossible for a compressor. Lifetime
    # totals put the same upper bound under 2 at /10 on six further units.
    # Upstream's "kWh/10" note claims /10 for these and is simply wrong here;
    # it also sits on 1059 and calculations 151/152/154, which need /10.
    # 1139 read 0.0 on every unit seen in #734, so it followed its siblings by
    # analogy until the readings below measured it.
    #
    # #752 confirmed the scale directly for the first time: on an LD9 whose
    # controller page was photographed at the moment of the dump, 1136 read
    # 543197 against a displayed 5431.9 kWh and 1137 read 222335 against
    # 2223.3 kWh. The same unit identified 1138 as the pool counter - 113191
    # against a displayed 1131.9 kWh - which had sat unregistered because a
    # unit without a pool reads 0.0 there.
    #
    # A second unit in that issue, an LD5 that cools, settled 1139 the same way
    # - 83272 counts against a displayed 832.7 kWh - and identified 1135 as the
    # cooling heat quantity, 410381 counts against a displayed 4103.8 kWh. 1135
    # had sat unregistered because a unit that never cools reads 0 there.
    1135: Energy2("COOLING_HEAT_AMOUNT", False),
    1136: Energy2("HEAT_ENERGY_INPUT", False),
    1137: Energy2("DHW_ENERGY_INPUT", False),
    1138: Energy2("POOL_ENERGY_INPUT", False),
    1139: Energy2("COOLING_ENERGY_INPUT", False),
    # Auxiliary-heater heat counters. 0.1 kWh per count on a series-3
    # controller, so Energy's own /10 is the whole conversion there (measured
    # against the rated element power in #625), but 0.01 kWh on series 2, where
    # their descriptions take a further /10 - see
    # AUX_HEATER_ENERGY_FACTOR_BY_SERIES in sensor_entities_predefined.py for
    # the per-generation evidence. The split cannot live here: these overrides
    # are applied once per process, while one process can serve two config
    # entries whose heat pumps are different generations. The name of 1059 must
    # stay ID_Waermemenge_ZWE, which is how const.py resolves it.
    1059: Energy("ID_Waermemenge_ZWE", False),
    1140: Energy("SECOND_HEAT_GENERATOR_AMOUNT_COUNTER", False),
    # Bouni/python-luxtronik's in-progress definitions mark these read-only,
    # but our switch/number entities treat them as user-writable by design.
    1158: Bool("POWER_LIMIT_SWITCH", True),
    1175: Bool("THERMAL_POWER_LIMIT_SWITCH", True),
    1176: Power("THERMAL_POWER_LIMIT_HEATING", True),
    1177: Power("THERMAL_POWER_LIMIT_WATER", True),
    # 1178 was previously (wrongly) mapped here as THERMAL_POWER_LIMIT_COOLING;
    # a hardware owner confirmed via the unit's own web interface that cooling
    # is actually 1179, and upstream's naming for 1178 turned out to be a copy
    # of this same guess rather than independent confirmation (see #680). Left
    # unregistered until 1178's real purpose is confirmed.
    1179: Power("THERMAL_POWER_LIMIT_COOLING", True),
    # Add more as needed
}

calculations_to_add_update = {
    258: MajorMinorVersion("RBE_Version", False),
}


def _update_entry(existing, override, *, preserve_existing_name=False):
    """Replace an entry by number while optionally preserving the existing name."""
    name = override.name
    if preserve_existing_name and getattr(existing, "name", None) is not None:
        name = existing.name

    updated = override.__class__(name, override.writeable)
    if hasattr(existing, "value"):
        updated.value = existing.value
    return updated


def update_Luxtronik_Parameters():
    Parameters.parameters.update(parameters_to_add_update)  # pyright: ignore[reportCallIssue, reportArgumentType]
    Calculations.calculations.update(calculations_to_add_update)  # pyright: ignore[reportCallIssue, reportArgumentType]

    # example bulk update of parameter classes for a range of numbers
    Celsius_numbers = [14, 15, 16, 141, 142, 143, 774, 775, 776] + [17, 47, 90, 93, 111]
    update_Luxtronik_Parameter_Classes(Celsius_numbers, Celsius)

    # Kelvin temperature-difference parameters stored as tenths.
    delta_temperature_numbers = [88, 89]
    update_Luxtronik_Parameter_Classes(delta_temperature_numbers, Kelvin)

    # Timer program schedule parameters: mostly TimeOfDay entries, with a
    # handful of TimerProgram mode selectors interspersed. 162-667 holds the
    # heating, mixing, DHW, circulation-pump and pool circuits; the
    # ventilation circuit sits apart at 895 (selector) and 896-955 (times).
    timer_program_numbers = {222, 283, 344, 405, 506, 607, 895}
    schedule_numbers = list(range(162, 668)) + list(range(895, 956))
    time_of_day_numbers = [
        n for n in schedule_numbers if n not in timer_program_numbers
    ]
    update_Luxtronik_Parameter_Classes(time_of_day_numbers, TimeOfDay)
    update_Luxtronik_Parameter_Classes(list(timer_program_numbers), TimerProgram)


def update_Luxtronik_Parameter_Classes(numbers, datatype_class):
    """Update only the class for a list or range of parameter numbers.

    This is intended for parameters that already exist in the upstream library
    and only need their datatype changed, e.g. from Unknown to Celsius.
    """
    if not isinstance(datatype_class, type) or not issubclass(datatype_class, Base):
        raise TypeError("datatype_class must be a Base subclass")

    for number in numbers:
        existing = Parameters.parameters.get(number)
        if existing is None:
            continue

        Parameters.parameters[number] = _update_entry(
            existing,
            datatype_class(getattr(existing, "name", str(number)), existing.writeable),
            preserve_existing_name=True,
        )


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


_PARSE_COUNTS_RECORDED = False
_UNKNOWN_CODE_WARNING_INSTALLED = False
_REPORTED_UNKNOWN_CODES: set[tuple[str, str, object]] = set()


def record_parsed_block_lengths():
    """Patch ``parse()`` to record how many values the controller returned.

    ``parse()`` assigns ``.value`` only for the indices present in the raw
    block; every other definition keeps whatever it had, which for a register
    the unit does not have means ``None`` forever.  The definition dict is
    static, so it cannot answer "does this controller have register N?" - but
    the block length can: register N is present exactly when ``N < length``.

    This is deliberately not inferred from ``.value is None``, because a
    register that IS present also reads ``None`` when its datatype cannot
    decode the raw value (``SelectionBase`` returns ``None`` for a code
    missing from its table, e.g. an unrecognised heat pump model).
    """
    # No lock needed: called only from synchronous code path (no await),
    # so the event loop cannot preempt between the guard check and flag set.
    global _PARSE_COUNTS_RECORDED
    if _PARSE_COUNTS_RECORDED:
        return

    for cls in (Parameters, Calculations, Visibilities):
        _orig_parse = cls.parse

        def _parse(self, raw_data, _orig_parse=_orig_parse):
            setattr(self, PARSED_COUNT_ATTR, len(raw_data))
            return _orig_parse(self, raw_data)

        cls.parse = _parse

    _PARSE_COUNTS_RECORDED = True


def warn_on_unknown_selection_codes():
    """Log once when the controller reports a code this integration cannot decode.

    ``SelectionBase.from_heatpump`` returns ``None`` for any raw value missing
    from its ``codes`` table, which otherwise fails silently - the entity just
    shows an empty state. New heat pump models and new status/switchoff codes
    reintroduce this every time the firmware moves ahead of our tables, so ask
    the user to report it rather than letting it sit undetected.

    Raw ``0`` is skipped for tables that have no entry for ``0``
    (e.g. ``BivalenceLevel``): there it means "slot empty", not "unknown code",
    and it is what a controller reports for anything it has not filled in yet.
    """
    # No lock needed: called only from synchronous code path (no await),
    # so the event loop cannot preempt between the guard check and flag set.
    global _UNKNOWN_CODE_WARNING_INSTALLED
    if _UNKNOWN_CODE_WARNING_INSTALLED:
        return

    _orig_from_heatpump = SelectionBase.from_heatpump

    def _from_heatpump(self, value):
        result = _orig_from_heatpump(self, value)
        if result is None and not (value == 0 and 0 not in self.codes):
            marker = (type(self).__name__, self.name, value)
            if marker not in _REPORTED_UNKNOWN_CODES:
                _REPORTED_UNKNOWN_CODES.add(marker)
                LOGGER.warning(
                    "Heat pump reported code %s for register '%s' (%s), which "
                    "this integration cannot decode - the matching entity will "
                    "have no state. Please report it at "
                    "https://github.com/BenPru/luxtronik/issues so the code "
                    "table can be extended, attaching the integration "
                    "diagnostics download",
                    value,
                    self.name,
                    type(self).__name__,
                )
        return result

    SelectionBase.from_heatpump = _from_heatpump

    _UNKNOWN_CODE_WARNING_INSTALLED = True


def update_Luxtronik_SwitchoffCodes():
    """Replace the pinned library's incomplete/shifted switchoff code table.

    luxtronik 0.3.14 knows only codes 1-9, and misnumbers three of them. It was
    released in June 2022 and is still the newest release on PyPI, so two merged
    upstream fixes never reached any user: `19: PV max` (issue #89, March 2023)
    and Bouni/python-luxtronik#186 (November 2024), which added 10-25 and
    renumbered 1/2/4 to 0/1/2. Without this override, every controller reporting
    one of the perfectly ordinary codes 10-25 (flow rate, low pressure pause,
    LPC, restart, ...) decodes to `None` and triggers the "please report it"
    warning from `warn_on_unknown_selection_codes()`.

    PR #186 derived the corrected numbering by reading the strings the heat pump
    itself displays and cross-checking them against the manual; issue #185 that
    prompted it confirmed `22` the same way, by lining the five register slots up
    with the five timestamps in the controller's own log. That is also where the
    numbering used by the `switchoff_reason` sensor's translations comes from, so
    both readings of the same history now agree.

    `24: LPC` is upstream's own uncertain guess (possibly "limit power
    consumption") and is deliberately left as the bare abbreviation.
    """
    SwitchoffFile.codes = {
        0: "heatpump error",
        1: "system error",
        2: "operation mode second heat generator",
        3: "evu lock",
        # 4 is left unassigned upstream: the old table's entry for it moved to 2.
        5: "air defrost",
        6: "maximal usage temperature",
        7: "minimal usage temperature",
        8: "lower usage limit",
        9: "no request",
        10: "external energy source",
        11: "flow rate",
        12: "low pressure pause",
        13: "superheating pause",
        14: "inverter pause",
        15: "desuperheater pause",
        16: "operation mode for switching over",
        17: "other shutdown",
        18: "min. flow cooling",
        19: "PV max",
        20: "hot gas pause",
        21: "overheating hot gas pause",
        22: "no request",
        23: "min. heat source out cooling",
        24: "LPC",
        25: "restart",
        # 27 is not in upstream's table: read off an HMD2 display, whose
        # "Abschaltungen" log showed "Aanvoer max." for the same timestamps the
        # switchoff history reported 27 (confirmed against a run that stopped
        # at 66.0 degrees flow and resumed two minutes later).
        27: "maximum flow temperature",
    }


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

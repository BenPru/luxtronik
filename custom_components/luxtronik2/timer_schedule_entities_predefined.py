"""Predefined timer-program schedule text entities.

Covers the DHW (Bw), heating (Hkr), ventilation (Luf) and circulation pump
(ZIP) circuits, plus the inverter silent mode (see `_SILENT_MODE_ENTITIES`). The remaining timer-program circuits (Mk1/Mk2/Mk3/Swb) follow
the DHW and heating pattern and need one `_TimerCircuit` instance plus translations
each; see the "lux-timer-program-parameter-layout" memory for their
selector/prefix values.

The ventilation circuit stores its windows differently (#789): each
register 896-955 packs a whole start-end window (`lux_overrides.TimeOfDay2`),
and every schedule shape has *two* blocks of three rows - block 0 is the
schedule page the controller marks with a sun symbol (day mode), block 1 the
page with a moon symbol (night mode), read off a KHZ LWC 60. The two blocks
are modelled as two circuits sharing one selector, so each shape yields a
day and a night entity.
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from homeassistant.const import EntityCategory

from .const import (
    AIR_INVERTER_MODELS,
    DeviceKey,
    LuxCalculation,
    LuxParameter,
    SensorKey as SK,
)
from .model import EntityActiveCondition, LuxtronikTimerScheduleTextDescription


@dataclass(frozen=True)
class _TimerCircuit:
    """Metadata for one timer-program circuit's schedule parameters.

    The heat pump's mode selector picks one of three schedule shapes, each
    backed by its own set of firmware parameters (the raw prefix each of
    these covers, e.g. "ID_Einst_SuBwWO"):

    - ``same_schedule_prefix`` ("WO" in the firmware): one schedule applies
      every day of the week.
    - ``weekday_weekend_prefix`` ("25"): one schedule for weekdays, a
      separate one for the weekend.
    - ``per_day_prefix`` ("TG"/"Tg", German "täglich"): a separate,
      independently editable schedule for each individual day of the week.

    Each prefix is also the parameter-name prefix under which the firmware
    exposes the actual start/end times. The name shape that follows it is
    decided per circuit by `name_builder` below (DHW and heating share
    ``<prefix>_zeit_<row>_<slot>``, see `_row_names_row_slot`; ventilation
    packs both halves into one register, see `_row_names_packed`); ``row``
    is the schedule slot within a day (0-based, up to `rows` per day) and
    ``column`` is 0 for the same-schedule block, 0/1 for weekday/weekend,
    and 0-6 for Sunday-Saturday.
    """

    #: Raw parameter name of the mode selector that picks which of the three
    #: schedule shapes below is actually active on the device (its value is
    #: one of "week", "5+2", or "days").
    mode_selector_name: str
    #: Number of independent start/end time slots available per day for
    #: this circuit (3 or 5, depending on circuit -- see the
    #: "lux-timer-program-parameter-layout" memory).
    rows: int
    same_schedule_prefix: str
    weekday_weekend_prefix: str
    per_day_prefix: str
    #: Builds the register names of one block, one tuple per row: a
    #: ``(start_name, end_name)`` pair, or a 1-tuple for a register that
    #: packs the whole window (see `LuxtronikTimerScheduleTextDescription`).
    #: The layout is per circuit so a circuit with another naming scheme
    #: can supply its own. Deliberately has no default: a default here would
    #: make it a class attribute and bind as a method on access.
    name_builder: Callable[[str, int, int], tuple[tuple[str] | tuple[str, str], ...]]
    device_key: DeviceKey
    #: A declarative existence gate for the whole circuit, see
    #: `LuxtronikEntityDescription.entity_active`. A gated circuit also
    #: names its mode selector as `selector_key`: `entity_active` requires the
    #: entity's own register to be returned (#738), and a schedule block has
    #: no single register of its own.
    selector_key: LuxParameter = LuxParameter.UNSET
    entity_active: tuple[EntityActiveCondition, ...] = ()


def _row_names_row_slot(
    prefix: str, rows: int, col: int
) -> tuple[tuple[str, str], ...]:
    """Build the (start_name, end_name) pairs for a `<row>_<slot>` block.

    Matches the firmware's ``<prefix>_zeit_<row>_<slot>`` numbering, where
    slot is ``2*col`` (start) / ``2*col + 1`` (end). Used by the DHW and
    heating circuits.
    """
    return tuple(
        (f"{prefix}_zeit_{row}_{2 * col}", f"{prefix}_zeit_{row}_{2 * col + 1}")
        for row in range(rows)
    )


def _row_names_packed(
    block: int, prefix: str, rows: int, col: int
) -> tuple[tuple[str] | tuple[str, str], ...]:
    """Build the 1-tuples of a ``<prefix>_zeit_<block>_<row>_<2*col>`` block.

    Ventilation names (896-955) keep the ``2*col`` slot numbering of the
    two-register layout although a single register now holds the whole
    window - the odd slots simply do not exist. ``block`` selects the day
    (0) or night (1) schedule; bind it with `functools.partial` to get a
    `_TimerCircuit.name_builder`.
    """
    return tuple((f"{prefix}_zeit_{block}_{row}_{2 * col}",) for row in range(rows))


# The per-day ("TG") columns run Sunday (0) to Saturday (6), not Monday-first
# (#842): corpus units with a weekend pattern hold it in columns 0 and 6, and
# a WZS 81 H/K owner matched every column against the controller display.
_FIRMWARE_DAY_ORDER = (
    "SUNDAY",
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
)


def _per_day_keys(circuit: str) -> tuple[tuple[SK, int], ...]:
    """Pair a circuit's per-day entity keys with their firmware column."""
    return tuple(
        (SK[f"TIMER_{circuit}_SCHEDULE_{day}"], column)
        for column, day in enumerate(_FIRMWARE_DAY_ORDER)
    )


# Numbers verified against a real diagnostics dump for parameters 162-667.
_DHW_CIRCUIT = _TimerCircuit(
    mode_selector_name="ID_Einst_SUBW_akt2",
    rows=5,
    same_schedule_prefix="ID_Einst_SuBwWO",
    weekday_weekend_prefix="ID_Einst_SuBw25",
    per_day_prefix="ID_Einst_SuBwTG",
    name_builder=_row_names_row_slot,
    device_key=DeviceKey.domestic_water,
)

_DHW_WEEKDAYS = _per_day_keys("DHW")

_HEATING_CIRCUIT = _TimerCircuit(
    mode_selector_name="ID_Einst_SuHkr_akt",
    rows=3,
    # `W0` ends in a digit zero and `TG` is uppercase: these are the upstream
    # library's literal names and differ from the DHW spellings.
    same_schedule_prefix="ID_Einst_SuHkrW0",
    weekday_weekend_prefix="ID_Einst_SuHkr25",
    per_day_prefix="ID_Einst_SuHkrTG",
    name_builder=_row_names_row_slot,
    device_key=DeviceKey.heating,
)

_HEATING_WEEKDAYS = _per_day_keys("HEATING")


# Verified against the diagnostics dump and controller photos of a KHZ LWC 60
# with a ventilation module (#789): selector 895, windows 896-955. Both
# circuits read the same selector; the mode ("week"/"5+2"/"days") applies to
# the day and the night block alike.
_VENTILATION_DAY_CIRCUIT = _TimerCircuit(
    mode_selector_name="ID_Einst_SuLuf_akt",
    rows=3,
    # Mixed-case `Wo`/`Tg`: again the upstream library's literal spellings.
    same_schedule_prefix="ID_Einst_SuLufWo",
    weekday_weekend_prefix="ID_Einst_SuLuf25",
    per_day_prefix="ID_Einst_SuLufTg",
    name_builder=partial(_row_names_packed, 0),
    device_key=DeviceKey.ventilation,
)

_VENTILATION_NIGHT_CIRCUIT = _TimerCircuit(
    mode_selector_name="ID_Einst_SuLuf_akt",
    rows=3,
    same_schedule_prefix="ID_Einst_SuLufWo",
    weekday_weekend_prefix="ID_Einst_SuLuf25",
    per_day_prefix="ID_Einst_SuLufTg",
    name_builder=partial(_row_names_packed, 1),
    device_key=DeviceKey.ventilation,
)

_VENTILATION_DAY_WEEKDAYS = _per_day_keys("VENTILATION_DAY")

_VENTILATION_NIGHT_WEEKDAYS = _per_day_keys("VENTILATION_NIGHT")


# Verified against the diagnostics corpus: selector 506 and windows 507-606
# hold "week"/"5+2" and real times on the units that program them. The windows
# are release times - "the times in which the circulation pump should run"
# (Lux 2.0/2.1 manual 83055200o, p. 28), which four owners confirmed in #310.
# The controller shows its circulation menu only while "Warmwasser 2" (P0085)
# is ZIP rather than BLP, and the entities follow it.
_CIRCULATION_CIRCUIT = _TimerCircuit(
    mode_selector_name="ID_Einst_SuZIP_akt",
    rows=5,
    # Mixed-case `Wo`/`Tg`, as on ventilation.
    same_schedule_prefix="ID_Einst_SuZIPWo",
    weekday_weekend_prefix="ID_Einst_SuZIP25",
    per_day_prefix="ID_Einst_SuZIPTg",
    name_builder=_row_names_row_slot,
    device_key=DeviceKey.domestic_water,
    selector_key=LuxParameter.P0506_TIMER_PROGRAM_CIRCULATION,
    entity_active=((LuxParameter.P0085_DHW_CHARGING_PUMP, "!= 1"),),
)

_CIRCULATION_WEEKDAYS = _per_day_keys("CIRCULATION")


# Inverter silent mode (#882, 1092 selector, 1093-1113 windows): a single
# block of 21 packed `TimeOfDay2` registers, seven days of three windows,
# day by day. No program shape has a block of its own - the controller keeps
# "week" as a copy in every day: a Hybrox 5 (LP5V) and pump 340716_0104
# (V3.92.1) with one 20:00-07:00 window held it in slots 0, 3, ..., 18, and
# an LP16V (V3.92.3) held 22:30-05:30 as 00:00-05:30 / 22:30-00:00 in rows 0
# and 1 of every day. So each shape reads one day and writes every day it
# covers, and the controller runs on the current day's block whatever the
# program. The days are taken to run Sunday-first like every other
# circuit's per-day columns (#842); unconfirmed for this block until a dump
# in "5+2" with distinct weekend windows shows them in days 0 and 6.
_SILENT_MODE_ROWS = 3
_SILENT_MODE_WEEKDAYS = (1, 2, 3, 4, 5)
_SILENT_MODE_WEEKEND = (6, 0)


def _silent_mode_day(day: int) -> tuple[tuple[str], ...]:
    """Return the three packed window registers of one silent-mode day."""
    return tuple(
        (f"ID_Einst_SilenceTimer_{day * _SILENT_MODE_ROWS + row}",)
        for row in range(_SILENT_MODE_ROWS)
    )


def _silent_mode_schedule(
    key: SK, active_mode: str, days: tuple[int, ...]
) -> LuxtronikTimerScheduleTextDescription:
    """Build a silent-mode schedule entity that reads ``days[0]`` and writes all."""
    return LuxtronikTimerScheduleTextDescription(
        key=key,
        device_key=DeviceKey.heatpump,
        entity_category=EntityCategory.CONFIG,
        mode_selector_name="ID_Einst_SuSilence",
        # The selector stands in as the entity's own register (#738).
        luxtronik_key=LuxParameter.P1092_TIMER_PROGRAM_SILENT_MODE,
        entity_active=((LuxCalculation.C0078_MODEL_CODE, f"in {AIR_INVERTER_MODELS}"),),
        active_mode=active_mode,
        row_names=_silent_mode_day(days[0]),
        mirror_row_names=tuple(_silent_mode_day(day) for day in days[1:]),
    )


_SILENT_MODE_ENTITIES = [
    _silent_mode_schedule(
        SK.TIMER_SILENT_MODE_SCHEDULE_WEEK, "week", (0, 1, 2, 3, 4, 5, 6)
    ),
    _silent_mode_schedule(
        SK.TIMER_SILENT_MODE_SCHEDULE_WEEKDAY, "5+2", _SILENT_MODE_WEEKDAYS
    ),
    _silent_mode_schedule(
        SK.TIMER_SILENT_MODE_SCHEDULE_WEEKEND, "5+2", _SILENT_MODE_WEEKEND
    ),
] + [
    _silent_mode_schedule(key, "days", (column,))
    for key, column in _per_day_keys("SILENT_MODE")
]


def _build_circuit_entities(
    circuit: _TimerCircuit,
    week_key: SK,
    weekday_key: SK,
    weekend_key: SK,
    day_keys: tuple[tuple[SK, int], ...],
) -> list[LuxtronikTimerScheduleTextDescription]:
    """Build the week/weekday/weekend/daily schedule entities for one circuit."""
    entities = [
        LuxtronikTimerScheduleTextDescription(
            key=week_key,
            device_key=circuit.device_key,
            entity_category=EntityCategory.CONFIG,
            mode_selector_name=circuit.mode_selector_name,
            luxtronik_key=circuit.selector_key,
            entity_active=circuit.entity_active,
            active_mode="week",
            row_names=circuit.name_builder(
                circuit.same_schedule_prefix, circuit.rows, 0
            ),
        ),
        LuxtronikTimerScheduleTextDescription(
            key=weekday_key,
            device_key=circuit.device_key,
            entity_category=EntityCategory.CONFIG,
            mode_selector_name=circuit.mode_selector_name,
            luxtronik_key=circuit.selector_key,
            entity_active=circuit.entity_active,
            active_mode="5+2",
            row_names=circuit.name_builder(
                circuit.weekday_weekend_prefix, circuit.rows, 0
            ),
        ),
        LuxtronikTimerScheduleTextDescription(
            key=weekend_key,
            device_key=circuit.device_key,
            entity_category=EntityCategory.CONFIG,
            mode_selector_name=circuit.mode_selector_name,
            luxtronik_key=circuit.selector_key,
            entity_active=circuit.entity_active,
            active_mode="5+2",
            row_names=circuit.name_builder(
                circuit.weekday_weekend_prefix, circuit.rows, 1
            ),
        ),
    ]
    entities.extend(
        LuxtronikTimerScheduleTextDescription(
            key=day_key,
            device_key=circuit.device_key,
            entity_category=EntityCategory.CONFIG,
            mode_selector_name=circuit.mode_selector_name,
            luxtronik_key=circuit.selector_key,
            entity_active=circuit.entity_active,
            active_mode="days",
            row_names=circuit.name_builder(
                circuit.per_day_prefix, circuit.rows, day_index
            ),
        )
        for day_key, day_index in day_keys
    )
    return entities


TIMER_SCHEDULE_ENTITIES: list[LuxtronikTimerScheduleTextDescription] = (
    _build_circuit_entities(
        _DHW_CIRCUIT,
        week_key=SK.TIMER_DHW_SCHEDULE_WEEK,
        weekday_key=SK.TIMER_DHW_SCHEDULE_WEEKDAY,
        weekend_key=SK.TIMER_DHW_SCHEDULE_WEEKEND,
        day_keys=_DHW_WEEKDAYS,
    )
    + _build_circuit_entities(
        _HEATING_CIRCUIT,
        week_key=SK.TIMER_HEATING_SCHEDULE_WEEK,
        weekday_key=SK.TIMER_HEATING_SCHEDULE_WEEKDAY,
        weekend_key=SK.TIMER_HEATING_SCHEDULE_WEEKEND,
        day_keys=_HEATING_WEEKDAYS,
    )
    + _build_circuit_entities(
        _VENTILATION_DAY_CIRCUIT,
        week_key=SK.TIMER_VENTILATION_DAY_SCHEDULE_WEEK,
        weekday_key=SK.TIMER_VENTILATION_DAY_SCHEDULE_WEEKDAY,
        weekend_key=SK.TIMER_VENTILATION_DAY_SCHEDULE_WEEKEND,
        day_keys=_VENTILATION_DAY_WEEKDAYS,
    )
    + _build_circuit_entities(
        _VENTILATION_NIGHT_CIRCUIT,
        week_key=SK.TIMER_VENTILATION_NIGHT_SCHEDULE_WEEK,
        weekday_key=SK.TIMER_VENTILATION_NIGHT_SCHEDULE_WEEKDAY,
        weekend_key=SK.TIMER_VENTILATION_NIGHT_SCHEDULE_WEEKEND,
        day_keys=_VENTILATION_NIGHT_WEEKDAYS,
    )
    + _build_circuit_entities(
        _CIRCULATION_CIRCUIT,
        week_key=SK.TIMER_CIRCULATION_SCHEDULE_WEEK,
        weekday_key=SK.TIMER_CIRCULATION_SCHEDULE_WEEKDAY,
        weekend_key=SK.TIMER_CIRCULATION_SCHEDULE_WEEKEND,
        day_keys=_CIRCULATION_WEEKDAYS,
    )
    + _SILENT_MODE_ENTITIES
)

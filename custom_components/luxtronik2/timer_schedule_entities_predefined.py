"""Predefined timer-program schedule text entities.

Covers the DHW (Bw) and heating (Hkr) circuits. The remaining timer-program
circuits (Mk1/Mk2/ZIP/Swb) follow the same pattern and need one
`_TimerCircuit` instance plus translations each; see the
"lux-timer-program-parameter-layout" memory for their selector/prefix values.
"""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.const import EntityCategory

from .const import DeviceKey, SensorKey as SK
from .model import LuxtronikTimerScheduleTextDescription


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

    Each prefix is also the parameter-name prefix: the firmware exposes the
    actual start/end times as ``<prefix>_zeit_<row>_<slot>``, where ``row``
    is the schedule slot within a day (0-based, up to `rows` per day) and
    ``slot`` is an even number for the start time and that same number + 1
    for its matching end time. For the weekday/weekend and per-day blocks,
    ``slot`` also encodes which day-group the row belongs to
    (``slot = 2 * column``, where ``column`` is 0/1 for weekday/weekend, or
    0-6 for Monday-Sunday) -- see `_row_names_row_slot` below.
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
    #: Builds the (start_name, end_name) pairs for one block. Circuits do not
    #: share a single naming scheme, so the layout is per circuit -- see the
    #: two `_row_names_*` functions. Deliberately has no default: a default
    #: here would make it a class attribute and bind as a method on access.
    name_builder: Callable[[str, int, int], tuple[tuple[str, str], ...]]
    device_key: DeviceKey


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

_DHW_WEEKDAYS: tuple[tuple[SK, int], ...] = (
    (SK.TIMER_DHW_SCHEDULE_MONDAY, 0),
    (SK.TIMER_DHW_SCHEDULE_TUESDAY, 1),
    (SK.TIMER_DHW_SCHEDULE_WEDNESDAY, 2),
    (SK.TIMER_DHW_SCHEDULE_THURSDAY, 3),
    (SK.TIMER_DHW_SCHEDULE_FRIDAY, 4),
    (SK.TIMER_DHW_SCHEDULE_SATURDAY, 5),
    (SK.TIMER_DHW_SCHEDULE_SUNDAY, 6),
)

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

_HEATING_WEEKDAYS: tuple[tuple[SK, int], ...] = (
    (SK.TIMER_HEATING_SCHEDULE_MONDAY, 0),
    (SK.TIMER_HEATING_SCHEDULE_TUESDAY, 1),
    (SK.TIMER_HEATING_SCHEDULE_WEDNESDAY, 2),
    (SK.TIMER_HEATING_SCHEDULE_THURSDAY, 3),
    (SK.TIMER_HEATING_SCHEDULE_FRIDAY, 4),
    (SK.TIMER_HEATING_SCHEDULE_SATURDAY, 5),
    (SK.TIMER_HEATING_SCHEDULE_SUNDAY, 6),
)


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
)

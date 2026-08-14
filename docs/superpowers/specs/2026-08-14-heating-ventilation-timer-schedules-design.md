# Heating and ventilation timer-program schedules

Date: 2026-08-14

## Goal

Extend the existing timer-program schedule text entities — today wired up for
the DHW circuit only — to the heating circuit and the ventilation module.

The DHW implementation was built as a deliberate pilot (see the module
docstring of `timer_schedule_entities_predefined.py`). This spec rolls it out
to two more circuits and fixes the one behaviour that only becomes wrong once
more than one circuit exists.

Out of scope: the mixing circuits (`SuMk1` 283, `SuMk2` 344), the circulation
pump (`SuZIP` 506), the pool (`SuSwb` 607), and the combined `SuAll` block
(162-221). They follow the same pattern and can be added later at the cost of
one `_TimerCircuit` instance plus translations each.

## Circuits

| | Heating | Ventilation |
|---|---|---|
| Mode selector | `ID_Einst_SuHkr_akt` (222) | `ID_Einst_SuLuf_akt` (895) |
| Rows per day | 3 | 3 |
| Week prefix | `ID_Einst_SuHkrW0` | `ID_Einst_SuLufWo` |
| Weekday/weekend prefix | `ID_Einst_SuHkr25` | `ID_Einst_SuLuf25` |
| Per-day prefix | `ID_Einst_SuHkrTG` | `ID_Einst_SuLufTg` |
| Parameter range | 223-282 | 896-955 |
| Device | `DeviceKey.heating` | `DeviceKey.ventilation` |

The prefix spellings are the upstream library's literal parameter names and are
inconsistent between circuits on purpose: heating uses `W0` with a **digit
zero** and uppercase `TG`, ventilation uses `Wo`/`Tg`, DHW uses `WO`/`TG`.
They must be copied verbatim, never derived.

Device gating is already generic: `coordinator.device_key_active` returns
`True` unconditionally for `DeviceKey.heating` and defers to `has_ventilation`
for `DeviceKey.ventilation`, and `_active_schedule_descriptions` already calls
`entity_active`. No coordinator change is needed.

Each circuit yields 10 entities: week, weekday, weekend, and one per weekday
Monday-Sunday. 20 new entities in total.

## Parameter-name layouts

The two circuits do **not** share a naming scheme.

Heating (same as DHW), `<prefix>_zeit_<row>_<slot>`:

```
slot = 2 * col      -> start time
slot = 2 * col + 1  -> end time
col  = 0            for the week block
col  = 0 | 1        for weekday | weekend
col  = 0..6         for Monday..Sunday
```

Ventilation, `<prefix>_zeit_<0|1>_<row>_<2*col>`:

```
leading index 0 -> start time, 1 -> end time
middle index    -> row (0..2)
trailing index  -> 2 * col, same col meaning as above
```

The start and end blocks are interleaved in the parameter numbering rather
than adjacent: `SuLufWo` starts live at 896-898 and their ends at 926-928;
`SuLufTg` starts at 905-925, ends at 935-955. Nothing in the integration
depends on the numbering — only on the names — but the split is why the
per-prefix number ranges overlap when listed.

## Unverified assumptions

Both are inferred from the naming pattern, not from a diagnostics dump, and
are shipped as such by explicit decision. Each gets a code comment saying so.

1. `ID_Einst_SuLuf_akt` (895) uses the same `TimerProgram` codes as the other
   selectors: `0 = week`, `1 = 5+2`, `2 = days`.
2. In the ventilation names, the leading index is start(0)/end(1).

If a dump later contradicts either, the correction is local: the datatype
override for 895, or the ventilation name builder.

## Changes

### `lux_overrides.py`

The timer datatype overrides currently cover 162-667 only, so every
ventilation time parameter is still `Unknown` and would surface as raw
seconds. Extend them:

- add `895` to `timer_program_numbers` (gets `TimerProgram`)
- add `range(896, 956)` to the `TimeOfDay` number list

Heating needs nothing here; 222 and 223-282 are already covered.

### `timer_schedule_entities_predefined.py`

`_row_names` hardcodes the heating/DHW layout. Give `_TimerCircuit` a
`name_builder` field holding one of two functions with the signature
`(prefix, rows, col) -> tuple[tuple[str, str], ...]`:

- `_row_names_row_slot` — the existing body, used by DHW and heating
- `_row_names_block_row_col` — the ventilation layout

`_build_circuit_entities` calls `circuit.name_builder(...)` instead of
`_row_names(...)` and is otherwise unchanged, as is
`LuxtronikTimerScheduleTextDescription`.

Add `_HEATING_CIRCUIT` and `_VENTILATION_CIRCUIT` instances plus their
weekday key tuples, and extend `TIMER_SCHEDULE_ENTITIES` with their built
entities. Update the module docstring: the pilot is over, and what remains
unrolled is the mixing/ZIP/pool set.

### `const.py`

20 new `SensorKey` members following the existing DHW naming:
`TIMER_HEATING_SCHEDULE_{WEEK,WEEKDAY,WEEKEND,MONDAY..SUNDAY}` and
`TIMER_VENTILATION_SCHEDULE_{...}`, with string values matching the member
name in lowercase.

### `translations/{en,de,nl,cs,pl}.json`

20 keys each under `entity.text`, mirroring the DHW wording, e.g.
`"Heating Timer Schedule (Monday)"` / `"Heizung-Zeitschaltplan (Montag)"` /
`"Verwarming tijdschema (maandag)"`. All five files stay in lockstep.

### `text.py` — per-circuit bail

`_active_schedule_descriptions` returns `None` for the entire pass as soon as
any selector it consults reads back `None`, which suppresses the add/remove
pass for every circuit at once. With DHW alone that was equivalent to "this
circuit is unreadable". With three circuits it is not: an undecodable
ventilation selector — precisely the assumption shipped unverified above —
would freeze the heating and DHW entities too.

Make the bail per-circuit: collect the `mode_selector_name`s that failed to
read this poll and skip only the descriptions belonging to them, computing the
other circuits' active blocks normally. The whole-pass `None` return stays for
`data is None`, which genuinely carries no information about any circuit.

Nothing else in `text.py` changes: the registry enable/disable sync, the write
batching in `async_set_value`, and the `available` property are all already
keyed per description via `mode_selector_name`.

## Testing

Extends `tests/test_text.py`. All existing DHW tests must pass unchanged.

- **Name generation, heating**: `_row_names_row_slot` output spot-checked
  against real upstream names, e.g. week row 0 -> `ID_Einst_SuHkrW0_zeit_0_0`
  / `..._zeit_0_1`; per-day row 2, Sunday end -> `ID_Einst_SuHkrTG_zeit_2_13`.
- **Name generation, ventilation**: e.g. week row 0 ->
  `ID_Einst_SuLufWo_zeit_0_0_0` / `ID_Einst_SuLufWo_zeit_1_0_0`; per-day row 1,
  Wednesday end -> `ID_Einst_SuLufTg_zeit_1_1_4`.
- **Every generated name exists upstream**: assert that each name in every
  description's `row_names` resolves to a defined parameter, which catches a
  mistyped prefix (`W0` vs `WO`) for all three circuits at once.
- **Device gating**: with `has_ventilation` False, no ventilation description
  is returned by `_active_schedule_descriptions`; with it True and the
  selector reading `week`, exactly the ventilation week block appears.
- **Per-circuit bail**: with the ventilation selector unreadable and the DHW
  and heating selectors reading `week`, the pass still returns both of their
  week blocks and no ventilation block — the regression this rollout forces.
- **Datatype overrides**: after `update_Luxtronik_Parameters()`, parameter 895
  is `TimerProgram` and 896/955 are `TimeOfDay`.

Coverage must not regress; run the full suite with `--cov` scoped at the
package root.

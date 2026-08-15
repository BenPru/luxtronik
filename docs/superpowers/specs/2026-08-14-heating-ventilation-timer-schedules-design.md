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

Each circuit yields 10 text entities: week, weekday, weekend, and one per
weekday Monday-Sunday. 20 new text entities in total.

## Program mode selects

DHW also exposes its mode selector as a select entity (`SK.TIMER_DHW_PROGRAM`
-> `LuxParameter.P0405_TIMER_PROGRAM_DHW` in `select_entities_predefined.py`).
Without the equivalents, a user can see the new schedules but cannot switch
which program is active from Home Assistant - and which schedule entities
exist at all is driven by exactly that selector. So both circuits get one too:

| | Heating | Ventilation |
|---|---|---|
| Sensor key | `SK.TIMER_HEATING_PROGRAM` | `SK.TIMER_VENTILATION_PROGRAM` |
| Lux parameter | `P0222_TIMER_PROGRAM_HEATING` | `P0895_TIMER_PROGRAM_VENTILATION` |
| Device | `DeviceKey.heating` | `DeviceKey.ventilation` |

Both reuse the existing `timer_program_options` /
`TIMER_PROGRAM_RAW_OPTIONS` mapping (`week` / `weekday_weekend` -> `"5+2"` /
`daily` -> `"days"`) and `EntityCategory.CONFIG`, exactly like the DHW one.
They need the same `name` + `state` translation shape as
`entity.select.timer_dhw_program` in all five languages.

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
name in lowercase, plus `TIMER_HEATING_PROGRAM` and
`TIMER_VENTILATION_PROGRAM`.

Two new `LuxParameter` members alongside `P0405_TIMER_PROGRAM_DHW`:
`P0222_TIMER_PROGRAM_HEATING = "parameters.ID_Einst_SuHkr_akt"` and
`P0895_TIMER_PROGRAM_VENTILATION = "parameters.ID_Einst_SuLuf_akt"`.

### `select_entities_predefined.py`

Two `LuxtronikSelectEntityDescription` entries appended to `SELECT_ENTITIES`,
copying the `SK.TIMER_DHW_PROGRAM` entry's shape with the keys, parameters and
devices from the table above.

### `translations/{en,de,nl,cs,pl}.json`

20 keys each under `entity.text`, mirroring the DHW wording, e.g.
`"Heating Timer Schedule (Monday)"` / `"Heizung-Zeitschaltplan (Montag)"` /
`"Verwarming tijdschema (maandag)"`, and 2 keys each under `entity.select`
with the same `name` + `state` shape as `timer_dhw_program`. All five files
stay in lockstep.

### `text.py` — per-circuit bail

`_active_schedule_descriptions` returns `None` for the entire pass as soon as
any selector it consults reads back `None`, which suppresses the add/remove
pass for every circuit at once. With DHW alone that was equivalent to "this
circuit is unreadable". With three circuits it is not: an undecodable
ventilation selector — precisely the assumption shipped unverified above —
would freeze the heating and DHW entities too.

Make the bail per-circuit. `_active_schedule_descriptions` returns
`tuple[list[description], set[str]] | None`: the active blocks, plus the
`mode_selector_name`s that could not be read this poll. `None` stays reserved
for `data is None`, which genuinely carries no information about any circuit.

"Skipping" an unreadable circuit means more than leaving it out of the active
list — its live entities must also survive. `async_apply` derives the frozen
keys (every description whose selector is unreadable) and excludes them from
both `to_remove` and the `_disable_inactive` pass, so an unreadable circuit is
left exactly as it is while the others are synced normally. Without that, the
per-circuit skip would cause the very teardown the whole-pass bail exists to
prevent.

Nothing else in `text.py` changes: `_enable_active`, the write batching in
`async_set_value`, and the `available` property already work per description.
An entity of an unreadable circuit reports unavailable (its selector reads
`None`, which never equals `active_mode`) while keeping its registry entry and
history — which is the intended behaviour.

This changes the helper's return type, so the private `_call` helper in
`TestActiveScheduleDescriptions` unwraps the tuple; its assertions and every
other existing DHW test stay as they are.

## Testing

Extends `tests/test_text.py`. All existing DHW tests keep their assertions;
the only edit permitted to them is unwrapping the new tuple return in the
`TestActiveScheduleDescriptions._call` helper.

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
- **Per-circuit bail**: with one circuit's selector unreadable and the others
  reading `week`, the pass still returns the readable circuits' week blocks
  and reports the unreadable selector in the second element of the tuple.
- **Frozen circuit is left alone**: a live entity of a circuit whose selector
  turns unreadable is neither removed from the state machine nor written to
  the registry, while a second, readable circuit still swaps its blocks in the
  same pass.
- **Datatype overrides**: after `update_Luxtronik_Parameters()`, parameter 895
  is `TimerProgram` and 896/955 are `TimeOfDay`.
- **Program selects** (`tests/test_select.py`): the two new descriptions are
  present in `SELECT_ENTITIES` with the expected `luxtronik_key`, device and
  `raw_option_map`, so a wrong parameter string is caught at CI time.

Coverage must not regress; run the full suite with `--cov` scoped at the
package root.

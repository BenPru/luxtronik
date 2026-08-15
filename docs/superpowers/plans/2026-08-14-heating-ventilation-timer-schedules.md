# Heating and Ventilation Timer Schedules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Roll the existing DHW timer-program entities out to the heating circuit and the ventilation module — 20 schedule text entities plus 2 program-mode selects.

**Architecture:** The generic machinery already exists in `text.py` and is driven entirely by the `TIMER_SCHEDULE_ENTITIES` table in `timer_schedule_entities_predefined.py`. Two circuits get added to that table; ventilation needs a second parameter-name builder because its firmware names put the start/end index first. `text.py` itself changes only to make its "selector unreadable" bail per-circuit instead of per-pass, which only becomes wrong once more than one circuit exists. `lux_overrides.py` gains the datatype coverage for the ventilation parameter block, which sits outside the currently-covered 162-667 range.

**Tech Stack:** Python 3.14, Home Assistant custom integration, `luxtronik` PyPI client library, pytest + pytest-homeassistant-custom-component, ruff, basedpyright.

**Spec:** `docs/superpowers/specs/2026-08-14-heating-ventilation-timer-schedules-design.md`

## Global Constraints

- Use the `py314` conda env by full path for every Python command:
  `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest`
- **Never commit without explicit user approval** (repo rule in `CLAUDE.md`). The commit step in each task means: stage the listed files, show the message, ask, then commit.
- Never scope `--cov` to a leaf submodule. Package root only:
  `-m pytest --cov=custom_components.luxtronik2`
- Branch is already created: `feat/timer-program-heating-ventilation`.
- Commit format: `<type>(<scope>): <gitmoji> <description>`, lowercase imperative, no trailing period; body is a bullet list. End the message with
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- Parameter-name prefixes are the upstream library's literal names and are **inconsistent between circuits on purpose**: heating `SuHkrW0` (digit zero) / `SuHkr25` / `SuHkrTG`; ventilation `SuLufWo` / `SuLuf25` / `SuLufTg`; DHW `SuBwWO` / `SuBw25` / `SuBwTG`. Copy them verbatim, never derive one from another.
- All five translation files (`en`, `de`, `nl`, `cs`, `pl`) must stay in lockstep — `tests/test_translation_coverage.py` enforces it.
- Before the final commit: `ruff check` clean, `ruff format --check` clean, `basedpyright` 0 errors, full test suite green, coverage not regressed.

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `custom_components/luxtronik2/lux_overrides.py` | Datatype coverage for the ventilation parameter block 895-955 | 1 |
| `custom_components/luxtronik2/const.py` | New `SensorKey` and `LuxParameter` members | 2, 4, 5 |
| `custom_components/luxtronik2/timer_schedule_entities_predefined.py` | Circuit table + the two parameter-name builders | 2, 4 |
| `custom_components/luxtronik2/text.py` | Per-circuit bail in the active-block computation and the sync pass | 3 |
| `custom_components/luxtronik2/select_entities_predefined.py` | The two program-mode select descriptions | 5 |
| `custom_components/luxtronik2/translations/{en,de,nl,cs,pl}.json` | Entity names | 2, 4, 5 |
| `tests/test_lux_overrides.py` | Datatype coverage assertions | 1 |
| `tests/test_text.py` | Table integrity, name layouts, per-circuit bail | 2, 3, 4 |
| `tests/test_select.py` | Program-select descriptions | 5 |

---

### Task 1: Ventilation datatype coverage

The ventilation timer parameters live at 895-955, outside the 162-667 range the overrides currently cover, so today every ventilation time reads back as a raw seconds integer and the selector as a raw int.

**Files:**
- Modify: `custom_components/luxtronik2/lux_overrides.py:238-243`
- Test: `tests/test_lux_overrides.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: after `update_Luxtronik_Parameters()`, parameter 895 is a `TimerProgram` instance (decodes to `"week"`/`"5+2"`/`"days"`) and 896-955 are `TimeOfDay` instances (decode to `"HH:MM"`). Tasks 2-5 assume this.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lux_overrides.py`:

```python
class TestTimerScheduleDatatypeCoverage:
    """Both timer-program parameter blocks must get their datatypes.

    The heating/DHW/pool block is contiguous at 162-667, but the ventilation
    block sits apart at 895-955 and was not covered at all, so every
    ventilation time decoded as a raw seconds integer.
    """

    def _applied(self):
        from luxtronik.parameters import Parameters

        from custom_components.luxtronik2.lux_overrides import (
            update_Luxtronik_Parameters,
        )

        update_Luxtronik_Parameters()
        return Parameters.parameters

    def test_ventilation_selector_is_a_timer_program(self):
        from custom_components.luxtronik2.lux_overrides import TimerProgram

        assert isinstance(self._applied()[895], TimerProgram)

    def test_ventilation_times_are_time_of_day(self):
        from custom_components.luxtronik2.lux_overrides import TimeOfDay

        parameters = self._applied()
        # First and last of both the start block (896-925) and the
        # interleaved end block (926-955).
        for number in (896, 925, 926, 955):
            assert isinstance(parameters[number], TimeOfDay), number

    def test_heating_block_is_still_covered(self):
        from custom_components.luxtronik2.lux_overrides import (
            TimeOfDay,
            TimerProgram,
        )

        parameters = self._applied()
        assert isinstance(parameters[222], TimerProgram)
        for number in (223, 282):
            assert isinstance(parameters[number], TimeOfDay), number
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_lux_overrides.py::TestTimerScheduleDatatypeCoverage -v`

Expected: the two ventilation tests FAIL (895/896/955 are `Unknown`); `test_heating_block_is_still_covered` PASSES.

- [ ] **Step 3: Extend the override ranges**

In `update_Luxtronik_Parameters()`, replace the timer-program block:

```python
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
```

- [ ] **Step 4: Run the test again**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_lux_overrides.py -v`

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/luxtronik2/lux_overrides.py tests/test_lux_overrides.py
```

Message:

```
fix(lux_overrides): 🐛 decode the ventilation timer program block

- extend the timer datatype overrides to 895-955, which sits outside the
  162-667 range and so decoded as raw seconds
- give selector 895 the TimerProgram datatype like the other six circuits

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

### Task 2: Heating circuit schedules

**Files:**
- Modify: `custom_components/luxtronik2/const.py:982` (after `TIMER_DHW_SCHEDULE_SUNDAY`)
- Modify: `custom_components/luxtronik2/timer_schedule_entities_predefined.py`
- Modify: `custom_components/luxtronik2/translations/{en,de,nl,cs,pl}.json`
- Test: `tests/test_text.py`

**Interfaces:**
- Consumes: Task 1's datatype coverage (not strictly required to pass these tests).
- Produces:
  - `SK.TIMER_HEATING_SCHEDULE_{WEEK,WEEKDAY,WEEKEND,MONDAY,TUESDAY,WEDNESDAY,THURSDAY,FRIDAY,SATURDAY,SUNDAY}`
  - `_row_names_row_slot(prefix: str, rows: int, col: int) -> tuple[tuple[str, str], ...]` — the existing `_row_names`, renamed
  - `_TimerCircuit.name_builder: Callable[[str, int, int], tuple[tuple[str, str], ...]]`
  - `TIMER_SCHEDULE_ENTITIES` grows from 10 to 20 entries

- [ ] **Step 1: Write the failing tests**

In `tests/test_text.py`, extend `TestTimerScheduleTable`. Replace `test_ten_dhw_entities_generated` and `test_row_counts_are_five_for_dhw` with the versions below (the old ones assert totals that this task changes) and add the rest:

```python
    def test_entity_count(self):
        assert len(TIMER_SCHEDULE_ENTITIES) == 20

    def test_row_counts_per_circuit(self):
        """DHW has 5 slots per day, the heating circuit only 3."""
        by_key = {d.key: len(d.row_names) for d in TIMER_SCHEDULE_ENTITIES}
        assert by_key[SK.TIMER_DHW_SCHEDULE_WEEK] == 5
        assert by_key[SK.TIMER_HEATING_SCHEDULE_WEEK] == 3
        assert by_key[SK.TIMER_HEATING_SCHEDULE_SUNDAY] == 3

    def test_heating_selector_and_device(self):
        from custom_components.luxtronik2.const import DeviceKey

        description = next(
            d
            for d in TIMER_SCHEDULE_ENTITIES
            if d.key == SK.TIMER_HEATING_SCHEDULE_WEEK
        )
        assert description.mode_selector_name == "ID_Einst_SuHkr_akt"
        assert description.device_key is DeviceKey.heating

    def test_heating_row_names(self):
        """Spot-checks against the real upstream names (222-282).

        The heating prefixes are spelled `SuHkrW0` (digit zero) and `SuHkrTG`,
        which differ from DHW's `SuBwWO`/`SuBwTG` - a copy-paste of the DHW
        prefix would still generate plausible-looking names.
        """
        by_key = {d.key: d.row_names for d in TIMER_SCHEDULE_ENTITIES}
        assert by_key[SK.TIMER_HEATING_SCHEDULE_WEEK][0] == (
            "ID_Einst_SuHkrW0_zeit_0_0",
            "ID_Einst_SuHkrW0_zeit_0_1",
        )
        assert by_key[SK.TIMER_HEATING_SCHEDULE_WEEKEND][0] == (
            "ID_Einst_SuHkr25_zeit_0_2",
            "ID_Einst_SuHkr25_zeit_0_3",
        )
        assert by_key[SK.TIMER_HEATING_SCHEDULE_SUNDAY][2] == (
            "ID_Einst_SuHkrTG_zeit_2_12",
            "ID_Einst_SuHkrTG_zeit_2_13",
        )

    def test_heating_active_modes(self):
        by_key = {d.key: d.active_mode for d in TIMER_SCHEDULE_ENTITIES}
        assert by_key[SK.TIMER_HEATING_SCHEDULE_WEEK] == "week"
        assert by_key[SK.TIMER_HEATING_SCHEDULE_WEEKDAY] == "5+2"
        assert by_key[SK.TIMER_HEATING_SCHEDULE_WEEKEND] == "5+2"
        assert by_key[SK.TIMER_HEATING_SCHEDULE_MONDAY] == "days"
```

`test_names_exist_in_library` already covers every new name automatically — leave it as is.

- [ ] **Step 2: Run them and confirm they fail**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_text.py::TestTimerScheduleTable -v`

Expected: FAIL with `AttributeError: TIMER_HEATING_SCHEDULE_WEEK` on the new tests, and `assert 10 == 20` on `test_entity_count`.

- [ ] **Step 3: Add the SensorKey members**

In `const.py`, directly after `TIMER_DHW_SCHEDULE_SUNDAY = "timer_dhw_schedule_sunday"`:

```python

    TIMER_HEATING_SCHEDULE_WEEK = "timer_heating_schedule_week"
    TIMER_HEATING_SCHEDULE_WEEKDAY = "timer_heating_schedule_weekday"
    TIMER_HEATING_SCHEDULE_WEEKEND = "timer_heating_schedule_weekend"
    TIMER_HEATING_SCHEDULE_MONDAY = "timer_heating_schedule_monday"
    TIMER_HEATING_SCHEDULE_TUESDAY = "timer_heating_schedule_tuesday"
    TIMER_HEATING_SCHEDULE_WEDNESDAY = "timer_heating_schedule_wednesday"
    TIMER_HEATING_SCHEDULE_THURSDAY = "timer_heating_schedule_thursday"
    TIMER_HEATING_SCHEDULE_FRIDAY = "timer_heating_schedule_friday"
    TIMER_HEATING_SCHEDULE_SATURDAY = "timer_heating_schedule_saturday"
    TIMER_HEATING_SCHEDULE_SUNDAY = "timer_heating_schedule_sunday"
```

- [ ] **Step 4: Make the name layout pluggable and add the heating circuit**

In `timer_schedule_entities_predefined.py`:

Add to the imports at the top:

```python
from collections.abc import Callable
```

Rename `_row_names` to `_row_names_row_slot` (body unchanged) and update its docstring:

```python
def _row_names_row_slot(prefix: str, rows: int, col: int) -> tuple[tuple[str, str], ...]:
    """Build the (start_name, end_name) pairs for a `<row>_<slot>` block.

    Matches the firmware's ``<prefix>_zeit_<row>_<slot>`` numbering, where
    slot is ``2*col`` (start) / ``2*col + 1`` (end). Used by the DHW and
    heating circuits.
    """
    return tuple(
        (f"{prefix}_zeit_{row}_{2 * col}", f"{prefix}_zeit_{row}_{2 * col + 1}")
        for row in range(rows)
    )
```

Add a field to `_TimerCircuit`, after `per_day_prefix` and before `device_key`:

```python
    #: Builds the (start_name, end_name) pairs for one block. Circuits do not
    #: share a single naming scheme, so the layout is per circuit -- see the
    #: two `_row_names_*` functions. Deliberately has no default: a default
    #: here would make it a class attribute and bind as a method on access.
    name_builder: Callable[[str, int, int], tuple[tuple[str, str], ...]]
```

Give `_DHW_CIRCUIT` the new field:

```python
    name_builder=_row_names_row_slot,
```

Add the heating circuit and its day keys below `_DHW_WEEKDAYS`:

```python
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
```

In `_build_circuit_entities`, replace all four `_row_names(...)` calls with `circuit.name_builder(...)`, e.g.:

```python
            row_names=circuit.name_builder(circuit.same_schedule_prefix, circuit.rows, 0),
```
```python
            row_names=circuit.name_builder(
                circuit.weekday_weekend_prefix, circuit.rows, 0
            ),
```
```python
            row_names=circuit.name_builder(
                circuit.weekday_weekend_prefix, circuit.rows, 1
            ),
```
```python
        row_names=circuit.name_builder(circuit.per_day_prefix, circuit.rows, day_index),
```

Extend the table at the bottom:

```python
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
```

Finally update the module docstring — the DHW-only pilot is over:

```python
"""Predefined timer-program schedule text entities.

Covers the DHW (Bw) and heating (Hkr) circuits. The remaining timer-program
circuits (Mk1/Mk2/ZIP/Swb) follow the same pattern and need one
`_TimerCircuit` instance plus translations each; see the
"lux-timer-program-parameter-layout" memory for their selector/prefix values.
"""
```

- [ ] **Step 5: Run the table tests**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_text.py -v`

Expected: all PASS. If `test_names_exist_in_library` fails, a prefix is mistyped — compare against the upstream names, do not "fix" the test.

- [ ] **Step 6: Add the translations**

In each `translations/<lang>.json`, inside `entity.text`, after the existing `timer_dhw_schedule_sunday` entry, add 10 entries in the shape `"timer_heating_schedule_week": {"name": "..."},` using the names below. Match the file's existing indentation.

`en.json`: Heating Timer Schedule (Week) / (Weekdays) / (Weekend) / (Monday) / (Tuesday) / (Wednesday) / (Thursday) / (Friday) / (Saturday) / (Sunday)

`de.json`: Heizung-Zeitschaltplan (Woche) / (Werktage) / (Wochenende) / (Montag) / (Dienstag) / (Mittwoch) / (Donnerstag) / (Freitag) / (Samstag) / (Sonntag)

`nl.json`: Verwarming tijdschema (week) / (werkdagen) / (weekend) / (maandag) / (dinsdag) / (woensdag) / (donderdag) / (vrijdag) / (zaterdag) / (zondag)

`cs.json`: Časový plán vytápění (týden) / (pracovní dny) / (víkend) / (pondělí) / (úterý) / (středa) / (čtvrtek) / (pátek) / (sobota) / (neděle)

`pl.json`: Harmonogram czasowy ogrzewania (tydzień) / (dni robocze) / (weekend) / (poniedziałek) / (wtorek) / (środa) / (czwartek) / (piątek) / (sobota) / (niedziela)

The key order is `week, weekday, weekend, monday, tuesday, wednesday, thursday, friday, saturday, sunday`, matching the name order above.

- [ ] **Step 7: Verify translation coverage**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_translation_coverage.py -v`

Expected: all PASS. A failure names the missing key and locale exactly.

- [ ] **Step 8: Lint, type-check and run the full suite**

```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff format custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest -q
```

Expected: ruff clean, basedpyright 0 errors, all tests pass.

- [ ] **Step 9: Commit**

```bash
git add custom_components/luxtronik2/const.py \
        custom_components/luxtronik2/timer_schedule_entities_predefined.py \
        custom_components/luxtronik2/translations/ \
        tests/test_text.py
```

Message:

```
feat(text): ✨ add heating circuit timer schedule entities

- add the 10 SuHkr schedule blocks (week, weekday/weekend, per day) on the
  heating device, 3 slots per day
- make the parameter-name layout pluggable per circuit, since not every
  circuit uses the <prefix>_zeit_<row>_<slot> shape
- add en/de/nl/cs/pl names for the new entities

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

### Task 3: Per-circuit bail on an unreadable selector

`_active_schedule_descriptions` returns `None` for the entire pass as soon as any selector reads back `None`. With DHW alone that meant "this circuit is unreadable"; with two or more circuits it freezes all of them. Do this before adding ventilation, whose selector datatype is the one shipping on an unverified assumption.

**Files:**
- Modify: `custom_components/luxtronik2/text.py:51-93` (`_active_schedule_descriptions`) and `custom_components/luxtronik2/text.py:147-209` (`async_apply`)
- Test: `tests/test_text.py`

**Interfaces:**
- Consumes: `SK.TIMER_HEATING_SCHEDULE_*` and the 20-entry `TIMER_SCHEDULE_ENTITIES` from Task 2.
- Produces:
  `_active_schedule_descriptions(coordinator, data) -> tuple[list[LuxtronikTimerScheduleTextDescription], set[str]] | None`
  — the active blocks plus the `mode_selector_name`s that could not be read. `None` only when `data is None`.

- [ ] **Step 1: Adapt the existing helper and write the failing tests**

In `tests/test_text.py`, `TestActiveScheduleDescriptions`, change only the `_call` helper to unwrap the tuple:

```python
    def _call(self, parameters, *, entity_active=True):
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        data = make_coordinator_data(parameters=parameters)
        coord = _mock_coordinator(data)
        coord.entity_active.return_value = entity_active
        active, _unreadable = _active_schedule_descriptions(coord, data)
        return [d.key for d in active]
```

Replace `test_undecodable_selector_yields_no_information` with the per-circuit version, and add the cross-circuit test:

```python
    def test_undecodable_selector_freezes_only_its_own_circuit(self):
        """A present-but-unreadable selector must not read as "no program active".

        `get_sensor_data` returns None both for an absent register and for a
        register whose datatype could not decode the raw value
        (`SelectionBase` returns None for an unrecognised code). The selector
        is reported as unreadable so the sync leaves that circuit alone.
        """
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        data = make_coordinator_data(parameters={self._SELECTOR: None})
        coord = _mock_coordinator(data)
        active, unreadable = _active_schedule_descriptions(coord, data)
        assert active == []
        assert unreadable == {self._SELECTOR}

    def test_one_unreadable_circuit_does_not_hide_another(self):
        """The regression the second circuit makes possible.

        Before this, any single unreadable selector returned "no information"
        for the whole pass, freezing every circuit's entities.
        """
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        data = make_coordinator_data(
            parameters={self._SELECTOR: None, "ID_Einst_SuHkr_akt": "week"}
        )
        coord = _mock_coordinator(data)
        active, unreadable = _active_schedule_descriptions(coord, data)
        assert [d.key for d in active] == [SK.TIMER_HEATING_SCHEDULE_WEEK]
        assert unreadable == {self._SELECTOR}

    def test_data_none_still_yields_no_information(self):
        """No coordinator data at all is "unknown" for every circuit."""
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        assert _active_schedule_descriptions(_mock_coordinator(), None) is None
```

Delete the now-superseded `test_data_none_yields_no_information` (replaced by the identical `test_data_none_still_yields_no_information` above) so it is not defined twice.

Then add the sync-level test to `TestTimerScheduleSync`:

```python
    @pytest.mark.asyncio
    async def test_an_unreadable_circuit_is_frozen_while_others_still_sync(self):
        """A frozen circuit keeps its live entities and registry entries.

        The per-circuit skip is only safe if the sync also refuses to remove
        and disable that circuit's blocks - otherwise it causes exactly the
        teardown the whole-pass bail existed to prevent.
        """
        from custom_components.luxtronik2.text import LuxtronikTimerScheduleText

        sync, coord, added = self._make_sync("week")
        registry = self._registry({})
        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            # Both circuits start in "week" mode.
            coord.data = make_coordinator_data(
                parameters={self._SELECTOR: "week", "ID_Einst_SuHkr_akt": "week"}
            )
            await sync.async_setup()
            assert set(sync._entities) == {
                SK.TIMER_DHW_SCHEDULE_WEEK,
                SK.TIMER_HEATING_SCHEDULE_WEEK,
            }

            # DHW's selector glitches while heating switches program.
            coord.data = make_coordinator_data(
                parameters={self._SELECTOR: None, "ID_Einst_SuHkr_akt": "5+2"}
            )
            with patch.object(
                LuxtronikTimerScheduleText, "async_remove", new=AsyncMock()
            ) as remove:
                await sync.async_apply()

        # Only the heating week block was removed; the DHW one is untouched.
        assert remove.await_count == 1
        assert SK.TIMER_DHW_SCHEDULE_WEEK in sync._entities
        assert SK.TIMER_HEATING_SCHEDULE_WEEK not in sync._entities
        assert [e.entity_description.key for e in added[2:]] == [
            SK.TIMER_HEATING_SCHEDULE_WEEKDAY,
            SK.TIMER_HEATING_SCHEDULE_WEEKEND,
        ]
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_text.py -v`

Expected: FAIL — `TypeError: cannot unpack non-sequence` in `_call` and the new tests, since the helper still returns a bare list.

- [ ] **Step 3: Make the helper report unreadable selectors**

Replace `_active_schedule_descriptions` in `text.py`:

```python
def _active_schedule_descriptions(
    coordinator: LuxtronikCoordinator,
    data: LuxtronikCoordinatorData | None,
) -> tuple[list[LuxtronikTimerScheduleTextDescription], set[str]] | None:
    """Return the active schedule blocks and the unreadable selectors.

    A block qualifies when its circuit's mode selector is present on this
    controller and its value equals the block's `active_mode`. Every other
    block is meaningless on the device, so no entity is created for it.

    The second element holds the `mode_selector_name`s that could not be read
    this poll. `get_sensor_data` returns ``None`` both for an absent register
    and for a present one whose datatype could not decode the raw value
    (``SelectionBase`` returns ``None`` for an unrecognised code), and
    `key_exists` cannot tell the two apart for a parameter inside upstream's
    defined index range. Reading a transient decode failure as "no program is
    active" would tear down that circuit's schedule entities and disable their
    registry entries until the next good poll, so the caller leaves those
    circuits untouched instead. The failure is per circuit: an unreadable
    selector on one circuit must not freeze the others.

    Returns ``None`` -- "no information about anything this poll" -- only when
    there is no coordinator data at all.
    """
    if data is None:
        return None

    descriptions: list[LuxtronikTimerScheduleTextDescription] = []
    unreadable: set[str] = set()
    for description in TIMER_SCHEDULE_ENTITIES:
        if not coordinator.entity_active(description):
            continue
        selector_name = description.mode_selector_name
        if selector_name in unreadable:
            continue
        selector_key = f"parameters.{selector_name}"
        if not key_exists(data, selector_key):
            continue
        mode = get_sensor_data(data, selector_key)
        if mode is None:
            LOGGER.debug(
                "Timer program selector %s could not be read this poll - "
                "leaving its schedule entities untouched",
                selector_key,
            )
            unreadable.add(selector_name)
            continue
        if mode != description.active_mode:
            continue
        descriptions.append(description)
    return descriptions, unreadable
```

- [ ] **Step 4: Freeze those circuits in the sync pass**

In `async_apply`, replace the block from `active = _active_schedule_descriptions(` through the `to_remove = [...]` assignment:

```python
            result = _active_schedule_descriptions(
                self.coordinator, self.coordinator.data
            )
            if result is None:
                # Nothing could be concluded this poll: do not add, remove or
                # write anything.
                return
            active, unreadable = result
            desired = {description.key: description for description in active}
            # A circuit whose selector could not be read keeps whatever it
            # has: its blocks are neither removed nor disabled, because we
            # cannot tell which of them the device is actually running.
            frozen = {
                description.key
                for description in TIMER_SCHEDULE_ENTITIES
                if description.mode_selector_name in unreadable
            }
            to_add = [
                description
                for key, description in desired.items()
                if key not in self._entities
            ]
            to_remove = [
                (key, entity)
                for key, entity in self._entities.items()
                if key not in desired and key not in frozen
            ]
```

and change the final disable call to spare the frozen keys:

```python
            self._disable_inactive(registry, set(desired) | frozen)
```

Update `async_apply`'s docstring to mention the freeze, and the class docstring line about "the registry entries of the other blocks are kept but disabled" to note the exception.

- [ ] **Step 5: Run the tests**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_text.py -v`

Expected: all PASS, including the pre-existing `test_unreadable_selector_does_not_remove_or_disable_anything` — with every DHW key frozen there is nothing to add or remove, so the pass returns before touching the registry.

- [ ] **Step 6: Run the full suite**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest -q`

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add custom_components/luxtronik2/text.py tests/test_text.py
```

Message:

```
fix(text): 🐛 freeze only the circuit whose selector is unreadable

- report unreadable mode selectors per circuit instead of bailing out of the
  whole sync pass, which froze every circuit's entities
- keep a frozen circuit's blocks out of both the removal and the disable
  pass, so its entities and registry entries survive the glitched read

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

### Task 4: Ventilation circuit schedules

The ventilation firmware names put the start/end index **first**: `<prefix>_zeit_<0|1>_<row>_<2*col>`, so its start block (896-925) and end block (926-955) are interleaved rather than adjacent. This needs the second name builder.

**Files:**
- Modify: `custom_components/luxtronik2/const.py` (after the heating keys from Task 2)
- Modify: `custom_components/luxtronik2/timer_schedule_entities_predefined.py`
- Modify: `custom_components/luxtronik2/translations/{en,de,nl,cs,pl}.json`
- Test: `tests/test_text.py`

**Interfaces:**
- Consumes: `_TimerCircuit.name_builder` and `_row_names_row_slot` from Task 2; the per-circuit bail from Task 3.
- Produces:
  - `SK.TIMER_VENTILATION_SCHEDULE_{WEEK,WEEKDAY,WEEKEND,MONDAY..SUNDAY}`
  - `_row_names_block_row_col(prefix: str, rows: int, col: int) -> tuple[tuple[str, str], ...]`
  - `TIMER_SCHEDULE_ENTITIES` grows from 20 to 30 entries

- [ ] **Step 1: Write the failing tests**

In `tests/test_text.py`, update `test_entity_count` to `30` and add to `TestTimerScheduleTable`:

```python
    def test_ventilation_selector_and_device(self):
        from custom_components.luxtronik2.const import DeviceKey

        description = next(
            d
            for d in TIMER_SCHEDULE_ENTITIES
            if d.key == SK.TIMER_VENTILATION_SCHEDULE_WEEK
        )
        assert description.mode_selector_name == "ID_Einst_SuLuf_akt"
        assert description.device_key is DeviceKey.ventilation
        assert len(description.row_names) == 3

    def test_ventilation_row_names_use_the_leading_start_end_index(self):
        """Ventilation names are `<prefix>_zeit_<0|1>_<row>_<2*col>`.

        The start and end blocks are interleaved in the parameter numbering
        (starts 896-925, ends 926-955), unlike every other circuit where the
        end sits immediately after its start.
        """
        by_key = {d.key: d.row_names for d in TIMER_SCHEDULE_ENTITIES}
        assert by_key[SK.TIMER_VENTILATION_SCHEDULE_WEEK][0] == (
            "ID_Einst_SuLufWo_zeit_0_0_0",
            "ID_Einst_SuLufWo_zeit_1_0_0",
        )
        assert by_key[SK.TIMER_VENTILATION_SCHEDULE_WEEKEND][2] == (
            "ID_Einst_SuLuf25_zeit_0_2_2",
            "ID_Einst_SuLuf25_zeit_1_2_2",
        )
        assert by_key[SK.TIMER_VENTILATION_SCHEDULE_WEDNESDAY][1] == (
            "ID_Einst_SuLufTg_zeit_0_1_4",
            "ID_Einst_SuLufTg_zeit_1_1_4",
        )
        assert by_key[SK.TIMER_VENTILATION_SCHEDULE_SUNDAY][2] == (
            "ID_Einst_SuLufTg_zeit_0_2_12",
            "ID_Einst_SuLufTg_zeit_1_2_12",
        )
```

And add the device-gating test to `TestActiveScheduleDescriptions`:

```python
    def test_ventilation_blocks_are_skipped_without_a_ventilation_module(self):
        """`entity_active` is False for the ventilation device on such a unit."""
        from custom_components.luxtronik2.text import _active_schedule_descriptions
        from custom_components.luxtronik2.const import DeviceKey

        data = make_coordinator_data(
            parameters={self._SELECTOR: "week", "ID_Einst_SuLuf_akt": "week"}
        )
        coord = _mock_coordinator(data)
        coord.entity_active.side_effect = (
            lambda description: description.device_key is not DeviceKey.ventilation
        )
        active, unreadable = _active_schedule_descriptions(coord, data)
        keys = [d.key for d in active]
        assert SK.TIMER_DHW_SCHEDULE_WEEK in keys
        assert SK.TIMER_VENTILATION_SCHEDULE_WEEK not in keys
        assert unreadable == set()
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_text.py::TestTimerScheduleTable -v`

Expected: FAIL with `AttributeError: TIMER_VENTILATION_SCHEDULE_WEEK` and `assert 20 == 30`.

- [ ] **Step 3: Add the SensorKey members**

In `const.py`, after `TIMER_HEATING_SCHEDULE_SUNDAY`:

```python

    TIMER_VENTILATION_SCHEDULE_WEEK = "timer_ventilation_schedule_week"
    TIMER_VENTILATION_SCHEDULE_WEEKDAY = "timer_ventilation_schedule_weekday"
    TIMER_VENTILATION_SCHEDULE_WEEKEND = "timer_ventilation_schedule_weekend"
    TIMER_VENTILATION_SCHEDULE_MONDAY = "timer_ventilation_schedule_monday"
    TIMER_VENTILATION_SCHEDULE_TUESDAY = "timer_ventilation_schedule_tuesday"
    TIMER_VENTILATION_SCHEDULE_WEDNESDAY = "timer_ventilation_schedule_wednesday"
    TIMER_VENTILATION_SCHEDULE_THURSDAY = "timer_ventilation_schedule_thursday"
    TIMER_VENTILATION_SCHEDULE_FRIDAY = "timer_ventilation_schedule_friday"
    TIMER_VENTILATION_SCHEDULE_SATURDAY = "timer_ventilation_schedule_saturday"
    TIMER_VENTILATION_SCHEDULE_SUNDAY = "timer_ventilation_schedule_sunday"
```

- [ ] **Step 4: Add the second name builder and the circuit**

In `timer_schedule_entities_predefined.py`, after `_row_names_row_slot`:

```python
def _row_names_block_row_col(
    prefix: str, rows: int, col: int
) -> tuple[tuple[str, str], ...]:
    """Build the (start_name, end_name) pairs for a `<0|1>_<row>_<col>` block.

    The ventilation circuit names its slots ``<prefix>_zeit_<0|1>_<row>_<2*col>``
    with the start/end index *first*, so its start times (896-925) and end
    times (926-955) form two interleaved blocks rather than adjacent pairs.

    Inferred from the parameter naming, not from a diagnostics dump: no unit
    with a ventilation module has been sampled yet. If a dump ever shows the
    leading index is not start/end, this function is the only thing to change.
    """
    return tuple(
        (f"{prefix}_zeit_0_{row}_{2 * col}", f"{prefix}_zeit_1_{row}_{2 * col}")
        for row in range(rows)
    )
```

Then, after `_HEATING_WEEKDAYS`:

```python
_VENTILATION_CIRCUIT = _TimerCircuit(
    mode_selector_name="ID_Einst_SuLuf_akt",
    rows=3,
    same_schedule_prefix="ID_Einst_SuLufWo",
    weekday_weekend_prefix="ID_Einst_SuLuf25",
    per_day_prefix="ID_Einst_SuLufTg",
    name_builder=_row_names_block_row_col,
    device_key=DeviceKey.ventilation,
)

_VENTILATION_WEEKDAYS: tuple[tuple[SK, int], ...] = (
    (SK.TIMER_VENTILATION_SCHEDULE_MONDAY, 0),
    (SK.TIMER_VENTILATION_SCHEDULE_TUESDAY, 1),
    (SK.TIMER_VENTILATION_SCHEDULE_WEDNESDAY, 2),
    (SK.TIMER_VENTILATION_SCHEDULE_THURSDAY, 3),
    (SK.TIMER_VENTILATION_SCHEDULE_FRIDAY, 4),
    (SK.TIMER_VENTILATION_SCHEDULE_SATURDAY, 5),
    (SK.TIMER_VENTILATION_SCHEDULE_SUNDAY, 6),
)
```

Extend the table:

```python
    + _build_circuit_entities(
        _VENTILATION_CIRCUIT,
        week_key=SK.TIMER_VENTILATION_SCHEDULE_WEEK,
        weekday_key=SK.TIMER_VENTILATION_SCHEDULE_WEEKDAY,
        weekend_key=SK.TIMER_VENTILATION_SCHEDULE_WEEKEND,
        day_keys=_VENTILATION_WEEKDAYS,
    )
```

Update the module docstring's first line to `Covers the DHW (Bw), heating (Hkr) and ventilation (Luf) circuits.`

Also note in the `_VENTILATION_CIRCUIT` block that the selector's `TimerProgram` codes are assumed to match the other circuits:

```python
# The selector's week/5+2/days codes are assumed to match the other circuits;
# see lux_overrides.update_Luxtronik_Parameters. Also inferred, not sampled.
```

- [ ] **Step 5: Run the tests**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_text.py -v`

Expected: all PASS. `test_names_exist_in_library` proves all 60 generated ventilation names resolve to real upstream parameters.

- [ ] **Step 6: Add the translations**

Same procedure as Task 2 Step 6, 10 more keys per file named `timer_ventilation_schedule_*`, placed after the heating ones:

`en.json`: Ventilation Timer Schedule (Week) / (Weekdays) / (Weekend) / (Monday) / (Tuesday) / (Wednesday) / (Thursday) / (Friday) / (Saturday) / (Sunday)

`de.json`: Lüftung-Zeitschaltplan (Woche) / (Werktage) / (Wochenende) / (Montag) / (Dienstag) / (Mittwoch) / (Donnerstag) / (Freitag) / (Samstag) / (Sonntag)

`nl.json`: Ventilatie tijdschema (week) / (werkdagen) / (weekend) / (maandag) / (dinsdag) / (woensdag) / (donderdag) / (vrijdag) / (zaterdag) / (zondag)

`cs.json`: Časový plán větrání (týden) / (pracovní dny) / (víkend) / (pondělí) / (úterý) / (středa) / (čtvrtek) / (pátek) / (sobota) / (neděle)

`pl.json`: Harmonogram czasowy wentylacji (tydzień) / (dni robocze) / (weekend) / (poniedziałek) / (wtorek) / (środa) / (czwartek) / (piątek) / (sobota) / (niedziela)

- [ ] **Step 7: Verify, lint and type-check**

```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_translation_coverage.py -v
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff format custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest -q
```

Expected: all clean and green.

- [ ] **Step 8: Commit**

```bash
git add custom_components/luxtronik2/const.py \
        custom_components/luxtronik2/timer_schedule_entities_predefined.py \
        custom_components/luxtronik2/translations/ \
        tests/test_text.py
```

Message:

```
feat(text): ✨ add ventilation timer schedule entities

- add the 10 SuLuf schedule blocks on the ventilation device, gated on the
  coordinator's ventilation detection
- add a second name builder for the ventilation layout, which puts the
  start/end index first and interleaves the two blocks
- add en/de/nl/cs/pl names for the new entities

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

### Task 5: Heating and ventilation program-mode selects

Without these, the new schedules are visible but the user cannot switch which program is active — and which schedule entities exist at all is driven by exactly that selector.

**Files:**
- Modify: `custom_components/luxtronik2/const.py` (`SensorKey` and `LuxParameter`)
- Modify: `custom_components/luxtronik2/select_entities_predefined.py:79-86` (after the DHW entry)
- Modify: `custom_components/luxtronik2/translations/{en,de,nl,cs,pl}.json`
- Test: `tests/test_select.py`

**Interfaces:**
- Consumes: nothing from Tasks 2-4 (independent), though it targets the same two selectors.
- Produces: `SK.TIMER_HEATING_PROGRAM`, `SK.TIMER_VENTILATION_PROGRAM`, `LuxParameter.P0222_TIMER_PROGRAM_HEATING`, `LuxParameter.P0895_TIMER_PROGRAM_VENTILATION`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_select.py` (match the file's existing import style):

```python
class TestTimerProgramSelects:
    """The program selector of every schedule-carrying circuit is settable."""

    def _description(self, key):
        from custom_components.luxtronik2.select_entities_predefined import (
            SELECT_ENTITIES,
        )

        return next(d for d in SELECT_ENTITIES if d.key == key)

    def test_heating_program_select(self):
        from custom_components.luxtronik2.const import (
            DeviceKey,
            LuxParameter,
            SensorKey,
        )

        description = self._description(SensorKey.TIMER_HEATING_PROGRAM)
        assert description.luxtronik_key == LuxParameter.P0222_TIMER_PROGRAM_HEATING
        assert description.device_key is DeviceKey.heating
        assert description.raw_option_map == {
            "week": "week",
            "weekday_weekend": "5+2",
            "daily": "days",
        }

    def test_ventilation_program_select(self):
        from custom_components.luxtronik2.const import (
            DeviceKey,
            LuxParameter,
            SensorKey,
        )

        description = self._description(SensorKey.TIMER_VENTILATION_PROGRAM)
        assert description.luxtronik_key == LuxParameter.P0895_TIMER_PROGRAM_VENTILATION
        assert description.device_key is DeviceKey.ventilation
        assert description.options == ["week", "weekday_weekend", "daily"]

    def test_parameter_strings_match_the_schedule_selectors(self):
        """The select and the schedule entities must drive the same register.

        A typo in either parameter string would silently give the user a
        selector that writes somewhere else while the schedules keep reading
        the real one.
        """
        from custom_components.luxtronik2.const import LuxParameter
        from custom_components.luxtronik2.timer_schedule_entities_predefined import (
            TIMER_SCHEDULE_ENTITIES,
        )
        from custom_components.luxtronik2.const import SensorKey

        selectors = {
            SensorKey.TIMER_HEATING_SCHEDULE_WEEK: (
                LuxParameter.P0222_TIMER_PROGRAM_HEATING
            ),
            SensorKey.TIMER_VENTILATION_SCHEDULE_WEEK: (
                LuxParameter.P0895_TIMER_PROGRAM_VENTILATION
            ),
        }
        for schedule_key, parameter in selectors.items():
            description = next(
                d for d in TIMER_SCHEDULE_ENTITIES if d.key == schedule_key
            )
            assert parameter.value == f"parameters.{description.mode_selector_name}"
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_select.py::TestTimerProgramSelects -v`

Expected: FAIL with `AttributeError: TIMER_HEATING_PROGRAM`.

- [ ] **Step 3: Add the const members**

In `const.py`, next to `TIMER_DHW_PROGRAM = "timer_dhw_program"`:

```python
    TIMER_HEATING_PROGRAM = "timer_heating_program"
    TIMER_VENTILATION_PROGRAM = "timer_ventilation_program"
```

And in `LuxParameter`, next to `P0405_TIMER_PROGRAM_DHW` (keep the members in numeric order — 222 belongs before 405, 895 before `P0894_VENTILATION_MODE`'s neighbours; place each at its numeric position):

```python
    P0222_TIMER_PROGRAM_HEATING = "parameters.ID_Einst_SuHkr_akt"
```
```python
    P0895_TIMER_PROGRAM_VENTILATION = "parameters.ID_Einst_SuLuf_akt"
```

- [ ] **Step 4: Add the select descriptions**

In `select_entities_predefined.py`, directly after the `SK.TIMER_DHW_PROGRAM` entry:

```python
    LuxtronikSelectEntityDescription(
        key=SK.TIMER_HEATING_PROGRAM,
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0222_TIMER_PROGRAM_HEATING,
        entity_category=EntityCategory.CONFIG,
        options=timer_program_options,
        raw_option_map=TIMER_PROGRAM_RAW_OPTIONS,
    ),
    LuxtronikSelectEntityDescription(
        key=SK.TIMER_VENTILATION_PROGRAM,
        device_key=DeviceKey.ventilation,
        luxtronik_key=LuxParameter.P0895_TIMER_PROGRAM_VENTILATION,
        entity_category=EntityCategory.CONFIG,
        options=timer_program_options,
        raw_option_map=TIMER_PROGRAM_RAW_OPTIONS,
    ),
```

- [ ] **Step 5: Run the test**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_select.py -v`

Expected: all PASS.

- [ ] **Step 6: Add the translations**

In each `translations/<lang>.json`, inside `entity.select`, after `timer_dhw_program`, add two entries with the same `name` + `state` shape. The three state keys are always `week`, `weekday_weekend`, `daily`, and their values are identical to the ones already on `timer_dhw_program` in that file — only the `name` differs:

| lang | heating name | ventilation name |
|---|---|---|
| en | Heating timer program | Ventilation timer program |
| de | Heizung Zeitprogramm | Lüftung Zeitprogramm |
| nl | Verwarming tijdprogramma | Ventilatie tijdprogramma |
| cs | Časový program vytápění | Časový program větrání |
| pl | Program czasowy ogrzewania | Program czasowy wentylacji |

For example, in `en.json`:

```json
    "timer_heating_program": {
      "name": "Heating timer program",
      "state": {
        "week": "Whole week",
        "weekday_weekend": "Weekdays + weekend",
        "daily": "Per day"
      }
    },
```

`tests/test_translation_coverage.py` fails if any locale's `state` key set differs, so copy all three states into all ten new blocks.

- [ ] **Step 7: Verify and commit**

```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_translation_coverage.py tests/test_select.py -v
```

Then stage and commit:

```bash
git add custom_components/luxtronik2/const.py \
        custom_components/luxtronik2/select_entities_predefined.py \
        custom_components/luxtronik2/translations/ \
        tests/test_select.py
```

Message:

```
feat(select): ✨ add heating and ventilation timer program selects

- expose the SuHkr (222) and SuLuf (895) mode selectors, so the program
  driving the new schedule entities can be switched from Home Assistant
- reuse the DHW selector's week/5+2/days option mapping
- add en/de/nl/cs/pl names and states

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

### Task 6: Final verification

**Files:** none modified unless something fails.

- [ ] **Step 1: Full pre-commit gate**

```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff format --check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m codespell custom_components/luxtronik2 tests
```

Expected: all clean, basedpyright 0 errors. Note that German entity names contain `ü`/`ö` — if codespell flags a translated word, add it to the existing ignore configuration rather than changing the translation.

- [ ] **Step 2: Full suite with coverage**

```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest --cov=custom_components.luxtronik2 --cov-report=term-missing -q
```

Expected: all tests pass, total coverage no lower than on `main`. Never scope `--cov` to a submodule (see Global Constraints).

- [ ] **Step 3: Report**

Summarise for the user: 30 schedule text entities across 3 circuits, 2 new selects, the two shipped-unverified ventilation assumptions and where to correct them, and the exact test/lint/coverage numbers observed. Do not claim anything that was not run.

---

## Self-Review

**Spec coverage:** Every spec section maps to a task — circuit table → 2 & 4; parameter-name layouts → 2 (`_row_names_row_slot`) & 4 (`_row_names_block_row_col`); unverified assumptions → comments in 4 and the datatype override in 1; program mode selects → 5; `lux_overrides.py` → 1; `const.py` → 2, 4, 5; `select_entities_predefined.py` → 5; translations → 2, 4, 5; per-circuit bail → 3; every testing bullet → the corresponding task's test step plus Task 6 for the coverage requirement.

**Placeholders:** none — every code step carries the actual code, and every translation string is spelled out.

**Type consistency:** `_row_names_row_slot` and `_row_names_block_row_col` share the signature `(str, int, int) -> tuple[tuple[str, str], ...]` declared on `_TimerCircuit.name_builder`. `_active_schedule_descriptions` returns `tuple[list[...], set[str]] | None` in Task 3 and is consumed with that shape in Tasks 3 and 4. Sensor and parameter key names are identical everywhere they appear.

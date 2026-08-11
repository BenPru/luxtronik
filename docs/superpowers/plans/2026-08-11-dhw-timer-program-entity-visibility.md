# DHW Timer-Program Entity Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Only the DHW schedule text entities of the currently selected timer program exist as live entities; the others are removed from the state machine and hidden in the entity registry, and the timer program itself becomes switchable from HA via a new select entity.

**Architecture:** `text.py` gains a `_TimerScheduleSync` helper that computes the active-mode description set from coordinator data, adds/removes entities, and flips `hidden_by` on the registry entries of inactive modes. It runs once at setup and again on every coordinator update through `coordinator.async_add_listener`. `select.py`/`model.py` gain an explicit HA-option → raw-device-value mapping so the raw value `"5+2"` can be exposed as the HA option `weekday_weekend`.

**Tech Stack:** Home Assistant custom integration, Python 3.14, pytest + pytest-asyncio, ruff, basedpyright.

## Global Constraints

- Design doc: `docs/superpowers/specs/2026-08-11-dhw-timer-program-entity-visibility-design.md`.
- Work happens on branch `feat/dhw-timer-program-visibility` (already created, spec already committed there).
- Run every Python command through the py314 env by full path:
  `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest ...`
- Before each commit: `python -m ruff check custom_components/luxtronik2 tests`,
  `python -m ruff format custom_components/luxtronik2 tests`,
  `python -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2` (must be 0 errors).
- Never scope `--cov` to a leaf submodule; measure at `--cov=custom_components.luxtronik2`.
- Commit format: `<type>(<scope>): <gitmoji> <description>` (lowercase imperative, no trailing period), body as a bullet list.
- Entity presence is gated on register existence (`key_exists`), never on firmware version.
- The raw device values of parameter 405 are exactly `"week"`, `"5+2"`, `"days"` (from `TimerProgram` in `lux_overrides.py`). The HA-facing option names are exactly `week`, `weekday_weekend`, `daily`.
- A registry entry whose `hidden_by` is `RegistryEntryHider.USER` is never modified.

## File Structure

- `custom_components/luxtronik2/text.py` — modify: add `_timer_schedule_unique_id`, `_active_schedule_descriptions`, `_TimerScheduleSync`; rewrite `async_setup_entry`.
- `custom_components/luxtronik2/const.py` — modify: add `LuxParameter.P0405_TIMER_PROGRAM_DHW` and `SensorKey.TIMER_DHW_PROGRAM`.
- `custom_components/luxtronik2/model.py` — modify: add `raw_option_map` field to `LuxtronikSelectEntityDescription`.
- `custom_components/luxtronik2/select.py` — modify: honour `raw_option_map` in `LuxtronikModeSelector`.
- `custom_components/luxtronik2/select_entities_predefined.py` — modify: add the timer-program description.
- `custom_components/luxtronik2/translations/{en,de,nl,cs,pl}.json` — modify: name + state strings for the new select.
- `tests/test_text.py` — modify: tests for the three new text.py units.
- `tests/test_select.py` — modify: tests for the option mapping.

---

### Task 1: Single-source the schedule unique_id

**Files:**
- Modify: `custom_components/luxtronik2/text.py:89-108`
- Test: `tests/test_text.py`

**Interfaces:**
- Produces: `_timer_schedule_unique_id(entry: LuxtronikConfigEntry, description: LuxtronikTimerScheduleTextDescription) -> str`, returning e.g. `"text.luxtronik_timer_dhw_schedule_week"`. Tasks 2 and 3 use it to look registry entries up.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_text.py`, at the end of the file:

```python
# ===========================================================================
# _timer_schedule_unique_id
# ===========================================================================


class TestTimerScheduleUniqueId:
    def test_matches_the_entity_id_the_entity_assigns_itself(self):
        from custom_components.luxtronik2.text import _timer_schedule_unique_id

        description = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_WEEK
        )
        assert (
            _timer_schedule_unique_id(_mock_entry(), description)
            == f"text.{DOMAIN}_{description.key}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_text.py::TestTimerScheduleUniqueId -v`
Expected: FAIL with `ImportError: cannot import name '_timer_schedule_unique_id'`

- [ ] **Step 3: Add the helper and use it in the entity**

In `custom_components/luxtronik2/text.py`, add after `_PAIR_PATTERN`:

```python
def _timer_schedule_unique_id(
    entry: LuxtronikConfigEntry,
    description: LuxtronikTimerScheduleTextDescription,
) -> str:
    """Return the unique_id of a schedule entity.

    Today this is also its default entity_id. The format lives here only, so
    decoupling unique_id from entity_id later (HA best practice) is a
    single-site change plus a registry migration.
    """
    prefix = entry.data[CONF_HA_SENSOR_PREFIX]
    return ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
```

Then replace these two lines in `LuxtronikTimerScheduleText.__init__`:

```python
        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id
```

with:

```python
        self.entity_id = _timer_schedule_unique_id(entry, description)
        self._attr_unique_id = self.entity_id
```

- [ ] **Step 4: Run the text tests**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_text.py -v`
Expected: PASS (including the pre-existing `test_entity_id`)

- [ ] **Step 5: Lint, typecheck, commit**

```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff format custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2
git add custom_components/luxtronik2/text.py tests/test_text.py
git commit -m "refactor(text): ♻️ single-source the timer schedule unique_id"
```

---

### Task 2: Compute the active timer program's descriptions

**Files:**
- Modify: `custom_components/luxtronik2/text.py`
- Test: `tests/test_text.py`

**Interfaces:**
- Consumes: `_timer_schedule_unique_id` (Task 1) — not directly, but the same module.
- Produces: `_active_schedule_descriptions(coordinator: LuxtronikCoordinator, data: LuxtronikCoordinatorData | None) -> list[LuxtronikTimerScheduleTextDescription]`. Task 3 calls it once per sync.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_text.py`:

```python
# ===========================================================================
# _active_schedule_descriptions
# ===========================================================================


class TestActiveScheduleDescriptions:
    _SELECTOR = "ID_Einst_SUBW_akt2"

    def _call(self, parameters, *, entity_active=True):
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        data = make_coordinator_data(parameters=parameters)
        coord = _mock_coordinator(data)
        coord.entity_active.return_value = entity_active
        return [d.key for d in _active_schedule_descriptions(coord, data)]

    def test_week_mode_yields_only_the_week_block(self):
        assert self._call({self._SELECTOR: "week"}) == [SK.TIMER_DHW_SCHEDULE_WEEK]

    def test_weekday_weekend_mode_yields_both_blocks(self):
        assert self._call({self._SELECTOR: "5+2"}) == [
            SK.TIMER_DHW_SCHEDULE_WEEKDAY,
            SK.TIMER_DHW_SCHEDULE_WEEKEND,
        ]

    def test_days_mode_yields_seven_day_blocks(self):
        keys = self._call({self._SELECTOR: "days"})
        assert len(keys) == 7
        assert SK.TIMER_DHW_SCHEDULE_MONDAY in keys
        assert SK.TIMER_DHW_SCHEDULE_SUNDAY in keys

    def test_missing_selector_parameter_yields_nothing(self):
        assert self._call({}) == []

    def test_data_none_yields_nothing(self):
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        assert _active_schedule_descriptions(_mock_coordinator(), None) == []

    def test_inactive_entity_yields_nothing(self):
        assert self._call({self._SELECTOR: "week"}, entity_active=False) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_text.py::TestActiveScheduleDescriptions -v`
Expected: FAIL with `ImportError: cannot import name '_active_schedule_descriptions'`

- [ ] **Step 3: Implement the function**

In `custom_components/luxtronik2/text.py`, add after `_timer_schedule_unique_id`:

```python
def _active_schedule_descriptions(
    coordinator: LuxtronikCoordinator,
    data: LuxtronikCoordinatorData | None,
) -> list[LuxtronikTimerScheduleTextDescription]:
    """Return the schedule blocks belonging to the circuit's active program.

    A block qualifies when the circuit's mode selector is present on this
    controller and its value equals the block's `active_mode`. Every other
    block is meaningless on the device, so no entity is created for it.
    """
    if data is None:
        return []

    descriptions: list[LuxtronikTimerScheduleTextDescription] = []
    for description in TIMER_SCHEDULE_ENTITIES:
        if not coordinator.entity_active(description):
            continue
        selector_key = f"parameters.{description.mode_selector_name}"
        if not key_exists(data, selector_key):
            continue
        if get_sensor_data(data, selector_key) != description.active_mode:
            continue
        descriptions.append(description)
    return descriptions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_text.py -v`
Expected: PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff format custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2
git add custom_components/luxtronik2/text.py tests/test_text.py
git commit -m "feat(text): ✨ derive the active timer program's schedule blocks"
```

---

### Task 3: Sync live entities with the active program

**Files:**
- Modify: `custom_components/luxtronik2/text.py:30-53` (`async_setup_entry`) plus new class
- Test: `tests/test_text.py`

**Interfaces:**
- Consumes: `_timer_schedule_unique_id` (Task 1), `_active_schedule_descriptions` (Task 2).
- Produces: `_TimerScheduleSync(hass, entry, coordinator, async_add_entities)` with
  `async def async_setup(self) -> None` (initial add + hide pass) and
  `@callback def async_sync(self) -> None` (coordinator-listener entry point, schedules the work).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_text.py`:

```python
# ===========================================================================
# _TimerScheduleSync
# ===========================================================================


class TestTimerScheduleSync:
    _SELECTOR = "ID_Einst_SUBW_akt2"

    def _make_sync(self, mode: str):
        from custom_components.luxtronik2.text import _TimerScheduleSync

        data = make_coordinator_data(parameters={self._SELECTOR: mode})
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        added: list = []

        def _add_entities(entities):
            added.extend(entities)

        sync = _TimerScheduleSync(MagicMock(), entry, coord, _add_entities)
        return sync, coord, added

    def _registry(self, known: dict[str, MagicMock]):
        """Fake entity registry: unique_id -> registry entry."""
        registry = MagicMock()
        registry.async_get_entity_id.side_effect = (
            lambda _domain, _platform, unique_id: unique_id if unique_id in known else None
        )
        registry.async_get.side_effect = lambda entity_id: known.get(entity_id)
        return registry

    def _entry(self, hidden_by=None):
        registry_entry = MagicMock()
        registry_entry.hidden_by = hidden_by
        return registry_entry

    @pytest.mark.asyncio
    async def test_setup_adds_only_the_active_blocks(self):
        sync, _coord, added = self._make_sync("week")
        with patch("custom_components.luxtronik2.text.er.async_get", return_value=self._registry({})), patch(
            "homeassistant.helpers.frame.report_usage"
        ):
            await sync.async_setup()
        assert [e.entity_description.key for e in added] == [SK.TIMER_DHW_SCHEDULE_WEEK]

    @pytest.mark.asyncio
    async def test_setup_hides_existing_entries_of_inactive_blocks(self):
        from custom_components.luxtronik2.text import _timer_schedule_unique_id
        from homeassistant.helpers.entity_registry import RegistryEntryHider

        sync, _coord, _added = self._make_sync("week")
        entry = _mock_entry()
        stale = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_MONDAY
        )
        stale_id = _timer_schedule_unique_id(entry, stale)
        registry = self._registry({stale_id: self._entry()})

        with patch("custom_components.luxtronik2.text.er.async_get", return_value=registry), patch(
            "homeassistant.helpers.frame.report_usage"
        ):
            await sync.async_setup()

        registry.async_update_entity.assert_any_call(
            stale_id, hidden_by=RegistryEntryHider.INTEGRATION
        )

    @pytest.mark.asyncio
    async def test_setup_does_not_touch_a_user_hidden_entry(self):
        from custom_components.luxtronik2.text import _timer_schedule_unique_id
        from homeassistant.helpers.entity_registry import RegistryEntryHider

        sync, _coord, _added = self._make_sync("week")
        entry = _mock_entry()
        week = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_WEEK
        )
        week_id = _timer_schedule_unique_id(entry, week)
        registry = self._registry({week_id: self._entry(RegistryEntryHider.USER)})

        with patch("custom_components.luxtronik2.text.er.async_get", return_value=registry), patch(
            "homeassistant.helpers.frame.report_usage"
        ):
            await sync.async_setup()

        registry.async_update_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_setup_unhides_an_integration_hidden_active_entry(self):
        from custom_components.luxtronik2.text import _timer_schedule_unique_id
        from homeassistant.helpers.entity_registry import RegistryEntryHider

        sync, _coord, _added = self._make_sync("week")
        entry = _mock_entry()
        week = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_WEEK
        )
        week_id = _timer_schedule_unique_id(entry, week)
        registry = self._registry({week_id: self._entry(RegistryEntryHider.INTEGRATION)})

        with patch("custom_components.luxtronik2.text.er.async_get", return_value=registry), patch(
            "homeassistant.helpers.frame.report_usage"
        ):
            await sync.async_setup()

        registry.async_update_entity.assert_any_call(week_id, hidden_by=None)

    @pytest.mark.asyncio
    async def test_mode_change_swaps_the_entities(self):
        from custom_components.luxtronik2.text import LuxtronikTimerScheduleText

        sync, coord, added = self._make_sync("week")
        registry = self._registry({})
        with patch("custom_components.luxtronik2.text.er.async_get", return_value=registry), patch(
            "homeassistant.helpers.frame.report_usage"
        ):
            await sync.async_setup()
            coord.data = make_coordinator_data(parameters={self._SELECTOR: "5+2"})
            with patch.object(
                LuxtronikTimerScheduleText, "async_remove", new=AsyncMock()
            ) as remove:
                await sync.async_apply()

        assert remove.await_count == 1
        assert [e.entity_description.key for e in added[1:]] == [
            SK.TIMER_DHW_SCHEDULE_WEEKDAY,
            SK.TIMER_DHW_SCHEDULE_WEEKEND,
        ]

    @pytest.mark.asyncio
    async def test_unchanged_mode_does_not_touch_anything(self):
        sync, _coord, added = self._make_sync("week")
        registry = self._registry({})
        with patch("custom_components.luxtronik2.text.er.async_get", return_value=registry), patch(
            "homeassistant.helpers.frame.report_usage"
        ):
            await sync.async_setup()
            registry.async_update_entity.reset_mock()
            await sync.async_apply()

        assert len(added) == 1
        registry.async_update_entity.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_text.py::TestTimerScheduleSync -v`
Expected: FAIL with `ImportError: cannot import name '_TimerScheduleSync'`

- [ ] **Step 3: Implement the sync helper**

Add these imports at the top of `custom_components/luxtronik2/text.py`:

```python
from homeassistant.components.text import DOMAIN as TEXT_DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryHider
```

Add the class after `_active_schedule_descriptions`:

```python
class _TimerScheduleSync:
    """Keeps the live schedule entities in step with the active timer program.

    Only the blocks of the running program exist as entities. The registry
    entries of the other blocks are kept but hidden, so a user's rename,
    area, icon and recorder history survive a program switch -- removing the
    registry entry would discard all of it.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LuxtronikConfigEntry,
        coordinator: LuxtronikCoordinator,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.async_add_entities = async_add_entities
        self._entities: dict[str, LuxtronikTimerScheduleText] = {}

    async def async_setup(self) -> None:
        """Add the active program's entities and hide the rest."""
        await self.async_apply()

    @callback
    def async_sync(self) -> None:
        """Coordinator listener: schedule an add/remove pass."""
        self.entry.async_create_task(
            self.hass, self.async_apply(), eager_start=False
        )

    async def async_apply(self) -> None:
        """Bring the live entity set in line with the active program."""
        desired = {
            description.key: description
            for description in _active_schedule_descriptions(
                self.coordinator, self.coordinator.data
            )
        }
        to_add = [
            description
            for key, description in desired.items()
            if key not in self._entities
        ]
        to_remove = [
            (key, entity)
            for key, entity in self._entities.items()
            if key not in desired
        ]
        if not to_add and not to_remove:
            return

        registry = er.async_get(self.hass)
        # Unhide before adding: an entity added while its registry entry is
        # hidden would stay hidden.
        self._unhide_active(registry, set(desired))

        if to_add:
            entities = [
                LuxtronikTimerScheduleText(
                    self.entry, self.coordinator, description, description.device_key
                )
                for description in to_add
            ]
            for description, entity in zip(to_add, entities, strict=True):
                self._entities[description.key] = entity
            self.async_add_entities(entities)

        for key, entity in to_remove:
            del self._entities[key]
            # No force_remove: the registry entry must survive so the user's
            # customisations and history are still there next time.
            await entity.async_remove()

        self._hide_inactive(registry, set(desired))

    def _unhide_active(
        self, registry: er.EntityRegistry, desired_keys: set[str]
    ) -> None:
        for description in TIMER_SCHEDULE_ENTITIES:
            if description.key not in desired_keys:
                continue
            entity_id = registry.async_get_entity_id(
                TEXT_DOMAIN, DOMAIN, _timer_schedule_unique_id(self.entry, description)
            )
            registry_entry = None if entity_id is None else registry.async_get(entity_id)
            if (
                registry_entry is not None
                and registry_entry.hidden_by is RegistryEntryHider.INTEGRATION
            ):
                registry.async_update_entity(entity_id, hidden_by=None)

    def _hide_inactive(
        self, registry: er.EntityRegistry, desired_keys: set[str]
    ) -> None:
        for description in TIMER_SCHEDULE_ENTITIES:
            if description.key in desired_keys:
                continue
            entity_id = registry.async_get_entity_id(
                TEXT_DOMAIN, DOMAIN, _timer_schedule_unique_id(self.entry, description)
            )
            registry_entry = None if entity_id is None else registry.async_get(entity_id)
            # hidden_by USER is the user's own decision and is left alone.
            if registry_entry is not None and registry_entry.hidden_by is None:
                registry.async_update_entity(
                    entity_id, hidden_by=RegistryEntryHider.INTEGRATION
                )
```

Replace the body of `async_setup_entry` with:

```python
async def async_setup_entry(  # pragma: no cover
    hass: HomeAssistant,
    entry: LuxtronikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    if not coordinator.last_update_success:
        return

    sync = _TimerScheduleSync(hass, entry, coordinator, async_add_entities)
    await sync.async_setup()
    entry.async_on_unload(coordinator.async_add_listener(sync.async_sync))
```

`key_exists` is no longer used by `async_setup_entry` but is still used by
`_active_schedule_descriptions`, so its import stays.

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_text.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite with coverage**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest --cov=custom_components.luxtronik2 -q`
Expected: all pass, coverage not lower than before the branch

- [ ] **Step 6: Lint, typecheck, commit**

```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff format custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2
git add custom_components/luxtronik2/text.py tests/test_text.py
git commit -m "feat(text): ✨ create only the selected timer program's schedule entities"
```

---

### Task 4: Expose the DHW timer program as a select entity

**Files:**
- Modify: `custom_components/luxtronik2/const.py` (`LuxParameter`, `SensorKey`)
- Modify: `custom_components/luxtronik2/model.py:245-252`
- Modify: `custom_components/luxtronik2/select.py:212-273`
- Modify: `custom_components/luxtronik2/select_entities_predefined.py`
- Modify: `custom_components/luxtronik2/translations/{en,de,nl,cs,pl}.json`
- Test: `tests/test_select.py`

**Interfaces:**
- Consumes: nothing from Tasks 1-3.
- Produces: `LuxtronikSelectEntityDescription.raw_option_map: dict[str, str] | None` (HA option → raw device value) honoured by `LuxtronikModeSelector`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_select.py`:

```python
# ===========================================================================
# raw_option_map (timer program selector)
# ===========================================================================


class TestRawOptionMap:
    def _make_selector(self, raw_value: str):
        from custom_components.luxtronik2.select import LuxtronikModeSelector

        desc = LuxtronikSelectEntityDescription(
            key=SensorKey.TIMER_DHW_PROGRAM,
            device_key=DeviceKey.domestic_water,
            luxtronik_key=LuxParameter.P0405_TIMER_PROGRAM_DHW,
            options=["week", "weekday_weekend", "daily"],
            raw_option_map={"week": "week", "weekday_weekend": "5+2", "daily": "days"},
        )
        data = make_coordinator_data(
            parameters={"ID_Einst_SUBW_akt2": raw_value}
        )
        coord = _mock_coordinator(data)
        entity = LuxtronikModeSelector(
            _mock_entry(), coord, desc, DeviceKey.domestic_water
        )
        _patch_entity(entity)
        return entity, coord

    def test_options_are_the_ha_names(self):
        entity, _coord = self._make_selector("week")
        assert entity._attr_options == ["week", "weekday_weekend", "daily"]

    def test_raw_value_maps_to_ha_option(self):
        entity, _coord = self._make_selector("5+2")
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "weekday_weekend"

    @pytest.mark.asyncio
    async def test_selecting_option_writes_raw_value(self):
        entity, coord = self._make_selector("week")
        await entity.async_select_option("weekday_weekend")
        coord.async_write.assert_awaited_once_with("ID_Einst_SUBW_akt2", "5+2")

    def test_existing_selectors_keep_working_without_a_map(self):
        from custom_components.luxtronik2.select import LuxtronikModeSelector

        desc = LuxtronikSelectEntityDescription(
            key=SensorKey.DOMESTIC_WATER_MODE_SELECTOR,
            device_key=DeviceKey.domestic_water,
            luxtronik_key=LuxParameter.P0004_MODE_DHW,
            options=["Automatic", "Off"],
        )
        data = make_coordinator_data(parameters={"ID_Ba_Bw_akt": "Automatic"})
        entity = LuxtronikModeSelector(
            _mock_entry(), _mock_coordinator(data), desc, DeviceKey.domestic_water
        )
        _patch_entity(entity)
        entity._handle_coordinator_update()
        assert entity._attr_options == ["automatic", "off"]
        assert entity._attr_current_option == "automatic"
```

Add `LuxParameter` to the `custom_components.luxtronik2.const` import block at the
top of `tests/test_select.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_select.py::TestRawOptionMap -v`
Expected: FAIL with `AttributeError: TIMER_DHW_PROGRAM` (or an unexpected-keyword error for `raw_option_map`)

- [ ] **Step 3: Add the const entries**

In `custom_components/luxtronik2/const.py`, in `class LuxParameter`, next to the other DHW parameters:

```python
    P0405_TIMER_PROGRAM_DHW = "parameters.ID_Einst_SUBW_akt2"
```

In `class SensorKey`, directly above `TIMER_DHW_SCHEDULE_WEEK`:

```python
    TIMER_DHW_PROGRAM = "timer_dhw_program"
```

- [ ] **Step 4: Add the description field**

In `custom_components/luxtronik2/model.py`, in `LuxtronikSelectEntityDescription`:

```python
class LuxtronikSelectEntityDescription(
    LuxtronikEntityDescription,
    SelectEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik select entities."""

    platform = Platform.SELECT
    #: Maps the HA-facing option name to the raw value the device expects,
    #: for parameters whose raw values are not usable as HA options (e.g.
    #: the timer program's "5+2"). When unset, options are derived from the
    #: raw values as before.
    raw_option_map: dict[str, str] | None = None
```

- [ ] **Step 5: Honour the map in the selector**

In `custom_components/luxtronik2/select.py`, replace this block in `LuxtronikModeSelector.__init__`:

```python
        raw_options = list(options or description.options or [])
        self._option_to_raw = {
            _normalize_select_option(raw_option): raw_option
            for raw_option in raw_options
        }
        self._attr_options = list(self._option_to_raw)
```

with:

```python
        if description.raw_option_map:
            self._option_to_raw = dict(description.raw_option_map)
        else:
            raw_options = list(options or description.options or [])
            self._option_to_raw = {
                _normalize_select_option(raw_option): raw_option
                for raw_option in raw_options
            }
        self._attr_options = list(self._option_to_raw)
        self._raw_to_option = {
            _normalize_select_option(raw): option
            for option, raw in self._option_to_raw.items()
        }
```

and in `_handle_coordinator_update` replace:

```python
        current_raw = str(get_sensor_data(data, self._lux_parameter))
        current = _normalize_select_option(current_raw)
```

with:

```python
        current_raw = str(get_sensor_data(data, self._lux_parameter))
        normalized = _normalize_select_option(current_raw)
        current = self._raw_to_option.get(normalized, normalized)
```

- [ ] **Step 6: Add the predefined description**

In `custom_components/luxtronik2/select_entities_predefined.py`, add to `SELECT_ENTITIES`:

```python
    LuxtronikSelectEntityDescription(
        key=SK.TIMER_DHW_PROGRAM,
        device_key=DeviceKey.domestic_water,
        luxtronik_key=LuxParameter.P0405_TIMER_PROGRAM_DHW,
        entity_category=EntityCategory.CONFIG,
        options=timer_program_options,
        raw_option_map=TIMER_PROGRAM_RAW_OPTIONS,
    ),
```

and above `SELECT_ENTITIES`:

```python
# The device's raw values ("5+2") are not usable as HA option names, so the
# HA-facing names are mapped explicitly onto them.
TIMER_PROGRAM_RAW_OPTIONS: dict[str, str] = {
    "week": "week",
    "weekday_weekend": "5+2",
    "daily": "days",
}
timer_program_options: list[str] = list(TIMER_PROGRAM_RAW_OPTIONS)
```

- [ ] **Step 7: Run the select tests**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_select.py -v`
Expected: PASS

- [ ] **Step 8: Add the translations**

In each of the five `custom_components/luxtronik2/translations/*.json` files, add an
entry inside the `"select"` object (next to `"pv_mode_selector"`), using the exact
key `"timer_dhw_program"` and exactly the three state keys `week`,
`weekday_weekend`, `daily`:

`en.json`:

```json
            "timer_dhw_program": {
                "name": "Hot water timer program",
                "state": {
                    "week": "Whole week",
                    "weekday_weekend": "Weekdays + weekend",
                    "daily": "Per day"
                }
            },
```

`de.json`:

```json
            "timer_dhw_program": {
                "name": "Warmwasser Zeitprogramm",
                "state": {
                    "week": "Ganze Woche",
                    "weekday_weekend": "Werktage + Wochenende",
                    "daily": "Einzelne Tage"
                }
            },
```

`nl.json`:

```json
            "timer_dhw_program": {
                "name": "Warmwater tijdprogramma",
                "state": {
                    "week": "Hele week",
                    "weekday_weekend": "Werkdagen + weekend",
                    "daily": "Per dag"
                }
            },
```

`cs.json`:

```json
            "timer_dhw_program": {
                "name": "Časový program TUV",
                "state": {
                    "week": "Celý týden",
                    "weekday_weekend": "Pracovní dny + víkend",
                    "daily": "Jednotlivé dny"
                }
            },
```

`pl.json`:

```json
            "timer_dhw_program": {
                "name": "Program czasowy CWU",
                "state": {
                    "week": "Cały tydzień",
                    "weekday_weekend": "Dni robocze + weekend",
                    "daily": "Poszczególne dni"
                }
            },
```

- [ ] **Step 9: Run the translation-coverage and full test suite**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_translation_coverage.py -v`
Expected: PASS (all five locales carry the same entity key and state keys)

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest --cov=custom_components.luxtronik2 -q`
Expected: all pass, no coverage regression

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m codespell_lib custom_components/luxtronik2 tests`
Expected: no findings

- [ ] **Step 10: Lint, typecheck, commit**

```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff format custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2
git add custom_components/luxtronik2 tests/test_select.py
git commit -m "feat(select): ✨ expose the DHW timer program selector"
```

---

### Task 5: Verify against the live heat pump

**Files:** none (manual verification)

**Interfaces:**
- Consumes: everything from Tasks 1-4.

- [ ] **Step 1: Reload the integration on the live HA instance**

Restart HA (or reload the Luxtronik config entry) with the branch installed.

- [ ] **Step 2: Check the DHW device page**

Expected: exactly the schedule entities of the running program are listed as
normal entities; the others appear only under "+N hidden entities" (existing
install) or not at all (fresh install). None of them are unavailable.

- [ ] **Step 3: Switch the program from HA**

Set the new `select.<prefix>_timer_dhw_program` to `weekday_weekend`.
Expected: within one poll the week block disappears and the weekday + weekend
blocks appear, with their times read from the device.

- [ ] **Step 4: Switch back and confirm nothing was lost**

Set the select back to `week`.
Expected: the week block returns with the same entity_id it had before, and any
rename/area you set on it is still in place.

- [ ] **Step 5: Report the results**

Note anything that deviates; do not claim the feature works without having seen
steps 2-4 behave as described.

---

## Notes for the implementer

- `zip(..., strict=True)` requires the two lists to be built in the same order — they are, `to_add` and `entities` are parallel.
- `entry.async_create_task(hass, coro, eager_start=False)` is deliberate: the sync runs from a synchronous coordinator listener callback, and eager start would re-enter the coordinator's update path.
- Do not add `force_remove=True` to `entity.async_remove()` — that would delete the registry entry and defeat the whole design.
- The existing `LuxtronikTimerScheduleText.available` mode check stays: it covers the window between a coordinator update carrying a new mode and the scheduled add/remove task running.

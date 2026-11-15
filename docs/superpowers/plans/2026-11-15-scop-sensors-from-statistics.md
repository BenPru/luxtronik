# SCOP Sensors from Long-Term Statistics — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rolling 1-year (SCOP) and 30-day COP sensors for Heating, DHW and the whole unit, computed as Σheat / Σelectricity from Home Assistant's hourly long-term statistics of the heat pump's own energy counters, with the user's external power meter as the electricity source when one is configured.

**Architecture:** A pure function (`scop.py: compute_scop`) turns hourly statistics rows into results; a `ScopTracker` (same module) resolves the counters' entity IDs, queries the recorder once an hour and fans the results out to six `LuxtronikScopSensorEntity` instances. No new persistence: the history already lives in the recorder.

**Tech Stack:** Home Assistant recorder statistics API (`statistics_during_period`, `get_metadata`, `get_instance`), entity registry, `async_track_time_interval`, `async_at_started`.

**Spec:** [`docs/superpowers/specs/2026-08-06-true-scop-sensors-design.md`](../specs/2026-08-06-true-scop-sensors-design.md) — the "Update 2026-11-08" section (approach D) and the "Decision 2026-11-15" section.

## Global Constraints

- Branch `feat/scop-sensors` off `main`; commits `<type>(<scope>): <gitmoji> <description>`; never commit without the user's approval.
- Windows: `365` days (SCOP) and `30` days; minimum coverage `30` days and `7` days respectively.
- Glitch hour: any counter with `change < 0`, or `change > 1 and change > 0.5 × state`. A glitch hour is dropped for **all** counters.
- Counting starts at the first kept hour where `ΔP1136 + ΔP1137 > 0`.
- Units requested from the recorder: `{"energy": "kWh", "power": "kW"}`; period `"hour"`.
- Statistic ID = the counter's current entity_id, looked up in the entity registry by unique_id `f"sensor.{prefix}_{SensorKey}"` (prefix = `entry.data[CONF_HA_SENSOR_PREFIX]`).
- No cooling SCOP. Not created on twin units (`P1010 != 0`). Not created when `recorder` is not loaded.
- Values rounded to 2 decimals; `state_class=MEASUREMENT`, no unit.
- Translations in all five files (en/de/nl/cs/pl) — `test_translation_coverage.py` enforces lockstep.
- Every touched file stays at 100% coverage; basedpyright 0 errors; ruff check/format clean; codespell clean.

## Review Focus

1. **User renamed a counter entity** (e.g. `sensor.luxtronik_heat_energy_input` → `sensor.wp_kwh`) — the tracker must still find it through the registry; test in Task 2.
2. **External sensor without long-term statistics** (no `state_class`) — fall back to controller counters, `electricity_source: controller`, one warning, not one per hour; test in Task 2.
3. **Recorder query raises** (DB locked, migration running) — entities keep their last value, no exception escapes the timer, next hour retries; test in Task 2.
4. **Fresh install / recently enabled counters** — coverage below the minimum gives `unknown` with `coverage_days` still shown; test in Task 1.
5. **Config entry unload/reload** — the hourly timer and the start listener are cancelled; no refresh after unload; test in Task 2.

---

### Task 1: Pure SCOP computation

**Files:**
- Create: `custom_components/luxtronik2/scop.py`
- Test: `tests/test_scop.py`

**Interfaces:**
- Produces:
  - `class ScopCircuit(StrEnum)`: `heating = "heating"`, `domestic_water = "domestic_water"`, `total = "total"`
  - `@dataclass(frozen=True) class ScopInputs`: `heat_heating: str`, `heat_dhw: str`, `elec_heating: str`, `elec_dhw: str`, `elec_other: tuple[str, ...] = ()`, `external: str | None = None`, `external_kind: Literal["energy", "power"] | None = None`; property `statistic_ids -> set[str]` (all non-None IDs)
  - `@dataclass(frozen=True) class ScopResult`: `value: float | None`, `coverage_days: float`, `heat_kwh: float`, `electricity_kwh: float`, `electricity_source: Literal["controller", "external"]`, `window_start: datetime | None`
  - `def compute_scop(rows: Mapping[str, Sequence[Mapping[str, Any]]], inputs: ScopInputs, now: datetime, window_days: int, min_coverage_days: float) -> dict[ScopCircuit, ScopResult]`

`rows` is exactly what `statistics_during_period` returns: statistic_id → list of rows with `start` (float epoch seconds), `change`, `state`, `mean`.

Algorithm (the part the tests do not fully pin):

```
hours = keys `start` where every core id (heat_heating, heat_dhw, elec_heating, elec_dhw)
        has a row with change not None, and - when external is set - the external row has
        change (energy) / mean (power) not None. elec_other ids missing an hour count as 0.
drop glitch hours: any id with `state` in the row (counters, external energy) and
        change < 0 or (change > 1 and change > 0.5 * state)
drop hours before the first kept hour with Δelec_heating + Δelec_dhw > 0
keep hours with start >= (now - window_days).timestamp()
coverage_days = len(kept) / 24
heat:  heating Σheat_heating, dhw Σheat_dhw, total both
elec without external: heating Σelec_heating, dhw Σelec_dhw, total both
elec with external: E = Σchange (energy) or Σmean * 1 h (power);
        core = Σelec_heating + Σelec_dhw + Σelec_other
        heating E*Σelec_heating/core, dhw E*Σelec_dhw/core, total E*(Σelec_heating+Σelec_dhw)/core
value = round(heat / elec, 2) if coverage_days >= min_coverage_days and elec > 0 else None
window_start = datetime of first kept hour (UTC) or None
```

- [ ] **Step 1: Write the failing tests** in `tests/test_scop.py`, with a helper `_rows(hours, **per_id)` that builds `rows` for `hours` consecutive hours ending at `NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)` (each id → constant `change`, with a monotonically growing `state` starting at 100). Use `min_coverage_days=1` unless stated.

```python
def test_ratio_of_sums_without_external():
    # 48 h: heat_h 2.0, elec_h 0.5, heat_dhw 1.0, elec_dhw 0.25
    r = compute_scop(rows, INPUTS, NOW, 30, 1)
    assert r[ScopCircuit.heating].value == 4.0
    assert r[ScopCircuit.domestic_water].value == 4.0
    assert r[ScopCircuit.total].value == 4.0
    assert r[ScopCircuit.heating].coverage_days == 2.0
    assert r[ScopCircuit.heating].electricity_source == "controller"

def test_glitch_hour_dropped_for_all_counters():
    # one hour: heat_h change 1000, state 1000 -> that hour gone for every id
    assert r[ScopCircuit.heating].value == 4.0
    assert r[ScopCircuit.heating].coverage_days == 47 / 24

def test_negative_change_is_a_glitch(): ...          # elec_dhw change -5 in one hour -> hour dropped
def test_small_counter_jump_is_not_a_glitch(): ...   # change 0.9, state 1.0 -> kept (change <= 1)
def test_hours_before_first_electricity_change_ignored():
    # first 24 h elec 0 (heat 2.0), then 24 h normal -> coverage 1.0, value 4.0
def test_hour_missing_a_core_counter_is_dropped(): ...  # remove heat_dhw row for one hour -> coverage 47/24
def test_missing_other_counter_hour_counts_as_zero(): ...
def test_window_excludes_older_hours():
    # 40 days of data, window 30 -> coverage_days == 30.0
def test_below_min_coverage_returns_none_but_reports_coverage():
    r = compute_scop(rows_48h, INPUTS, NOW, 365, 30)
    assert r[ScopCircuit.heating].value is None
    assert r[ScopCircuit.heating].coverage_days == 2.0
def test_zero_electricity_returns_none(): ...         # dhw never runs -> dhw value None, heating fine
def test_external_power_split_by_controller_share():
    # 24 h: ext mean 1.0 kW, elec_h 0.3, elec_dhw 0.1, heat_h 2.0, heat_dhw 0.4
    assert r[ScopCircuit.heating].electricity_kwh == 18.0      # 24 * 0.75
    assert r[ScopCircuit.heating].value == round(48 / 18, 2)
    assert r[ScopCircuit.total].electricity_kwh == 24.0
    assert r[ScopCircuit.heating].electricity_source == "external"
def test_external_energy_uses_change(): ...           # kind "energy", change 1.0 -> same numbers as above
def test_external_split_excludes_cooling_and_pool():
    # elec_other cooling 0.1 -> core 0.5; heating 24*0.6, total 24*0.8
def test_external_hour_missing_drops_hour(): ...
def test_external_energy_glitch_drops_hour(): ...
def test_no_rows_at_all_returns_none_with_zero_coverage(): ...  # window_start None
def test_statistic_ids_skips_none(): ...              # ScopInputs.statistic_ids
```

- [ ] **Step 2: Run them to see them fail**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_scop.py -v`
Expected: collection error, `ModuleNotFoundError: custom_components.luxtronik2.scop`.

- [ ] **Step 3: Implement `ScopCircuit`, `ScopInputs`, `ScopResult`, `compute_scop` in `custom_components/luxtronik2/scop.py`** following the algorithm above. Module docstring: why ratio of sums (link the spec), why hourly, the glitch rule's origin (card PR #2, #856).

- [ ] **Step 4: Run the tests to see them pass**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_scop.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit** (after approval) `feat(sensor): ✨ compute windowed scop from hourly statistics rows` — include the spec and this plan.

---

### Task 2: `ScopTracker` — recorder query, entity lookup, hourly refresh

**Files:**
- Modify: `custom_components/luxtronik2/scop.py`
- Modify: `custom_components/luxtronik2/manifest.json` (`"after_dependencies": ["recorder"]`)
- Test: `tests/test_scop.py`

**Interfaces:**
- Consumes: Task 1's `ScopInputs`, `ScopResult`, `ScopCircuit`, `compute_scop`.
- Produces:
  - `SCOP_WINDOWS: dict[int, float] = {365: 30, 30: 7}` (window_days → min_coverage_days)
  - `type ScopKey = tuple[ScopCircuit, int]`
  - `class ScopTracker`:
    - `__init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None`
    - `results: dict[ScopKey, ScopResult]` (empty until the first refresh)
    - `def async_add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]` (returns remover)
    - `def async_start(self) -> None` — `async_at_started(hass, ...)` for the first refresh, `async_track_time_interval(hass, ..., timedelta(hours=1))`; both unsubscribers go to `entry.async_on_unload`
    - `async def async_refresh(self) -> None`

Behaviour:
- `_resolve_inputs() -> ScopInputs | None`: registry lookup `er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"sensor.{prefix}_{key}")` for `HEAT_AMOUNT_HEATING`, `DHW_HEAT_AMOUNT`, `HEAT_ENERGY_INPUT`, `DHW_ENERGY_INPUT` (required → `None` if any is missing) and `POOL_ENERGY_INPUT`, `COOLING_ENERGY_INPUT` (optional → `elec_other`). External ID from `entry.options.get(CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION, entry.data.get(...))`.
- External kind from `get_metadata(hass, statistic_ids={external})` run in the recorder executor: `has_sum` → `"energy"`, `mean_type != StatisticMeanType.NONE` → `"power"`, metadata missing → drop `external`, log a warning **once per tracker**.
- Query: `get_instance(hass).async_add_executor_job(statistics_during_period, hass, now - timedelta(days=max(SCOP_WINDOWS)), None, inputs.statistic_ids, "hour", {"energy": "kWh", "power": "kW"}, {"change", "state", "mean"})`.
- Any exception from the recorder: log at warning with `exc_info`, keep previous `results`, do not notify listeners.
- On success: `results = {(c, w): r for w, m in SCOP_WINDOWS.items() for c, r in compute_scop(rows, inputs, now, w, m).items()}`, then call each listener.

- [ ] **Step 1: Write the failing tests** (patch `custom_components.luxtronik2.scop.statistics_during_period`, `.get_metadata`, `.get_instance`; use the `hass` fixture and a real entity registry):

```python
async def test_refresh_resolves_renamed_counter_entities(hass): ...
    # register the four counters with unique_id sensor.luxtronik_<key> but entity_id sensor.wp_*;
    # assert statistics_during_period got {"sensor.wp_heat", ...} and period "hour"
async def test_refresh_fills_results_for_both_windows_and_notifies(hass): ...
    # 6 keys: (heating|domestic_water|total) x (365|30); listener called once
async def test_missing_required_counter_leaves_results_empty(hass): ...
async def test_optional_cooling_counter_goes_to_elec_other(hass): ...
async def test_external_power_sensor_detected_from_metadata(hass): ...   # mean_type ARITHMETIC -> "power"
async def test_external_energy_sensor_detected_from_metadata(hass): ...  # has_sum -> "energy"
async def test_external_without_statistics_falls_back_and_warns_once(hass, caplog): ...
    # two refreshes -> one warning; results' electricity_source == "controller"
async def test_recorder_error_keeps_previous_results(hass, caplog): ...
async def test_listener_remover_stops_notifications(hass): ...
async def test_start_schedules_hourly_and_unload_cancels(hass): ...
    # MockConfigEntry; async_fire_time_changed +1 h -> refresh; after entry unload -> no refresh
def test_manifest_after_dependencies_include_recorder(): ...
```

- [ ] **Step 2: Run them to see them fail**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_scop.py -v`
Expected: new tests FAIL (`ScopTracker` not defined).

- [ ] **Step 3: Implement `ScopTracker` and add `recorder` to `after_dependencies`.** Import the recorder functions at module level from `homeassistant.components.recorder` / `.statistics` so tests can patch them.

- [ ] **Step 4: Run the tests to see them pass**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_scop.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit** (after approval) `feat(sensor): ✨ query hourly statistics for scop once an hour`

---

### Task 3: Sensor entities, descriptions, translations, docs

**Files:**
- Modify: `custom_components/luxtronik2/const.py` (six `SensorKey` members)
- Modify: `custom_components/luxtronik2/model.py` (`LuxtronikScopSensorDescription`)
- Modify: `custom_components/luxtronik2/sensor_entities_predefined.py` (`SENSORS_SCOP`)
- Modify: `custom_components/luxtronik2/sensor.py` (`LuxtronikScopSensorEntity`, setup wiring)
- Modify: `custom_components/luxtronik2/translations/{en,de,nl,cs,pl}.json`
- Modify: `ADVANCED_FEATURES.md` (new section after "COP Calculation and the External Power Sensor")
- Test: `tests/test_scop_sensor.py`, `tests/test_predefined_entities.py`

**Interfaces:**
- Consumes: Task 2's `ScopTracker`, `ScopKey`, `SCOP_WINDOWS`; Task 1's `ScopCircuit`, `ScopResult`.
- Produces:
  - `SensorKey`: `SCOP_HEATING = "scop_heating"`, `SCOP_DHW = "scop_dhw"`, `SCOP = "scop"`, `COP_30D_HEATING = "cop_30d_heating"`, `COP_30D_DHW = "cop_30d_dhw"`, `COP_30D = "cop_30d"`
  - `LuxtronikScopSensorDescription(LuxtronikSensorDescription, SensorEntityDescription)`: `circuit: ScopCircuit = ScopCircuit.total`, `window_days: int = 365`
  - `LuxtronikScopSensorEntity(LuxtronikSensorEntity)`: `__init__(hass, entry, coordinator, description, device_info_ident, tracker: ScopTracker)`

Descriptions (`SENSORS_SCOP`), all `state_class=MEASUREMENT`, `icon="mdi:chart-line"`, `entity_category=None`, enabled by default:

| key | device_key | circuit | window_days | luxtronik_key | entity_active |
|---|---|---|---|---|---|
| SCOP_HEATING | heating | heating | 365 | P1136 | `((P1010, "== 0"), (P1136, "!= 0.0"))` |
| COP_30D_HEATING | heating | heating | 30 | P1136 | same |
| SCOP_DHW | domestic_water | domestic_water | 365 | P1137 | `((P1010, "== 0"), (P1137, "!= 0.0"))` |
| COP_30D_DHW | domestic_water | domestic_water | 30 | P1137 | same |
| SCOP | heatpump | total | 365 | P1136 | `((P1010, "== 0"), (P1136, "!= 0.0"), (P1137, "!= 0.0"))` |
| COP_30D | heatpump | total | 30 | P1136 | same |

`luxtronik_key` is set because `coordinator.entity_active` requires the entity's own register to be returned once a gate is declared; it names the electricity counter the ratio rests on.

Entity behaviour: `async_added_to_hass` registers `tracker.async_add_listener(self._handle_scop_update)` via `async_on_remove`; `_handle_coordinator_update` is a no-op apart from `async_write_ha_state()` (the value does not come from the poll); `_handle_scop_update` reads `tracker.results.get((circuit, window_days))` and sets `native_value = result.value` and attributes `coverage_days` (1 decimal), `heat_kwh`, `electricity_kwh` (1 decimal), `electricity_source`, `window_start` (ISO string or `None`). Before the first refresh: `native_value None`, no SCOP attributes. Add the attribute names to `SensorAttrKey` only if `recorder.py`'s exclusion should cover them (it should — they change hourly).

Setup: in `sensor.async_setup_entry`, only when `"recorder" in hass.config.components`: create one `ScopTracker(hass, entry)`, add the entities for descriptions passing `coordinator.entity_active`, then `tracker.async_start()` only if at least one was added.

Names (`entity.sensor.<key>.name`):

| key | en | de | nl | cs | pl |
|---|---|---|---|---|---|
| scop_heating / scop_dhw / scop | SCOP | JAZ | SCOP | SCOP | SCOP |
| cop_30d_heating / cop_30d_dhw / cop_30d | COP 30 days | Arbeitszahl 30 Tage | COP 30 dagen | COP 30 dní | COP 30 dni |

- [ ] **Step 1: Write the failing tests** in `tests/test_scop_sensor.py`:

```python
def test_value_and_attributes_from_tracker_result(): ...
    # result value 5.9, coverage 365.0, heat 16000.04, elec 2711.9, external -> state 5.9,
    # attrs coverage_days 365.0, heat_kwh 16000.0, electricity_kwh 2711.9, electricity_source "external"
def test_unknown_before_first_refresh(): ...
def test_unknown_below_min_coverage_keeps_coverage_attribute(): ...
def test_listener_registered_and_removed_with_entity(): ...
def test_coordinator_poll_does_not_change_value(): ...
async def test_setup_creates_six_entities_with_recorder(hass): ...
async def test_setup_creates_none_without_recorder(hass): ...
async def test_setup_skips_twin_units(hass): ...       # P1010 = 1
async def test_setup_skips_dhw_when_p1137_zero(hass): ...
```

and in `tests/test_predefined_entities.py` a test that every `SENSORS_SCOP` description declares `P1010 == 0` in `entity_active` and that its `(circuit, window_days)` pairs are unique and cover `ScopCircuit × SCOP_WINDOWS`.

- [ ] **Step 2: Run them to see them fail**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_scop_sensor.py tests/test_predefined_entities.py -v`
Expected: FAIL on missing `SensorKey.SCOP_HEATING` / `LuxtronikScopSensorEntity`.

- [ ] **Step 3: Implement keys, description, `SENSORS_SCOP`, entity, setup wiring and the five translation entries.**

- [ ] **Step 4: Document it in `ADVANCED_FEATURES.md`**: what the six sensors show, that they need the four counter sensors enabled and recorded (default), that values appear after 7 / 30 days of history, how the external meter is used and split, the `coverage_days` attribute, twin units and series 1 not covered. Link it from the existing "averaging COP" text.

- [ ] **Step 5: Run the tests to see them pass**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_scop_sensor.py tests/test_predefined_entities.py tests/test_translation_coverage.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit** (after approval) `feat(sensor): ✨ add rolling scop and 30-day cop sensors`

---

### Task 4: Full verification, review, live check

- [ ] **Step 1: Full checks** — all five commands from CLAUDE.md. Expected: pytest passes, `scop.py`/`sensor.py`/`model.py`/`const.py`/`sensor_entities_predefined.py` at 100%; basedpyright `0 errors`; ruff clean; codespell clean.
- [ ] **Step 2: Superpowers code review** (`superpowers:requesting-code-review` over `main..HEAD`); fix Critical/Important.
- [ ] **Step 3: Live check on the Pi** (deploy only after the user approves, `bash .claude/deploy-pi.sh`). Expected after the first hourly refresh: SCOP heating ≈ 6.44, DHW ≈ 3.94, whole unit ≈ 5.90 (the 2026-11-08 card figures; small drift from a week of new data and hourly vs daily glitch handling is fine, a difference > 0.2 is not). `coverage_days` ≈ 365 minus the dropped glitch hours. Those figures are controller-counter based; if the Pi's entry has an external power sensor configured, compare against `electricity_source` and expect different values.
- [ ] **Step 4: PR** per `.github/pull_request_template.md`, referencing #188.

# Code review remediation plan — 2026-07-18

Source: full architecture + HA-best-practices review of `custom_components/luxtronik2/` at commit `46b0c4b` (main). All quality gates were green at review time (784 tests, ruff clean, basedpyright 0 errors on HA 2026.4.3) — every issue below survived a green CI run, mostly because the test suite mocks Home Assistant instead of exercising it.

This document is written so that any AI model or contributor can pick up a single task without other context. Read the whole "How to work in this repo" section first, then jump to a task.

---

## How to work in this repo (read first)

- **Environment**: use the `py314` conda env by full path (it is NOT on PATH in a fresh shell):
  ```
  "C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest -q
  "C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff check custom_components/luxtronik2 tests
  "C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff format custom_components/luxtronik2 tests
  "C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2
  ```
- **Definition of done for every task**: basedpyright 0 errors, `ruff check` clean, `ruff format --check` clean, **full** test suite passes, coverage does not regress. Run coverage as `pytest --cov=custom_components.luxtronik2` — never scope `--cov` to a leaf submodule (it triggers a bcrypt/PyO3 re-init crash; see CLAUDE.md for the root cause).
- **Git rules**: never commit on `main` — create a branch `fix/<description>` or `feat/<description>` first, always starting from an up-to-date `origin/main` (`git fetch origin` then branch off `origin/main`) to prevent merge conflicts as much as possible. **Never run `git commit` without explicit user approval.** Commit format: `<type>(<scope>): <gitmoji> <description>` (lowercase imperative), e.g. `fix(base): 🐛 restore visibility-driven enabled default`.
- **Line numbers in this document** were verified against commit `46b0c4b` and will drift as fixes land. Always re-locate the code by the quoted snippet or symbol name, not the line number alone.
- **Tests-first**: for each behavioral fix, write a failing test that demonstrates the bug before changing the code (TDD). Existing tests live in `tests/`, one file per module (`tests/test_base.py`, `tests/test_sensor.py`, …).
- **Architecture primer**: every platform follows a three-file pattern — `<platform>_entities_predefined.py` (static description lists), `model.py` (description dataclasses), `<platform>.py` (setup + entity classes subclassing `LuxtronikEntity` from `base.py`). `coordinator.py` holds `LuxtronikCoordinator` (a `DataUpdateCoordinator`) that owns the single socket connection to the heat pump. `lux_overrides.py` monkey-patches the upstream `luxtronik` PyPI library once per process. Config entries store the coordinator in `entry.runtime_data` (typed alias `LuxtronikConfigEntry` in `__init__.py`).
- **This integration writes to real heating equipment.** Treat any change to the write path (`coordinator.async_write`, the `luxtronik2.write` service, number/select/switch/climate `set_*` methods) with extra care and extra tests.

### Suggested execution order

| Phase | Tasks | Theme |
|---|---|---|
| 1 | C1, I3 | Write safety (touches physical equipment) |
| 2 | C2, C3, I6 | Availability / enabled-default / restore plumbing |
| 3 | I11 | Integration-test harness (regression net for phase 2) |
| 4 | I1, I2, I3b, I4, I5, I7, I8, I9, I10 | HA best-practice alignment |
| 5 | M1–M12 | Cleanup / polish |

Each task is independently mergeable unless a dependency is stated. Do NOT batch multiple tasks into one branch/PR unless they are trivially related.

---

## CRITICAL

### C1 — `luxtronik2.write` service writes to an arbitrary heat pump

- **File**: `custom_components/luxtronik2/__init__.py` (~lines 141–148, inside `write_parameter`, registered in `setup_hass_services`)
- **Current code**:
  ```python
  # Find the first available coordinator
  for config_entry in hass.config_entries.async_entries(DOMAIN):
      if config_entry.state is ConfigEntryState.LOADED and hasattr(
          config_entry, "runtime_data"
      ):
          coordinator = config_entry.runtime_data
          await coordinator.async_write(parameter, value)
          return
  ```
- **What's wrong**: the service handler picks the *first* loaded config entry. With two or more heat pumps configured, a service call writes a parameter to whichever entry happens to be first — potentially the wrong physical device.
- **Why it matters**: this is a write to real heating equipment; wrong-target writes can change heating curves, temperatures, or operating modes on the wrong house/unit.
- **Fix**:
  1. Add an optional-but-validated target to `SERVICE_WRITE_SCHEMA` (defined near the top of `__init__.py`): accept `device_id` and/or `config_entry_id`. Keep backward compatibility: if exactly one entry is loaded and no target is given, use it (existing single-pump users must not break); if multiple entries are loaded and no target is given, raise `ServiceValidationError` with a new translation key (add it to ALL locale files, see the translations note in I-general below).
  2. Resolve `device_id` → config entry via `homeassistant.helpers.device_registry` (`dr.async_get(hass)`, look up the device, use `device.config_entries`).
  3. Update `custom_components/luxtronik2/services.yaml` so the UI offers a device selector.
  4. Tests: multi-entry scenario writing to the second entry; no-target + multi-entry raises; no-target + single entry still works.

### C2 — Visibility-driven `entity_registry_enabled_default` is dead code

- **Files**: `custom_components/luxtronik2/model.py` (~line 91) and `custom_components/luxtronik2/base.py` (~lines 76–80)
- **Current code** (`model.py`, in `LuxtronikEntityDescription`):
  ```python
  entity_registry_enabled_default: bool = True
  ```
  (`base.py`, in `LuxtronikEntity.__init__`):
  ```python
  if description.entity_registry_enabled_default is None:
      description = replace(
          description,
          entity_registry_enabled_default=coordinator.entity_visible(description),
      )
  ```
- **What's wrong**: the base class only computes the enabled-default from `coordinator.entity_visible(...)` when the description field is `None` — but the field is typed `bool = True` and no predefined description in any `*_entities_predefined.py` file ever sets it to `None` (only `tests/test_base.py` does). So the intended behavior "entities not visible on this heat pump model default to disabled in the registry" never happens in production.
- **Why it matters**: users get dozens of enabled entities their hardware doesn't support, cluttering the UI with `unknown` states.
- **Fix**:
  1. In `model.py`, change the field to `entity_registry_enabled_default: bool | None = None`. Note the dataclass inherits from HA's `EntityDescription` which declares this field as `bool` — a pyright ignore comment matching the existing style in `model.py` (`# pyright: ignore[reportIncompatibleVariableOverride]`) may be needed.
  2. Keep the `is None` resolution logic in `base.py` unchanged — it becomes live.
  3. Audit all `*_entities_predefined.py` files: descriptions that currently pass `entity_registry_enabled_default=False` explicitly must keep doing so (explicit `False` must win over visibility). Descriptions passing `=True` explicitly: decide per case whether they mean "always enabled even if invisible" (keep `True`) or were just restating the old default (change to omit → `None`). When unsure, keep the explicit value — behavior-preserving.
  4. Tests: a description with `visibility` set to a flag the fake coordinator reports as not visible ends up with `entity_registry_enabled_default == False` after `LuxtronikEntity.__init__`; explicit `True`/`False` are untouched.
- **Caution**: this changes which entities are enabled by default for NEW installs / newly-added entities. Existing registry entries are not affected (HA only applies the default at first registration). Mention this in the PR body.

### C3 — `_attr_available` is ignored on the SmartGrid sensor

- **File**: `custom_components/luxtronik2/sensor.py` (~lines 295–314, `_update_smart_grid_status` in the SmartGrid sensor class)
- **Current code**:
  ```python
  if not smartgrid_enabled or smartgrid_enabled in [False, 0, "false", "False"]:
      self._attr_available = False
      self._attr_native_value = None
  else:
      self._attr_available = True
  ```
- **What's wrong**: `CoordinatorEntity` defines `available` as a **property** (returning `coordinator.last_update_success`), and a property on the class always shadows the `_attr_available` instance attribute. Setting `self._attr_available` therefore has no effect — the sensor never becomes unavailable when SmartGrid is disabled; it just shows `unknown`.
- **Why it matters**: misleading UI state; also a template for a whole bug class — grep for other `_attr_available` writes in classes inheriting `LuxtronikEntity` and fix them the same way.
- **Fix**: override the property on the SmartGrid sensor class instead. There is a correct example already in the codebase — `custom_components/luxtronik2/text.py` (~lines 111–122) overrides `available` combining its own condition with `super().available`. Pattern:
  ```python
  @property
  def available(self) -> bool:
      return super().available and self._smart_grid_enabled
  ```
  where `_smart_grid_enabled` is a plain instance flag set in `_update_smart_grid_status` (replacing the `_attr_available` writes).
- **Tests**: with the coordinator's update successful, sensor is unavailable when P1030 SmartGrid switch is off and available when on. Note: a `MagicMock` hass can't verify this end-to-end (that's why it slipped through) — a real property-level unit test is fine, but the harness tests in I11 should cover it too.

---

## IMPORTANT

### I1 — Unique IDs are derived from entity IDs / the user-facing prefix

- **Files**: every platform module — e.g. `custom_components/luxtronik2/sensor.py` (~161–162), `number.py` (~96–97), `switch.py` (~85–86), `select.py` (~164–165); pattern looks like:
  ```python
  self.entity_id = f"{DOMAIN}.{prefix}_{description.key}"   # variations per platform
  self._attr_unique_id = self.entity_id
  ```
- **What's wrong**: HA guidance says unique IDs must be stable and never derived from entity IDs or user-configurable values (here `CONF_HA_SENSOR_PREFIX`). This design is the root cause of the v5–v9 migration treadmill in `__init__.py` (including the bug where a `binary_sensor.` prefix leaked into select unique_ids).
- **Fix** (this is a whole-release project, do it alone on its own branch):
  1. New unique-id scheme: `f"{coordinator.unique_id}_{description.key}"` — serial-number based, no domain, no prefix.
  2. Write ONE new config-entry migration (bump `VERSION` in `config_flow.py`, add a step in `async_migrate_entry` in `__init__.py` following the style of the existing v5–v9 steps) that rewrites every entity-registry entry from the old unique_id to the new scheme. Use `er.async_entries_for_config_entry(...)` and `entity_registry.async_update_entity(entity_id, new_unique_id=...)`. Guard against collisions (skip + warn if target unique_id already exists).
  3. The mapping old→new must handle every historical variant the previous migrations produced. Study `__init__.py` migrations v5–v9 carefully first and enumerate the old formats in a comment.
  4. Extensive tests: registry entries in each historical format migrate correctly; entity IDs (user-visible) must NOT change — only unique_ids.
- **Why it matters**: ends the recurring need for registry surgery on every rename, and makes unique_ids survive prefix changes.

### I2 — Deprecated `OptionsFlowWithConfigEntry`

- **File**: `custom_components/luxtronik2/config_flow.py` (~line 512, options-flow class; explicit constructor arg at ~509)
- **What's wrong**: HA is phasing out `OptionsFlowWithConfigEntry`; when removed, the options flow breaks.
- **Fix**: subclass plain `homeassistant.config_entries.OptionsFlow` instead; `self.config_entry` is auto-populated by core, so delete the constructor that passes the entry, and delete any `self._config_entry`/`self.options` usage that relied on the deprecated base (read the current class first; keep behavior identical). Update `async_get_options_flow` to `return LuxtronikOptionsFlowHandler()` (no arg).
- **Tests**: existing options-flow tests should keep passing unchanged.

### I3 — Confirm-after-write only logs; schedule edits do up to 10 serial full refreshes

- **File**: `custom_components/luxtronik2/coordinator.py` (~lines 115–134, `async_write`); `custom_components/luxtronik2/text.py` (~155–162, timer-schedule writes)
- **What's wrong** (two parts):
  1. After writing a parameter, the coordinator refreshes and reads the value back, but only *logs* the read-back — if the device rejected or clamped the write, the UI silently keeps the optimistic value until the next poll.
  2. A timer-schedule edit in `text.py` performs up to 10 sequential `async_write` calls, each triggering a full three-block refresh (parameters + calculations + visibilities) — slow and hammers the device.
- **Fix**:
  1. In `async_write`, after refresh, compare read-back vs written value; on mismatch raise `HomeAssistantError` (translated message; add the key to all locale files) so the UI surfaces the failure and the entity state re-syncs to the device's actual value. Be careful with type coercion in the comparison (the datatypes convert raw ints to floats/enums — compare post-conversion values, and allow equal-after-round for temperature datatypes with 0.1 steps).
  2. Add a batch-write method (e.g. `async_write_many(pairs: list[tuple[parameter, value]])`) that queues all writes then refreshes once. The vendored client in `custom_components/luxtronik2/lux_helper.py` (~311–327) already supports queuing multiple parameter writes before `.write()`. Convert `text.py`'s schedule write to use it.
- **Tests**: mismatch raises; match does not; batch write issues one refresh (assert refresh called once via mock).
- **Note**: CLAUDE.md already (incorrectly) claims "confirms the value stuck" — after this fix the doc becomes true; no doc change needed if you implement it, otherwise fix CLAUDE.md (see M12).

### I3b — Debounced writes (number/climate/water_heater) never surface write-confirmation failures

- **Files**: `custom_components/luxtronik2/number.py` (~lines 101–154, `_debouncer`/`async_set_native_value`/`_async_set_native_value`), `custom_components/luxtronik2/climate.py` (~lines 343–400, `_debouncer_set_temp`), `custom_components/luxtronik2/water_heater.py` (~lines 163–232, `_debouncer_set_temp`)
- **Discovered during**: task review of [[I3]] (spawned as a deferred follow-up rather than folded into I3, since fixing it properly means redesigning error handling across three platforms, not a one-line patch).
- **What's wrong**: all three platforms rate-limit writes via `homeassistant.helpers.debounce.Debouncer(cooldown=0.5, immediate=False, function=...)`. HA core's `Debouncer` wraps the scheduled (non-immediate) callback in `try/except Exception: self.logger.exception(...)` and never propagates the exception back to the original caller — `await self._debouncer.async_call()` returns as soon as the call is *scheduled*, not after the debounced function actually runs. Since I3 made `coordinator.async_write`/`async_write_many` raise `HomeAssistantError` (`write_confirmation_mismatch`) on a rejected/clamped write, and the write happens inside exactly these debounced callbacks (`number.py` `_async_set_native_value`, and the analogous methods in `climate.py`/`water_heater.py`), that error is now swallowed for these three platforms — only logged to the HA log, never surfaced to the UI/service-call caller.
- **Why it matters**: temperature-control entities (number sliders, climate thermostat, water heater target temp) are the ones most likely to hit device-side clamping/rejection, and they are exactly the platforms where I3's fix doesn't reach the user. The entity's displayed value does still self-correct on the next coordinator refresh (via the normal `CoordinatorEntity` update-listener path), so this is a UX/error-visibility gap, not a data-integrity one — but it undermines I3's stated goal ("so the UI surfaces the failure") for roughly half the write-path entity types.
- **Fix** (needs a design decision, not prescribed here):
  1. Survey how other HA integrations surface async, fire-and-forget failures from a debounced/rate-limited write (options include: an `ir.async_create_issue`/repair, a persistent notification, exposing the last write error as an entity attribute, or restructuring so only the *device write* is debounced while confirmation/exception propagation happens synchronously on the *next* call).
  2. Whatever approach is chosen, apply it consistently across `number.py`, `climate.py`, `water_heater.py` — do not solve it three different ways.
  3. Tests: simulate `coordinator.async_write`/`async_write_many` raising inside the debounced callback and assert the chosen surfacing mechanism fires (repair issue created / notification sent / attribute set — whatever was chosen).
- **Caution**: this touches the same real-equipment write path C1/I3 already flagged for extra care — do not remove or bypass the 0.5s debounce cooldown itself (it exists to avoid hammering the device during slider drags), only fix what happens to a write failure once it occurs.

### I4 — `number.py` overrides `state`, bypassing NumberEntity machinery

- **File**: `custom_components/luxtronik2/number.py` (~lines 194–196)
- **Current code**:
  ```python
  @property
  def state(self) -> str | float | None:
      return self._attr_native_value
  ```
- **What's wrong**: `NumberEntity.state` implements unit conversion (°C→°F for imperial users), display precision, and range validation. This override bypasses all of it — imperial users see raw °C numbers labeled °F.
- **Fix**: delete the override. Then run the full test suite; if any test fails, the test was asserting the broken behavior — fix the test/root cause, don't restore the override. Check git history (`git log -S "def state" -- custom_components/luxtronik2/number.py`) to see if it was added to work around something; address that instead.

### I5 — Update entity claims `INSTALL` but cannot install

- **File**: `custom_components/luxtronik2/update.py` (~lines 72–74)
- **Current code**:
  ```python
  _attr_supported_features: UpdateEntityFeature = (
      UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
  )
  ```
- **What's wrong**: no `async_install` is implemented, and the release notes even say "The Install button below has no function" (~line 166). Pressing Install in the UI raises `NotImplementedError`.
- **Fix**: remove `UpdateEntityFeature.INSTALL` (keep `RELEASE_NOTES`); update notifications still appear without it. Remove the "Install button has no function" sentence from the release-notes text. Adjust any tests asserting the flag.

### I6 — `base.py` restore path: early return + sentinel restore

- **File**: `custom_components/luxtronik2/base.py` (~lines 120–140, `async_added_to_hass`)
- **Current code**:
  ```python
  last_state = await self.async_get_last_state()
  if last_state is None:
      return
  self._attr_state = last_state.state
  ```
- **What's wrong** (two bugs):
  1. When there is no previous state (first add of an entity), the method returns early and skips everything after — including the dispatcher hookup / initial update logic further down in the method (read the full method to see what's skipped). First-time entities behave differently from restarted ones.
  2. `last_state.state` can be the literal strings `"unavailable"` or `"unknown"`, which get restored into `_attr_state`; `update.py` (~101–103) then reports that string as `installed_version`.
- **Fix**:
  1. Restructure so the restore block is conditional but the rest of the method always runs: `if last_state is not None: <restore block>` instead of the early return.
  2. Skip restoring when `last_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)` (import from `homeassistant.const`).
- **Tests**: entity added with no previous state still gets its post-restore setup (assert whatever the tail of the method does, e.g. dispatcher connect); restoring an `"unavailable"` state leaves `_attr_state` at its freshly-computed value.

### I7 — Status-text sensor reads sibling entities by hard-coded entity_id

- **File**: `custom_components/luxtronik2/sensor.py` (~lines 261–276)
- **What's wrong**: builds `sensor.{prefix}_status_time`, `_status_line_1`, `_status_line_2` entity_ids and reads them from `hass.states`. HA explicitly allows users to rename entities; after a rename the status text silently breaks. All underlying data is already in `coordinator.data`.
- **Fix**: compute the status text directly from `coordinator.data` via the same `LuxCalculation` keys the sibling sensors use (find their keys in `sensor_entities_predefined.py`), including the same formatting/translation the sibling sensors apply. The translation lookup used by those sensors is accessible on the coordinator — reuse it rather than `hass.states`.
- **Tests**: status text is correct with default entity_ids AND when the sibling entities have been renamed (or simply: no `hass.states.get` calls remain — assert via mock).

### I8 — Config flow: shared class-level state, blanket abort, no manual escape

- **File**: `custom_components/luxtronik2/config_flow.py`
- **Three sub-issues**:
  1. (~lines 50–51) `_all_devices` / `_available_devices` are class-level mutable lists — shared across concurrent flow instances (two users / discovery + manual simultaneously). Move them into `__init__` as instance attributes.
  2. (~lines 190–195) `async_step_user` wraps everything in `except Exception: return self.async_abort(reason="unknown")`. A transient network error kills the flow. Catch specific expected exceptions and re-show the form with `errors={"base": "cannot_connect"}` (key must exist in `strings.json` + all `translations/*.json`); keep a last-resort `except Exception` that logs with traceback but also re-shows the form rather than aborting.
  3. (~lines 152–188) When discovery finds unconfigured devices, the flow forces a selection among them — manual host entry is unreachable, so a pump on another subnet can't be added while any discovered pump is unconfigured. Add a "manual entry" option to the selection list that routes to the manual host form.
- **Tests**: two concurrent flows don't see each other's device lists; connection error re-shows form; manual option reachable when devices are discovered.

### I9 — Direct `ConfigEntry.disabled_by` mutation

- **File**: `custom_components/luxtronik2/config_flow.py` (~lines 287–290)
- **What's wrong**: assigns `legacy_entry.disabled_by = ...` directly. Works today but bypasses `hass.config_entries.async_set_disabled_by(entry_id, disabled_by)`, which persists the change and handles unload; core is progressively freezing ConfigEntry attributes.
- **Fix**: replace the direct assignment with `await hass.config_entries.async_set_disabled_by(legacy_entry.entry_id, <ConfigEntryDisabler or None>)`. Check the surrounding code for what value is being set and preserve it.

### I10 — Migration v1 requires a live device

- **File**: `custom_components/luxtronik2/__init__.py` (~lines 191–198, inside `async_migrate_entry`)
- **What's wrong**: the v1→v2 step calls `connect_and_get_coordinator(...)` to resolve the unique_id. If the heat pump is offline during an HA upgrade, the migration fails and the config entry goes into a migration-error state (worse than setup-retry: HA does not retry failed migrations automatically).
- **Fix**: make the migration a pure data transform. If the unique_id can't be derived from stored entry data alone, leave it unset/sentinel in the migration and resolve it lazily during `async_setup_entry` (where `ConfigEntryNotReady` gives automatic retries). Follow how later setup code already obtains `coordinator.unique_id`.
- **Tests**: migration succeeds with no network available (mock `connect_and_get_coordinator` to raise; migration must still return `True`).

### I11 — Add a thin harness-based integration-test layer

- **Files**: `tests/` (new file, e.g. `tests/test_setup_integration.py`), `tests/conftest.py`
- **What's wrong**: all 784 tests run against `MagicMock` hass objects and fake sensor containers; `pytest-homeassistant-custom-component` is already in `tests/requirements-dev.txt` but its real `hass` fixture is never used. Bugs C2, C3, I4 are exactly the class ("HA ignores this attribute / property shadows attribute") that mocks cannot catch. Also, substantive paths carry `# pragma: no cover`: `LuxtronikCoordinator.connect`, v1/v2 migrations, legacy migration, `date.py`/`text.py` `async_setup_entry`.
- **Fix**: add 5–10 tests using the real `hass` fixture from `pytest-homeassistant-custom-component` (use the `enable_custom_integrations` fixture to allow loading `custom_components/luxtronik2`). Mock only the socket layer (`lux_helper.Luxtronik` / the `Luxtronik` client class used by `connect_and_get_coordinator`), not HA. Minimum scenarios:
  1. `async_setup_entry` with a mocked client → entry is LOADED, expected entities exist in the registry with correct unique_ids and enabled/disabled defaults (regression net for C2).
  2. Failed refresh → entities report unavailable (regression net for C3-class bugs).
  3. A number entity `set_native_value` round-trip → client write called with converted raw value (regression net for I3/I4).
  4. Config entry unload → client disconnected, service unregistered when last entry unloads.
  5. A migration test running the real `async_migrate_entry` against a v1 entry (regression net for I10).
- **Caution**: keep the existing unit suite untouched — this is an additional layer. The harness tests will be slower; that's acceptable (with the plugin loaded, the existing 793-test suite goes from ~5s to ~18s because of the plugin's autouse fixtures — verified, all still pass).

#### I11 — Windows setup (empirically verified 2026-07-18 on this machine; follow exactly)

The harness DOES work on this Windows/py314 environment, but NOT out of the box. All of the following was verified by actually running it (HA 2026.4.3, Python 3.14.4, Windows 11):

1. **Install the matching plugin version** (pip changes no other packages — verified via `--dry-run`):
   ```
   "C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pip install "pytest-homeassistant-custom-component==0.13.324"
   ```
   The plugin pins an exact HA version per release; 0.13.324 matches the installed homeassistant 2026.4.3. If HA is ever upgraded in the env, re-resolve with `pip install --dry-run pytest-homeassistant-custom-component "homeassistant==<installed version>"`.

2. **WARNING — merely installing it breaks EVERY `pytest` run on Windows.** The package registers a `pytest11` entry point named `homeassistant` that auto-loads on all pytest runs and imports `homeassistant.runner`, which does `import fcntl` (Unix-only) → `ModuleNotFoundError` before any test collects. So the autoload MUST be blocked repo-wide: add `"-p", "no:homeassistant"` to `addopts` in `[tool.pytest.ini_options]` in `pyproject.toml` (create `addopts` if absent). This is platform-neutral: on Linux/CI the plugin is then loaded explicitly per step 3 instead of via autoload.

3. **Load the plugin explicitly from a repo-ROOT `conftest.py`** (pytest only allows `pytest_plugins` in the rootdir conftest — putting it in `tests/conftest.py` is an error). Create `conftest.py` at the repo root containing, in this order: the three Windows shims below (guarded by `if sys.platform == "win32":`), then `pytest_plugins = "pytest_homeassistant_custom_component.plugins"`. The shims are no-ops on Linux, so the same conftest works in CI.

4. **The three Windows shims** (all verified necessary, in import order):
   - **`fcntl` stub**: before the plugin imports, insert a fake module into `sys.modules["fcntl"]` with no-op `flock`/`lockf`/`fcntl`/`ioctl` and `LOCK_SH/LOCK_EX/LOCK_NB/LOCK_UN` constants. Safe because HA only uses `fcntl.flock` for a single-instance runtime lock never exercised by tests.
   - **`resource` stub**: same for `sys.modules["resource"]` with `RLIMIT_NOFILE = 7`, `RLIM_INFINITY = -1`, `getrlimit = lambda *a, **k: (8192, 8192)`, no-op `setrlimit`. HA uses it only to raise the fd limit at startup.
   - **`socket.socketpair` shim**: the plugin enables pytest-socket blocking (AF_UNIX allowed, hosts allowlist `127.0.0.1`). On Windows, `socket.socketpair()` is emulated with real AF_INET localhost sockets, and every asyncio event loop creates one internally (self-pipe) → `SocketBlockedError` on loop creation. Wrap `socket.socketpair`: if `socket.socket.__module__ == "pytest_socket"` (blocking active), call `pytest_socket.enable_socket()`, run the original socketpair, then in a `finally:` restore with `pytest_socket.socket_allow_hosts(["127.0.0.1"])` followed by `pytest_socket.disable_socket(allow_unix_socket=True)` (that order matters, and it must mirror the plugin's own config in `pytest_homeassistant_custom_component/plugins.py`). Do NOT implement this as try/except around a blocked call — the plugin counts `HASocketBlockedError` instantiations in its cleanup verification and will fail the test.

   A complete verified copy of these shims exists as a probe at `C:\Users\rhamm\AppData\Local\Temp\claude\c--Users-rhamm-OneDrive-Documenten-GitHub-luxtronik\89ba9c83-9136-4c66-8bcc-94463beb0980\scratchpad\phacc_probe\win_ha_compat.py` (session scratchpad — may be gone; the description above is self-sufficient).

5. **Verified end state**: with shims + `-p no:homeassistant` + explicit plugin load, (a) three probe tests using the real `hass` fixture pass on Windows, including a full `input_boolean` component setup with a blocking service call and `MockConfigEntry.add_to_hass`; (b) the ENTIRE existing suite passes unchanged (793 passed).

6. **Definition of done additions for this task**: plain `pytest` (no extra flags) must still pass on Windows after your changes, and CI on ubuntu must stay green (the explicit-load path replaces autoload there too). `asyncio_mode = "auto"` is already set in `pyproject.toml` — do not remove it; the async `hass` fixture depends on it.

7. **Known cosmetic issue**: the harness emits `DeprecationWarning`s about `asyncio.set_event_loop_policy` on Python 3.14 (removal slated for 3.16). Upstream HA/plugin problem — do not chase it; if warnings are promoted to errors anywhere, add a targeted `filterwarnings` ignore.

---

## MINOR (cleanup checklist)

Each of these is a small, independent change. Verify with the standard gates. Line refs approximate.

- **M1 Dead code**: delete `metaclass_resolver` (`model.py` ~187–194, unused); delete the inert throttling machinery — `should_update` (`base.py` ~159–163), `update_interval` fields (`model.py` ~125, ~156) and the ~20 `UPDATE_INTERVAL_*` assignments in `*_entities_predefined.py` — all call sites are commented out (`number.py` ~118, `switch.py` ~93, `binary_sensor.py` ~91), so it silently does nothing and misleads contributors; delete `update_reason_write` (`coordinator.py` ~71, set but never read); remove the `platform = Platform.AIR_QUALITY` placeholder (`model.py` ~74); remove `LuxtronikThermalDesinfectionDaySelector.async_update` (coordinator entities don't poll). If any deletion breaks a test, the test was testing dead code — delete the test too.
- **M2 DeviceInfo**: `coordinator.py` ~243–251 — remove `connections={(DOMAIN, ...)}` (the connections set is for real connection types like `CONNECTION_NETWORK_MAC`; `common.py` has `async_get_mac_address` if a MAC connection is wanted) and remove `suggested_area=""` (omit instead of empty string).
- **M3 Double state writes**: platform `_handle_coordinator_update` implementations call `self.async_write_ha_state()` AND then `super()._handle_coordinator_update()` which writes again (`sensor.py` ~189–190, `number.py` ~139–140, others). Remove the explicit write; let the base/super write once.
- **M4 `update_before_add`**: `async_add_entities([...], True)` in platform `async_setup_entry` functions triggers a pointless per-entity refresh request on CoordinatorEntities. Change to `async_add_entities([...])`.
- **M5 Log levels**: routine operations at INFO (`config_flow.py` ~124–158 per-discovery-step, `coordinator.py` ~86, ~129, `__init__.py` ~87, ~106) → DEBUG. HA guidance: integrations should be quiet at INFO.
- **M6 Private HA API**: `platform.platform_data.platform_translations` (`coordinator.py` ~222–224, `sensor.py` ~277–281) is internal HA API. At minimum wrap in `try/except AttributeError` with a logged fallback so an HA release change degrades gracefully instead of crashing.
- **M7 climate KeyError**: `climate.py` ~364–374 — `hvac_mode_mapping[mode]` / `HVAC_PRESET_MAPPING[mode]` raise `KeyError` on unexpected mode strings inside the coordinator listener. Use `.get(mode)` with a logged warning + safe fallback. Also rename the local `THERMOSTATS = ...` at ~220 that shadows the module-level constant.
- **M8 Naive timestamp**: `date.py` ~97 uses `datetime.fromtimestamp(value)` (server-local tz, naive). Use explicit tz handling like `sensor.py` ~375 does.
- **M9 Diagnostics redaction**: `diagnostics.py` ~19 redacts username/password (which don't exist in this integration's config) but emits serial number and host unredacted. Redact host, MAC and serial (`TO_REDACT` set), like core integrations.
- **M10 Discovery port**: `lux_helper.py` ~66 binds UDP 47808 (the standard BACnet port) on all interfaces — conflicts with BACnet tools on the same host. Bind only when actually discovering and close promptly; document the conflict. Also `Luxtronik.__del__` (`lux_helper.py` ~227–229) can perform socket ops during GC on the event-loop thread — guard with try/except and prefer explicit `disconnect()` (already called from coordinator shutdown; verify, then make `__del__` a no-op-on-error).
- **M11 Manifest**: `manifest.json` — the `http` dependency (~line 12) appears unused (no views/APIs registered): verify with a grep for `http` usage, then remove. Check `packaging>=26.2` requirement against HA core's pinned `packaging` constraint to avoid pip conflicts.
- **M12 CLAUDE.md drift**: CLAUDE.md says `async_write` "confirms the value stuck" — only true after I3 lands. If I3 is not done first, fix the wording; if I3 is done, no change needed.

---

## Verification recipe (run after every task)

```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff format --check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest --cov=custom_components.luxtronik2 -q
```

All four must be clean (0 lint findings, 0 format diffs, 0 type errors, all tests green, coverage not lower than before your change). Translations note: any new user-facing string (service errors, config-flow errors) must be added to `strings.json` AND every file in `custom_components/luxtronik2/translations/` — there is a cross-locale parity test that will fail otherwise.

## Status tracking

Mark tasks here as they land (edit this file in the same PR as the fix):

- [x] C1  - [x] C2  - [x] C3
- [ ] I1  - [x] I2  - [x] I3  - [ ] I3b  - [x] I4  - [x] I5  - [x] I6  - [x] I7  - [ ] I8  - [ ] I9  - [ ] I10  - [x] I11
- [x] M1  - [ ] M2  - [x] M3  - [x] M4  - [ ] M5  - [x] M6  - [x] M7  - [ ] M8  - [ ] M9  - [ ] M10  - [x] M11  - [ ] M12

Recovery note (2026-07-18): this file was found deleted mid-session with no git history (it was never committed) and was reconstructed from the content captured earlier in the same conversation. If you're reading this and something looks off versus the actual code state, re-verify line numbers/snippets against the current `main` rather than trusting this doc blindly — several tasks (I11, M3, M4) landed after the original review and their line refs above are stale by design (see the note at the top of this section).

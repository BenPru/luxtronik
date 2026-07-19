# External Power Sensor for COP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user configure an external Home Assistant power sensor (e.g. a Shelly smart plug) in the integration's options flow, and have `sensor.*_cop_heating`/`cop_dhw` use that sensor's value as their denominator instead of the heat pump's own (sometimes bogus) `current_power_consumption` reading — without changing what `current_power_consumption` itself displays.

**Architecture:** Mirrors the existing `ha_sensor_indoor_temperature` options-flow override (used today by `climate.py`) for a new field, `ha_sensor_current_power_consumption`. The override lives entirely in `LuxtronikCopSensorEntity` (`sensor.py`) — read once from the config entry in `__init__`, consulted in `_handle_coordinator_update` in place of the internal `C0268` reading when set. No changes to `LuxtronikCopSensorDescription` (the override is a per-config-entry runtime concern, not a static per-sensor definition).

**Tech Stack:** Home Assistant custom integration (Python 3.14, `homeassistant` + `luxtronik` libs), pytest, ruff, basedpyright. Env: `py314` conda env, invoked via full path per `CLAUDE.md`.

Full design rationale: `docs/superpowers/specs/2026-07-19-external-power-sensor-for-cop-design.md`.

## Global Constraints

- Branch: create and work on `feat/external-power-sensor-for-cop`, branched from `main`.
- Never commit automatically — stop after each commit step and let the human review before the next.
- `basedpyright custom_components/luxtronik2` must report 0 errors before any commit that touches non-test files.
- `ruff check` and `ruff format --check` must be clean before any commit.
- Full test suite (`pytest --cov=custom_components.luxtronik2`) must pass with no coverage regression before any commit.
- **Numerator (`current_heat_output`/`C0257`) is never overridden by this feature** — only the denominator (power consumption). Do not add a symmetric override for the numerator; out of scope.
- **Do not change what `sensor.*_current_power_consumption` displays.** This feature only changes what `LuxtronikCopSensorEntity` reads as its denominator internally — the diagnostic `current_power_consumption` sensor keeps showing the raw `C0268` value regardless of this option.
- **No live event tracking** (`async_track_state_change_event` or similar) — the external sensor's state is read via `hass.states.get()` inside the normal `_handle_coordinator_update` cycle, same polling model the existing `ha_sensor_indoor_temperature` override already uses. Do not add push-based updates.
- **No unit conversion** — assume the external sensor reports Watts, same unit as the internal `C0268` reading. Do not add kW-to-W conversion or similar.
- Configured-but-currently-invalid external sensor (unavailable/unknown/non-numeric/missing entity) → COP entity goes unavailable. It must NEVER silently fall back to the internal `C0268` reading when the option is configured — that reading is exactly what the user configured this feature to avoid trusting.
- codespell must be run from the repo root with relative paths (`custom_components/luxtronik2 tests`), never absolute paths — `pyproject.toml`'s `[tool.codespell]` `skip` rule for the translations directory only matches relative paths.
- Scope discipline: stay inside each task's declared File Structure. A prior branch on this repo (`feat/instant-cop-sensors`) had implementers wander into translation files out of scope, and once accidentally re-serialize an entire `cs.json` file via a JSON load/dump round-trip (turning a ~9-line change into ~1150 changed lines) — always edit JSON translation files with targeted text insertion, never by loading the whole file into a JSON library and re-dumping it.

## File Structure

- **Modify** `custom_components/luxtronik2/const.py` — add `CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION`.
- **Modify** `custom_components/luxtronik2/schema_helper.py` — add the new `EntitySelector` field to `build_options_schema`.
- **Modify** `custom_components/luxtronik2/config_flow.py` — read/save/clear the new option in `LuxtronikOptionsFlowHandler.async_step_user`.
- **Modify** `custom_components/luxtronik2/sensor.py` — `LuxtronikCopSensorEntity` gets a custom `__init__` (reads the option) and its `_handle_coordinator_update` branches on it for the denominator.
- **Modify** `custom_components/luxtronik2/translations/{en,de,nl,pl,cs}.json` — add `options.step.user.data`/`data_description` entries for the new field.
- **Modify** `tests/test_config_flow.py` — extend `TestOptionsFlow` with save/clear tests for the new field.
- **Modify** `tests/test_cop_sensor.py` — extend with tests for the external-sensor-configured behavior, and fix the shared `_mock_entry()` helper (see Task 2 — required so existing tests keep passing once `LuxtronikCopSensorEntity.__init__` starts reading `entry.options`).

## Task 1: Config constant, options schema, options flow, and its tests

**Files:**
- Modify: `custom_components/luxtronik2/const.py` (near `CONF_HA_SENSOR_INDOOR_TEMPERATURE`, currently at `const.py:75`)
- Modify: `custom_components/luxtronik2/schema_helper.py:1-68`
- Modify: `custom_components/luxtronik2/config_flow.py:18-31` (imports), `:486-544` (`LuxtronikOptionsFlowHandler`)
- Test: `tests/test_config_flow.py:592-703` (`TestOptionsFlow`)

**Interfaces:**
- Produces: `CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION: Final = "ha_sensor_current_power_consumption"` (a plain module-level string constant in `const.py`) — consumed by Task 2 (`sensor.py`) and Task 3 (translations).

- [ ] **Step 1: Add the config constant**

In `custom_components/luxtronik2/const.py`, find:

```python
CONF_HA_SENSOR_INDOOR_TEMPERATURE: Final = "ha_sensor_indoor_temperature"
```

Add immediately after it:

```python
CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION: Final = "ha_sensor_current_power_consumption"
```

- [ ] **Step 2: Add the options-flow schema field**

In `custom_components/luxtronik2/schema_helper.py`, find:

```python
from .const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_MAX_DATA_LENGTH,
    CONF_UPDATE_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL_OPTION,
    UPDATE_INTERVAL_OPTIONS,
)
```

Replace with:

```python
from .const import (
    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_MAX_DATA_LENGTH,
    CONF_UPDATE_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL_OPTION,
    UPDATE_INTERVAL_OPTIONS,
)
```

Then find:

```python
def build_options_schema(
    current_indoor_temp: str | None = None,
    current_interval: str | None = None,
) -> vol.Schema:
    interval_options = [
        selector.SelectOptionDict(value=k, label=k) for k in UPDATE_INTERVAL_OPTIONS
    ]
    return vol.Schema(
        {
            vol.Optional(
                CONF_HA_SENSOR_INDOOR_TEMPERATURE,
                default=current_indoor_temp,
                description={"suggested_value": current_indoor_temp},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="temperature"
                )
            ),
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=current_interval or DEFAULT_UPDATE_INTERVAL_OPTION,
                description={
                    "suggested_value": current_interval
                    or DEFAULT_UPDATE_INTERVAL_OPTION
                },
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=interval_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )
```

Replace with:

```python
def build_options_schema(
    current_indoor_temp: str | None = None,
    current_power_consumption_sensor: str | None = None,
    current_interval: str | None = None,
) -> vol.Schema:
    interval_options = [
        selector.SelectOptionDict(value=k, label=k) for k in UPDATE_INTERVAL_OPTIONS
    ]
    return vol.Schema(
        {
            vol.Optional(
                CONF_HA_SENSOR_INDOOR_TEMPERATURE,
                default=current_indoor_temp,
                description={"suggested_value": current_indoor_temp},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="temperature"
                )
            ),
            vol.Optional(
                CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
                default=current_power_consumption_sensor,
                description={
                    "suggested_value": current_power_consumption_sensor
                },
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=current_interval or DEFAULT_UPDATE_INTERVAL_OPTION,
                description={
                    "suggested_value": current_interval
                    or DEFAULT_UPDATE_INTERVAL_OPTION
                },
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=interval_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )
```

- [ ] **Step 3: Wire the new option into the options flow**

In `custom_components/luxtronik2/config_flow.py`, find:

```python
from .const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    CONF_UPDATE_INTERVAL,
    CONFIG_ENTRY_VERSION,
    DEFAULT_HOST,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL_OPTION,
    DOMAIN,
    LOGGER,
)
```

Replace with:

```python
from .const import (
    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    CONF_UPDATE_INTERVAL,
    CONFIG_ENTRY_VERSION,
    DEFAULT_HOST,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL_OPTION,
    DOMAIN,
    LOGGER,
)
```

Then find:

```python
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user options step."""
        try:
            if user_input is not None:
                new_options = dict(self.config_entry.options)
                value = user_input.get(CONF_HA_SENSOR_INDOOR_TEMPERATURE)
                if value:
                    new_options[CONF_HA_SENSOR_INDOOR_TEMPERATURE] = value
                elif (
                    CONF_HA_SENSOR_INDOOR_TEMPERATURE in new_options
                    or CONF_HA_SENSOR_INDOOR_TEMPERATURE in self.config_entry.data
                ):
                    new_options[CONF_HA_SENSOR_INDOOR_TEMPERATURE] = None

                update_interval = user_input.get(
                    CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_OPTION
                )
                new_options[CONF_UPDATE_INTERVAL] = update_interval

                return self.async_create_entry(title="", data=new_options)

            current_indoor_temp = self._get_value(CONF_HA_SENSOR_INDOOR_TEMPERATURE)
            current_interval = self._get_value(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_OPTION
            )

            return self.async_show_form(
                step_id="user",
                data_schema=build_options_schema(
                    current_indoor_temp=current_indoor_temp,
                    current_interval=current_interval,
                ),
                description_placeholders={"name": self.config_entry.title},
            )

        except Exception as err:
            LOGGER.error(
                "Could not handle LuxtronikOptionsFlowHandler.async_step_user: %s",
                user_input,
                exc_info=err,
            )
            return self.async_abort(reason="options_error")
```

Replace with:

```python
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user options step."""
        try:
            if user_input is not None:
                new_options = dict(self.config_entry.options)
                value = user_input.get(CONF_HA_SENSOR_INDOOR_TEMPERATURE)
                if value:
                    new_options[CONF_HA_SENSOR_INDOOR_TEMPERATURE] = value
                elif (
                    CONF_HA_SENSOR_INDOOR_TEMPERATURE in new_options
                    or CONF_HA_SENSOR_INDOOR_TEMPERATURE in self.config_entry.data
                ):
                    new_options[CONF_HA_SENSOR_INDOOR_TEMPERATURE] = None

                power_value = user_input.get(CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION)
                if power_value:
                    new_options[CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION] = power_value
                elif (
                    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION in new_options
                    or CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION
                    in self.config_entry.data
                ):
                    new_options[CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION] = None

                update_interval = user_input.get(
                    CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_OPTION
                )
                new_options[CONF_UPDATE_INTERVAL] = update_interval

                return self.async_create_entry(title="", data=new_options)

            current_indoor_temp = self._get_value(CONF_HA_SENSOR_INDOOR_TEMPERATURE)
            current_power_consumption_sensor = self._get_value(
                CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION
            )
            current_interval = self._get_value(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_OPTION
            )

            return self.async_show_form(
                step_id="user",
                data_schema=build_options_schema(
                    current_indoor_temp=current_indoor_temp,
                    current_power_consumption_sensor=current_power_consumption_sensor,
                    current_interval=current_interval,
                ),
                description_placeholders={"name": self.config_entry.title},
            )

        except Exception as err:
            LOGGER.error(
                "Could not handle LuxtronikOptionsFlowHandler.async_step_user: %s",
                user_input,
                exc_info=err,
            )
            return self.async_abort(reason="options_error")
```

- [ ] **Step 4: Write the failing tests**

In `tests/test_config_flow.py`, find the `CONF_HA_SENSOR_INDOOR_TEMPERATURE` import (top of file) and add `CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION` alongside it (same import line/block it currently comes from — check the existing import statement for `CONF_HA_SENSOR_INDOOR_TEMPERATURE` near the top of the file and add the new name to that same `from custom_components.luxtronik2.const import (...)` block, alphabetically).

Then, inside `class TestOptionsFlow` (`tests/test_config_flow.py:592-703`), add these two tests immediately after `test_step_user_clears_indoor_temp` (`tests/test_config_flow.py:648-660`):

```python
    @pytest.mark.asyncio
    async def test_step_user_saves_power_consumption_sensor(self):
        entry = MagicMock()
        entry.data = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}
        entry.options = {}
        entry.title = "Test HP"
        flow = _make_options_flow(entry)
        flow.hass = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        await flow.async_step_user(
            {CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION: "sensor.shelly_power"}
        )
        flow.async_create_entry.assert_called_once()
        call_kwargs = flow.async_create_entry.call_args[1]
        assert (
            call_kwargs["data"][CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION]
            == "sensor.shelly_power"
        )

    @pytest.mark.asyncio
    async def test_step_user_clears_power_consumption_sensor(self):
        entry = MagicMock()
        entry.data = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}
        entry.options = {CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION: "sensor.old_power"}
        entry.title = "Test HP"
        flow = _make_options_flow(entry)
        flow.hass = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        await flow.async_step_user({})
        flow.async_create_entry.assert_called_once()
        call_kwargs = flow.async_create_entry.call_args[1]
        assert (
            call_kwargs["data"].get(CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION) is None
        )
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_config_flow.py -k "power_consumption_sensor" -v`
Expected: `NameError` or `ImportError` for `CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION` (doesn't exist in `const.py` yet) — if you did Steps 1-3 before writing tests, this will instead FAIL with an assertion error since the const already exists but nothing reads it from `user_input` yet. Either failure mode is acceptable proof the test is meaningful; if implementing strictly TDD-first, do Step 4 before Steps 1-3 and expect the import error.

- [ ] **Step 6: Run tests to verify they pass**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_config_flow.py -v`
Expected: all tests in the file pass, including the 2 new ones.

- [ ] **Step 7: basedpyright + ruff**

Run:
```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff format --check custom_components/luxtronik2 tests
```
Expected: `0 errors`; ruff clean (run `ruff format` to fix if needed, then re-verify).

- [ ] **Step 8: Commit**

```bash
git add custom_components/luxtronik2/const.py custom_components/luxtronik2/schema_helper.py custom_components/luxtronik2/config_flow.py tests/test_config_flow.py
git commit -m "feat(config_flow): add external power sensor option for COP"
```

---

## Task 2: `LuxtronikCopSensorEntity` denominator override

**Files:**
- Modify: `custom_components/luxtronik2/sensor.py:1-40` (imports), `:397-440` (`LuxtronikCopSensorEntity`)
- Test: `tests/test_cop_sensor.py` (existing file from `feat/instant-cop-sensors`)

**Interfaces:**
- Consumes: `CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION` (Task 1).
- Produces: `LuxtronikCopSensorEntity._external_power_sensor_entity_id: str | None` — an instance attribute read once in `__init__`, consulted in `_handle_coordinator_update`. Not consumed by any later task.

**Regression risk — read before starting:** `tests/test_cop_sensor.py`'s `_mock_entry()` helper currently returns a `MagicMock()` with only `entry.data` set. `LuxtronikCopSensorEntity.__init__` will now call `entry.options.get(CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION, ...)` — on an unconfigured `MagicMock()`, `entry.options.get(...)` returns a *new truthy `MagicMock`*, not `None`, which would make every existing test in the file wrongly take the "external sensor configured" branch and fail. Step 1 below fixes `_mock_entry()` to set `entry.options = {}` (a real dict) before any other change, so the existing 5 tests keep passing throughout.

- [ ] **Step 1: Fix the test helper first (prevents spurious failures in later steps)**

In `tests/test_cop_sensor.py`, find:

```python
def _mock_entry():
    entry = MagicMock()
    entry.data = _ENTRY_DATA.copy()
    return entry
```

Replace with:

```python
def _mock_entry():
    entry = MagicMock()
    entry.data = _ENTRY_DATA.copy()
    entry.options = {}
    return entry
```

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_cop_sensor.py -v`
Expected: `5 passed` (unchanged — this step only makes the mock more realistic, doesn't change behavior yet).

- [ ] **Step 2: Write the failing tests**

In `tests/test_cop_sensor.py`, find the imports block:

```python
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxCalculation as LC,
    LuxOperationMode,
    SensorKey,
)
```

Replace with:

```python
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxCalculation as LC,
    LuxOperationMode,
    SensorKey,
)
```

Then add these tests inside `class TestCopSensorHandleCoordinatorUpdate` (after `test_computes_ratio_when_status_matches`):

```python
    def test_uses_external_power_sensor_when_configured(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,
                "Heat_Output": 6000,
                # Deliberately different from the external value below, to
                # prove the external sensor takes priority, not just that
                # it's "also read".
                "Unknown_Calculation_268": 999999,
            }
        )
        entry = _mock_entry()
        entry.options = {CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION: "sensor.shelly_power"}
        hass = MagicMock()
        external_state = MagicMock()
        external_state.state = "1500"
        hass.states.get.return_value = external_state
        coord = _mock_coordinator(data)
        description = _heating_cop_description()
        entity = LuxtronikCopSensorEntity(
            hass, entry, coord, description, DeviceKey.heating
        )
        entity.hass = hass
        entity.hass.config.time_zone = "UTC"
        entity.async_write_ha_state = MagicMock()

        entity._handle_coordinator_update(data)

        hass.states.get.assert_called_with("sensor.shelly_power")
        assert entity._attr_native_value == 4.0
        assert entity._attr_available is True

    def test_external_power_sensor_unavailable_makes_entity_unavailable(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,
                "Heat_Output": 6000,
                "Unknown_Calculation_268": 1500,
            }
        )
        entry = _mock_entry()
        entry.options = {CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION: "sensor.shelly_power"}
        hass = MagicMock()
        hass.states.get.return_value = None
        coord = _mock_coordinator(data)
        description = _heating_cop_description()
        entity = LuxtronikCopSensorEntity(
            hass, entry, coord, description, DeviceKey.heating
        )
        entity.hass = hass
        entity.hass.config.time_zone = "UTC"
        entity.async_write_ha_state = MagicMock()

        entity._handle_coordinator_update(data)

        assert entity._attr_native_value is None
        assert entity._attr_available is False

    def test_no_external_sensor_configured_uses_internal_value(self):
        # Regression guard: entry.options == {} (the _mock_entry() default)
        # must still take the internal C0268 path, unchanged from before
        # this feature existed.
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,
                "Heat_Output": 6000,
                "Unknown_Calculation_268": 1500,
            }
        )
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 4.0
        assert entity._attr_available is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_cop_sensor.py -v`
Expected: the 3 new tests FAIL (`AttributeError: 'LuxtronikCopSensorEntity' object has no attribute '_external_power_sensor_entity_id'` or similar — the entity doesn't read the option yet), the original 5 tests still PASS.

- [ ] **Step 4: Implement the override**

In `custom_components/luxtronik2/sensor.py`, find the imports:

```python
from .common import get_sensor_data, key_exists
from .const import (
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    LOGGER,
    DeviceKey,
    LuxCalculation as LC,
    LuxParameter as LP,
    LuxSmartGridStatus,
    SensorAttrKey as SA,
    SensorKey,
)
```

Replace with:

```python
from .common import get_sensor_data, key_exists, state_as_number_or_none
from .const import (
    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    LOGGER,
    DeviceKey,
    LuxCalculation as LC,
    LuxParameter as LP,
    LuxSmartGridStatus,
    SensorAttrKey as SA,
    SensorKey,
)
```

Then find the `LuxtronikCopSensorEntity` class:

```python
class LuxtronikCopSensorEntity(LuxtronikSensorEntity):
    """Instantaneous COP: current heat output divided by current power consumption.

    Only meaningful while the heat pump is actively serving the circuit this
    entity represents, so it goes unavailable outside that operating status
    rather than showing a stale or misleading ratio from a different mode.

    Reads C0080_STATUS through the normal (non-raw) get_sensor_data path,
    same as base.py's SWITCH_GAP formatter - this applies
    normalize_sensor_value()'s existing "heating but compressor not
    actually running -> no_request" reclassification (common.py:223-228),
    which is exactly the condition under which a COP reading would be
    meaningless anyway, so it's a useful extra gate, not just incidental.
    """

    entity_description: LuxtronikCopSensorDescription  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data if data is None else data
        if data is None:
            return

        descr = self.entity_description
        status = get_sensor_data(data, LC.C0080_STATUS)
        numerator = get_sensor_data(data, descr.numerator_key)
        denominator = get_sensor_data(data, descr.denominator_key)

        if (descr.required_status is not None and status != descr.required_status) or (
            not isinstance(numerator, (float, int))
            or not isinstance(denominator, (float, int))
            or denominator <= 0
            or numerator < 0
        ):
            self._attr_available = False
            self._attr_native_value = None
        else:
            self._attr_available = True
            self._attr_native_value = round(numerator / denominator, 2)

        self.async_write_ha_state()
```

Replace with:

```python
class LuxtronikCopSensorEntity(LuxtronikSensorEntity):
    """Instantaneous COP: current heat output divided by current power consumption.

    Only meaningful while the heat pump is actively serving the circuit this
    entity represents, so it goes unavailable outside that operating status
    rather than showing a stale or misleading ratio from a different mode.

    Reads C0080_STATUS through the normal (non-raw) get_sensor_data path,
    same as base.py's SWITCH_GAP formatter - this applies
    normalize_sensor_value()'s existing "heating but compressor not
    actually running -> no_request" reclassification (common.py:223-228),
    which is exactly the condition under which a COP reading would be
    meaningless anyway, so it's a useful extra gate, not just incidental.

    The denominator (power consumption) can be sourced from an external HA
    sensor instead of the heat pump's own (sometimes inaccurate)
    current_power_consumption reading, if the user configured one via
    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION in the options flow - same
    pattern climate.py already uses for the indoor-temperature override.
    Only the denominator is overridable this way; the numerator
    (current_heat_output) always comes from the heat pump.
    """

    entity_description: LuxtronikCopSensorDescription  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikCopSensorDescription,
        device_info_ident: DeviceKey,
    ) -> None:
        """Init Luxtronik COP Sensor."""
        super().__init__(hass, entry, coordinator, description, device_info_ident)
        self._external_power_sensor_entity_id: str | None = entry.options.get(
            CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
            entry.data.get(CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION),
        )

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data if data is None else data
        if data is None:
            return

        descr = self.entity_description
        status = get_sensor_data(data, LC.C0080_STATUS)
        numerator = get_sensor_data(data, descr.numerator_key)

        if self._external_power_sensor_entity_id:
            external_state = self.hass.states.get(self._external_power_sensor_entity_id)
            denominator = (
                state_as_number_or_none(external_state)
                if external_state is not None
                else None
            )
        else:
            denominator = get_sensor_data(data, descr.denominator_key)

        if (descr.required_status is not None and status != descr.required_status) or (
            not isinstance(numerator, (float, int))
            or not isinstance(denominator, (float, int))
            or denominator <= 0
            or numerator < 0
        ):
            self._attr_available = False
            self._attr_native_value = None
        else:
            self._attr_available = True
            self._attr_native_value = round(numerator / denominator, 2)

        self.async_write_ha_state()
```

Note: `LuxtronikSensorEntity.__init__` (the base class) already has the exact same `(hass, entry, coordinator, description, device_info_ident)` signature and already imports `HomeAssistant`/`ConfigEntry`/`LuxtronikCoordinator` at module level in `sensor.py` — no new imports needed for the `__init__` signature itself, only the two named in Step 4's import-block edit above (`CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION`, `state_as_number_or_none`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_cop_sensor.py -v`
Expected: `8 passed` (the original 5 plus the 3 new ones).

- [ ] **Step 6: basedpyright + ruff**

Run:
```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff format --check custom_components/luxtronik2 tests
```
Expected: `0 errors`; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add custom_components/luxtronik2/sensor.py tests/test_cop_sensor.py
git commit -m "feat(sensor): use external power sensor for COP denominator when configured"
```

---

## Task 3: Translations (all 5 locales)

**Files:**
- Modify: `custom_components/luxtronik2/translations/en.json`
- Modify: `custom_components/luxtronik2/translations/de.json`
- Modify: `custom_components/luxtronik2/translations/nl.json`
- Modify: `custom_components/luxtronik2/translations/pl.json`
- Modify: `custom_components/luxtronik2/translations/cs.json`

**Interfaces:**
- Consumes: `CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION` (Task 1) — this is an options-flow field key, not a `SensorKey`, so it is **not** covered by `tests/test_translation_coverage.py` (that test only scans `*_entities_predefined.py` files for `SensorKey` references — options-flow fields are a separate, unenforced translation surface, same as `ha_sensor_indoor_temperature` itself). Still add it to all 5 locales for consistency and so English-only users aren't the only ones who see a label.
- Produces: nothing consumed by later tasks.

**Scope discipline:** this task only adds JSON content next to the existing `ha_sensor_indoor_temperature` entries. Use targeted text insertion (Edit tool), never load-and-redump a whole file with a JSON library — see Global Constraints.

- [ ] **Step 1: en.json**

In `custom_components/luxtronik2/translations/en.json`, find the `options.step.user.data` block containing:

```json
                "data": {
                    "ha_sensor_indoor_temperature": "Sensor ID for the indoor temperature",
                    "update_interval": "Update interval"
                },
```

Replace with:

```json
                "data": {
                    "ha_sensor_indoor_temperature": "Sensor ID for the indoor temperature",
                    "ha_sensor_current_power_consumption": "Sensor ID for the current power consumption",
                    "update_interval": "Update interval"
                },
```

Then find the matching `data_description` block:

```json
                "data_description": {
                    "ha_sensor_indoor_temperature": "A thermostat for heating control is created in Home Assistant. The actual temperature for this is set by a Home Assistant sensor.\nIf Luxtronik is connected to a hardware room thermostat, then this field should be left empty.",
                    "update_interval": "How often the heat pump should be queried for new data."
                }
```

(Exact English wording of `update_interval`'s description may differ slightly from what's shown above — match whatever is actually adjacent to `ha_sensor_indoor_temperature` in the real file; the important part is inserting the new key between them or right after `ha_sensor_indoor_temperature`.)

Replace with (adding the new key right after `ha_sensor_indoor_temperature`, keeping whatever `update_interval` text was already there):

```json
                "data_description": {
                    "ha_sensor_indoor_temperature": "A thermostat for heating control is created in Home Assistant. The actual temperature for this is set by a Home Assistant sensor.\nIf Luxtronik is connected to a hardware room thermostat, then this field should be left empty.",
                    "ha_sensor_current_power_consumption": "If the heat pump's built-in current power consumption reading is inaccurate, an external Home Assistant power sensor (e.g. a smart plug) can be used instead for the Heating/DHW COP calculations. This does not change what the Current power consumption sensor itself displays.\nLeave empty to use the heat pump's built-in reading.",
                    "update_interval": "How often the heat pump should be queried for new data."
                }
```

- [ ] **Step 2: de.json / nl.json / pl.json / cs.json**

Repeat Step 1's two insertions (same JSON keys `ha_sensor_current_power_consumption` in both `data` and `data_description`) in each of `de.json`, `nl.json`, `pl.json`, `cs.json`, right after that locale's own `ha_sensor_indoor_temperature` entries in the `options.step.user.data`/`data_description` blocks. Translate the label/description into each locale's language, matching the tone and phrasing style already used for the neighboring `ha_sensor_indoor_temperature` entries in that same file. Use each file's existing indentation and `\uXXXX`-escaping convention for any non-ASCII characters — do not change how any other line in these files is encoded.

- [ ] **Step 3: Validate all JSON files parse AND diffs are minimal**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -c "import json; [json.load(open(f'custom_components/luxtronik2/translations/{l}.json', encoding='utf-8')) for l in ['en','de','nl','pl','cs']]; print('ok')"`
Expected: `ok`

Then run `git diff --stat -- custom_components/luxtronik2/translations/` and confirm each of the 5 files shows roughly 2-4 changed lines (one line added to `data`, one line added to `data_description`) — if any file shows dramatically more, stop and investigate (signature of the cs.json-style whole-file reformatting mishap from a prior branch).

- [ ] **Step 4: Run the full test suite**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest -q`
Expected: all tests pass (no translation-coverage test is affected by this task, per the Interfaces note above, but run the full suite anyway to catch anything unexpected).

- [ ] **Step 5: Commit**

```bash
git add custom_components/luxtronik2/translations
git commit -m "feat(translations): add ha_sensor_current_power_consumption option labels"
```

---

## Task 4: Full verification

- [ ] **Step 1: Full test suite with coverage**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest --cov=custom_components.luxtronik2 --cov-report=term-missing -q`
Expected: all tests pass, coverage not lower than before this branch started.

- [ ] **Step 2: codespell**

Run from the repo root (relative paths, so `pyproject.toml`'s translations-skip rule applies):
`"C:\Users\rhamm\anaconda3\envs\py314\Scripts\codespell.exe" custom_components/luxtronik2 tests`
Expected: no output.

- [ ] **Step 3: Manual sanity check (optional but recommended)**

In a real or mocked HA instance: open the integration's options flow, configure a `sensor.*` power entity (e.g. an existing test/dummy power sensor), save, and confirm `sensor.*_cop_heating`/`cop_dhw` start reflecting that entity's state as their denominator instead of the internal reading — then clear the option and confirm they revert to the internal `current_power_consumption` reading.

## Self-Review Notes

- **Spec coverage:** options-flow field (✅ Task 1), COP entity override with correct fallback semantics (✅ Task 2), unavailable-not-fallback on bad external state (✅ Task 2, covered by `test_external_power_sensor_unavailable_makes_entity_unavailable`), translations (✅ Task 3), `current_power_consumption` sensor itself unchanged (✅ — no task touches its own description or entity class), no numerator override (✅ — Task 2's diff never touches `numerator`).
- **Regression risk called out explicitly:** Task 2 Step 1 fixes `_mock_entry()` before any behavior change, specifically to prevent the existing 5 tests from silently breaking once `__init__` starts reading `entry.options`.
- **No placeholders:** every step has literal file content/diffs; the one exception (Task 3 Step 1's parenthetical about `update_interval`'s exact adjacent text) is flagged explicitly as "match what's actually there," not left ambiguous about what to add or where.

# Instantaneous COP Sensors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three native, regular (non-diagnostic) sensors — Heating COP, DHW COP, Cooling COP — that compute an instantaneous coefficient of performance from two Luxtronik calculations the integration already exposes (`current_heat_output` / `current_power_consumption`), with no external power meter (e.g. Shelly plug) required.

**Architecture:** A new `LuxtronikCopSensorDescription` (subclass of `LuxtronikSensorDescription`) carries `numerator_key`/`denominator_key`/`required_status` instead of a single `luxtronik_key`. A new `LuxtronikCopSensorEntity` (subclass of `LuxtronikSensorEntity`) reads both raw values plus the heat pump's live operating status (`C0080_STATUS`) every coordinator update, and only publishes a value while the status matches the entity's circuit (heating/domestic_water/cooling) — otherwise it goes `unavailable`. This mirrors the existing `LuxtronikStatusSensorEntity` pattern of a sensor computed from multiple coordinator values rather than one raw key.

**Tech Stack:** Home Assistant custom integration (Python 3.14, `homeassistant` + `luxtronik` libs), pytest, ruff, basedpyright. Env: `py314` conda env, invoked via full path per `CLAUDE.md`.

## Global Constraints

- Branch: create and work on `feat/instant-cop-sensors`, branched from `main` (do not reuse `fix/error-reason-cause-remedy-translations`).
- Never commit automatically — stop after each commit step and let the human review before the next.
- `basedpyright custom_components/luxtronik2` must report 0 errors before any commit that touches non-test files.
- `ruff check` and `ruff format --check` must be clean before any commit.
- Full test suite (`pytest --cov=custom_components.luxtronik2`) must pass with no coverage regression before any commit.
- New sensors are enabled by default (`entity_registry_enabled_default` left at its default `True`) and are regular sensors, not diagnostics (no `entity_category` set — leave it at its default `None`), unlike `current_heat_output`/`current_power_consumption` which stay disabled-by-default diagnostics.
- New sensors are `state_class=SensorStateClass.MEASUREMENT`, no `device_class` (HA has no native COP device class) and no `native_unit_of_measurement` (dimensionless ratio).
- Every `SensorKey` added to `sensor_entities_predefined.py` must get a matching `entity.sensor.<key>` block in **all five** locale files (`en.json`, `de.json`, `nl.json`, `pl.json`, `cs.json`) — enforced by `tests/test_translation_coverage.py::test_all_referenced_entity_keys_have_translations`. This exact class of bug (missing `en.json` entries) is what commit `f9b4e61` fixed for `error_reason`/`switchoff_reason` — don't repeat it.
- `current_power_consumption` (`LC.C0268`) is exposed via a best-effort library mapping (`Unknown_Calculation_268` upstream, not a documented field) with a *commented-out* firmware-version gate (`sensor_entities_predefined.py:448`). Do not silently assume it's populated — the entity setup already only adds entities whose backing keys exist in `coordinator.data` (`key_exists`), so on heat pumps where 268 is genuinely absent, the COP entities simply won't be created. Do not re-enable the commented-out firmware gate as part of this plan — that's a separate, unverified change or the maintainer would have already flagped it in review; if the user wants it revisited, that's a follow-up.

## File Structure

- **Modify** `custom_components/luxtronik2/const.py` — add `SensorKey.COP_HEATING`, `COP_DHW`, `COP_COOLING`.
- **Modify** `custom_components/luxtronik2/model.py` — add `LuxtronikCopSensorDescription` dataclass.
- **Modify** `custom_components/luxtronik2/sensor_entities_predefined.py` — add `SENSORS_COP: list[LuxtronikCopSensorDescription]`.
- **Modify** `custom_components/luxtronik2/sensor.py` — add `LuxtronikCopSensorEntity` class + a third `async_add_entities(...)` block in `async_setup_entry`.
- **Modify** `custom_components/luxtronik2/translations/{en,de,nl,pl,cs}.json` — add `entity.sensor.cop_heating/cop_dhw/cop_cooling` name blocks.
- **Modify** `custom_components/luxtronik2/icons.json` — add icons for the three new keys (cosmetic, not test-gated).
- **Create** `tests/test_cop_sensor.py` — unit tests for `LuxtronikCopSensorEntity._handle_coordinator_update`.

## Task 1: `SensorKey` enum members

**Files:**
- Modify: `custom_components/luxtronik2/const.py:783-789`

**Interfaces:**
- Produces: `SensorKey.COP_HEATING`, `SensorKey.COP_DHW`, `SensorKey.COP_COOLING` — string enum members, values `"cop_heating"`, `"cop_dhw"`, `"cop_cooling"`.

- [ ] **Step 1: Add the enum members**

In `custom_components/luxtronik2/const.py`, find:

```python
    HEAT_AMOUNT_HEATING = "heat_amount_heating"
    HEAT_AMOUNT_FLOW_RATE = "heat_amount_flow_rate"
    HEAT_SOURCE_FLOW_RATE = "heat_source_flow_rate"
    DHW_HEAT_AMOUNT = "dhw_heat_amount"
    HEAT_ENERGY_INPUT = "heat_energy_input"
    DHW_ENERGY_INPUT = "dhw_energy_input"
    COOLING_ENERGY_INPUT = "cooling_energy_input"
```

Replace with:

```python
    HEAT_AMOUNT_HEATING = "heat_amount_heating"
    HEAT_AMOUNT_FLOW_RATE = "heat_amount_flow_rate"
    HEAT_SOURCE_FLOW_RATE = "heat_source_flow_rate"
    DHW_HEAT_AMOUNT = "dhw_heat_amount"
    HEAT_ENERGY_INPUT = "heat_energy_input"
    DHW_ENERGY_INPUT = "dhw_energy_input"
    COOLING_ENERGY_INPUT = "cooling_energy_input"
    COP_HEATING = "cop_heating"
    COP_DHW = "cop_dhw"
    COP_COOLING = "cop_cooling"
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -c "from custom_components.luxtronik2.const import SensorKey; print(SensorKey.COP_HEATING, SensorKey.COP_DHW, SensorKey.COP_COOLING)"`
Expected: `SensorKey.COP_HEATING SensorKey.COP_DHW SensorKey.COP_COOLING` (or equivalent repr), no traceback.

- [ ] **Step 3: Commit**

```bash
git add custom_components/luxtronik2/const.py
git commit -m "feat(const): add COP_HEATING/COP_DHW/COP_COOLING sensor keys"
```

---

## Task 2: `LuxtronikCopSensorDescription` model

**Files:**
- Modify: `custom_components/luxtronik2/model.py:107-115` (right after `LuxtronikIndexSensorDescription`)

**Interfaces:**
- Consumes: `LuxtronikSensorDescription` (base class, `model.py:95-104`), `LuxCalculation`, `LuxOperationMode` (already imported in `model.py`).
- Produces: `LuxtronikCopSensorDescription` with fields `numerator_key: LuxCalculation`, `denominator_key: LuxCalculation`, `required_status: LuxOperationMode | None`.

- [ ] **Step 1: Add the dataclass**

In `custom_components/luxtronik2/model.py`, find:

```python
class LuxtronikIndexSensorDescription(  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    LuxtronikSensorDescription,
    SensorEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik index sensor entities."""

    luxtronik_key_timestamp: LuxParameter | LuxCalculation = LuxParameter.UNSET
```

Add immediately after it (still before the `class LuxtronikNumberDescription` block):

```python


class LuxtronikCopSensorDescription(  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    LuxtronikSensorDescription,
    SensorEntityDescription,
    frozen_or_thawed=True,
):
    """Class describing Luxtronik instantaneous COP sensor entities.

    Unlike a plain sensor, the displayed value is a ratio of two other
    coordinator values (numerator_key / denominator_key), only considered
    valid while the heat pump's live operating status equals
    required_status. luxtronik_key is intentionally left at its UNSET
    default, same convention as LuxtronikTimerScheduleTextDescription.
    """

    numerator_key: LuxCalculation = LuxCalculation.UNSET
    denominator_key: LuxCalculation = LuxCalculation.UNSET
    required_status: LuxOperationMode | None = None
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -c "from custom_components.luxtronik2.model import LuxtronikCopSensorDescription; print(LuxtronikCopSensorDescription)"`
Expected: prints the class, no traceback.

- [ ] **Step 3: basedpyright check**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2/model.py`
Expected: `0 errors`

- [ ] **Step 4: Commit**

```bash
git add custom_components/luxtronik2/model.py
git commit -m "feat(model): add LuxtronikCopSensorDescription"
```

---

## Task 3: `SENSORS_COP` predefined entities

**Files:**
- Modify: `custom_components/luxtronik2/sensor_entities_predefined.py:35-39` (imports), append new list at end of file (after line 719, before `# endregion Cooling` closes — actually insert right after the cooling region, see below)

**Interfaces:**
- Consumes: `LuxtronikCopSensorDescription` (Task 2), `SensorKey.COP_HEATING/COP_DHW/COP_COOLING` (Task 1), `LC.C0257_CURRENT_HEAT_OUTPUT`, `LC.C0268_CURRENT_POWER_CONSUMPTION`, `LuxOperationMode.heating/domestic_water/cooling`, `DeviceKey.heating/domestic_water/cooling`.
- Produces: `SENSORS_COP: list[LuxtronikCopSensorDescription]` — consumed by Task 4 (`sensor.py`).

- [ ] **Step 1: Import the new description class**

In `custom_components/luxtronik2/sensor_entities_predefined.py`, find:

```python
from .model import (
    LuxtronikEntityAttributeDescription as attr,
    LuxtronikIndexSensorDescription as descr_index,
    LuxtronikSensorDescription as descr,
)
```

Replace with:

```python
from .model import (
    LuxtronikCopSensorDescription as cop_descr,
    LuxtronikEntityAttributeDescription as attr,
    LuxtronikIndexSensorDescription as descr_index,
    LuxtronikSensorDescription as descr,
)
```

- [ ] **Step 2: Add the `SENSORS_COP` list**

At the end of the file (after the `# endregion Cooling` line that follows the `COOLING_ENERGY_INPUT` entry, i.e. after line 719), append:

```python

# region COP (instantaneous, no external meter)
SENSORS_COP: list[cop_descr] = [
    cop_descr(
        key=SensorKey.COP_HEATING,
        device_key=DeviceKey.heating,
        state_class=SensorStateClass.MEASUREMENT,
        numerator_key=LC.C0257_CURRENT_HEAT_OUTPUT,
        denominator_key=LC.C0268_CURRENT_POWER_CONSUMPTION,
        required_status=LuxOperationMode.heating,
        icon="mdi:speedometer",
    ),
    cop_descr(
        key=SensorKey.COP_DHW,
        device_key=DeviceKey.domestic_water,
        state_class=SensorStateClass.MEASUREMENT,
        numerator_key=LC.C0257_CURRENT_HEAT_OUTPUT,
        denominator_key=LC.C0268_CURRENT_POWER_CONSUMPTION,
        required_status=LuxOperationMode.domestic_water,
        icon="mdi:speedometer",
    ),
    cop_descr(
        key=SensorKey.COP_COOLING,
        device_key=DeviceKey.cooling,
        state_class=SensorStateClass.MEASUREMENT,
        numerator_key=LC.C0257_CURRENT_HEAT_OUTPUT,
        denominator_key=LC.C0268_CURRENT_POWER_CONSUMPTION,
        required_status=LuxOperationMode.cooling,
        icon="mdi:speedometer",
    ),
]
# endregion COP
```

- [ ] **Step 3: Verify it imports cleanly**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -c "from custom_components.luxtronik2.sensor_entities_predefined import SENSORS_COP; print(len(SENSORS_COP))"`
Expected: `3`

- [ ] **Step 4: Commit**

```bash
git add custom_components/luxtronik2/sensor_entities_predefined.py
git commit -m "feat(sensor): add SENSORS_COP predefined entity descriptions"
```

---

## Task 4: `LuxtronikCopSensorEntity` + wiring in `sensor.py`

**Files:**
- Modify: `custom_components/luxtronik2/sensor.py`
- Test: `tests/test_cop_sensor.py` (new)

**Interfaces:**
- Consumes: `SENSORS_COP` (Task 3), `LuxtronikCopSensorDescription` (Task 2), `get_sensor_data`/`key_exists` (`common.py`), `coordinator.entity_active` (`coordinator.py:471`).
- Produces: `LuxtronikCopSensorEntity` — a `SensorEntity` whose `_attr_native_value` is `round(numerator / denominator, 2)` while available, `None` otherwise; `_attr_available` reflects whether the heat pump is currently in the required operating status and both readings are valid numbers.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cop_sensor.py`:

```python
"""Tests for LuxtronikCopSensorEntity (instantaneous COP)."""

from __future__ import annotations

from unittest.mock import MagicMock

from conftest import make_coordinator_data
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT

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
from custom_components.luxtronik2.model import LuxtronikCopSensorDescription
from custom_components.luxtronik2.sensor import LuxtronikCopSensorEntity

_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
    CONF_HA_SENSOR_PREFIX: DOMAIN,
}


def _mock_entry():
    entry = MagicMock()
    entry.data = _ENTRY_DATA.copy()
    return entry


def _mock_coordinator(data):
    coord = MagicMock()
    coord.data = data
    coord.last_update_success = True
    coord.entity_active.return_value = True
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    return coord


def _heating_cop_description() -> LuxtronikCopSensorDescription:
    return LuxtronikCopSensorDescription(
        key=SensorKey.COP_HEATING,
        device_key=DeviceKey.heating,
        numerator_key=LC.C0257_CURRENT_HEAT_OUTPUT,
        denominator_key=LC.C0268_CURRENT_POWER_CONSUMPTION,
        required_status=LuxOperationMode.heating,
    )


def _make_entity(data, description=None):
    hass = MagicMock()
    entry = _mock_entry()
    coord = _mock_coordinator(data)
    description = description or _heating_cop_description()
    entity = LuxtronikCopSensorEntity(
        hass, entry, coord, description, DeviceKey.heating
    )
    entity.hass = hass
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    return entity


class TestCopSensorHandleCoordinatorUpdate:
    def test_computes_ratio_when_status_matches(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,  # compressor running
                "Heat_Output": 6000,
                "Unknown_Calculation_268": 1500,
            }
        )
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 4.0
        assert entity._attr_available is True

    def test_unavailable_when_status_does_not_match(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.domestic_water,
                "Heat_Output": 6000,
                "Unknown_Calculation_268": 1500,
            }
        )
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None
        assert entity._attr_available is False

    def test_unavailable_when_denominator_zero(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,
                "Heat_Output": 6000,
                "Unknown_Calculation_268": 0,
            }
        )
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None
        assert entity._attr_available is False

    def test_unavailable_when_values_missing(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,
                "Heat_Output": None,
                "Unknown_Calculation_268": None,
            }
        )
        entity = _make_entity(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None
        assert entity._attr_available is False

    def test_none_data_returns_early(self):
        data = make_coordinator_data(
            calculations={
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": True,
                "Heat_Output": 6000,
                "Unknown_Calculation_268": 1500,
            }
        )
        entity = _make_entity(data)
        entity.coordinator.data = None
        entity._handle_coordinator_update(None)
        entity.async_write_ha_state.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_cop_sensor.py -v`
Expected: `ImportError: cannot import name 'LuxtronikCopSensorEntity'` (it doesn't exist yet).

- [ ] **Step 3: Add the entity class and wire it into `async_setup_entry`**

In `custom_components/luxtronik2/sensor.py`, find:

```python
from .model import LuxtronikIndexSensorDescription, LuxtronikSensorDescription
from .sensor_entities_predefined import SENSORS, SENSORS_INDEX, SENSORS_STATUS
```

Replace with:

```python
from .model import (
    LuxtronikCopSensorDescription,
    LuxtronikIndexSensorDescription,
    LuxtronikSensorDescription,
)
from .sensor_entities_predefined import (
    SENSORS,
    SENSORS_COP,
    SENSORS_INDEX,
    SENSORS_STATUS,
)
```

Then find the third `async_add_entities` block in `async_setup_entry` (the `LuxtronikIndexSensor` one):

```python
    async_add_entities(
        [
            LuxtronikIndexSensor(
                hass, entry, coordinator, description, description.device_key
            )
            for description in SENSORS_INDEX
            if coordinator.entity_active(description)
        ],
        True,
    )
```

Add a fourth block immediately after it (still inside `async_setup_entry`, before its closing):

```python

    async_add_entities(
        [
            LuxtronikCopSensorEntity(
                hass, entry, coordinator, description, description.device_key
            )
            for description in SENSORS_COP
            if (
                coordinator.entity_active(description)
                and key_exists(coordinator.data, description.numerator_key)
                and key_exists(coordinator.data, description.denominator_key)
            )
        ],
        True,
    )
```

Finally, add the entity class at the end of the file (after `LuxtronikIndexSensor`):

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

        if descr.required_status is not None and status != descr.required_status:
            self._attr_available = False
            self._attr_native_value = None
        elif (
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_cop_sensor.py -v`
Expected: `5 passed`

- [ ] **Step 5: basedpyright + ruff**

Run:
```bash
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m basedpyright --pythonpath "C:\Users\rhamm\anaconda3\envs\py314\python.exe" custom_components/luxtronik2
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff check custom_components/luxtronik2 tests
"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m ruff format --check custom_components/luxtronik2 tests
```
Expected: `0 errors` from basedpyright; ruff check/format clean (fix with `ruff format` if format check fails, then re-run).

- [ ] **Step 6: Commit**

```bash
git add custom_components/luxtronik2/sensor.py tests/test_cop_sensor.py
git commit -m "feat(sensor): add LuxtronikCopSensorEntity for instantaneous COP"
```

---

## Task 5: Translations (all 5 locales) + icons

**Files:**
- Modify: `custom_components/luxtronik2/translations/en.json`
- Modify: `custom_components/luxtronik2/translations/de.json`
- Modify: `custom_components/luxtronik2/translations/nl.json`
- Modify: `custom_components/luxtronik2/translations/pl.json`
- Modify: `custom_components/luxtronik2/translations/cs.json`
- Modify: `custom_components/luxtronik2/icons.json`

**Interfaces:**
- Consumes: `SensorKey.COP_HEATING/COP_DHW/COP_COOLING` (Task 1).
- Produces: nothing consumed by later tasks — this satisfies `tests/test_translation_coverage.py::test_all_referenced_entity_keys_have_translations`.

Each entity already belongs to a device (Heating / Domestic hot water / Cooling per `device_key`) and `has_entity_name=True`, so Home Assistant prefixes the device name automatically — the entity's own `name` only needs to say "COP", not "Heating COP". "COP" is used as-is (untranslated) in all five locales here, matching how the codebase already leaves other HVAC acronyms (e.g. "TDI") untranslated.

- [ ] **Step 1: en.json**

In `custom_components/luxtronik2/translations/en.json`, find:

```json
            "cooling_energy_input": {
                "name": "Energy input"
```

(the one inside the Cooling device section, i.e. the *second* occurrence — around line 913, immediately after `"operation_hours_cooling"`). Add right after that whole `cooling_energy_input` block's closing `},`:

```json
            "cop_cooling": {
                "name": "COP"
            },
```

Then find the heating section's:

```json
            "heat_energy_input": {
                "name": "Energy input heating"
            },
```

Add right after it:

```json
            "cop_heating": {
                "name": "COP"
            },
```

Then find the DHW section's:

```json
            "dhw_energy_input": {
                "name": "Energy input"
            },
```

Add right after it:

```json
            "cop_dhw": {
                "name": "COP"
            },
```

- [ ] **Step 2: de.json / nl.json / pl.json / cs.json**

Repeat Step 1's three insertions (same JSON keys `cop_heating`, `cop_dhw`, `cop_cooling`, same English value `"COP"`) in each of `de.json`, `nl.json`, `pl.json`, `cs.json`, next to that locale's own `heat_energy_input` / `dhw_energy_input` / `cooling_energy_input` blocks respectively. Use each file's existing indentation (they match `en.json`'s structure).

- [ ] **Step 3: icons.json**

In `custom_components/luxtronik2/icons.json`, find:

```json
      "current_heat_output": { "default": "mdi:lightning-bolt-circle" },
```

Add right after it:

```json
      "cop_heating": { "default": "mdi:speedometer" },
      "cop_dhw": { "default": "mdi:speedometer" },
      "cop_cooling": { "default": "mdi:speedometer" },
```

(If `icons.json` structure nests per-platform like the translation files, place these under the `"sensor"` section alongside `current_heat_output` — check the surrounding braces before inserting.)

- [ ] **Step 4: Run translation coverage tests**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest tests/test_translation_coverage.py -v`
Expected: `2 passed`

- [ ] **Step 5: Validate all JSON files parse**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -c "import json; [json.load(open(f'custom_components/luxtronik2/translations/{l}.json', encoding='utf-8')) for l in ['en','de','nl','pl','cs']]; json.load(open('custom_components/luxtronik2/icons.json', encoding='utf-8')); print('ok')"`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add custom_components/luxtronik2/translations custom_components/luxtronik2/icons.json
git commit -m "feat(translations): add cop_heating/cop_dhw/cop_cooling entity names"
```

---

## Task 6: Full verification

- [ ] **Step 1: Full test suite with coverage**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m pytest --cov=custom_components.luxtronik2 --cov-report=term-missing -q`
Expected: all tests pass, coverage not lower than before this branch started (check against `main`'s baseline number).

- [ ] **Step 2: codespell**

Run: `"C:\Users\rhamm\anaconda3\envs\py314\python.exe" -m codespell custom_components/luxtronik2 tests`
Expected: no output / 0 findings.

- [ ] **Step 3: Manual sanity check (optional but recommended)**

Point a real or mocked Luxtronik connection at HA and watch the three new `sensor.*_cop_heating` / `cop_dhw` / `cop_cooling` entities (enabled by default) over a heating cycle: COP should hold a plausible value (roughly 2-6 for a compressor heat pump) while heating is active, and go `unavailable` the moment status changes to idle/DHW/defrost.

## Self-Review Notes

- **Spec coverage:** instantaneous COP (✅ Task 4), no external meter (✅ uses only `C0257`/`C0268`), split by Heating/DHW/Cooling (✅ Task 3, gated by `required_status` + `device_key`), translations for all locales (✅ Task 5).
- **Firmware caveat:** documented in Global Constraints rather than "fixed" — re-enabling the commented-out firmware gate on `C0268` is explicitly out of scope for this branch.
- **No placeholders:** every step has literal file content/diffs; no TBD/TODO left in code.

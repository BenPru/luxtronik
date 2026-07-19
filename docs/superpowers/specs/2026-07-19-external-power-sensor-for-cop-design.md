# External Power Sensor for COP Calculations — Design

## Problem

`sensor.*_current_power_consumption` (`LC.C0268_CURRENT_POWER_CONSUMPTION`) is a best-effort mapping — the upstream `luxtronik` library has no confirmed name for this register (`Unknown_Calculation_268`). On PR #693, collaborator `AJediIAm` reported it reports implausible values on their unit (e.g. a flat ~6000 W during a period that should read close to 0 W), making it physically meaningless there. Since `sensor.*_cop_heating` / `cop_dhw` (merged in #693) divide by this exact value, COP is unusable for anyone in this situation — which is likely a nontrivial share of users, given `C0268` was already known to be an unconfirmed/best-effort mapping before this report.

`AJediIAm` asked for the ability to configure an external Home Assistant sensor (e.g. a Shelly smart plug measuring the heat pump's actual draw) as a substitute, "similar to the room thermostat sensor" — referring to the existing `ha_sensor_indoor_temperature` options-flow override used by `climate.py`.

## Goals

- Let a user configure an external HA `sensor` entity (device_class `power`) in the integration's options flow.
- When configured, `cop_heating` and `cop_dhw` use that external sensor's state as their denominator instead of `C0268`.
- When not configured, behavior is unchanged (today's `C0268`-based calculation).

## Non-goals

- **Numerator (`current_heat_output` / `C0257`) is not overridable by this feature** — only the denominator (power consumption). Neither the PR report nor the repo owner's clarification mentioned heat output being wrong; scoping the override to exactly the value reported as broken.
- **Do not** change what `sensor.*_current_power_consumption` itself displays. It keeps showing the raw `C0268` reading regardless of this option — this option only affects the COP calculation's input, not the diagnostic sensor's own value. (Confirmed with the repo owner: no need to mirror the external value into a new/replacement sensor.)
- **Does not** apply to `sensor.*_lifetime_cop_heating` / `lifetime_cop_dhw` (the cumulative-counter COP from the sibling, not-yet-implemented `feat/lifetime-cop-sensors` plan) — that entity's denominator is `HEAT_ENERGY_INPUT`/`DHW_ENERGY_INPUT`, unrelated to instantaneous power. Out of scope here; revisit only if a similar report comes in for that entity.
- No live event-driven updates (`async_track_state_change_event`) — matches the existing `ha_sensor_indoor_temperature` override, which is polled alongside the normal coordinator refresh cycle, not push-driven. Consistency with the established pattern over a (currently unrequested) latency improvement.
- No unit conversion (e.g. accepting a `kW`-unit sensor and converting to `W`). The existing indoor-temperature override doesn't convert units either; if this becomes a real need later, it's a separate follow-up.

## Architecture

Mirrors the existing `ha_sensor_indoor_temperature` mechanism (`config_flow.py:486-544`, `schema_helper.py:36-68`, consumed in `climate.py:280-397`), narrowed to the one field this needs:

1. **New config constant** `CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION = "ha_sensor_current_power_consumption"` in `const.py`, alongside `CONF_HA_SENSOR_INDOOR_TEMPERATURE`.
2. **New options-flow field**, `schema_helper.py`'s `build_options_schema`: a `selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="power"))`, same shape as the existing temperature field.
3. **New options-flow read/write branch** in `LuxtronikOptionsFlowHandler.async_step_user` (`config_flow.py:501-544`): same save/clear logic as `CONF_HA_SENSOR_INDOOR_TEMPERATURE` (`config_flow.py:508-515`) — set if truthy, explicitly `None` if cleared and previously present in options or legacy data.
4. **Consumption in `LuxtronikCopSensorEntity`** (`sensor.py`, added in the `feat/instant-cop-sensors` branch): no new dataclass field on `LuxtronikCopSensorDescription` — this is entity-level, not description-level, since it comes from the config entry, not a static per-sensor definition. Read the configured entity-id once in `__init__` (mirroring `climate.py:298-301`'s read), store as `self._external_power_sensor_entity_id: str | None`. In `_handle_coordinator_update`, when that attribute is set, resolve `denominator` from `self.hass.states.get(entity_id)` via `state_as_number_or_none` (already imported from `common.py` elsewhere in the codebase) instead of `get_sensor_data(data, descr.denominator_key)`.

This intentionally does NOT touch `LuxtronikCopSensorDescription` (Task 2 of the merged plan) — the override is a per-entity runtime concern (which config entry, which options), not a static description field. Keeping it in the entity class matches where `climate.py` put its own equivalent logic.

## Data Flow

```
Options flow save
  -> entry.options[CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION] = "sensor.shelly_heatpump_power" (or None)

LuxtronikCopSensorEntity.__init__(hass, entry, coordinator, description, device_key)
  -> self._external_power_sensor_entity_id = entry.options.get(
         CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
         entry.data.get(CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION),
     )

LuxtronikCopSensorEntity._handle_coordinator_update(data)
  status = get_sensor_data(data, LC.C0080_STATUS)          # unchanged
  numerator = get_sensor_data(data, descr.numerator_key)   # unchanged (still C0257 internally)

  if self._external_power_sensor_entity_id:
      state = self.hass.states.get(self._external_power_sensor_entity_id)
      denominator = state_as_number_or_none(state) if state is not None else None
  else:
      denominator = get_sensor_data(data, descr.denominator_key)   # existing C0268 path, unchanged

  # existing gating logic (status match, isinstance/positivity guards) applies unchanged to `denominator`
  # regardless of which branch produced it
```

Only the denominator's *source* changes; every downstream guard (status gate, `isinstance` checks, `denominator <= 0`, `numerator < 0`, rounding) is untouched and applies identically to both branches.

## Error Handling

| Situation | Behavior |
|---|---|
| Option not configured | Unchanged: denominator = internal `C0268` reading. |
| Option configured, external sensor state is a valid number | Denominator = that number. COP computed normally (subject to existing status/positivity guards). |
| Option configured, external sensor unavailable/unknown/non-numeric | `state_as_number_or_none` returns `None` → denominator is `None` → existing `isinstance` guard already makes the entity unavailable. **No new guard code needed** — this falls out of the existing logic for free once `denominator` can be `None` from either source. |
| Option configured, external entity_id doesn't exist at all (e.g. renamed/removed) | `hass.states.get()` returns `None` → same as above, denominator `None` → unavailable. |

Per the earlier decision: configured-but-currently-bad external sensor never silently falls back to the internal (known-questionable) `C0268` value — it goes unavailable, same as the entity's other "we don't have a trustworthy number right now" cases.

## Config Flow / UI

- New field appears in the **options flow only** (not initial setup), directly below `ha_sensor_indoor_temperature` in the form — same section, same UX pattern.
- Translation keys (all 5 locales, under `options.step.user.data` / `data_description`, mirroring the existing `ha_sensor_indoor_temperature` entries at `en.json:1149-1164`):
  - `data.ha_sensor_current_power_consumption`: `"Sensor ID for the current power consumption"`
  - `data_description.ha_sensor_current_power_consumption`: `"If the heat pump's built-in current power consumption reading is inaccurate, an external Home Assistant power sensor (e.g. a smart plug) can be used instead for the Heating/DHW COP calculations. This does not change what the Current power consumption sensor itself displays.\nLeave empty to use the heat pump's built-in reading."`

## Testing

- `tests/test_config_flow.py`: extend the existing `TestOptionsFlow`/reset-test pattern (`config_flow.py:592-734` equivalent tests) with the same three cases already covered for indoor temp — save, clear-when-falsy, clear-of-legacy-data-value — parameterized or duplicated for `CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION`.
- `tests/test_cop_sensor.py` (extends the suite added in `feat/instant-cop-sensors`): new tests for `LuxtronikCopSensorEntity`:
  - external sensor configured + valid numeric state → COP computed from that value (not from `C0268` in the coordinator data, even if present and different — proves the override actually takes priority).
  - external sensor configured + `STATE_UNAVAILABLE`/missing entity → COP entity unavailable.
  - external sensor not configured → today's `C0268`-based behavior unchanged (regression coverage for the existing 5 tests, which must still pass unmodified since the default/no-config path is untouched).

## Scope Check

Single cohesive change across 4 files (`const.py`, `schema_helper.py`, `config_flow.py`, `sensor.py`) plus translations — fits one implementation plan, no decomposition needed.

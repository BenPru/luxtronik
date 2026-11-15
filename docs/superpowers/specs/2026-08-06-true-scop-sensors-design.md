# True SCOP Sensors — Design (DRAFT, IN PROGRESS)

> **Status: approach D agreed 2026-11-15 — see [Decision](#decision-2026-11-15-build-d-for-30-d-and-1-y).** Plan: [`2026-11-15-scop-sensors-from-statistics.md`](../plans/2026-11-15-scop-sensors-from-statistics.md). C and B below are deferred until D proves insufficient.

## Decision 2026-11-15: build D for 30 d and 1 y

- **Build D only**, with two windows: **1 year (SCOP)** and **30 days**, rolling, for Heating, DHW and both together (whole unit). "This may well be enough"; C/B stay on the shelf.
- **Cooling is dropped.** @rhammen's pump cools passively (no compressor, nothing in C0257); there is no heat counter for cooling either.
- **Hourly long-term statistics, not daily.** The hourly table is also kept indefinitely; using hours avoids aligning to local-midnight day buckets and makes the glitch rule finer. The glitch rule (`change > 1 and change > 0.5 × state`, or `change < 0`) is applied per hour and drops the hour for every counter.
- **External meter (`CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION`) is used when configured.** It measures the whole unit, so its energy over the window is split between the circuits by the controller's own electricity shares over that window: `heating = E_ext × ΣP1136 / (ΣP1136 + ΣP1137 + ΣP1138 + ΣP1139)`, and likewise for DHW; the whole-unit figure takes the heating + DHW share. That attributes standby proportionally and keeps pool/cooling pump energy out. Power sensors (LTS `mean`, kW × 1 h) and energy sensors (LTS `change`) both work; a sensor with no long-term statistics falls back to the controller counters.
- **Not created on twin units** (P1010 ≠ 0): C0151/C0152 count compressor 1 only (#815) and it is unknown whether P1136/P1137 cover both.
- **Coverage instead of a fake window.** Each sensor reports how many days of data it actually used, and stays `unknown` below 7 days (30 d window) or 30 days (1 y window).

**Goal:** Give users a true seasonal COP (SCOP) — total heat delivered divided by total electricity consumed over a period — for the Heating and DHW circuits, over rolling windows (24 h, 7 d, 30 d, 1 y).

**Related:** [issue #188](https://github.com/BenPru/luxtronik/issues/188) · [instant COP plan](../plans/2026-07-17-instant-cop-sensors.md) · [external power sensor design](2026-07-19-external-power-sensor-for-cop-design.md) · superseded [lifetime COP plan](../plans/2026-07-17-lifetime-cop-sensors.md) (branch `docs/lifetime-cop-sensors-plan`)

## Why the obvious approach does not work

Two approaches suggest themselves and both fail. Recording why, so neither gets re-proposed.

### Averaging the instantaneous COP sensor is not SCOP

`sensor.*_cop_heating` / `cop_dhw` report an instantaneous ratio. Averaging them — via a `statistics` helper or Home Assistant's long-term statistics — gives an unweighted mean of a ratio, where SCOP is a ratio of totals:

```
SCOP_true = ΣQᵢ/ΣPᵢ = Σ(COPᵢ·Pᵢ)/ΣPᵢ      ← power-weighted mean of COP
averaging  = (1/N)·ΣCOPᵢ                    ← unweighted mean of COP

SCOP_true − averaged = Cov(COP, P) / mean(P)
```

The gap is driven by the covariance between COP and power draw, not by sampling rate — polling faster does not converge on SCOP. On an inverter unit that covariance is reliably negative (high power ⇒ cold weather, high flow temperature, low COP), so **averaging the ratio systematically overestimates SCOP**. This is documented for users in [`ADVANCED_FEATURES.md`](../../../ADVANCED_FEATURES.md#averaging-cop-over-time-daily-weekly-monthly).

### Dividing the heat pump's cumulative counters is not SCOP either

The integration already exposes matched cumulative pairs, all `TOTAL_INCREASING` + `device_class: ENERGY`:

| Circuit | Heat delivered | Electricity consumed |
|---|---|---|
| Heating | `heat_amount_heating` (C0151) | `heat_energy_input` (P1136) |
| DHW | `dhw_heat_amount` (C0152) | `dhw_energy_input` (P1137) |
| Cooling | — *(no counter exists)* | `cooling_energy_input` (P1139) |

Dividing them fails for two independent reasons:

1. **Different epochs.** `*_energy_input` was added in later firmware and starts from zero years after the heat-amount counters. Measured on @rhammen's live system (2026-08-06): DHW `24284.1 / 713.42 = SCOP 34`; Heating `163258.4 / 2699.38 = SCOP 60`. Both physically impossible. Confirms @AJediIAm's observation in discussion #325 (heat amount a 4-year total, energy input a 1-year total). **This invalidates the lifetime COP plan as designed** — it divides the raw totals.

   *Deltas* over a window are unaffected: on the one day DHW ran, `+4.60 kWh / +1.08 kWh = COP 4.26`, consistent with the ~4.6 daily mean from the instantaneous sensor.

2. **~2-hour firmware update cadence.** Per @AJediIAm (discussion #325), the heat pump updates `*_energy_input` internally only every ~2 hours regardless of poll rate. Any window shorter than a day is a step function, not a curve.

### Update 2026-11-08: counter deltas over long-term statistics do work

Established while fixing the SPF tile of Gifford47's [luxtronik-heatpump-card](https://github.com/Gifford47/luxtronik-heatpump-card/pull/2), on @rhammen's MSW4-16 (V3.92.1):

- **The epoch is the firmware upgrade.** The daily long-term statistics (LTS) of `heat_energy_input` / `dhw_energy_input` begin on 2025-10-05, the day this unit was upgraded to V3.92.1, at 8.44 / 2.71 kWh. That is the counters starting from 0, not a recorder gap. The heat counters go back to commissioning.
- **Windowed deltas from LTS give a real SPF:** Σ daily `change` of heat ÷ Σ daily `change` of electricity over 365 days. The `recorder/statistics_during_period` websocket call (period `day`, types `change` + `state`) returns this directly. Results: heating **6.44**, DHW **3.94**, combined **5.90**. Dividing lifetime totals gives 49.79.
- **LTS has no retention limit.** The objection to approach A below ("a window cannot exceed `purge_keep_days`") applies to the `statistics` *helper* only. A 1-year rolling window computed from LTS is not bound by recorder retention.
- **Glitch days must be excluded.** On a day when a `TOTAL_INCREASING` counter dips to 0 and recovers, HA books the full counter value as that day's `change`. Rule used: a day is a glitch when `change > 0.5 × state` (and `change > 1`), and it is dropped for all counters so heat and electricity stay paired. On this unit the rule flags exactly 2025-10-05 (upgrade day), 2026-07-04 (the P1136/P1137 double-/10 fix, a full-value jump) and the zeroed calculations blocks of 2026-07-28 and 2026-10-07. It flags no other day.
- **Counting starts on the first day the electricity counter advances.** That keeps pre-epoch heat out of the ratio on windows that reach back before the firmware upgrade.

This gives the counter route a working form: **D. windowed counter deltas from LTS, glitch days excluded.** It needs no new persistence and no enabled diagnostic sensors, and the history it needs already exists. It cannot do cooling (still no heat counter) or series 1 (P1136/P1137 absent or 0). Day granularity also hides the ~2-hour counter cadence. It should be weighed against C before building anything; it could also be what B's snapshot ring stores, instead of integrated power.

## Chosen direction: integrate power, then divide

Build on the *same* inputs the instantaneous COP already uses — `C0257_CURRENT_HEAT_OUTPUT` and `C0268_CURRENT_POWER_CONSUMPTION`, both in Watts — and integrate them over time into energy:

```
SCOP_window = ∫Q(t)dt / ∫P(t)dt
```

This is not an approximation of SCOP; integrating before dividing *is* the power weighting, so it yields SCOP exactly. It also sidesteps the 2-hour counter cadence entirely, and inherits the user-configured external power sensor (`CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION`) for free, since that override already applies to the denominator in `LuxtronikCopSensorEntity`.

**Constraint noted during brainstorming:** both source sensors are `entity_category=DIAGNOSTIC` with `entity_registry_enabled_default=False` (`sensor_entities_predefined.py:352-361, 422-431`) — neither is registered on @rhammen's live system. Any approach built on *HA helpers* therefore requires users to enable them first; an approach built *inside the integration* reads coordinator data directly and does not.

## Approaches considered

### A. Pure HA building blocks — rejected as the user-facing answer

Enable the two diagnostic sensors → two `integration` (Riemann sum) helpers convert W to kWh → one `statistics` helper per window with `state_characteristic: change` → a template sensor divides them.

- ✅ Zero integration code; usable today for a personal proof at 24 h / 7 d.
- ❌ ~14 helpers for 4 windows × 2 circuits.
- ❌ **Fatal for long windows:** the `statistics` helper reads recorder history, so a window cannot exceed `purge_keep_days` (10 days by default). 30 d and 1 y would need a year of full-resolution recorder data.

### B. Full SCOP sensors inside the integration

Integrate power into running energy totals each coordinator poll; keep a persisted snapshot ring `[(ts, E_heat, E_elec)]`. Every window is then one subtraction:

```
SCOP_W = (E_heat_now − E_heat_@t−W) / (E_elec_now − E_elec_@t−W)
```

- ✅ One buffer feeds all windows (hourly snapshots for a year ≈ 8760 × 2 floats — trivial).
- ✅ No diagnostic entities need enabling; external power override inherited.
- ❌ Needs restart-safe persistence — an HA `Store`, not just `RestoreEntity` attributes.
- ❌ A fresh install shows nothing useful for 30 days.

### C. Integration exposes integrated *energy* sensors only

Two new `TOTAL_INCREASING` kWh sensors per circuit (heat out, electricity in), honouring the external power sensor, gated by operating status so Heating and DHW are attributed separately. Windowing is left to the user: `utility_meter` for calendar periods, `statistics` for rolling ones. `utility_meter` keeps its own state and is therefore **not** bound by recorder retention.

### Recommendation (proposed, not yet agreed)

**C first, then B on top.** C is the smallest change that makes true SCOP possible at all — it fixes both the epoch mismatch and the 2-hour delay, and is a straightforward extension of the existing COP entity rather than new persistence machinery. B then becomes a thin convenience layer over data that already exists, and the window set can be decided after seeing real numbers.

## User intent captured so far

- Prefers **rolling windows** over calendar periods — calendar resets cause large swings at each boundary.
- Wants roughly **24 h, 7 d, 30 d, 1 y**.
- Wants SCOP **sensors and graphs** eventually, not only documentation.
- Wants it built on the **same sensors the instantaneous COP uses**, including the user-configured external energy sensor, specifically because of the multi-hour delay on the cumulative counters.
- Not committed to an exact design yet.

## Open Questions

1. **Standby power attribution.** A true SCOP must integrate electricity while idle — standby draw is real consumption. But idle power belongs to neither circuit, so gating integration by operating status (needed to separate Heating from DHW) leaves standby unattributed, while an ungated total would double-count across circuits. Options: leave standby unattributed (SCOP slightly optimistic), or add a third *whole heat pump* SCOP that integrates ungated. Current lean: the third, ungated sensor is the honest one.

2. **Cooling.** The counter route cannot do cooling (no heat-output counter). The power-integration route might — *if* `C0257_CURRENT_HEAT_OUTPUT` reports anything meaningful in cooling mode. Unknown and empirically checkable: @rhammen's system has 2878 cooling hours.

3. Window set and whether snapshot granularity should be hourly throughout or hourly for short windows and daily for 1 y.

   Not open, but settled by the 2026-08-18 diagnostics analysis: **series 1 is out of scope either way.** No V1.x unit can feed either route. `P1136`/`P1137` (`HEAT_ENERGY_INPUT`, `DHW_ENERGY_INPUT`) are not returned at all on V1.73/V1.77 — their parameter blocks stop at 1021 and 1075 — and read exactly 0 on all three V1.88.3/V1.90.0 dumps despite large runtime counters, so the counter route has no input energy. `C0268` (current power consumption), which the instantaneous COP route needs, is not returned on V1.73/V1.77 either; the V1.88.3 and V1.90.0 dumps predate the override that defines it, so they cannot answer for those minors. Any SCOP sensor should simply not be created on a controller that returns none of these — which register-presence detection already decides, without a firmware gate.

4. Whether the superseded lifetime COP plan should be formally closed out, and its branch deleted.

## Unrelated bug found while investigating

`LuxtronikCopSensorEntity` sets `self._attr_available` (`sensor.py:467-470`), but inherits `CoordinatorEntity.available` — a `@property` returning `coordinator.last_update_success`, which shadows the attribute entirely. The assignment has no effect: the COP sensors go to `unknown` when idle, never `unavailable`. Confirmed on live HA — both sensors read `unknown` continuously. `LuxtronikStatusSensorEntity` gets this right by overriding the property (`sensor.py:246-251`). The class docstring (`sensor.py:398-403`) documents the intended-but-not-actual behaviour.

Harmless for the statistics/averaging documentation (HA skips both `unknown` and `unavailable` when aggregating), but it should be fixed or the docstring corrected. Not yet filed.

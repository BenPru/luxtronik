# Timer Schedules

Several circuits on the heat pump controller can be programmed with a weekly schedule directly on the controller (or its firmware's built-in web interface). This integration exposes those schedules as editable Home Assistant entities so they can be read and changed without touching the physical controller.

Only the **DHW (Bw)** circuit is wired up so far. The other five timer-program circuits — heating (Hkr), mixing circuits 1/2 (Mk1/Mk2), circulation pump (ZIP), and pool (Swb) — are intentionally deferred until the DHW implementation has been validated in the field; see [Extending to other circuits](#extending-to-other-circuits) below.

## DHW Timer Schedule (Blocking Times)

The heat pump controller can be programmed with a weekly schedule of **blocking times** for DHW. Unlike a heating schedule (which defines when heating is *raised*), a DHW schedule window is a **"do not heat" window**: during a configured time span, automatic DHW heating is switched off; outside those spans it runs normally according to the *Mode* setting (see [README § 2.4 DHW](README.md#24-dhw-domestic-hot-water)). If you need hot water during an active blocking window, switch *Mode* to *Party* to override it temporarily (see the README's [Automating DHW](README.md#312-automating-dhw) section, *Boost hot water* example).

The controller supports three mutually-exclusive schedule shapes for DHW, up to 5 blocking windows per day each:
- **Week** – one schedule applies to every day.
- **Weekday / Weekend** ("5+2") – one schedule for Monday-Friday, a separate one for Saturday-Sunday.
- **Per day** – an independent schedule for each individual day of the week.

Only one shape is active at a time. Which shape is active is exposed as the **DHW Timer Program** select entity, so it can be switched from Home Assistant as well as on the physical controller (or its web interface).

| Name | Entity Type | Description |
| :--- | :--- | :--- |
| **DHW Timer Program** | Select | Which schedule shape the controller uses: *Whole week*, *Weekdays + weekend*, or *Per day*. |
| **DHW Timer Schedule (Week)** | Text | Exists while the *Week* shape is active. |
| **DHW Timer Schedule (Weekdays)** | Text | Exists while *Weekday/Weekend* is active; covers Monday-Friday. |
| **DHW Timer Schedule (Weekend)** | Text | Exists while *Weekday/Weekend* is active; covers Saturday-Sunday. |
| **DHW Timer Schedule (Monday)** … **(Sunday)** | Text | One entity per day of the week, present while *Per day* is active. |

Each entity holds up to 5 blocking windows as a single string of `HH:MM-HH:MM` pairs separated by `/`, for example:
```
12:00-13:00/22:00-23:30
```
This blocks DHW heating over lunch (12:00-13:00) and in the evening (22:00-23:30). Set the value to an empty string to clear all blocking windows for that entity.

### Only the active shape's entities are present

Only the schedule entities of the shape currently selected in *DHW Timer Program* exist as usable entities. The other shapes' entities are **disabled** rather than left permanently unavailable, so the device page collapses them behind a *"+N disabled entities"* button instead of listing them as broken.

Changing the timer program — from Home Assistant or on the controller itself — swaps the entity set automatically within one polling interval; no restart or integration reload is needed. Because the entities are disabled rather than deleted, everything you attached to them survives the switch: a renamed entity ID, friendly name, icon, area, labels, and their recorder history all come back unchanged when that shape becomes active again.

> **ℹ️ Note:** Home Assistant reloads an integration ~30 seconds after any of its entities is re-enabled, so switching the timer program is followed by a brief reload of the Luxtronik integration. The new shape's schedule entities themselves appear immediately — the reload happens afterwards and needs no action from you.

Entities of an inactive shape keep a stale `unavailable` state in the state machine (Home Assistant's normal behaviour for a registered entity that no integration is currently providing). Nothing surfaces this in the UI, but a dashboard card that references such an entity by ID directly will show it as unavailable while its shape is inactive.

## Extending to other circuits

The remaining five timer-program circuits share the same underlying shape (mode selector + Week/5+2/Per-day time blocks), just with different parameter-name prefixes and row counts:

| Circuit | Mode selector | Rows/day |
| :--- | :--- | :--- |
| Heating (Hkr) | `ID_Einst_SuHkr_akt` | 3 |
| Mixing circuit 1 (Mk1) | `ID_Einst_SuMk1_akt` | 3 |
| Mixing circuit 2 (Mk2) | `ID_Einst_SuMk2_akt` | 3 |
| Circulation pump (ZIP) | `ID_Einst_SuZIP_akt` | 5 |
| Pool (Swb) | `ID_Einst_SuSwb_akt` | 3 |

Adding one is additive: define a `_TimerCircuit` in `timer_schedule_entities_predefined.py` (mirroring `_DHW_CIRCUIT`) with that circuit's selector name, row count, and `WO`/`25`/`TG` parameter prefixes, then call `_build_circuit_entities` with a matching set of `SensorKey` entries and translations. No changes to `text.py` itself should be needed — its logic, including the active-shape sync that enables and disables entities as the program changes, is already generic per `LuxtronikTimerScheduleTextDescription`. A select entity for the new circuit's own mode selector is one description in `select_entities_predefined.py`, reusing `raw_option_map` to map the HA option names onto the raw `week` / `5+2` / `days` values.

Unlike DHW, the heating/mixing/pool circuit schedules define when the circuit is *raised* (comfort setback), not blocking times — the semantics are the opposite of DHW's "Sperrzeiten". Confirm the correct direction for each circuit against the controller manual before writing its documentation, rather than assuming DHW's polarity applies uniformly.

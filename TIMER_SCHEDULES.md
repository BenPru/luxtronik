# Timer Schedules

Several circuits on the heat pump controller can be programmed with a weekly schedule directly on the controller (or its firmware's built-in web interface). This integration exposes those schedules as editable Home Assistant entities so they can be read and changed without touching the physical controller.

Only the **DHW (Bw)** circuit is wired up so far. The other five timer-program circuits — heating (Hkr), mixing circuits 1/2 (Mk1/Mk2), circulation pump (ZIP), and pool (Swb) — are intentionally deferred until the DHW implementation has been validated in the field; see [Extending to other circuits](#extending-to-other-circuits) below.

## DHW Timer Schedule (Blocking Times)

The heat pump controller can be programmed with a weekly schedule of **blocking times** for DHW. Unlike a heating schedule (which defines when heating is *raised*), a DHW schedule window is a **"do not heat" window**: during a configured time span, automatic DHW heating is switched off; outside those spans it runs normally according to the *Mode* setting (see [README § 2.4 DHW](README.md#24-dhw-domestic-hot-water)). If you need hot water during an active blocking window, switch *Mode* to *Party* to override it temporarily (see the README's [Automating DHW](README.md#312-automating-dhw) section, *Boost hot water* example).

The controller supports three mutually-exclusive schedule shapes for DHW, up to 5 blocking windows per day each:
- **Week** – one schedule applies to every day.
- **Weekday / Weekend** ("5+2") – one schedule for Monday-Friday, a separate one for Saturday-Sunday.
- **Per day** – an independent schedule for each individual day of the week.

Only one shape is active at a time. Which shape is active is selected on the physical controller (or its web interface) — this integration does not yet expose a control for that selector, only for editing the time windows themselves.

| Name | Entity Type | Description |
| :--- | :--- | :--- |
| **DHW Timer Schedule (Week)** | Text | Editable only while the *Week* shape is active. |
| **DHW Timer Schedule (Weekdays)** | Text | Editable only while *Weekday/Weekend* is active; covers Monday-Friday. |
| **DHW Timer Schedule (Weekend)** | Text | Editable only while *Weekday/Weekend* is active; covers Saturday-Sunday. |
| **DHW Timer Schedule (Monday)** … **(Sunday)** | Text | One entity per day of the week, editable only while *Per day* is active. |

Each entity holds up to 5 blocking windows as a single string of `HH:MM-HH:MM` pairs separated by `/`, for example:
```
12:00-13:00/22:00-23:30
```
This blocks DHW heating over lunch (12:00-13:00) and in the evening (22:00-23:30). Set the value to an empty string to clear all blocking windows for that entity. Entities belonging to a schedule shape other than the one currently active on the controller show as `unavailable` — this is expected, not an error.

## Extending to other circuits

The remaining five timer-program circuits share the same underlying shape (mode selector + Week/5+2/Per-day time blocks), just with different parameter-name prefixes and row counts:

| Circuit | Mode selector | Rows/day |
| :--- | :--- | :--- |
| Heating (Hkr) | `ID_Einst_SuHkr_akt` | 3 |
| Mixing circuit 1 (Mk1) | `ID_Einst_SuMk1_akt` | 3 |
| Mixing circuit 2 (Mk2) | `ID_Einst_SuMk2_akt` | 3 |
| Circulation pump (ZIP) | `ID_Einst_SuZIP_akt` | 5 |
| Pool (Swb) | `ID_Einst_SuSwb_akt` | 3 |

Adding one is additive: define a `_TimerCircuit` in `timer_schedule_entities_predefined.py` (mirroring `_DHW_CIRCUIT`) with that circuit's selector name, row count, and `WO`/`25`/`TG` parameter prefixes, then call `_build_circuit_entities` with a matching set of `SensorKey` entries and translations. No changes to `text.py` itself should be needed — its logic is already generic per `LuxtronikTimerScheduleTextDescription`.

Unlike DHW, the heating/mixing/pool circuit schedules define when the circuit is *raised* (comfort setback), not blocking times — the semantics are the opposite of DHW's "Sperrzeiten". Confirm the correct direction for each circuit against the controller manual before writing its documentation, rather than assuming DHW's polarity applies uniformly.

# Timer Schedules

Several circuits on the heat pump controller can be programmed with a weekly schedule directly on the controller (or its firmware's built-in web interface). This integration exposes those schedules as editable Home Assistant entities so they can be read and changed without touching the physical controller.

Three circuits are wired up: **DHW (Bw)**, **heating (Hkr)**, and the **ventilation module (Luf)**. The remaining timer-program circuits — mixing circuits 1/2/3 (Mk1/Mk2/Mk3), circulation pump (ZIP), pool (Swb), and the combined "all circuits" block — are still deferred; see [Extending to other circuits](#extending-to-other-circuits) below.

**A schedule window does not mean the same thing on every circuit.** On DHW it *blocks* heating; on the heating circuit it *raises* the circuit into day mode. Read your circuit's section below before programming it.

## How a schedule is programmed

Every circuit works the same way, and each has two kinds of entity:

- One **timer program** select, which picks the schedule *shape*. The controller supports three mutually-exclusive shapes:
  - **Whole week** – one schedule applies to every day.
  - **Weekdays + weekend** ("5+2") – one schedule for Monday-Friday, a separate one for Saturday-Sunday.
  - **Per day** – an independent schedule for each individual day of the week.
- A set of **schedule** text entities, one per day or day-group of the active shape.

Each schedule entity holds that day's time windows as a single string of `HH:MM-HH:MM` pairs separated by `/`, for example:

```
12:00-13:00/22:00-23:30
```

Set the value to an empty string to clear all windows for that entity. How many windows fit per day differs per circuit (5 for DHW, 3 for heating and ventilation), and times are always whole minutes — the controller cannot set seconds.

The timer program can be switched from Home Assistant as well as on the physical controller (or its web interface), and both directions are picked up automatically.

### Only the active shape's entities are present

Only the schedule entities of the shape currently selected in that circuit's *timer program* exist as usable entities. The other shapes' entities are **disabled** rather than left permanently unavailable, so the device page collapses them behind a *"+N disabled entities"* button instead of listing them as broken. Each circuit is tracked independently — DHW being on *Per day* while heating is on *Whole week* is perfectly normal.

Changing a timer program — from Home Assistant or on the controller itself — swaps the entity set automatically within one polling interval; no restart or integration reload is needed. Because the entities are disabled rather than deleted, everything you attached to them survives the switch: a renamed entity ID, friendly name, icon, area, labels, and their recorder history all come back unchanged when that shape becomes active again.

> **ℹ️ Note:** Home Assistant reloads an integration ~30 seconds after any of its entities is re-enabled, so switching a timer program is followed by a brief reload of the Luxtronik integration. The new shape's schedule entities themselves appear immediately — the reload happens afterwards and needs no action from you.

Entities of an inactive shape keep a stale `unavailable` state in the state machine (Home Assistant's normal behaviour for a registered entity that no integration is currently providing). Nothing surfaces this in the UI, but a dashboard card that references such an entity by ID directly will show it as unavailable while its shape is inactive.

## DHW Timer Schedule (Blocking Times)

**On the DHW device.** Up to **5 windows per day**, and each window is a **"do not heat" window**: during a configured time span, automatic DHW heating is switched off; outside those spans it runs normally according to the *Mode* setting (see [README § 2.4 DHW](README.md#24-dhw-domestic-hot-water)). This is the opposite polarity from the heating circuit below — the controller calls these windows *Sperrzeiten*, blocking times.

If you need hot water during an active blocking window, switch *Mode* to *Party* to override it temporarily (see the README's [Common Automations](README.md#31-common-automations) section, *Boost hot water* example).

| Name | Entity Type | Description |
| :--- | :--- | :--- |
| **Hot water timer program** | Select | Which schedule shape the controller uses: *Whole week*, *Weekdays + weekend*, or *Per day*. |
| **DHW Timer Schedule (Week)** | Text | Exists while the *Week* shape is active. |
| **DHW Timer Schedule (Weekdays)** | Text | Exists while *Weekday/Weekend* is active; covers Monday-Friday. |
| **DHW Timer Schedule (Weekend)** | Text | Exists while *Weekday/Weekend* is active; covers Saturday-Sunday. |
| **DHW Timer Schedule (Monday)** … **(Sunday)** | Text | One entity per day of the week, present while *Per day* is active. |

The example above (`12:00-13:00/22:00-23:30`) blocks DHW heating over lunch and late in the evening.

## Heating Timer Schedule (Raise / Setback Times)

**On the Heating device.** Up to **3 windows per day**, and a window means the **opposite** of DHW's: inside a window the heating circuit is *raised* (day mode); outside every window it is *lowered* (night setback, by the amount set in the **Heating curve night reduction** number entity). Clearing a schedule therefore does not "disable" it — it leaves the circuit in night setback around the clock.

| Name | Entity Type | Description |
| :--- | :--- | :--- |
| **Heating timer program** | Select | Which schedule shape the controller uses: *Whole week*, *Weekdays + weekend*, or *Per day*. |
| **Heating Timer Schedule (Week)** | Text | Exists while the *Week* shape is active. |
| **Heating Timer Schedule (Weekdays)** | Text | Exists while *Weekday/Weekend* is active; covers Monday-Friday. |
| **Heating Timer Schedule (Weekend)** | Text | Exists while *Weekday/Weekend* is active; covers Saturday-Sunday. |
| **Heating Timer Schedule (Monday)** … **(Sunday)** | Text | One entity per day of the week, present while *Per day* is active. |

So `06:00-12:00/13:00-22:00` runs the heating raised in the morning and again from the afternoon into the evening, and in setback overnight and over lunch.

> **⚠️ A window of `00:00-00:00` does not mean "all day".** The controller reads it as *permanently lowered*: the circuit then runs in night mode only. This is firmware behaviour, documented in the controller's own manual (*Betriebsanleitung Heizungs- und Wärmepumpenregler 2.0/2.1*, document 83055200bDE, section "Einstellen der Schaltzeiten des Heizkreises"), not something this integration imposes.

The schedule only has an effect while the heating *Mode* is **Automatic** — *Party* holds day mode and *Holidays* holds setback regardless of the programmed times.

## Ventilation Timer Schedule

**On the Ventilation device**, so these entities only exist if your unit has an integrated ventilation module (see [README § 2.5 Ventilation](README.md#25-ventilation)). Up to **3 windows per day**. The module is *expected* to follow the heating circuit's raise/setback pattern rather than DHW's blocking one — a window raising the stage rather than suppressing ventilation — but see the note below: that has not been confirmed against a physical unit.

| Name | Entity Type | Description |
| :--- | :--- | :--- |
| **Ventilation timer program** | Select | Which schedule shape the controller uses: *Whole week*, *Weekdays + weekend*, or *Per day*. |
| **Ventilation Timer Schedule (Week)** | Text | Exists while the *Week* shape is active. |
| **Ventilation Timer Schedule (Weekdays)** | Text | Exists while *Weekday/Weekend* is active; covers Monday-Friday. |
| **Ventilation Timer Schedule (Weekend)** | Text | Exists while *Weekday/Weekend* is active; covers Saturday-Sunday. |
| **Ventilation Timer Schedule (Monday)** … **(Sunday)** | Text | One entity per day of the week, present while *Per day* is active. |

> **ℹ️ No unit with a ventilation module has been sampled yet, so four things here are inferred rather than confirmed:**
>
> 1. That a window *raises* the ventilation stage, rather than blocking it the way a DHW window does.
> 2. That the schedule applies only while *Ventilation mode* is *Automatic*.
> 3. That the program selector uses the same *week / 5+2 / per day* codes as the other circuits.
> 4. That the leading index in its parameter names distinguishes start time from end time.
>
> Items 3 and 4 are inferred from the firmware's parameter naming (and are marked as such in the code); items 1 and 2 are inferred from how the other circuits behave. If the shape you select doesn't match what the controller shows, if start and end times look swapped, or if the module behaves the opposite way round from what is described here, please open an issue with a [diagnostics download](ADVANCED_FEATURES.md#diagnostics-download) attached — that is exactly the evidence needed to settle all four.

## Extending to other circuits

The remaining timer-program circuits share the same underlying shape (mode selector + Week/5+2/Per-day time blocks), just with different parameter-name prefixes and row counts:

| Circuit | Mode selector | Prefixes (week / 5+2 / per day) | Rows/day |
| :--- | :--- | :--- | :--- |
| Mixing circuit 1 (Mk1) | `ID_Einst_SuMk1_akt` (283) | `SuMk1W0` / `SuMk125` / `SuMk1TG` | 3 |
| Mixing circuit 2 (Mk2) | `ID_Einst_SuMk2_akt2` (344) | `SuMk2Wo` / `SuMk225` / `SuMk2Tg` | 3 |
| Mixing circuit 3 (Mk3) | `ID_Einst_SuMk3_akt2` (788) | `SuMk3Wo` / `SuMk325` / `SuMk3Tg` | 3 |
| Circulation pump (ZIP) | `ID_Einst_SuZIP_akt` (506) | `SuZIPWo` / `SuZIP25` / `SuZIPTg` | 5 |
| Pool (Swb) | `ID_Einst_SuSwb_akt` (607) | `SuSwbWo` / `SuSwb25` / `SuSwbTg` | 3 |
| All circuits combined (All) | `ID_Einst_SuAll_akt2` (161) | `SuAllWo` / `SuAll25` / `SuAllTg` | 3 |

> **⚠️ Several circuits expose *two* plausible selector parameters, an `_akt` and an `_akt2`, and the one that works is not always the first.** DHW's live selector is `ID_Einst_SUBW_akt2` (405), not `ID_Einst_SUBW_akt` (19); Mk2 and Mk3 and the combined block are the same way. The reliable rule in the library's parameter table is that a circuit's selector sits **immediately before its own time block** — 405 precedes the DHW block at 406, 222 precedes heating's 223, 895 precedes ventilation's 896. The selectors above were picked by that rule; confirm against a diagnostics dump before wiring one up.

Adding one is additive: define a `_TimerCircuit` in `timer_schedule_entities_predefined.py` (mirroring `_HEATING_CIRCUIT`) with that circuit's selector name, row count, `WO`/`25`/`TG` parameter prefixes and name builder, then call `_build_circuit_entities` with a matching set of `SensorKey` entries and translations. No changes to `text.py` itself should be needed — its logic, including the per-circuit active-shape sync that enables and disables entities as a program changes, is already generic per `LuxtronikTimerScheduleTextDescription`. A select entity for the new circuit's own mode selector is one description in `select_entities_predefined.py`, reusing `raw_option_map` to map the HA option names onto the raw `week` / `5+2` / `days` values.

Three things do *not* generalise, and cost a bug each time they are assumed:

- **The parameter-name spelling is per circuit and must be copied verbatim from the library**, never derived: DHW uses `WO`/`TG`, heating uses `W0` (with a digit zero) and `TG`, ventilation uses `Wo`/`Tg`.
- **The naming layout differs too.** DHW and heating name their parameters `<prefix>_zeit_<row>_<slot>`, with the start/end distinction in the trailing slot; ventilation puts it first, as `<prefix>_zeit_<0|1>_<row>_<2*col>`. That is why `_TimerCircuit` takes a `name_builder`. Check which layout a new circuit uses against a real diagnostics dump before wiring it up.
- **The direction of a window is per circuit.** DHW blocks, heating raises; neither polarity can be assumed to carry over to the pool or the circulation pump. Confirm each new circuit against the controller manual before documenting it.

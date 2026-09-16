# Timer Schedules

Several circuits on the heat pump controller can be programmed with a weekly schedule directly on the controller (or its firmware's built-in web interface). This integration exposes those schedules as editable Home Assistant entities so they can be read and changed without touching the physical controller.

Two circuits are wired up: **DHW (Bw)** and **heating (Hkr)**. The **ventilation module (Luf)** has its program selector but no schedule entities yet — its registers are laid out differently, see [Ventilation Timer Schedule](#ventilation-timer-schedule). The remaining timer-program circuits — mixing circuits 1/2/3 (Mk1/Mk2/Mk3), circulation pump (ZIP), pool (Swb), and the combined "all circuits" block — are still deferred; see [Extending to other circuits](#extending-to-other-circuits) below.

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

### What the times mean

**An end time of `00:00` means midnight**, not "unset". `18:00-00:00` is a window running from 18:00 until the end of the day, and it is how the controller itself writes such a window — `23:59` is not needed and leaves a one-minute hole. A start time of `00:00` is equally ordinary: `00:00-12:00` runs from midnight to noon.

**A window counts as unused only when *both* halves are `00:00`.** That is why `00:00-00:00` has its own meaning per circuit (see the heating warning below), while `18:00-00:00` is a perfectly normal window.

So to cover everything outside 12:00–18:00 on a five-window circuit like DHW, the value is:

```
00:00-12:00/18:00-00:00
```

> **ℹ️ Note:** the midnight reading of a trailing `00:00` is observed behaviour, not a documented one. The controller's manual (*Regelaar Deel 1*, document 83055200, revision iNL) covers `00:00-00:00` but says nothing about `HH:MM-00:00`. It is how real controllers store their schedules — including units whose active program uses such a window — so it is safe to rely on, but it is not quotable from the manual.

#### `24:00` as an end time

Most controllers only let you enter times up to `23:59`, and reject `24:00` outright — on those units the manufacturer's own app and web portal will not offer it either. A few controllers do accept it and store it, spelling the end of the day as `24:00` instead of `00:00` (issue [#787](https://github.com/BenPru/luxtronik/issues/787)). The two spellings mean the same window.

The integration handles both without you having to configure anything:

- `24:00` is always accepted as an end time in the text field, on any heat pump.
- If your controller has never been seen holding a `24:00`, the integration writes `00:00` instead — the same window, in the spelling every controller stores. A `24:00` you type will therefore read back as `00:00`.
- The one exception is a whole-day window, `00:00-24:00`: respelled it would become `00:00-00:00`, which is the *unused* row, so on such a controller the integration refuses it instead. Use `00:00-23:59` there.
- The first time the integration reads a `24:00` out of one of your schedule registers, it takes that as proof your controller supports it and remembers it for that heat pump. From then on `24:00` is written through unchanged.

Since only the controller itself can put a `24:00` into a register, that observation is the evidence — there is nothing in the protocol that advertises the capability. If you want `24:00` on a controller that supports it, set it once on the controller or its web interface; the integration will pick it up from the next poll onwards.

> **ℹ️ Note:** the poll that first spots a `24:00` reloads the integration once, so the change takes effect everywhere. It happens at most once per heat pump.

**An empty schedule does not mean "no schedule".** What it does depends on the circuit's polarity, and the two are opposites: on DHW an empty schedule blocks nothing, so hot water follows the *Mode* setting alone; on heating it leaves the circuit lowered around the clock. Read your circuit's section below before clearing one.

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
| **DHW Blocking Times (Week)** | Text | Exists while the *Week* shape is active. |
| **DHW Blocking Times (Weekdays)** | Text | Exists while *Weekday/Weekend* is active; covers Monday-Friday. |
| **DHW Blocking Times (Weekend)** | Text | Exists while *Weekday/Weekend* is active; covers Saturday-Sunday. |
| **DHW Blocking Times (Monday)** … **(Sunday)** | Text | One entity per day of the week, present while *Per day* is active. |

The example above (`12:00-13:00/22:00-23:30`) blocks DHW heating over lunch and late in the evening.

> **⚠️ Leave the field empty for "no restriction".** An empty schedule means DHW is never blocked. Entering a window that spans the whole day (for example `00:00-23:59`) does the opposite of what it looks like: it blocks automatic DHW heating around the clock.

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

**On the Ventilation device**, so it only exists if your unit has an integrated ventilation module (see [README § 2.5 Ventilation](README.md#25-ventilation)). Only the program selector is exposed for now:

| Name | Entity Type | Description |
| :--- | :--- | :--- |
| **Ventilation timer program** | Select | Which schedule shape the controller uses: *Whole week*, *Weekdays + weekend*, or *Per day*. |

The selector does **not** use the same codes as the other circuits: a KHZ LWC 60 with a module reports `3` for *Week*, `4` for *Weekdays + weekend* and `5` for *Per day* (issue #789); units without a module report `0`. The controller's own menu labels the middle option *5+3*.

> **ℹ️ Why there are no schedule text entities yet.** The first unit with a working module that sent a diagnostics download (#789) showed that the ventilation time registers are stored differently from every other circuit: instead of one time per register, each register holds a whole `start-end` window (start minute in the low 16 bits, end minute in the high 16 bits — the same layout the upstream `python-luxtronik` library calls `TimeOfDay2`). Per schedule shape there are *two* blocks of three such windows (on that unit: `05:00-08:30 / 10:00-11:00 / 20:00-21:00` in the first block, `22:00-05:00 / 12:00-12:30 / 16:00-16:30` in the second), and what distinguishes the two blocks — two ventilation stages, on versus off, something else — has not been read off a controller yet. Releases 2026.08.15 to 2026.09.16 exposed these registers as if they were single times; on that unit they rendered as `9284:21-5461:42/...`, and Home Assistant rejected the over-long state on every poll. The entities were withdrawn rather than shaped by a guess, because a wrong shape would mean renaming them later; any registry entries those releases left behind are removed automatically on the next start. The `TimeOfDay2` decoding is in place, so a diagnostics download from a module unit now shows readable windows — if yours does, and you can say what the controller displays next to each row, that is exactly what is needed to bring the entities back.
>
> Two behaviours remain unconfirmed as well: whether a window *raises* the ventilation stage (as heating does) or blocks it (as DHW does), and whether the schedule applies only while *Ventilation mode* is *Automatic*.

## Extending to other circuits

The remaining timer-program circuits share the same underlying shape (mode selector + Week/5+2/Per-day time blocks), just with different parameter-name prefixes and row counts:

| Circuit | Mode selector | Prefixes (week / 5+2 / per day) | Rows/day |
| :--- | :--- | :--- | :--- |
| Mixing circuit 1 (Mk1) | `ID_Einst_SuMk1_akt` (283) | `SuMk1W0` / `SuMk125` / `SuMk1TG` | 3 |
| Mixing circuit 2 (Mk2) | `ID_Einst_SuMk2_akt2` (344) | `SuMk2Wo` / `SuMk225` / `SuMk2Tg` | 3 |
| Mixing circuit 3 (Mk3) | `ID_Einst_SuMk3_akt2` (788) | `SuMk3Wo` / `SuMk325` / `SuMk3Tg` | 3 |
| Circulation pump (ZIP) | `ID_Einst_SuZIP_akt` (506) | `SuZIPWo` / `SuZIP25` / `SuZIPTg` | 5 |
| Pool (Swb) | *unknown* — see below | `SuSwbWo` / `SuSwb25` / `SuSwbTg` | 3 |
| All circuits combined (All) | `ID_Einst_SuAll_akt2` (161) | `SuAllWo` / `SuAll25` / `SuAllTg` | 3 |

> **⚠️ Several circuits expose *two* plausible selector parameters, an `_akt` and an `_akt2`, and the one that works is not always the first.** DHW's live selector is `ID_Einst_SUBW_akt2` (405), not `ID_Einst_SUBW_akt` (19); Mk2 and Mk3 and the combined block are the same way. The reliable rule in the library's parameter table is that a circuit's selector sits **immediately before its own time block** — 405 precedes the DHW block at 406, 222 precedes heating's 223, 895 precedes ventilation's 896. The selectors above were picked by that rule; confirm against a diagnostics dump before wiring one up. The pool circuit shows why: parameter 607 is named `ID_Einst_SuSwb_akt`, yet three units with a non-zero value there report a time of day (06:30, 07:00, 07:30), each followed by an end time in 608 — so it is a time slot and the integration types it as one. Where the pool selector actually lives is not known.

Adding one is additive: define a `_TimerCircuit` in `timer_schedule_entities_predefined.py` (mirroring `_HEATING_CIRCUIT`) with that circuit's selector name, row count, `WO`/`25`/`TG` parameter prefixes and name builder, then call `_build_circuit_entities` with a matching set of `SensorKey` entries and translations. No changes to `text.py` itself should be needed — its logic, including the per-circuit active-shape sync that enables and disables entities as a program changes, is already generic per `LuxtronikTimerScheduleTextDescription`. A select entity for the new circuit's own mode selector is one description in `select_entities_predefined.py`, reusing `raw_option_map` to map the HA option names onto the raw `week` / `5+2` / `days` values.

Three things do *not* generalise, and cost a bug each time they are assumed:

- **The parameter-name spelling is per circuit and must be copied verbatim from the library**, never derived: DHW uses `WO`/`TG`, heating uses `W0` (with a digit zero) and `TG`, ventilation uses `Wo`/`Tg`.
- **The storage layout can differ too.** DHW and heating name their parameters `<prefix>_zeit_<row>_<slot>` with one time per register; ventilation names them `<prefix>_zeit_<0|1>_<row>_<2*col>` and packs a whole window into each register (see above). `_TimerCircuit` takes a `name_builder` for the naming, but a packed circuit also needs a different read/write model in `text.py`. Check both against a real diagnostics dump before wiring a circuit up — the ventilation guess cost a release.
- **The direction of a window is per circuit.** DHW blocks, heating raises; neither polarity can be assumed to carry over to the pool or the circulation pump. Confirm each new circuit against the controller manual before documenting it.

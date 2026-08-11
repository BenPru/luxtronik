# DHW timer-program entities: only create the selected program

Date: 2026-08-11
Status: approved design, not yet implemented

## Problem

The DHW timer-program feature creates all 10 schedule text entities
(`timer_dhw_schedule_week`, `_weekday`, `_weekend`, and one per weekday) for
every install, regardless of which timer program the heat pump actually runs.
`LuxtronikTimerScheduleText.available` returns `False` for the blocks whose
`active_mode` does not match the current value of the mode selector
(`ID_Einst_SUBW_akt2`, parameter 405), so 7 or 9 of the 10 entities are
permanently unavailable. They clutter the device page and dashboards.

## Goal

Only the schedule entities belonging to the currently selected timer program
exist. When the program changes, the entity set follows — without a config
entry reload or a restart. Additionally, expose the program selector itself as
a HA `select` entity so the program can be switched from Home Assistant.

Scope is DHW only. The mechanism is written against the existing
`_TimerCircuit` abstraction so the remaining five circuits (Hkr/Mk1/Mk2/ZIP/Swb)
inherit it when they are added.

## Design

### 1. Active-mode-only entity set (`text.py`)

`async_setup_entry` builds a small sync helper that owns the lifecycle:

- **Desired set:** the descriptions in `TIMER_SCHEDULE_ENTITIES` whose
  `mode_selector_name` parameter exists in `coordinator.data` *and* whose
  `active_mode` equals the current selector value. This is a pure function of
  `LuxtronikCoordinatorData`, so it is directly unit-testable.
- **At setup:** add only the desired entities. For every non-desired key that
  *already has* a registry entry (existing installs, or a mode that was active
  earlier), set `disabled_by = RegistryEntryDisabler.INTEGRATION`. On a fresh
  install the inactive modes were never registered, so nothing exists to disable
  and the device page shows only the active program's blocks. Registry entries
  are looked up with `er.async_get_entity_id(TEXT_DOMAIN, DOMAIN, unique_id)`.
- **On change:** the helper is registered as a coordinator listener via
  `entry.async_on_unload(coordinator.async_add_listener(...))`. Each poll it
  recomputes the desired set; when it differs from the live set it
  1. clears `disabled_by` on the newly active keys (only when it is
     `INTEGRATION` — a user's own disable is never overridden) and adds their
     entities through the retained `async_add_entities` callback, and
  2. removes the stale entities from the state machine with
     `entity.async_remove()` (**not** `force_remove=True`: the registry entry
     must survive) and sets `disabled_by = INTEGRATION` on them.

  Coordinator listener callbacks are synchronous, so the add/remove work is
  scheduled with `entry.async_create_task`.

  A one-time migration runs alongside this: any schedule entity still carrying
  `hidden_by = RegistryEntryHider.INTEGRATION` from the earlier hide-based build
  (see below) gets it cleared, for both active and inactive keys, on the first
  sync pass that touches it.

### Why disable instead of hide, and why not remove the registry entry

The first implementation of this design hid inactive entries
(`hidden_by = RegistryEntryHider.INTEGRATION`) instead of disabling them. Live
verification on a real HA instance (2026.7.2) showed that this does not achieve
the goal: on the **device page**, HA renders hidden entities inline, labelled
"(Hidden)" and showing `unavailable`:

```
Tijdschema (dinsdag) (Verborgen)     unavailable
Tijdschema (week)    (Verborgen)     unavailable
Tijdschema (weekend)                 00:00-11:00/12:00-14:00/17:00-00:00
```

*Disabled* entities, by contrast, are collapsed behind a `+N disabled entities`
button. Hiding only cleans dashboards, entity pickers and auto-generated
views — not the device page, which is where the clutter was reported. So the
mechanism is `disabled_by = RegistryEntryDisabler.INTEGRATION`, not `hidden_by`.

Purging the registry entry outright (instead of hiding or disabling it) was
considered and rejected: it discards everything the user attached to it — a
renamed entity_id, friendly name, icon, area, labels. Today the entity_id is
integration-assigned (`unique_id == entity_id == "text.<prefix>_<key>"`), so the
loss is mostly invisible — but that convention is expected to change toward
HA best practice, where entity_ids are user-owned, and that loss gets worse
once `unique_id` is decoupled from `entity_id`. A program switch silently
reverting user renames would be a genuine bug. Disabling keeps the registry
entry, its customizations, and the recorder history intact; only `disabled_by`
flips.

Cost, accepted because switching timer program is a rare action: clearing
`disabled_by` makes HA's `EntityRegistryDisabledHandler` schedule a config-entry
reload 30 seconds later (`config_entries.RELOAD_AFTER_UPDATE_DELAY`) — enabling
a registry entry is, in HA's model, indistinguishable from a user re-enabling it
by hand, and both are followed by a reload. There is no way to clear
`disabled_by` on an entity without triggering this, short of not using
`disabled_by` at all (which the device-page evidence above rules out). No
suppression hack is used to work around it.

Accepted edge case: if a user manually re-enables an inactive-mode entity via
the registry, HA schedules its own 30s reload for that (same mechanism as
above); on the reload, `_disable_inactive` runs again, finds `disabled_by` is
`None` for a still-inactive key, and sets it back to `INTEGRATION` — so the
manual re-enable does not stick past the reload it itself triggers. Outside of
a reload, the sync only runs its enable/add/remove/disable pass when the
desired entity set differs from the live one, so an unchanged poll
deliberately writes nothing to the registry — no per-poll re-disable loop, and
no per-poll reload either.

Reading the selector is treated as three-valued: "program X", "this controller
has no such selector" (no blocks — nothing to create), and "unreadable this
poll". The last one is not the same as "no program active":
`get_sensor_data` returns `None` both for an absent register and for a present
register whose datatype could not decode the raw value (`SelectionBase` returns
`None` for an unrecognised code), and `key_exists` cannot separate them for
parameter 405, which lies inside upstream's defined index range. So an
unreadable selector makes the sync a complete no-op for that poll — otherwise a
single glitched read would remove all live schedule entities and hide all ten
registry entries, to be undone again by the next good poll.

### Coupling to the entity_id convention

Both `LuxtronikTimerScheduleText.__init__` and the sync helper need the
unique_id. The format is written down **once**, in a shared
`_timer_schedule_unique_id(entry, description)` helper used by both, so that
decoupling unique_id from entity_id later is a single-site change plus a
registry migration — not a hunt for duplicated string formatting.

`LuxtronikTimerScheduleText.available` keeps its mode check. After this change
it is no longer the primary mechanism, but it remains a cheap safety net
covering the window between a coordinator update carrying a new mode and the
scheduled add/remove task running.

Because the registry entry survives, switching a program away and back restores
the same entity_id (including a user-chosen one) with its customizations and
history; dashboard cards and automations referencing it keep working. While a
program is inactive its entity has no state — dashboard cards referencing it
show as unavailable, which is the same behaviour as today.

### 2. Timer-program select entity

Parameter 405 already carries the `TimerProgram` datatype defined in
`lux_overrides.py` (codes `0: "week"`, `1: "5+2"`, `2: "days"`), so no library
work is needed. Additions:

- `const.py`: `LuxParameter.P0405_TIMER_PROGRAM_DHW = "parameters.ID_Einst_SUBW_akt2"`
  and `SensorKey.TIMER_DHW_PROGRAM = "timer_dhw_program"`.
- `select_entities_predefined.py`: a `LuxtronikSelectEntityDescription` on
  `DeviceKey.domestic_water`, `entity_category=EntityCategory.CONFIG`.
- Options are HA-side names `week` / `weekday_weekend` / `daily`, mapped to the
  raw device values `week` / `5+2` / `days`. The raw value `"5+2"` is an awkward
  HA option and translation key; `LuxtronikModeSelector` already supports a
  display→raw mapping through `_option_to_raw`, which is extended to carry this
  explicit mapping instead of relying on `_normalize_select_option`.
- Presence gating is the existing `key_exists(coordinator.data, luxtronik_key)`
  check in `select.py` — register existence, not a firmware version gate.
- Translations for the entity name and the three option states in
  `en/de/nl/cs/pl.json`.

Writing the selector goes through `coordinator.async_write`, which refreshes the
coordinator; the refresh fires the text-platform listener, so the schedule
entities swap immediately after the user changes the program in HA.

### 3. Tests

`tests/test_text.py`:

- desired-set computation returns the right descriptions for each of `week`,
  `5+2`, `days`, and an empty set when the selector parameter is absent
- setup adds only the active mode's entities
- setup disables pre-existing registry entries of the non-active keys, and does
  nothing for non-active keys that have no registry entry
- a mode change on a later coordinator update adds + enables the new mode's
  entities and removes + disables the previous ones, with the registry entries
  of the previous mode still present afterwards
- a user-set `disabled_by = USER` is not cleared when that mode becomes active
- no churn (no add, remove, or registry write) when the mode is unchanged
  between polls
- a `hidden_by = RegistryEntryHider.INTEGRATION` left over from the earlier
  hide-based build is cleared on the next sync pass, for both an active and an
  inactive key (the inactive one is then disabled as usual)
- against a real `hass`/entity registry: entity_id survives a program
  round-trip, the registry entry survives removal, a user rename survives, and
  `disabled_by` flips `INTEGRATION` ↔ `None` across the switch — including
  letting the resulting config-entry reload actually run in-test (the delay is
  collapsed to 0 via monkeypatch rather than skipped or waited out for real)

`tests/test_select.py` and the predefined-entity/translation-coverage tests
cover the new selector: description shape, display→raw option mapping, write of
`5+2` for the `weekday_weekend` option, and presence of the name/state strings
in all five language files.

## Out of scope

- The other five timer circuits.
- Decoupling `unique_id` from `entity_id` (HA best practice) and the registry
  migration that would need — this design only makes sure it stays a
  single-site change.
- Any change to schedule parsing/writing in `LuxtronikTimerScheduleText`.

"""Support for Luxtronik timer-program schedule text entities."""

from __future__ import annotations

import asyncio
import re

from homeassistant.components.text import (
    DOMAIN as TEXT_DOMAIN,
    ENTITY_ID_FORMAT,  # pyright: ignore[reportAttributeAccessIssue]
    TextEntity,
    TextMode,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import (
    RegistryEntryDisabler,
    RegistryEntryHider,
)

from . import LuxtronikConfigEntry
from .base import LuxtronikEntity
from .common import get_sensor_data, key_exists
from .const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_SUPPORTS_TIME_24_00,
    DOMAIN,
    LOGGER,
    LUX_SCHEDULE_TIME_24_00,
    DeviceKey,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikTimerScheduleTextDescription
from .timer_schedule_entities_predefined import TIMER_SCHEDULE_ENTITIES

PARALLEL_UPDATES = 1

_UNSET_TIME = "00:00"
# A packed `TimeOfDay2` register renders both halves at once; this is its
# unused-row spelling (start 0, end 0).
_UNSET_WINDOW = f"{_UNSET_TIME}-{_UNSET_TIME}"
# "24:00" is accepted in the end position only - a start time of "24:00" would
# be meaningless. Accepting it says nothing about whether the controller can
# store it; see `_parse_schedule`.
_PAIR_PATTERN = re.compile(
    r"^([01]\d|2[0-3]):[0-5]\d-((?:[01]\d|2[0-3]):[0-5]\d|24:00)$"
)


def _timer_schedule_unique_id(
    entry: LuxtronikConfigEntry,
    description: LuxtronikTimerScheduleTextDescription,
) -> str:
    """Return the unique_id of a schedule entity.

    Today this is also its default entity_id. The format lives here only, so
    decoupling unique_id from entity_id later (HA best practice) is a
    single-site change plus a registry migration.
    """
    prefix = entry.data[CONF_HA_SENSOR_PREFIX]
    return ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")


def _active_schedule_descriptions(
    coordinator: LuxtronikCoordinator,
    data: LuxtronikCoordinatorData | None,
) -> tuple[list[LuxtronikTimerScheduleTextDescription], set[str]] | None:
    """Return the active schedule blocks and the unreadable selectors.

    A block qualifies when its circuit's mode selector is present on this
    controller and its value equals the block's `active_mode`. Every other
    block is meaningless on the device, so no entity is created for it.

    The second element holds the `mode_selector_name`s that could not be read
    this poll. `get_sensor_data` returns ``None`` both for an absent register
    and for a present one whose datatype could not decode the raw value
    (``SelectionBase`` returns ``None`` for an unrecognised code), and
    `key_exists` cannot tell the two apart for a parameter inside upstream's
    defined index range. Reading a transient decode failure as "no program is
    active" would tear down that circuit's schedule entities and disable their
    registry entries until the next good poll, so the caller leaves those
    circuits untouched instead. The failure is per circuit: an unreadable
    selector on one circuit must not freeze the others.

    Returns ``None`` -- "no information about anything this poll" -- only when
    there is no coordinator data at all.
    """
    if data is None:
        return None

    descriptions: list[LuxtronikTimerScheduleTextDescription] = []
    unreadable: set[str] = set()
    for description in TIMER_SCHEDULE_ENTITIES:
        if not coordinator.entity_active(description):
            continue
        selector_name = description.mode_selector_name
        if selector_name in unreadable:
            continue
        selector_key = f"parameters.{selector_name}"
        if not key_exists(data, selector_key):
            continue
        mode = get_sensor_data(data, selector_key)
        if mode is None:
            LOGGER.debug(
                "Timer program selector %s could not be read this poll - "
                "leaving its schedule entities untouched",
                selector_key,
            )
            unreadable.add(selector_name)
            continue
        if mode != description.active_mode:
            continue
        descriptions.append(description)
    return descriptions, unreadable


class _TimerScheduleSync:
    """Keeps the live schedule entities in step with the active timer program.

    Only the blocks of the running program exist as entities. The registry
    entries of the other blocks are kept but disabled, so a user's rename,
    area, icon and recorder history survive a program switch -- removing the
    registry entry would discard all of it. (An earlier build hid the
    inactive entries instead; see `_enable_active`/`_disable_inactive` for
    the one-time migration off that mechanism.) The exception is a circuit
    whose mode selector could not be read this poll: its blocks are left
    exactly as they were, neither removed nor disabled, since a transient
    decode failure is not evidence that the circuit's program changed.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LuxtronikConfigEntry,
        coordinator: LuxtronikCoordinator,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.async_add_entities = async_add_entities
        self._entities: dict[str, LuxtronikTimerScheduleText] = {}
        # Coordinator updates arrive independently of any in-flight apply, and
        # `async_apply` awaits mid-mutation (each entity removal). Without
        # serializing here, a second update landing during that await would
        # compute `desired` against a dict the first call is still mutating,
        # risking a duplicate registration for the same key.
        self._lock = asyncio.Lock()
        self._closing = False

    async def async_setup(self) -> None:
        """Add the active program's entities and disable the rest."""
        await self.async_apply()

    @callback
    def async_close(self) -> None:
        """Stop applying: the config entry is unloading.

        HA resets the platforms *before* running the entry's on-unload
        callbacks and then awaits (rather than cancels) the entry's pending
        tasks, so an `async_apply` queued just before the unload could
        otherwise add entities to an already-reset platform.
        """
        self._closing = True

    @callback
    def async_sync(self) -> None:
        """Coordinator listener: schedule an add/remove pass."""
        self.entry.async_create_task(self.hass, self.async_apply(), eager_start=False)

    async def async_apply(self) -> None:
        """Bring the live entity set in line with the active program.

        Serialized by `self._lock`: a second call queued behind an in-flight
        one (e.g. two coordinator updates arriving while the first call is
        still awaiting an entity removal) waits for it to finish, then
        re-derives `desired` from the then-current coordinator data instead
        of acting on a stale snapshot -- otherwise it could compute `desired`
        and mutate `self._entities` concurrently with the in-flight call,
        risking a duplicate registration for the same key.

        A circuit whose mode selector could not be read this poll is frozen:
        its blocks are excluded from both `to_remove` and the disable pass,
        so they survive untouched until a poll can actually read that
        selector again.
        """
        if self._closing:
            return
        async with self._lock:
            if self._closing:
                return
            result = _active_schedule_descriptions(
                self.coordinator, self.coordinator.data
            )
            if result is None:
                # Nothing could be concluded this poll: do not add, remove or
                # write anything.
                return
            active, unreadable = result
            desired = {description.key: description for description in active}
            # A circuit whose selector could not be read keeps whatever it
            # has: its blocks are neither removed nor disabled, because we
            # cannot tell which of them the device is actually running.
            frozen = {
                description.key
                for description in TIMER_SCHEDULE_ENTITIES
                if description.mode_selector_name in unreadable
            }
            to_add = [
                description
                for key, description in desired.items()
                if key not in self._entities
            ]
            to_remove = [
                (key, entity)
                for key, entity in self._entities.items()
                if key not in desired and key not in frozen
            ]
            if not to_add and not to_remove:
                return

            registry = er.async_get(self.hass)
            # Enable before adding: EntityPlatform._async_add_entity calls
            # add_to_platform_abort() for a disabled registry entry, so an
            # entity added while its registry entry is still disabled would
            # never come up.
            self._enable_active(registry, set(desired))

            if to_add:
                entities = [
                    LuxtronikTimerScheduleText(
                        self.entry,
                        self.coordinator,
                        description,
                        description.device_key,
                    )
                    for description in to_add
                ]
                for description, entity in zip(to_add, entities, strict=True):
                    self._entities[description.key] = entity
                self.async_add_entities(entities)

            for key, entity in to_remove:
                del self._entities[key]
                await self._async_remove_entity(key, entity)

            self._disable_inactive(registry, set(desired) | frozen)

    async def _async_remove_entity(
        self, key: str, entity: LuxtronikTimerScheduleText
    ) -> None:
        """Take one schedule entity out of the state machine.

        `async_add_entities` is a synchronous callback: it only *schedules*
        the add, so an entry in `self._entities` is not necessarily a live
        entity. `EntityPlatform._async_add_entity` calls
        `add_to_platform_abort()` for a disabled registry entry (setting
        `entity.hass = None`), and a fast enough second program switch can
        reach here before the platform's add task has run at all. Removing
        such an entity would raise on `self.hass.loop`, and - since this runs
        inside one `entry.async_create_task` - would abort the remaining
        removals and the disable pass with it, so every failure is contained
        and logged instead.
        """
        if entity.hass is None:  # pyright: ignore[reportUnnecessaryComparison]
            LOGGER.debug(
                "Timer schedule entity %s was never added to the platform - "
                "nothing to remove",
                key,
            )
            return
        try:
            # No force_remove: the registry entry must survive so the user's
            # customisations and history are still there next time.
            await entity.async_remove()
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Error removing timer schedule entity %s", key)

    def _enable_active(
        self, registry: er.EntityRegistry, desired_keys: set[str]
    ) -> None:
        for description in TIMER_SCHEDULE_ENTITIES:
            if description.key not in desired_keys:
                continue
            entity_id = registry.async_get_entity_id(
                TEXT_DOMAIN, DOMAIN, _timer_schedule_unique_id(self.entry, description)
            )
            if entity_id is None:
                continue
            registry_entry = registry.async_get(entity_id)
            if (
                registry_entry is not None
                and registry_entry.hidden_by is RegistryEntryHider.INTEGRATION
            ):
                # Migration: an earlier build hid inactive blocks instead of
                # disabling them. Scrub the stale hidden_by so it doesn't
                # linger on installs that ran that build.
                registry.async_update_entity(entity_id, hidden_by=None)
            if (
                registry_entry is not None
                and registry_entry.disabled_by is RegistryEntryDisabler.INTEGRATION
            ):
                # Clearing here, before the entity is added, is required:
                # EntityPlatform._async_add_entity calls
                # add_to_platform_abort() for a disabled registry entry.
                # This clear makes HA schedule a config-entry reload 30s from
                # now (config_entries.RELOAD_AFTER_UPDATE_DELAY) - accepted,
                # since switching timer program is rare.
                registry.async_update_entity(entity_id, disabled_by=None)

    def _disable_inactive(
        self, registry: er.EntityRegistry, desired_keys: set[str]
    ) -> None:
        for description in TIMER_SCHEDULE_ENTITIES:
            if description.key in desired_keys:
                continue
            entity_id = registry.async_get_entity_id(
                TEXT_DOMAIN, DOMAIN, _timer_schedule_unique_id(self.entry, description)
            )
            if entity_id is None:
                continue
            registry_entry = registry.async_get(entity_id)
            if (
                registry_entry is not None
                and registry_entry.hidden_by is RegistryEntryHider.INTEGRATION
            ):
                # Migration: see _enable_active.
                registry.async_update_entity(entity_id, hidden_by=None)
            # disabled_by USER is the user's own decision and is left alone.
            if registry_entry is not None and registry_entry.disabled_by is None:
                registry.async_update_entity(
                    entity_id, disabled_by=RegistryEntryDisabler.INTEGRATION
                )


async def async_setup_entry(  # pragma: no cover
    hass: HomeAssistant,
    entry: LuxtronikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    if not coordinator.last_update_success:
        return

    sync = _TimerScheduleSync(hass, entry, coordinator, async_add_entities)
    # Registered before the listener so the closing flag is in place for
    # every pass the listener can ever schedule.
    entry.async_on_unload(sync.async_close)
    await sync.async_setup()
    entry.async_on_unload(coordinator.async_add_listener(sync.async_sync))


def _parse_schedule(value: str, max_rows: int) -> list[tuple[str, str]]:
    """Parse a "HH:MM-HH:MM/HH:MM-HH:MM/..." schedule string into pairs.

    Returns exactly what the user typed, "24:00" included; deciding what
    actually reaches the device is `async_set_value`'s job, because that
    decision needs the value currently on the device as well.

    Raises ServiceValidationError if the string doesn't match the expected
    shape or supplies more entries than the block has rows.
    """
    if value == "":
        return []

    entries = value.split("/")
    # fullmatch, not match: "$" also matches before a trailing newline, and a
    # trailing-newline end time slipping through would defeat the "24:00"
    # handling in `async_set_value`, which compares the end time as a
    # string.
    if len(entries) > max_rows or not all(
        _PAIR_PATTERN.fullmatch(entry) for entry in entries
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_timer_schedule",
            translation_placeholders={"value": value, "max_rows": str(max_rows)},
        )
    return [(entry[:5], entry[6:]) for entry in entries]


class LuxtronikTimerScheduleText(
    LuxtronikEntity[LuxtronikTimerScheduleTextDescription],  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    TextEntity,
):
    """A single timer-program schedule block, edited as a delimited string.

    Reads/writes multiple raw parameters (one start/end pair per row, or one
    packed window register per row - see the description's `row_names`) at
    once, so it deliberately does not go through `LuxtronikEntity`'s
    `luxtronik_key`-based state handling -- reading and writing are fully
    custom, similar to how `LuxtronikDateEntity` bypasses `_get_value`.
    """

    def __init__(
        self,
        entry: LuxtronikConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikTimerScheduleTextDescription,
        device_info_ident: DeviceKey,
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
        )
        self.entity_id = _timer_schedule_unique_id(entry, description)
        self._attr_unique_id = self.entity_id
        # Refreshed by the reload that arming the flag triggers, which
        # rebuilds every entity (see
        # `LuxtronikCoordinator._detect_time_24_00_support`). It is stale for
        # the length of that reload, and on first setup the flag is armed
        # before the update listener is even registered - the write-diff
        # guard in `async_set_value` is what covers those gaps, so it is not
        # dead code.
        self._supports_24_00 = bool(entry.data.get(CONF_SUPPORTS_TIME_24_00, False))
        self._attr_mode = TextMode.TEXT
        self._attr_native_min = 0
        # Each "HH:MM-HH:MM" pair is 11 chars, joined by a single "/". The
        # width is guaranteed by the `TimeOfDay` and `TimeOfDay2` datatypes,
        # which always render "HH:MM" halves - see their docstrings in
        # `lux_overrides`.
        self._attr_native_max = len(description.row_names) * 12 - 1
        self._attr_native_value = None
        # Last over-budget value warned about; never reset on purpose, so a
        # value that comes back after a good poll is not reported twice.
        self._reported_over_long: str | None = None

    @property
    def available(self) -> bool:
        """Only the schedule block matching the circuit's active mode is available."""
        if not super().available:
            return False
        data = self.coordinator.data
        if data is None:
            return False
        current_mode = get_sensor_data(
            data, f"parameters.{self.entity_description.mode_selector_name}"
        )
        return current_mode == self.entity_description.active_mode

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        data = self.coordinator.data if data is None else data
        if data is None:
            return

        pairs = []
        for names in self.entity_description.row_names:
            if len(names) == 1:
                # Packed register: the datatype already renders the window.
                window = get_sensor_data(data, f"parameters.{names[0]}")
                if window in (None, _UNSET_WINDOW):
                    continue
                pairs.append(window)
                continue
            start_name, end_name = names
            start = get_sensor_data(data, f"parameters.{start_name}")
            end = get_sensor_data(data, f"parameters.{end_name}")
            if start in (None, _UNSET_TIME) and end in (None, _UNSET_TIME):
                continue
            pairs.append(f"{start}-{end}")
        value = "/".join(pairs)

        # `TextEntity.state` raises past `native_max`, and the coordinator
        # reports that as an unexpected listener error on every poll. The
        # budget holds as long as the datatype renders fixed-width pairs, so
        # an overrun means the registers do not hold what this entity
        # assumes (the ventilation block once decoded as "9284:21", #789).
        # Report it once and show no state rather than break every update.
        if len(value) > self._attr_native_max:
            if value != self._reported_over_long:
                self._reported_over_long = value
                LOGGER.warning(
                    "%s: schedule %r does not fit the %d-character budget - "
                    "the registers behind it are not decoded as expected; "
                    "please report this at "
                    "https://github.com/BenPru/luxtronik/issues with the "
                    "integration diagnostics download",
                    self.entity_id,
                    value,
                    self._attr_native_max,
                )
            value = None
        self._attr_native_value = value

        super()._handle_coordinator_update()

    async def async_set_value(self, value: str) -> None:
        """Handle a user-edited schedule string.

        Rows beyond the supplied entries are cleared to 00:00-00:00 so a
        shortened string actually removes the trailing rows on the device,
        rather than leaving stale values in effect. Changed start/end values
        (up to 10 for a 5-row block) are queued and written in a single
        `async_write_many` batch, so the device sees one write cycle and the
        coordinator refreshes once - instead of up to 10 sequential
        `async_write` calls each triggering a full refresh.
        """
        row_names = self.entity_description.row_names
        pairs = _parse_schedule(value, len(row_names))

        data = self.coordinator.data
        writes: list[tuple[str, str]] = []
        for index, names in enumerate(row_names):
            start, typed_end = (
                pairs[index] if index < len(pairs) else (_UNSET_TIME, _UNSET_TIME)
            )
            # A packed register holds minutes 0-1439 per half, so "24:00"
            # can never be stored there whatever the per-entry latch says;
            # it is always respelled as "00:00". `TimeOfDay2.to_heatpump`
            # would otherwise reject 1440 and the row would silently stay.
            packed = len(names) == 1
            supports_24_00 = self._supports_24_00 and not packed
            # "24:00" only reaches a controller already known to store it;
            # everywhere else it becomes "00:00", the same instant in the
            # spelling every controller accepts. See
            # `LuxtronikCoordinator._detect_time_24_00_support`.
            #
            # The one window that cannot be respelled is the whole day:
            # "00:00-00:00" is the unused row, so "00:00-24:00" would flip
            # into the opposite of what was asked. Refuse it rather than
            # silently choose "23:59" on the user's behalf.
            if (
                not supports_24_00
                and start == _UNSET_TIME
                and typed_end == LUX_SCHEDULE_TIME_24_00
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="timer_schedule_all_day_unsupported",
                    translation_placeholders={"value": value},
                )
            end = (
                typed_end
                if supports_24_00 or typed_end != LUX_SCHEDULE_TIME_24_00
                else _UNSET_TIME
            )

            if packed:
                window = f"{start}-{end}"
                if get_sensor_data(data, f"parameters.{names[0]}") != window:
                    writes.append((names[0], window))
                continue

            start_name, end_name = names
            if get_sensor_data(data, f"parameters.{start_name}") != start:
                writes.append((start_name, start))
            current_end = get_sensor_data(data, f"parameters.{end_name}")
            if current_end != end and not (
                # The user asked for the midnight the device already holds,
                # just spelled the other way: leave it alone rather than
                # rewrite it as part of an edit to some other row. Keyed on
                # what was *typed*, not on the normalized `end`, so clearing a
                # row still clears it - "00:00" here is a request for an
                # unused row, and a row left at 86400 would read back as an
                # all-day window instead (see TIMER_SCHEDULES.md).
                not supports_24_00
                and typed_end == LUX_SCHEDULE_TIME_24_00
                and current_end == LUX_SCHEDULE_TIME_24_00
            ):
                writes.append((end_name, end))

        if writes:
            data = await self.coordinator.async_write_many(writes)

        self._handle_coordinator_update(data)

"""Support for Luxtronik timer-program schedule text entities."""

from __future__ import annotations

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
from homeassistant.helpers.entity_registry import RegistryEntryHider

from . import LuxtronikConfigEntry
from .base import LuxtronikEntity
from .common import get_sensor_data, key_exists
from .const import CONF_HA_SENSOR_PREFIX, DOMAIN, DeviceKey
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikTimerScheduleTextDescription
from .timer_schedule_entities_predefined import TIMER_SCHEDULE_ENTITIES

PARALLEL_UPDATES = 1

_UNSET_TIME = "00:00"
_PAIR_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")


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
) -> list[LuxtronikTimerScheduleTextDescription]:
    """Return the schedule blocks belonging to the circuit's active program.

    A block qualifies when the circuit's mode selector is present on this
    controller and its value equals the block's `active_mode`. Every other
    block is meaningless on the device, so no entity is created for it.
    """
    if data is None:
        return []

    descriptions: list[LuxtronikTimerScheduleTextDescription] = []
    for description in TIMER_SCHEDULE_ENTITIES:
        if not coordinator.entity_active(description):
            continue
        selector_key = f"parameters.{description.mode_selector_name}"
        if not key_exists(data, selector_key):
            continue
        if get_sensor_data(data, selector_key) != description.active_mode:
            continue
        descriptions.append(description)
    return descriptions


class _TimerScheduleSync:
    """Keeps the live schedule entities in step with the active timer program.

    Only the blocks of the running program exist as entities. The registry
    entries of the other blocks are kept but hidden, so a user's rename,
    area, icon and recorder history survive a program switch -- removing the
    registry entry would discard all of it.
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

    async def async_setup(self) -> None:
        """Add the active program's entities and hide the rest."""
        await self.async_apply()

    @callback
    def async_sync(self) -> None:
        """Coordinator listener: schedule an add/remove pass."""
        self.entry.async_create_task(self.hass, self.async_apply(), eager_start=False)

    async def async_apply(self) -> None:
        """Bring the live entity set in line with the active program."""
        desired = {
            description.key: description
            for description in _active_schedule_descriptions(
                self.coordinator, self.coordinator.data
            )
        }
        to_add = [
            description
            for key, description in desired.items()
            if key not in self._entities
        ]
        to_remove = [
            (key, entity)
            for key, entity in self._entities.items()
            if key not in desired
        ]
        if not to_add and not to_remove:
            return

        registry = er.async_get(self.hass)
        # Unhide before adding: an entity added while its registry entry is
        # hidden would stay hidden.
        self._unhide_active(registry, set(desired))

        if to_add:
            entities = [
                LuxtronikTimerScheduleText(
                    self.entry, self.coordinator, description, description.device_key
                )
                for description in to_add
            ]
            for description, entity in zip(to_add, entities, strict=True):
                self._entities[description.key] = entity
            self.async_add_entities(entities)

        for key, entity in to_remove:
            del self._entities[key]
            # No force_remove: the registry entry must survive so the user's
            # customisations and history are still there next time.
            await entity.async_remove()

        self._hide_inactive(registry, set(desired))

    def _unhide_active(
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
                registry.async_update_entity(entity_id, hidden_by=None)

    def _hide_inactive(
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
            # hidden_by USER is the user's own decision and is left alone.
            if registry_entry is not None and registry_entry.hidden_by is None:
                registry.async_update_entity(
                    entity_id, hidden_by=RegistryEntryHider.INTEGRATION
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
    await sync.async_setup()
    entry.async_on_unload(coordinator.async_add_listener(sync.async_sync))


def _parse_schedule(value: str, max_rows: int) -> list[tuple[str, str]]:
    """Parse a "HH:MM-HH:MM/HH:MM-HH:MM/..." schedule string into pairs.

    Raises ServiceValidationError if the string doesn't match the expected
    shape or supplies more entries than the block has rows.
    """
    if value == "":
        return []

    entries = value.split("/")
    if len(entries) > max_rows or not all(
        _PAIR_PATTERN.match(entry) for entry in entries
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

    Reads/writes multiple raw parameters (one start/end pair per row) at
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
        self._attr_mode = TextMode.TEXT
        self._attr_native_min = 0
        # Each "HH:MM-HH:MM" pair is 11 chars, joined by a single "/".
        self._attr_native_max = len(description.row_names) * 12 - 1
        self._attr_native_value = None

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
        for start_name, end_name in self.entity_description.row_names:
            start = get_sensor_data(data, f"parameters.{start_name}")
            end = get_sensor_data(data, f"parameters.{end_name}")
            if start in (None, _UNSET_TIME) and end in (None, _UNSET_TIME):
                continue
            pairs.append(f"{start}-{end}")
        self._attr_native_value = "/".join(pairs)

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
        for index, (start_name, end_name) in enumerate(row_names):
            start, end = (
                pairs[index] if index < len(pairs) else (_UNSET_TIME, _UNSET_TIME)
            )
            if get_sensor_data(data, f"parameters.{start_name}") != start:
                writes.append((start_name, start))
            if get_sensor_data(data, f"parameters.{end_name}") != end:
                writes.append((end_name, end))

        if writes:
            data = await self.coordinator.async_write_many(writes)

        self._handle_coordinator_update(data)

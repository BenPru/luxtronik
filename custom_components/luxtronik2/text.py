"""Support for Luxtronik timer-program schedule text entities."""

from __future__ import annotations

import re

from homeassistant.components.text import (
    ENTITY_ID_FORMAT,  # pyright: ignore[reportAttributeAccessIssue]
    TextEntity,
    TextMode,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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


async def async_setup_entry(  # pragma: no cover
    hass: HomeAssistant,
    entry: LuxtronikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    if not coordinator.last_update_success:
        return

    async_add_entities(
        [
            LuxtronikTimerScheduleText(
                entry, coordinator, description, description.device_key
            )
            for description in TIMER_SCHEDULE_ENTITIES
            if (
                coordinator.entity_active(description)
                and key_exists(
                    coordinator.data, f"parameters.{description.mode_selector_name}"
                )
            )
        ]
    )


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
        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
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

        self.async_write_ha_state()
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

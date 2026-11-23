"""Helper class with all EVU logic"""

import calendar
from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import LOGGER, LuxOperationMode, SensorAttrKey as SA


class LuxtronikEVUTracker:
    """Luxtronik EVU tracker class"""

    def __init__(self):
        self._last_state = None
        self._evu_first_start: time | None = None
        self._evu_first_end: time | None = None
        self._evu_second_start: time | None = None
        self._evu_second_end: time | None = None
        self._evu_days: list[int] = []
        self._active_slot: int | None = None
        self._slot_day: date | None = None
        self._daily_starts = 0
        self._resuming = False

    def update(self, current_value: str | None, now: datetime | None = None):
        """Learn paired EVU transitions, optionally replaying historical timestamps."""
        now = now if now is not None else dt_util.now()
        time_now = time(now.hour, now.minute)
        weekday = now.weekday()
        evu = LuxOperationMode.evu

        if current_value not in LuxOperationMode:
            self._last_state = None
            self._active_slot = None
            return

        if self._resuming:
            self.resume(current_value)
            return

        if self._last_state is None:
            self._last_state = current_value
            return

        if current_value == evu and self._last_state != evu:
            if weekday not in self._evu_days:
                self._evu_days.append(weekday)
            if self._slot_day != now.date():
                self._slot_day = now.date()
                self._daily_starts = 0
            if self._daily_starts >= 2:
                LOGGER.warning("EVU schedule supports only two time windows per day")
                self._last_state = current_value
                self._active_slot = None
                return
            first_slot = self._daily_starts == 0
            self._daily_starts = 1 if first_slot else 2
            self._active_slot = 0 if first_slot else 1
            if first_slot:
                self._evu_first_start = time_now
            else:
                self._evu_second_start = time_now

        elif current_value != evu and self._last_state == evu:
            if self._active_slot == 0:
                self._evu_first_end = time_now
            elif self._active_slot == 1:
                self._evu_second_end = time_now
            self._active_slot = None

        self._last_state = current_value

    def resume(self, current_value: str | None) -> None:
        """Resume without inventing a transition during downtime or a history query."""
        if current_value != self._last_state:
            self._active_slot = None
        self._last_state = current_value
        self._resuming = False

    def get_next_event_minutes(self) -> int | None:
        now = dt_util.now().replace(second=0, microsecond=0)
        events = []
        for start, end in (
            (self._evu_first_start, self._evu_first_end),
            (self._evu_second_start, self._evu_second_end),
        ):
            if start is not None:
                events.append((start, 0))
            if end is not None:
                events.append((end, int(start is not None and end < start)))
        candidates = []
        for offset in range(-1, 8):
            day = now.date() + timedelta(days=offset)
            if self._evu_days and day.weekday() not in self._evu_days:
                continue
            for event_time, day_shift in events:
                event = datetime.combine(
                    day + timedelta(days=day_shift), event_time, now.tzinfo
                )
                minutes = int((event.timestamp() - now.timestamp()) / 60)
                if minutes > 0:
                    candidates.append(minutes)
        return min(candidates) if candidates else None

    def restore_attributes(self, attributes: Mapping[str, Any]) -> None:
        """Restore the learned schedule, including stores from older releases."""
        for key, name in (
            (SA.EVU_FIRST_START_TIME, "_evu_first_start"),
            (SA.EVU_FIRST_END_TIME, "_evu_first_end"),
            (SA.EVU_SECOND_START_TIME, "_evu_second_start"),
            (SA.EVU_SECOND_END_TIME, "_evu_second_end"),
        ):
            value = attributes.get(key, "")
            try:
                parsed = time.fromisoformat(value) if value else None
            except (TypeError, ValueError):
                LOGGER.warning("Ignoring invalid restored EVU time %s: %r", key, value)
                parsed = None
            setattr(self, name, parsed)
        days = attributes.get(SA.EVU_DAYS, "")
        self._evu_days = [
            index
            for index, name in enumerate(calendar.day_name)
            if isinstance(days, str) and name in days.split(",")
        ]

    def as_dict(self) -> dict[str, Any]:
        """Serialize schedule and transition context for RestoreEntity."""
        return {
            "attributes": self.get_attributes(),
            "last_state": self._last_state,
            "active_slot": self._active_slot,
            "slot_day": self._slot_day.isoformat() if self._slot_day else None,
            "daily_starts": self._daily_starts,
        }

    def restore(self, data: Mapping[str, Any]) -> None:
        """Restore transition context without treating startup as an EVU event."""
        self.restore_attributes(data.get("attributes", {}))
        self._last_state = data.get("last_state")
        self._active_slot = data.get("active_slot")
        self._daily_starts = data.get("daily_starts", 0)
        self._slot_day = (
            date.fromisoformat(data["slot_day"]) if data.get("slot_day") else None
        )
        self._resuming = True

    def get_attributes(self) -> dict[str, str]:
        return {
            SA.EVU_FIRST_START_TIME: self._format_time(self._evu_first_start),
            SA.EVU_FIRST_END_TIME: self._format_time(self._evu_first_end),
            SA.EVU_SECOND_START_TIME: self._format_time(self._evu_second_start),
            SA.EVU_SECOND_END_TIME: self._format_time(self._evu_second_end),
            SA.EVU_DAYS: self._format_days(self._evu_days),
            SA.EVU_MINUTES_UNTIL_NEXT_EVENT: str(self.get_next_event_minutes() or ""),
        }

    def get_evu_status_suffix(self, current_value: str | None) -> str:
        """Return EVU status suffix for status text."""
        evu_event_minutes = self.get_next_event_minutes()
        if evu_event_minutes is None:
            return ""
        if current_value == LuxOperationMode.evu:
            return f"EVU until {evu_event_minutes} min"
        if evu_event_minutes <= 30:
            return f"EVU in {evu_event_minutes} min"
        return ""

    def _format_time(self, value: time | None) -> str:
        return "" if value is None else value.strftime("%H:%M")

    def _format_days(self, days: list[int]) -> str:
        return ",".join(calendar.day_name[d] for d in sorted(days))

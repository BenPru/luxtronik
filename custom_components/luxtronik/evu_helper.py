"""Helper class with all EVU logic"""

from datetime import time
import calendar
from homeassistant.util import dt as dt_util
from .const import LuxOperationMode, SensorAttrKey as SA


class LuxtronikEVUTracker:
    """Luxtronik EVU tracker class"""

    def __init__(self):
        self._last_state = None
        self._cache = {
            SA.EVU_FIRST_START_TIME: time.min,
            SA.EVU_FIRST_END_TIME: time.min,
            SA.EVU_SECOND_START_TIME: time.min,
            SA.EVU_SECOND_END_TIME: time.min,
            SA.EVU_DAYS: [],
        }

    def update(self, current_value: str | None):
        """Update EVU state based on current value."""
        now = dt_util.now()
        time_now = time(now.hour, now.minute)
        weekday = now.weekday()
        evu = LuxOperationMode.evu.value

        if current_value is None or self._last_state is None:
            self._last_state = current_value
            return

        if current_value == evu and self._last_state != evu:
            if weekday not in self._cache[SA.EVU_DAYS]:
                self._cache[SA.EVU_DAYS].append(weekday)
            if self._should_use_first_slot(time_now):
                self._cache[SA.EVU_FIRST_START_TIME] = time_now
            else:
                self._cache[SA.EVU_SECOND_START_TIME] = time_now

        elif current_value != evu and self._last_state == evu:
            if self._should_use_first_slot(time_now):
                self._cache[SA.EVU_FIRST_END_TIME] = time_now
            else:
                self._cache[SA.EVU_SECOND_END_TIME] = time_now

        self._last_state = current_value

    def _should_use_first_slot(self, time_now: time) -> bool:
        return (
            self._cache[SA.EVU_FIRST_START_TIME] == time.min
            or time_now <= self._cache[SA.EVU_FIRST_START_TIME]
            or time_now <= self._cache[SA.EVU_FIRST_END_TIME]
        )

    def get_next_event_minutes(self) -> int | None:
        now = dt_util.now()
        time_now = time(now.hour, now.minute)
        weekday = now.weekday()

        evu_time = self._get_next_event_time(time_now)
        if evu_time == time.min:
            return None

        evu_hours = (24 if evu_time < time_now else 0) + evu_time.hour
        evu_pause = 0

        if self._cache[SA.EVU_DAYS] and weekday not in self._cache[SA.EVU_DAYS]:
            evu_pause += (24 - now.hour) * 60 - now.minute
            evu_time = self._cache[SA.EVU_FIRST_START_TIME]
            for i in range(1, 7):
                next_day = (weekday + i) % 7
                if next_day in self._cache[SA.EVU_DAYS]:
                    return evu_time.hour * 60 + evu_time.minute + evu_pause
                evu_pause += 1440
        else:
            return (evu_hours - time_now.hour) * 60 + evu_time.minute - time_now.minute

    def _get_next_event_time(self, time_now: time) -> time:
        candidates = [
            self._cache[SA.EVU_FIRST_START_TIME],
            self._cache[SA.EVU_FIRST_END_TIME],
            self._cache[SA.EVU_SECOND_START_TIME],
            self._cache[SA.EVU_SECOND_END_TIME],
        ]
        future_events = [t for t in candidates if t > time_now and t != time.min]
        return (
            min(future_events)
            if future_events
            else self._fallback_event_time(candidates)
        )

    def _fallback_event_time(self, candidates: list[time]) -> time:
        valid_times = [t for t in candidates if t != time.min]
        return min(valid_times) if valid_times else time.min

    def get_attributes(self) -> dict[str, str]:
        return {
            SA.EVU_FIRST_START_TIME: self._format_time(
                self._cache[SA.EVU_FIRST_START_TIME]
            ),
            SA.EVU_FIRST_END_TIME: self._format_time(
                self._cache[SA.EVU_FIRST_END_TIME]
            ),
            SA.EVU_SECOND_START_TIME: self._format_time(
                self._cache[SA.EVU_SECOND_START_TIME]
            ),
            SA.EVU_SECOND_END_TIME: self._format_time(
                self._cache[SA.EVU_SECOND_END_TIME]
            ),
            SA.EVU_DAYS: self._format_days(self._cache[SA.EVU_DAYS]),
            SA.EVU_MINUTES_UNTIL_NEXT_EVENT: str(self.get_next_event_minutes() or ""),
        }

    def get_evu_status_suffix(self, current_value: str | None) -> str:
        """Return EVU status suffix for status text."""
        evu_event_minutes = self.get_next_event_minutes()
        if evu_event_minutes is None:
            return ""
        if current_value == LuxOperationMode.evu.value:
            return f"EVU until {evu_event_minutes} min"
        if evu_event_minutes <= 30:
            return f"EVU in {evu_event_minutes} min"
        return ""

    def _format_time(self, value: time) -> str:
        return "" if value == time.min else value.strftime("%H:%M")

    def _format_days(self, days: list[int]) -> str:
        return ",".join(calendar.day_name[d] for d in days)

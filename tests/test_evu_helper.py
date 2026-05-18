"""Tests for custom_components.luxtronik.evu_helper."""

from __future__ import annotations

from datetime import time
from unittest.mock import patch

from custom_components.luxtronik.const import LuxOperationMode, SensorAttrKey as SA
from custom_components.luxtronik.evu_helper import LuxtronikEVUTracker


class TestEVUTrackerInit:
    def test_initial_state(self):
        tracker = LuxtronikEVUTracker()
        assert tracker._last_state is None
        assert tracker._evu_first_start == time.min
        assert tracker._evu_first_end == time.min
        assert tracker._evu_second_start == time.min
        assert tracker._evu_second_end == time.min
        assert tracker._evu_days == []


class TestEVUTrackerUpdate:
    def test_first_update_sets_last_state(self):
        tracker = LuxtronikEVUTracker()
        tracker.update("heating")
        assert tracker._last_state == "heating"

    def test_none_value_sets_last_state(self):
        tracker = LuxtronikEVUTracker()
        tracker.update(None)
        assert tracker._last_state is None

    @patch("custom_components.luxtronik.evu_helper.dt_util")
    def test_evu_start_recorded(self, mock_dt):
        from datetime import datetime

        mock_dt.now.return_value = datetime(2024, 1, 1, 10, 30)  # Monday

        tracker = LuxtronikEVUTracker()
        tracker._last_state = "heating"  # previous state was non-evu
        tracker.update(LuxOperationMode.evu)

        assert 0 in tracker._evu_days  # Monday
        assert tracker._evu_first_start == time(10, 30)

    @patch("custom_components.luxtronik.evu_helper.dt_util")
    def test_evu_end_recorded(self, mock_dt):
        from datetime import datetime

        mock_dt.now.return_value = datetime(2024, 1, 1, 11, 0)

        tracker = LuxtronikEVUTracker()
        tracker._last_state = LuxOperationMode.evu  # previous state was evu
        tracker.update("heating")  # EVU ended

        assert tracker._evu_first_end == time(11, 0)


class TestEVUTrackerGetNextEventMinutes:
    def test_no_events_returns_none(self):
        tracker = LuxtronikEVUTracker()
        assert tracker.get_next_event_minutes() is None

    @patch("custom_components.luxtronik.evu_helper.dt_util")
    def test_next_event_in_future(self, mock_dt):
        from datetime import datetime

        mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0)  # Monday

        tracker = LuxtronikEVUTracker()
        tracker._evu_first_start = time(12, 0)
        tracker._evu_days = [0]  # Monday

        minutes = tracker.get_next_event_minutes()
        assert minutes is not None
        assert minutes == 120  # 2 hours ahead


class TestEVUTrackerGetAttributes:
    def test_get_attributes(self):
        tracker = LuxtronikEVUTracker()
        attrs = tracker.get_attributes()
        assert SA.EVU_FIRST_START_TIME in attrs
        assert SA.EVU_FIRST_END_TIME in attrs
        assert SA.EVU_SECOND_START_TIME in attrs
        assert SA.EVU_SECOND_END_TIME in attrs
        assert SA.EVU_DAYS in attrs
        assert SA.EVU_MINUTES_UNTIL_NEXT_EVENT in attrs

    def test_get_attributes_empty_defaults(self):
        tracker = LuxtronikEVUTracker()
        attrs = tracker.get_attributes()
        assert attrs[SA.EVU_FIRST_START_TIME] == ""
        assert attrs[SA.EVU_FIRST_END_TIME] == ""
        assert attrs[SA.EVU_DAYS] == ""

    def test_get_attributes_with_data(self):
        tracker = LuxtronikEVUTracker()
        tracker._evu_first_start = time(8, 30)
        tracker._evu_first_end = time(10, 0)
        tracker._evu_days = [0, 2, 4]  # Mon, Wed, Fri
        attrs = tracker.get_attributes()
        assert attrs[SA.EVU_FIRST_START_TIME] == "08:30"
        assert attrs[SA.EVU_FIRST_END_TIME] == "10:00"
        assert "Monday" in attrs[SA.EVU_DAYS]

    def test_evu_status_suffix_active(self):
        tracker = LuxtronikEVUTracker()
        with patch.object(tracker, "get_next_event_minutes", return_value=15):
            result = tracker.get_evu_status_suffix(LuxOperationMode.evu)
        assert "EVU until" in result
        assert "15" in result

    def test_evu_status_suffix_upcoming(self):
        tracker = LuxtronikEVUTracker()
        with patch.object(tracker, "get_next_event_minutes", return_value=20):
            result = tracker.get_evu_status_suffix("heating")
        assert "EVU in" in result
        assert "20" in result

    def test_evu_status_suffix_far_away(self):
        tracker = LuxtronikEVUTracker()
        with patch.object(tracker, "get_next_event_minutes", return_value=60):
            result = tracker.get_evu_status_suffix("heating")
        assert result == ""

    def test_evu_status_suffix_no_events(self):
        tracker = LuxtronikEVUTracker()
        result = tracker.get_evu_status_suffix("heating")
        assert result == ""

    def test_update_second_slot(self):
        """EVU transitions use second slot when first slot already used."""
        from datetime import datetime as dt_cls

        tracker = LuxtronikEVUTracker()

        # Pre-fill first slot so _should_use_first_slot returns False
        tracker._evu_first_start = time(6, 0)
        tracker._evu_first_end = time(8, 0)

        # Simulate EVU activation at 14:00 (after first slot)
        tracker._last_state = "heating"
        fake_pm = dt_cls(2024, 1, 2, 14, 0)
        with patch("custom_components.luxtronik.evu_helper.dt_util") as mock_dt:
            mock_dt.now.return_value = fake_pm
            tracker.update(LuxOperationMode.evu)
        assert tracker._evu_second_start == time(14, 0)

        # Simulate EVU deactivation at 16:00
        fake_pm_end = dt_cls(2024, 1, 2, 16, 0)
        with patch("custom_components.luxtronik.evu_helper.dt_util") as mock_dt:
            mock_dt.now.return_value = fake_pm_end
            tracker.update("heating")
        assert tracker._evu_second_end == time(16, 0)


class TestShouldUseFirstSlot:
    def test_first_slot_when_empty(self):
        tracker = LuxtronikEVUTracker()
        assert tracker._should_use_first_slot(time(10, 0)) is True

    def test_first_slot_before_start(self):
        tracker = LuxtronikEVUTracker()
        tracker._evu_first_start = time(12, 0)
        assert tracker._should_use_first_slot(time(10, 0)) is True

    def test_second_slot_after_first_end(self):
        tracker = LuxtronikEVUTracker()
        tracker._evu_first_start = time(8, 0)
        tracker._evu_first_end = time(10, 0)
        assert tracker._should_use_first_slot(time(14, 0)) is False


# ===========================================================================
# evu_helper.py — multi-day gap (line 75) and else branch (lines 76-79)
# ===========================================================================


class TestEVUHelperMultiDayGap:
    @patch("custom_components.luxtronik.evu_helper.dt_util")
    def test_multi_day_gap_adds_1440(self, mock_dt):
        from datetime import datetime

        # Current time: Wednesday 10:00
        mock_dt.now.return_value = datetime(2024, 1, 3, 10, 0)  # Wednesday=2

        tracker = LuxtronikEVUTracker()
        tracker._evu_first_start = time(8, 0)
        tracker._evu_days = [5]  # Only Friday has EVU events

        minutes = tracker.get_next_event_minutes()
        assert minutes is not None
        assert minutes > 1440  # At least one full day skipped

    @patch("custom_components.luxtronik.evu_helper.dt_util")
    def test_weekday_in_evu_days_returns_minutes(self, mock_dt):
        from datetime import datetime

        # Current time: Monday 10:00
        mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0)  # Monday=0

        tracker = LuxtronikEVUTracker()
        tracker._evu_first_start = time(12, 0)
        tracker._evu_days = [0]  # Monday is in evu_days

        minutes = tracker.get_next_event_minutes()
        assert minutes is not None
        assert minutes == 120  # 12:00 - 10:00 = 120 min

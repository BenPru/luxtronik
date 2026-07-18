"""Tests for the DHW timer-program schedule text entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from conftest import make_coordinator_data
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.exceptions import ServiceValidationError
from luxtronik.parameters import Parameters
import pytest

from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SensorKey as SK,
)
from custom_components.luxtronik2.lux_overrides import update_Luxtronik_Parameters
from custom_components.luxtronik2.timer_schedule_entities_predefined import (
    TIMER_SCHEDULE_ENTITIES,
)

_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
    CONF_HA_SENSOR_PREFIX: DOMAIN,
}


def _mock_entry():
    entry = MagicMock()
    entry.data = _ENTRY_DATA.copy()
    return entry


def _mock_coordinator(data=None, *, last_update_success: bool = True):
    if data is None:
        data = make_coordinator_data()
    coord = MagicMock()
    coord.data = data
    coord.last_update_success = last_update_success
    coord.entity_active.return_value = True
    coord.get_device.return_value = MagicMock()
    coord.async_write = AsyncMock(return_value=data)
    coord.async_write_many = AsyncMock(return_value=data)
    return coord


def _patch_entity_hass(entity):
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()


# ===========================================================================
# Table integrity
# ===========================================================================


class TestTimerScheduleTable:
    """Every generated row/selector name must resolve to a real Parameters
    entry once lux_overrides has run, catching a prefix or row-math typo at
    CI time instead of against a physical device."""

    def test_names_exist_in_library(self):
        update_Luxtronik_Parameters()

        known_names = {p.name for p in Parameters.parameters.values()}
        problems = []
        for description in TIMER_SCHEDULE_ENTITIES:
            names = [description.mode_selector_name]
            for start_name, end_name in description.row_names:
                names.extend([start_name, end_name])
            for name in names:
                if name not in known_names:
                    problems.append(f"{description.key}: {name!r} not in Parameters")

        assert not problems, "\n".join(problems)

    def test_ten_dhw_entities_generated(self):
        assert len(TIMER_SCHEDULE_ENTITIES) == 10

    def test_row_counts_are_five_for_dhw(self):
        for description in TIMER_SCHEDULE_ENTITIES:
            assert len(description.row_names) == 5

    def test_active_modes(self):
        by_key = {d.key: d.active_mode for d in TIMER_SCHEDULE_ENTITIES}
        assert by_key[SK.TIMER_DHW_SCHEDULE_WEEK] == "week"
        assert by_key[SK.TIMER_DHW_SCHEDULE_WEEKDAY] == "5+2"
        assert by_key[SK.TIMER_DHW_SCHEDULE_WEEKEND] == "5+2"
        assert by_key[SK.TIMER_DHW_SCHEDULE_MONDAY] == "days"
        assert by_key[SK.TIMER_DHW_SCHEDULE_SUNDAY] == "days"


# ===========================================================================
# _parse_schedule
# ===========================================================================


class TestParseSchedule:
    def test_empty_string_is_no_rows(self):
        from custom_components.luxtronik2.text import _parse_schedule

        assert _parse_schedule("", 5) == []

    def test_single_pair(self):
        from custom_components.luxtronik2.text import _parse_schedule

        assert _parse_schedule("06:00-22:00", 5) == [("06:00", "22:00")]

    def test_multiple_pairs(self):
        from custom_components.luxtronik2.text import _parse_schedule

        assert _parse_schedule("06:00-22:00/07:30-22:00", 5) == [
            ("06:00", "22:00"),
            ("07:30", "22:00"),
        ]

    def test_too_many_pairs_raises(self):
        from custom_components.luxtronik2.text import _parse_schedule

        with pytest.raises(ServiceValidationError):
            _parse_schedule("/".join(["06:00-07:00"] * 6), 5)

    def test_malformed_pair_raises(self):
        from custom_components.luxtronik2.text import _parse_schedule

        with pytest.raises(ServiceValidationError):
            _parse_schedule("6:00-22:00", 5)  # not zero-padded

        with pytest.raises(ServiceValidationError):
            _parse_schedule("06:00_22:00", 5)  # wrong separator


# ===========================================================================
# LuxtronikTimerScheduleText
# ===========================================================================


class TestLuxtronikTimerScheduleText:
    def _make_entity(self, key=SK.TIMER_DHW_SCHEDULE_WEEK, parameters=None):
        from custom_components.luxtronik2.text import LuxtronikTimerScheduleText

        description = next(d for d in TIMER_SCHEDULE_ENTITIES if d.key == key)

        data = make_coordinator_data(parameters=parameters or {})
        coord = _mock_coordinator(data)
        entry = _mock_entry()

        with patch("homeassistant.helpers.frame.report_usage"):
            entity = LuxtronikTimerScheduleText(
                entry, coord, description, description.device_key
            )
        _patch_entity_hass(entity)
        return entity, coord, description

    def test_entity_id(self):
        entity, _, description = self._make_entity()
        assert entity.entity_id == f"text.{DOMAIN}_{description.key}"
        assert entity._attr_unique_id == entity.entity_id

    def test_native_max_matches_row_count(self):
        entity, _, description = self._make_entity()
        assert entity._attr_native_max == len(description.row_names) * 12 - 1

    def test_handle_coordinator_update_renders_used_rows(self):
        entity, _, description = self._make_entity()
        start0, end0 = description.row_names[0]
        start1, end1 = description.row_names[1]
        data = make_coordinator_data(
            parameters={
                start0: "06:00",
                end0: "22:00",
                start1: "07:30",
                end1: "22:00",
            }
        )
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == "06:00-22:00/07:30-22:00"

    def test_handle_coordinator_update_skips_unset_rows(self):
        entity, _, description = self._make_entity()
        start0, end0 = description.row_names[0]
        data = make_coordinator_data(parameters={start0: "00:00", end0: "00:00"})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == ""

    def test_handle_coordinator_update_none_data(self):
        entity, coord, _ = self._make_entity()
        coord.data = None
        entity._handle_coordinator_update(None)  # should not crash

    def test_available_when_mode_matches(self):
        selector = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_WEEK
        ).mode_selector_name
        entity, _, _description = self._make_entity(parameters={selector: "week"})
        assert entity.available is True

    def test_unavailable_when_mode_does_not_match(self):
        selector = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_WEEK
        ).mode_selector_name
        entity, _, _description = self._make_entity(parameters={selector: "5+2"})
        assert entity.available is False

    def test_unavailable_when_data_is_none(self):
        entity, coord, _description = self._make_entity()
        coord.data = None
        assert entity.available is False

    def test_unavailable_when_coordinator_unavailable(self):
        selector = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_WEEK
        ).mode_selector_name
        entity, coord, _description = self._make_entity(parameters={selector: "week"})
        coord.last_update_success = False
        assert entity.available is False

    @pytest.mark.asyncio
    async def test_set_value_writes_only_changed_rows_in_one_batch(self):
        entity, coord, description = self._make_entity()
        start0, end0 = description.row_names[0]
        data = make_coordinator_data(parameters={start0: "06:00", end0: "22:00"})
        coord.data = data
        coord.async_write_many = AsyncMock(return_value=data)

        await entity.async_set_value("06:00-22:00")

        # Row 0 already matches; remaining rows get cleared (2 writes each) -
        # but all queued into a single async_write_many call (one refresh),
        # not one async_write call per changed value.
        coord.async_write_many.assert_awaited_once()
        (pairs,), _kwargs = coord.async_write_many.await_args
        assert len(pairs) == (len(description.row_names) - 1) * 2
        coord.async_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_value_sends_expected_pairs(self):
        entity, coord, description = self._make_entity()
        start0, end0 = description.row_names[0]
        start1, end1 = description.row_names[1]
        data = make_coordinator_data(parameters={start0: "06:00", end0: "22:00"})
        coord.data = data
        coord.async_write_many = AsyncMock(return_value=data)

        await entity.async_set_value("06:00-22:00/07:30-21:00")

        (pairs,), _kwargs = coord.async_write_many.await_args
        assert (start1, "07:30") in pairs
        assert (end1, "21:00") in pairs

    @pytest.mark.asyncio
    async def test_set_value_idempotent_when_unchanged(self):
        entity, coord, description = self._make_entity()
        start0, end0 = description.row_names[0]
        row_values = {}
        for s_name, e_name in description.row_names:
            row_values[s_name] = "00:00"
            row_values[e_name] = "00:00"
        row_values[start0] = "06:00"
        row_values[end0] = "22:00"
        data = make_coordinator_data(parameters=row_values)
        coord.data = data
        coord.async_write_many = AsyncMock(return_value=data)

        entity._handle_coordinator_update(data)
        await entity.async_set_value(entity._attr_native_value)

        coord.async_write_many.assert_not_called()
        coord.async_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_value_rejects_invalid_input(self):
        entity, coord, _ = self._make_entity()
        with pytest.raises(ServiceValidationError):
            await entity.async_set_value("not-a-schedule")
        coord.async_write.assert_not_called()
        coord.async_write_many.assert_not_called()

"""Tests for the DHW, heating and ventilation timer-program schedule text entities."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import (
    RegistryEntryDisabler,
    RegistryEntryHider,
)
from luxtronik.parameters import Parameters
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from conftest import DEFAULT_PARAMETERS, make_coordinator_data
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    CONF_SUPPORTS_TIME_24_00,
    CONFIG_ENTRY_VERSION,
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
            for row in description.row_names:
                names.extend(row)
            for name in names:
                if name not in known_names:
                    problems.append(f"{description.key}: {name!r} not in Parameters")

        assert not problems, "\n".join(problems)

    def test_entity_count(self):
        # 10 DHW + 10 heating + 10 ventilation day + 10 ventilation night
        assert len(TIMER_SCHEDULE_ENTITIES) == 40

    def test_row_counts_per_circuit(self):
        """DHW has 5 slots per day, the heating circuit only 3."""
        by_key = {d.key: len(d.row_names) for d in TIMER_SCHEDULE_ENTITIES}
        assert by_key[SK.TIMER_DHW_SCHEDULE_WEEK] == 5
        assert by_key[SK.TIMER_HEATING_SCHEDULE_WEEK] == 3
        assert by_key[SK.TIMER_HEATING_SCHEDULE_SUNDAY] == 3

    def test_active_modes(self):
        by_key = {d.key: d.active_mode for d in TIMER_SCHEDULE_ENTITIES}
        assert by_key[SK.TIMER_DHW_SCHEDULE_WEEK] == "week"
        assert by_key[SK.TIMER_DHW_SCHEDULE_WEEKDAY] == "5+2"
        assert by_key[SK.TIMER_DHW_SCHEDULE_WEEKEND] == "5+2"
        assert by_key[SK.TIMER_DHW_SCHEDULE_MONDAY] == "days"
        assert by_key[SK.TIMER_DHW_SCHEDULE_SUNDAY] == "days"

    def test_heating_selector_and_device(self):
        from custom_components.luxtronik2.const import DeviceKey

        description = next(
            d
            for d in TIMER_SCHEDULE_ENTITIES
            if d.key == SK.TIMER_HEATING_SCHEDULE_WEEK
        )
        assert description.mode_selector_name == "ID_Einst_SuHkr_akt"
        assert description.device_key is DeviceKey.heating

    def test_heating_row_names(self):
        """Spot-checks against the real upstream names (222-282).

        The heating prefixes are spelled `SuHkrW0` (digit zero) and `SuHkrTG`,
        which differ from DHW's `SuBwWO`/`SuBwTG` - a copy-paste of the DHW
        prefix would still generate plausible-looking names.
        """
        by_key = {d.key: d.row_names for d in TIMER_SCHEDULE_ENTITIES}
        assert by_key[SK.TIMER_HEATING_SCHEDULE_WEEK][0] == (
            "ID_Einst_SuHkrW0_zeit_0_0",
            "ID_Einst_SuHkrW0_zeit_0_1",
        )
        assert by_key[SK.TIMER_HEATING_SCHEDULE_WEEKEND][0] == (
            "ID_Einst_SuHkr25_zeit_0_2",
            "ID_Einst_SuHkr25_zeit_0_3",
        )
        assert by_key[SK.TIMER_HEATING_SCHEDULE_SUNDAY][2] == (
            "ID_Einst_SuHkrTG_zeit_2_12",
            "ID_Einst_SuHkrTG_zeit_2_13",
        )

    def test_heating_active_modes(self):
        by_key = {d.key: d.active_mode for d in TIMER_SCHEDULE_ENTITIES}
        assert by_key[SK.TIMER_HEATING_SCHEDULE_WEEK] == "week"
        assert by_key[SK.TIMER_HEATING_SCHEDULE_WEEKDAY] == "5+2"
        assert by_key[SK.TIMER_HEATING_SCHEDULE_WEEKEND] == "5+2"
        assert by_key[SK.TIMER_HEATING_SCHEDULE_MONDAY] == "days"

    def test_ventilation_row_names_are_packed_day_and_night_blocks(self):
        """Ventilation rows are 1-tuples on the block the key names (#789).

        Register names verified against a KHZ LWC 60 dump: block 0 is the
        controller's sun (day) page, block 1 its moon (night) page, and the
        column keeps the `2*col` slot numbering of the two-register layout.
        """
        from custom_components.luxtronik2.const import DeviceKey

        by_key = {d.key: d for d in TIMER_SCHEDULE_ENTITIES}
        day_week = by_key[SK.TIMER_VENTILATION_DAY_SCHEDULE_WEEK]
        night_week = by_key[SK.TIMER_VENTILATION_NIGHT_SCHEDULE_WEEK]
        assert day_week.device_key is DeviceKey.ventilation
        assert day_week.mode_selector_name == "ID_Einst_SuLuf_akt"
        assert night_week.mode_selector_name == "ID_Einst_SuLuf_akt"
        assert day_week.row_names == (
            ("ID_Einst_SuLufWo_zeit_0_0_0",),
            ("ID_Einst_SuLufWo_zeit_0_1_0",),
            ("ID_Einst_SuLufWo_zeit_0_2_0",),
        )
        assert night_week.row_names == (
            ("ID_Einst_SuLufWo_zeit_1_0_0",),
            ("ID_Einst_SuLufWo_zeit_1_1_0",),
            ("ID_Einst_SuLufWo_zeit_1_2_0",),
        )
        assert by_key[SK.TIMER_VENTILATION_DAY_SCHEDULE_WEEKEND].row_names[0] == (
            "ID_Einst_SuLuf25_zeit_0_0_2",
        )
        assert by_key[SK.TIMER_VENTILATION_NIGHT_SCHEDULE_SUNDAY].row_names[2] == (
            "ID_Einst_SuLufTg_zeit_1_2_12",
        )

    def test_ventilation_active_modes(self):
        by_key = {d.key: d.active_mode for d in TIMER_SCHEDULE_ENTITIES}
        for block in ("DAY", "NIGHT"):
            assert by_key[SK[f"TIMER_VENTILATION_{block}_SCHEDULE_WEEK"]] == "week"
            assert by_key[SK[f"TIMER_VENTILATION_{block}_SCHEDULE_WEEKDAY"]] == "5+2"
            assert by_key[SK[f"TIMER_VENTILATION_{block}_SCHEDULE_WEEKEND"]] == "5+2"
            assert by_key[SK[f"TIMER_VENTILATION_{block}_SCHEDULE_MONDAY"]] == "days"

    def test_every_row_is_a_pair_or_a_packed_register(self):
        for d in TIMER_SCHEDULE_ENTITIES:
            assert all(len(row) in (1, 2) for row in d.row_names), d.key


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

    def test_rejects_24_00_as_a_start_time(self):
        from custom_components.luxtronik2.text import _parse_schedule

        with pytest.raises(ServiceValidationError):
            _parse_schedule("24:00-06:00", 5)

    def test_rejects_times_past_24_00(self):
        from custom_components.luxtronik2.text import _parse_schedule

        for value in ("06:00-24:01", "06:00-25:00"):
            with pytest.raises(ServiceValidationError):
                _parse_schedule(value, 5)

    def test_returns_24_00_as_typed(self):
        """The parser reports what was typed; the write path decides the rest."""
        from custom_components.luxtronik2.text import _parse_schedule

        assert _parse_schedule("14:00-24:00", 5) == [("14:00", "24:00")]

    def test_rejects_a_trailing_newline(self):
        """A trailing newline must not slip past - "$" matches before one.

        It would be compared as a string against the device value and against
        "24:00" on the write path, and `TimeOfDay.to_heatpump` strips it - so
        a newline would defeat the normalization and send 86400 to a
        controller never shown to accept it.
        """
        from custom_components.luxtronik2.text import _parse_schedule

        with pytest.raises(ServiceValidationError):
            _parse_schedule("14:00-24:00" + chr(10), 5)


# ===========================================================================
# LuxtronikTimerScheduleText
# ===========================================================================


class TestLuxtronikTimerScheduleText:
    def _make_entity(
        self,
        key=SK.TIMER_DHW_SCHEDULE_WEEK,
        parameters=None,
        supports_24_00: bool = False,
    ):
        from custom_components.luxtronik2.text import LuxtronikTimerScheduleText

        description = next(d for d in TIMER_SCHEDULE_ENTITIES if d.key == key)

        data = make_coordinator_data(parameters=parameters or {})
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        if supports_24_00:
            entry.data[CONF_SUPPORTS_TIME_24_00] = True

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

    def test_a_fully_populated_block_lands_exactly_on_native_max(self):
        """`_attr_native_max` must fit the widest value the block can render.

        Every pair is 11 characters because `TimeOfDay` always renders
        "HH:MM" (it drops the seconds a non-minute-aligned register would
        otherwise carry) - this is the consumer side of that invariant.
        """
        longest = max(TIMER_SCHEDULE_ENTITIES, key=lambda d: len(d.row_names))
        entity, _, description = self._make_entity(key=longest.key)
        parameters = {}
        for start_name, end_name in description.row_names:
            parameters[start_name] = "06:00"
            parameters[end_name] = "22:00"
        entity._handle_coordinator_update(make_coordinator_data(parameters=parameters))
        assert len(entity._attr_native_value) == entity._attr_native_max

    def test_handle_coordinator_update_none_data(self):
        entity, coord, _ = self._make_entity()
        coord.data = None
        entity._handle_coordinator_update(None)  # should not crash

    def test_packed_rows_render_the_window_as_is(self):
        """The reporter's day block (#789): three packed windows, verbatim."""
        entity, _, description = self._make_entity(
            key=SK.TIMER_VENTILATION_DAY_SCHEDULE_WEEK
        )
        (r0,), (r1,), (r2,) = description.row_names
        data = make_coordinator_data(
            parameters={r0: "05:00-08:30", r1: "10:00-11:00", r2: "20:00-21:00"}
        )
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == "05:00-08:30/10:00-11:00/20:00-21:00"
        assert len(entity._attr_native_value) == entity._attr_native_max

    def test_packed_rows_skip_unset_and_missing_registers(self):
        entity, _, description = self._make_entity(
            key=SK.TIMER_VENTILATION_NIGHT_SCHEDULE_WEEK
        )
        (r0,), (r1,), _ = description.row_names
        data = make_coordinator_data(parameters={r0: "00:00-00:00", r1: "22:00-05:00"})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == "22:00-05:00"

    def test_packed_rows_through_the_real_datatype(self):
        """End to end: raw register -> TimeOfDay2 -> entity state."""
        from custom_components.luxtronik2.lux_overrides import TimeOfDay2

        entity, _, description = self._make_entity(
            key=SK.TIMER_VENTILATION_DAY_SCHEDULE_WEEK
        )
        (r0,), _, _ = description.row_names
        # 05:00-08:30: start 300 in the low word, end 510 in the high word.
        raw = (510 << 16) | 300
        data = make_coordinator_data(parameters={r0: TimeOfDay2.from_heatpump(raw)})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == "05:00-08:30"

    def test_an_over_long_value_is_dropped_instead_of_raised(self, caplog):
        """A register the datatype cannot render within budget must not
        take every listener update down with it.

        `TextEntity.state` raises ValueError past `native_max`, and the
        coordinator logs that as an unexpected listener error on every poll
        - the failure the first ventilation-module unit hit when 896-955
        decoded as "9284:21" (#789).
        """
        entity, _, description = self._make_entity(key=SK.TIMER_HEATING_SCHEDULE_WEEK)
        garbage = (
            ("9284:21", "5461:42"),
            ("12015:06", "13653:32"),
            ("22937:56", "18022:40"),
        )
        parameters = {}
        for (start_name, end_name), (start, end) in zip(
            description.row_names, garbage, strict=True
        ):
            parameters[start_name] = start
            parameters[end_name] = end
        data = make_coordinator_data(parameters=parameters)
        rendered = "9284:21-5461:42/12015:06-13653:32/22937:56-18022:40"

        # What HA does with the value if it gets through - the contract
        # the guard exists for.
        entity._attr_native_value = rendered
        with pytest.raises(ValueError, match="too long"):
            _ = entity.state

        entity._handle_coordinator_update(data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None
        assert entity.state is None
        assert caplog.text.count(rendered) == 1

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
    async def test_set_value_writes_whole_windows_to_packed_rows(self):
        """One (name, "HH:MM-HH:MM") write per changed packed row, the
        rest cleared to the unused window."""
        entity, coord, description = self._make_entity(
            key=SK.TIMER_VENTILATION_DAY_SCHEDULE_WEEK
        )
        (r0,), (r1,), (r2,) = description.row_names
        data = make_coordinator_data(
            parameters={r0: "05:00-08:30", r1: "10:00-11:00", r2: "20:00-21:00"}
        )
        coord.data = data
        coord.async_write_many = AsyncMock(return_value=data)

        await entity.async_set_value("05:00-08:30/12:00-13:00")

        coord.async_write_many.assert_awaited_once()
        (pairs,), _kwargs = coord.async_write_many.await_args
        assert pairs == [(r1, "12:00-13:00"), (r2, "00:00-00:00")]

    @pytest.mark.asyncio
    async def test_empty_string_clears_every_packed_row(self):
        entity, coord, description = self._make_entity(
            key=SK.TIMER_VENTILATION_DAY_SCHEDULE_WEEK
        )
        (r0,), (r1,), (r2,) = description.row_names
        data = make_coordinator_data(
            parameters={r0: "05:00-08:30", r1: "10:00-11:00", r2: "00:00-00:00"}
        )
        coord.data = data
        coord.async_write_many = AsyncMock(return_value=data)

        await entity.async_set_value("")

        (pairs,), _kwargs = coord.async_write_many.await_args
        assert pairs == [(r0, "00:00-00:00"), (r1, "00:00-00:00")]

    @pytest.mark.asyncio
    async def test_packed_rows_never_receive_24_00(self):
        """A packed half holds 0-1439, so 24:00 is respelled 00:00 even on a
        controller whose seconds registers store 86400."""
        entity, coord, description = self._make_entity(
            key=SK.TIMER_VENTILATION_NIGHT_SCHEDULE_WEEK, supports_24_00=True
        )
        (r0,), _, _ = description.row_names
        coord.data = make_coordinator_data(parameters={r0: "00:00-00:00"})

        await entity.async_set_value("22:00-24:00")

        (pairs,), _kwargs = coord.async_write_many.await_args
        assert pairs[0] == (r0, "22:00-00:00")

        with pytest.raises(ServiceValidationError) as excinfo:
            await entity.async_set_value("00:00-24:00")
        assert excinfo.value.translation_key == "timer_schedule_all_day_unsupported"

    @pytest.mark.asyncio
    async def test_set_value_writes_midnight_for_24_00_by_default(self):
        """A "24:00" typed in HA reaches an unproven controller as "00:00"."""
        entity, coord, description = self._make_entity()
        start0, end0 = description.row_names[0]
        data = make_coordinator_data(parameters={start0: "14:00", end0: "22:00"})
        coord.data = data

        await entity.async_set_value("14:00-24:00")

        (pairs,), _kwargs = coord.async_write_many.await_args
        assert (end0, "00:00") in pairs
        assert (end0, "24:00") not in pairs

    @pytest.mark.asyncio
    async def test_set_value_refuses_an_all_day_window_by_default(self):
        """ "00:00-24:00" has no "00:00" spelling: it would become the unused row."""
        entity, coord, description = self._make_entity()
        start0, end0 = description.row_names[0]
        coord.data = make_coordinator_data(parameters={start0: "14:00", end0: "22:00"})

        with pytest.raises(ServiceValidationError) as excinfo:
            await entity.async_set_value("00:00-24:00")

        assert excinfo.value.translation_key == "timer_schedule_all_day_unsupported"
        coord.async_write_many.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_value_writes_an_all_day_window_once_supported(self):
        entity, coord, description = self._make_entity(supports_24_00=True)
        start0, end0 = description.row_names[0]
        coord.data = make_coordinator_data(parameters={start0: "14:00", end0: "22:00"})

        await entity.async_set_value("00:00-24:00")

        (pairs,), _kwargs = coord.async_write_many.await_args
        assert (start0, "00:00") in pairs
        assert (end0, "24:00") in pairs

    @pytest.mark.asyncio
    async def test_set_value_writes_24_00_verbatim_once_supported(self):
        entity, coord, description = self._make_entity(supports_24_00=True)
        start0, end0 = description.row_names[0]
        data = make_coordinator_data(parameters={start0: "14:00", end0: "22:00"})
        coord.data = data

        await entity.async_set_value("14:00-24:00")

        (pairs,), _kwargs = coord.async_write_many.await_args
        assert (end0, "24:00") in pairs

    @pytest.mark.asyncio
    async def test_set_value_leaves_an_existing_24_00_alone(self):
        """Editing another row must not rewrite a "24:00" the controller set.

        Without midnight-equivalence the normalized "00:00" would look like a
        change, silently clearing a row the user never touched. (The entity
        can still see "24:00" here because it snapshots the latch at setup,
        while the reload that follows the coordinator's latch is pending.)
        """
        entity, coord, description = self._make_entity()
        start0, end0 = description.row_names[0]
        start1, end1 = description.row_names[1]
        row_values = {name: "00:00" for pair in description.row_names for name in pair}
        row_values[start0] = "14:00"
        row_values[end0] = "24:00"
        data = make_coordinator_data(parameters=row_values)
        coord.data = data

        await entity.async_set_value("14:00-24:00/07:30-21:00")

        (pairs,), _kwargs = coord.async_write_many.await_args
        assert [name for name, _ in pairs] == [start1, end1]

    @pytest.mark.asyncio
    async def test_set_value_can_clear_a_24_00_once_supported(self):
        """With the latch armed the user's spelling is authoritative again."""
        entity, coord, description = self._make_entity(supports_24_00=True)
        start0, end0 = description.row_names[0]
        row_values = {name: "00:00" for pair in description.row_names for name in pair}
        row_values[start0] = "14:00"
        row_values[end0] = "24:00"
        data = make_coordinator_data(parameters=row_values)
        coord.data = data

        await entity.async_set_value("14:00-00:00")

        (pairs,), _kwargs = coord.async_write_many.await_args
        assert (end0, "00:00") in pairs

    @pytest.mark.asyncio
    async def test_set_value_clears_a_row_holding_24_00(self):
        """Clearing a row must leave it unused, not turn it into an all-day one.

        A row left at start=00:00 / end=24:00 is not an unused row: only a
        both-00:00 pair is (see TIMER_SCHEDULES.md). On DHW that would block
        hot water around the clock - the opposite of what clearing the field
        asks for.
        """
        entity, coord, description = self._make_entity()
        start0, end0 = description.row_names[0]
        row_values = {name: "00:00" for pair in description.row_names for name in pair}
        row_values[start0] = "18:00"
        row_values[end0] = "24:00"
        data = make_coordinator_data(parameters=row_values)
        coord.data = data

        await entity.async_set_value("")

        (pairs,), _kwargs = coord.async_write_many.await_args
        assert (start0, "00:00") in pairs
        assert (end0, "00:00") in pairs

    @pytest.mark.asyncio
    async def test_set_value_overwrites_a_24_00_row_with_a_real_window(self):
        """Only a typed "24:00" is protected - any other end time wins."""
        entity, coord, description = self._make_entity()
        start0, end0 = description.row_names[0]
        row_values = {name: "00:00" for pair in description.row_names for name in pair}
        row_values[start0] = "18:00"
        row_values[end0] = "24:00"
        data = make_coordinator_data(parameters=row_values)
        coord.data = data

        await entity.async_set_value("18:00-22:00")

        (pairs,), _kwargs = coord.async_write_many.await_args
        assert (end0, "22:00") in pairs

    def test_handle_coordinator_update_preserves_a_device_24_00(self):
        """Read path never normalizes - it shows what the register holds."""
        entity, _coord, description = self._make_entity()
        start0, end0 = description.row_names[0]
        data = make_coordinator_data(parameters={start0: "14:00", end0: "24:00"})

        entity._handle_coordinator_update(data)

        assert entity._attr_native_value == "14:00-24:00"

    @pytest.mark.asyncio
    async def test_set_value_rejects_invalid_input(self):
        entity, coord, _ = self._make_entity()
        with pytest.raises(ServiceValidationError):
            await entity.async_set_value("not-a-schedule")
        coord.async_write.assert_not_called()
        coord.async_write_many.assert_not_called()


# ===========================================================================
# _timer_schedule_unique_id
# ===========================================================================


class TestTimerScheduleUniqueId:
    def test_matches_the_entity_id_the_entity_assigns_itself(self):
        from custom_components.luxtronik2.text import _timer_schedule_unique_id

        description = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_WEEK
        )
        assert (
            _timer_schedule_unique_id(_mock_entry(), description)
            == f"text.{DOMAIN}_{description.key}"
        )


# ===========================================================================
# _active_schedule_descriptions
# ===========================================================================


class TestActiveScheduleDescriptions:
    _SELECTOR = "ID_Einst_SUBW_akt2"

    def _call(self, parameters, *, entity_active=True):
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        data = make_coordinator_data(parameters=parameters)
        coord = _mock_coordinator(data)
        coord.entity_active.return_value = entity_active
        active, _unreadable = _active_schedule_descriptions(coord, data)
        return [d.key for d in active]

    def test_week_mode_yields_only_the_week_block(self):
        assert self._call({self._SELECTOR: "week"}) == [SK.TIMER_DHW_SCHEDULE_WEEK]

    def test_weekday_weekend_mode_yields_both_blocks(self):
        assert self._call({self._SELECTOR: "5+2"}) == [
            SK.TIMER_DHW_SCHEDULE_WEEKDAY,
            SK.TIMER_DHW_SCHEDULE_WEEKEND,
        ]

    def test_days_mode_yields_seven_day_blocks(self):
        keys = self._call({self._SELECTOR: "days"})
        assert len(keys) == 7
        assert SK.TIMER_DHW_SCHEDULE_MONDAY in keys
        assert SK.TIMER_DHW_SCHEDULE_SUNDAY in keys

    def test_missing_selector_parameter_yields_nothing(self):
        """A selector that this controller does not have is a real answer: no blocks."""
        assert self._call({}) == []

    def test_ventilation_selector_yields_the_day_and_night_blocks(self):
        """Two circuits on one selector: both blocks of the shape come up."""
        assert self._call({"ID_Einst_SuLuf_akt": "5+2"}) == [
            SK.TIMER_VENTILATION_DAY_SCHEDULE_WEEKDAY,
            SK.TIMER_VENTILATION_DAY_SCHEDULE_WEEKEND,
            SK.TIMER_VENTILATION_NIGHT_SCHEDULE_WEEKDAY,
            SK.TIMER_VENTILATION_NIGHT_SCHEDULE_WEEKEND,
        ]

    def test_unreadable_ventilation_selector_freezes_both_blocks(self):
        """Day and night share the selector, so they freeze together."""
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        data = make_coordinator_data(parameters={"ID_Einst_SuLuf_akt": None})
        coord = _mock_coordinator(data)
        active, unreadable = _active_schedule_descriptions(coord, data)
        assert active == []
        assert unreadable == {"ID_Einst_SuLuf_akt"}
        frozen = {
            d.key for d in TIMER_SCHEDULE_ENTITIES if d.mode_selector_name in unreadable
        }
        assert len(frozen) == 20
        assert all("timer_ventilation_" in key for key in frozen)

    def test_inactive_entity_yields_nothing(self):
        assert self._call({self._SELECTOR: "week"}, entity_active=False) == []

    def test_undecodable_selector_freezes_only_its_own_circuit(self):
        """A present-but-unreadable selector must not read as "no program active".

        `get_sensor_data` returns None both for an absent register and for a
        register whose datatype could not decode the raw value
        (`SelectionBase` returns None for an unrecognised code). The selector
        is reported as unreadable so the sync leaves that circuit alone.
        """
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        data = make_coordinator_data(parameters={self._SELECTOR: None})
        coord = _mock_coordinator(data)
        active, unreadable = _active_schedule_descriptions(coord, data)
        assert active == []
        assert unreadable == {self._SELECTOR}

    def test_one_unreadable_circuit_does_not_hide_another(self):
        """The regression the second circuit makes possible.

        Before this, any single unreadable selector returned "no information"
        for the whole pass, freezing every circuit's entities.
        """
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        data = make_coordinator_data(
            parameters={self._SELECTOR: None, "ID_Einst_SuHkr_akt": "week"}
        )
        coord = _mock_coordinator(data)
        active, unreadable = _active_schedule_descriptions(coord, data)
        assert [d.key for d in active] == [SK.TIMER_HEATING_SCHEDULE_WEEK]
        assert unreadable == {self._SELECTOR}

    def test_blocks_of_an_inactive_device_are_skipped(self):
        """`entity_active` is False for a device the unit does not have."""
        from custom_components.luxtronik2.const import DeviceKey
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        data = make_coordinator_data(
            parameters={self._SELECTOR: "week", "ID_Einst_SuHkr_akt": "week"}
        )
        coord = _mock_coordinator(data)
        coord.entity_active.side_effect = lambda description: (
            description.device_key is not DeviceKey.heating
        )
        active, unreadable = _active_schedule_descriptions(coord, data)
        keys = [d.key for d in active]
        assert keys == [SK.TIMER_DHW_SCHEDULE_WEEK]
        assert unreadable == set()

    def test_data_none_still_yields_no_information(self):
        """No coordinator data at all is "unknown" for every circuit."""
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        assert _active_schedule_descriptions(_mock_coordinator(), None) is None


# ===========================================================================
# _TimerScheduleSync
# ===========================================================================


class TestTimerScheduleSync:
    _SELECTOR = "ID_Einst_SUBW_akt2"

    def _make_sync(self, mode: str):
        from custom_components.luxtronik2.text import _TimerScheduleSync

        data = make_coordinator_data(parameters={self._SELECTOR: mode})
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        added: list = []
        hass = MagicMock()

        def _add_entities(entities):
            for entity in entities:
                # Stand in for what the platform's `add_to_platform_start`
                # does once it actually runs the scheduled add. The sync
                # keys its removal guard off this, because an add that was
                # aborted (or has not run yet) leaves `hass` unset.
                entity.hass = hass
            added.extend(entities)

        sync = _TimerScheduleSync(hass, entry, coord, _add_entities)
        return sync, coord, added

    def _registry(self, known: dict[str, MagicMock]):
        """Fake entity registry: unique_id -> registry entry."""
        registry = MagicMock()
        registry.async_get_entity_id.side_effect = (
            lambda _domain, _platform, unique_id: (
                unique_id if unique_id in known else None
            )
        )
        registry.async_get.side_effect = lambda entity_id: known.get(entity_id)
        return registry

    def _entry(self, disabled_by=None, hidden_by=None):
        registry_entry = MagicMock()
        registry_entry.disabled_by = disabled_by
        registry_entry.hidden_by = hidden_by
        return registry_entry

    @pytest.mark.asyncio
    async def test_setup_adds_only_the_active_blocks(self):
        sync, _coord, added = self._make_sync("week")
        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get",
                return_value=self._registry({}),
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()
        assert [e.entity_description.key for e in added] == [SK.TIMER_DHW_SCHEDULE_WEEK]

    @pytest.mark.asyncio
    async def test_setup_disables_existing_entries_of_inactive_blocks(self):
        from custom_components.luxtronik2.text import _timer_schedule_unique_id

        sync, _coord, _added = self._make_sync("week")
        entry = _mock_entry()
        stale = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_MONDAY
        )
        stale_id = _timer_schedule_unique_id(entry, stale)
        registry = self._registry({stale_id: self._entry()})

        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()

        registry.async_update_entity.assert_any_call(
            stale_id, disabled_by=RegistryEntryDisabler.INTEGRATION
        )

    @pytest.mark.asyncio
    async def test_setup_does_not_touch_a_user_disabled_entry(self):
        from custom_components.luxtronik2.text import _timer_schedule_unique_id

        sync, _coord, _added = self._make_sync("week")
        entry = _mock_entry()
        week = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_WEEK
        )
        week_id = _timer_schedule_unique_id(entry, week)
        registry = self._registry({week_id: self._entry(RegistryEntryDisabler.USER)})

        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()

        registry.async_update_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_setup_enables_an_integration_disabled_active_entry(self):
        from custom_components.luxtronik2.text import _timer_schedule_unique_id

        sync, _coord, _added = self._make_sync("week")
        entry = _mock_entry()
        week = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_WEEK
        )
        week_id = _timer_schedule_unique_id(entry, week)
        registry = self._registry(
            {week_id: self._entry(RegistryEntryDisabler.INTEGRATION)}
        )

        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()

        registry.async_update_entity.assert_any_call(week_id, disabled_by=None)

    @pytest.mark.asyncio
    async def test_setup_migrates_a_hidden_active_entry_without_disabling_it(self):
        """An earlier build hid the active entry too; the migration just clears it."""
        from custom_components.luxtronik2.text import _timer_schedule_unique_id

        sync, _coord, _added = self._make_sync("week")
        entry = _mock_entry()
        week = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_WEEK
        )
        week_id = _timer_schedule_unique_id(entry, week)
        registry = self._registry(
            {week_id: self._entry(hidden_by=RegistryEntryHider.INTEGRATION)}
        )

        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()

        registry.async_update_entity.assert_any_call(week_id, hidden_by=None)
        for call in registry.async_update_entity.call_args_list:
            assert "disabled_by" not in call.kwargs

    @pytest.mark.asyncio
    async def test_setup_migrates_a_hidden_inactive_entry_and_disables_it(self):
        """An inactive entry left over from the hidden-based build gets both:
        the stale hidden_by is scrubbed and disabled_by is now set."""
        from custom_components.luxtronik2.text import _timer_schedule_unique_id

        sync, _coord, _added = self._make_sync("week")
        entry = _mock_entry()
        stale = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_MONDAY
        )
        stale_id = _timer_schedule_unique_id(entry, stale)
        registry = self._registry(
            {stale_id: self._entry(hidden_by=RegistryEntryHider.INTEGRATION)}
        )

        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()

        registry.async_update_entity.assert_any_call(stale_id, hidden_by=None)
        registry.async_update_entity.assert_any_call(
            stale_id, disabled_by=RegistryEntryDisabler.INTEGRATION
        )

    @pytest.mark.asyncio
    async def test_mode_change_swaps_the_entities(self):
        from custom_components.luxtronik2.text import LuxtronikTimerScheduleText

        sync, coord, added = self._make_sync("week")
        registry = self._registry({})
        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()
            coord.data = make_coordinator_data(parameters={self._SELECTOR: "5+2"})
            with patch.object(
                LuxtronikTimerScheduleText, "async_remove", new=AsyncMock()
            ) as remove:
                await sync.async_apply()

        assert remove.await_count == 1
        assert [e.entity_description.key for e in added[1:]] == [
            SK.TIMER_DHW_SCHEDULE_WEEKDAY,
            SK.TIMER_DHW_SCHEDULE_WEEKEND,
        ]

    @pytest.mark.asyncio
    async def test_apply_without_coordinator_data_changes_nothing(self):
        """A poll that produced no data at all concludes nothing.

        `_active_schedule_descriptions` returns None only in that case, and
        the entities already live must then survive untouched - removing or
        disabling them on a failed read is exactly the churn the per-circuit
        freeze elsewhere in this method exists to avoid.
        """
        from custom_components.luxtronik2.text import LuxtronikTimerScheduleText

        sync, coord, added = self._make_sync("week")
        registry = self._registry({})
        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()
            live_before = list(added)
            coord.data = None
            with patch.object(
                LuxtronikTimerScheduleText, "async_remove", new=AsyncMock()
            ) as remove:
                await sync.async_apply()

        assert added == live_before
        remove.assert_not_awaited()
        registry.async_update_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_overlapping_apply_calls_are_serialized(self):
        """Two overlapping `async_apply()` calls must not interleave.

        Regression test: without a lock, a second coordinator update landing
        while a first `async_apply()` is suspended mid-removal would compute
        `desired` and mutate `self._entities` concurrently with the first
        call, risking a duplicate registration for the same key.
        """
        from custom_components.luxtronik2.text import LuxtronikTimerScheduleText

        sync, coord, _added = self._make_sync("week")
        registry = self._registry({})

        remove_started = asyncio.Event()
        release_remove = asyncio.Event()

        async def _slow_remove(self_entity):
            remove_started.set()
            await release_remove.wait()

        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()
            coord.data = make_coordinator_data(parameters={self._SELECTOR: "5+2"})

            with patch.object(
                LuxtronikTimerScheduleText, "async_remove", new=_slow_remove
            ):
                first = asyncio.create_task(sync.async_apply())
                await remove_started.wait()

                # A second coordinator update lands (mode flips back to
                # "week") while the first apply is still suspended awaiting
                # the removal it started.
                coord.data = make_coordinator_data(parameters={self._SELECTOR: "week"})
                second = asyncio.create_task(sync.async_apply())
                await asyncio.sleep(0)
                await asyncio.sleep(0)

                # The lock must keep the second call from starting its own
                # add/remove pass until the first call has fully finished.
                assert not second.done()
                assert sync._lock.locked()

                release_remove.set()
                await first
                await second

        # The entity set ends up matching the final ("week") mode, with no
        # duplicate registration for the week key.
        assert list(sync._entities) == [SK.TIMER_DHW_SCHEDULE_WEEK]

    @pytest.mark.asyncio
    async def test_an_unreadable_circuit_is_frozen_while_others_still_sync(self):
        """A frozen circuit keeps its live entities and registry entries.

        Regression test: treating an undecodable selector value as "no
        program active" removed every live schedule entity of that circuit
        and wrote `disabled_by = INTEGRATION` on its registry entries, with
        the next good poll re-adding and re-enabling them - entity churn,
        registry writes and a recorder gap caused by one transient read.

        The per-circuit skip is only safe if the sync also refuses to remove
        and disable that circuit's blocks - otherwise it causes exactly the
        teardown the whole-pass bail existed to prevent. Real registry ids
        are seeded for both circuits (not an empty registry) so that a
        regression which drops the freeze from the `_disable_inactive` call
        has an actual row to wrongly write `disabled_by` to - an empty
        registry would make `async_get_entity_id` return `None` for the
        frozen circuit and the assertions below would pass for the wrong
        reason.
        """
        from custom_components.luxtronik2.text import (
            LuxtronikTimerScheduleText,
            _timer_schedule_unique_id,
        )

        sync, coord, added = self._make_sync("week")
        entry = _mock_entry()
        dhw_week = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_WEEK
        )
        dhw_week_id = _timer_schedule_unique_id(entry, dhw_week)
        heating_week = next(
            d
            for d in TIMER_SCHEDULE_ENTITIES
            if d.key == SK.TIMER_HEATING_SCHEDULE_WEEK
        )
        heating_week_id = _timer_schedule_unique_id(entry, heating_week)
        registry = self._registry(
            {dhw_week_id: self._entry(), heating_week_id: self._entry()}
        )
        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            # Both circuits start in "week" mode.
            coord.data = make_coordinator_data(
                parameters={self._SELECTOR: "week", "ID_Einst_SuHkr_akt": "week"}
            )
            await sync.async_setup()
            assert set(sync._entities) == {
                SK.TIMER_DHW_SCHEDULE_WEEK,
                SK.TIMER_HEATING_SCHEDULE_WEEK,
            }
            registry.async_update_entity.reset_mock()

            # DHW's selector glitches while heating switches program.
            coord.data = make_coordinator_data(
                parameters={self._SELECTOR: None, "ID_Einst_SuHkr_akt": "5+2"}
            )
            with patch.object(
                LuxtronikTimerScheduleText, "async_remove", new=AsyncMock()
            ) as remove:
                await sync.async_apply()

        # Only the heating week block was removed; the DHW one is untouched.
        assert remove.await_count == 1
        assert SK.TIMER_DHW_SCHEDULE_WEEK in sync._entities
        assert SK.TIMER_HEATING_SCHEDULE_WEEK not in sync._entities
        assert [e.entity_description.key for e in added[2:]] == [
            SK.TIMER_HEATING_SCHEDULE_WEEKDAY,
            SK.TIMER_HEATING_SCHEDULE_WEEKEND,
        ]
        # The heating circuit's now-inactive week entry got disabled...
        registry.async_update_entity.assert_any_call(
            heating_week_id, disabled_by=RegistryEntryDisabler.INTEGRATION
        )
        # ...but the frozen DHW circuit's registry entry was never touched by
        # any call, in either position.
        for call in registry.async_update_entity.call_args_list:
            assert call.args[0] != dhw_week_id

    @pytest.mark.asyncio
    async def test_removal_of_an_entity_that_never_reached_the_platform(self):
        """An entity whose add was aborted must be dropped without crashing.

        `async_add_entities` only schedules the add. If the registry entry is
        disabled, `EntityPlatform._async_add_entity` calls
        `add_to_platform_abort()`, which sets `entity.hass = None`; a later
        `entity.async_remove()` would then blow up on
        `self.hass.loop.create_future()` inside the sync task, skipping the
        rest of the removal loop and the disable pass.
        """
        from custom_components.luxtronik2.text import _timer_schedule_unique_id

        sync, coord, _added = self._make_sync("week")
        entry = _mock_entry()
        week = next(
            d for d in TIMER_SCHEDULE_ENTITIES if d.key == SK.TIMER_DHW_SCHEDULE_WEEK
        )
        week_id = _timer_schedule_unique_id(entry, week)
        registry = self._registry({week_id: self._entry()})

        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()
            # The platform aborted the add (disabled registry entry).
            sync._entities[SK.TIMER_DHW_SCHEDULE_WEEK].hass = None  # type: ignore[assignment]
            registry.async_update_entity.reset_mock()
            coord.data = make_coordinator_data(parameters={self._SELECTOR: "5+2"})
            await sync.async_apply()

        assert SK.TIMER_DHW_SCHEDULE_WEEK not in sync._entities
        # The rest of the pass still ran: the now-inactive week block is disabled.
        registry.async_update_entity.assert_any_call(
            week_id, disabled_by=RegistryEntryDisabler.INTEGRATION
        )

    @pytest.mark.asyncio
    async def test_a_failing_removal_does_not_abort_the_pass(self):
        """One entity failing to remove must not skip the others or the disable pass."""
        from custom_components.luxtronik2.text import LuxtronikTimerScheduleText

        sync, coord, _added = self._make_sync("days")
        registry = self._registry({})
        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()
            assert len(sync._entities) == 7
            coord.data = make_coordinator_data(parameters={self._SELECTOR: "week"})
            calls: list = []

            async def _boom(self_entity):
                calls.append(self_entity)
                raise RuntimeError("removal exploded")

            with patch.object(LuxtronikTimerScheduleText, "async_remove", new=_boom):
                await sync.async_apply()

        assert len(calls) == 7
        assert list(sync._entities) == [SK.TIMER_DHW_SCHEDULE_WEEK]

    @pytest.mark.asyncio
    async def test_apply_after_close_is_a_no_op(self):
        """A task queued before unload must not add entities to a reset platform."""
        sync, _coord, added = self._make_sync("week")
        registry = self._registry({})
        sync.async_close()
        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_apply()

        assert added == []
        registry.async_update_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_while_waiting_for_the_lock_stops_the_queued_pass(self):
        """The unload can land while a pass is already queued behind the lock."""
        sync, _coord, added = self._make_sync("week")
        registry = self._registry({})
        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync._lock.acquire()
            queued = asyncio.create_task(sync.async_apply())
            await asyncio.sleep(0)
            assert not queued.done()

            sync.async_close()
            sync._lock.release()
            await queued

        assert added == []
        registry.async_update_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_unchanged_mode_does_not_touch_anything(self):
        sync, _coord, added = self._make_sync("week")
        registry = self._registry({})
        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()
            registry.async_update_entity.reset_mock()
            await sync.async_apply()

        assert len(added) == 1
        registry.async_update_entity.assert_not_called()


# ===========================================================================
# Real-hass integration tests
# ===========================================================================


@pytest.mark.usefixtures("enable_custom_integrations")
class TestTimerScheduleSyncAgainstRealHass:
    """The swap mechanism against a real `hass` and a real entity registry.

    The unit tests above drive `_TimerScheduleSync` with a MagicMock registry
    and a stubbed `async_remove`, so they cannot pin the HA contracts this
    design actually rests on: that `async_remove()` without `force_remove`
    keeps the registry entry (and leaves a `restored` state behind), that
    re-adding the same unique_id after a swap-back succeeds instead of
    tripping "Entity id already exists", and that an entity whose add was
    aborted (disabled registry entry) does not break the next pass.
    """

    _SELECTOR = "ID_Einst_SUBW_akt2"
    _WEEK_ID = f"text.{DOMAIN}_{SK.TIMER_DHW_SCHEDULE_WEEK}"
    _WEEKDAY_ID = f"text.{DOMAIN}_{SK.TIMER_DHW_SCHEDULE_WEEKDAY}"
    _WEEKEND_ID = f"text.{DOMAIN}_{SK.TIMER_DHW_SCHEDULE_WEEKEND}"

    def _client(self, mode: str):
        from test_setup_integration import FakeLuxtronikClient

        parameters: dict[str, Any] = DEFAULT_PARAMETERS.copy()
        parameters[self._SELECTOR] = mode
        return FakeLuxtronikClient(
            host="192.168.1.100",
            port=DEFAULT_PORT,
            socket_timeout=10,
            max_data_length=1024,
            parameters=parameters,
        )

    async def _setup(self, hass: HomeAssistant, monkeypatch, client) -> MockConfigEntry:
        monkeypatch.setattr(
            "custom_components.luxtronik2.coordinator.Luxtronik",
            lambda **kwargs: client,
        )
        entry = MockConfigEntry(
            domain=DOMAIN,
            version=CONFIG_ENTRY_VERSION,
            data={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: DEFAULT_PORT,
                CONF_HA_SENSOR_PREFIX: DOMAIN,
            },
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    async def _switch_to(self, hass: HomeAssistant, entry, client, mode: str) -> None:
        client.parameters.set(self._SELECTOR, mode)
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    async def test_program_round_trip_keeps_the_registry_entry(
        self, hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = self._client("week")
        entry = await self._setup(hass, monkeypatch, client)
        registry = er.async_get(hass)

        # Active program: entity live, registry entry enabled.
        assert hass.states.get(self._WEEK_ID) is not None
        assert hass.states.get(self._WEEKDAY_ID) is None
        week_entry = registry.async_get(self._WEEK_ID)
        assert week_entry is not None
        assert week_entry.disabled_by is None

        await self._switch_to(hass, entry, client, "5+2")

        # The week block is gone from the state machine (async_remove without
        # force_remove leaves a `restored` placeholder because the registry
        # entry survives), and its registry entry is disabled, not removed.
        week_state = hass.states.get(self._WEEK_ID)
        assert week_state is None or week_state.attributes.get("restored") is True
        week_entry = registry.async_get(self._WEEK_ID)
        assert week_entry is not None
        assert week_entry.disabled_by is RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(self._WEEKDAY_ID) is not None
        assert hass.states.get(self._WEEKEND_ID) is not None

        # Clearing disabled_by makes HA schedule a config-entry reload 30s
        # from now (config_entries.RELOAD_AFTER_UPDATE_DELAY) via
        # EntityRegistryDisabledHandler. Collapse that delay to 0 so the
        # reload actually runs inside this test instead of leaving a 30s
        # timer pending - both to exercise the real end-to-end behaviour and
        # to avoid a lingering-timer teardown warning.
        monkeypatch.setattr("homeassistant.config_entries.RELOAD_AFTER_UPDATE_DELAY", 0)

        await self._switch_to(hass, entry, client, "week")
        # Let the (now near-instant) reload timer fire and the resulting
        # config-entry reload task finish.
        await hass.async_block_till_done()

        # Swapping back re-adds under the same entity_id and re-enables it -
        # surviving the config-entry reload that clearing disabled_by causes.
        week_state = hass.states.get(self._WEEK_ID)
        assert week_state is not None
        assert week_state.attributes.get("restored") is not True
        week_entry = registry.async_get(self._WEEK_ID)
        assert week_entry is not None
        assert week_entry.disabled_by is None

    async def test_a_user_rename_survives_the_round_trip(
        self, hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The whole point of disabling instead of removing the registry entry."""
        client = self._client("week")
        entry = await self._setup(hass, monkeypatch, client)
        registry = er.async_get(hass)
        renamed_id = "text.my_dhw_week_schedule"
        registry.async_update_entity(
            self._WEEK_ID, new_entity_id=renamed_id, name="My week schedule"
        )
        await hass.async_block_till_done()

        # See test_program_round_trip_keeps_the_registry_entry: re-enabling
        # the week block on the way back schedules HA's 30s config-entry
        # reload; collapse it so it actually runs in this test.
        monkeypatch.setattr("homeassistant.config_entries.RELOAD_AFTER_UPDATE_DELAY", 0)

        await self._switch_to(hass, entry, client, "5+2")
        await self._switch_to(hass, entry, client, "week")
        await hass.async_block_till_done()

        renamed_entry = registry.async_get(renamed_id)
        assert renamed_entry is not None
        assert renamed_entry.name == "My week schedule"
        assert renamed_entry.disabled_by is None
        assert hass.states.get(renamed_id) is not None

    async def test_a_disabled_schedule_entity_does_not_break_the_swap(
        self, hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A user-disabled block is never added, so it must not be removed either.

        Regression test: `async_add_entities` only schedules the add, and
        `EntityPlatform._async_add_entity` aborts it for a disabled registry
        entry (setting `entity.hass = None`). The next program switch then
        raised inside the sync task, skipping the remaining removals and the
        disable pass entirely.
        """
        client = self._client("week")
        registry = er.async_get(hass)
        registry.async_get_or_create(
            "text",
            DOMAIN,
            self._WEEK_ID,
            suggested_object_id=f"{DOMAIN}_{SK.TIMER_DHW_SCHEDULE_WEEK}",
            disabled_by=er.RegistryEntryDisabler.USER,
        )
        entry = await self._setup(hass, monkeypatch, client)
        assert hass.states.get(self._WEEK_ID) is None

        await self._switch_to(hass, entry, client, "5+2")

        # The pass completed: the new program's entities exist and the
        # user-disabled, now-inactive week entry is left exactly as the user
        # set it.
        assert hass.states.get(self._WEEKDAY_ID) is not None
        assert hass.states.get(self._WEEKEND_ID) is not None
        week_entry = registry.async_get(self._WEEK_ID)
        assert week_entry is not None
        assert week_entry.disabled_by is er.RegistryEntryDisabler.USER

    async def test_hidden_by_from_the_previous_hide_based_build_is_cleared(
        self, hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Installs that ran the interim hidden-based build must not keep it.

        Both an active and an inactive schedule entity carrying the old
        `hidden_by = INTEGRATION` from that build get it cleared on the next
        sync pass - the inactive one is disabled instead, the active one is
        left enabled.
        """
        client = self._client("week")
        registry = er.async_get(hass)
        registry.async_get_or_create(
            "text",
            DOMAIN,
            self._WEEK_ID,
            suggested_object_id=f"{DOMAIN}_{SK.TIMER_DHW_SCHEDULE_WEEK}",
            hidden_by=RegistryEntryHider.INTEGRATION,
        )
        registry.async_get_or_create(
            "text",
            DOMAIN,
            self._WEEKDAY_ID,
            suggested_object_id=f"{DOMAIN}_{SK.TIMER_DHW_SCHEDULE_WEEKDAY}",
            hidden_by=RegistryEntryHider.INTEGRATION,
        )

        entry = await self._setup(hass, monkeypatch, client)
        assert entry.state.value == "loaded"

        week_entry = registry.async_get(self._WEEK_ID)
        assert week_entry is not None
        assert week_entry.hidden_by is None
        assert week_entry.disabled_by is None

        weekday_entry = registry.async_get(self._WEEKDAY_ID)
        assert weekday_entry is not None
        assert weekday_entry.hidden_by is None
        assert weekday_entry.disabled_by is RegistryEntryDisabler.INTEGRATION

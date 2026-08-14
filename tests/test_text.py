"""Tests for the DHW timer-program schedule text entities."""

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
            for start_name, end_name in description.row_names:
                names.extend([start_name, end_name])
            for name in names:
                if name not in known_names:
                    problems.append(f"{description.key}: {name!r} not in Parameters")

        assert not problems, "\n".join(problems)

    def test_entity_count(self):
        assert len(TIMER_SCHEDULE_ENTITIES) == 20

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
        return [d.key for d in _active_schedule_descriptions(coord, data)]

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

    def test_data_none_yields_no_information(self):
        """No coordinator data at all is "unknown", not "no program active"."""
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        assert _active_schedule_descriptions(_mock_coordinator(), None) is None

    def test_undecodable_selector_yields_no_information(self):
        """A present-but-unreadable selector must not read as "no program active".

        `get_sensor_data` returns None both for an absent register and for a
        register whose datatype could not decode the raw value this poll
        (`SelectionBase` returns None for an unrecognised code). Treating the
        latter as "nothing is active" would drop all 10 entities and disable
        all 10 registry entries on a single glitched read.
        """
        from custom_components.luxtronik2.text import _active_schedule_descriptions

        data = make_coordinator_data(parameters={self._SELECTOR: None})
        coord = _mock_coordinator(data)
        assert _active_schedule_descriptions(coord, data) is None

    def test_inactive_entity_yields_nothing(self):
        assert self._call({self._SELECTOR: "week"}, entity_active=False) == []


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
    async def test_unreadable_selector_does_not_remove_or_disable_anything(self):
        """A glitched selector read must be a no-op, not a full teardown.

        Regression test: treating an undecodable selector value as "no
        program active" removed every live schedule entity and wrote
        `disabled_by = INTEGRATION` on all 10 registry entries, with the next
        good poll re-adding and re-enabling them - entity churn, registry
        writes and a recorder gap caused by one transient read.
        """
        from custom_components.luxtronik2.text import LuxtronikTimerScheduleText

        sync, coord, _added = self._make_sync("week")
        registry = self._registry({})
        with (
            patch(
                "custom_components.luxtronik2.text.er.async_get", return_value=registry
            ),
            patch("homeassistant.helpers.frame.report_usage"),
        ):
            await sync.async_setup()
            registry.async_update_entity.reset_mock()
            coord.data = make_coordinator_data(parameters={self._SELECTOR: None})
            with patch.object(
                LuxtronikTimerScheduleText, "async_remove", new=AsyncMock()
            ) as remove:
                await sync.async_apply()

        remove.assert_not_awaited()
        registry.async_update_entity.assert_not_called()
        assert list(sync._entities) == [SK.TIMER_DHW_SCHEDULE_WEEK]

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

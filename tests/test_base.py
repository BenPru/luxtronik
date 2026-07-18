"""Tests for custom_components.luxtronik2.base (LuxtronikEntity)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from conftest import make_coordinator_data
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TIMEOUT,
    UnitOfTime,
)
import pytest

from custom_components.luxtronik2.base import LuxtronikEntity
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxCalculation as LC,
    LuxMode,
    LuxOperationMode,
    LuxParameter as LP,
    LuxVisibility as LV,
    SensorAttrFormat,
    SensorAttrKey as SA,
    SensorKey,
)
from custom_components.luxtronik2.model import (
    LuxtronikClimateDescription,
    LuxtronikEntityAttributeDescription,
    LuxtronikIndexSensorDescription,
    LuxtronikSensorDescription,
)
from custom_components.luxtronik2.sensor import LuxtronikSensorEntity

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


def _mock_coordinator(data=None):
    if data is None:
        data = make_coordinator_data()
    coord = MagicMock()
    coord.data = data
    coord.entity_active.return_value = True
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    return coord


def _patch_entity(entity):
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()


def _make_sensor_entity(data=None, description=None):
    hass = MagicMock()
    entry = _mock_entry()
    coord = _mock_coordinator(data)
    if description is None:
        description = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
        )
    entity = LuxtronikSensorEntity(hass, entry, coord, description, DeviceKey.heatpump)
    _patch_entity(entity)
    return entity


# ===========================================================================
# _handle_coordinator_update (base)
# ===========================================================================


class TestBaseHandleCoordinatorUpdate:
    def test_datetime_without_tzinfo_gets_timezone(self):
        """Datetime values without tzinfo get local timezone."""
        naive_dt = datetime(2024, 1, 15, 10, 30, 0)
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": naive_dt})
        entity = _make_sensor_entity(data)
        # Call the base _handle_coordinator_update
        LuxtronikEntity._handle_coordinator_update(entity, data)
        assert entity._attr_state.tzinfo is not None

    def test_icon_by_state(self):
        """Icon changes based on state."""
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": "heating"})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            icon="mdi:default",
            icon_by_state={"heating": "mdi:fire"},
        )
        entity = _make_sensor_entity(data, desc)
        LuxtronikEntity._handle_coordinator_update(entity, data)
        assert entity._attr_icon == "mdi:fire"

    def test_icon_fallback(self):
        """When no matching icon_by_state, use default icon."""
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": "unknown"})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            icon="mdi:default",
            icon_by_state={"heating": "mdi:fire"},
        )
        entity = _make_sensor_entity(data, desc)
        LuxtronikEntity._handle_coordinator_update(entity, data)
        assert entity._attr_icon == "mdi:default"


# ===========================================================================
# should_update
# ===========================================================================


class TestShouldUpdate:
    def test_no_interval_always_true(self):
        entity = _make_sensor_entity()
        assert entity.should_update() is True

    def test_with_interval_and_no_next_update(self):
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            update_interval=timedelta(seconds=60),
        )
        entity = _make_sensor_entity(description=desc)
        entity.next_update = None
        assert entity.should_update() is True

    def test_with_interval_and_future_next_update(self):
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            update_interval=timedelta(seconds=60),
        )
        entity = _make_sensor_entity(description=desc)
        # Set next_update far in the future (UTC) so should_update returns False
        entity.next_update = datetime.now(UTC) + timedelta(hours=1)
        assert entity.should_update() is False

    def test_with_interval_and_past_next_update(self):
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            update_interval=timedelta(seconds=60),
        )
        entity = _make_sensor_entity(description=desc)
        entity.next_update = datetime.now(UTC) - timedelta(hours=1)
        assert entity.should_update() is True


# ===========================================================================
# compute_is_on
# ===========================================================================


class TestComputeIsOn:
    def _make_entity_with_on_state(
        self, on_state, state=None, inverted=False, on_states=None
    ):
        from custom_components.luxtronik2.model import LuxtronikSwitchDescription

        desc = LuxtronikSwitchDescription(
            key=SensorKey.HEATING,
            luxtronik_key=LP.P0003_MODE_HEATING,
            device_key=DeviceKey.heating,
            on_state=on_state,
            inverted=inverted,
            on_states=on_states,
        )
        from custom_components.luxtronik2.switch import LuxtronikSwitchEntity

        hass = MagicMock()
        entry = _mock_entry()
        coord = _mock_coordinator()
        entity = LuxtronikSwitchEntity(hass, entry, coord, desc, DeviceKey.heating)
        return entity

    def test_bool_on_state_true(self):
        entity = self._make_entity_with_on_state(True)
        assert entity.compute_is_on(True) is True

    def test_bool_on_state_false(self):
        entity = self._make_entity_with_on_state(True)
        assert entity.compute_is_on(False) is False

    def test_string_state_matches(self):
        entity = self._make_entity_with_on_state("active")
        assert entity.compute_is_on("active") is True

    def test_string_state_not_matches(self):
        entity = self._make_entity_with_on_state("active")
        assert entity.compute_is_on("inactive") is False

    def test_on_states_list(self):
        entity = self._make_entity_with_on_state(
            "active", on_states=["active", "running"]
        )
        assert entity.compute_is_on("running") is True

    def test_inverted(self):
        entity = self._make_entity_with_on_state(True, inverted=True)
        assert entity.compute_is_on(True) is False
        assert entity.compute_is_on(False) is True

    def test_none_state_with_bool_on_state(self):
        entity = self._make_entity_with_on_state(True)
        assert entity.compute_is_on(None) is False

    def test_int_state_as_bool(self):
        entity = self._make_entity_with_on_state(True)
        assert entity.compute_is_on(1) is True
        assert entity.compute_is_on(0) is False


# ===========================================================================
# formatted_data
# ===========================================================================


class TestFormattedData:
    def test_hour_minute_format(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 7200})
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.HOUR_MINUTE,
        )
        result = entity.formatted_data(attr)
        assert UnitOfTime.HOURS in result
        assert "2:00" in result

    def test_celsius_tenth_format(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 255})
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.CELSIUS_TENTH,
        )
        result = entity.formatted_data(attr)
        assert "25.5" in result

    def test_none_value_returns_empty(self):
        data = make_coordinator_data(calculations={})
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
        )
        result = entity.formatted_data(attr)
        assert result == ""

    def test_no_format_returns_str(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 42})
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
        )
        result = entity.formatted_data(attr)
        assert result == "42"

    def test_datetime_value_returns_str(self):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": dt})
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.HOUR_MINUTE,
        )
        # datetime is handled before format check
        result = entity.formatted_data(attr)
        assert "2024" in result

    def test_switch_gap_heating(self):
        """Test SWITCH_GAP format when heating."""
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Automatic",
                "ID_Ba_Bw_akt": "Automatic",
                "ID_Einst_HRHyst_akt": 50,  # 50 * 0.1 = 5.0
            },
            calculations={
                "ID_WEB_Temperatur_TRL": 30.0,  # flow_out
                "ID_WEB_Sollwert_TRL_HZ": 28.0,  # flow_out_target
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            },
        )
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.SWITCH_GAP,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.SWITCH_GAP,
        )
        result = entity.formatted_data(attr)
        assert "K" in result  # UnitOfTemperature.KELVIN

    def test_switch_gap_not_heating_not_off(self):
        """Test SWITCH_GAP when mode is not heating and not off."""
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Automatic",  # not LuxMode.off
                "ID_Ba_Bw_akt": "Automatic",
                "ID_Einst_HRHyst_akt": 50,
            },
            calculations={
                "ID_WEB_Temperatur_TRL": 30.0,
                "ID_WEB_Sollwert_TRL_HZ": 28.0,
                "ID_WEB_WP_BZ_akt": LuxOperationMode.domestic_water,
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            },
        )
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.SWITCH_GAP,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.SWITCH_GAP,
        )
        result = entity.formatted_data(attr)
        assert "K" in result

    def test_switch_gap_mode_off(self):
        """Test SWITCH_GAP when heating mode is off."""
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": LuxMode.off,
                "ID_Ba_Bw_akt": "Automatic",
                "ID_Einst_HRHyst_akt": 50,
            },
            calculations={
                "ID_WEB_Temperatur_TRL": 30.0,
                "ID_WEB_Sollwert_TRL_HZ": 28.0,
                "ID_WEB_WP_BZ_akt": LuxOperationMode.domestic_water,
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            },
        )
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.SWITCH_GAP,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.SWITCH_GAP,
        )
        result = entity.formatted_data(attr)
        assert result == ""


# ===========================================================================
# async_added_to_hass
# ===========================================================================


class TestAsyncAddedToHass:
    @pytest.mark.asyncio
    async def test_restores_last_state(self):
        entity = _make_sensor_entity()
        last_state = MagicMock()
        last_state.state = "25.5"
        last_state.attributes = {}
        entity.async_get_last_state = AsyncMock(return_value=last_state)
        entity.async_get_last_extra_data = AsyncMock(return_value=None)
        entity.async_on_remove = MagicMock()
        entity.entity_id = "sensor.test_entity"
        entity.platform = MagicMock()
        # Prevent _handle_coordinator_update from overwriting
        entity.coordinator.data = None

        with patch("custom_components.luxtronik2.base.async_dispatcher_connect"):
            await LuxtronikEntity.async_added_to_hass(entity)

        assert entity._attr_state == "25.5"

    @pytest.mark.asyncio
    async def test_restores_attr_cache_on_startup(self):
        """When last_state has restorable attrs, they fill _attr_cache."""
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            extra_attributes=(
                LuxtronikEntityAttributeDescription(
                    key=SA.TIMER_HEATPUMP_ON,
                    luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
                    restore_on_startup=True,
                ),
                LuxtronikEntityAttributeDescription(
                    key=SA.LUXTRONIK_KEY,
                    luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
                    restore_on_startup=False,
                ),
            ),
        )
        entity = _make_sensor_entity(description=desc)
        last_state = MagicMock()
        last_state.state = "25.5"
        last_state.attributes = {SA.TIMER_HEATPUMP_ON: "restored_value"}
        entity.async_get_last_state = AsyncMock(return_value=last_state)
        entity.async_get_last_extra_data = AsyncMock(return_value=None)
        entity.async_on_remove = MagicMock()
        entity.entity_id = "sensor.test_entity"
        entity.platform = MagicMock()
        entity.coordinator.data = None

        with patch("custom_components.luxtronik2.base.async_dispatcher_connect"):
            await LuxtronikEntity.async_added_to_hass(entity)

        assert entity._attr_cache[SA.TIMER_HEATPUMP_ON] == "restored_value"

    @pytest.mark.asyncio
    async def test_no_last_state_returns_early(self):
        entity = _make_sensor_entity()
        entity.async_get_last_state = AsyncMock(return_value=None)
        entity.async_get_last_extra_data = AsyncMock(return_value=None)
        entity.platform = MagicMock()

        await LuxtronikEntity.async_added_to_hass(entity)
        # Should not crash

    @pytest.mark.asyncio
    async def test_restores_extra_data(self):
        entity = _make_sensor_entity()
        last_state = MagicMock()
        last_state.state = "42"
        last_state.attributes = {}
        entity.async_get_last_state = AsyncMock(return_value=last_state)

        extra_data = MagicMock()
        extra_data.as_dict.return_value = {"_attr_target_temperature": 22.0}
        entity.async_get_last_extra_data = AsyncMock(return_value=extra_data)
        entity.async_on_remove = MagicMock()
        entity.entity_id = "sensor.test_entity"
        entity.platform = MagicMock()

        with patch("custom_components.luxtronik2.base.async_dispatcher_connect"):
            await LuxtronikEntity.async_added_to_hass(entity)

        assert entity._attr_target_temperature == 22.0

    @pytest.mark.asyncio
    async def test_exception_is_caught(self):
        entity = _make_sensor_entity()
        entity.async_get_last_state = AsyncMock(side_effect=Exception("test error"))
        entity.platform = MagicMock()

        # Should not raise
        await LuxtronikEntity.async_added_to_hass(entity)


# ===========================================================================
# _handle_coordinator_update — icon with current_operation
# ===========================================================================


class TestIconByState:
    def test_icon_by_state_sets_icon(self):
        """When icon_by_state matches current state, _attr_icon is set."""
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 25.0})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            icon="mdi:water",
            icon_by_state={25.0: "mdi:water-check"},
        )
        entity = _make_sensor_entity(data, desc)
        LuxtronikEntity._handle_coordinator_update(entity, data)
        assert entity._attr_icon == "mdi:water-check"

    def test_icon_by_state_fallback_to_icon(self):
        """When icon_by_state doesn't match, falls back to descr.icon."""
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 99.0})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            icon="mdi:water",
            icon_by_state={25.0: "mdi:water-check"},
        )
        entity = _make_sensor_entity(data, desc)
        LuxtronikEntity._handle_coordinator_update(entity, data)
        assert entity._attr_icon == "mdi:water"

    def test_icon_by_state_clears_stale_icon(self):
        """When icon_by_state doesn't match and descr.icon is None, stale icon is cleared."""
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 99.0})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            icon_by_state={25.0: "mdi:water-check"},
        )
        entity = _make_sensor_entity(data, desc)
        entity._attr_icon = "mdi:water-check"  # simulate previous match
        LuxtronikEntity._handle_coordinator_update(entity, data)
        assert entity._attr_icon is None

    def test_no_icon_set_without_icon_by_state(self):
        """When icon_by_state is not set, _attr_icon is not touched (icons.json handles it)."""
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 25.0})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
        )
        entity = _make_sensor_entity(data, desc)
        LuxtronikEntity._handle_coordinator_update(entity, data)
        assert not hasattr(entity, "_attr_icon") or entity._attr_icon is None


# ===========================================================================
# entity_registry_enabled_default is None (base.py line 78)
# ===========================================================================


class TestBaseEntityRegistryEnabledDefault:
    def test_none_enabled_default_calls_entity_visible(self):
        """When entity_registry_enabled_default is None, coordinator.entity_visible is called."""
        coord = _mock_coordinator()
        coord.entity_visible.return_value = False
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            entity_registry_enabled_default=None,  # triggers the branch
        )
        entity = LuxtronikSensorEntity(
            MagicMock(), _mock_entry(), coord, desc, DeviceKey.heatpump
        )
        _patch_entity(entity)
        assert entity.entity_description.entity_registry_enabled_default is False
        coord.entity_visible.assert_called()

    def test_default_omitted_falls_back_to_coordinator_visibility_when_not_visible(
        self,
    ):
        """Regression test for C2: a description that does NOT explicitly set
        entity_registry_enabled_default (i.e. relies on the dataclass default)
        must still have its enabled-default driven by coordinator.entity_visible()
        when the heat pump reports the entity's visibility flag as not visible.

        Before the fix, LuxtronikEntityDescription.entity_registry_enabled_default
        defaulted to `bool = True`, so the `is None` branch in
        LuxtronikEntity.__init__ never fired for real (non-test-authored)
        descriptions, and this assertion failed with True != False.
        """
        coord = _mock_coordinator()
        coord.entity_visible.return_value = False
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            visibility=LV.V0005_COOLING,
            # entity_registry_enabled_default intentionally omitted
        )
        entity = LuxtronikSensorEntity(
            MagicMock(), _mock_entry(), coord, desc, DeviceKey.heatpump
        )
        _patch_entity(entity)
        assert entity.entity_description.entity_registry_enabled_default is False
        coord.entity_visible.assert_called()

    def test_default_omitted_stays_enabled_when_coordinator_reports_visible(self):
        """Sanity check for the same fallback: when the coordinator reports the
        entity IS visible, the omitted-default description ends up enabled."""
        coord = _mock_coordinator()
        coord.entity_visible.return_value = True
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            visibility=LV.V0005_COOLING,
        )
        entity = LuxtronikSensorEntity(
            MagicMock(), _mock_entry(), coord, desc, DeviceKey.heatpump
        )
        _patch_entity(entity)
        assert entity.entity_description.entity_registry_enabled_default is True

    def test_explicit_false_wins_over_visibility(self):
        """Explicit False must keep winning even when the coordinator reports
        the entity as visible (i.e. explicit values are never overridden)."""
        coord = _mock_coordinator()
        coord.entity_visible.return_value = True
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            entity_registry_enabled_default=False,
        )
        entity = LuxtronikSensorEntity(
            MagicMock(), _mock_entry(), coord, desc, DeviceKey.heatpump
        )
        _patch_entity(entity)
        assert entity.entity_description.entity_registry_enabled_default is False
        coord.entity_visible.assert_not_called()

    def test_explicit_true_wins_over_visibility(self):
        """Explicit True must keep winning even when the coordinator reports
        the entity as not visible (i.e. explicit values are never overridden)."""
        coord = _mock_coordinator()
        coord.entity_visible.return_value = False
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            entity_registry_enabled_default=True,
        )
        entity = LuxtronikSensorEntity(
            MagicMock(), _mock_entry(), coord, desc, DeviceKey.heatpump
        )
        _patch_entity(entity)
        assert entity.entity_description.entity_registry_enabled_default is True
        coord.entity_visible.assert_not_called()


# ===========================================================================
# StrEnum / None / else branches in __init__ loop (base.py lines 103, 109)
# ===========================================================================


class TestBaseExtraKeyLoop:
    def test_strenum_value_in_extra_attrs(self):
        """StrEnum value is formatted as 'name[1:5] value'."""
        desc = LuxtronikClimateDescription(
            key=SensorKey.HEATING,
            luxtronik_key=LP.P0003_MODE_HEATING,
            device_key=DeviceKey.heating,
            luxtronik_key_current_temperature=LC.C0227_ROOM_THERMOSTAT_TEMPERATURE,
            luxtronik_key_current_action=LC.C0080_STATUS,
        )
        coord = _mock_coordinator()
        entity = LuxtronikEntity(coord, desc, DeviceKey.heating)
        _patch_entity(entity)
        assert (
            "luxtronik_key_current_temperature" in entity._attr_extra_state_attributes
        )
        val = entity._attr_extra_state_attributes["luxtronik_key_current_temperature"]
        assert isinstance(val, str)
        assert LC.C0227_ROOM_THERMOSTAT_TEMPERATURE.value in val

    def test_non_strenum_value_in_extra_attrs(self):
        """Non-StrEnum value is stored directly."""
        desc = LuxtronikClimateDescription(
            key=SensorKey.HEATING,
            luxtronik_key=LP.P0003_MODE_HEATING,
            device_key=DeviceKey.heating,
            luxtronik_key_current_temperature="sensor.my_temp",  # string, not StrEnum
            luxtronik_key_current_action=LC.C0080_STATUS,
        )
        coord = _mock_coordinator()
        entity = LuxtronikEntity(coord, desc, DeviceKey.heating)
        _patch_entity(entity)
        assert (
            entity._attr_extra_state_attributes["luxtronik_key_current_temperature"]
            == "sensor.my_temp"
        )

    def test_none_value_skipped_in_extra_attrs(self):
        """When a luxtronik_key_* field is None, it's skipped."""
        desc = LuxtronikIndexSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            luxtronik_key_timestamp=None,  # pyright: ignore[reportArgumentType]
        )
        coord = _mock_coordinator()
        entity = LuxtronikEntity(coord, desc, DeviceKey.heatpump)
        _patch_entity(entity)
        assert "luxtronik_key_timestamp" not in entity._attr_extra_state_attributes


# ===========================================================================
# _restore_attr_value (base.py line 162), _data_update (base.py line 171)
# ===========================================================================


class TestBaseHelperMethods:
    def test_restore_attr_value_passthrough(self):
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
        )
        coord = _mock_coordinator()
        entity = LuxtronikEntity(coord, desc, DeviceKey.heatpump)
        _patch_entity(entity)
        assert entity._restore_attr_value(42) == 42
        assert entity._restore_attr_value(None) is None

    @pytest.mark.asyncio
    async def test_data_update_calls_handle(self):
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
        )
        coord = _mock_coordinator()
        entity = LuxtronikEntity(coord, desc, DeviceKey.heatpump)
        _patch_entity(entity)
        with patch.object(entity, "_handle_coordinator_update") as mock_handle:
            await entity._data_update(MagicMock())
            mock_handle.assert_called_once()


# ===========================================================================
# _enrich_extra_attributes (base.py lines 227-231)
# ===========================================================================


class TestBaseEnrichExtraAttributes:
    def test_skips_attr_with_no_format_and_unset_key(self):
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            extra_attributes=(
                LuxtronikEntityAttributeDescription(
                    key=SA.TIMER_HEATPUMP_ON,
                    luxtronik_key=LP.UNSET,
                    format=None,
                ),
            ),
        )
        coord = _mock_coordinator()
        entity = LuxtronikEntity(coord, desc, DeviceKey.heatpump)
        _patch_entity(entity)
        entity._enrich_extra_attributes()
        assert SA.TIMER_HEATPUMP_ON.value not in entity._attr_extra_state_attributes

    def test_includes_attr_with_format(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 7200})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            extra_attributes=(
                LuxtronikEntityAttributeDescription(
                    key=SA.TIMER_HEATPUMP_ON,
                    luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
                    format=SensorAttrFormat.HOUR_MINUTE,
                ),
            ),
        )
        coord = _mock_coordinator(data)
        entity = LuxtronikSensorEntity(
            MagicMock(), _mock_entry(), coord, desc, DeviceKey.heatpump
        )
        _patch_entity(entity)
        entity._enrich_extra_attributes()
        assert SA.TIMER_HEATPUMP_ON.value in entity._attr_extra_state_attributes


# ===========================================================================
# _schedule_immediate_update (base.py line 239)
# ===========================================================================


class TestBaseScheduleImmediateUpdate:
    def test_schedule_immediate_update(self):
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
        )
        coord = _mock_coordinator()
        entity = LuxtronikEntity(coord, desc, DeviceKey.heatpump)
        _patch_entity(entity)
        entity._schedule_immediate_update()
        entity.async_schedule_update_ha_state.assert_called_once_with(True)


# ===========================================================================
# return str(value) fallback (base.py line 274)
# ===========================================================================


class TestBaseFormattedDataFallback:
    def test_unknown_format_returns_str(self):
        """When format doesn't match any known case, return str(value)."""
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 42})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
        )
        coord = _mock_coordinator(data)
        entity = LuxtronikSensorEntity(
            MagicMock(), _mock_entry(), coord, desc, DeviceKey.heatpump
        )
        _patch_entity(entity)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.TIMESTAMP_LAST_OVER,
        )
        result = entity.formatted_data(attr)
        assert result == "42"

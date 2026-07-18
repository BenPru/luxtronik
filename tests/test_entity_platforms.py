"""Tests for entity platform setup and entity behaviour."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, UnitOfTemperature
import pytest

from conftest import make_coordinator_data
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
    SensorKey as SK,
)
from custom_components.luxtronik2.model import (
    LuxtronikBinarySensorEntityDescription,
    LuxtronikClimateDescription,
    LuxtronikDateEntityDescription,
    LuxtronikNumberDescription,
    LuxtronikSelectEntityDescription,
    LuxtronikSensorDescription,
    LuxtronikSwitchDescription,
    LuxtronikWaterHeaterDescription,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    coord.async_write = AsyncMock(return_value=data)
    return coord


def _patch_entity_hass(entity):
    """Patch entity so _handle_coordinator_update doesn't require real HA."""
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()


# ===========================================================================
# async_setup_entry — switch
# ===========================================================================


class TestSwitchAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_skips_when_no_update_success(self):
        from custom_components.luxtronik2.switch import async_setup_entry

        coord = _mock_coordinator(last_update_success=False)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()

        await async_setup_entry(MagicMock(), entry, add)
        add.assert_not_called()

    @pytest.mark.asyncio
    async def test_adds_entities(self):
        from custom_components.luxtronik2.switch import async_setup_entry

        data = make_coordinator_data(
            parameters={
                "ID_Einst_Fernwartung_akt": 0,
                "ID_Einst_Effizienzpumpe_akt": 0,
                "ID_Einst_Popt_akt": 0,
                "ID_Einst_P155_PumpHeatCtrl_akt": 0,
                "ID_Einst_Heizgrenze_Sollwert_akt": 1,
            }
        )
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()

        with patch("homeassistant.helpers.frame.report_usage"):
            await async_setup_entry(MagicMock(), entry, add)

        # At least one entity should be added (from predefined SWITCHES)
        add.assert_called_once()
        entities = add.call_args[0][0]
        assert len(entities) > 0


# ===========================================================================
# LuxtronikSwitchEntity
# ===========================================================================


class TestLuxtronikSwitchEntity:
    def _make_switch(self, param_key="ID_Einst_Fernwartung_akt", value=0):
        from custom_components.luxtronik2.switch import LuxtronikSwitchEntity

        data = make_coordinator_data(parameters={param_key: value})
        coord = _mock_coordinator(data)
        desc = LuxtronikSwitchDescription(
            key=SK.REMOTE_MAINTENANCE,
            luxtronik_key=LP.P0860_REMOTE_MAINTENANCE,
            on_state=1,
            off_state=0,
            device_key=DeviceKey.heatpump,
        )
        entry = _mock_entry()

        with patch("homeassistant.helpers.frame.report_usage"):
            entity = LuxtronikSwitchEntity(
                MagicMock(), entry, coord, desc, DeviceKey.heatpump
            )
        _patch_entity_hass(entity)
        return entity, coord

    def test_entity_id(self):
        entity, _ = self._make_switch()
        assert entity.entity_id == f"switch.{DOMAIN}_{SK.REMOTE_MAINTENANCE}"
        assert entity._attr_unique_id == entity.entity_id

    def test_handle_coordinator_update_on(self):
        entity, _ = self._make_switch(value=1)
        data = make_coordinator_data(parameters={"ID_Einst_Fernwartung_akt": 1})
        entity._handle_coordinator_update(data)
        assert entity._attr_is_on is True

    def test_handle_coordinator_update_off(self):
        entity, _ = self._make_switch(value=0)
        data = make_coordinator_data(parameters={"ID_Einst_Fernwartung_akt": 0})
        entity._handle_coordinator_update(data)
        assert entity._attr_is_on is False

    def test_handle_coordinator_update_none_data(self):
        entity, coord = self._make_switch()
        coord.data = None
        entity._handle_coordinator_update(None)
        # Should not crash

    @pytest.mark.asyncio
    async def test_turn_on(self):
        entity, coord = self._make_switch()
        await entity.async_turn_on()
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_turn_off(self):
        entity, coord = self._make_switch()
        await entity.async_turn_off()
        coord.async_write.assert_called_once()


# ===========================================================================
# async_setup_entry — binary_sensor
# ===========================================================================


class TestBinarySensorAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_adds_entities(self):
        from custom_components.luxtronik2.binary_sensor import async_setup_entry

        data = make_coordinator_data(
            calculations={
                "ID_WEB_EVUin": 0,
                "ID_WEB_HZIO_EVU2": 1,
                "ID_WEB_LIN_VDH_Pumpe": False,
                "ID_WEB_VD1out": 0,
                "ID_WEB_HUPout": 0,
                "ID_WEB_FreigabKuehl": 0,
            }
        )
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()

        with patch("homeassistant.helpers.frame.report_usage"):
            await async_setup_entry(MagicMock(), entry, add)

        add.assert_called_once()
        entities = add.call_args[0][0]
        assert len(entities) > 0


# ===========================================================================
# LuxtronikBinarySensorEntity
# ===========================================================================


class TestLuxtronikBinarySensorEntity:
    def _make_binary_sensor(self, calc_key="ID_WEB_FreigabKuehl", value=0):
        from custom_components.luxtronik2.binary_sensor import (
            LuxtronikBinarySensorEntity,
        )

        data = make_coordinator_data(calculations={calc_key: value})
        coord = _mock_coordinator(data)
        desc = LuxtronikBinarySensorEntityDescription(
            key=SK.EVU_UNLOCKED,
            luxtronik_key=LC.C0146_APPROVAL_COOLING,
            on_state=1,
            off_state=0,
            device_key=DeviceKey.heatpump,
        )
        entry = _mock_entry()

        with patch("homeassistant.helpers.frame.report_usage"):
            entity = LuxtronikBinarySensorEntity(
                MagicMock(), entry, coord, desc, DeviceKey.heatpump
            )
        _patch_entity_hass(entity)
        return entity, coord

    def test_entity_id(self):
        entity, _ = self._make_binary_sensor()
        assert entity.entity_id == f"binary_sensor.{DOMAIN}_{SK.EVU_UNLOCKED}"

    def test_handle_coordinator_update_on(self):
        entity, _ = self._make_binary_sensor(value=1)
        data = make_coordinator_data(calculations={"ID_WEB_FreigabKuehl": 1})
        entity._handle_coordinator_update(data)
        assert entity._attr_is_on is True

    def test_handle_coordinator_update_off(self):
        entity, _ = self._make_binary_sensor(value=0)
        data = make_coordinator_data(calculations={"ID_WEB_FreigabKuehl": 0})
        entity._handle_coordinator_update(data)
        assert entity._attr_is_on is False

    def test_handle_coordinator_update_none_data(self):
        entity, coord = self._make_binary_sensor()
        coord.data = None
        entity._handle_coordinator_update(None)


# ===========================================================================
# async_setup_entry — number
# ===========================================================================


class TestNumberAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_skips_when_no_update_success(self):
        from custom_components.luxtronik2.number import async_setup_entry

        coord = _mock_coordinator(last_update_success=False)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()

        await async_setup_entry(MagicMock(), entry, add)
        add.assert_not_called()

    @pytest.mark.asyncio
    async def test_adds_entities(self):
        from custom_components.luxtronik2.number import async_setup_entry

        data = make_coordinator_data(
            parameters={
                "ID_Einst_BWS_akt": 50.0,
                "ID_Einst_HzMKE1_akt": 0,
                "ID_Einst_Kuhl_Frei_akt": 0,
                "ID_Sollwert_KuCft1_akt": 20.0,
                "ID_Einst_Heizgrenze_akt": 20.0,
            }
        )
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()

        with patch("homeassistant.helpers.frame.report_usage"):
            await async_setup_entry(MagicMock(), entry, add)

        add.assert_called_once()
        entities = add.call_args[0][0]
        assert len(entities) > 0


# ===========================================================================
# LuxtronikNumberEntity
# ===========================================================================


class TestLuxtronikNumberEntity:
    def _make_number(self, param_key="ID_Einst_BWS_akt", value=50.0, factor=None):
        from custom_components.luxtronik2.number import LuxtronikNumberEntity

        data = make_coordinator_data(parameters={param_key: value})
        coord = _mock_coordinator(data)
        desc = LuxtronikNumberDescription(
            key=SK.DHW_TARGET_TEMPERATURE,
            luxtronik_key=LP.P0002_DHW_TARGET_TEMPERATURE,
            device_key=DeviceKey.domestic_water,
            factor=factor,
        )
        entry = _mock_entry()

        with patch("homeassistant.helpers.frame.report_usage"):
            entity = LuxtronikNumberEntity(
                MagicMock(), entry, coord, desc, DeviceKey.domestic_water
            )
        _patch_entity_hass(entity)
        return entity, coord

    def test_entity_id(self):
        entity, _ = self._make_number()
        assert entity.entity_id == f"number.{DOMAIN}_{SK.DHW_TARGET_TEMPERATURE}"

    def test_handle_coordinator_update_float(self):
        entity, _ = self._make_number(value=50.0)
        data = make_coordinator_data(parameters={"ID_Einst_BWS_akt": 50.0})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 50.0

    def test_handle_coordinator_update_with_factor(self):
        entity, _ = self._make_number(value=500, factor=0.1)
        data = make_coordinator_data(parameters={"ID_Einst_BWS_akt": 500})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 50.0

    def test_handle_coordinator_update_none(self):
        entity, _ = self._make_number()
        data = make_coordinator_data(parameters={})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None

    def test_handle_coordinator_update_none_data(self):
        entity, coord = self._make_number()
        coord.data = None
        entity._handle_coordinator_update(None)

    def test_handle_coordinator_update_non_numeric(self):
        entity, _ = self._make_number()
        data = make_coordinator_data(parameters={"ID_Einst_BWS_akt": "some_string"})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == "some_string"

    @pytest.mark.asyncio
    async def test_set_native_value(self):
        entity, _ = self._make_number()
        entity._debouncer = MagicMock()
        entity._debouncer.async_call = AsyncMock()
        await entity.async_set_native_value(55.0)
        assert entity._pending_value == 55.0
        entity._debouncer.async_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_set_native_value_with_factor(self):
        entity, coord = self._make_number(factor=0.1)
        entity._pending_value = 50.0
        await entity._async_set_native_value()
        coord.async_write.assert_called_once()
        # value / factor = 50.0 / 0.1 = 500
        call_args = coord.async_write.call_args
        assert call_args[0][1] == 500

    @pytest.mark.asyncio
    async def test_async_set_native_value_no_pending(self):
        entity, coord = self._make_number()
        entity._pending_value = None
        await entity._async_set_native_value()
        coord.async_write.assert_not_called()


# ===========================================================================
# async_setup_entry — date
# ===========================================================================


class TestDateAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_skips_when_no_update_success(self):
        from custom_components.luxtronik2.date import async_setup_entry

        coord = _mock_coordinator(last_update_success=False)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()

        await async_setup_entry(MagicMock(), entry, add)
        add.assert_not_called()


# ===========================================================================
# LuxtronikDateEntity
# ===========================================================================


class TestLuxtronikDateEntity:
    def _make_date_entity(self, param_key="ID_SU_FstdBw", value=1):
        from custom_components.luxtronik2.date import LuxtronikDateEntity

        data = make_coordinator_data(parameters={param_key: value})
        coord = _mock_coordinator(data)
        desc = LuxtronikDateEntityDescription(
            key=SK.AWAY_DHW_STARTDATE,
            luxtronik_key=LP.P0732_AWAY_DHW_STARTDATE,
            device_key=DeviceKey.domestic_water,
        )
        entry = _mock_entry()

        with patch("homeassistant.helpers.frame.report_usage"):
            entity = LuxtronikDateEntity(
                MagicMock(), entry, coord, desc, DeviceKey.domestic_water
            )
        _patch_entity_hass(entity)
        return entity, coord

    def test_entity_id(self):
        entity, _ = self._make_date_entity()
        assert entity.entity_id == f"date.{DOMAIN}_{SK.AWAY_DHW_STARTDATE}"

    def test_handle_coordinator_update_timestamp(self):
        # Use a known timestamp
        ts = datetime(2025, 1, 15, 12, 0, 0).timestamp()
        entity, _ = self._make_date_entity(value=ts)
        data = make_coordinator_data(parameters={"ID_SU_FstdBw": ts})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == date(2025, 1, 15)

    def test_handle_coordinator_update_timestamp_is_utc_anchored(self):
        """M8: date() must come from a UTC-interpreted timestamp, independent
        of the host's local timezone (previously used naive fromtimestamp())."""
        ts = datetime(2025, 1, 15, 0, 0, 0, tzinfo=UTC).timestamp()
        entity, _ = self._make_date_entity(value=ts)
        data = make_coordinator_data(parameters={"ID_SU_FstdBw": ts})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == date(2025, 1, 15)

    def test_handle_coordinator_update_date_object(self):
        d = date(2025, 6, 15)
        entity, _ = self._make_date_entity()
        data = make_coordinator_data(parameters={"ID_SU_FstdBw": d})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == d

    def test_handle_coordinator_update_none(self):
        entity, _ = self._make_date_entity()
        data = make_coordinator_data(parameters={})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None

    def test_handle_coordinator_update_string_value(self):
        entity, _ = self._make_date_entity()
        data = make_coordinator_data(parameters={"ID_SU_FstdBw": "not-a-date"})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None

    def test_handle_coordinator_update_invalid_timestamp(self):
        entity, _ = self._make_date_entity()
        data = make_coordinator_data(parameters={"ID_SU_FstdBw": -999999999999})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None

    def test_handle_coordinator_update_none_data(self):
        entity, coord = self._make_date_entity()
        coord.data = None
        entity._handle_coordinator_update(None)

    @pytest.mark.asyncio
    async def test_set_value(self):
        entity, coord = self._make_date_entity()
        d = date(2025, 7, 1)
        await entity.async_set_value(d)
        assert entity._attr_native_value == d
        coord.async_write.assert_called_once()


# ===========================================================================
# async_setup_entry — sensor
# ===========================================================================


class TestSensorAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_skips_when_no_update_success(self):
        from custom_components.luxtronik2.sensor import async_setup_entry

        coord = _mock_coordinator(last_update_success=False)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()

        await async_setup_entry(MagicMock(), entry, add)
        add.assert_not_called()

    @pytest.mark.asyncio
    async def test_adds_entities(self):
        from custom_components.luxtronik2.sensor import async_setup_entry

        data = make_coordinator_data(
            calculations={
                "ID_WEB_Temperatur_TRL": 35.0,
                "ID_WEB_Temperatur_TA": 10.0,
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            }
        )
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()

        with patch("homeassistant.helpers.frame.report_usage"):
            await async_setup_entry(MagicMock(), entry, add)

        assert add.called


# ===========================================================================
# LuxtronikSensorEntity
# ===========================================================================


class TestLuxtronikSensorEntity:
    def _make_sensor(self, calc_key="ID_WEB_Temperatur_TRL", value=35.0, **desc_kw):
        from custom_components.luxtronik2.sensor import LuxtronikSensorEntity

        data = make_coordinator_data(calculations={calc_key: value})
        coord = _mock_coordinator(data)
        desc = LuxtronikSensorDescription(
            key=SK.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heating,
            **desc_kw,
        )
        entry = _mock_entry()

        with patch("homeassistant.helpers.frame.report_usage"):
            entity = LuxtronikSensorEntity(
                MagicMock(), entry, coord, desc, DeviceKey.heating
            )
        _patch_entity_hass(entity)
        return entity, coord

    def test_entity_id(self):
        entity, _ = self._make_sensor()
        assert entity.entity_id == f"sensor.{DOMAIN}_{SK.FLOW_OUT_TEMPERATURE}"
        assert entity._attr_unique_id == entity.entity_id

    def test_handle_coordinator_update_float(self):
        entity, _ = self._make_sensor(value=35.5)
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 35.5})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 35.5

    def test_handle_coordinator_update_with_factor(self):
        entity, _ = self._make_sensor(value=350, factor=0.1)
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 350})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == pytest.approx(35.0)

    def test_handle_coordinator_update_with_precision(self):
        entity, _ = self._make_sensor(value=35.567, native_precision=1)
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 35.567})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 35.6

    def test_handle_coordinator_update_none_value(self):
        entity, _ = self._make_sensor()
        data = make_coordinator_data(calculations={})
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None

    def test_handle_coordinator_update_string_value(self):
        entity, _ = self._make_sensor(value="some_status")
        data = make_coordinator_data(
            calculations={"ID_WEB_Temperatur_TRL": "some_status"}
        )
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == "some_status"

    def test_handle_coordinator_update_none_data(self):
        entity, coord = self._make_sensor()
        coord.data = None
        entity._handle_coordinator_update(None)


# ===========================================================================
# LuxtronikStatusSensorEntity — SmartGrid
# ===========================================================================


class TestSmartGridSensor:
    def _make_smart_grid(self, evu=0, evu2=0, sg_enabled=1):
        from custom_components.luxtronik2.sensor import LuxtronikStatusSensorEntity

        data = make_coordinator_data(
            calculations={
                "ID_WEB_EVUin": evu,
                "ID_WEB_HZIO_EVU2": evu2,
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            },
            parameters={
                "ID_Einst_SmartGrid": sg_enabled,
            },
        )
        coord = _mock_coordinator(data)
        desc = LuxtronikSensorDescription(
            key=SK.SMART_GRID_STATUS,
            luxtronik_key=LC.UNSET,
            device_key=DeviceKey.heatpump,
        )
        entry = _mock_entry()

        with patch("homeassistant.helpers.frame.report_usage"):
            entity = LuxtronikStatusSensorEntity(
                MagicMock(), entry, coord, desc, DeviceKey.heatpump
            )
        _patch_entity_hass(entity)
        return entity, coord

    def test_smart_grid_locked(self):
        entity, _ = self._make_smart_grid(evu=1, evu2=0)
        entity._handle_coordinator_update()
        from custom_components.luxtronik2.const import LuxSmartGridStatus

        assert entity._attr_native_value == LuxSmartGridStatus.locked

    def test_smart_grid_reduced(self):
        entity, _ = self._make_smart_grid(evu=0, evu2=0)
        entity._handle_coordinator_update()
        from custom_components.luxtronik2.const import LuxSmartGridStatus

        assert entity._attr_native_value == LuxSmartGridStatus.reduced

    def test_smart_grid_normal(self):
        entity, _ = self._make_smart_grid(evu=0, evu2=1)
        entity._handle_coordinator_update()
        from custom_components.luxtronik2.const import LuxSmartGridStatus

        assert entity._attr_native_value == LuxSmartGridStatus.normal

    def test_smart_grid_increased(self):
        entity, _ = self._make_smart_grid(evu=1, evu2=1)
        entity._handle_coordinator_update()
        from custom_components.luxtronik2.const import LuxSmartGridStatus

        assert entity._attr_native_value == LuxSmartGridStatus.increased

    def test_smart_grid_disabled(self):
        entity, _ = self._make_smart_grid(sg_enabled=0)
        entity._handle_coordinator_update()
        assert entity.available is False
        assert entity._attr_native_value is None


# ===========================================================================
# async_setup_entry — select
# ===========================================================================


class TestSelectAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_skips_when_no_update_success(self):
        from custom_components.luxtronik2.select import async_setup_entry

        coord = _mock_coordinator(last_update_success=False)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()

        await async_setup_entry(MagicMock(), entry, add)
        add.assert_not_called()

    @pytest.mark.asyncio
    async def test_adds_entities(self):
        from custom_components.luxtronik2.select import async_setup_entry

        data = make_coordinator_data(
            parameters={
                "ID_Einst_BwTDI_akt_MO": 1,
                "ID_Einst_BwTDI_akt_DI": 0,
                "ID_Einst_BwTDI_akt_MI": 0,
                "ID_Einst_BwTDI_akt_DO": 0,
                "ID_Einst_BwTDI_akt_FR": 0,
                "ID_Einst_BwTDI_akt_SA": 0,
                "ID_Einst_BwTDI_akt_SO": 0,
                "ID_Einst_BwTDI_akt_AL": 0,
                "ID_Ba_Hz_akt": "Automatic",
                "ID_Ba_Bw_akt": "Automatic",
            }
        )
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()

        with patch("homeassistant.helpers.frame.report_usage"):
            await async_setup_entry(MagicMock(), entry, add)

        assert add.called
        entities = add.call_args[0][0]
        assert len(entities) > 0


# ===========================================================================
# LuxtronikThermalDesinfectionDaySelector
# ===========================================================================


class TestThermalDesinfectionDaySelector:
    def _make_tdi_selector(self, day_values=None):
        from custom_components.luxtronik2.select import (
            LuxtronikThermalDesinfectionDaySelector,
        )

        day_params = {
            "ID_Einst_BwTDI_akt_MO": 0,
            "ID_Einst_BwTDI_akt_DI": 0,
            "ID_Einst_BwTDI_akt_MI": 0,
            "ID_Einst_BwTDI_akt_DO": 0,
            "ID_Einst_BwTDI_akt_FR": 0,
            "ID_Einst_BwTDI_akt_SA": 0,
            "ID_Einst_BwTDI_akt_SO": 0,
            "ID_Einst_BwTDI_akt_AL": 0,
        }
        if day_values:
            day_params.update(day_values)

        data = make_coordinator_data(parameters=day_params)
        coord = _mock_coordinator(data)
        from custom_components.luxtronik2.const import LuxDaySelectorParameter

        desc = LuxtronikSelectEntityDescription(
            key=SK.THERMAL_DESINFECTION_DAY,
            device_key=DeviceKey.domestic_water,
            luxtronik_key=LuxDaySelectorParameter.MONDAY,
        )
        entry = _mock_entry()

        with patch("homeassistant.helpers.frame.report_usage"):
            entity = LuxtronikThermalDesinfectionDaySelector(
                entry, coord, desc, DeviceKey.domestic_water
            )
        _patch_entity_hass(entity)
        return entity, coord

    def test_entity_id(self):
        entity, _ = self._make_tdi_selector()
        assert "thermal_desinfection_day" in entity.entity_id

    def test_handle_coordinator_update_monday(self):
        entity, _ = self._make_tdi_selector({"ID_Einst_BwTDI_akt_MO": 1})
        data = make_coordinator_data(
            parameters={
                "ID_Einst_BwTDI_akt_MO": 1,
                "ID_Einst_BwTDI_akt_DI": 0,
                "ID_Einst_BwTDI_akt_MI": 0,
                "ID_Einst_BwTDI_akt_DO": 0,
                "ID_Einst_BwTDI_akt_FR": 0,
                "ID_Einst_BwTDI_akt_SA": 0,
                "ID_Einst_BwTDI_akt_SO": 0,
                "ID_Einst_BwTDI_akt_AL": 0,
            }
        )
        entity._handle_coordinator_update(data)
        assert entity._attr_current_option == "monday"

    def test_handle_coordinator_update_none_selected(self):
        entity, _ = self._make_tdi_selector()
        data = make_coordinator_data(
            parameters={
                "ID_Einst_BwTDI_akt_MO": 0,
                "ID_Einst_BwTDI_akt_DI": 0,
                "ID_Einst_BwTDI_akt_MI": 0,
                "ID_Einst_BwTDI_akt_DO": 0,
                "ID_Einst_BwTDI_akt_FR": 0,
                "ID_Einst_BwTDI_akt_SA": 0,
                "ID_Einst_BwTDI_akt_SO": 0,
                "ID_Einst_BwTDI_akt_AL": 0,
            }
        )
        entity._handle_coordinator_update(data)
        assert entity._attr_current_option == "none"

    def test_handle_coordinator_update_none_data(self):
        entity, coord = self._make_tdi_selector()
        coord.data = None
        entity._handle_coordinator_update(None)

    @pytest.mark.asyncio
    async def test_select_option(self):
        entity, coord = self._make_tdi_selector()
        # async_write returns updated data with Wednesday=1
        updated_data = make_coordinator_data(
            parameters={
                "ID_Einst_BwTDI_akt_MO": 0,
                "ID_Einst_BwTDI_akt_DI": 0,
                "ID_Einst_BwTDI_akt_MI": 1,
                "ID_Einst_BwTDI_akt_DO": 0,
                "ID_Einst_BwTDI_akt_FR": 0,
                "ID_Einst_BwTDI_akt_SA": 0,
                "ID_Einst_BwTDI_akt_SO": 0,
                "ID_Einst_BwTDI_akt_AL": 0,
            }
        )
        coord.async_write = AsyncMock(return_value=updated_data)
        await entity.async_select_option("wednesday")
        assert entity._attr_current_option == "wednesday"


# ===========================================================================
# LuxtronikModeSelector
# ===========================================================================


class TestLuxtronikModeSelector:
    def _make_mode_selector(self, param_key="ID_Ba_Hz_akt", value="Automatic"):
        from custom_components.luxtronik2.select import LuxtronikModeSelector

        data = make_coordinator_data(parameters={param_key: value})
        coord = _mock_coordinator(data)
        desc = LuxtronikSelectEntityDescription(
            key=SK.HEATING_MODE_SELECTOR,
            device_key=DeviceKey.heating,
            luxtronik_key=LP.P0003_MODE_HEATING,
        )
        entry = _mock_entry()
        options = [str(x.value) for x in LuxMode]

        with patch("homeassistant.helpers.frame.report_usage"):
            entity = LuxtronikModeSelector(
                entry=entry,
                coordinator=coord,
                description=desc,
                device_info_ident=DeviceKey.heating,
                lux_parameter=LP.P0003_MODE_HEATING,
                options=options,
            )
        _patch_entity_hass(entity)
        return entity, coord

    def test_entity_id(self):
        entity, _ = self._make_mode_selector()
        assert SK.HEATING_MODE_SELECTOR in entity.entity_id

    def test_options_are_normalized(self):
        entity, _ = self._make_mode_selector()
        assert entity._attr_options == [
            "off",
            "automatic",
            "second_heatsource",
            "party",
            "holidays",
        ]

    def test_handle_coordinator_update_valid(self):
        entity, _ = self._make_mode_selector(value="Automatic")
        data = make_coordinator_data(parameters={"ID_Ba_Hz_akt": "Automatic"})
        entity._handle_coordinator_update(data)
        assert entity._attr_current_option == "automatic"

    def test_handle_coordinator_update_invalid_option(self):
        entity, _ = self._make_mode_selector(value="InvalidMode")
        data = make_coordinator_data(parameters={"ID_Ba_Hz_akt": "InvalidMode"})
        entity._handle_coordinator_update(data)
        # Should not change current_option when value is not in options
        assert entity._attr_current_option is None

    def test_handle_coordinator_update_none_data(self):
        entity, coord = self._make_mode_selector()
        coord.data = None
        entity._handle_coordinator_update(None)

    @pytest.mark.asyncio
    async def test_select_valid_option(self):
        entity, coord = self._make_mode_selector()
        await entity.async_select_option("off")
        coord.async_write.assert_called_once_with("ID_Ba_Hz_akt", "Off")

    @pytest.mark.asyncio
    async def test_select_invalid_option(self):
        entity, coord = self._make_mode_selector()
        await entity.async_select_option("NotAMode")
        coord.async_write.assert_not_called()


# ===========================================================================
# async_setup_entry — water_heater
# ===========================================================================


class TestWaterHeaterAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_skips_when_no_update_success(self):
        from custom_components.luxtronik2.water_heater import async_setup_entry

        coord = _mock_coordinator(last_update_success=False)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()

        await async_setup_entry(MagicMock(), entry, add)
        add.assert_not_called()

    @pytest.mark.asyncio
    async def test_adds_entities(self):
        from custom_components.luxtronik2.water_heater import async_setup_entry

        data = make_coordinator_data(
            parameters={
                "ID_Ba_Bw_akt": "Automatic",
                "ID_Einst_BWS_akt": 50.0,
            },
            calculations={
                "ID_WEB_Temperatur_TBW": 45.0,
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            },
        )
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()

        with patch("homeassistant.helpers.frame.report_usage"):
            await async_setup_entry(MagicMock(), entry, add)

        add.assert_called_once()
        entities = add.call_args[0][0]
        assert len(entities) > 0


# ===========================================================================
# LuxtronikWaterHeater
# ===========================================================================


class TestLuxtronikWaterHeater:
    def _make_water_heater(
        self,
        mode="Automatic",
        current_temp=45.0,
        target_temp=50.0,
        status="heating",
    ):
        from homeassistant.components.water_heater import WaterHeaterEntityFeature
        from homeassistant.const import UnitOfTemperature

        from custom_components.luxtronik2.water_heater import LuxtronikWaterHeater

        data = make_coordinator_data(
            parameters={
                "ID_Ba_Bw_akt": mode,
                "ID_Einst_BWS_akt": target_temp,
            },
            calculations={
                "ID_WEB_Temperatur_TBW": current_temp,
                "ID_WEB_WP_BZ_akt": status,
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            },
        )
        coord = _mock_coordinator(data)
        desc = LuxtronikWaterHeaterDescription(
            key=SK.DOMESTIC_WATER,
            luxtronik_key=LP.P0004_MODE_DHW,
            luxtronik_key_current_temperature=LC.C0017_DHW_TEMPERATURE,
            luxtronik_key_target_temperature=LP.P0002_DHW_TARGET_TEMPERATURE,
            luxtronik_key_current_action=LC.C0080_STATUS,
            luxtronik_action_heating=LuxOperationMode.domestic_water,
            temperature_unit=UnitOfTemperature.CELSIUS,
            operation_list=["off", "heat_pump", "electric", "performance"],
            supported_features=(
                WaterHeaterEntityFeature.OPERATION_MODE
                | WaterHeaterEntityFeature.TARGET_TEMPERATURE
                | WaterHeaterEntityFeature.AWAY_MODE
            ),
            device_key=DeviceKey.domestic_water,
        )
        entry = _mock_entry()

        with patch("homeassistant.helpers.frame.report_usage"):
            entity = LuxtronikWaterHeater(MagicMock(), entry, coord, desc)
        _patch_entity_hass(entity)
        return entity, coord

    def test_entity_id(self):
        entity, _ = self._make_water_heater()
        assert SK.DOMESTIC_WATER in entity.entity_id

    def test_handle_coordinator_update(self):
        entity, _ = self._make_water_heater(mode="Automatic")
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Bw_akt": "Automatic",
                "ID_Einst_BWS_akt": 50.0,
            },
            calculations={
                "ID_WEB_Temperatur_TBW": 45.0,
                "ID_WEB_WP_BZ_akt": "hot_water",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            },
        )
        entity._handle_coordinator_update(data)
        assert entity._attr_current_operation == "heat_pump"

    def test_handle_coordinator_update_off_mode(self):
        entity, _ = self._make_water_heater(mode="Off")
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Bw_akt": "Off",
                "ID_Einst_BWS_akt": 50.0,
            },
            calculations={
                "ID_WEB_Temperatur_TBW": 45.0,
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            },
        )
        entity._handle_coordinator_update(data)
        assert entity._attr_current_operation == "off"

    def test_handle_coordinator_update_holidays(self):
        entity, _ = self._make_water_heater(mode="Holidays")
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Bw_akt": "Holidays",
                "ID_Einst_BWS_akt": 50.0,
            },
            calculations={
                "ID_WEB_Temperatur_TBW": 45.0,
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            },
        )
        entity._handle_coordinator_update(data)
        assert entity._attr_is_away_mode_on is True

    def test_handle_coordinator_update_none_data(self):
        entity, coord = self._make_water_heater()
        coord.data = None
        entity._handle_coordinator_update(None)

    def test_hvac_action_heating(self):
        entity, _ = self._make_water_heater()
        entity._current_action = LuxOperationMode.domestic_water
        from homeassistant.components.climate.const import HVACAction

        assert entity.hvac_action == HVACAction.HEATING

    def test_hvac_action_off(self):
        entity, _ = self._make_water_heater()
        entity._current_action = "something_else"
        from homeassistant.components.climate.const import HVACAction

        assert entity.hvac_action == HVACAction.OFF

    @pytest.mark.asyncio
    async def test_set_operation_mode(self):
        entity, coord = self._make_water_heater()
        await entity.async_set_operation_mode("off")
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_temperature(self):
        entity, _ = self._make_water_heater()
        entity._debouncer_set_temp = MagicMock()
        entity._debouncer_set_temp.async_call = AsyncMock()
        await entity.async_set_temperature(temperature=55.0)
        assert entity._pending_temperature == 55.0
        entity._debouncer_set_temp.async_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_write_temperature(self):
        entity, coord = self._make_water_heater()
        entity._pending_temperature = 55.0
        await entity._async_write_temperature()
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_write_temperature_no_pending(self):
        entity, coord = self._make_water_heater()
        entity._pending_temperature = None
        await entity._async_write_temperature()
        coord.async_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_away_mode_on(self):
        entity, coord = self._make_water_heater()
        entity._attr_current_operation = "heat_pump"
        await entity.async_turn_away_mode_on()
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_turn_away_mode_off(self):
        entity, coord = self._make_water_heater()
        entity._last_operation_mode_before_away = "heat_pump"
        await entity.async_turn_away_mode_off()
        coord.async_write.assert_called()

    @pytest.mark.asyncio
    async def test_turn_away_mode_off_no_previous(self):
        entity, coord = self._make_water_heater()
        entity._last_operation_mode_before_away = None
        await entity.async_turn_away_mode_off()
        coord.async_write.assert_called()

    def test_max_temp_with_key(self):
        entity, _ = self._make_water_heater()
        # max_temp property reads from coordinator
        temp = entity.max_temp
        assert isinstance(temp, float)

    def test_max_temp_fallback(self):
        entity, _ = self._make_water_heater()

        with patch(
            "custom_components.luxtronik2.water_heater.key_exists",
            return_value=False,
        ):
            assert entity.max_temp == 60.0


# ===========================================================================
# async_setup_entry — climate
# ===========================================================================


class TestClimateAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_adds_entities(self):
        from custom_components.luxtronik2.climate import async_setup_entry

        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Automatic",
                "HEATING_TARGET_TEMP_ROOM_THERMOSTAT": 21.0,
                "ID_Einst_BA_Kuehl_akt": "Off",
                "ID_Einst_KuehlFreig_akt": 20.0,
            },
            calculations={
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
                "ID_WEB_RBE_RT_Ist": 22.0,
                "ID_WEB_RBE_RT_Soll": 21.0,
            },
        )
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        entry.runtime_data = coord
        entry.options = {}
        add = MagicMock()

        with patch("homeassistant.helpers.frame.report_usage"):
            await async_setup_entry(MagicMock(), entry, add)

        add.assert_called_once()
        entities = add.call_args[0][0]
        assert len(entities) > 0


# ===========================================================================
# LuxtronikThermostat
# ===========================================================================


class TestLuxtronikThermostat:
    def _make_thermostat(self, mode="Automatic", status="heating", target=21.0):
        from custom_components.luxtronik2.climate import LuxtronikThermostat
        from custom_components.luxtronik2.const import (
            LuxCalculation,
            LuxParameter,
        )

        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": mode,
                "HEATING_TARGET_TEMP_ROOM_THERMOSTAT": target,
            },
            calculations={
                "ID_WEB_WP_BZ_akt": status,
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
                "ID_WEB_RBE_RT_Ist": 22.0,
                "ID_WEB_RBE_RT_Soll": target,
            },
        )
        coord = _mock_coordinator(data)
        desc = LuxtronikClimateDescription(
            key=SK.HEATING,
            hvac_modes=[HVACMode.HEAT, HVACMode.OFF],
            hvac_mode_mapping={
                LuxMode.off: HVACMode.OFF.value,
                LuxMode.automatic: HVACMode.HEAT.value,
                LuxMode.second_heatsource: HVACMode.HEAT.value,
                LuxMode.party: HVACMode.HEAT.value,
                LuxMode.holidays: HVACMode.HEAT.value,
            },
            hvac_action_mapping={
                LuxOperationMode.heating: HVACAction.HEATING.value,
                LuxOperationMode.domestic_water: HVACAction.IDLE.value,
                LuxOperationMode.swimming_pool_solar: "unknown",
                LuxOperationMode.evu: HVACAction.IDLE.value,
                LuxOperationMode.defrost: HVACAction.IDLE.value,
                LuxOperationMode.no_request: HVACAction.IDLE.value,
                LuxOperationMode.heating_external_source: HVACAction.HEATING.value,
                LuxOperationMode.cooling: HVACAction.IDLE.value,
            },
            preset_modes=[PRESET_NONE, PRESET_AWAY, PRESET_BOOST],
            supported_features=(
                ClimateEntityFeature.PRESET_MODE
                | ClimateEntityFeature.TURN_OFF
                | ClimateEntityFeature.TURN_ON
                | ClimateEntityFeature.TARGET_TEMPERATURE
            ),
            luxtronik_key=LuxParameter.P0003_MODE_HEATING,
            luxtronik_key_target_temperature=LuxParameter.P1148_HEATING_TARGET_TEMP_ROOM_THERMOSTAT,
            luxtronik_key_current_action=LuxCalculation.C0080_STATUS,
            luxtronik_action_active=LuxOperationMode.heating,
            temperature_unit=UnitOfTemperature.CELSIUS,
            translation_key_name="heating_controller",
            device_key=DeviceKey.heating,
        )
        entry = _mock_entry()
        entry.options = {}

        with patch("homeassistant.helpers.frame.report_usage"):
            entity = LuxtronikThermostat(MagicMock(), entry, coord, desc)
        _patch_entity_hass(entity)
        return entity, coord

    def test_entity_id(self):
        entity, _ = self._make_thermostat()
        assert SK.HEATING in entity.entity_id

    def test_handle_coordinator_update_heating(self):
        entity, _ = self._make_thermostat(mode="Automatic", status="heating")
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Automatic",
                "HEATING_TARGET_TEMP_ROOM_THERMOSTAT": 21.0,
            },
            calculations={
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
                "ID_WEB_RBE_RT_Ist": 22.0,
                "ID_WEB_RBE_RT_Soll": 21.0,
            },
        )
        entity._handle_coordinator_update(data)
        assert entity._attr_hvac_mode == HVACMode.HEAT.value
        assert entity._attr_hvac_action == HVACAction.HEATING.value

    def test_handle_coordinator_update_off(self):
        entity, _ = self._make_thermostat(mode="Off", status="no_request")
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Off",
                "HEATING_TARGET_TEMP_ROOM_THERMOSTAT": 21.0,
            },
            calculations={
                "ID_WEB_WP_BZ_akt": "no_request",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
                "ID_WEB_RBE_RT_Ist": 22.0,
                "ID_WEB_RBE_RT_Soll": 21.0,
            },
        )
        entity._handle_coordinator_update(data)
        assert entity._attr_hvac_mode == HVACMode.OFF.value

    def test_handle_coordinator_update_none_data(self):
        entity, coord = self._make_thermostat()
        coord.data = None
        entity._handle_coordinator_update(None)

    def test_handle_coordinator_update_preset_away(self):
        entity, _ = self._make_thermostat(mode="Holidays")
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Holidays",
                "HEATING_TARGET_TEMP_ROOM_THERMOSTAT": 21.0,
            },
            calculations={
                "ID_WEB_WP_BZ_akt": "no_request",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
                "ID_WEB_RBE_RT_Ist": 22.0,
                "ID_WEB_RBE_RT_Soll": 21.0,
            },
        )
        entity._handle_coordinator_update(data)
        assert entity._attr_preset_mode == PRESET_AWAY

    @pytest.mark.asyncio
    async def test_set_temperature(self):
        entity, _ = self._make_thermostat()
        entity._debouncer_set_temp = MagicMock()
        entity._debouncer_set_temp.async_call = AsyncMock()
        await entity.async_set_temperature(temperature=22.0)
        assert entity._pending_temperature == 22.0
        entity._debouncer_set_temp.async_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_write_temperature(self):
        entity, coord = self._make_thermostat()
        entity._pending_temperature = 22.0
        await entity._async_write_temperature()
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_write_temperature_no_pending(self):
        entity, coord = self._make_thermostat()
        entity._pending_temperature = None
        await entity._async_write_temperature()
        coord.async_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_hvac_mode_off(self):
        entity, coord = self._make_thermostat()
        await entity.async_set_hvac_mode(HVACMode.OFF)
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_hvac_mode_heat(self):
        entity, coord = self._make_thermostat()
        await entity.async_set_hvac_mode(HVACMode.HEAT)
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_turn_off(self):
        entity, coord = self._make_thermostat()
        await entity.async_turn_off()
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_turn_on(self):
        entity, coord = self._make_thermostat()
        await entity.async_turn_on()
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_preset_away(self):
        entity, coord = self._make_thermostat()
        await entity.async_set_preset_mode(PRESET_AWAY)
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_preset_none_restores_mode(self):
        entity, coord = self._make_thermostat()
        entity._last_hvac_mode_before_preset = LuxMode.automatic
        await entity.async_set_preset_mode(PRESET_NONE)
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_preset_none_defaults_to_off(self):
        entity, coord = self._make_thermostat()
        entity._last_hvac_mode_before_preset = None
        await entity.async_set_preset_mode(PRESET_NONE)
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_preset_boost(self):
        entity, coord = self._make_thermostat()
        await entity.async_set_preset_mode(PRESET_BOOST)
        coord.async_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_preset_comfort(self):
        entity, coord = self._make_thermostat()
        await entity.async_set_preset_mode(PRESET_COMFORT)
        coord.async_write.assert_called_once()

    def test_extra_restore_state_data(self):
        entity, _ = self._make_thermostat()
        data = entity.extra_restore_state_data
        assert hasattr(data, "as_dict")
        d = data.as_dict()
        assert "_attr_target_temperature" in d

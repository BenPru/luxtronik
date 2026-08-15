"""Tests for sensor entity classes (LuxtronikSensorEntity, StatusSensor, IndexSensor)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TIMEOUT,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfVolumeFlowRate,
)
from luxtronik.calculations import Calculations

from conftest import make_coordinator_data
from custom_components.luxtronik2.binary_sensor import LuxtronikBinarySensorEntity
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxCalculation as LC,
    LuxOperationMode,
    LuxSmartGridStatus,
    LuxStatus1Option,
    LuxStatus3Option,
    LuxVisibility,
    SensorKey,
)
from custom_components.luxtronik2.lux_overrides import parameters_to_add_update
from custom_components.luxtronik2.model import (
    LuxtronikBinarySensorEntityDescription,
    LuxtronikSensorDescription,
)
from custom_components.luxtronik2.sensor import (
    LuxtronikIndexSensor,
    LuxtronikSensorEntity,
    LuxtronikStatusSensorEntity,
)
from custom_components.luxtronik2.sensor_entities_predefined import SENSORS

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


def _mock_coordinator(data=None, *, last_update_success=True):
    if data is None:
        data = make_coordinator_data()
    coord = MagicMock()
    coord.data = data
    coord.last_update_success = last_update_success
    coord.entity_active.return_value = True
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    return coord


def _patch_entity(entity):
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()


# ===========================================================================
# LuxtronikSensorEntity._handle_coordinator_update
# ===========================================================================


def _make_sensor(description=None, data=None):
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


class TestSensorHandleCoordinatorUpdate:
    def test_none_data_returns_early(self):
        entity = _make_sensor()
        entity.coordinator.data = None
        entity._handle_coordinator_update(None)
        entity.async_write_ha_state.assert_not_called()

    def test_value_none_sets_none(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": None})
        entity = _make_sensor(data=data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value is None

    def test_numeric_value_with_factor(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 30.0})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            factor=0.1,
            native_precision=1,
        )
        entity = _make_sensor(desc, data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 3.0

    def test_numeric_value_without_factor(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 25.5})
        entity = _make_sensor(data=data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 25.5

    def test_string_value_passthrough(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": "some_str"})
        entity = _make_sensor(data=data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == "some_str"

    def test_error_reason_passthrough(self):
        data = make_coordinator_data(calculations={"ID_WEB_ERROR_Nr0": 42})
        desc = LuxtronikSensorDescription(
            key=SensorKey.ERROR_REASON,
            luxtronik_key=LC.C0100_ERROR_REASON,
            device_key=DeviceKey.heatpump,
        )
        entity = _make_sensor(desc, data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == 42


# ===========================================================================
# LuxtronikStatusSensorEntity._handle_coordinator_update
# ===========================================================================


def _make_status_sensor(data=None, description=None):
    hass = MagicMock()
    entry = _mock_entry()
    if data is None:
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Automatic",
                "ID_Ba_Bw_akt": "Automatic",
            },
            calculations={
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
                "ID_WEB_HauptMenuStatus_Zeile1": "heatpump_running",
                "ID_WEB_HauptMenuStatus_Zeile3": "heating",
                "ID_WEB_ZUPout": 0,
            },
        )
    coord = _mock_coordinator(data)
    if description is None:
        description = LuxtronikSensorDescription(
            key=SensorKey.STATUS,
            luxtronik_key=LC.C0080_STATUS,
            device_key=DeviceKey.heatpump,
        )
    entity = LuxtronikStatusSensorEntity(
        hass, entry, coord, description, DeviceKey.heatpump
    )
    _patch_entity(entity)
    entity._get_entity_translations = MagicMock(return_value={})
    return entity


class TestStatusSensorUpdate:
    def test_normal_status_update(self):
        entity = _make_status_sensor()
        entity._handle_coordinator_update()
        entity.async_write_ha_state.assert_called()

    def test_workaround_pump_forerun_no_request(self):
        """When sl1 is pump_forerun and sl3 is no_request, override to no_request."""
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Automatic",
                "ID_Ba_Bw_akt": "Automatic",
            },
            calculations={
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
                "ID_WEB_HauptMenuStatus_Zeile1": LuxStatus1Option.pump_forerun,
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.no_request,
                "ID_WEB_ZUPout": 0,
            },
        )
        entity = _make_status_sensor(data)
        entity._last_state = "heating"
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == LuxOperationMode.no_request

    def test_workaround_thermal_desinfection(self):
        """Thermal desinfection maps to domestic_water."""
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Automatic",
                "ID_Ba_Bw_akt": "Automatic",
            },
            calculations={
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
                "ID_WEB_HauptMenuStatus_Zeile1": "heatpump_running",
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.thermal_desinfection,
                "ID_WEB_ZUPout": 0,
            },
        )
        entity = _make_status_sensor(data)
        entity._last_state = "heating"
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == LuxOperationMode.domestic_water

    def test_workaround_second_heat_source_domestic_water(self):
        """When sl3=no_request, AddHeat and DHW_recirculation → domestic_water."""
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Automatic",
                "ID_Ba_Bw_akt": "Automatic",
            },
            calculations={
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 1,
                "ID_WEB_HauptMenuStatus_Zeile1": "heatpump_running",
                "ID_WEB_HauptMenuStatus_Zeile3": LuxStatus3Option.no_request,
                "ID_WEB_ZUPout": 0,
                "ID_WEB_BUPout": 1,
            },
        )
        entity = _make_status_sensor(data)
        entity._last_state = "heating"
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == LuxOperationMode.domestic_water


# ===========================================================================
# SmartGrid status
# ===========================================================================


class TestSmartGridStatus:
    def _make_smartgrid_sensor(self, evu=0, evu2=0, smartgrid_enabled=1):
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Automatic",
                "ID_Ba_Bw_akt": "Automatic",
                "ID_Einst_SmartGrid": smartgrid_enabled,
            },
            calculations={
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
                "ID_WEB_EVUin": evu,
                "ID_WEB_HZIO_EVU2": evu2,
                "ID_WEB_HauptMenuStatus_Zeile1": "heatpump_running",
                "ID_WEB_HauptMenuStatus_Zeile3": "heating",
                "ID_WEB_ZUPout": 0,
            },
        )
        desc = LuxtronikSensorDescription(
            key=SensorKey.SMART_GRID_STATUS,
            luxtronik_key=LC.UNSET,
            device_key=DeviceKey.heatpump,
        )
        entity = _make_status_sensor(data, desc)
        return entity

    def test_smartgrid_disabled(self):
        entity = self._make_smartgrid_sensor(smartgrid_enabled=0)
        entity._handle_coordinator_update()
        assert entity.available is False
        assert entity._attr_native_value is None

    def test_smartgrid_enabled_is_available(self):
        entity = self._make_smartgrid_sensor()
        entity._handle_coordinator_update()
        assert entity.available is True

    def test_smartgrid_enabled_but_coordinator_update_failed(self):
        entity = self._make_smartgrid_sensor()
        entity._handle_coordinator_update()
        entity.coordinator.last_update_success = False
        assert entity.available is False

    def test_other_status_sensor_available_tracks_coordinator_only(self):
        entity = _make_status_sensor()
        entity._handle_coordinator_update()
        entity.coordinator.last_update_success = True
        assert entity.available is True
        entity.coordinator.last_update_success = False
        assert entity.available is False

    def test_smartgrid_locked(self):
        entity = self._make_smartgrid_sensor(evu=1, evu2=0)
        entity._handle_coordinator_update()
        assert entity._attr_native_value == LuxSmartGridStatus.locked

    def test_smartgrid_reduced(self):
        entity = self._make_smartgrid_sensor(evu=0, evu2=0)
        entity._handle_coordinator_update()
        assert entity._attr_native_value == LuxSmartGridStatus.reduced

    def test_smartgrid_normal(self):
        entity = self._make_smartgrid_sensor(evu=0, evu2=1)
        entity._handle_coordinator_update()
        assert entity._attr_native_value == LuxSmartGridStatus.normal

    def test_smartgrid_increased(self):
        entity = self._make_smartgrid_sensor(evu=1, evu2=1)
        entity._handle_coordinator_update()
        assert entity._attr_native_value == LuxSmartGridStatus.increased

    def test_smartgrid_icon_by_state(self):
        """SmartGrid sensor no longer sets _attr_icon — icons come from icons.json."""
        desc = LuxtronikSensorDescription(
            key=SensorKey.SMART_GRID_STATUS,
            luxtronik_key=LC.UNSET,
            device_key=DeviceKey.heatpump,
        )
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Automatic",
                "ID_Ba_Bw_akt": "Automatic",
                "ID_Einst_SmartGrid": 1,
            },
            calculations={
                "ID_WEB_WP_BZ_akt": "heating",
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
                "ID_WEB_EVUin": 0,
                "ID_WEB_HZIO_EVU2": 1,
                "ID_WEB_HauptMenuStatus_Zeile1": "heatpump_running",
                "ID_WEB_HauptMenuStatus_Zeile3": "heating",
                "ID_WEB_ZUPout": 0,
            },
        )
        entity = _make_status_sensor(data, desc)
        entity._handle_coordinator_update()
        assert entity._attr_native_value == LuxSmartGridStatus.normal
        # Icon is resolved from icons.json, not set in code
        assert not hasattr(entity, "_attr_icon") or entity._attr_icon is None


# ===========================================================================
# StatusSensor._build_status_text
# ===========================================================================


def _status_text_data(**calc_overrides):
    calculations = {
        "ID_WEB_HauptMenuStatus_Zeit": 4980,  # 1h 23m
        "ID_WEB_HauptMenuStatus_Zeile1": "heatpump_running",
        "ID_WEB_HauptMenuStatus_Zeile2": "heating",
    }
    calculations.update(calc_overrides)
    return make_coordinator_data(calculations=calculations)


class TestBuildStatusText:
    def test_returns_empty_when_status_time_none(self):
        data = _status_text_data(**{"ID_WEB_HauptMenuStatus_Zeit": None})
        entity = _make_status_sensor(data)
        result = entity._build_status_text()
        assert result == ""

    def test_returns_empty_when_line1_none(self):
        data = _status_text_data(**{"ID_WEB_HauptMenuStatus_Zeile1": None})
        entity = _make_status_sensor(data)
        result = entity._build_status_text()
        assert result == ""

    def test_returns_empty_when_line2_none(self):
        data = _status_text_data(**{"ID_WEB_HauptMenuStatus_Zeile2": None})
        entity = _make_status_sensor(data)
        result = entity._build_status_text()
        assert result == ""

    def test_returns_full_text_when_all_present(self):
        entity = _make_status_sensor(_status_text_data())
        entity._attr_native_value = LuxOperationMode.heating
        entity._get_entity_translations.return_value = {
            f"component.{DOMAIN}.entity.sensor.status_line_1.state.heatpump_running": "HP Running",
            f"component.{DOMAIN}.entity.sensor.status_line_2.state.heating": "Heating",
        }
        result = entity._build_status_text()
        assert "HP Running" in result
        assert "Heating" in result
        assert "1:23" in result

    def test_get_entity_translations_uses_public_helper(self):
        """_get_entity_translations must use the public translation helper, not
        the private platform.platform_data.platform_translations attribute."""
        entity = _make_status_sensor()
        entity._get_entity_translations = (
            LuxtronikStatusSensorEntity._get_entity_translations.__get__(entity)
        )
        entity.hass.config.language = "en"
        with patch(
            "custom_components.luxtronik2.sensor.async_get_cached_translations"
        ) as mock_get_translations:
            mock_get_translations.return_value = {"some.key": "value"}
            result = entity._get_entity_translations()
        mock_get_translations.assert_called_once_with(
            entity.hass, "en", "entity", DOMAIN
        )
        assert result == {"some.key": "value"}

    def test_reflects_sibling_entity_renames(self):
        """Status text is unaffected by the sibling sensor entities being renamed."""
        entity = _make_status_sensor(_status_text_data())
        entity._get_entity_translations.return_value = {
            f"component.{DOMAIN}.entity.sensor.status_line_1.state.heatpump_running": "HP Running",
            f"component.{DOMAIN}.entity.sensor.status_line_2.state.heating": "Heating",
        }
        result = entity._build_status_text()
        assert "HP Running" in result
        assert "Heating" in result
        entity.hass.states.get.assert_not_called()


# ===========================================================================
# LuxtronikIndexSensor
# ===========================================================================


class TestIndexSensor:
    def _make_index_sensor(self):
        from custom_components.luxtronik2.sensor_entities_predefined import (
            SENSORS_INDEX,
        )

        data = make_coordinator_data()
        hass = MagicMock()
        entry = _mock_entry()
        coord = _mock_coordinator(data)
        desc = SENSORS_INDEX[0]  # SWITCHOFF_REASON
        entity = LuxtronikIndexSensor(hass, entry, coord, desc, DeviceKey.heatpump)
        _patch_entity(entity)

        def get_value_side_effect(key):
            mapping = {
                str(desc.luxtronik_key_timestamp).format(ID=0): 1700000000,
                str(desc.luxtronik_key_timestamp).format(ID=1): 1700000100,
                str(desc.luxtronik_key_timestamp).format(ID=2): 1700000200,
                str(desc.luxtronik_key_timestamp).format(ID=3): 1700000300,
                str(desc.luxtronik_key_timestamp).format(ID=4): 1700000400,
                str(desc.luxtronik_key).format(ID=0): 10,
                str(desc.luxtronik_key).format(ID=1): 20,
                str(desc.luxtronik_key).format(ID=2): 30,
                str(desc.luxtronik_key).format(ID=3): 40,
                str(desc.luxtronik_key).format(ID=4): 50,
            }
            return mapping.get(key)

        coord.get_value.side_effect = get_value_side_effect
        return entity

    def test_handle_coordinator_update(self):
        entity = self._make_index_sensor()
        entity._handle_coordinator_update()
        assert entity._attr_native_value == 50
        entity.async_write_ha_state.assert_called()

    def test_format_time_none(self):
        entity = self._make_index_sensor()
        assert entity.format_time(None) is None

    def test_format_time_valid(self):
        entity = self._make_index_sensor()
        result = entity.format_time(1700000000)
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC


# ===========================================================================
# sensor.py — icon fallback in smart grid (line 391)
# ===========================================================================


class TestSensorSmartGridIconFallback:
    def test_icon_not_set_when_no_icon_by_state(self):
        """SmartGrid sensor delegates icon resolution to icons.json."""
        data = make_coordinator_data(
            parameters={"ID_Einst_SmartGrid": 1},
            calculations={
                "ID_WEB_EVU": 0,
                "ID_WEB_EVU2": 1,
            },
        )
        desc = LuxtronikSensorDescription(
            key=SensorKey.SMART_GRID_STATUS,
            luxtronik_key=LC.UNSET,
            device_key=DeviceKey.heatpump,
        )
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        entity = LuxtronikStatusSensorEntity(
            MagicMock(), entry, coord, desc, DeviceKey.heatpump
        )
        _patch_entity(entity)
        entity._handle_coordinator_update(data)
        # Icon is resolved from icons.json, not set in code
        assert not hasattr(entity, "_attr_icon") or entity._attr_icon is None


def _make_binary_sensor(description=None, data=None):
    hass = MagicMock()
    entry = _mock_entry()
    coord = _mock_coordinator(data)
    if description is None:
        description = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
        )
    entity = LuxtronikBinarySensorEntity(
        hass, entry, coord, description, DeviceKey.heatpump
    )
    _patch_entity(entity)
    return entity


# ===========================================================================
# LuxtronikBinarySensorEntity.compute_is_on
# ===========================================================================


class TestBinarySensorComputeIsOn:
    def test_disturbance_output_fault_detection_error_changed_before(self):
        """When disturbance_output is ON and error_reason changed before, it's a real fault."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_ZW2SSTout": True,
                "ID_WEB_ERROR_Nr0": 42,
            }
        )
        desc = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
        )
        entity = _make_binary_sensor(desc, data)

        disturbance_state = MagicMock()
        disturbance_state.last_changed = datetime(2026, 1, 1, 12, 0, 1)
        error_state = MagicMock()
        error_state.last_changed = datetime(2026, 1, 1, 12, 0, 0)

        def get_side_effect(entity_id):
            if entity_id == entity.entity_id:
                return disturbance_state
            if entity_id.endswith("_error_reason"):
                return error_state
            return None

        entity.hass.states.get.side_effect = get_side_effect

        entity._handle_coordinator_update(data)
        assert entity.is_on is False

    def test_disturbance_output_timestamp_comparison_exception(self):
        """Exception during timestamp comparison falls back to default computation."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_ZW2SSTout": True,
                "ID_WEB_ERROR_Nr0": 42,
            }
        )
        desc = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
            on_state=True,
        )
        entity = _make_binary_sensor(desc, data)

        disturbance_state = MagicMock()
        type(disturbance_state).last_changed = property(
            lambda self: (_ for _ in ()).throw(AttributeError("no last_changed"))
        )
        error_state = MagicMock()
        error_state.last_changed = datetime(2026, 1, 1, 12, 0, 0)

        def get_side_effect(entity_id):
            if entity_id == entity.entity_id:
                return disturbance_state
            if entity_id.endswith("_error_reason"):
                return error_state
            return None

        entity.hass.states.get.side_effect = get_side_effect

        entity._handle_coordinator_update(data)
        assert entity.is_on is True

    def test_disturbance_output_fault_detection_equal_timestamps(self):
        """When disturbance_output is ON and error_reason changed at same time, it's a real fault."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_ZW2SSTout": True,
                "ID_WEB_ERROR_Nr0": 42,
            }
        )
        desc = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
        )
        entity = _make_binary_sensor(desc, data)

        disturbance_state = MagicMock()
        disturbance_state.last_changed = datetime(2026, 1, 1, 12, 0, 0)
        error_state = MagicMock()
        error_state.last_changed = datetime(2026, 1, 1, 12, 0, 0)

        def get_side_effect(entity_id):
            if entity_id == entity.entity_id:
                return disturbance_state
            if entity_id.endswith("_error_reason"):
                return error_state
            return None

        entity.hass.states.get.side_effect = get_side_effect

        entity._handle_coordinator_update(data)
        assert entity.is_on is True

    def test_disturbance_output_missing_states(self):
        """When disturbance or error state is missing, fall back to default computation."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_ZW2SSTout": True,
            }
        )
        desc = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
            on_state=True,
        )
        entity = _make_binary_sensor(desc, data)

        def get_side_effect(entity_id):
            return None

        entity.hass.states.get.side_effect = get_side_effect

        entity._handle_coordinator_update(data)
        assert entity.is_on is True

    def test_disturbance_output_off_uses_default_computation(self):
        """When disturbance_output is OFF, use default computation."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_ZW2SSTout": False,
            }
        )
        desc = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
            on_state=True,
        )
        entity = _make_binary_sensor(desc, data)
        _patch_entity(entity)

        entity._handle_coordinator_update(data)
        assert entity.is_on is False

    def test_disturbance_output_on_uses_default_when_no_error_reason(self):
        """When disturbance_output is ON but no error_reason entity, use default computation."""
        data = make_coordinator_data(
            calculations={
                "ID_WEB_ZW2SSTout": True,
            }
        )
        desc = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
            on_state=True,
        )
        entity = _make_binary_sensor(desc, data)

        disturbance_state = MagicMock()
        disturbance_state.last_changed = datetime(2026, 1, 1, 12, 0, 0)

        def get_side_effect(entity_id):
            if entity_id == entity.entity_id:
                return disturbance_state
            return None

        entity.hass.states.get.side_effect = get_side_effect

        entity._handle_coordinator_update(data)
        assert entity.is_on is True


# ===========================================================================
# Energy input sensors: Energy.from_heatpump() divides raw by 10; the
# description's `factor` must supply the remaining /10 (raw is in "kWh/10"
# units per Bouni/python-luxtronik), not another /100. Regression test for
# the double-scaling bug introduced in 461875c, where factor=0.01 combined
# with Energy's own /10 produced values 10x too low.
# ===========================================================================


def _energy_input_case(
    sensor_key: SensorKey,
) -> tuple[LuxtronikSensorDescription, object]:
    description = next(d for d in SENSORS if d.key == sensor_key)
    raw_name = description.luxtronik_key.rsplit(".", 1)[1]
    datatype = next(
        dt for dt in parameters_to_add_update.values() if dt.name == raw_name
    )
    return description, datatype


def _assert_raw_converts_to(
    sensor_key: SensorKey, raw_value: int, expected: float
) -> None:
    """Push a raw register value through the real datatype and description."""
    description = next(d for d in SENSORS if d.key == sensor_key)
    raw_name = description.luxtronik_key.rsplit(".", 1)[1]
    datatype = Calculations().get(raw_name)
    converted = datatype.from_heatpump(raw_value)
    group, sensor_id = description.luxtronik_key.split(".", 1)
    data = make_coordinator_data(**{group: {sensor_id: converted}})
    entity = _make_sensor(description, data)
    entity._handle_coordinator_update(data)
    assert entity._attr_native_value == expected


class TestVentilationStageSetpoints:
    """The four ventilation stages hold the configured airflow in m3/h: the
    library types them Unknown/UINT32, so no conversion runs and the raw
    register is the value. #729's LWC407 (400 m3/h unit) read 130 / 200 / 250
    against fan outputs of 32.5 % / 50.0 % / 62.5 % at the same moments.
    They stay read-only - that is one system, and a `number` would commit to
    the scale before writing real airflow."""

    STAGE_KEYS = (
        SensorKey.VENTILATION_STAGE_HUMIDITY_PROTECTION,
        SensorKey.VENTILATION_STAGE_REDUCED,
        SensorKey.VENTILATION_STAGE_NOMINAL,
        SensorKey.VENTILATION_STAGE_INTENSIVE,
    )

    def test_stages_are_airflow_and_unscaled(self):
        for key in self.STAGE_KEYS:
            description = next(d for d in SENSORS if d.key == key)
            assert (
                description.native_unit_of_measurement
                == UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
            )
            assert description.device_class == SensorDeviceClass.VOLUME_FLOW_RATE
            assert description.factor is None
            assert description.device_key == DeviceKey.ventilation

    def test_stage_value_is_the_raw_register(self):
        """130/200/250 on #729's controller, passed through untouched. The
        intensive value is synthetic - that stage is not reachable through the
        mode parameter there, so it was never observed."""
        for key, raw in zip(self.STAGE_KEYS, (130, 200, 250, 400), strict=True):
            description = next(d for d in SENSORS if d.key == key)
            group, sensor_id = description.luxtronik_key.split(".", 1)
            data = make_coordinator_data(**{group: {sensor_id: raw}})
            entity = _make_sensor(description, data)
            entity._handle_coordinator_update(data)
            assert entity._attr_native_value == raw

    def test_stages_are_not_gated_on_the_ventilation_visibility_flags(self):
        """Same flag family that reads 0 on a working module, which is why
        has_ventilation ignores it - the ventilation device is the gate."""
        for key in self.STAGE_KEYS:
            description = next(d for d in SENSORS if d.key == key)
            assert description.visibility == LuxVisibility.UNSET


class TestAnalogOutScaling:
    """The analog outputs are per mille of a 10 V full scale: the library's
    Voltage datatype (raw / 10) lands on 0-100 and the description's `factor`
    supplies the remaining tenth. Dropping the factor reports raw 1000 as
    100 V on a 10 V output - across 45 diagnostics dumps AnalogOut1-4 never
    exceed 100.0 and cluster on 0.0 / 50.0 / 100.0 (#729)."""

    def test_analog_out1_scaling(self):
        _assert_raw_converts_to(SensorKey.ANALOG_OUT1, 1000, 10.0)

    def test_analog_out2_scaling(self):
        _assert_raw_converts_to(SensorKey.ANALOG_OUT2, 550, 5.5)

    def test_analog_outs_are_volts(self):
        """0/50/100 is equally round read as percent, so the dumps alone
        cannot settle volts vs percent. #729's controller web UI does:
        AnalogOut2 85.0 displays as 8.50 V, AnalogOut3 50.0 as 5.00 V. The
        factor only makes sense alongside volts, so the two are asserted
        together."""
        for key in (SensorKey.ANALOG_OUT1, SensorKey.ANALOG_OUT2):
            description = next(d for d in SENSORS if d.key == key)
            assert description.device_class == SensorDeviceClass.VOLTAGE
            assert (
                description.native_unit_of_measurement == UnitOfElectricPotential.VOLT
            )
            assert description.factor == 0.1


class TestVentilationFanScaling:
    """The fan outputs share the analog outputs' per-mille encoding but are
    reported as a modulation percentage without a `factor`: the value handed
    out is the undivided register, and #729's controller displays 3.25 V where
    this integration shows 32.5 - correct as percent of the 10 V scale, ten
    times too large as volts. Raw values from that LWC407."""

    def test_supply_fan_scaling(self):
        """340 in the reduced ventilation stage."""
        _assert_raw_converts_to(SensorKey.VENTILATION_SUPPLY_FAN, 340, 34.0)

    def test_exhaust_fan_scaling(self):
        """625 on the exhaust channel in the nominal stage."""
        _assert_raw_converts_to(SensorKey.VENTILATION_EXHAUST_FAN, 625, 62.5)

    def test_fans_are_percent_without_factor(self):
        for key in (
            SensorKey.VENTILATION_SUPPLY_FAN,
            SensorKey.VENTILATION_EXHAUST_FAN,
        ):
            description = next(d for d in SENSORS if d.key == key)
            assert description.native_unit_of_measurement == PERCENTAGE
            assert description.device_class is None
            assert description.factor is None


class TestEnergyInputScaling:
    """Parameters 1136/1137/1139 count energy input in 0.01 kWh units, so the
    Energy2 datatype they are registered with is the whole conversion and none
    of the three descriptions carries a `factor`.

    The scale was measured in #734, not read off upstream's "kWh/10" note
    (which claims /10 for these registers and is wrong): regressing the
    heat-quantity calculations on these counters across 19 diagnostics
    snapshots of one MSW4-16 gives a marginal COP of 6.4 for heating and 3.8
    for DHW at 0.01 kWh per count - and 0.64 / 0.38 at 0.1 kWh per count,
    which no compressor can achieve. The raw values below are from that same
    series.
    """

    def _assert_raw_converts_to(
        self, sensor_key: SensorKey, raw_value: int, expected_kwh: float
    ) -> None:
        description, datatype = _energy_input_case(sensor_key)
        converted = datatype.from_heatpump(raw_value)
        group, sensor_id = description.luxtronik_key.split(".", 1)
        data = make_coordinator_data(**{group: {sensor_id: converted}})
        entity = _make_sensor(description, data)
        entity._handle_coordinator_update(data)
        assert entity._attr_native_value == expected_kwh

    def test_heat_energy_input_scaling(self):
        self._assert_raw_converts_to(SensorKey.HEAT_ENERGY_INPUT, 269938, 2699.38)

    def test_dhw_energy_input_scaling(self):
        self._assert_raw_converts_to(SensorKey.DHW_ENERGY_INPUT, 66818, 668.18)

    def test_cooling_energy_input_scaling(self):
        self._assert_raw_converts_to(SensorKey.COOLING_ENERGY_INPUT, 12345, 123.45)

    def _converted_value(self, sensor_key: SensorKey, raw_value: int) -> float:
        description, datatype = _energy_input_case(sensor_key)
        converted = datatype.from_heatpump(raw_value)
        group, sensor_id = description.luxtronik_key.split(".", 1)
        data = make_coordinator_data(**{group: {sensor_id: converted}})
        entity = _make_sensor(description, data)
        entity._handle_coordinator_update(data)
        return entity._attr_native_value

    def test_implied_cop_is_physical(self):
        """Guards the whole chain - datatype plus description - against a
        factor-of-ten change: over the window covered by the #734 series the
        unit put out 17345.0 kWh of heating heat for 269232 counts of input
        and 2680.7 kWh of DHW heat for 69627 counts, which has to come out as
        a COP above 1 and below the ~8 no air-source unit exceeds seasonally.
        """
        for sensor_key, counts, heat_kwh in (
            (SensorKey.HEAT_ENERGY_INPUT, 269232, 17345.0),
            (SensorKey.DHW_ENERGY_INPUT, 69627, 2680.7),
        ):
            cop = heat_kwh / self._converted_value(sensor_key, counts)
            assert 1.0 < cop < 8.0


class TestAuxHeaterAmountScaling:
    """Parameters 1059 and 1140 both count auxiliary-heater heat in 0.1 kWh
    units, so the Energy datatype they are registered with is the whole
    conversion and neither description carries a `factor`.

    The scale is pinned by physics rather than by upstream's unit note:
    energy divided by the aux heater's run time must equal its rated power
    (parameter 1025). The values below are real readings from user
    diagnostics in #625 - 37539 counts over 420.03 hours of ZWE1 run time on
    a unit whose rated element is 9.0 kW, giving 8.94 kW at 0.1 kWh per count
    and 0.89 kW if a further /10 is applied on top, as #490 did.
    """

    def _converted_value(self, sensor_key: SensorKey, raw_value: int) -> float:
        description, datatype = _energy_input_case(sensor_key)
        converted = datatype.from_heatpump(raw_value)
        group, sensor_id = description.luxtronik_key.split(".", 1)
        data = make_coordinator_data(**{group: {sensor_id: converted}})
        entity = _make_sensor(description, data)
        entity._handle_coordinator_update(data)
        return entity._attr_native_value

    def test_p1059_energy_scaling(self):
        value = self._converted_value(
            SensorKey.ADDITIONAL_HEAT_GENERATOR_ENERGY_P1059, 37539
        )
        assert value == 3753.9

    def test_p1140_energy_scaling(self):
        value = self._converted_value(
            SensorKey.ADDITIONAL_HEAT_GENERATOR_ENERGY_P1140, 841
        )
        assert value == 84.1

    def test_implied_power_matches_rated_element(self):
        """Guards the whole chain - datatype plus description - rather than a
        magic number: 37539 counts over 420.03 ZWE1 hours must come out near
        the unit's rated 9.0 kW, which fails if either scaling step changes.
        """
        kwh = self._converted_value(
            SensorKey.ADDITIONAL_HEAT_GENERATOR_ENERGY_P1059, 37539
        )
        assert 8.0 <= kwh / 420.03 <= 9.5

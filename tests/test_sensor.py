"""Tests for sensor entity classes (LuxtronikSensorEntity, StatusSensor, IndexSensor)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from conftest import make_coordinator_data
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, STATE_UNAVAILABLE

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
    SensorAttrKey as SA,
    SensorKey,
)
from custom_components.luxtronik2.model import (
    LuxtronikBinarySensorEntityDescription,
    LuxtronikSensorDescription,
)
from custom_components.luxtronik2.sensor import (
    LuxtronikIndexSensor,
    LuxtronikSensorEntity,
    LuxtronikStatusSensorEntity,
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
    entity.platform = MagicMock()
    entity.platform.platform_data.platform_translations = {}
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
        assert entity._attr_available is False
        assert entity._attr_native_value is None

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


class TestBuildStatusText:
    def test_returns_empty_when_status_time_none(self):
        entity = _make_status_sensor()
        entity.hass.states.get.return_value = None
        result = entity._build_status_text()
        assert result == ""

    def test_returns_empty_when_status_time_unavailable(self):
        entity = _make_status_sensor()
        mock_state = MagicMock()
        mock_state.state = STATE_UNAVAILABLE
        mock_state.attributes = {SA.STATUS_TEXT: STATE_UNAVAILABLE}

        def get_side_effect(sensor_name):
            if "status_time" in sensor_name:
                return mock_state
            return None

        entity.hass.states.get.side_effect = get_side_effect
        result = entity._build_status_text()
        assert result == ""

    def test_returns_full_text_when_all_present(self):
        entity = _make_status_sensor()
        entity._sensor_prefix = DOMAIN
        entity._attr_native_value = LuxOperationMode.heating

        def get_side_effect(sensor_name):
            mock = MagicMock()
            if "status_time" in sensor_name:
                mock.state = "01:23"
                mock.attributes = {SA.STATUS_TEXT: "01:23"}
                return mock
            if "status_line_1" in sensor_name:
                mock.state = "heatpump_running"
                return mock
            if "status_line_2" in sensor_name:
                mock.state = "heating"
                return mock
            return None

        entity.hass.states.get.side_effect = get_side_effect
        entity.platform.platform_data.platform_translations = {
            f"component.{DOMAIN}.entity.sensor.status_line_1.state.heatpump_running": "HP Running",
            f"component.{DOMAIN}.entity.sensor.status_line_2.state.heating": "Heating",
        }
        result = entity._build_status_text()
        assert "HP Running" in result
        assert "Heating" in result

    def test_returns_empty_when_line1_unavailable(self):
        entity = _make_status_sensor()
        entity._sensor_prefix = DOMAIN

        def get_side_effect(sensor_name):
            mock = MagicMock()
            if "status_time" in sensor_name:
                mock.state = "01:23"
                mock.attributes = {SA.STATUS_TEXT: "01:23"}
                return mock
            if "status_line_1" in sensor_name:
                mock.state = STATE_UNAVAILABLE
                return mock
            return MagicMock(state="ok")

        entity.hass.states.get.side_effect = get_side_effect
        result = entity._build_status_text()
        assert result == ""

    def test_returns_empty_when_line2_unavailable(self):
        entity = _make_status_sensor()
        entity._sensor_prefix = DOMAIN

        def get_side_effect(sensor_name):
            mock = MagicMock()
            if "status_time" in sensor_name:
                mock.state = "01:23"
                mock.attributes = {SA.STATUS_TEXT: "01:23"}
                return mock
            if "status_line_1" in sensor_name:
                mock.state = "heatpump_running"
                return mock
            if "status_line_2" in sensor_name:
                mock.state = STATE_UNAVAILABLE
                return mock
            return None

        entity.hass.states.get.side_effect = get_side_effect
        result = entity._build_status_text()
        assert result == ""


# ===========================================================================
# StatusSensor._get_sensor_value / _get_sensor_attr
# ===========================================================================


class TestSensorHelpers:
    def test_get_sensor_value_existing(self):
        entity = _make_status_sensor()
        mock_state = MagicMock()
        mock_state.state = "42"
        entity.hass.states.get.return_value = mock_state
        assert entity._get_sensor_value("sensor.test") == "42"

    def test_get_sensor_value_missing(self):
        entity = _make_status_sensor()
        entity.hass.states.get.return_value = None
        assert entity._get_sensor_value("sensor.test") is None

    def test_get_sensor_attr_existing(self):
        entity = _make_status_sensor()
        mock_state = MagicMock()
        mock_state.attributes = {"foo": "bar"}
        entity.hass.states.get.return_value = mock_state
        assert entity._get_sensor_attr("sensor.test", "foo") == "bar"

    def test_get_sensor_attr_missing_sensor(self):
        entity = _make_status_sensor()
        entity.hass.states.get.return_value = None
        assert entity._get_sensor_attr("sensor.test", "foo") is None

    def test_get_sensor_attr_missing_attr(self):
        entity = _make_status_sensor()
        mock_state = MagicMock()
        mock_state.attributes = {}
        entity.hass.states.get.return_value = mock_state
        assert entity._get_sensor_attr("sensor.test", "foo") is None


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
        # Create coordinator data with disturbance_output=True
        data = make_coordinator_data(
            calculations={
                "ID_WEB_ZW2SSTout": 1,  # disturbance_output ON
                "ID_WEB_ERROR_Nr0": 42,  # error_reason has value
            }
        )

        # Create binary sensor entity for disturbance output
        desc = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
        )
        entity = _make_binary_sensor(desc, data)

        # Mock hass.states.get to return state objects with timestamps
        disturbance_state = MagicMock()
        disturbance_state.last_changed = datetime(2026, 1, 1, 12, 0, 1)  # 12:00:01

        error_state = MagicMock()
        error_state.last_changed = datetime(2026, 1, 1, 12, 0, 0)  # 12:00:00 (changed BEFORE disturbance)

        def get_side_effect(entity_id):
            if entity_id == entity.entity_id:
                return disturbance_state
            elif entity_id == f"{entity.entity_id.rsplit('_', 1)[0]}_error_reason":
                return error_state
            return None

        entity.hass.states.get.side_effect = get_side_effect

        # Call compute_is_on directly to test the logic
        result = entity.compute_is_on(True)

        # Should return True (real fault) because error_changed < disturbance_changed
        assert result is True

    def test_disturbance_output_fault_detection_error_changed_after(self):
        """When disturbance_output is ON and error_reason changed after, it's a real fault."""
        # Create coordinator data with disturbance_output=True
        data = make_coordinator_data(
            calculations={
                "ID_WEB_ZW2SSTout": 1,  # disturbance_output ON
                "ID_WEB_ERROR_Nr0": 42,  # error_reason has value
            }
        )

        # Create binary sensor entity for disturbance output
        desc = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
        )
        entity = _make_binary_sensor(desc, data)

        # Mock hass.states.get to return state objects with timestamps
        disturbance_state = MagicMock()
        disturbance_state.last_changed = datetime(2026, 1, 1, 12, 0, 0)  # 12:00:00

        error_state = MagicMock()
        error_state.last_changed = datetime(2026, 1, 1, 12, 0, 1)  # 12:00:01 (changed AFTER disturbance)

        def get_side_effect(entity_id):
            if entity_id == entity.entity_id:
                return disturbance_state
            elif entity_id == f"{entity.entity_id.rsplit('_', 1)[0]}_error_reason":
                return error_state
            return None

        entity.hass.states.get.side_effect = get_side_effect

        # Call compute_is_on directly to test the logic
        result = entity.compute_is_on(True)

        # Should return True (real fault) because error_changed > disturbance_changed
        # (error changed AFTER disturbance, so not treated as ZWE2 noise)
        assert result is True

    def test_disturbance_output_fault_detection_equal_timestamps(self):
        """When disturbance_output is ON and error_reason changed at same time, it's a real fault."""
        # Create coordinator data with disturbance_output=True
        data = make_coordinator_data(
            calculations={
                "ID_WEB_ZW2SSTout": 1,  # disturbance_output ON
                "ID_WEB_ERROR_Nr0": 42,  # error_reason has value
            }
        )

        # Create binary sensor entity for disturbance output
        desc = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
        )
        entity = _make_binary_sensor(desc, data)

        # Mock hass.states.get to return state objects with same timestamps
        disturbance_state = MagicMock()
        disturbance_state.last_changed = datetime(2026, 1, 1, 12, 0, 0)

        error_state = MagicMock()
        error_state.last_changed = datetime(2026, 1, 1, 12, 0, 0)  # Same time

        def get_side_effect(entity_id):
            if entity_id == entity.entity_id:
                return disturbance_state
            elif entity_id == f"{entity.entity_id.rsplit('_', 1)[0]}_error_reason":
                return error_state
            return None

        entity.hass.states.get.side_effect = get_side_effect

        # Call compute_is_on directly to test the logic
        result = entity.compute_is_on(True)

        # Should return True (real fault) because error_changed is NOT < disturbance_changed
        # (error changed at same time as disturbance, so not treated as ZWE2 noise)
        assert result is True

    def test_disturbance_output_missing_states(self):
        """When disturbance or error state is missing, fall back to default computation."""
        # Create coordinator data with disturbance_output=True
        data = make_coordinator_data(
            calculations={
                "ID_WEB_ZW2SSTout": 1,  # disturbance_output ON
            }
        )

        # Create binary sensor entity for disturbance output
        desc = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
            on_state=True,  # Assume it's ON when value is True
        )
        entity = _make_binary_sensor(desc, data)

        # Mock hass.states.get to return None for one or both states
        def get_side_effect(entity_id):
            return None  # Return None for both states

        entity.hass.states.get.side_effect = get_side_effect

        # Call compute_is_on directly to test the logic
        result = entity.compute_is_on(True)

        # Should fall back to default computation and return True (since state == on_state)
        assert result is True

    def test_disturbance_output_off_uses_default_computation(self):
        """When disturbance_output is OFF, use default computation."""
        # Create coordinator data with disturbance_output=False
        data = make_coordinator_data(
            calculations={
                "ID_WEB_ZW2SSTout": 0,  # disturbance_output OFF
            }
        )

        # Create binary sensor entity for disturbance output
        desc = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
            on_state=True,  # Assume it's ON when value is True
        )
        entity = _make_binary_sensor(desc, data)
        _patch_entity(entity)

        # Call compute_is_on directly to test the logic
        result = entity.compute_is_on(False)

        # Should use default computation: state (False) == on_state (True) -> False
        assert result is False

    def test_disturbance_output_on_uses_default_when_no_error_reason(self):
        """When disturbance_output is ON but no error_reason entity, use default computation."""
        # Create coordinator data with disturbance_output=True
        data = make_coordinator_data(
            calculations={
                "ID_WEB_ZW2SSTout": 1,  # disturbance_output ON
                # No error_reason data
            }
        )

        # Create binary sensor entity for disturbance output
        desc = LuxtronikBinarySensorEntityDescription(
            key=SensorKey.DISTURBANCE_OUTPUT,
            luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
            device_key=DeviceKey.heatpump,
            on_state=True,  # Assume it's ON when value is True
        )
        entity = _make_binary_sensor(desc, data)

        # Mock hass.states.get to return disturbance state but None for error state
        disturbance_state = MagicMock()
        disturbance_state.last_changed = datetime(2026, 1, 1, 12, 0, 0)

        def get_side_effect(entity_id):
            if entity_id == entity.entity_id:
                return disturbance_state
            return None  # Error state not found

        entity.hass.states.get.side_effect = get_side_effect

        # Call compute_is_on directly to test the logic
        result = entity.compute_is_on(True)

        # Should fall back to default computation and return True (since state == on_state)
        assert result is True

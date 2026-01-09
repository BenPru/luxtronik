"""Support for Luxtronik sensors."""

# flake8: noqa: W503
# region Imports
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import ENTITY_ID_FORMAT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import dt as dt_util

from .base import LuxtronikEntity
from .common import get_sensor_data, key_exists
from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    LOGGER,
    DeviceKey,
    LuxCalculation as LC,
    LuxOperationMode,
    LuxParameter as LP,
    LuxSmartGridStatus,
    LuxStatus1Option,
    LuxStatus3Option,
    SensorAttrKey as SA,
    SensorKey,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .evu_helper import LuxtronikEVUTracker
from .model import LuxtronikIndexSensorDescription, LuxtronikSensorDescription
from .sensor_entities_predefined import SENSORS, SENSORS_INDEX, SENSORS_STATUS

# endregion Imports


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Luxtronik sensors dynamically through Luxtronik discovery."""

    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not data or CONF_COORDINATOR not in data:
        raise ConfigEntryNotReady

    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]

    # Ensure coordinator has valid data before adding entities
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    unavailable_keys = [
        i.luxtronik_key
        for i in SENSORS + SENSORS_STATUS
        if not key_exists(coordinator.data, i.luxtronik_key)
        and not i.luxtronik_key == LC.UNSET
    ]
    if unavailable_keys:
        LOGGER.warning("Not present in Luxtronik data, skipping: %s", unavailable_keys)

    async_add_entities(
        [
            LuxtronikSensorEntity(
                hass, entry, coordinator, description, description.device_key
            )
            for description in SENSORS
            if (
                coordinator.entity_active(description)
                and key_exists(coordinator.data, description.luxtronik_key)
            )
        ],
        True,
    )

    async_add_entities(
        [
            LuxtronikStatusSensorEntity(
                hass, entry, coordinator, description, description.device_key
            )
            for description in SENSORS_STATUS
            if (
                coordinator.entity_active(description)
                and (
                    # Check if firmware supports the Luxtronik Parameter/Calculation key
                    key_exists(coordinator.data, description.luxtronik_key)
                    or (
                        # For SmartGrid status sensor, check if required parameters exist
                        description.key == SensorKey.SMART_GRID_STATUS
                        and (
                            key_exists(coordinator.data, LP.P1030_SMART_GRID_SWITCH)
                            and key_exists(coordinator.data, LC.C0031_EVU_UNLOCKED)
                            and key_exists(coordinator.data, LC.C0185_EVU2)
                        )
                    )
                )
            )
        ],
        True,
    )

    async_add_entities(
        [
            LuxtronikIndexSensor(
                hass, entry, coordinator, description, description.device_key
            )
            for description in SENSORS_INDEX
            if coordinator.entity_active(description)
        ],
        True,
    )


class LuxtronikSensorEntity(LuxtronikEntity, SensorEntity):
    """Luxtronik Sensor Entity."""

    entity_description: LuxtronikSensorDescription
    _coordinator: LuxtronikCoordinator

    _unrecorded_attributes = frozenset(
        {
            SA.SWITCH_GAP,
            SA.CODE,
            SA.CAUSE,
            SA.REMEDY,
            SA.TIMER_HEATPUMP_ON,
            SA.TIMER_ADD_HEAT_GENERATOR_ON,
            SA.TIMER_SEC_HEAT_GENERATOR_ON,
            SA.TIMER_NET_INPUT_DELAY,
            SA.TIMER_SCB_OFF,
            SA.TIMER_SCB_ON,
            SA.TIMER_COMPRESSOR_OFF,
            SA.TIMER_HC_ADD,
            SA.TIMER_HC_LESS,
            SA.TIMER_TDI,
            SA.TIMER_BLOCK_DHW,
            SA.TIMER_DEFROST,
            SA.TIMER_HOT_GAS,
        }
    )

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikSensorDescription,
        device_info_ident: DeviceKey,
    ) -> None:
        """Init Luxtronik Switch."""
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
        )

        self._sensor_prefix = prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        # if not self.should_update():
        #    return

        data = self.coordinator.data if data is None else data
        if data is None:
            return

        value = get_sensor_data(data, self.entity_description.luxtronik_key.value)

        if value is None:
            self._attr_native_value = None
        elif isinstance(value, (float, int)):
            factor = self.entity_description.factor or 1
            precision = self.entity_description.native_precision
            value = float(value) * factor
            if precision is not None:
                value = round(value, precision)
            self._attr_native_value = value
        else:
            self._attr_native_value = value

        self.async_write_ha_state()
        super()._handle_coordinator_update()


class LuxtronikStatusSensorEntity(LuxtronikSensorEntity, SensorEntity):
    """Luxtronik Status Sensor with extended attr."""

    entity_description: LuxtronikSensorDescription

    _coordinator: LuxtronikCoordinator
    _evu_tracker: LuxtronikEVUTracker = LuxtronikEVUTracker()

    _last_state: StateType | date | datetime | Decimal = None

    _unrecorded_attributes = frozenset(
        LuxtronikSensorEntity._unrecorded_attributes
        | {
            SA.STATUS_TEXT,
            SA.STATUS_RAW,
            SA.EVU_FIRST_START_TIME,
            SA.EVU_FIRST_END_TIME,
            SA.EVU_SECOND_START_TIME,
            SA.EVU_SECOND_END_TIME,
            SA.EVU_MINUTES_UNTIL_NEXT_EVENT,
            SA.EVU_DAYS,
        }
    )

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        if self.entity_description.key == SensorKey.SMART_GRID_STATUS:
            self._update_smart_grid_status()
            return

        # For normal status sensors, use the parent's update logic
        super()._handle_coordinator_update(data)

        self._evu_tracker.update(self._attr_native_value)

        if self._attr_native_value is None or self._last_state is None:
            pass

        # region Workaround Luxtronik Bug
        else:
            # region Workaround: Inverter heater is active but not the heatpump!
            # Status shows heating but status 3 = no request!
            sl1 = self._get_value(LC.C0117_STATUS_LINE_1)
            sl3 = self._get_value(LC.C0119_STATUS_LINE_3)
            add_circ_pump = self._get_value(LC.C0047_ADDITIONAL_CIRCULATION_PUMP)
            s1_workaround: list[str] = [
                LuxStatus1Option.heatpump_idle,
                LuxStatus1Option.pump_forerun,
                LuxStatus1Option.heatpump_coming,
            ]
            s3_workaround: list[str | None] = [
                LuxStatus3Option.no_request,
                LuxStatus3Option.unknown,
                LuxStatus3Option.none,
                LuxStatus3Option.grid_switch_on_delay,
                None,
            ]
            if sl1 in s1_workaround and sl3 in s3_workaround and not add_circ_pump:
                # ignore pump forerun
                self._attr_native_value = LuxOperationMode.no_request.value
            # endregion Workaround: Inverter heater is active but not the heatpump!

            # region Workaround Thermal desinfection with heatpump running
            if sl3 == LuxStatus3Option.thermal_desinfection:
                # map thermal desinfection to Domestic Water iso Heating
                self._attr_native_value = LuxOperationMode.domestic_water.value
            # endregion Workaround Thermal desinfection with heatpump running

            # region Workaround Thermal desinfection with (only) using 2nd heatsource
            s3_workaround: list[str | None] = [
                LuxStatus3Option.no_request,
                LuxStatus3Option.cycle_lock,
            ]
            if sl3 in s3_workaround:
                DHW_recirculation = self._get_value(LC.C0038_DHW_RECIRCULATION_PUMP)
                AddHeat = self._get_value(LC.C0048_ADDITIONAL_HEAT_GENERATOR)
                if AddHeat and DHW_recirculation:
                    # more fixes to detect thermal desinfection sequences
                    self._attr_native_value = LuxOperationMode.domestic_water.value
            # endregion Workaround Thermal desinfection with (only) using 2nd heatsource

        # endregion Workaround Luxtronik Bug

        self._last_state = self._attr_native_value

        attr = self._attr_extra_state_attributes
        attr[SA.STATUS_RAW] = self._attr_native_value
        attr[SA.STATUS_TEXT] = self._build_status_text()
        attr.update(self._evu_tracker.get_attributes())
        self._enrich_extra_attributes()
        self.async_write_ha_state()

    def _get_sensor_value(self, sensor_name: str) -> Any:
        sensor = self.hass.states.get(sensor_name)
        if sensor is not None:
            return sensor.state
        return None

    def _get_sensor_attr(self, sensor_name: str, attr: str) -> Any:
        sensor = self.hass.states.get(sensor_name)
        if sensor is not None and attr in sensor.attributes:
            return sensor.attributes[attr]
        return None

    def _build_status_text(self) -> str:
        status_time = self._get_sensor_attr(
            f"sensor.{self._sensor_prefix}_status_time", SA.STATUS_TEXT
        )
        line_1_state = self._get_sensor_value(
            f"sensor.{self._sensor_prefix}_status_line_1"
        )
        line_2_state = self._get_sensor_value(
            f"sensor.{self._sensor_prefix}_status_line_2"
        )
        if status_time is None or status_time == STATE_UNAVAILABLE:
            return ""
        if line_1_state is None or line_1_state == STATE_UNAVAILABLE:
            return ""
        if line_2_state is None or line_2_state == STATE_UNAVAILABLE:
            return ""
        line_1 = self.platform.platform_data.platform_translations.get(
            f"component.{DOMAIN}.entity.sensor.status_line_1.state.{line_1_state}"
        )
        line_2 = self.platform.platform_data.platform_translations.get(
            f"component.{DOMAIN}.entity.sensor.status_line_2.state.{line_2_state}"
        )
        # Show evu end time if available
        suffix = self._evu_tracker.get_evu_status_suffix(self._attr_native_value)
        return (
            f"{line_1} {line_2} {status_time}. {suffix}"
            if suffix
            else f"{line_1} {line_2} {status_time}."
        )

    def _update_smart_grid_status(self) -> None:
        """Calculate and update SmartGrid status based on EVU and EVU2 inputs."""
        from .const import LuxParameter as LP

        # Check if SmartGrid is enabled (P1030)
        smartgrid_enabled = self._get_value(LP.P1030_SMART_GRID_SWITCH)

        # If SmartGrid is disabled, set sensor to unavailable
        if not smartgrid_enabled or smartgrid_enabled in [False, 0, "false", "False"]:
            self._attr_available = False
            self._attr_native_value = None
        else:
            self._attr_available = True

            evu = self._get_value(LC.C0031_EVU_UNLOCKED)
            evu2 = self._get_value(LC.C0185_EVU2)

            # Convert to boolean (handle True/False/1/0/"true"/"false")
            evu_on = evu in [True, 1, "true", "True"]
            evu2_on = evu2 in [True, 1, "true", "True"]

            # Determine SmartGrid status based on EVU and EVU2 inputs
            # EVU=0, EVU2=0 → Status 2 (reduced operation)
            # EVU=1, EVU2=0 → Status 1 (EVU locked)
            # EVU=0, EVU2=1 → Status 3 (normal operation)
            # EVU=1, EVU2=1 → Status 4 (increased operation)
            if evu_on and not evu2_on:
                self._attr_native_value = LuxSmartGridStatus.locked.value  # Status 1
            elif not evu_on and not evu2_on:
                self._attr_native_value = LuxSmartGridStatus.reduced.value  # Status 2
            elif not evu_on and evu2_on:
                self._attr_native_value = LuxSmartGridStatus.normal.value  # Status 3
            else:  # evu_on and evu2_on
                self._attr_native_value = LuxSmartGridStatus.increased.value  # Status 4

            # Set icon based on current state
            descr = self.entity_description
            if descr.icon_by_state and self._attr_native_value in descr.icon_by_state:
                self._attr_icon = descr.icon_by_state.get(self._attr_native_value)
            elif descr.icon:
                self._attr_icon = descr.icon

        # Don't call super() to avoid setting value to None (luxtronik_key=UNSET)
        self._enrich_extra_attributes()
        self.async_write_ha_state()


class LuxtronikIndexSensor(LuxtronikSensorEntity, SensorEntity):
    _min_index = 0
    _max_index = 4

    entity_description: LuxtronikIndexSensorDescription

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""

        values = dict()
        for i in range(self._min_index, self._max_index + 1):
            luxtronik_key_timestamp = str(
                self.entity_description.luxtronik_key_timestamp
            ).format(ID=i)
            luxtronik_key = str(self.entity_description.luxtronik_key).format(ID=i)
            key = self.coordinator.get_value(luxtronik_key_timestamp)
            values[key] = self.coordinator.get_value(luxtronik_key)

        values = dict(sorted(values.items()))
        attr = self._attr_extra_state_attributes

        item = values.popitem()
        self._attr_native_value = attr[SA.CODE] = item[1]
        attr[SA.TIMESTAMP] = self.format_time(item[0])

        i = 1
        while len(values) > 0:
            item = values.popitem()
            attr[SA.CODE + f"_{i}"] = item[1]
            attr[SA.TIMESTAMP + f"_{i}"] = self.format_time(item[0])
            i += 1

        self.async_write_ha_state()

    def format_time(self, value_timestamp: int | None) -> datetime | None:
        if value_timestamp is not None and isinstance(value_timestamp, int):
            value_timestamp = datetime.fromtimestamp(value_timestamp, timezone.utc)
        if (
            value_timestamp is not None
            and isinstance(value_timestamp, datetime)
            and value_timestamp.tzinfo is None
        ):
            time_zone = dt_util.get_time_zone(self.hass.config.time_zone)
            value_timestamp = value_timestamp.replace(tzinfo=time_zone)
        return value_timestamp

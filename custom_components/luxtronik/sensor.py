"""Support for Luxtronik sensors."""
# flake8: noqa: W503
# region Imports
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import ENTITY_ID_FORMAT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .base import LuxtronikEntity
from .common import get_sensor_data
from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    LOGGER,
    DeviceKey,
    LuxCalculation as LC,
    LuxOperationMode,
    LuxStatus1Option,
    LuxStatus3Option,
    SensorAttrKey as SA,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikSensorDescription
from .sensor_entities_predefined import SENSORS, SENSORS_STATUS

# endregion Imports


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up luxtronik sensors dynamically through luxtronik discovery."""
    data: dict = hass.data[DOMAIN][entry.entry_id]
    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        LuxtronikSensorEntity(
            hass, entry, coordinator, description, description.device_key
        )
        for description in SENSORS
        if coordinator.entity_active(description)
    )

    async_add_entities(
        LuxtronikStatusSensorEntity(
            hass, entry, coordinator, description, description.device_key
        )
        for description in SENSORS_STATUS
        if coordinator.entity_active(description)
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
        self._sensor_prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"{self._sensor_prefix}_{description.key}"
        )
        self._attr_unique_id = self.entity_id
        self._sensor_data = get_sensor_data(
            coordinator.data, description.luxtronik_key.value
        )

    async def _data_update(self, event):
        self._handle_coordinator_update()

    def _handle_coordinator_update_internal(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        if (
            not self.coordinator.update_reason_write
            and self.next_update is not None
            and self.next_update > utcnow()
        ):
            return
        data = self.coordinator.data if data is None else data
        if data is None:
            return
        self._attr_native_value = get_sensor_data(
            data, self.entity_description.luxtronik_key.value
        )

        if self._attr_native_value is None:
            pass

        elif isinstance(self._attr_native_value, (float, int)) and (
            self.entity_description.factor is not None
            or self.entity_description.native_precision is not None
        ):
            float_value = float(self._attr_native_value)
            if self.entity_description.factor is not None:
                float_value *= self.entity_description.factor
            if self.entity_description.native_precision is not None:
                float_value = round(
                    float_value, self.entity_description.native_precision
                )
            self._attr_native_value = float_value

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        self._handle_coordinator_update_internal(data)
        super()._handle_coordinator_update()


class LuxtronikStatusSensorEntity(LuxtronikSensorEntity, SensorEntity):
    """Luxtronik Status Sensor with extended attr."""

    entity_description: LuxtronikSensorDescription

    _coordinator: LuxtronikCoordinator
    _last_state: StateType | date | datetime | Decimal = None

    _attr_cache: dict[SA, time] = {}
    _attr_cache[SA.EVU_FIRST_START_TIME] = time.min
    _attr_cache[SA.EVU_FIRST_END_TIME] = time.min
    _attr_cache[SA.EVU_SECOND_START_TIME] = time.min
    _attr_cache[SA.EVU_SECOND_END_TIME] = time.min

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
        }
    )

    async def _data_update(self, event):
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update(data)
        time_now = time(datetime.now().hour, datetime.now().minute)
        evu = LuxOperationMode.evu.value
        if self._attr_native_value is None or self._last_state is None:
            pass
        elif self._attr_native_value == evu and str(self._last_state) != evu:
            # evu start
            if (
                self._attr_cache[SA.EVU_FIRST_START_TIME] == time.min
                or time_now.hour <= self._attr_cache[SA.EVU_FIRST_START_TIME].hour
                or (
                    self._attr_cache[SA.EVU_SECOND_START_TIME] != time.min
                    and time_now.hour < self._attr_cache[SA.EVU_SECOND_START_TIME].hour
                )
                or time_now.hour <= self._attr_cache[SA.EVU_FIRST_END_TIME].hour
            ):
                self._attr_cache[SA.EVU_FIRST_START_TIME] = time_now
            else:
                self._attr_cache[SA.EVU_SECOND_START_TIME] = time_now
        elif self._attr_native_value != evu and str(self._last_state) == evu:
            # evu end
            if (
                self._attr_cache[SA.EVU_FIRST_END_TIME] == time.min
                or time_now.hour <= self._attr_cache[SA.EVU_FIRST_END_TIME].hour
                or (
                    self._attr_cache[SA.EVU_SECOND_START_TIME] != time.min
                    and time_now < self._attr_cache[SA.EVU_SECOND_START_TIME]
                )
            ):
                self._attr_cache[SA.EVU_FIRST_END_TIME] = time_now
            else:
                self._attr_cache[SA.EVU_SECOND_END_TIME] = time_now

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
                AddHeat           = self._get_value(LC.C0048_ADDITIONAL_HEAT_GENERATOR)
                if AddHeat and DHW_recirculation:
                    # more fixes to detect thermal desinfection sequences 
                    self._attr_native_value = LuxOperationMode.domestic_water.value
            # endregion Workaround Thermal desinfection with (only) using 2nd heatsource
             
            # region Workaround Detect passive cooling operation mode
            if self._attr_native_value == LuxOperationMode.no_request.value:
                # detect passive cooling
                if self.coordinator.detect_cooling_present():
                    T_in       = self._get_value(LC.C0010_FLOW_IN_TEMPERATURE)
                    T_out      = self._get_value(LC.C0011_FLOW_OUT_TEMPERATURE)
                    T_heat_in  = self._get_value(LC.C0204_HEAT_SOURCE_INPUT_TEMPERATURE)
                    T_heat_out = self._get_value(LC.C0020_HEAT_SOURCE_OUTPUT_TEMPERATURE)
                    Flow_WQ    = self._get_value(LC.C0173_HEAT_SOURCE_FLOW_RATE)
                    if (T_out > T_in) and (T_heat_out > T_heat_in) and (Flow_WQ > 0):
                        #LOGGER.info(f"Cooling mode detected!!!")
                        self._attr_native_value = LuxOperationMode.cooling.value
            # endregion Workaround Detect passive cooling operation mode                  
        # endregion Workaround Luxtronik Bug

        self._last_state = self._attr_native_value

        attr = self._attr_extra_state_attributes
        attr[SA.STATUS_RAW] = self._attr_native_value
        attr[SA.STATUS_TEXT] = self._build_status_text()
        attr[SA.EVU_MINUTES_UNTIL_NEXT_EVENT] = self._calc_next_evu_event_minutes_text()
        attr[SA.EVU_FIRST_START_TIME] = self._tm_txt(
            self._attr_cache[SA.EVU_FIRST_START_TIME]
        )
        attr[SA.EVU_FIRST_END_TIME] = self._tm_txt(
            self._attr_cache[SA.EVU_FIRST_END_TIME]
        )
        attr[SA.EVU_SECOND_START_TIME] = self._tm_txt(
            self._attr_cache[SA.EVU_SECOND_START_TIME]
        )
        attr[SA.EVU_SECOND_END_TIME] = self._tm_txt(
            self._attr_cache[SA.EVU_SECOND_END_TIME]
        )
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
        line_1 = self.platform.platform_translations.get(
            f"component.{DOMAIN}.entity.sensor.status_line_1.state.{line_1_state}"
        )
        line_2 = self.platform.platform_translations.get(
            f"component.{DOMAIN}.entity.sensor.status_line_2.state.{line_2_state}"
        )
        # Show evu end time if available
        evu_event_minutes = self._calc_next_evu_event_minutes()
        if evu_event_minutes is None:
            pass
        elif self.native_value == LuxOperationMode.evu.value:
            text_locale = self.platform.platform_translations.get(
                f"component.{DOMAIN}.entity.sensor.status.state_attributes.evu_text.state.evu_until"
            )
            evu_until = text_locale.format(evu_time=evu_event_minutes)
            return f"{evu_until} {line_1} {line_2} {status_time}."
        elif evu_event_minutes <= 30:
            text_locale = self.platform.platform_translations.get(
                f"component.{DOMAIN}.entity.sensor.status.state_attributes.evu_text.state.evu_in"
            )
            evu_in = text_locale.format(evu_time=evu_event_minutes)
            return f"{line_1} {line_2} {status_time}. {evu_in}"
        return f"{line_1} {line_2} {status_time}."

    def _calc_next_evu_event_minutes_text(self) -> str:
        minutes = self._calc_next_evu_event_minutes()
        return "" if minutes is None else str(minutes)

    def _calc_next_evu_event_minutes(self) -> int | None:
        evu_time = self._get_next_evu_event_time()
        time_now = time(datetime.now().hour, datetime.now().minute)
        if evu_time == time.min:
            return None
        evu_hours = (24 if evu_time < time_now else 0) + evu_time.hour
        return (evu_hours - time_now.hour) * 60 + evu_time.minute - time_now.minute

    def _get_next_evu_event_time(self) -> time:
        event: time = time.min
        time_now = time(datetime.now().hour, datetime.now().minute)
        for evu_time in (
            self._attr_cache[SA.EVU_FIRST_START_TIME],
            self._attr_cache[SA.EVU_FIRST_END_TIME],
            self._attr_cache[SA.EVU_SECOND_START_TIME],
            self._attr_cache[SA.EVU_SECOND_END_TIME],
        ):
            if evu_time == time.min:
                continue
            if evu_time > time_now and (event == time.min or evu_time < event):
                event = evu_time
        if event == time.min:
            for evu_time in (
                self._attr_cache[SA.EVU_FIRST_START_TIME],
                self._attr_cache[SA.EVU_FIRST_END_TIME],
                self._attr_cache[SA.EVU_SECOND_START_TIME],
                self._attr_cache[SA.EVU_SECOND_END_TIME],
            ):
                if evu_time == time.min:
                    continue
                if event == time.min or evu_time < event:
                    event = evu_time
        return event

    def _tm_txt(self, value: time) -> str:
        return "" if value == time.min else value.strftime("%H:%M")

    def _restore_attr_value(self, value: Any | None) -> Any:
        if value is None or ":" not in str(value):
            return time.min
        vals = str(value).split(":")
        return time(int(vals[0]), int(vals[1]))

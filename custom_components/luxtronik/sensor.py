"""Support for Luxtronik sensors."""
# region Imports
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import ENTITY_ID_FORMAT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .base import LuxtronikEntity
from .common import get_sensor_data
from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    DeviceKey,
    LuxOperationMode,
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

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data if data is None else data
        if data is None:
            return
        self._attr_native_value = get_sensor_data(
            data, self.entity_description.luxtronik_key.value
        )
        if self._attr_native_value is not None and isinstance(
            self._attr_native_value, (float, int)
        ):
            float_value = float(self._attr_native_value)
            if self.entity_description.factor is not None:
                float_value *= self.entity_description.factor
            if self.entity_description.native_precision is not None:
                float_value = round(
                    float_value, self.entity_description.native_precision
                )
            self._attr_native_value = float_value
        super()._handle_coordinator_update()


class LuxtronikStatusSensorEntity(LuxtronikSensorEntity, SensorEntity):
    """Luxtronik Status Sensor with extended attr."""

    entity_description: LuxtronikSensorDescription

    _coordinator: LuxtronikCoordinator
    _last_state: StateType | date | datetime | Decimal = None

    _first_evu_start: time = time.min
    _first_evu_end: time = time.min
    _second_evu_start: time = time.min
    _second_evu_end: time = time.min

    async def _data_update(self, event):
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
        time_now = time(datetime.now().hour, datetime.now().minute)
        evu = LuxOperationMode.evu.value
        if self._attr_native_value is None or self._last_state is None:
            pass
        elif self._attr_native_value == evu and str(self._last_state) != evu:
            # evu start
            if (
                self._first_evu_start == time.min
                or time_now.hour <= self._first_evu_start.hour  # noqa: W503
                or (  # noqa: W503
                    self._second_evu_start != time.min
                    and time_now.hour < self._second_evu_start.hour  # noqa: W503
                )
                or time_now.hour <= self._first_evu_end.hour  # noqa: W503
            ):
                self._first_evu_start = time_now
            else:
                self._second_evu_start = time_now
        elif self._attr_native_value != evu and str(self._last_state) == evu:
            # evu end
            if (
                self._first_evu_end == time.min
                or time_now.hour <= self._first_evu_end.hour  # noqa: W503
                or (  # noqa: W503
                    self._second_evu_start != time.min
                    and time_now < self._second_evu_start  # noqa: W503
                )
            ):
                self._first_evu_end = time_now
            else:
                self._second_evu_end = time_now

        self._last_state = self._attr_native_value

        attr = self._attr_extra_state_attributes
        attr[SA.STATUS_RAW] = self._attr_native_value
        attr[SA.STATUS_TEXT] = self._build_status_text()
        attr[SA.EVU_MINUTES_UNTIL_NEXT_EVENT] = self._calc_next_evu_event_minutes_text()
        attr[SA.EVU_FIRST_START_TIME] = self._tm_txt(self._first_evu_start)
        attr[SA.EVU_FIRST_END_TIME] = self._tm_txt(self._first_evu_end)
        attr[SA.EVU_SECOND_START_TIME] = self._tm_txt(self._second_evu_start)
        attr[SA.EVU_SECOND_END_TIME] = self._tm_txt(self._second_evu_end)

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
        line_1 = self._get_sensor_value(f"sensor.{self._sensor_prefix}_status_line_1")
        line_2 = self._get_sensor_value(f"sensor.{self._sensor_prefix}_status_line_2")
        if status_time is None or status_time == STATE_UNAVAILABLE:
            return ""
        if line_1 is None or line_1 == STATE_UNAVAILABLE:
            return ""
        if line_2 is None or line_2 == STATE_UNAVAILABLE:
            return ""
        line_1 = self.coordinator.get_sensor_value_text("status_line_1", line_1)
        line_2 = self.coordinator.get_sensor_value_text("status_line_2", line_2)
        # Show evu end time if available
        evu_event_minutes = self._calc_next_evu_event_minutes()
        if evu_event_minutes is None:
            pass
        elif self.native_value == LuxOperationMode.evu.value:
            evu_until = self.coordinator.get_text("evu_until").format(
                evu_time=evu_event_minutes
            )
            return f"{evu_until} {line_1} {line_2} {status_time}."
        elif evu_event_minutes <= 30:
            evu_in = self.coordinator.get_text("evu_in").format(
                evu_time=evu_event_minutes
            )
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
            self._first_evu_start,
            self._first_evu_end,
            self._second_evu_start,
            self._second_evu_end,
        ):
            if evu_time == time.min:
                continue
            if evu_time > time_now and (event == time.min or evu_time < event):
                event = evu_time
        if event == time.min:
            for evu_time in (
                self._first_evu_start,
                self._first_evu_end,
                self._second_evu_start,
                self._second_evu_end,
            ):
                if evu_time == time.min:
                    continue
                if event == time.min or evu_time < event:
                    event = evu_time
        return event

    def _tm_txt(self, value: time) -> str:
        return "" if value == time.min else value.strftime("%H:%M")

    def _restore_value(self, value: str | None) -> time:
        if value is None or ":" not in value:
            return time.min
        vals = value.split(":")
        return time(int(vals[0]), int(vals[1]))

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is None:
            return
        self._attr_native_value = str(state.state)

        if SA.EVU_FIRST_START_TIME in state.attributes:
            self._first_evu_start = self._restore_value(
                state.attributes[SA.EVU_FIRST_START_TIME]
            )
            self._first_evu_end = self._restore_value(
                state.attributes[SA.EVU_FIRST_END_TIME]
            )
            self._second_evu_start = self._restore_value(
                state.attributes[SA.EVU_SECOND_START_TIME]
            )
            self._second_evu_end = self._restore_value(
                state.attributes[SA.EVU_SECOND_END_TIME]
            )

        data_updated = f"{self._sensor_prefix}_data_updated"
        async_dispatcher_connect(
            self.hass, data_updated, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

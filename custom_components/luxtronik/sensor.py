"""Support for Luxtronik sensors."""
# flake8: noqa: W503
# region Imports
from __future__ import annotations
from dataclasses import asdict, dataclass

from datetime import date, datetime, time, timezone
from decimal import Decimal, DecimalException, InvalidOperation
from typing import Any, Self

from croniter import croniter

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.utility_meter.const import DAILY, SIGNAL_RESET_METER
from homeassistant.components.utility_meter.sensor import PERIOD2CRON

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    RestoreSensor,
    SensorEntity,
    SensorExtraStoredData,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.restore_state import ExtraStoredData
from homeassistant.helpers.template import is_number
from homeassistant.helpers.typing import StateType
import homeassistant.util.dt as dt_util

from .base import LuxtronikEntity
from .common import get_sensor_data
from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    LOGGER,
    UNIT_FACTOR_MAP,
    DeviceKey,
    Calculation_SensorKey as LC,
    LuxOperationMode,
    LuxStatus1Option,
    LuxStatus3Option,
    SensorAttrKey as SA,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import (
    LuxtronikIndexSensorDescription,
    LuxtronikPeriodStatSensorDescription,
    LuxtronikSensorDescription,
)
from .sensor_entities_predefined import (
    SENSORS,
    SENSORS_INDEX,
    SENSORS_PERIOD,
    SENSORS_STATUS,
)

# endregion Imports

# region Consts
ATTR_LAST_VALID_STATE = "last_valid_state"
ATTR_TODAY = "today"
ATTR_YESTERDAY = "yesterday"
ATTR_WEEK = "week"
ATTR_LAST_WEEK = "last_week"
ATTR_MONTH = "month"
ATTR_LAST_MONTH = "last_month"
ATTR_YEAR = "year"
ATTR_LAST_YEAR = "last_year"
ATTR_HEATING_PERIOD = "heating_period"
ATTR_LAST_HEATING_PERIOD = "last_heating_period"
ATTR_CURRENT_IMPULSE = "current_impulse"
ATTR_LAST_IMPULSE = "last_impulse"
# endregion Consts


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up luxtronik sensors dynamically through luxtronik discovery."""
    data: dict = hass.data[DOMAIN][entry.entry_id]
    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        (
            LuxtronikSensorEntity(
                hass, entry, coordinator, description, description.device_key
            )
            for description in SENSORS
            if coordinator.entity_active(description)
        ),
        True,
    )

    async_add_entities(
        (
            LuxtronikStatusSensorEntity(
                hass, entry, coordinator, description, description.device_key
            )
            for description in SENSORS_STATUS
            if coordinator.entity_active(description)
        ),
        True,
    )

    async_add_entities(
        (
            LuxtronikIndexSensor(
                hass, entry, coordinator, description, description.device_key
            )
            for description in SENSORS_INDEX
            if coordinator.entity_active(description)
        ),
        True,
    )

    async_add_entities(
        (
            LuxtronikPeriodStatSensor(
                hass, entry, coordinator, description, description.device_key
            )
            for description in SENSORS_PERIOD
            if coordinator.entity_active(description)
        ),
        True,
    )


class LuxtronikSensorEntity(LuxtronikEntity, SensorEntity):  # RestoreSensor):
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
        self.hass = hass
        self._sensor_prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"{self._sensor_prefix}_{description.key}"
        )
        self._attr_unique_id = self.entity_id
        self._sensor_data = get_sensor_data(
            coordinator.data, description.luxtronik_key
        )

    def enrich_description(self, d: LuxtronikSensorDescription) -> None:
        super().enrich_description(d)
        d.factor = d.factor or UNIT_FACTOR_MAP.get(d.native_unit_of_measurement)

    async def _data_update(self, event):
        self._handle_coordinator_update()

    def _handle_coordinator_update_internal(
        self, data: LuxtronikCoordinatorData | None = None, use_key: str | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        if (
            not self.coordinator.update_reason_write
            and self.next_update is not None
            and self.next_update > dt_util.utcnow()
        ):
            return
        data = self.coordinator.data if data is None else data
        if data is None:
            return
        self._attr_native_value = get_sensor_data(
            data, use_key or self.entity_description.luxtronik_key
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
        self, data: LuxtronikCoordinatorData | None = None, use_key: str | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        self._handle_coordinator_update_internal(data, use_key)
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
            sl1 = self._get_value(LC.STATUS_LINE_1)
            sl3 = self._get_value(LC.STATUS_LINE_3)
            add_circ_pump = self._get_value(LC.ADDITIONAL_CIRCULATION_PUMP)
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
                DHW_recirculation = self._get_value(LC.DHW_RECIRCULATION_PUMP)
                AddHeat = self._get_value(LC.ADDITIONAL_HEAT_GENERATOR)
                if AddHeat and DHW_recirculation:
                    # more fixes to detect thermal desinfection sequences
                    self._attr_native_value = LuxOperationMode.domestic_water.value
            # endregion Workaround Thermal desinfection with (only) using 2nd heatsource

            # region Workaround Detect passive cooling operation mode
            if self._attr_native_value == LuxOperationMode.no_request.value:
                # detect passive cooling
                if self.coordinator.detect_cooling_present():
                    T_in = self._get_value(LC.FLOW_IN_TEMPERATURE)
                    T_out = self._get_value(LC.FLOW_OUT_TEMPERATURE)
                    T_heat_in = self._get_value(LC.HEAT_SOURCE_INPUT_TEMPERATURE)
                    T_heat_out = self._get_value(
                        LC.HEAT_SOURCE_OUTPUT_TEMPERATURE
                    )
                    Pump = self._get_value(LC.PUMP_FLOW)
                    Flow_WQ = self._get_value(LC.HEAT_SOURCE_FLOW_RATE)
                    if (T_out > T_in) and (T_heat_out > T_heat_in) and (Flow_WQ > 0) and Pump:
                        # LOGGER.info(f"Cooling mode detected!!!")
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


@dataclass
class LuxtronikPeriodStatSensorExtraStoredData(SensorExtraStoredData):
    """Object to hold extra stored data."""

    _last_valid_state: int | float | Decimal | None = None
    _today: int | float | Decimal | None = None
    _yesterday: int | float | Decimal | None = None
    _week: int | float | Decimal | None = None
    _last_week: int | float | Decimal | None = None
    _month: int | float | Decimal | None = None
    _last_month: int | float | Decimal | None = None
    _year: int | float | Decimal | None = None
    _last_year: int | float | Decimal | None = None
    _heating_period: Decimal = Decimal(0)
    _last_heating_period: Decimal = Decimal(0)
    _current_impulse: Decimal = Decimal(0)
    _last_impulse: Decimal = Decimal(0)

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the text data."""
        # return super().as_dict() | asdict(self)
        return asdict(self)

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        # obj = super().from_dict(restored)
        _last_valid_state = Decimal(restored["_last_valid_state"])
        _today = Decimal(restored["_today"])
        _yesterday = Decimal(restored["_yesterday"])
        _week = Decimal(restored["_week"])
        _last_week = Decimal(restored["_last_week"])
        _month = Decimal(restored["_month"])
        _last_month = Decimal(restored["_last_month"])
        _year = Decimal(restored["_year"])
        _last_year = Decimal(restored["_last_year"])
        _heating_period = Decimal(restored["_heating_period"])
        _last_heating_period = Decimal(restored["_last_heating_period"])
        _current_impulse: Decimal = Decimal(restored["_current_impulse"])
        _last_impulse: Decimal = Decimal(restored["_last_impulse"])
        cls(
            _last_valid_state,
            _today,
            _yesterday,
            _week,
            _last_week,
            _month,
            _last_month,
            _year,
            _last_year,
            _heating_period,
            _last_heating_period,
            _current_impulse,
            _last_impulse,
        )


class LuxtronikPeriodStatSensor(LuxtronikSensorEntity, SensorEntity):  # RestoreSensor):
    # region Members
    entity_description: LuxtronikPeriodStatSensorDescription

    _cron_pattern = PERIOD2CRON[DAILY].format(minute=0, hour=0)

    _impulse_active: bool | None = None

    _last_valid_state: Decimal = None
    _today: Decimal = Decimal(0)
    _yesterday: Decimal = Decimal(0)
    _week: Decimal = Decimal(0)
    _last_week: Decimal = Decimal(0)
    _month: Decimal = Decimal(0)
    _last_month: Decimal = Decimal(0)
    _year: Decimal = Decimal(0)
    _last_year: Decimal = Decimal(0)
    _heating_period: Decimal = Decimal(0)
    _last_heating_period: Decimal = Decimal(0)
    _current_impulse: Decimal = Decimal(0)
    _last_impulse: Decimal = Decimal(0)
    # endregion Members

    #    @native_value.setter
    # def native_value(self, value: StateType | date | datetime | Decimal) -> None:
    #     """Set the value reported by the sensor."""
    #     self._attr_native_value = value

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        def handle_event_impulse_active(event):
            self._impulse_active = True

        def handle_event_impulse_inactive(event):
            self._impulse_active = False
            self._last_impulse = self._current_impulse
            self._current_impulse = Decimal(0)

        # if self.entity_description.event_id_impulse_active is not None:
        #     self.hass.bus.listen(
        #         self.entity_description.event_id_impulse_active,
        #         handle_event_impulse_active,
        #     )
        # if self.entity_description.event_id_impulse_inactive is not None:
        #     self.hass.bus.listen(
        #         self.entity_description.event_id_impulse_inactive,
        #         handle_event_impulse_inactive,
        #     )

    @staticmethod
    def _validate_value(
        state: StateType | date | datetime | Decimal | None,
    ) -> Decimal | None:
        """Parse the state as a Decimal if available. Throws DecimalException if the state is not a number."""
        try:
            return (
                None
                if state is None or state in [STATE_UNAVAILABLE, STATE_UNKNOWN]
                else Decimal(state)
            )
        except DecimalException:
            return None

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update_internal(data)
        new_value = self._validate_value(self._attr_native_value)
        if new_value is not None:
            if self._last_valid_state is None:
                self._last_valid_state = new_value
            else:
                adjustment = new_value - self._last_valid_state
                self._today += adjustment
                self._week += adjustment
                self._month += adjustment
                self._year += adjustment
                self._heating_period += adjustment
                if self._impulse_active == True:
                    self._current_impulse += adjustment

            self._last_valid_state = new_value

        self.async_write_ha_state()

    async def _async_reset_meter(self, event):
        """Determine cycle - Helper function for larger than daily cycles."""
        if self._cron_pattern is not None:
            self.async_on_remove(
                async_track_point_in_time(
                    self.hass,
                    self._async_reset_meter,
                    croniter(self._cron_pattern, dt_util.now()).get_next(datetime),
                )
            )
        await self.async_reset_meter(self.entity_id)

    async def async_reset_meter(self, entity_id):
        """Reset meter."""
        if self.entity_id != entity_id:
            return
        LOGGER.debug("Reset utility meter <%s>", self.entity_id)
        last_reset = dt_util.utcnow()

        self._yesterday = self._today
        self._today = Decimal(0)

        day_of_week = last_reset.weekday()  # for 0 is Monday
        if day_of_week == 0:
            self._last_week = self._week
            self._week = Decimal(0)

        if last_reset.day == 1:
            self._last_month = self._month
            self._month = Decimal(0)

            if last_reset.month == 9:
                self._last_heating_period = self._heating_period
                self._heating_period = Decimal(0)

            if last_reset.month == 1:
                self._last_year = self._year
                self._year = Decimal(0)

        self.async_write_ha_state()

    # async def async_added_to_hass(self) -> None:
    #     """Handle entity which will be added."""
    #     await CoordinatorEntity.async_added_to_hass(self)

    #     await super().async_added_to_hass()

    #     if self._cron_pattern is not None:
    #         self.async_on_remove(
    #             async_track_point_in_time(
    #                 self.hass,
    #                 self._async_reset_meter,
    #                 croniter(self._cron_pattern, dt_util.now()).get_next(datetime),
    #             )
    #         )

    #     self.async_on_remove(
    #         async_dispatcher_connect(
    #             self.hass, SIGNAL_RESET_METER, self.async_reset_meter
    #         )
    #     )

    #     if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
    #         # new introduced in 2022.04
    #         self._attr_native_value = last_sensor_data.native_value
    #         self._attr_unit_of_measurement = last_sensor_data.native_unit_of_measurement
    #         # self._last_valid_state = last_sensor_data.last_valid_state

    #     elif state := await self.async_get_last_state():
    #         # legacy to be removed on 2022.10 (we are keeping this to avoid utility_meter counter losses)
    #         try:
    #             self._state = Decimal(state.state)
    #         except InvalidOperation:
    #             LOGGER.error(
    #                 "Could not restore state <%s>. Resetting utility_meter.%s",
    #                 state.state,
    #                 self.name,
    #             )
    #         else:
    #             self._attr_unit_of_measurement = state.attributes.get(
    #                 ATTR_UNIT_OF_MEASUREMENT
    #             )
    #             self._last_valid_state = (
    #                 Decimal(state.attributes[ATTR_LAST_VALID_STATE])
    #                 if state.attributes.get(ATTR_LAST_VALID_STATE)
    #                 and is_number(state.attributes[ATTR_LAST_VALID_STATE])
    #                 else None
    #             )

    @property
    def extra_state_attributes(self):  #  -> dict[str, str]:
        """Return the state attributes of the sensor."""
        state_attr = {
            ATTR_LAST_VALID_STATE: str(self._last_valid_state),
            ATTR_TODAY: str(self._today),
            ATTR_YESTERDAY: str(self._yesterday),
            ATTR_WEEK: str(self._week),
            ATTR_LAST_WEEK: str(self._last_week),
            ATTR_MONTH: str(self._month),
            ATTR_LAST_MONTH: str(self._last_month),
            ATTR_YEAR: str(self._year),
            ATTR_LAST_YEAR: str(self._last_year),
            ATTR_HEATING_PERIOD: str(self._heating_period),
            ATTR_LAST_HEATING_PERIOD: str(self._last_heating_period),
            ATTR_CURRENT_IMPULSE: str(self._current_impulse),
            ATTR_LAST_IMPULSE: str(self._last_impulse),
        }
        return state_attr

    # @property
    # def extra_restore_state_data(self) -> LuxtronikPeriodStatSensorExtraStoredData:
    #     """Return luxtronik climate specific state data to be restored."""
    #     return LuxtronikPeriodStatSensorExtraStoredData(
    #         self._last_valid_state,
    #         self._today,
    #         self._yesterday,
    #         self._week,
    #         self._last_week,
    #         self._month,
    #         self._last_month,
    #         self._year,
    #         self._last_year,
    #         self._heating_period,
    #         self._last_heating_period,
    #         self._current_impulse,
    #         self._last_impulse,
    #     )

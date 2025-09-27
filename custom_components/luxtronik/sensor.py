"""Support for Luxtronik sensors."""

# flake8: noqa: W503
# region Imports
from __future__ import annotations

from datetime import date, datetime, time, timezone
import calendar
from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import ENTITY_ID_FORMAT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow, dt as dt_util

from .base import LuxtronikEntity
from .common import get_sensor_data
from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    DeviceKey,
    LuxCalculation as LC,
    LuxOperationMode,
    LuxStatus1Option,
    LuxStatus3Option,
    SensorAttrKey as SA,
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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Sync callback registered with DataUpdateCoordinator."""
        self.hass.async_create_task(self._async_handle_coordinator_update())

    async def _async_handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None, use_key: str | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        await self._async_handle_coordinator_update_internal(data, use_key)
        await super()._async_handle_coordinator_update()

    async def _async_handle_coordinator_update_internal(
        self, data: LuxtronikCoordinatorData | None = None, use_key: str | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data if data is None else data
        if data is None:
            return
        self._attr_native_value = self._get_value(self.entity_description.luxtronik_key)

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

class LuxtronikStatusSensorEntity(LuxtronikSensorEntity, SensorEntity):
    """Luxtronik Status Sensor with extended attributes and EVU tracking."""

    _unrecorded_attributes = frozenset(
        LuxtronikSensorEntity._unrecorded_attributes
        | {
            SA.STATUS_TEXT,
            SA.STATUS_RAW,
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
        super().__init__(hass, entry, coordinator, description, device_info_ident)
        self._evu_tracker = LuxtronikEVUTracker()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Sync callback registered with DataUpdateCoordinator."""
        self.hass.async_create_task(self._async_handle_coordinator_update())

    async def _async_handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        await super()._async_handle_coordinator_update(data)

        # Update EVU tracker
        self._evu_tracker.update(self._attr_native_value)

        # Workaround logic for Luxtronik quirks
        sl1 = self._get_value(LC.C0117_STATUS_LINE_1)
        sl3 = self._get_value(LC.C0119_STATUS_LINE_3)
        add_circ_pump = self._get_value(LC.C0047_ADDITIONAL_CIRCULATION_PUMP)

        s1_workaround = [
            LuxStatus1Option.heatpump_idle,
            LuxStatus1Option.pump_forerun,
            LuxStatus1Option.heatpump_coming,
        ]
        s3_workaround = [
            LuxStatus3Option.no_request,
            LuxStatus3Option.unknown,
            LuxStatus3Option.none,
            LuxStatus3Option.grid_switch_on_delay,
            None,
        ]

        if sl1 in s1_workaround and sl3 in s3_workaround and not add_circ_pump:
            self._attr_native_value = LuxOperationMode.no_request.value

        if sl3 == LuxStatus3Option.thermal_desinfection:
            self._attr_native_value = LuxOperationMode.domestic_water.value

        if sl3 in [LuxStatus3Option.no_request, LuxStatus3Option.cycle_lock]:
            DHW_recirculation = self._get_value(LC.C0038_DHW_RECIRCULATION_PUMP)
            AddHeat = self._get_value(LC.C0048_ADDITIONAL_HEAT_GENERATOR)
            if AddHeat and DHW_recirculation:
                self._attr_native_value = LuxOperationMode.domestic_water.value

        # Update attributes
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

        evu_event_minutes = self._evu_tracker.get_next_event_minutes()
        if evu_event_minutes is None:
            return f"{line_1} {line_2} {status_time}."

        if self.native_value == LuxOperationMode.evu.value:
            text_locale = self.platform.platform_data.platform_translations.get(
                f"component.{DOMAIN}.entity.sensor.status.state_attributes.evu_text.state.evu_until"
            )
            evu_until = text_locale.format(evu_time=evu_event_minutes)
            return f"{evu_until} {line_1} {line_2} {status_time}."

        if evu_event_minutes <= 30:
            text_locale = self.platform.platform_data.platform_translations.get(
                f"component.{DOMAIN}.entity.sensor.status.state_attributes.evu_text.state.evu_in"
            )
            evu_in = text_locale.format(evu_time=evu_event_minutes)
            return f"{line_1} {line_2} {status_time}. {evu_in}"

        return f"{line_1} {line_2} {status_time}."


class LuxtronikIndexSensor(LuxtronikSensorEntity, SensorEntity):
    _min_index = 0
    _max_index = 4

    entity_description: LuxtronikIndexSensorDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Sync callback registered with DataUpdateCoordinator."""
        self.hass.async_create_task(self._async_handle_coordinator_update())

    async def _async_handle_coordinator_update(
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

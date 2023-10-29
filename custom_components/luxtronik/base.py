"""Luxtronik Home Assistant Base Device Model."""
# region Imports
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.backports.enum import StrEnum
from homeassistant.components.sensor import RestoreSensor
from homeassistant.components.water_heater import STATE_HEAT_PUMP
from homeassistant.const import STATE_OFF, UnitOfTemperature, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util.dt import utcnow

from .common import get_sensor_data
from .const import (
    DeviceKey,
    LOGGER,
    LuxCalculation as LC,
    LuxMode,
    LuxOperationMode,
    LuxParameter as LP,
    SensorAttrFormat,
    SensorAttrKey as SA,
)
from .coordinator import LuxtronikCoordinator
from .model import LuxtronikEntityAttributeDescription, LuxtronikEntityDescription

# endregion Imports


class LuxtronikEntity(CoordinatorEntity[LuxtronikCoordinator], RestoreEntity):
    """Luxtronik base device."""

    entity_description: LuxtronikEntityDescription
    next_update: datetime | None = None

    _attr_cache: dict[SA, Any] = {}
    _entity_component_unrecorded_attributes = frozenset(
        {
            SA.LUXTRONIK_KEY,
        }
    )

    def __init__(
        self,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikEntityDescription,
        device_info_ident: DeviceKey,
    ) -> None:
        """Init LuxtronikEntity."""
        super().__init__(coordinator=coordinator)
        self._device_info_ident = device_info_ident
        self._attr_extra_state_attributes = {
            SA.LUXTRONIK_KEY: f"{description.luxtronik_key.name[1:5]} {description.luxtronik_key.value}"
        }
        for field in description.__dataclass_fields__:
            if field.startswith("luxtronik_key_"):
                value = description.__getattribute__(field)
                if value is None:
                    pass
                elif isinstance(value, StrEnum):
                    self._attr_extra_state_attributes[
                        field
                    ] = f"{value.name[1:5]} {value.value}"
                else:
                    self._attr_extra_state_attributes[field] = value
        if description.translation_key is None:
            description.translation_key = description.key.value
        if description.entity_registry_enabled_default:
            description.entity_registry_enabled_default = coordinator.entity_visible(
                description
            )
        self.entity_description = description
        self._attr_device_info = coordinator.get_device(device_info_ident)

        translation_key = (
            description.key.value
            if description.translation_key_name is None
            else description.translation_key_name
        )
        description.translation_key = translation_key
        description.has_entity_name = True
        self._attr_state = self._get_value(description.luxtronik_key)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Force device name:
        self._attr_device_info = self.coordinator.get_device(
            self._device_info_ident, self.platform
        )

        try:
            last_state = await self.async_get_last_state()
            if last_state is None:
                return
            self._attr_state = last_state.state

            for attr in self.entity_description.extra_attributes:
                if not attr.restore_on_startup or attr.key not in last_state.attributes:
                    continue
                self._attr_cache[attr.key] = self._restore_attr_value(
                    last_state.attributes[attr.key]
                )

            last_extra_data = await self.async_get_last_extra_data()
            if last_extra_data is not None:
                data: dict[str, Any] = last_extra_data.as_dict()
                for attr in data:
                    setattr(self, attr, data.get(attr))

            data_updated = f"{self.entity_id}_data_updated"
            async_dispatcher_connect(
                self.hass, data_updated, self._schedule_immediate_update
            )
        except Exception as err:
            LOGGER.error(
                "Could not restore latest data (async_added_to_hass)",
                exc_info=err,
            )

    def _restore_attr_value(self, value: Any | None) -> Any:
        return value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        descr = self.entity_description
        value = self._get_value(descr.luxtronik_key)
        if value is None:
            pass
        elif isinstance(value, datetime) and value.tzinfo is None:
            # Ensure timezone:
            time_zone = dt_util.get_time_zone(self.hass.config.time_zone)
            value = value.replace(tzinfo=time_zone)

        self._attr_state = value

        # Calc icon:
        icon_state = self._attr_state
        if hasattr(self, "_attr_is_on"):
            icon_state = self._attr_is_on
        elif hasattr(self, "_attr_current_lux_operation"):
            icon_state = self._attr_current_lux_operation
        if descr.icon_by_state is not None and icon_state in descr.icon_by_state:
            self._attr_icon = descr.icon_by_state.get(icon_state)
        else:
            self._attr_icon = descr.icon
        if hasattr(self, "_attr_current_operation"):
            if self._attr_current_operation == STATE_OFF:
                self._attr_icon += "-off"
            elif self._attr_current_operation == STATE_HEAT_PUMP:
                self._attr_icon += "-auto"

        self._enrich_extra_attributes()

        if descr.update_interval is not None and (
            self.next_update is None or self.next_update < utcnow()
        ):
            self.next_update = utcnow() + descr.update_interval
        super()._handle_coordinator_update()

    def _enrich_extra_attributes(self) -> None:
        for attr in self.entity_description.extra_attributes:
            if attr.format is None and (
                attr.luxtronik_key is None or attr.luxtronik_key == LP.UNSET
            ):
                continue
            self._attr_extra_state_attributes[attr.key.value] = self.formatted_data(
                attr
            )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    def formatted_data(self, attr: LuxtronikEntityAttributeDescription) -> str:
        """Calculate the attribute value."""
        value = self._get_value(attr.luxtronik_key)
        if value is None:
            return ""
        if isinstance(value, datetime) and value.tzinfo is None:
            # Ensure timezone:
            time_zone = dt_util.get_time_zone(self.hass.config.time_zone)
            value = value.replace(tzinfo=time_zone)
        if attr.format is None:
            return str(value)
        if attr.format == SensorAttrFormat.HOUR_MINUTE:
            minutes: int = 0
            minutes, _ = divmod(int(value), 60)
            hours, minutes = divmod(minutes, 60)
            return f"{hours:01.0f}:{minutes:02.0f} {UnitOfTime.HOURS}"
        if attr.format == SensorAttrFormat.CELSIUS_TENTH:
            return f"{value/10:.1f} {UnitOfTemperature.CELSIUS}"
        if attr.format == SensorAttrFormat.SWITCH_GAP:
            flow_out_target = float(
                self._get_value(LC.C0012_FLOW_OUT_TEMPERATURE_TARGET)
            )
            flow_out = float(value)
            hyst = float(self._get_value(LP.P0088_HEATING_HYSTERESIS)) * 0.1

            if self._get_value(LC.C0080_STATUS) == LuxOperationMode.heating:
                return f"{flow_out + hyst - flow_out_target:.1f} {UnitOfTemperature.KELVIN}"
            if self._get_value(LP.P0003_MODE_HEATING) != LuxMode.off:
                return f"{flow_out - hyst - flow_out_target:.1f} {UnitOfTemperature.KELVIN}"
            return ""

        return str(value)

    def _get_value(self, key: LC | LP) -> Any:
        return get_sensor_data(self.coordinator.data, key)

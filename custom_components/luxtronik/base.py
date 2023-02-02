"""Luxtronik Home Assistant Base Device Model."""
# region Imports
from __future__ import annotations

from contextlib import suppress
from datetime import datetime
import locale
from typing import Any

from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .common import get_sensor_data
from .const import (
    DeviceKey,
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

    _attr_cache: dict[SA, Any] = {}

    def __init__(
        self,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikEntityDescription,
        device_info_ident: DeviceKey,
    ) -> None:
        """Init LuxtronikEntity."""
        super().__init__(coordinator=coordinator)
        self._attr_extra_state_attributes = {
            SA.LUXTRONIK_KEY: f"{description.luxtronik_key.name[1:5]} {description.luxtronik_key.value}"
        }
        for field in description.__dataclass_fields__:
            if field.startswith("luxtronik_key_"):
                value = description.__getattribute__(field)
                if value is not None:
                    self._attr_extra_state_attributes[
                        field
                    ] = f"{value.name[1:5]} {value.value}"
        if description.translation_key is None:
            description.translation_key = description.key
        if description.entity_registry_enabled_default:
            description.entity_registry_enabled_default = coordinator.entity_visible(
                description
            )
        self.entity_description = description
        self._attr_device_info = coordinator.device_infos[device_info_ident.value]

        translation_key = (
            description.key
            if description.translation_key_name is None
            else description.translation_key_name
        )
        self._attr_name = coordinator.get_device_entity_title(
            translation_key, description.platform
        )
        self._attr_state = self._get_value(description.luxtronik_key)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # try set locale for local formatting
        with suppress(locale.Error):
            ha_locale = f"{self.hass.config.language}_{self.hass.config.country}"
            locale.setlocale(locale.LC_ALL, locale.normalize(ha_locale))
        state = await self.async_get_last_state()
        if state is None:
            return
        self._attr_state = state.state

        for attr in self.entity_description.extra_attributes:
            if not attr.restore_on_startup or attr.key not in state.attributes:
                continue
            self._attr_cache[attr.key] = self._restore_attr_value(
                state.attributes[attr.key]
            )

        data_updated = f"{self.entity_id}_data_updated"
        async_dispatcher_connect(
            self.hass, data_updated, self._schedule_immediate_update
        )

    def _restore_attr_value(self, value: Any | None) -> Any:
        return value

    @property
    def icon(self) -> str | None:
        """Return the icon to be used for this entity."""
        if self.entity_description.icon_by_state is not None:
            if self._attr_state in self.entity_description.icon_by_state:
                return self.entity_description.icon_by_state.get(self._attr_state)
        return super().icon

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value = self._get_value(self.entity_description.luxtronik_key)
        if value is None:
            pass
        elif isinstance(value, datetime) and value.tzinfo is None:
            # Ensure timezone:
            time_zone = dt_util.get_time_zone(self.hass.config.time_zone)
            value = value.replace(tzinfo=time_zone)

        self._attr_state = value

        for attr in self.entity_description.extra_attributes:
            if attr.format is None and (
                attr.luxtronik_key is None or attr.luxtronik_key == LP.UNSET
            ):
                continue
            self._attr_extra_state_attributes[attr.key.value] = self.formatted_data(
                attr
            )

        super()._handle_coordinator_update()

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

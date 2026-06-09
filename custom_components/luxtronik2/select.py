"""Support for Luxtronik selectors."""

from __future__ import annotations

from dataclasses import replace

from homeassistant.components.select import (
    ENTITY_ID_FORMAT,  # pyright: ignore[reportAttributeAccessIssue]
    SelectEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LuxtronikConfigEntry
from .base import LuxtronikEntity
from .common import get_sensor_data, key_exists
from .const import (
    CONF_HA_SENSOR_PREFIX,
    DAY_NAME_TO_PARAM,
    DAY_SELECTOR_OPTIONS,
    LOGGER,
    DeviceKey,
    LuxParameter as LP,
    LuxPoolPVMode,
    SensorKey as SK,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikSelectEntityDescription
from .select_entities_predefined import SELECT_ENTITIES

PARALLEL_UPDATES = 1


def _normalize_select_option(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuxtronikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Luxtronik Select entities."""
    coordinator = entry.runtime_data

    # Ensure coordinator has valid data before adding entities
    if not coordinator.last_update_success:
        return

    unavailable_keys = [
        i.luxtronik_key
        for i in SELECT_ENTITIES
        if not key_exists(coordinator.data, i.luxtronik_key)
    ]
    if unavailable_keys:
        # Not all models/firmware versions support every parameter;
        # missing keys are expected and not an error.
        LOGGER.debug("Not present in Luxtronik data, skipping: %s", unavailable_keys)

    # Descriptions are defined in select_entities_predefined.py

    # ---- Build entities in a compact, data-driven way -----------------

    select_descriptions = build_select_descriptions(coordinator)

    async_add_entities(
        [
            LuxtronikThermalDesinfectionDaySelector(
                entry=entry,
                coordinator=coordinator,
                description=desc,
                device_info_ident=desc.device_key,
            )
            if desc.key == SK.THERMAL_DESINFECTION_DAY
            else LuxtronikModeSelector(
                entry=entry,
                coordinator=coordinator,
                description=desc,
                device_info_ident=desc.device_key,
            )
            for desc in select_descriptions
            if (
                coordinator.entity_active(desc)
                and key_exists(coordinator.data, desc.luxtronik_key)
            )
        ],
        True,
    )


def build_select_descriptions(
    coordinator: LuxtronikCoordinator,
) -> list[LuxtronikSelectEntityDescription]:
    """Return select descriptions with PV mode options adjusted at runtime."""
    descriptions: list[LuxtronikSelectEntityDescription] = []
    for desc in SELECT_ENTITIES:
        if desc.key == SK.PV_MODE_SELECTOR:
            descriptions.append(_build_pv_mode_selector_description(coordinator, desc))
        else:
            descriptions.append(desc)
    return descriptions


def _build_pv_mode_selector_description(
    coordinator: LuxtronikCoordinator,
    description: LuxtronikSelectEntityDescription,
) -> LuxtronikSelectEntityDescription:
    value = coordinator.get_value(description.luxtronik_key)

    if value == LuxPoolPVMode.pv_off:
        options = [
            m.value
            for m in (
                LuxPoolPVMode.automatic,
                LuxPoolPVMode.pv_off,
            )
        ]
    elif value in (
        LuxPoolPVMode.pool_party,
        LuxPoolPVMode.pool_holidays,
        LuxPoolPVMode.pool_off,
    ):
        options = [
            m.value
            for m in (
                LuxPoolPVMode.automatic,
                LuxPoolPVMode.pool_off,
                LuxPoolPVMode.pool_party,
                LuxPoolPVMode.pool_holidays,
            )
        ]
    else:
        return description

    return replace(description, options=options)


class LuxtronikThermalDesinfectionDaySelector(  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    LuxtronikEntity[LuxtronikSelectEntityDescription], SelectEntity
):
    """Luxtronik Thermal Desinfection Day Selector Entity."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikSelectEntityDescription,
        device_info_ident: DeviceKey,
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
        )

        self._attr_options = DAY_SELECTOR_OPTIONS
        self._attr_current_option = "none"
        self._attr_entity_category = EntityCategory.CONFIG

        # ---- DO NOT TOUCH: manual entity_id + unique_id approach --------
        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_thermal_desinfection_day")
        self._attr_unique_id = self.entity_id

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
        data = self.coordinator.data if data is None else data
        if data is None:
            return

        selected_day = "none"
        for day, param_enum in DAY_NAME_TO_PARAM.items():
            param = param_enum.value
            if str(get_sensor_data(data, param)) == "1":
                selected_day = day
                break

        if self._attr_current_option != selected_day:
            self._attr_current_option = selected_day
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Handle selection of a new day."""
        self._attr_current_option = option
        data = self.coordinator.data
        if data is None:
            return

        for day, param_enum in DAY_NAME_TO_PARAM.items():
            param = param_enum.value
            desired_value = 0 if option == "none" else 1 if day == option else 0
            current_value = int(get_sensor_data(data, param))

            if current_value != desired_value:
                updated_data = await self.coordinator.async_write(
                    param.split(".")[1],
                    desired_value,
                )
                self._handle_coordinator_update(updated_data)

    async def async_update(self) -> None:
        """Read current day from heat pump and update selected option."""
        data = self.coordinator.data
        if data is None:
            return

        selected_day = "none"
        for day, param_enum in DAY_NAME_TO_PARAM.items():
            param = param_enum.value
            if str(get_sensor_data(data, param)) == "1":
                selected_day = day
                break

        self._attr_current_option = selected_day


class LuxtronikModeSelector(
    LuxtronikEntity[LuxtronikSelectEntityDescription], SelectEntity
):
    """Generic Luxtronik Mode Selector."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikSelectEntityDescription,
        device_info_ident: DeviceKey,
        lux_parameter: str | LP | None = None,
        options: list[str] | None = None,
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=device_info_ident,
        )

        self._lux_parameter = (
            description.luxtronik_key if lux_parameter is None else lux_parameter
        )
        raw_options = list(options or description.options or [])
        self._option_to_raw = {
            _normalize_select_option(raw_option): raw_option
            for raw_option in raw_options
        }
        self._attr_options = list(self._option_to_raw)
        self._attr_current_option = None

        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        super()._handle_coordinator_update()

        data = self.coordinator.data if data is None else data
        if data is None:
            return

        current_raw = str(get_sensor_data(data, self._lux_parameter))
        current = _normalize_select_option(current_raw)

        LOGGER.debug(
            "%s raw value from coordinator: %r, normalized value: %r",
            self.entity_id,
            current_raw,
            current,
        )

        if current not in self._attr_options:
            LOGGER.warning(
                "%s value %r not in options %r",
                self.entity_id,
                current_raw,
                self._attr_options,
            )
            return

        if self._attr_current_option != current:
            self._attr_current_option = current
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            LOGGER.warning(
                "Selected value %r not in options %r",
                option,
                self._attr_options,
            )
            return

        LOGGER.debug("Setting %s to %r", self.entity_id, option)

        self._attr_current_option = option
        raw_option = self._option_to_raw.get(option, option)

        updated_data = await self.coordinator.async_write(
            str(self._lux_parameter).split(".")[1],
            raw_option,
        )
        self._handle_coordinator_update(updated_data)

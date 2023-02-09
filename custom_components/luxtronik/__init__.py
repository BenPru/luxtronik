"""The Luxtronik heatpump integration."""
# region Imports
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform as P
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_registry import (
    EntityRegistry,
    RegistryEntry,
    async_get,
)

from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SensorKey as SK,
)
from .coordinator import LuxtronikCoordinator

# endregion Imports


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Luxtronik from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # Create API instance
    coordinator = LuxtronikCoordinator.connect(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    entry.async_on_unload(entry.add_update_listener(update_listener))

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = {}
    data[entry.entry_id][CONF_COORDINATOR] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Trigger a refresh again now that all platforms have registered
    hass.async_create_task(coordinator.async_refresh())

    # hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]
        await coordinator.async_shutdown()

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        coordinator = LuxtronikCoordinator.connect(hass, config_entry)

        new = {**config_entry.data}
        if CONF_HA_SENSOR_PREFIX not in new:
            new[CONF_HA_SENSOR_PREFIX] = "luxtronik"
        config_entry.unique_id = coordinator.unique_id
        config_entry.supports_remove_device = True

        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new)

    if config_entry.version == 2:
        _delete_legacy_devices(hass, config_entry)

        new = {**config_entry.data}
        config_entry.version = 3
        hass.config_entries.async_update_entry(config_entry, data=new)

    if config_entry.version == 3:
        # Ensure sensor prefix:
        if CONF_HA_SENSOR_PREFIX not in config_entry.data and (
            DOMAIN == "luxtronik2"
            or len(hass.config_entries.async_entries("luxtronik2")) > 0
        ):
            new_data = {**config_entry.data, CONF_HA_SENSOR_PREFIX: "luxtronik2"}
        else:
            new_data = {**config_entry.data}
        config_entry.version = 4
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    if config_entry.version == 4:
        # Ensure sensor prefix:
        ent_reg = async_get(hass)
        prefix = config_entry.data[CONF_HA_SENSOR_PREFIX]

        def _up(ident: str, new_id: SK, platform: P = P.SENSOR) -> None:
            entity_id = f"{platform}.{prefix}_{ident}"
            new_ident = f"{platform}.{prefix}_{new_id}"
            try:
                ent_reg.async_update_entity(
                    entity_id, new_entity_id=new_ident, new_unique_id=new_ident
                )
            except (KeyError, ValueError) as err:
                LOGGER.warning(
                    "Could not rename entity %s->%s", entity_id, new_ident, exc_info=err
                )

        _up("heat_amount_domestic_water", SK.DHW_HEAT_AMOUNT)
        _up("domestic_water_energy_input", SK.DHW_ENERGY_INPUT)
        _up("domestic_water_temperature", SK.DHW_TEMPERATURE)
        _up("operation_hours_domestic_water", SK.DHW_OPERATION_HOURS)
        _up("domestic_water_target_temperature", SK.DHW_TARGET_TEMPERATURE, P.NUMBER)
        _up("domestic_water_hysteresis", SK.DHW_HYSTERESIS, P.NUMBER)
        _up(
            "domestic_water_thermal_desinfection_target",
            SK.DHW_THERMAL_DESINFECTION_TARGET,
            P.NUMBER,
        )
        _up(
            "domestic_water_recirculation_pump",
            SK.DHW_RECIRCULATION_PUMP,
            P.BINARY_SENSOR,
        )
        _up(
            "domestic_water_circulation_pump",
            SK.DHW_CIRCULATION_PUMP,
            P.BINARY_SENSOR,
        )
        _up("domestic_water_charging_pump", SK.DHW_CHARGING_PUMP, P.BINARY_SENSOR)

        new_data = {**config_entry.data}
        config_entry.version = 5
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


def _identifiers_exists(
    identifiers_list: list[set[tuple[str, str]]], identifiers: set[tuple[str, str]]
) -> bool:
    for ident in identifiers_list:
        if ident == identifiers:
            return True
    return False


def _delete_legacy_devices(hass: HomeAssistant, config_entry: ConfigEntry):
    coordinator = LuxtronikCoordinator.connect(hass, config_entry)
    dr_instance = dr.async_get(hass)
    devices: list[dr.DeviceEntry] = dr.async_entries_for_config_entry(
        dr_instance, config_entry.entry_id
    )
    identifiers_list = []
    for device_info in coordinator.device_infos.values():
        identifiers_list.append(device_info["identifiers"])
    for device_entry in devices:
        if not _identifiers_exists(identifiers_list, device_entry.identifiers):
            dr_instance.async_remove_device(device_entry.id)

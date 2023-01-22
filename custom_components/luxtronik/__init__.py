"""The Luxtronik heatpump integration."""
# region Imports
from homeassistant.config_entries import ConfigEntry, ConfigEntryDisabler
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_COORDINATOR, CONF_HA_SENSOR_PREFIX, DOMAIN, LOGGER, PLATFORMS
from .coordinator import LuxtronikCoordinator

# endregion Imports


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    coordinator = LuxtronikCoordinator.connect(hass, config_entry)

    await coordinator.async_config_entry_first_refresh()
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    data = hass.data.setdefault(DOMAIN, {})
    data[config_entry.entry_id] = {}
    data[config_entry.entry_id][CONF_COORDINATOR] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Trigger a refresh again now that all platforms have registered
    hass.async_create_task(coordinator.async_refresh())
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        data = hass.data[DOMAIN].pop(config_entry.entry_id)
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
    identifiers_list = list()
    for device in coordinator.device_infos.values():
        identifiers_list.append(device["identifiers"])
    for device in devices:
        if not _identifiers_exists(identifiers_list, device.identifiers):
            dr_instance.async_remove_device(device.id)

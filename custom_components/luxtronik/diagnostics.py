"""Diagnostics support for Luxtronik."""

# region Imports
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from async_timeout import timeout
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_COORDINATOR, DOMAIN
from .coordinator import LuxtronikCoordinator
from .common import async_get_mac_address

# endregion Imports

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""
    data: dict = hass.data[DOMAIN][entry.entry_id]
    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]

    # Optionally refresh data to ensure it's up to date
    await coordinator.async_request_refresh()

    mac: str | None = None
    async with timeout(10):
        mac = await async_get_mac_address(hass, entry.data[CONF_HOST])

    entry_data = async_redact_data(entry.as_dict(), TO_REDACT)
    if "data" not in entry_data:
        entry_data["data"] = {}
    if mac is not None:
        entry_data["data"]["mac"] = mac[:9] + "*"

    diag_data = {
        "entry": entry_data,
        "devices": coordinator.device_infos,
        "parameters": _dump_items(coordinator.data.parameters.parameters),
        "calculations": _dump_items(coordinator.data.calculations.calculations),
        "visibilities": _dump_items(coordinator.data.visibilities.visibilities),
    }
    return diag_data


def _dump_items(items: dict) -> dict:
    dump = {}
    for index, item in sorted(items.items()):
        dump[f"{index:<4d} {item.name:<60}"] = f"{item}"
    return dump

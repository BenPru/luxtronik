"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from .const import SensorAttrKey


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude attributes from being recorded in the database."""
    exclude = set[str]()
    for attr in SensorAttrKey:
        exclude.add(attr.value)
    return exclude

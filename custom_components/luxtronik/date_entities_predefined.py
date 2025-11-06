from homeassistant.helpers.entity import EntityCategory

from .const import (
    DeviceKey,
    LuxParameter as LP,
    SensorKey as SK,
)
from .model import (
    LuxtronikDateEntityDescription,
)


CALENDAR_ENTITIES: list[LuxtronikDateEntityDescription] = [
    LuxtronikDateEntityDescription(
        key=SK.AWAY_DHW_STARTDATE,
        luxtronik_key=LP.P0732_AWAY_DHW_STARTDATE,
        device_key=DeviceKey.domestic_water,
        entity_category=EntityCategory.CONFIG,
    ),
    LuxtronikDateEntityDescription(
        key=SK.AWAY_DHW_ENDDATE,
        luxtronik_key=LP.P0007_AWAY_DHW_ENDDATE,
        device_key=DeviceKey.domestic_water,
        entity_category=EntityCategory.CONFIG,
    ),
    LuxtronikDateEntityDescription(
        key=SK.AWAY_HEATING_STARTDATE,
        luxtronik_key=LP.P0731_AWAY_HEATING_STARTDATE,
        device_key=DeviceKey.heating,
        entity_category=EntityCategory.CONFIG,
    ),
    LuxtronikDateEntityDescription(
        key=SK.AWAY_HEATING_ENDDATE,
        luxtronik_key=LP.P0006_AWAY_HEATING_ENDDATE,
        device_key=DeviceKey.heating,
        entity_category=EntityCategory.CONFIG,
    ),
]

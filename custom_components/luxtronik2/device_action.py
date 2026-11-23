"""Device action for rebuilding the EVU schedule from recorded status history."""

from homeassistant.components.device_automation import async_validate_entity_schema
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN, SERVICE_RECALCULATE_EVU, SensorKey
from .schema_compat import vol

_ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_RECALCULATE_EVU,
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
    }
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """Offer the action only on the device owning an enabled status sensor."""
    registry = er.async_get(hass)
    return [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.id,
            CONF_TYPE: SERVICE_RECALCULATE_EVU,
        }
        for entry in er.async_entries_for_device(registry, device_id)
        if entry.platform == DOMAIN
        and entry.domain == "sensor"
        and entry.translation_key == SensorKey.STATUS
        and entry.disabled_by is None
    ]


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Resolve renamed entities and reject unrelated entities or devices."""
    config = async_validate_entity_schema(hass, config, _ACTION_SCHEMA)
    entry = er.async_get(hass).async_get(config[CONF_ENTITY_ID])
    if (
        entry is None
        or entry.platform != DOMAIN
        or entry.domain != "sensor"
        or entry.translation_key != SensorKey.STATUS
        or entry.device_id != config[CONF_DEVICE_ID]
        or entry.disabled_by is not None
    ):
        raise vol.Invalid(
            "An enabled Luxtronik status sensor on this device is required"
        )
    return config


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Rebuild the selected heat pump's EVU schedule without device writes."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RECALCULATE_EVU,
        {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]},
        blocking=True,
        context=context,
    )

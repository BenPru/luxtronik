"""EVU device action discovery, targeting and execution."""

from unittest.mock import AsyncMock

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
)
from homeassistant.core import Context
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luxtronik2.const import DOMAIN, SERVICE_RECALCULATE_EVU
from custom_components.luxtronik2.device_action import (
    async_call_action_from_config,
    async_get_actions,
    async_validate_action_config,
)
from custom_components.luxtronik2.schema_compat import vol


async def test_device_action_tracks_renamed_status_and_rejects_other_devices(hass):
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    device = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "heatpump")}
    )
    registry = er.async_get(hass)
    status = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "status",
        config_entry=entry,
        device_id=device.id,
        translation_key="status",
        suggested_object_id="my_heatpump",
    )
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "smart_grid_status",
        config_entry=entry,
        device_id=device.id,
        translation_key="smart_grid_status",
    )
    actions = await async_get_actions(hass, device.id)
    assert len(actions) == 1
    registry.async_update_entity(status.entity_id, new_entity_id="sensor.renamed_wp")
    config = await async_validate_action_config(hass, actions[0])
    assert config[CONF_ENTITY_ID] == "sensor.renamed_wp"
    with pytest.raises(vol.Invalid):
        await async_validate_action_config(
            hass, {**actions[0], CONF_DEVICE_ID: "another_device"}
        )
    assert await async_get_actions(hass, "another_device") == []


async def test_device_action_calls_targeted_service_with_context(hass):
    handler = AsyncMock()
    hass.services.async_register(DOMAIN, SERVICE_RECALCULATE_EVU, handler)
    context = Context()
    await async_call_action_from_config(
        hass,
        {
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: SERVICE_RECALCULATE_EVU,
            CONF_DEVICE_ID: "heatpump",
            CONF_ENTITY_ID: "sensor.my_status",
        },
        {},
        context,
    )
    call = handler.call_args.args[0]
    assert call.data == {ATTR_ENTITY_ID: "sensor.my_status"}
    assert call.context is context

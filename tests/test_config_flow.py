import pytest
pytestmark = pytest.mark.enable_custom_integrations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.luxtronik.config_flow import LuxtronikFlowHandler, LuxtronikOptionsFlowHandler
from custom_components.luxtronik.const import DOMAIN, DEFAULT_PORT


@pytest.fixture
def mock_hass():
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    hass.config_entries.async_update_entry = AsyncMock()
    hass.config_entries.async_reload = AsyncMock()
    return hass

@pytest.fixture
def flow_handler(mock_hass):
    handler = LuxtronikFlowHandler()
    handler.hass = mock_hass
    return handler

@pytest.mark.asyncio
async def test_async_step_user_with_available_devices(flow_handler):
    flow_handler._async_current_entries = MagicMock(return_value=[])
    flow_handler._discover_devices = AsyncMock(return_value=[("192.168.1.100", 8888)])

    result = await flow_handler.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "select_devices"

@pytest.mark.asyncio
async def test_async_step_user_with_no_available_devices(flow_handler):
    flow_handler._async_current_entries = MagicMock(return_value=[
        MagicMock(data={CONF_HOST: "192.168.1.100", CONF_PORT: 8888})
    ])
    flow_handler._discover_devices = AsyncMock(return_value=[("192.168.1.100", 8888)])

    result = await flow_handler.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "manual_entry"

@pytest.mark.asyncio
async def test_async_step_select_devices_success(flow_handler):
    flow_handler._connect_and_get_coordinator = AsyncMock(return_value=MagicMock(unique_id="123"))
    flow_handler._set_unique_id_or_abort = AsyncMock(return_value=True)

    result = await flow_handler.async_step_select_devices({"selected_devices": ["192.168.1.100:8888"]})

    assert result["type"] == "create_entry"
    assert result["title"] == "192.168.1.100:8888"

@pytest.mark.asyncio
async def test_async_step_manual_entry_success(flow_handler):
    flow_handler._connect_and_get_coordinator = AsyncMock(return_value=MagicMock(unique_id="123"))
    flow_handler._set_unique_id_or_abort = AsyncMock(return_value=True)

    result = await flow_handler.async_step_manual_entry({CONF_HOST: "192.168.1.100", CONF_PORT: 8888})

    assert result["type"] == "create_entry"
    assert result["title"] == "192.168.1.100:8888"

@pytest.mark.asyncio
async def test_async_step_dhcp_success(flow_handler):
    flow_handler._discover_devices = AsyncMock(return_value=[("192.168.1.100", 8888)])
    flow_handler._connect_and_get_coordinator = AsyncMock(return_value=MagicMock(unique_id="123"))
    flow_handler._set_unique_id_or_abort = AsyncMock(return_value=True)

    dhcp_info = MagicMock(ip="192.168.1.100", hostname="luxtronik")
    result = await flow_handler.async_step_dhcp(dhcp_info)

    assert result["type"] == "create_entry"
    assert result["title"] == "192.168.1.100:8888"

@pytest.mark.asyncio
async def test_options_flow_update_options():
    config_entry = MagicMock(data={CONF_HOST: "192.168.1.100", CONF_PORT: 8888}, options={})
    handler = LuxtronikOptionsFlowHandler(config_entry)
    handler.hass = MagicMock()
    handler.hass.config_entries.async_update_entry = AsyncMock()
    handler.hass.config_entries.async_reload = AsyncMock()

    result = await handler.async_step_user({})

    assert result["type"] == "create_entry"

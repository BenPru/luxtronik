import pytest
from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant
from custom_components.luxtronik.config_flow import LuxtronikOptionsFlowHandler
from custom_components.luxtronik.const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HOST,
    CONF_PORT,
)


@pytest.fixture
def mock_config_entry():
    class MockConfigEntry:
        data = {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 8888,
        }
        options = {}
        entry_id = "test_entry"

    return MockConfigEntry()


@pytest.fixture
def mock_connect(monkeypatch):
    class MockCoordinator:
        manufacturer = "Luxtronik"
        model = "HP"
        serial_number = "123456789"

    monkeypatch.setattr(
        "custom_components.luxtronik.coordinator.LuxtronikCoordinator.connect",
        lambda hass, config: MockCoordinator(),
    )
    return MockCoordinator()


@pytest.mark.asyncio
async def test_options_flow_form_rendering(
    hass: HomeAssistant, mock_config_entry, mock_connect
):
    flow = LuxtronikOptionsFlowHandler(mock_config_entry)
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "data_schema" in result


@pytest.mark.asyncio
async def test_options_flow_updates_options(
    hass: HomeAssistant, mock_config_entry, mock_connect
):
    flow = LuxtronikOptionsFlowHandler(mock_config_entry)
    flow.hass = hass

    user_input = {CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.indoor_temp"}

    result = await flow.async_step_user(user_input)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {}


@pytest.mark.asyncio
async def test_options_flow_init_redirects_to_user(
    hass: HomeAssistant, mock_config_entry
):
    flow = LuxtronikOptionsFlowHandler(mock_config_entry)
    flow.hass = hass

    result = await flow.async_step_init()
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

"""Tests for config_flow.py — ConfigFlow and OptionsFlow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.data_entry_flow import AbortFlow
import pytest

from custom_components.luxtronik.config_flow import (
    LuxtronikFlowHandler,
    LuxtronikOptionsFlowHandler,
)
from custom_components.luxtronik.const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from custom_components.luxtronik.coordinator import LuxtronikConnectionError


def _mock_coordinator():
    coord = MagicMock()
    coord.unique_id = "20230101_0xff"
    coord.manufacturer = "Alpha Innotec"
    coord.model = "LWP 10"
    return coord


# ===========================================================================
# LuxtronikFlowHandler helpers
# ===========================================================================


class TestFlowHelpers:
    def test_build_config(self):
        flow = LuxtronikFlowHandler()
        config = flow._build_config("1.2.3.4", 8889)
        assert config[CONF_HOST] == "1.2.3.4"
        assert config[CONF_PORT] == 8889
        assert config[CONF_TIMEOUT] == DEFAULT_TIMEOUT
        assert config[CONF_MAX_DATA_LENGTH] == DEFAULT_MAX_DATA_LENGTH

    def test_build_config_custom(self):
        flow = LuxtronikFlowHandler()
        config = flow._build_config("1.2.3.4", 8889, timeout=30.0, max_data_length=500)
        assert config[CONF_TIMEOUT] == 30.0
        assert config[CONF_MAX_DATA_LENGTH] == 500

    def test_create_entry_with_manufacturer(self):
        flow = LuxtronikFlowHandler()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        coord = _mock_coordinator()
        config = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}
        flow._create_entry(config, coord)
        call_kwargs = flow.async_create_entry.call_args[1]
        assert "Alpha Innotec" in call_kwargs["title"]
        assert CONF_HA_SENSOR_PREFIX in call_kwargs["data"]

    def test_create_entry_without_manufacturer(self):
        flow = LuxtronikFlowHandler()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        coord = _mock_coordinator()
        coord.manufacturer = None
        config = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}
        flow._create_entry(config, coord)
        call_kwargs = flow.async_create_entry.call_args[1]
        assert "Luxtronik @" in call_kwargs["title"]

    def test_create_entry_preserves_existing_prefix(self):
        flow = LuxtronikFlowHandler()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        coord = _mock_coordinator()
        config = {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 8889,
            CONF_HA_SENSOR_PREFIX: "my_prefix",
        }
        flow._create_entry(config, coord)
        call_kwargs = flow.async_create_entry.call_args[1]
        assert call_kwargs["data"][CONF_HA_SENSOR_PREFIX] == "my_prefix"


# ===========================================================================
# _set_unique_id_or_abort
# ===========================================================================


class TestSetUniqueIdOrAbort:
    @pytest.mark.asyncio
    async def test_sets_unique_id(self):
        flow = LuxtronikFlowHandler()
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        coord = _mock_coordinator()
        result = await flow._set_unique_id_or_abort(coord, {CONF_HOST: "1.2.3.4"})
        assert result is True
        flow.async_set_unique_id.assert_awaited_once_with(coord.unique_id)

    @pytest.mark.asyncio
    async def test_returns_false_on_abort(self):
        flow = LuxtronikFlowHandler()
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock(
            side_effect=AbortFlow("already_configured")
        )
        coord = _mock_coordinator()
        result = await flow._set_unique_id_or_abort(coord, {CONF_HOST: "1.2.3.4"})
        assert result is False


# ===========================================================================
# async_step_user
# ===========================================================================


class TestAsyncStepUser:
    @pytest.mark.asyncio
    async def test_shows_selection_form_when_devices_found(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(return_value=[("1.2.3.4", 8889)])
        flow._async_current_entries = MagicMock(return_value=[])
        flow._async_migrate_data_from_custom_component_luxtronik2 = AsyncMock()
        flow.async_show_form = MagicMock(
            return_value={"type": "form", "step_id": "select_devices"}
        )
        await flow.async_step_user()
        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["step_id"] == "select_devices"

    @pytest.mark.asyncio
    async def test_shows_manual_form_when_all_configured(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(return_value=[("1.2.3.4", 8889)])
        existing = MagicMock()
        existing.data = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}
        flow._async_current_entries = MagicMock(return_value=[existing])
        flow._async_migrate_data_from_custom_component_luxtronik2 = AsyncMock()
        flow.async_show_form = MagicMock(
            return_value={"type": "form", "step_id": "manual_entry"}
        )
        await flow.async_step_user()
        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["step_id"] == "manual_entry"

    @pytest.mark.asyncio
    async def test_shows_manual_when_no_devices_found(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(return_value=[])
        flow._async_current_entries = MagicMock(return_value=[])
        flow._async_migrate_data_from_custom_component_luxtronik2 = AsyncMock()
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        await flow.async_step_user()
        flow.async_show_form.assert_called_once()

    @pytest.mark.asyncio
    async def test_aborts_on_exception(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(side_effect=Exception("boom"))
        flow._async_migrate_data_from_custom_component_luxtronik2 = AsyncMock()
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        await flow.async_step_user()
        flow.async_abort.assert_called_once_with(reason="unknown")


# ===========================================================================
# async_step_select_devices
# ===========================================================================


class TestAsyncStepSelectDevices:
    @pytest.mark.asyncio
    async def test_no_input_redirects_to_user(self):
        flow = LuxtronikFlowHandler()
        flow.async_step_user = AsyncMock(return_value={"type": "form"})
        await flow.async_step_select_devices(None)
        flow.async_step_user.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_device_selected_aborts(self):
        flow = LuxtronikFlowHandler()
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        await flow.async_step_select_devices({})
        flow.async_abort.assert_called_with(reason="unknown")

    @pytest.mark.asyncio
    async def test_connection_error_aborts(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        err = LuxtronikConnectionError("1.2.3.4", 8889, Exception("refused"))
        with patch(
            "custom_components.luxtronik.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            side_effect=err,
        ):
            await flow.async_step_select_devices(
                {"select_device_to_configure": "1.2.3.4:8889"}
            )
        flow.async_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_selection(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        coord = _mock_coordinator()
        with patch(
            "custom_components.luxtronik.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            await flow.async_step_select_devices(
                {"select_device_to_configure": "1.2.3.4:8889"}
            )
        flow.async_create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_already_configured_aborts(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock(
            side_effect=AbortFlow("already_configured")
        )
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        coord = _mock_coordinator()
        with patch(
            "custom_components.luxtronik.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            await flow.async_step_select_devices(
                {"select_device_to_configure": "1.2.3.4:8889"}
            )
        flow.async_abort.assert_called_with(reason="already_configured")


# ===========================================================================
# async_step_manual_entry
# ===========================================================================


class TestAsyncStepManualEntry:
    @pytest.mark.asyncio
    async def test_no_input_shows_form(self):
        flow = LuxtronikFlowHandler()
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        await flow.async_step_manual_entry(None)
        flow.async_show_form.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_error_aborts(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        err = LuxtronikConnectionError("1.2.3.4", 8889, Exception("refused"))
        with patch(
            "custom_components.luxtronik.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            side_effect=err,
        ):
            await flow.async_step_manual_entry({CONF_HOST: "1.2.3.4", CONF_PORT: 8889})
        flow.async_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_entry(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        coord = _mock_coordinator()
        with patch(
            "custom_components.luxtronik.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            await flow.async_step_manual_entry({CONF_HOST: "1.2.3.4", CONF_PORT: 8889})
        flow.async_create_entry.assert_called_once()


# ===========================================================================
# async_step_dhcp
# ===========================================================================


class TestAsyncStepDhcp:
    def _make_dhcp_info(self, ip="1.2.3.4", hostname="luxtronik"):
        info = MagicMock()
        info.ip = ip
        info.hostname = hostname
        return info

    @pytest.mark.asyncio
    async def test_already_configured_ip_aborts(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        existing = MagicMock()
        existing.data = {CONF_HOST: "1.2.3.4"}
        flow._async_current_entries = MagicMock(return_value=[existing])
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        await flow.async_step_dhcp(self._make_dhcp_info())
        flow.async_abort.assert_called_with(reason="already_configured")

    @pytest.mark.asyncio
    async def test_dhcp_discovery_creates_entry(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(return_value=[("1.2.3.4", 8889)])
        flow._async_current_entries = MagicMock(return_value=[])
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        coord = _mock_coordinator()
        with patch(
            "custom_components.luxtronik.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            await flow.async_step_dhcp(self._make_dhcp_info())
        flow.async_create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_dhcp_no_match_uses_default_port(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        # Discovery returns different IP
        flow.hass.async_add_executor_job = AsyncMock(return_value=[("5.6.7.8", 8889)])
        flow._async_current_entries = MagicMock(return_value=[])
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        coord = _mock_coordinator()
        with patch(
            "custom_components.luxtronik.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            await flow.async_step_dhcp(self._make_dhcp_info())
        flow.async_create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_dhcp_connection_error_aborts(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(return_value=[("1.2.3.4", 8889)])
        flow._async_current_entries = MagicMock(return_value=[])
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        err = LuxtronikConnectionError("1.2.3.4", 8889, Exception("refused"))
        with patch(
            "custom_components.luxtronik.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            side_effect=err,
        ):
            await flow.async_step_dhcp(self._make_dhcp_info())
        flow.async_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_dhcp_unknown_error_aborts(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(side_effect=Exception("boom"))
        flow._async_current_entries = MagicMock(return_value=[])
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        await flow.async_step_dhcp(self._make_dhcp_info())
        flow.async_abort.assert_called_with(reason="unknown")


# ===========================================================================
# Options flow
# ===========================================================================


class _TestableOptionsFlow(LuxtronikOptionsFlowHandler):
    """Subclass that makes config_entry directly accessible without hass."""

    @property  # type: ignore[override]
    def config_entry(self):
        return self._config_entry


def _make_options_flow(entry=None):
    """Create an OptionsFlowHandler bypassing HA frame helper."""
    if entry is None:
        entry = MagicMock()
        entry.data = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}
        entry.options = {}
    with patch("homeassistant.config_entries.report_usage"):
        flow = _TestableOptionsFlow(entry)
    return flow


class TestOptionsFlow:
    @pytest.mark.asyncio
    async def test_init_delegates_to_user(self):
        flow = _make_options_flow()
        flow.async_step_user = AsyncMock(return_value={"type": "form"})
        await flow.async_step_init()
        flow.async_step_user.assert_awaited_once()

    def test_get_value_from_options(self):
        entry = MagicMock()
        entry.data = {CONF_HOST: "1.2.3.4"}
        entry.options = {"test_key": "opt_val"}
        flow = _make_options_flow(entry)
        assert flow._get_value("test_key") == "opt_val"

    def test_get_value_from_data(self):
        entry = MagicMock()
        entry.data = {CONF_HOST: "1.2.3.4"}
        entry.options = {}
        flow = _make_options_flow(entry)
        assert flow._get_value(CONF_HOST) == "1.2.3.4"

    def test_get_value_default(self):
        entry = MagicMock()
        entry.data = {}
        entry.options = {}
        flow = _make_options_flow(entry)
        assert flow._get_value("missing", "default") == "default"

    @pytest.mark.asyncio
    async def test_step_user_no_input_shows_form(self):
        flow = _make_options_flow()
        flow.hass = MagicMock()
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        await flow.async_step_user(None)
        flow.async_show_form.assert_called_once()

    @pytest.mark.asyncio
    async def test_step_user_connection_error(self):
        flow = _make_options_flow()
        flow.hass = MagicMock()
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        err = LuxtronikConnectionError("1.2.3.4", 8889, Exception("refused"))
        with patch(
            "custom_components.luxtronik.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            side_effect=err,
        ):
            await flow.async_step_user({CONF_HOST: "1.2.3.4", CONF_PORT: 8889})
        flow.async_show_form.assert_called_once()

    @pytest.mark.asyncio
    async def test_step_user_success(self):
        entry = MagicMock()
        entry.data = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}
        entry.options = {}
        entry.entry_id = "test"
        flow = _make_options_flow(entry)
        flow.hass = MagicMock()
        flow.hass.config_entries.async_reload = AsyncMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        coord = _mock_coordinator()
        with patch(
            "custom_components.luxtronik.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            await flow.async_step_user({CONF_HOST: "1.2.3.4", CONF_PORT: 8889})
        flow.async_create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_step_user_with_indoor_temp(self):
        entry = MagicMock()
        entry.data = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}
        entry.options = {}
        entry.entry_id = "test"
        flow = _make_options_flow(entry)
        flow.hass = MagicMock()
        flow.hass.config_entries.async_reload = AsyncMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        coord = _mock_coordinator()
        with patch(
            "custom_components.luxtronik.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            await flow.async_step_user(
                {
                    CONF_HOST: "1.2.3.4",
                    CONF_PORT: 8889,
                    CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.indoor_temp",
                }
            )
        flow.async_create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_step_user_exception_aborts(self):
        flow = _make_options_flow()
        flow.hass = MagicMock()
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        flow.async_show_form = MagicMock(side_effect=Exception("unexpected"))
        await flow.async_step_user(None)
        flow.async_abort.assert_called_with(reason="options_error")


# ===========================================================================
# config_flow.py — indoor_temp None reset (line 432)
# ===========================================================================

_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
    CONF_HA_SENSOR_PREFIX: DOMAIN,
}


class TestConfigFlowIndoorTempReset:
    @pytest.mark.asyncio
    async def test_indoor_temp_reset_to_none(self):
        handler = MagicMock(spec=LuxtronikOptionsFlowHandler)
        handler.options = {CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.old"}
        handler.config_entry = MagicMock()
        handler.config_entry.data = _ENTRY_DATA.copy()
        handler.config_entry.entry_id = "test_id"
        handler.hass = MagicMock()
        handler.hass.config_entries.async_reload = AsyncMock()

        user_input = {CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT}

        with patch(
            "custom_components.luxtronik.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
        ):
            await LuxtronikOptionsFlowHandler.async_step_user(handler, user_input)

        handler.hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = handler.hass.config_entries.async_update_entry.call_args
        updated_options = call_kwargs.kwargs.get(
            "options", call_kwargs[1].get("options", {})
        )
        assert updated_options.get(CONF_HA_SENSOR_INDOOR_TEMPERATURE) is None

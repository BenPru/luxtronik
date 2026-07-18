"""Tests for config_flow.py — ConfigFlow, OptionsFlow, and ReconfigureFlow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.data_entry_flow import AbortFlow
import pytest

from custom_components.luxtronik2.config_flow import (
    MANUAL_ENTRY_VALUE,
    SELECT_DEVICE_LABEL,
    LuxtronikFlowHandler,
    LuxtronikOptionsFlowHandler,
)
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    CONF_UPDATE_INTERVAL,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from custom_components.luxtronik2.coordinator import (
    LuxtronikConnectionError,
    LuxtronikSerialNumberError,
)


def _mock_coordinator():
    coord = MagicMock()
    coord.unique_id = "20230101_0xff"
    coord.manufacturer = "Alpha Innotec"
    coord.model = "LWP 10"
    return coord


@pytest.fixture(autouse=True)
def _stub_network_broadcasts():
    # _discover_devices calls network.async_get_ipv4_broadcast_addresses(hass);
    # tests use a MagicMock hass, so the real helper crashes on storage load.
    with patch(
        "custom_components.luxtronik2.config_flow.network."
        "async_get_ipv4_broadcast_addresses",
        new_callable=AsyncMock,
        return_value=[],
    ):
        yield


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
        assert result is None
        flow.async_set_unique_id.assert_awaited_once_with(coord.unique_id)

    @pytest.mark.asyncio
    async def test_returns_abort_result_on_already_configured(self):
        flow = LuxtronikFlowHandler()
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock(
            side_effect=AbortFlow("already_configured")
        )
        coord = _mock_coordinator()
        result = await flow._set_unique_id_or_abort(coord, {CONF_HOST: "1.2.3.4"})
        assert result is not None
        assert result["reason"] == "already_configured"

    @pytest.mark.asyncio
    async def test_returns_abort_result_on_serial_number_error(self):
        flow = LuxtronikFlowHandler()
        flow.async_set_unique_id = AsyncMock()
        coord = MagicMock()
        type(coord).unique_id = PropertyMock(
            side_effect=LuxtronikSerialNumberError("no serial number")
        )
        result = await flow._set_unique_id_or_abort(coord, {CONF_HOST: "1.2.3.4"})
        assert result is not None
        assert result["reason"] == "cannot_identify"


# ===========================================================================
# Instance isolation (I8)
# ===========================================================================


class TestFlowInstanceIsolation:
    def test_device_lists_are_not_shared_across_flow_instances(self):
        """`_all_devices`/`_available_devices` must be per-instance, not class-level.

        Two concurrent flows (e.g. two users, or discovery + manual entry
        running simultaneously) must never see each other's discovered
        device lists.
        """
        flow1 = LuxtronikFlowHandler()
        flow2 = LuxtronikFlowHandler()
        assert flow1._available_devices is not flow2._available_devices
        assert flow1._all_devices is not flow2._all_devices

    @pytest.mark.asyncio
    async def test_concurrent_discovery_does_not_cross_contaminate(self):
        """Two flows discovering different devices must not see each other's results."""

        def _prepare(flow, devices):
            flow.hass = MagicMock()
            flow.hass.async_add_executor_job = AsyncMock(return_value=devices)
            flow._async_current_entries = MagicMock(return_value=[])
            flow.async_show_form = MagicMock(return_value={"type": "form"})

        flow1 = LuxtronikFlowHandler()
        flow2 = LuxtronikFlowHandler()
        _prepare(flow1, [("1.2.3.4", 8889)])
        _prepare(flow2, [("5.6.7.8", 8888)])

        await flow1.async_step_user()
        await flow2.async_step_user()

        assert [d["host"] for d in flow1._all_devices] == ["1.2.3.4"]
        assert [d["host"] for d in flow2._all_devices] == ["5.6.7.8"]


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
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        await flow.async_step_user()
        flow.async_show_form.assert_called_once()

    @pytest.mark.asyncio
    async def test_discovery_os_error_reshows_manual_form_with_cannot_connect(self):
        """A transient network error during discovery must not kill the flow."""
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(
            side_effect=OSError("network unreachable")
        )
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        await flow.async_step_user()
        flow.async_abort.assert_not_called()
        flow.async_show_form.assert_called_once()
        call_kwargs = flow.async_show_form.call_args[1]
        assert call_kwargs["step_id"] == "manual_entry"
        assert call_kwargs["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_unexpected_error_reshows_manual_form_with_unknown_error(self):
        """A last-resort catch-all must also re-show the form, not abort the flow."""
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(side_effect=Exception("boom"))
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        await flow.async_step_user()
        flow.async_abort.assert_not_called()
        flow.async_show_form.assert_called_once()
        call_kwargs = flow.async_show_form.call_args[1]
        assert call_kwargs["step_id"] == "manual_entry"
        assert call_kwargs["errors"] == {"base": "unknown"}

    @pytest.mark.asyncio
    async def test_selection_form_includes_manual_entry_option(self):
        """A pump on another subnet must stay reachable while devices are discovered."""
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(return_value=[("1.2.3.4", 8889)])
        flow._async_current_entries = MagicMock(return_value=[])
        flow.async_show_form = MagicMock(
            return_value={"type": "form", "step_id": "select_devices"}
        )
        await flow.async_step_user()
        schema = flow.async_show_form.call_args[1]["data_schema"]
        select_selector = next(iter(schema.schema.values()))
        options = select_selector.config["options"]
        values = {opt["value"] if isinstance(opt, dict) else opt for opt in options}
        assert MANUAL_ENTRY_VALUE in values


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
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
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
        coord.async_config_entry_first_refresh = AsyncMock()
        with patch(
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            await flow.async_step_select_devices(
                {"select_device_to_configure": "1.2.3.4:8889"}
            )
        flow.async_create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_manual_entry_option_routes_to_manual_form(self):
        """Selecting the manual-entry sentinel must reach the manual host form."""
        flow = LuxtronikFlowHandler()
        flow.async_step_manual_entry = AsyncMock(
            return_value={"type": "form", "step_id": "manual_entry"}
        )
        result = await flow.async_step_select_devices(
            {SELECT_DEVICE_LABEL: MANUAL_ENTRY_VALUE}
        )
        flow.async_step_manual_entry.assert_awaited_once_with()
        assert result["step_id"] == "manual_entry"

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
        coord.async_config_entry_first_refresh = AsyncMock()
        with patch(
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
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
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
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
        coord.async_config_entry_first_refresh = AsyncMock()
        with patch(
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
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
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            await flow.async_step_dhcp(self._make_dhcp_info())
        flow.async_create_entry.assert_called_once()
        # Regression guard: our own update listener (__init__.py) already
        # reloads the entry on data changes. If this ever goes back to the
        # default (reload_on_update=True), core schedules a second reload and
        # logs HA's "has an update listener and should use it for scheduling
        # a reload" deprecation warning (removed in 2026.12.0).
        assert (
            flow._abort_if_unique_id_configured.call_args.kwargs["reload_on_update"]
            is False
        )

    @pytest.mark.asyncio
    async def test_dhcp_already_configured_after_connect_reraises_abort(self):
        """AbortFlow raised by _abort_if_unique_id_configured after a successful
        connect must propagate (via the `except AbortFlow: raise` guard added in
        c8f0795) instead of being swallowed by the catch-all handler and
        reported as an "unknown" error.
        """
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(return_value=[("1.2.3.4", 8889)])
        flow._async_current_entries = MagicMock(return_value=[])
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock(
            side_effect=AbortFlow("already_configured")
        )
        coord = _mock_coordinator()
        with (
            patch(
                "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
                new_callable=AsyncMock,
                return_value=coord,
            ),
            pytest.raises(AbortFlow, match="already_configured"),
        ):
            await flow.async_step_dhcp(self._make_dhcp_info())

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
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
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
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            side_effect=err,
        ):
            await flow.async_step_dhcp(self._make_dhcp_info())
        flow.async_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_dhcp_cannot_identify_aborts(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(return_value=[("1.2.3.4", 8889)])
        flow._async_current_entries = MagicMock(return_value=[])
        flow.async_set_unique_id = AsyncMock(
            side_effect=LuxtronikSerialNumberError("no serial number")
        )
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        coord = _mock_coordinator()
        with patch(
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            await flow.async_step_dhcp(self._make_dhcp_info())
        flow.async_abort.assert_called_with(
            reason="cannot_identify",
            description_placeholders={
                "host": "1.2.3.4",
                "error": "no serial number",
            },
        )

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

    def __init__(self, config_entry):
        self._config_entry = config_entry

    @property  # type: ignore[override]
    def config_entry(self):
        return self._config_entry


def _make_options_flow(entry=None):
    """Create an OptionsFlowHandler bypassing HA frame helper."""
    if entry is None:
        entry = MagicMock()
        entry.data = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}
        entry.options = {}
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
    async def test_step_user_saves_indoor_temp(self):
        entry = MagicMock()
        entry.data = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}
        entry.options = {}
        entry.title = "Test HP"
        flow = _make_options_flow(entry)
        flow.hass = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        await flow.async_step_user(
            {CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.indoor_temp"}
        )
        flow.async_create_entry.assert_called_once()
        call_kwargs = flow.async_create_entry.call_args[1]
        assert (
            call_kwargs["data"][CONF_HA_SENSOR_INDOOR_TEMPERATURE]
            == "sensor.indoor_temp"
        )

    @pytest.mark.asyncio
    async def test_step_user_clears_indoor_temp(self):
        entry = MagicMock()
        entry.data = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}
        entry.options = {CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.old"}
        entry.title = "Test HP"
        flow = _make_options_flow(entry)
        flow.hass = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        await flow.async_step_user({})
        flow.async_create_entry.assert_called_once()
        call_kwargs = flow.async_create_entry.call_args[1]
        assert call_kwargs["data"].get(CONF_HA_SENSOR_INDOOR_TEMPERATURE) is None

    @pytest.mark.asyncio
    async def test_step_user_saves_update_interval(self):
        entry = MagicMock()
        entry.data = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}
        entry.options = {}
        entry.title = "Test HP"
        flow = _make_options_flow(entry)
        flow.hass = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        await flow.async_step_user({CONF_UPDATE_INTERVAL: "1 minute (default)"})
        flow.async_create_entry.assert_called_once()
        call_kwargs = flow.async_create_entry.call_args[1]
        assert call_kwargs["data"][CONF_UPDATE_INTERVAL] == "1 minute (default)"

    @pytest.mark.asyncio
    async def test_step_user_clears_legacy_indoor_temp_from_data(self):
        """Clearing works even when the value only exists in config_entry.data."""
        entry = MagicMock()
        entry.data = {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 8889,
            CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.legacy",
        }
        entry.options = {}
        entry.title = "Test HP"
        flow = _make_options_flow(entry)
        flow.hass = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        await flow.async_step_user({})
        flow.async_create_entry.assert_called_once()
        call_kwargs = flow.async_create_entry.call_args[1]
        assert call_kwargs["data"][CONF_HA_SENSOR_INDOOR_TEMPERATURE] is None

    @pytest.mark.asyncio
    async def test_step_user_exception_aborts(self):
        flow = _make_options_flow()
        flow.hass = MagicMock()
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        flow.async_show_form = MagicMock(side_effect=Exception("unexpected"))
        await flow.async_step_user(None)
        flow.async_abort.assert_called_with(reason="options_error")


# ===========================================================================
# config_flow.py — indoor_temp None reset
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
        entry = MagicMock()
        entry.data = _ENTRY_DATA.copy()
        entry.options = {CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.old"}
        entry.title = "Test HP"
        flow = _make_options_flow(entry)
        flow.hass = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

        user_input: dict[str, Any] = {}
        await flow.async_step_user(user_input)

        flow.async_create_entry.assert_called_once()
        call_kwargs = flow.async_create_entry.call_args[1]
        assert call_kwargs["data"].get(CONF_HA_SENSOR_INDOOR_TEMPERATURE) is None


# ===========================================================================
# async_step_reconfigure
# ===========================================================================


class TestAsyncStepReconfigure:
    @pytest.mark.asyncio
    async def test_no_input_shows_form(self):
        flow = LuxtronikFlowHandler()
        entry = MagicMock()
        entry.data = {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 8889,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
        }
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        await flow.async_step_reconfigure(None)
        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["step_id"] == "reconfigure"

    @pytest.mark.asyncio
    async def test_connection_error_shows_form_with_error(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 8889,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
        }
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        err = LuxtronikConnectionError("5.6.7.8", 8889, Exception("refused"))
        user_input = {CONF_HOST: "5.6.7.8", CONF_PORT: 8889}
        with patch(
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            side_effect=err,
        ):
            await flow.async_step_reconfigure(user_input)
        flow.async_show_form.assert_called_once()
        call_kwargs = flow.async_show_form.call_args[1]
        assert call_kwargs["errors"] == {"base": "cannot_connect"}
        # Form must preserve user's attempted values, not revert to entry data
        schema = call_kwargs["data_schema"]
        defaults = {k.schema: k.default() for k in schema.schema}
        assert defaults[CONF_HOST] == "5.6.7.8"

    @pytest.mark.asyncio
    async def test_connect_exception_shows_unknown_error(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 8889,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
        }
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        user_input = {CONF_HOST: "5.6.7.8", CONF_PORT: 8889}
        with patch(
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            side_effect=Exception("boom"),
        ):
            await flow.async_step_reconfigure(user_input)
        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["errors"] == {"base": "unknown"}

    @pytest.mark.asyncio
    async def test_update_exception_shows_unknown_error(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 8889,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
        }
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        flow.async_set_unique_id = AsyncMock(side_effect=Exception("boom"))
        coord = _mock_coordinator()
        with patch(
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            await flow.async_step_reconfigure({CONF_HOST: "5.6.7.8", CONF_PORT: 8889})
        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["errors"] == {"base": "unknown"}

    @pytest.mark.asyncio
    async def test_serial_number_error_shows_cannot_identify_error(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 8889,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
        }
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        flow.async_set_unique_id = AsyncMock(
            side_effect=LuxtronikSerialNumberError("no serial number")
        )
        coord = _mock_coordinator()
        with patch(
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            await flow.async_step_reconfigure({CONF_HOST: "5.6.7.8", CONF_PORT: 8889})
        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["errors"] == {
            "base": "cannot_identify"
        }

    @pytest.mark.asyncio
    async def test_successful_reconfigure(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 8889,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
        }
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_mismatch = MagicMock()
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": "abort", "reason": "reconfigure_successful"}
        )
        coord = _mock_coordinator()
        coord.async_config_entry_first_refresh = AsyncMock()
        with patch(
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            result = await flow.async_step_reconfigure(
                {CONF_HOST: "5.6.7.8", CONF_PORT: 8889}
            )
        assert result.get("type") == "abort"
        assert result.get("reason") == "reconfigure_successful"
        flow.async_update_reload_and_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconfigure_without_existing_unique_id_updates_entry(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 8889,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
        }
        entry.unique_id = None
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_mismatch = MagicMock(
            side_effect=AbortFlow("unique_id_mismatch")
        )
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": "abort", "reason": "reconfigure_successful"}
        )
        coord = _mock_coordinator()
        coord.async_config_entry_first_refresh = AsyncMock()
        with patch(
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coord,
        ):
            result = await flow.async_step_reconfigure(
                {CONF_HOST: "5.6.7.8", CONF_PORT: 8889}
            )
        assert result.get("type") == "abort"
        assert result.get("reason") == "reconfigure_successful"
        flow.async_update_reload_and_abort.assert_called_once_with(
            entry,
            unique_id=coord.unique_id,
            data_updates={
                CONF_HOST: "5.6.7.8",
                CONF_PORT: 8889,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
                CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
            },
        )

    @pytest.mark.asyncio
    async def test_unique_id_mismatch_aborts(self):
        flow = LuxtronikFlowHandler()
        flow.hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 8889,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
        }
        entry.unique_id = "old_id"
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_mismatch = MagicMock(
            side_effect=AbortFlow("unique_id_mismatch")
        )
        coord = _mock_coordinator()
        coord.async_config_entry_first_refresh = AsyncMock()
        with (
            patch(
                "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
                new_callable=AsyncMock,
                return_value=coord,
            ),
            pytest.raises(AbortFlow, match="unique_id_mismatch"),
        ):
            await flow.async_step_reconfigure({CONF_HOST: "5.6.7.8", CONF_PORT: 8889})

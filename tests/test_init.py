"""Tests for custom_components.luxtronik2.__init__ (migration, setup, unload, services)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from conftest import make_coordinator_data
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, Platform as P
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
import pytest

from custom_components.luxtronik2 import (
    _async_update_config_entry,
    _fix_select_entity_unique_ids,
    _identifiers_exists,
    _up_many,
    async_migrate_entry,
    async_setup_entry,
    async_unload_entry,
    setup_hass_services,
    update_listener,
)
from custom_components.luxtronik2.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DEVICE_ID,
    ATTR_PARAMETER,
    ATTR_VALUE,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    CONFIG_ENTRY_VERSION,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PLATFORMS,
    SERVICE_WRITE,
    WRITABLE_PARAMETER_PREFIXES,
    SensorKey as SK,
)

_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
    CONF_HA_SENSOR_PREFIX: DOMAIN,
}


def _mock_entry(version=CONFIG_ENTRY_VERSION):
    entry = MagicMock()
    entry.data = _ENTRY_DATA.copy()
    entry.entry_id = "test_entry_id"
    entry.version = version
    entry.options = {}
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    return entry


def _mock_coordinator(hass):
    coord = MagicMock()
    coord.hass = hass
    coord.data = make_coordinator_data()
    coord.manufacturer = "Alpha Innotec"
    coord.model = "LWP 10"
    coord.async_config_entry_first_refresh = AsyncMock()
    coord.async_shutdown = AsyncMock()
    coord.async_write = AsyncMock()
    return coord


# ===========================================================================
# Service write_parameter validation
# ===========================================================================


class TestWriteParameterValidation:
    """Test the write_parameter service handler validation logic."""

    def test_writable_prefix_accepted(self):
        """Verify whitelisted prefixes are accepted."""
        test_params = [
            "ID_Einst_BWS_akt",
            "ID_Ba_Hz_akt",
            "ID_Soll_BWS_akt",
            "ID_Sollwert_KuCft1_akt",
            "ID_SU_FrkdHz",
            "ID_RBE_Einflussfaktor_RT_akt",
            "Unknown_Parameter_1119",
            "HEATING_TARGET_TEMP_ROOM_THERMOSTAT",
            "ELECTRICAL_POWER_LIMIT_VALUE",
            "POWER_LIMIT_SWITCH",
            "THERMAL_POWER_LIMIT_HEATING",
        ]
        for param in test_params:
            assert param.startswith(WRITABLE_PARAMETER_PREFIXES), (
                f"{param} should be writable"
            )

    def test_non_writable_prefix_rejected(self):
        """Verify non-whitelisted prefixes are rejected."""
        forbidden_params = [
            "ID_WEB_Temperatur_TVL",
            "ID_Visi_Solar",
            "system_command",
            "admin_access",
        ]
        for param in forbidden_params:
            assert not param.startswith(WRITABLE_PARAMETER_PREFIXES), (
                f"{param} should NOT be writable"
            )


# ===========================================================================
# convert_to_int_if_possible (used by service handler)
# ===========================================================================


class TestConvertToIntInService:
    def test_int_conversion(self):
        from custom_components.luxtronik2.common import convert_to_int_if_possible

        assert convert_to_int_if_possible("42") == 42
        assert convert_to_int_if_possible("not_a_number") == "not_a_number"


# ===========================================================================
# _identifiers_exists
# ===========================================================================


class TestIdentifiersExists:
    def test_match(self):
        idents_list = [{(DOMAIN, "abc")}, {(DOMAIN, "def")}]
        assert _identifiers_exists(idents_list, {(DOMAIN, "abc")}) is True

    def test_no_match(self):
        idents_list = [{(DOMAIN, "abc")}]
        assert _identifiers_exists(idents_list, {(DOMAIN, "xyz")}) is False

    def test_empty_list(self):
        assert _identifiers_exists([], {(DOMAIN, "abc")}) is False


# ===========================================================================
# _async_update_config_entry
# ===========================================================================


class TestAsyncUpdateConfigEntry:
    @pytest.mark.asyncio
    async def test_updates_entry(self):
        hass = MagicMock()
        entry = _mock_entry()
        await _async_update_config_entry(hass, entry, {"key": "val"}, 5)
        hass.config_entries.async_update_entry.assert_called_once_with(
            entry, data={"key": "val"}, version=5
        )


# ===========================================================================
# _up_many
# ===========================================================================


class TestUpMany:
    @pytest.mark.asyncio
    async def test_rename_success(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            await _up_many(
                hass,
                entry,
                {P.SENSOR: [("old_key", SK.FLOW_OUT_TEMPERATURE)]},
            )
        ent_reg.async_update_entity.assert_called_once()

    @pytest.mark.asyncio
    async def test_rename_key_error(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        ent_reg.async_update_entity.side_effect = KeyError("not found")
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            # Should not raise
            await _up_many(
                hass,
                entry,
                {P.SENSOR: [("old_key", SK.FLOW_OUT_TEMPERATURE)]},
            )

    @pytest.mark.asyncio
    async def test_rename_value_error(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        ent_reg.async_update_entity.side_effect = ValueError("conflict")
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            await _up_many(
                hass,
                entry,
                {P.SENSOR: [("old_key", SK.FLOW_OUT_TEMPERATURE)]},
            )

    @pytest.mark.asyncio
    async def test_rename_generic_exception(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        ent_reg.async_update_entity.side_effect = RuntimeError("unexpected")
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            await _up_many(
                hass,
                entry,
                {P.SENSOR: [("old_key", SK.FLOW_OUT_TEMPERATURE)]},
            )


# ===========================================================================
# _fix_select_entity_unique_ids
# ===========================================================================


class TestFixSelectEntityUniqueIds:
    @pytest.mark.asyncio
    async def test_migrates_old_unique_id(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        ent_reg.async_get_entity_id.return_value = "select.luxtronik2_old"
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            await _fix_select_entity_unique_ids(hass, entry)
        assert ent_reg.async_update_entity.call_count == 3  # 3 select keys

    @pytest.mark.asyncio
    async def test_skips_when_no_old_entity(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        ent_reg.async_get_entity_id.return_value = None
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            await _fix_select_entity_unique_ids(hass, entry)
        ent_reg.async_update_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_value_error(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        ent_reg.async_get_entity_id.return_value = "select.luxtronik2_old"
        ent_reg.async_update_entity.side_effect = ValueError("conflict")
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            await _fix_select_entity_unique_ids(hass, entry)


# ===========================================================================
# async_migrate_entry
# ===========================================================================


class TestAsyncMigrateEntry:
    @pytest.mark.asyncio
    async def test_already_at_latest_version(self):
        hass = MagicMock()
        entry = _mock_entry(version=CONFIG_ENTRY_VERSION)
        result = await async_migrate_entry(hass, entry)
        assert result is True

    @pytest.mark.asyncio
    async def test_migration_from_v3_to_v4(self):
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []
        entry = _mock_entry(version=3)
        # Set version to 3 so we migrate 3->4->...->9
        entry.version = 3
        entry.data = {**_ENTRY_DATA}

        with (
            patch(
                "custom_components.luxtronik2._async_update_config_entry",
                new_callable=AsyncMock,
            ) as mock_update,
            patch(
                "custom_components.luxtronik2._rename_entities",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._rename_cooling_entities",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._rename_curve_entities",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._fix_select_entity_unique_ids",
                new_callable=AsyncMock,
            ),
        ):
            result = await async_migrate_entry(hass, entry)

        assert result is True
        # Should have been called for versions 4, 5, 6, 7, 8, 9
        assert mock_update.call_count == 6

    @pytest.mark.asyncio
    async def test_migration_v3_adds_prefix(self):
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []
        entry = _mock_entry(version=3)
        entry.data = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}

        with (
            patch(
                "custom_components.luxtronik2._async_update_config_entry",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._rename_entities",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._rename_cooling_entities",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._rename_curve_entities",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._fix_select_entity_unique_ids",
                new_callable=AsyncMock,
            ),
        ):
            result = await async_migrate_entry(hass, entry)

        assert result is True


# ===========================================================================
# update_listener
# ===========================================================================


class TestUpdateListener:
    @pytest.mark.asyncio
    async def test_reloads_entry(self):
        hass = MagicMock()
        hass.config_entries.async_reload = AsyncMock()
        entry = _mock_entry()
        await update_listener(hass, entry)
        hass.config_entries.async_reload.assert_awaited_once_with(entry.entry_id)


# ===========================================================================
# async_setup_entry
# ===========================================================================


class TestAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_raises_config_entry_not_ready_on_failure(self):
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = False
        entry = _mock_entry()
        with (
            patch(
                "custom_components.luxtronik2.connect_and_get_coordinator",
                new_callable=AsyncMock,
                side_effect=Exception("Connection failed"),
            ),
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_entry(hass, entry)

    @pytest.mark.asyncio
    async def test_successful_setup(self):
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = False
        entry = _mock_entry()

        coordinator = MagicMock()
        coordinator.manufacturer = "Alpha Innotec"
        coordinator.async_config_entry_first_refresh = AsyncMock()

        with patch(
            "custom_components.luxtronik2.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coordinator,
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True
        assert entry.runtime_data == coordinator

    @pytest.mark.asyncio
    async def test_setup_no_manufacturer(self):
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = False
        entry = _mock_entry()

        coordinator = MagicMock()
        coordinator.manufacturer = None
        coordinator.async_config_entry_first_refresh = AsyncMock()

        with patch(
            "custom_components.luxtronik2.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coordinator,
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True
        # Title should start with "Luxtronik @"
        call_args = hass.config_entries.async_update_entry.call_args
        assert "Luxtronik @" in call_args.kwargs.get(
            "title", call_args[1].get("title", "")
        )

    @pytest.mark.asyncio
    async def test_success(self):
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.config_entries.async_update_entry = MagicMock()
        hass.services.has_service = MagicMock(return_value=True)
        entry = _mock_entry()
        coord = _mock_coordinator(hass)

        with patch(
            "custom_components.luxtronik2.connect_and_get_coordinator",
            return_value=coord,
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True
        hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
            entry, PLATFORMS
        )

    @pytest.mark.asyncio
    async def test_connection_failure_raises_not_ready(self):
        hass = MagicMock()
        entry = _mock_entry()

        with (
            patch(
                "custom_components.luxtronik2.connect_and_get_coordinator",
                side_effect=ConnectionRefusedError("refused"),
            ),
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_entry(hass, entry)

    @pytest.mark.asyncio
    async def test_title_without_manufacturer(self):
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.config_entries.async_update_entry = MagicMock()
        hass.services.has_service = MagicMock(return_value=True)
        entry = _mock_entry()
        coord = _mock_coordinator(hass)
        coord.manufacturer = None

        with patch(
            "custom_components.luxtronik2.connect_and_get_coordinator",
            return_value=coord,
        ):
            await async_setup_entry(hass, entry)

        call_args = hass.config_entries.async_update_entry.call_args
        title = call_args.kwargs.get("title", "")
        assert "Luxtronik @" in title

    @pytest.mark.asyncio
    async def test_connection_failure_creates_repair_issue(self):
        """Connection failure creates a repair issue and raises ConfigEntryNotReady."""
        hass = MagicMock()
        entry = _mock_entry()

        with (
            patch(
                "custom_components.luxtronik2.connect_and_get_coordinator",
                side_effect=ConnectionRefusedError("refused"),
            ),
            patch("custom_components.luxtronik2.ir.async_create_issue") as mock_create,
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_entry(hass, entry)

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["translation_key"] == "connection_failed"
        assert call_kwargs["severity"].value == "error"
        assert entry.data[CONF_HOST] in call_kwargs["translation_placeholders"]["host"]

    @pytest.mark.asyncio
    async def test_successful_setup_clears_connection_issue(self):
        """Successful setup clears any previous connection failure issue."""
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = True
        entry = _mock_entry()
        coord = _mock_coordinator(hass)

        with (
            patch(
                "custom_components.luxtronik2.connect_and_get_coordinator",
                return_value=coord,
            ),
            patch("custom_components.luxtronik2.ir.async_delete_issue") as mock_delete,
        ):
            await async_setup_entry(hass, entry)

        mock_delete.assert_any_call(hass, DOMAIN, f"connection_failed_{entry.entry_id}")

    @pytest.mark.asyncio
    async def test_preserves_existing_matching_title(self):
        """Existing title matching new_title logs already up-to-date message."""
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.config_entries.async_update_entry = MagicMock()
        hass.services.has_service = MagicMock(return_value=True)
        entry = _mock_entry()
        coord = _mock_coordinator(hass)
        coord.manufacturer = "Alpha Innotec"
        entry.data = {
            **entry.data,
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
        }
        entry.title = "Alpha Innotec @ 192.168.1.100:8889"

        with (
            patch(
                "custom_components.luxtronik2.connect_and_get_coordinator",
                return_value=coord,
            ),
            patch("custom_components.luxtronik2.LOGGER") as mock_logger,
        ):
            await async_setup_entry(hass, entry)

        hass.config_entries.async_update_entry.assert_not_called()
        mock_logger.debug.assert_any_call(
            "Config entry title already up-to-date: %s",
            "Alpha Innotec @ 192.168.1.100:8889",
        )

    @pytest.mark.asyncio
    async def test_preserves_user_renamed_title(self):
        """User-renamed title different from new_title is preserved."""
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.config_entries.async_update_entry = MagicMock()
        hass.services.has_service = MagicMock(return_value=True)
        entry = _mock_entry()
        coord = _mock_coordinator(hass)
        coord.manufacturer = "Alpha Innotec"
        entry.data = {
            **entry.data,
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
        }
        entry.title = "My Custom Heatpump Name"

        with (
            patch(
                "custom_components.luxtronik2.connect_and_get_coordinator",
                return_value=coord,
            ),
            patch("custom_components.luxtronik2.LOGGER") as mock_logger,
        ):
            await async_setup_entry(hass, entry)

        hass.config_entries.async_update_entry.assert_not_called()
        mock_logger.debug.assert_any_call(
            "Preserve user-set config entry title: %s", "My Custom Heatpump Name"
        )


# ===========================================================================
# async_unload_entry
# ===========================================================================


class TestAsyncUnloadEntry:
    @pytest.mark.asyncio
    async def test_unload_removes_service_when_last_entry(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.config_entries.async_entries.return_value = []
        entry = _mock_entry()
        entry.runtime_data = MagicMock()
        entry.runtime_data.async_shutdown = AsyncMock()
        result = await async_unload_entry(hass, entry)
        assert result is True
        hass.services.async_remove.assert_called_once_with(DOMAIN, SERVICE_WRITE)

    @pytest.mark.asyncio
    async def test_unload_keeps_service_when_other_entries_remain(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        other_entry = MagicMock()
        other_entry.entry_id = "other_entry"
        hass.config_entries.async_entries.return_value = [other_entry]
        entry = _mock_entry()
        entry.runtime_data = MagicMock()
        entry.runtime_data.async_shutdown = AsyncMock()
        result = await async_unload_entry(hass, entry)
        assert result is True
        hass.services.async_remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_unload_success(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.config_entries.async_entries = MagicMock(return_value=[])
        hass.services.async_remove = MagicMock()
        entry = _mock_entry()
        entry.runtime_data = _mock_coordinator(hass)

        result = await async_unload_entry(hass, entry)

        assert result is True
        entry.runtime_data.async_shutdown.assert_awaited_once()
        hass.services.async_remove.assert_called_once_with(DOMAIN, SERVICE_WRITE)

    @pytest.mark.asyncio
    async def test_unload_with_remaining_entries(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        other_entry = MagicMock()
        other_entry.entry_id = "other_entry"
        hass.config_entries.async_entries = MagicMock(return_value=[other_entry])
        hass.services.async_remove = MagicMock()
        entry = _mock_entry()
        entry.runtime_data = _mock_coordinator(hass)

        await async_unload_entry(hass, entry)

        hass.services.async_remove.assert_not_called()


# ===========================================================================
# setup_hass_services
# ===========================================================================


class TestSetupHassServices:
    def test_skips_when_already_registered(self):
        hass = MagicMock()
        hass.services.has_service.return_value = True
        entry = _mock_entry()
        setup_hass_services(hass, entry)
        hass.services.async_register.assert_not_called()

    def test_registers_service(self):
        hass = MagicMock()
        hass.services.has_service.return_value = False
        entry = _mock_entry()
        setup_hass_services(hass, entry)
        hass.services.async_register.assert_called_once()

    def test_service_already_registered(self):
        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=True)
        entry = _mock_entry()

        setup_hass_services(hass, entry)

        hass.services.async_register.assert_not_called()

    def test_service_registered(self):
        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        entry = _mock_entry()

        setup_hass_services(hass, entry)

        hass.services.async_register.assert_called_once()


# ===========================================================================
# write_parameter service handler
# ===========================================================================


class TestWriteParameterService:
    @pytest.mark.asyncio
    async def test_write_valid_parameter(self):
        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        entry = _mock_entry()

        setup_hass_services(hass, entry)
        handler = hass.services.async_register.call_args[0][2]

        from homeassistant.config_entries import ConfigEntryState

        mock_entry = MagicMock()
        mock_entry.state = ConfigEntryState.LOADED
        mock_entry.runtime_data = _mock_coordinator(hass)
        hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Einst_BWS_akt",
            ATTR_VALUE: "42",
        }

        await handler(service)

        mock_entry.runtime_data.async_write.assert_awaited_once_with(
            "ID_Einst_BWS_akt", 42
        )

    @pytest.mark.asyncio
    async def test_write_rejected_parameter(self):
        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        entry = _mock_entry()

        setup_hass_services(hass, entry)
        handler = hass.services.async_register.call_args[0][2]

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Forbidden_param",
            ATTR_VALUE: "42",
        }

        with pytest.raises(ServiceValidationError) as exc_info:
            await handler(service)
        assert exc_info.value.translation_key == "parameter_not_writable"
        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_placeholders == {
            "parameter": "ID_Forbidden_param",
            "prefixes": ", ".join(WRITABLE_PARAMETER_PREFIXES),
        }

    @pytest.mark.asyncio
    async def test_write_invalid_parameter_name(self):
        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        entry = _mock_entry()

        setup_hass_services(hass, entry)
        handler = hass.services.async_register.call_args[0][2]

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: None,
            ATTR_VALUE: "42",
        }

        with pytest.raises(ServiceValidationError) as exc_info:
            await handler(service)
        assert exc_info.value.translation_key == "invalid_parameter_name"
        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_placeholders == {"parameter": "None"}


# ===========================================================================
# write_parameter service handler - multi config entry target selection
# ===========================================================================


def _mock_loaded_config_entry(entry_id: str, hass) -> MagicMock:
    """Build a MagicMock config entry that looks LOADED with runtime_data."""
    from homeassistant.config_entries import ConfigEntryState

    entry = MagicMock()
    entry.entry_id = entry_id
    entry.domain = DOMAIN
    entry.state = ConfigEntryState.LOADED
    entry.runtime_data = _mock_coordinator(hass)
    return entry


class TestWriteParameterServiceTargetSelection:
    """The write service must target a specific config entry when several
    heat pumps (config entries) are loaded, instead of silently picking the
    first one returned by hass.config_entries.async_entries()."""

    def _setup(self):
        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        entry = _mock_entry()
        setup_hass_services(hass, entry)
        handler = hass.services.async_register.call_args[0][2]
        return hass, handler

    @pytest.mark.asyncio
    async def test_write_multi_entry_with_config_entry_id_targets_correct_entry(self):
        """A config_entry_id target must select that exact entry, even when
        it is not first in hass.config_entries.async_entries()."""
        hass, handler = self._setup()

        entry_1 = _mock_loaded_config_entry("entry_1", hass)
        entry_2 = _mock_loaded_config_entry("entry_2", hass)
        hass.config_entries.async_entries = MagicMock(return_value=[entry_1, entry_2])
        hass.config_entries.async_get_entry = MagicMock(
            side_effect=lambda eid: {"entry_1": entry_1, "entry_2": entry_2}.get(eid)
        )

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Einst_BWS_akt",
            ATTR_VALUE: "42",
            ATTR_CONFIG_ENTRY_ID: "entry_2",
        }

        await handler(service)

        entry_2.runtime_data.async_write.assert_awaited_once_with(
            "ID_Einst_BWS_akt", 42
        )
        entry_1.runtime_data.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_write_multi_entry_with_device_id_targets_correct_entry(self):
        """A device_id target must be resolved via the device registry to the
        config entry that owns that device, then write to that entry only."""
        hass, handler = self._setup()

        entry_1 = _mock_loaded_config_entry("entry_1", hass)
        entry_2 = _mock_loaded_config_entry("entry_2", hass)
        hass.config_entries.async_entries = MagicMock(return_value=[entry_1, entry_2])
        hass.config_entries.async_get_entry = MagicMock(
            side_effect=lambda eid: {"entry_1": entry_1, "entry_2": entry_2}.get(eid)
        )

        device = MagicMock()
        device.config_entries = {"entry_2"}
        device_registry = MagicMock()
        device_registry.async_get = MagicMock(return_value=device)

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Einst_BWS_akt",
            ATTR_VALUE: "42",
            ATTR_DEVICE_ID: "device_xyz",
        }

        with patch(
            "custom_components.luxtronik2.dr.async_get", return_value=device_registry
        ):
            await handler(service)

        device_registry.async_get.assert_called_once_with("device_xyz")
        entry_2.runtime_data.async_write.assert_awaited_once_with(
            "ID_Einst_BWS_akt", 42
        )
        entry_1.runtime_data.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_write_multi_entry_no_target_raises_ambiguous(self):
        """With no device_id/config_entry_id and more than one loaded entry,
        the service must refuse to guess and raise instead of silently
        writing to whichever entry happens to come first."""
        hass, handler = self._setup()

        entry_1 = _mock_loaded_config_entry("entry_1", hass)
        entry_2 = _mock_loaded_config_entry("entry_2", hass)
        hass.config_entries.async_entries = MagicMock(return_value=[entry_1, entry_2])

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Einst_BWS_akt",
            ATTR_VALUE: "42",
        }

        with pytest.raises(ServiceValidationError) as exc_info:
            await handler(service)

        assert exc_info.value.translation_key == "ambiguous_write_target"
        assert exc_info.value.translation_domain == DOMAIN
        entry_1.runtime_data.async_write.assert_not_awaited()
        entry_2.runtime_data.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_write_no_target_single_entry_still_works(self):
        """Backward compatibility: a single-heat-pump setup with no explicit
        target must keep working exactly as before."""
        hass, handler = self._setup()

        entry_1 = _mock_loaded_config_entry("entry_1", hass)
        hass.config_entries.async_entries = MagicMock(return_value=[entry_1])

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Einst_BWS_akt",
            ATTR_VALUE: "42",
        }

        await handler(service)

        entry_1.runtime_data.async_write.assert_awaited_once_with(
            "ID_Einst_BWS_akt", 42
        )

    @pytest.mark.asyncio
    async def test_write_unknown_device_id_raises(self):
        """A device_id that does not resolve to any known device must raise,
        not silently fall through to writing the wrong entry."""
        hass, handler = self._setup()

        entry_1 = _mock_loaded_config_entry("entry_1", hass)
        hass.config_entries.async_entries = MagicMock(return_value=[entry_1])
        hass.config_entries.async_get_entry = MagicMock(
            side_effect=lambda eid: {"entry_1": entry_1}.get(eid)
        )

        device_registry = MagicMock()
        device_registry.async_get = MagicMock(return_value=None)

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Einst_BWS_akt",
            ATTR_VALUE: "42",
            ATTR_DEVICE_ID: "does_not_exist",
        }

        with (
            patch(
                "custom_components.luxtronik2.dr.async_get",
                return_value=device_registry,
            ),
            pytest.raises(ServiceValidationError) as exc_info,
        ):
            await handler(service)

        assert exc_info.value.translation_key == "invalid_write_target"
        assert exc_info.value.translation_domain == DOMAIN
        entry_1.runtime_data.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_write_device_id_from_other_integration_raises(self):
        """A device_id belonging to a device from a different integration
        (not a Luxtronik config entry) must raise, not fall back to picking
        an arbitrary Luxtronik entry."""
        hass, handler = self._setup()

        entry_1 = _mock_loaded_config_entry("entry_1", hass)
        hass.config_entries.async_entries = MagicMock(return_value=[entry_1])

        other_entry = MagicMock()
        other_entry.entry_id = "other_entry"
        other_entry.domain = "some_other_integration"

        hass.config_entries.async_get_entry = MagicMock(
            side_effect=lambda eid: {
                "entry_1": entry_1,
                "other_entry": other_entry,
            }.get(eid)
        )

        device = MagicMock()
        device.config_entries = {"other_entry"}
        device_registry = MagicMock()
        device_registry.async_get = MagicMock(return_value=device)

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Einst_BWS_akt",
            ATTR_VALUE: "42",
            ATTR_DEVICE_ID: "device_of_other_integration",
        }

        with (
            patch(
                "custom_components.luxtronik2.dr.async_get",
                return_value=device_registry,
            ),
            pytest.raises(ServiceValidationError) as exc_info,
        ):
            await handler(service)

        assert exc_info.value.translation_key == "invalid_write_target"
        assert exc_info.value.translation_domain == DOMAIN
        entry_1.runtime_data.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_write_unknown_config_entry_id_raises(self):
        """A config_entry_id that does not resolve to a loaded Luxtronik
        entry must raise rather than silently targeting a different entry."""
        hass, handler = self._setup()

        entry_1 = _mock_loaded_config_entry("entry_1", hass)
        hass.config_entries.async_entries = MagicMock(return_value=[entry_1])
        hass.config_entries.async_get_entry = MagicMock(return_value=None)

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Einst_BWS_akt",
            ATTR_VALUE: "42",
            ATTR_CONFIG_ENTRY_ID: "does_not_exist",
        }

        with pytest.raises(ServiceValidationError) as exc_info:
            await handler(service)

        assert exc_info.value.translation_key == "invalid_write_target"
        assert exc_info.value.translation_domain == DOMAIN
        entry_1.runtime_data.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_write_config_entry_id_not_loaded_raises(self):
        """A config_entry_id that belongs to this integration but whose entry
        is not currently loaded (e.g. disabled, failed setup) must raise
        rather than write through a coordinator that may not exist."""
        hass, handler = self._setup()

        from homeassistant.config_entries import ConfigEntryState

        entry_1 = _mock_loaded_config_entry("entry_1", hass)
        hass.config_entries.async_entries = MagicMock(return_value=[entry_1])

        unloaded_entry = MagicMock()
        unloaded_entry.entry_id = "entry_unloaded"
        unloaded_entry.domain = DOMAIN
        unloaded_entry.state = ConfigEntryState.NOT_LOADED
        del unloaded_entry.runtime_data

        hass.config_entries.async_get_entry = MagicMock(
            side_effect=lambda eid: {
                "entry_1": entry_1,
                "entry_unloaded": unloaded_entry,
            }.get(eid)
        )

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Einst_BWS_akt",
            ATTR_VALUE: "42",
            ATTR_CONFIG_ENTRY_ID: "entry_unloaded",
        }

        with pytest.raises(ServiceValidationError) as exc_info:
            await handler(service)

        assert exc_info.value.translation_key == "invalid_write_target"
        assert exc_info.value.translation_domain == DOMAIN
        entry_1.runtime_data.async_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_write_device_id_takes_precedence_over_config_entry_id(self):
        """When both device_id and config_entry_id are given, device_id wins
        (documented precedence) rather than the two silently disagreeing."""
        hass, handler = self._setup()

        entry_1 = _mock_loaded_config_entry("entry_1", hass)
        entry_2 = _mock_loaded_config_entry("entry_2", hass)
        hass.config_entries.async_entries = MagicMock(return_value=[entry_1, entry_2])
        hass.config_entries.async_get_entry = MagicMock(
            side_effect=lambda eid: {"entry_1": entry_1, "entry_2": entry_2}.get(eid)
        )

        device = MagicMock()
        device.config_entries = {"entry_2"}
        device_registry = MagicMock()
        device_registry.async_get = MagicMock(return_value=device)

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Einst_BWS_akt",
            ATTR_VALUE: "42",
            ATTR_DEVICE_ID: "device_xyz",
            ATTR_CONFIG_ENTRY_ID: "entry_1",
        }

        with patch(
            "custom_components.luxtronik2.dr.async_get", return_value=device_registry
        ):
            await handler(service)

        entry_2.runtime_data.async_write.assert_awaited_once_with(
            "ID_Einst_BWS_akt", 42
        )
        entry_1.runtime_data.async_write.assert_not_awaited()

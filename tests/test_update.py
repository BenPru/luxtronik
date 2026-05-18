"""Tests for custom_components.luxtronik2.update (firmware update entity)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from conftest import make_coordinator_data
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, STATE_UNAVAILABLE
import pytest

from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxCalculation,
    LuxCalculation as LC,
    SensorKey,
)
from custom_components.luxtronik2.model import LuxtronikUpdateEntityDescription
from custom_components.luxtronik2.update import (
    FIRMWARE_UPDATE_MANUAL_DE,
    FIRMWARE_UPDATE_MANUAL_EN,
    LANG_DE,
    MIN_TIME_BETWEEN_UPDATES,
    LuxtronikUpdateEntity,
)

# ===========================================================================
# Helpers
# ===========================================================================

_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
    CONF_HA_SENSOR_PREFIX: DOMAIN,
}


def _mock_entry():
    entry = MagicMock()
    entry.data = _ENTRY_DATA.copy()
    return entry


def _mock_coordinator(data=None):
    if data is None:
        data = make_coordinator_data(calculations={"ID_WEB_SoftStand": "V3.90.1"})
    coord = MagicMock()
    coord.data = data
    coord.entity_active.return_value = True
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    coord.model = "LWP 10"
    coord.manufacturer = "Alpha Innotec"
    return coord


def _make_update_entity(data=None):
    entry = _mock_entry()
    coord = _mock_coordinator(data)
    desc = LuxtronikUpdateEntityDescription(
        luxtronik_key=LuxCalculation.C0081_FIRMWARE_VERSION,
        key=SensorKey.FIRMWARE,
    )
    entity = LuxtronikUpdateEntity(entry=entry, coordinator=coord, description=desc)
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.hass.config.language = "en"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()
    return entity


def _make_full_update_entity():
    """Create a real LuxtronikUpdateEntity for integration-level tests."""
    desc = LuxtronikUpdateEntityDescription(
        key=SensorKey.FIRMWARE,
        luxtronik_key=LC.C0081_FIRMWARE_VERSION,
        device_key=DeviceKey.heatpump,
    )
    data = make_coordinator_data()
    coord = MagicMock()
    coord.data = data
    coord.entity_active.return_value = True
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    coord.model = "LW"
    coord.manufacturer = "Alpha Innotec"
    entry = MagicMock()
    entry.data = _ENTRY_DATA.copy()
    entity = LuxtronikUpdateEntity(entry, coord, desc)
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()
    return entity


def _make_version_entity():
    entity = MagicMock(spec=LuxtronikUpdateEntity)
    entity.version_is_newer = LuxtronikUpdateEntity.version_is_newer.__get__(entity)
    return entity


def _make_latest_entity():
    entity = MagicMock(spec=LuxtronikUpdateEntity)
    entity.latest_version = LuxtronikUpdateEntity.latest_version.fget.__get__(entity)
    entity.update_available = LuxtronikUpdateEntity.update_available.fget.__get__(
        entity
    )
    return entity


# ===========================================================================
# extract_firmware_version
# ===========================================================================


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("wp2reg-V3.91.0_d0dc76bb", "V3.91.0"),
        ("wp2reg-V2.88.1-9086", "V2.88.1-9086"),
        ("wpreg.V1.88.3-9717", "V1.88.3-9717"),
        ("otherprefix-V2.99.2-1234", "V2.99.2-1234"),
        ("something-V3.91.0_moretext", "V3.91.0"),
        ("nofirmwarehere.txt", None),
        (None, None),
        ("", None),
        ("wp2reg-B1.0.0", "B1.0.0"),
    ],
)
def test_extract_firmware_version(filename, expected):
    assert LuxtronikUpdateEntity.extract_firmware_version(filename) == expected


# ===========================================================================
# version_is_newer
# ===========================================================================


@pytest.mark.parametrize(
    ("available", "installed", "expected"),
    [
        ("V4.0.0", "V3.90.1", True),
        ("V3.91.0", "V3.90.1", True),
        ("V3.90.1", "V3.90.1", False),
        ("V3.89.0", "V3.90.1", False),
        ("invalid", "V3.90.1", False),
    ],
)
def test_version_is_newer(available, installed, expected):
    entity = _make_version_entity()
    assert entity.version_is_newer(available, installed) is expected


# ===========================================================================
# latest_version
# ===========================================================================


def test_latest_version_none_when_no_available():
    entity = _make_latest_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = None
    entity._attr_state = "V3.90.1"
    result = LuxtronikUpdateEntity.latest_version.fget(entity)
    assert result is None


def test_latest_version_none_when_no_installed():
    entity = _make_latest_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
    entity._attr_state = None
    type(entity).installed_version = property(lambda s: s._attr_state)
    result = LuxtronikUpdateEntity.latest_version.fget(entity)
    assert result is None


def test_latest_version_strips_build_number():
    entity = _make_latest_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0-9086"
    entity._attr_state = "V3.90.1"
    type(entity).installed_version = property(lambda s: s._attr_state)
    result = LuxtronikUpdateEntity.latest_version.fget(entity)
    assert result == "V3.91.0"


# ===========================================================================
# release_notes
# ===========================================================================


def test_release_notes_none_when_no_download_id():
    entity = MagicMock(spec=LuxtronikUpdateEntity)
    entity._attr_state = "X99.0.0"
    type(entity).installed_version = property(lambda s: s._attr_state)
    result = LuxtronikUpdateEntity.release_notes(entity)
    assert result is None


def test_release_notes_returns_html():
    entity = MagicMock(spec=LuxtronikUpdateEntity)
    entity._attr_state = "V3.90.1"
    type(entity).installed_version = property(lambda s: s._attr_state)
    entity.coordinator = MagicMock()
    entity.coordinator.model = "LWP 10"
    entity.coordinator.manufacturer = "Alpha Innotec"
    entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
    entity._LuxtronikUpdateEntity__firmware_version_changelog = "Bug fixes"
    entity.hass = MagicMock()
    entity.hass.config.language = "en"
    result = LuxtronikUpdateEntity.release_notes(entity)
    assert result is not None
    assert "V3.91.0" in result
    assert "Bug fixes" in result


# ===========================================================================
# update_available, manual_url
# ===========================================================================


def test_update_available_true():
    entity = _make_full_update_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
    entity._attr_state = "V3.90.1"
    assert entity.update_available is True


def test_update_available_false_no_latest():
    entity = _make_full_update_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = None
    entity._attr_state = "V3.90.1"
    assert entity.update_available is False


def test_manual_url_german():
    entity = _make_full_update_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
    entity._attr_state = "V3.90.1"
    entity.hass.config.language = LANG_DE
    notes = entity.release_notes()
    assert FIRMWARE_UPDATE_MANUAL_DE in notes


def test_manual_url_english():
    entity = _make_full_update_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
    entity._attr_state = "V3.90.1"
    entity.hass.config.language = "en"
    notes = entity.release_notes()
    assert FIRMWARE_UPDATE_MANUAL_EN in notes


# ===========================================================================
# async_setup_entry
# ===========================================================================


class TestUpdateAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_setup_creates_entity(self):
        from custom_components.luxtronik2.update import async_setup_entry

        data = make_coordinator_data(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()
        await async_setup_entry(MagicMock(), entry, add)
        add.assert_called_once()
        entities = add.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], LuxtronikUpdateEntity)


# ===========================================================================
# installed_version
# ===========================================================================


class TestInstalledVersion:
    def test_returns_attr_state(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"
        assert entity.installed_version == "V3.90.1"

    def test_returns_none_when_no_state(self):
        entity = _make_update_entity()
        entity._attr_state = None
        assert entity.installed_version is None


# ===========================================================================
# async_update — throttle logic
# ===========================================================================


class TestAsyncUpdate:
    @pytest.mark.asyncio
    async def test_first_call_requests_firmware(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"
        entity._LuxtronikUpdateEntity__firmware_version_available_last_request = None
        with patch.object(
            entity, "_request_available_firmware_version", new_callable=AsyncMock
        ) as mock_req:
            await entity.async_update()
            mock_req.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_when_recently_requested(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"
        entity._LuxtronikUpdateEntity__firmware_version_available_last_request = (
            datetime.now(UTC).timestamp()
        )
        with patch.object(
            entity, "_request_available_firmware_version", new_callable=AsyncMock
        ) as mock_req:
            await entity.async_update()
            mock_req.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_requests_when_expired(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"
        entity._LuxtronikUpdateEntity__firmware_version_available_last_request = (
            datetime.now(UTC).timestamp()
            - MIN_TIME_BETWEEN_UPDATES.total_seconds()
            - 10
        )
        with patch.object(
            entity, "_request_available_firmware_version", new_callable=AsyncMock
        ) as mock_req:
            await entity.async_update()
            mock_req.assert_awaited_once()


# ===========================================================================
# _request_available_firmware_version
# ===========================================================================


class TestRequestAvailableFirmwareVersion:
    @pytest.mark.asyncio
    async def test_no_download_id_sets_unavailable(self):
        entity = _make_update_entity()
        entity._attr_state = "X99.0.0"  # Unknown prefix → no download ID
        await entity._request_available_firmware_version()
        assert (
            entity._LuxtronikUpdateEntity__firmware_version_available
            == STATE_UNAVAILABLE
        )

    @pytest.mark.asyncio
    async def test_successful_request(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"

        mock_response_fw = AsyncMock()
        mock_response_fw.status = 200
        mock_response_fw.headers = {
            "Content-Disposition": "filename=wp2reg-V3.91.0_abc"
        }
        mock_response_fw.__aenter__ = AsyncMock(return_value=mock_response_fw)
        mock_response_fw.__aexit__ = AsyncMock(return_value=False)

        mock_response_cl = AsyncMock()
        mock_response_cl.status = 200
        mock_response_cl.text = AsyncMock(return_value="Bug fixes")
        mock_response_cl.__aenter__ = AsyncMock(return_value=mock_response_cl)
        mock_response_cl.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=[mock_response_fw, mock_response_cl])

        with patch(
            "custom_components.luxtronik2.update.async_get_clientsession",
            return_value=mock_session,
        ):
            await entity._request_available_firmware_version()

        assert entity._LuxtronikUpdateEntity__firmware_version_available == "V3.91.0"
        assert entity._LuxtronikUpdateEntity__firmware_version_changelog == "Bug fixes"

    @pytest.mark.asyncio
    async def test_http_error_sets_unavailable(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        with patch(
            "custom_components.luxtronik2.update.async_get_clientsession",
            return_value=mock_session,
        ):
            await entity._request_available_firmware_version()

        assert (
            entity._LuxtronikUpdateEntity__firmware_version_available
            == STATE_UNAVAILABLE
        )

    @pytest.mark.asyncio
    async def test_connection_error_sets_unavailable(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("Connection refused"))

        with patch(
            "custom_components.luxtronik2.update.async_get_clientsession",
            return_value=mock_session,
        ):
            await entity._request_available_firmware_version()

        assert (
            entity._LuxtronikUpdateEntity__firmware_version_available
            == STATE_UNAVAILABLE
        )


# ===========================================================================
# release_notes (async)
# ===========================================================================


class TestReleaseNotes:
    def test_returns_html_with_all_info(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"
        entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
        entity._LuxtronikUpdateEntity__firmware_version_changelog = "Bug fixes"
        result = entity.release_notes()
        assert result is not None
        assert "V3.91.0" in result
        assert "Bug fixes" in result
        assert "Alpha Innotec" in result

    def test_returns_none_for_unknown_prefix(self):
        entity = _make_update_entity()
        entity._attr_state = "X99.0.0"
        assert entity.release_notes() is None

    def test_german_language_uses_de_manual(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"
        entity.hass.config.language = "de"
        entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
        entity._LuxtronikUpdateEntity__firmware_version_changelog = "Fixes"
        result = entity.release_notes()
        assert result is not None

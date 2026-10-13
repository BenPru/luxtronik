"""Read-only mode on firmware V1.90.x / V2.90.x (issue #831)."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
import pytest

from custom_components.luxtronik2.const import DOMAIN, SERVICE_WRITE
from tests.conftest import DEFAULT_CALCULATIONS, DEFAULT_PORT
from tests.test_setup_integration import (
    FakeLuxtronikClient,
    _make_entry,
    _patch_client,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


class RecordingClient(FakeLuxtronikClient):
    """Fake client that counts flushed writes."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.write_calls = 0

    def write(self) -> None:
        self.write_calls += 1


async def _setup(hass: HomeAssistant, monkeypatch, firmware: str):
    calculations = DEFAULT_CALCULATIONS.copy()
    calculations["ID_WEB_SoftStand"] = firmware
    client = RecordingClient(
        host="192.168.1.100",
        port=DEFAULT_PORT,
        socket_timeout=10,
        max_data_length=1024,
        calculations=calculations,
    )
    _patch_client(monkeypatch, client)
    entry = _make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry, client


@pytest.mark.parametrize(
    ("firmware", "blocked"),
    [
        ("V1.90.0", True),
        ("V1.90.3", True),
        ("V2.90.1", True),
        ("2.90", True),
        ("V1.89.9", False),
        ("V1.91.0", False),
        ("V2.88.3", False),
        ("V3.90.1", False),
        ("V3.92.3", False),
        ("garbage", False),
    ],
)
async def test_write_blocked_by_firmware(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, firmware: str, blocked: bool
) -> None:
    entry, _ = await _setup(hass, monkeypatch, firmware)
    assert entry.runtime_data.write_blocked is blocked


@pytest.mark.parametrize("firmware", ["V1.90.2", "V2.90.0"])
async def test_coordinator_write_is_blocked_and_never_reaches_client(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, firmware: str
) -> None:
    entry, client = await _setup(hass, monkeypatch, firmware)
    coordinator = entry.runtime_data

    with pytest.raises(HomeAssistantError):
        await coordinator.async_write("ID_Soll_BWS_akt", 55.0)
    with pytest.raises(HomeAssistantError):
        await coordinator.async_write_many([("ID_Soll_BWS_akt", 55.0)])

    assert client.write_calls == 0
    assert client.parameters.get("ID_Soll_BWS_akt").value != 55.0


async def test_write_service_is_blocked(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, client = await _setup(hass, monkeypatch, "V2.90.1")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WRITE,
            {"parameter": "ID_Soll_BWS_akt", "value": 55},
            blocking=True,
        )
    assert client.write_calls == 0


async def test_entity_service_write_is_blocked(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A number entity write is stopped as well, with no flush to the device."""
    import asyncio

    from custom_components.luxtronik2.const import SensorKey

    _, client = await _setup(hass, monkeypatch, "V1.90.1")
    entity_id = f"number.{DOMAIN}_{SensorKey.DHW_TARGET_TEMPERATURE}"
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id, "value": 55.0}, blocking=True
    )
    await asyncio.sleep(0.6)
    await hass.async_block_till_done()

    assert client.write_calls == 0
    assert client.parameters.get("ID_Soll_BWS_akt").value != 55.0


async def test_repair_issue_and_warning_when_blocked(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    entry, _ = await _setup(hass, monkeypatch, "V1.90.1")

    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"readonly_firmware_{entry.entry_id}"
    )
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_placeholders == {"firmware": "V1.90.1"}
    assert "read-only" in caplog.text

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"readonly_firmware_{entry.entry_id}")
        is None
    )


async def test_writes_and_no_issue_on_safe_firmware(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry, client = await _setup(hass, monkeypatch, "V3.90.1")

    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"readonly_firmware_{entry.entry_id}")
        is None
    )
    await entry.runtime_data.async_write("ID_Soll_BWS_akt", 55.0)
    assert client.write_calls == 1

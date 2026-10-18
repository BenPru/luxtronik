"""Read-only mode on firmware V1.90.x / V2.90.x (issue #831)."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
import pytest

from custom_components.luxtronik2.const import DOMAIN, SERVICE_WRITE
from custom_components.luxtronik2.coordinator import (
    READONLY_FIRMWARE_FORUM_URL,
    READONLY_FIRMWARE_LEARN_MORE_URL,
    connect_and_get_coordinator,
)
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


def _issue(hass: HomeAssistant, entry) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(
        DOMAIN, f"readonly_firmware_{entry.entry_id}"
    )


def _client(firmware: str) -> RecordingClient:
    calculations = DEFAULT_CALCULATIONS.copy()
    calculations["ID_WEB_SoftStand"] = firmware
    return RecordingClient(
        host="192.168.1.100",
        port=DEFAULT_PORT,
        socket_timeout=10,
        max_data_length=1024,
        calculations=calculations,
    )


async def _setup(hass: HomeAssistant, monkeypatch, firmware: str):
    client = _client(firmware)
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
        ("V2.90.0-12815", True),
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


@pytest.mark.parametrize(
    ("domain", "service", "entity_id", "data"),
    [
        # Debounced: without the up-front check the write would fail later,
        # with no caller left to show the error to.
        (
            "number",
            "set_value",
            "number.luxtronik2_dhw_target_temperature",
            {"value": 55.0},
        ),
        (
            "water_heater",
            "set_temperature",
            "water_heater.luxtronik2_domestic_water",
            {"temperature": 55.0},
        ),
        (
            "climate",
            "set_temperature",
            "climate.luxtronik2_heating",
            None,
        ),
        # Set entity state before writing.
        (
            "climate",
            "set_preset_mode",
            "climate.luxtronik2_heating",
            {"preset_mode": "away"},
        ),
        (
            "select",
            "select_option",
            "select.luxtronik2_thermal_desinfection_day",
            {"option": "friday"},
        ),
        ("select", "select_option", "select.luxtronik2_heating_mode", None),
    ],
)
async def test_entity_setter_raises_and_keeps_state(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    domain: str,
    service: str,
    entity_id: str,
    data: dict | None,
) -> None:
    """Each setter raises up front: no write, and no state the device never got."""
    _, client = await _setup(hass, monkeypatch, "V1.90.1")
    before = hass.states.get(entity_id)
    assert before is not None
    # Values HA's own validation accepts, so the call reaches the entity.
    if data is None and domain == "climate":
        data = {"temperature": before.attributes["min_temp"]}
    elif data is None:  # any option other than the current one
        data = {
            "option": next(o for o in before.attributes["options"] if o != before.state)
        }

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            domain, service, {"entity_id": entity_id, **data}, blocking=True
        )
    await hass.async_block_till_done()

    assert exc.value.translation_key == "readonly_firmware"
    assert client.write_calls == 0
    after = hass.states.get(entity_id)
    assert after is not None
    assert (after.state, after.attributes) == (before.state, before.attributes)


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
    assert issue.translation_placeholders == {
        "firmware": "V1.90.1",
        "forum_url": READONLY_FIRMWARE_FORUM_URL,
    }
    assert issue.learn_more_url == READONLY_FIRMWARE_LEARN_MORE_URL
    assert "read-only" in caplog.text

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN, f"readonly_firmware_{entry.entry_id}"
        )
        is None
    )


async def test_writes_and_no_issue_on_safe_firmware(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry, client = await _setup(hass, monkeypatch, "V3.90.1")

    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN, f"readonly_firmware_{entry.entry_id}"
        )
        is None
    )
    await entry.runtime_data.async_write("ID_Soll_BWS_akt", 55.0)
    assert client.write_calls == 1


async def test_issue_cleared_when_firmware_is_downgraded(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The remedy for #831 happens while HA runs; writes and Repairs follow it."""
    entry, client = await _setup(hass, monkeypatch, "V1.90.0")
    coordinator = entry.runtime_data
    assert _issue(hass, entry) is not None

    client.calculations.set("ID_WEB_SoftStand", "V1.88.3")
    await coordinator.async_refresh()

    assert _issue(hass, entry) is None
    assert coordinator.write_blocked is False
    await coordinator.async_write("ID_Soll_BWS_akt", 55.0)
    assert client.write_calls == 1

    # Back on an affected release: blocked and reported again.
    client.calculations.set("ID_WEB_SoftStand", "V1.90.0")
    await coordinator.async_refresh()
    assert _issue(hass, entry) is not None


async def test_issue_follows_a_blocked_to_blocked_update(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The repair text names the firmware actually running."""
    entry, client = await _setup(hass, monkeypatch, "V1.90.0")

    client.calculations.set("ID_WEB_SoftStand", "V1.90.1")
    await entry.runtime_data.async_refresh()

    issue = _issue(hass, entry)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["firmware"] == "V1.90.1"


async def test_config_flow_coordinator_raises_no_issue(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The flow's entry-less coordinator is never shut down; it must not leave an issue."""
    _patch_client(monkeypatch, _client("V2.90.0"))

    coordinator = await connect_and_get_coordinator(
        hass, {CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT}
    )

    assert coordinator.write_blocked is True
    assert not [
        issue_id for (domain, issue_id) in ir.async_get(hass).issues if domain == DOMAIN
    ]


async def test_invalid_firmware_is_warned_about_once(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """write_blocked reads the version every poll; the warning must not repeat."""
    caplog.set_level(logging.WARNING)
    entry, _ = await _setup(hass, monkeypatch, "garbage")

    for _ in range(3):
        await entry.runtime_data.async_refresh()

    assert caplog.text.count("Invalid firmware version") == 1

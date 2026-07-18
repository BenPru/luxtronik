"""Harness-based integration tests using a real `hass` (I11).

Unlike the rest of the suite (MagicMock hass + fake sensor containers), these
tests run against `pytest-homeassistant-custom-component`'s real HomeAssistant
core so bugs where "HA ignores this attribute" or "a property shadows an
instance attribute" (the C2/C3/I4 class) are actually caught. Only the socket
layer is mocked: `custom_components.luxtronik2.coordinator.Luxtronik` is
replaced with `FakeLuxtronikClient`, which reuses the fake sensor containers
already defined in `tests/conftest.py`. Everything else - config entries,
entity registry, platform setup, services - runs for real.
"""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONFIG_ENTRY_VERSION,
    DEFAULT_PORT,
    DOMAIN,
    SERVICE_WRITE,
    SensorKey,
)
from tests.conftest import (
    DEFAULT_CALCULATIONS,
    DEFAULT_PARAMETERS,
    DEFAULT_VISIBILITIES,
    FakeSensorGroup,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


class FakeLuxtronikClient:
    """Stand-in for `lux_helper.Luxtronik` - the socket layer, and nothing else.

    Constructed with the exact keyword arguments `LuxtronikCoordinator.connect`
    passes to the real client, so it can be swapped in via a single
    `monkeypatch.setattr("custom_components.luxtronik2.coordinator.Luxtronik", ...)`.
    """

    def __init__(
        self,
        host: str,
        port: int,
        socket_timeout: float,
        max_data_length: int,
        safe: bool = False,
        parameters: dict[str, Any] | None = None,
        calculations: dict[str, Any] | None = None,
        visibilities: dict[str, Any] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.parameters = FakeSensorGroup(
            parameters if parameters is not None else DEFAULT_PARAMETERS.copy()
        )
        self.calculations = FakeSensorGroup(
            calculations if calculations is not None else DEFAULT_CALCULATIONS.copy()
        )
        self.visibilities = FakeSensorGroup(
            visibilities if visibilities is not None else DEFAULT_VISIBILITIES.copy()
        )
        self.connected = False
        self.disconnected = False
        self.fail_read = False

    def connect(self) -> None:
        self.connected = True

    def read(self) -> None:
        if self.fail_read:
            raise OSError("simulated read failure")

    def write(self) -> None:
        pass

    def disconnect(self) -> None:
        self.disconnected = True


def _patch_client(monkeypatch: pytest.MonkeyPatch, client: FakeLuxtronikClient) -> None:
    monkeypatch.setattr(
        "custom_components.luxtronik2.coordinator.Luxtronik",
        lambda **kwargs: client,
    )


def _make_entry(**data_overrides: Any) -> MockConfigEntry:
    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: DEFAULT_PORT,
        CONF_HA_SENSOR_PREFIX: DOMAIN,
    }
    data.update(data_overrides)
    return MockConfigEntry(domain=DOMAIN, version=CONFIG_ENTRY_VERSION, data=data)


async def test_setup_entry_registers_entities_with_visibility_driven_defaults(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """async_setup_entry loads the entry and registers entities (regression net for C2).

    ID_Visi_SysEin_EVUSperre=0 makes the EVU_UNLOCKED binary sensor invisible on
    this (fake) heat pump model, so it must land in the registry disabled by
    default; a sibling entity with no visibility flag (EVU2) must stay enabled.
    """
    visibilities = DEFAULT_VISIBILITIES.copy()
    visibilities["ID_Visi_SysEin_EVUSperre"] = 0
    client = FakeLuxtronikClient(
        host="192.168.1.100",
        port=DEFAULT_PORT,
        socket_timeout=10,
        max_data_length=1024,
        visibilities=visibilities,
    )
    _patch_client(monkeypatch, client)

    entry = _make_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    ent_reg = er.async_get(hass)
    invisible_entity_id = f"binary_sensor.{DOMAIN}_{SensorKey.EVU_UNLOCKED}"
    visible_entity_id = f"binary_sensor.{DOMAIN}_{SensorKey.EVU2}"

    invisible_entry = ent_reg.entities.get(invisible_entity_id)
    visible_entry = ent_reg.entities.get(visible_entity_id)
    assert invisible_entry is not None
    assert visible_entry is not None

    assert invisible_entry.unique_id == invisible_entity_id
    assert visible_entry.unique_id == visible_entity_id

    assert invisible_entry.disabled_by is not None
    assert visible_entry.disabled_by is None


async def test_failed_refresh_makes_entities_unavailable(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed coordinator refresh must surface as unavailable entities (C3-class regression net)."""
    client = FakeLuxtronikClient(
        host="192.168.1.100", port=DEFAULT_PORT, socket_timeout=10, max_data_length=1024
    )
    _patch_client(monkeypatch, client)

    entry = _make_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"binary_sensor.{DOMAIN}_{SensorKey.EVU2}"
    assert hass.states.get(entity_id).state != "unavailable"

    client.fail_read = True
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"


async def test_number_set_native_value_writes_converted_raw_value(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A number entity's set_value service round-trips to a raw client write (I3/I4 regression net)."""
    client = FakeLuxtronikClient(
        host="192.168.1.100", port=DEFAULT_PORT, socket_timeout=10, max_data_length=1024
    )
    _patch_client(monkeypatch, client)

    entry = _make_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"number.{DOMAIN}_{SensorKey.DHW_TARGET_TEMPERATURE}"
    assert hass.states.get(entity_id) is not None

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 55.0},
        blocking=True,
    )
    # The write is debounced (0.5s cooldown, non-immediate) before it reaches
    # the client - the service call above only schedules it.
    await asyncio.sleep(0.6)
    await hass.async_block_till_done()

    assert client.parameters.get("ID_Soll_BWS_akt").value == 55.0
    assert float(hass.states.get(entity_id).state) == 55.0


async def test_number_temperature_state_converts_to_imperial_unit(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A temperature number entity's state respects hass's display unit (I4 regression net).

    `LuxtronikNumberEntity` used to override `state` to return
    `self._attr_native_value` unconditionally, bypassing `NumberEntity`'s
    built-in unit conversion - imperial users would see the raw Celsius
    number mislabeled as Fahrenheit.
    """
    hass.config.units = US_CUSTOMARY_SYSTEM
    client = FakeLuxtronikClient(
        host="192.168.1.100", port=DEFAULT_PORT, socket_timeout=10, max_data_length=1024
    )
    _patch_client(monkeypatch, client)

    entry = _make_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"number.{DOMAIN}_{SensorKey.DHW_TARGET_TEMPERATURE}"
    state = hass.states.get(entity_id)
    assert state is not None
    # Native value is 50.0 degC (see DEFAULT_PARAMETERS["ID_Soll_BWS_akt"]).
    assert float(state.state) == pytest.approx(122.0)
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.FAHRENHEIT


async def test_unload_disconnects_client_and_unregisters_service(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unloading the only config entry disconnects the client and removes the service."""
    client = FakeLuxtronikClient(
        host="192.168.1.100", port=DEFAULT_PORT, socket_timeout=10, max_data_length=1024
    )
    _patch_client(monkeypatch, client)

    entry = _make_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, SERVICE_WRITE)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert client.disconnected is True
    assert not hass.services.has_service(DOMAIN, SERVICE_WRITE)


async def test_migration_from_v1_reaches_current_version(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Setting up a v1 entry runs the real async_migrate_entry up to CONFIG_ENTRY_VERSION (I10 regression net).

    Going through `hass.config_entries.async_setup` (rather than calling
    `async_migrate_entry` directly) matters: HA only allows
    `async_config_entry_first_refresh` - used by the v1 step's
    `connect_and_get_coordinator` call - while the entry is in
    `SETUP_IN_PROGRESS`, which only the real setup flow puts it in.
    """
    client = FakeLuxtronikClient(
        host="192.168.1.100", port=DEFAULT_PORT, socket_timeout=10, max_data_length=1024
    )
    _patch_client(monkeypatch, client)

    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == CONFIG_ENTRY_VERSION
    # The v1 step hardcodes the legacy prefix "luxtronik" (not the domain
    # "luxtronik2"); later steps only fill CONF_HA_SENSOR_PREFIX in if it's
    # still absent, so a v1 entry keeps "luxtronik" through to the latest
    # version.
    assert entry.data[CONF_HA_SENSOR_PREFIX] == "luxtronik"

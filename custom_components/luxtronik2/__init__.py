"""The Luxtronik heatpump integration."""

# region Imports
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, Platform as P
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.entity_registry import (
    async_get,
)

from .common import convert_to_int_if_possible
from .const import (
    ATTR_PARAMETER,
    ATTR_VALUE,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    CONFIG_ENTRY_VERSION,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SERVICE_WRITE,
    SERVICE_WRITE_SCHEMA,
    SensorKey as SK,
)
from .coordinator import LuxtronikCoordinator, connect_and_get_coordinator

# endregion Imports

type LuxtronikConfigEntry = ConfigEntry[LuxtronikCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: LuxtronikConfigEntry) -> bool:
    """Set up Luxtronik from a config entry."""

    config = entry.data

    try:
        coordinator = await connect_and_get_coordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        LOGGER.error("Luxtronik connection failed: %s", err)
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"connection_failed_{entry.entry_id}",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="connection_failed",
            translation_placeholders={
                "host": str(config.get(CONF_HOST, "unknown")),
                "port": str(config.get(CONF_PORT, "")),
                "error": str(err),
            },
        )
        raise ConfigEntryNotReady from err

    # Clear any previous connection failure issue
    ir.async_delete_issue(hass, DOMAIN, f"connection_failed_{entry.entry_id}")

    entry.async_on_unload(entry.add_update_listener(update_listener))

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Trigger a refresh again now that all platforms have registered
    # await coordinator.async_refresh()

    # 🛠️ Update title on initial setup only
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    if coordinator.manufacturer is not None:
        new_title = f"{coordinator.manufacturer} @ {host}:{port}"
    else:
        new_title = f"Luxtronik @ {host}:{port}"

    LOGGER.info("new_title: %s", new_title)

    # Preserve any user-provided title. Only auto-update when the existing
    # title is empty. If the title already matches `new_title`, do nothing.
    # Otherwise, assume the user renamed the entry and preserve it.
    # Only treat existing title as valid when it's an explicit string value.

    old_title = entry.title if isinstance(entry.title, str) else ""

    if not old_title:
        hass.config_entries.async_update_entry(entry, title=new_title.strip())
    else:
        if old_title == new_title.strip():
            LOGGER.debug("Config entry title already up-to-date: %s", old_title)
        else:
            LOGGER.debug("Preserve user-set config entry title: %s", old_title)

    setup_hass_services(hass, entry)

    LOGGER.info("Luxtronik integration setup completed for %s", entry.entry_id)

    return True


def setup_hass_services(hass: HomeAssistant, entry: LuxtronikConfigEntry):
    """Register Home Assistant services (once)."""

    if hass.services.has_service(DOMAIN, SERVICE_WRITE):
        return

    async def write_parameter(service):
        """Write a parameter to the Luxtronik heatpump."""
        parameter = service.data.get(ATTR_PARAMETER)
        if not parameter or not isinstance(parameter, str):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_parameter_name",
                translation_placeholders={"parameter": str(parameter)},
            )

        # convert to int needed for Unknown parameters
        value = convert_to_int_if_possible(service.data.get(ATTR_VALUE))

        # Only allow writing to known writable parameter prefixes
        writable_prefixes = (
            "ID_Einst_",
            "ID_Ba_",
            "ID_Soll_",
            "ID_Sollwert_",
            "ID_SU_",
            "ID_RBE_",
            "Unknown_Parameter_",
            "HEATING_TARGET_TEMP_ROOM_THERMOSTAT",
        )
        if not parameter.startswith(writable_prefixes):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="parameter_not_writable",
                translation_placeholders={
                    "parameter": parameter,
                    "prefixes": ", ".join(writable_prefixes),
                },
            )

        # Find the first available coordinator
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            if config_entry.state is ConfigEntryState.LOADED and hasattr(
                config_entry, "runtime_data"
            ):
                coordinator = config_entry.runtime_data
                await coordinator.async_write(parameter, value)
                return
        LOGGER.error(
            "No active Luxtronik coordinator found for service call"
        )  # pragma: no cover

    hass.services.async_register(
        DOMAIN, SERVICE_WRITE, write_parameter, schema=SERVICE_WRITE_SCHEMA
    )


async def async_unload_entry(hass: HomeAssistant, entry: LuxtronikConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()

    # Unregister service when no entries remain
    remaining = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id != entry.entry_id
    ]
    if not remaining:
        hass.services.async_remove(DOMAIN, SERVICE_WRITE)

    return unload_ok


async def update_listener(
    hass: HomeAssistant, config_entry: LuxtronikConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry to the latest version."""
    current_version = config_entry.version
    latest_version = CONFIG_ENTRY_VERSION

    while current_version < latest_version:
        LOGGER.debug("Starting migration from version %s", current_version)
        new_data = {**config_entry.data}

        if current_version == 1:  # pragma: no cover
            coordinator = await connect_and_get_coordinator(hass, config_entry)
            if CONF_HA_SENSOR_PREFIX not in new_data:
                new_data[CONF_HA_SENSOR_PREFIX] = "luxtronik"
            hass.config_entries.async_update_entry(
                config_entry, data=new_data, version=2, unique_id=coordinator.unique_id
            )
            current_version = 2

        elif current_version == 2:  # pragma: no cover
            await _async_delete_legacy_devices(hass, config_entry)
            await _async_update_config_entry(hass, config_entry, new_data, 3)
            current_version = 3

        elif current_version == 3:
            if CONF_HA_SENSOR_PREFIX not in new_data and (
                DOMAIN == "luxtronik2"
                or len(hass.config_entries.async_entries("luxtronik2")) > 0
            ):
                new_data[CONF_HA_SENSOR_PREFIX] = "luxtronik2"
            await _async_update_config_entry(hass, config_entry, new_data, 4)
            current_version = 4

        elif current_version == 4:
            await _async_update_config_entry(hass, config_entry, new_data, 5)
            current_version = 5

        elif current_version == 5:
            await _rename_entities(hass, config_entry)
            new_data[CONF_TIMEOUT] = DEFAULT_TIMEOUT
            new_data[CONF_MAX_DATA_LENGTH] = DEFAULT_MAX_DATA_LENGTH
            await _async_update_config_entry(hass, config_entry, new_data, 6)
            current_version = 6

        elif current_version == 6:
            await _rename_cooling_entities(hass, config_entry)
            await _async_update_config_entry(hass, config_entry, new_data, 7)
            current_version = 7

        elif current_version == 7:
            await _rename_curve_entities(hass, config_entry)
            await _async_update_config_entry(hass, config_entry, new_data, 8)
            current_version = 8

        elif current_version == 8:
            await _fix_select_entity_unique_ids(hass, config_entry)
            await _async_update_config_entry(hass, config_entry, new_data, 9)
            current_version = 9

    LOGGER.info("Migration to version %s successful", current_version)
    return True


async def _async_update_config_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any], version: int
) -> None:
    """Update config entry with new data and version."""
    hass.config_entries.async_update_entry(config_entry, data=data, version=version)


async def _rename_entities(
    hass: HomeAssistant, config_entry: ConfigEntry
):  # pragma: no cover
    """Rename all entities for version 5 migration."""
    await _up_many(
        hass,
        config_entry,
        {
            P.SENSOR: [
                ("pump_frequency", SK.PUMP_FREQUENCY),
                ("room_thermostat_temperature", SK.ROOM_THERMOSTAT_TEMPERATURE),
                (
                    "room_thermostat_temperature_target",
                    SK.ROOM_THERMOSTAT_TEMPERATURE_TARGET,
                ),
            ],
            P.BINARY_SENSOR: [
                ("evu_unlocked", SK.EVU_UNLOCKED),
                ("compressor", SK.COMPRESSOR),
                ("pump_flow", SK.PUMP_FLOW),
                ("compressor_heater", SK.COMPRESSOR_HEATER),
                ("defrost_valve", SK.DEFROST_VALVE),
                ("additional_heat_generator", SK.ADDITIONAL_HEAT_GENERATOR),
                ("disturbance_output", SK.DISTURBANCE_OUTPUT),
                ("circulation_pump_heating", SK.CIRCULATION_PUMP_HEATING),
                ("additional_circulation_pump", SK.ADDITIONAL_CIRCULATION_PUMP),
                ("approval_cooling", SK.APPROVAL_COOLING),
            ],
            P.NUMBER: [
                ("release_second_heat_generator", SK.RELEASE_SECOND_HEAT_GENERATOR),
                (
                    "release_time_second_heat_generator",
                    SK.RELEASE_TIME_SECOND_HEAT_GENERATOR,
                ),
                ("heating_target_correction", SK.HEATING_TARGET_CORRECTION),
                ("pump_optimization_time", SK.PUMP_OPTIMIZATION_TIME),
                ("heating_threshold_temperature", SK.HEATING_THRESHOLD_TEMPERATURE),
                (
                    "heating_min_flow_out_temperature",
                    SK.HEATING_MIN_FLOW_OUT_TEMPERATURE,
                ),
                (
                    "heating_circuit_curve1_temperature",
                    SK.HEATING_CURVE_END_TEMPERATURE,
                ),
                (
                    "heating_circuit_curve2_temperature",
                    SK.HEATING_CURVE_PARALLEL_SHIFT_TEMPERATURE,
                ),
                (
                    "heating_circuit_curve_night_temperature",
                    SK.HEATING_CURVE_NIGHT_TEMPERATURE,
                ),
                (
                    "heating_night_lowering_to_temperature",
                    SK.HEATING_NIGHT_LOWERING_TO_TEMPERATURE,
                ),
                ("heating_hysteresis", SK.HEATING_HYSTERESIS),
                (
                    "heating_max_flow_out_increase_temperature",
                    SK.HEATING_MAX_FLOW_OUT_INCREASE_TEMPERATURE,
                ),
                (
                    "heating_maximum_circulation_pump_speed",
                    SK.HEATING_MAXIMUM_CIRCULATION_PUMP_SPEED,
                ),
                (
                    "heating_room_temperature_impact_factor",
                    SK.HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR,
                ),
            ],
            P.SWITCH: [
                ("remote_maintenance", SK.REMOTE_MAINTENANCE),
                ("efficiency_pump", SK.EFFICIENCY_PUMP),
                ("pump_heat_control", SK.PUMP_HEAT_CONTROL),
                ("heating", SK.HEATING),
                ("pump_optimization", SK.PUMP_OPTIMIZATION),
                ("heating_threshold", SK.HEATING_THRESHOLD),
                ("domestic_water", SK.DOMESTIC_WATER),
                ("cooling", SK.COOLING),
            ],
            P.CLIMATE: [
                ("heating", SK.HEATING),
                ("cooling", SK.COOLING),
            ],
        },
    )


async def _rename_cooling_entities(
    hass: HomeAssistant, config_entry: ConfigEntry
):  # pragma: no cover
    await _up_many(
        hass,
        config_entry,
        {
            P.NUMBER: [
                ("cooling_threshold_temperature", SK.COOLING_OUTDOOR_TEMP_THRESHOLD),
                ("cooling_start_delay_hours", SK.COOLING_START_DELAY_HOURS),
                ("cooling_stop_delay_hours", SK.COOLING_STOP_DELAY_HOURS),
            ]
        },
    )


async def _rename_curve_entities(
    hass: HomeAssistant, config_entry: ConfigEntry
):  # pragma: no cover
    await _up_many(
        hass,
        config_entry,
        {
            P.NUMBER: [
                ("flow_in_circuit2_temperature", SK.FLOW_IN_CIRCUIT1_TEMPERATURE),
                ("flow_in_circuit3_temperature", SK.FLOW_IN_CIRCUIT2_TEMPERATURE),
                (
                    "flow_in_circuit2_target_temperature",
                    SK.FLOW_IN_CIRCUIT1_TARGET_TEMPERATURE,
                ),
                (
                    "flow_in_circuit3_target_temperature",
                    SK.FLOW_IN_CIRCUIT2_TARGET_TEMPERATURE,
                ),
                (
                    "heating_circuit_curve1_temperature",
                    SK.HEATING_CURVE_END_TEMPERATURE,
                ),
                (
                    "heating_circuit_curve2_temperature",
                    SK.HEATING_CURVE_PARALLEL_SHIFT_TEMPERATURE,
                ),
                (
                    "heating_circuit_curve_night_temperature",
                    SK.HEATING_CURVE_NIGHT_TEMPERATURE,
                ),
                (
                    "heating_circuit2_curve1_temperature",
                    SK.HEATING_CURVE_CIRCUIT1_END_TEMPERATURE,
                ),
                (
                    "heating_circuit2_curve2_temperature",
                    SK.HEATING_CURVE_CIRCUIT1_PARALLEL_SHIFT_TEMPERATURE,
                ),
                (
                    "heating_circuit2_curve_night_temperature",
                    SK.HEATING_CURVE_CIRCUIT1_NIGHT_TEMPERATURE,
                ),
                (
                    "heating_circuit3_curve1_temperature",
                    SK.HEATING_CURVE_CIRCUIT3_END_TEMPERATURE,
                ),
                (
                    "heating_circuit3_curve2_temperature",
                    SK.HEATING_CURVE_CIRCUIT3_PARALLEL_SHIFT_TEMPERATURE,
                ),
                (
                    "heating_circuit3_curve_night_temperature",
                    SK.HEATING_CURVE_CIRCUIT3_NIGHT_TEMPERATURE,
                ),
            ]
        },
    )


async def _fix_select_entity_unique_ids(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Fix select entity unique_ids incorrectly using binary_sensor prefix.

    PR #563 fixed ENTITY_ID_FORMAT import in select.py from
    homeassistant.components.binary_sensor to homeassistant.components.select,
    changing unique_ids from binary_sensor.{prefix}_xxx to select.{prefix}_xxx.
    Migrate old unique_ids to prevent duplicate entities.
    """
    prefix = config_entry.data[CONF_HA_SENSOR_PREFIX]
    ent_reg = async_get(hass)
    select_keys = [
        SK.THERMAL_DESINFECTION_DAY,
        SK.DOMESTIC_WATER_MODE_SELECTOR,
        SK.HEATING_MODE_SELECTOR,
    ]
    for key in select_keys:
        old_unique_id = f"binary_sensor.{prefix}_{key}"
        new_unique_id = f"select.{prefix}_{key}"
        entity_id = ent_reg.async_get_entity_id(P.SELECT, DOMAIN, old_unique_id)
        if entity_id is not None:
            try:
                ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)
                LOGGER.info(
                    "Migrated select entity unique_id: %s -> %s",
                    old_unique_id,
                    new_unique_id,
                )
            except ValueError as err:
                LOGGER.warning(
                    "Could not migrate select entity %s: %s",
                    old_unique_id,
                    err,
                )


async def _up_many(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    mappings: dict[P, list[tuple[str, SK]]],
):
    prefix = config_entry.data[CONF_HA_SENSOR_PREFIX]
    ent_reg = async_get(hass)

    for platform, items in mappings.items():
        for ident, new_id in items:
            entity_id = f"{platform}.{prefix}_{ident}"
            new_ident = f"{platform}.{prefix}_{new_id}"
            try:
                ent_reg.async_update_entity(
                    entity_id, new_entity_id=new_ident, new_unique_id=new_ident
                )
            except KeyError as err:
                LOGGER.info(
                    "Skip rename entity - Not existing: %s -> %s",
                    entity_id,
                    new_ident,
                    exc_info=err,
                )
            except ValueError as err:
                LOGGER.warning(
                    "Could not rename entity %s -> %s",
                    entity_id,
                    new_ident,
                    exc_info=err,
                )
            except Exception as err:
                LOGGER.error(
                    "Could not rename entity %s -> %s",
                    entity_id,
                    new_ident,
                    exc_info=err,
                )


def _identifiers_exists(
    identifiers_list: list[set[tuple[str, str]]], identifiers: set[tuple[str, str]]
) -> bool:
    return any(ident == identifiers for ident in identifiers_list)


async def _async_delete_legacy_devices(
    hass: HomeAssistant, config_entry: ConfigEntry
):  # pragma: no cover
    coordinator = await connect_and_get_coordinator(hass, config_entry)
    dr_instance = dr.async_get(hass)
    devices: list[dr.DeviceEntry] = dr.async_entries_for_config_entry(
        dr_instance, config_entry.entry_id
    )
    identifiers_list = []
    for device_info in coordinator.device_infos.values():
        identifiers_list.append(device_info.get("identifiers", set()))
    for device_entry in devices:
        if not _identifiers_exists(identifiers_list, device_entry.identifiers):
            dr_instance.async_remove_device(device_entry.id)

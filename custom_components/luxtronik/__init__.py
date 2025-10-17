"""The Luxtronik heatpump integration."""

# region Imports
from __future__ import annotations
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, Platform as P
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_registry import (
    async_get,
)

from .const import (
    ATTR_PARAMETER,
    ATTR_VALUE,
    CONF_COORDINATOR,
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

# Apply global overrides before anything else
from .lux_overrides import update_Luxtronik_HeatpumpCodes, update_Luxtronik_Parameters
from .common import convert_to_int_if_possible
from .coordinator import LuxtronikCoordinator, connect_and_get_coordinator

# endregion Imports

# override HeatpumpCode datatype, so it includes recent Heatpump models
update_Luxtronik_HeatpumpCodes()
# update/extend Luxtronik.Parameters
update_Luxtronik_Parameters()

LOGGER.info("Custom HeatpumpCode and Parameters overrides applied.")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Luxtronik from a config entry."""

    data = hass.data.setdefault(DOMAIN, {})
    config = entry.data

    try:
        coordinator = await connect_and_get_coordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        LOGGER.error("Luxtronik connection failed: %s", err)
        raise ConfigEntryNotReady from err

    entry.async_on_unload(entry.add_update_listener(update_listener))

    data[entry.entry_id] = {CONF_COORDINATOR: coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Trigger a refresh again now that all platforms have registered
    # await coordinator.async_refresh()

    # 🛠️ Update title
    if coordinator.manufacturer is not None:
        new_title = (
            f"{coordinator.manufacturer} @ {config[CONF_HOST]}:{config[CONF_PORT]}"
        )
    else:
        new_title = f"Luxtronik @ {config[CONF_HOST]}:{config[CONF_PORT]}"
    LOGGER.info("new_title: %s", new_title)

    hass.config_entries.async_update_entry(entry, title=new_title.strip())

    setup_hass_services(hass, entry)

    LOGGER.info("Luxtronik integration setup completed for %s", entry.entry_id)

    return True


def setup_hass_services(hass: HomeAssistant, entry: ConfigEntry):
    """Home Assistant services."""

    async def write_parameter(service):
        """Write a parameter to the Luxtronik heatpump."""
        parameter = service.data.get(ATTR_PARAMETER)
        # convert to int needed for Unknown parameters
        value = convert_to_int_if_possible(service.data.get(ATTR_VALUE))
        data = hass.data[DOMAIN].get(entry.entry_id)
        coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]
        await coordinator.async_write(parameter, value)

    hass.services.async_register(
        DOMAIN, SERVICE_WRITE, write_parameter, schema=SERVICE_WRITE_SCHEMA
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]
        await coordinator.async_shutdown()

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry to the latest version."""
    current_version = config_entry.version
    latest_version = CONFIG_ENTRY_VERSION

    while current_version < latest_version:
        LOGGER.debug("Starting migration from version %s", current_version)
        new_data = {**config_entry.data}

        if current_version == 1:
            coordinator = await connect_and_get_coordinator(hass, config_entry)
            if CONF_HA_SENSOR_PREFIX not in new_data:
                new_data[CONF_HA_SENSOR_PREFIX] = "luxtronik"
            await hass.config_entries.async_update_entry(
                config_entry, data=new_data, version=2, unique_id=coordinator.unique_id
            )
            current_version = 2

        elif current_version == 2:
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

    LOGGER.info("Migration to version %s successful", current_version)
    return True


async def _async_update_config_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any], version: int
) -> None:
    """Update config entry with new data and version."""
    hass.config_entries.async_update_entry(config_entry, data=data, version=version)


async def _rename_entities(hass: HomeAssistant, config_entry: ConfigEntry):
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


async def _rename_cooling_entities(hass: HomeAssistant, config_entry: ConfigEntry):
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


async def _rename_curve_entities(hass: HomeAssistant, config_entry: ConfigEntry):
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
                await ent_reg.async_update_entity(
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
    for ident in identifiers_list:
        if ident == identifiers:
            return True
    return False


async def _async_delete_legacy_devices(hass: HomeAssistant, config_entry: ConfigEntry):
    coordinator = await connect_and_get_coordinator(hass, config_entry)
    dr_instance = dr.async_get(hass)
    devices: list[dr.DeviceEntry] = dr.async_entries_for_config_entry(
        dr_instance, config_entry.entry_id
    )
    identifiers_list = []
    for device_info in coordinator.device_infos.values():
        identifiers_list.append(device_info["identifiers"])
    for device_entry in devices:
        if not _identifiers_exists(identifiers_list, device_entry.identifiers):
            dr_instance.async_remove_device(device_entry.id)

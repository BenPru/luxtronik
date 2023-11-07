"""The Luxtronik heatpump integration."""
# region Imports
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TIMEOUT, Platform as P
from homeassistant.core import HomeAssistant
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
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SERVICE_WRITE,
    SERVICE_WRITE_SCHEMA,
    Parameter_SensorKey as LP,
    Calculation_SensorKey as LC,
)
from .coordinator import LuxtronikCoordinator

# endregion Imports


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Luxtronik from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # Create API instance
    coordinator = LuxtronikCoordinator.connect(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    entry.async_on_unload(entry.add_update_listener(update_listener))

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = {}
    data[entry.entry_id][CONF_COORDINATOR] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Trigger a refresh again now that all platforms have registered
    hass.async_create_task(coordinator.async_refresh())

    # hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    await hass.async_add_executor_job(setup_hass_services, hass, entry)

    return True


def setup_hass_services(hass: HomeAssistant, entry: ConfigEntry):
    """Home Assistant services."""

    def write_parameter(service):
        """Write a parameter to the Luxtronik heatpump."""
        parameter = service.data.get(ATTR_PARAMETER)
        value = service.data.get(ATTR_VALUE)
        coordinator = LuxtronikCoordinator.connect(hass, entry)
        coordinator.write(parameter, value)

    hass.services.register(
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
    """Migrate old entry."""

    LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        coordinator = LuxtronikCoordinator.connect(hass, config_entry)

        new = {**config_entry.data}
        if CONF_HA_SENSOR_PREFIX not in new:
            new[CONF_HA_SENSOR_PREFIX] = "luxtronik"
        config_entry.unique_id = coordinator.unique_id
        config_entry.supports_remove_device = True

        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new)

    if config_entry.version == 2:
        await _async_delete_legacy_devices(hass, config_entry)

        new = {**config_entry.data}
        config_entry.version = 3
        hass.config_entries.async_update_entry(config_entry, data=new)

    if config_entry.version == 3:
        # Ensure sensor prefix:
        if CONF_HA_SENSOR_PREFIX not in config_entry.data and (
            DOMAIN == "luxtronik2"
            or len(hass.config_entries.async_entries("luxtronik2")) > 0
        ):
            new_data = {**config_entry.data, CONF_HA_SENSOR_PREFIX: "luxtronik2"}
        else:
            new_data = {**config_entry.data}
        config_entry.version = 4
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    # Ensure sensor prefix:
    prefix = None
    ent_reg = None

    def _up(ident: str, new_id: LC | LP, platform: P = P.SENSOR) -> None:
        nonlocal prefix, ent_reg
        if prefix is None or ent_reg is None:
            prefix = config_entry.data[CONF_HA_SENSOR_PREFIX]
            ent_reg = async_get(hass)
        entity_id = f"{platform}.{prefix}_{ident}"
        new_ident = f"{platform}.{prefix}_{new_id.name.lower()}"
        try:
            ent_reg.async_update_entity(
                entity_id, new_entity_id=new_ident, new_unique_id=new_ident
            )
        except KeyError as err:
            LOGGER.info(
                "Skip rename entity - Not existing: %s->%s",
                entity_id,
                new_ident,
                exc_info=err,
            )
        except ValueError as err:
            LOGGER.warning(
                "Could not rename entity %s->%s", entity_id, new_ident, exc_info=err
            )
        except Exception as err:
            LOGGER.error(
                "Could not rename entity %s->%s", entity_id, new_ident, exc_info=err
            )

    if config_entry.version == 4:
        new_data = {**config_entry.data}
        config_entry.version = 5
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    if config_entry.version == 5:
        _up("heat_amount_domestic_water", LC.DHW_HEAT_AMOUNT)
        _up("domestic_water_energy_input", LP.DHW_ENERGY_INPUT)
        _up("domestic_water_temperature", LC.DHW_TEMPERATURE)
        _up("operation_hours_domestic_water", LC.DHW_OPERATION_HOURS)
        _up("domestic_water_target_temperature", LP.DHW_TARGET_TEMPERATURE, P.NUMBER)
        _up("domestic_water_hysteresis", LP.DHW_HYSTERESIS, P.NUMBER)
        _up(
            "domestic_water_thermal_desinfection_target",
            LP.DHW_THERMAL_DESINFECTION_TARGET,
            P.NUMBER,
        )
        _up(
            "domestic_water_recirculation_pump",
            LC.DHW_RECIRCULATION_PUMP,
            P.BINARY_SENSOR,
        )
        _up(
            "domestic_water_circulation_pump",
            LC.DHW_CIRCULATION_PUMP,
            P.BINARY_SENSOR,
        )
        _up("domestic_water_charging_pump", LP.DHW_CHARGING_PUMP, P.BINARY_SENSOR)

        # [sensor]
        _up("pump_frequency", LC.PUMP_FREQUENCY, P.SENSOR)
        _up("room_thermostat_temperature", LC.ROOM_THERMOSTAT_TEMPERATURE, P.SENSOR)
        _up(
            "room_thermostat_temperature_target",
            LC.ROOM_THERMOSTAT_TEMPERATURE_TARGET,
            P.SENSOR,
        )

        # [binary sensor]
        _up("evu_unlocked", LC.EVU_UNLOCKED, P.BINARY_SENSOR)
        _up("compressor", LC.COMPRESSOR, P.BINARY_SENSOR)
        _up("pump_flow", LC.PUMP_FLOW, P.BINARY_SENSOR)
        _up("compressor_heater", LC.COMPRESSOR_HEATER, P.BINARY_SENSOR)
        _up("defrost_valve", LC.DEFROST_VALVE, P.BINARY_SENSOR)
        _up("additional_heat_generator", LC.ADDITIONAL_HEAT_GENERATOR, P.BINARY_SENSOR)
        _up("disturbance_output", LC.DISTURBANCE_OUTPUT, P.BINARY_SENSOR)
        _up("circulation_pump_heating", LC.CIRCULATION_PUMP_HEATING, P.BINARY_SENSOR)
        _up(
            "additional_circulation_pump",
            LC.ADDITIONAL_CIRCULATION_PUMP,
            P.BINARY_SENSOR,
        )
        _up("approval_cooling", LC.APPROVAL_COOLING, P.BINARY_SENSOR)

        # [number]
        _up("release_second_heat_generator", LP.RELEASE_SECOND_HEAT_GENERATOR, P.NUMBER)
        _up(
            "release_time_second_heat_generator",
            LP.RELEASE_TIME_SECOND_HEAT_GENERATOR,
            P.NUMBER,
        )
        _up("heating_target_correction", LP.HEATING_TARGET_CORRECTION, P.NUMBER)
        _up("pump_optimization_time", LP.PUMP_OPTIMIZATION_TIME, P.NUMBER)
        _up("heating_threshold_temperature", LP.HEATING_THRESHOLD_TEMPERATURE, P.NUMBER)
        _up(
            "heating_min_flow_out_temperature",
            LP.HEATING_MIN_FLOW_OUT_TEMPERATURE,
            P.NUMBER,
        )
        _up(
            "heating_circuit_curve1_temperature",
            LP.HEATING_CIRCUIT_CURVE1_TEMPERATURE,
            P.NUMBER,
        )
        _up(
            "heating_circuit_curve2_temperature",
            LP.HEATING_CIRCUIT_CURVE2_TEMPERATURE,
            P.NUMBER,
        )
        _up(
            "heating_circuit_curve_night_temperature",
            LP.HEATING_CIRCUIT_CURVE_NIGHT_TEMPERATURE,
            P.NUMBER,
        )
        _up(
            "heating_night_lowering_to_temperature",
            LP.HEATING_NIGHT_LOWERING_TO_TEMPERATURE,
            P.NUMBER,
        )
        _up("heating_hysteresis", LP.HEATING_HYSTERESIS, P.NUMBER)
        _up(
            "heating_max_flow_out_increase_temperature",
            LP.HEATING_MAX_FLOW_OUT_INCREASE_TEMPERATURE,
            P.NUMBER,
        )
        _up(
            "heating_maximum_circulation_pump_speed",
            LP.HEATING_MAXIMUM_CIRCULATION_PUMP_SPEED,
            P.NUMBER,
        )
        _up(
            "heating_room_temperature_impact_factor",
            LP.HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR,
            P.NUMBER,
        )

        # [switch]
        _up("remote_maintenance", LP.REMOTE_MAINTENANCE, P.SWITCH)
        _up("efficiency_pump", LP.EFFICIENCY_PUMP, P.SWITCH)
        _up("pump_heat_control", LP.PUMP_HEAT_CONTROL, P.SWITCH)
        _up("heating", LP.HEATING, P.SWITCH)
        _up("pump_optimization", LP.PUMP_OPTIMIZATION, P.SWITCH)
        _up("heating_threshold", LP.HEATING_THRESHOLD, P.SWITCH)
        _up("domestic_water", LP.DOMESTIC_WATER, P.SWITCH)
        _up("cooling", LP.COOLING, P.SWITCH)

        # [climate]
        _up("heating", LP.HEATING, P.CLIMATE)
        _up("cooling", LP.COOLING, P.CLIMATE)

        new_data = {**config_entry.data}
        config_entry.version = 6
        new_data[CONF_TIMEOUT] = DEFAULT_TIMEOUT
        new_data[CONF_MAX_DATA_LENGTH] = DEFAULT_MAX_DATA_LENGTH
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    if config_entry.version == 6:
        _up(
            "cooling_threshold_temperature", LP.COOLING_OUTDOOR_TEMP_THRESHOLD, P.NUMBER
        )
        _up("cooling_start_delay_hours", LP.COOLING_START_DELAY_HOURS, P.NUMBER)
        _up("cooling_stop_delay_hours", LP.COOLING_STOP_DELAY_HOURS, P.NUMBER)

        new_data = {**config_entry.data}
        config_entry.version = 7
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


def _identifiers_exists(
    identifiers_list: list[set[tuple[str, str]]], identifiers: set[tuple[str, str]]
) -> bool:
    for ident in identifiers_list:
        if ident == identifiers:
            return True
    return False


async def _async_delete_legacy_devices(hass: HomeAssistant, config_entry: ConfigEntry):
    coordinator = LuxtronikCoordinator.connect(hass, config_entry)
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

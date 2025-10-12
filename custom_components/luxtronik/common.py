"""Support for Luxtronik classes."""

# region Imports
from typing import Any

from functools import partial
from ipaddress import IPv6Address, ip_address
from getmac import get_mac_address

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry
from homeassistant.helpers.state import state_as_number

from .const import (
    CONF_CALCULATIONS,
    CONF_PARAMETERS,
    CONF_VISIBILITIES,
    LOGGER,
    LuxCalculation as LC,
    LuxOperationMode,
    LuxParameter as LP,
    LuxStatus1Option,
    LuxStatus3Option,
    LuxVisibility as LV,
)
from .model import LuxtronikCoordinatorData

# endregion Imports


def get_sensor_data(
    coordinator: LuxtronikCoordinatorData,
    luxtronik_key: str | LP | LC | LV,
    warn_unset=True,
) -> Any:
    """Get sensor data."""
    if coordinator is None:
        return None
    if luxtronik_key is None or "." not in luxtronik_key:
        if warn_unset:
            LOGGER.warning(
                "Function get_sensor_data luxtronik_key %s is None", luxtronik_key
            )
        return None
    elif "{" in luxtronik_key:
        return None
    key = luxtronik_key.split(".")
    group: str = key[0]
    sensor_id: str = key[1]

    if group == CONF_PARAMETERS:
        sensor = coordinator.parameters.get(sensor_id)
    elif group == CONF_CALCULATIONS:
        sensor = coordinator.calculations.get(sensor_id)
    elif group == CONF_VISIBILITIES:
        sensor = coordinator.visibilities.get(sensor_id)
    else:
        raise NotImplementedError
    if sensor is None:
        LOGGER.warning(
            "Get_sensor %s returns None",
            sensor_id,
        )
        return None
    return correct_key_value(sensor.value, coordinator, luxtronik_key)


def correct_key_value(
    value: Any,
    coordinator: LuxtronikCoordinatorData | None,
    sensor_id: str | LP | LC | LV,
) -> Any:
    """Handle special value corrections."""
    # prevent dealing with None value below
    if value is None:
        return value
    # fix 'states may not contain spaces ea for valid translations'
    if sensor_id in [
        LC.C0080_STATUS,
        LC.C0117_STATUS_LINE_1,
        LC.C0119_STATUS_LINE_3,
    ]:
        value = value.replace(" ", "_").replace("/", "_").lower()
    if sensor_id in [
        LC.C0100_ERROR_REASON,
        # LP.P0716_0720_SWITCHOFF_REASON,
    ] and ((value == -1) or (value == "-1")):
        value = "minus_1"

    if (
        sensor_id == LC.C0080_STATUS
        and value == LuxOperationMode.heating
        and not get_sensor_data(coordinator, LC.C0044_COMPRESSOR)
        and not get_sensor_data(coordinator, LC.C0048_ADDITIONAL_HEAT_GENERATOR)
    ):
        return LuxOperationMode.no_request
    # region Workaround Luxtronik Bug: Line 1 shows 'heatpump coming' on shutdown!
    if (
        sensor_id == LC.C0117_STATUS_LINE_1
        and value == LuxStatus1Option.heatpump_coming
        and int(get_sensor_data(coordinator, LC.C0072_TIMER_SCB_ON)) < 10
        and int(get_sensor_data(coordinator, LC.C0071_TIMER_SCB_OFF)) > 0
    ):
        return LuxStatus1Option.heatpump_shutdown
    # endregion Workaround Luxtronik Bug: Line 1 shows 'heatpump coming' on shutdown!
    # region Workaround Luxtronik Bug: Line 1 shows 'pump forerun' on CompressorHeater!
    if (
        sensor_id == LC.C0117_STATUS_LINE_1
        and value == LuxStatus1Option.pump_forerun
        and bool(get_sensor_data(coordinator, LC.C0182_COMPRESSOR_HEATER))
    ):
        return LuxStatus1Option.compressor_heater
    # endregion Workaround Luxtronik Bug: Line 1 shows 'pump forerun' on CompressorHeater!
    # region Workaround Detect passive cooling operation mode
    if (
        sensor_id == LC.C0080_STATUS
        and value == LuxOperationMode.no_request
        and bool(
            get_sensor_data(coordinator, LC.C0119_STATUS_LINE_3)
            == LuxStatus3Option.cooling.value
        )
    ):
        return LuxOperationMode.cooling
    # endregion Workaround Detect passive cooling operation mode
    # region Workaround Detect active cooling operation mode
    if (
        sensor_id == LC.C0080_STATUS
        and value == LuxOperationMode.no_request
        and bool(
            get_sensor_data(coordinator, LC.C0119_STATUS_LINE_3)
            in LuxStatus3Option.heating.value
        )
    ):
        T_in = get_sensor_data(coordinator, LC.C0010_FLOW_IN_TEMPERATURE)
        T_out = get_sensor_data(coordinator, LC.C0011_FLOW_OUT_TEMPERATURE)
        T_heat_in = get_sensor_data(coordinator, LC.C0204_HEAT_SOURCE_INPUT_TEMPERATURE)
        T_heat_out = get_sensor_data(coordinator, LC.C0024_HEAT_SOURCE_OUTPUT_TEMPERATURE)
        Flow_WQ = get_sensor_data(coordinator, LC.C0173_HEAT_SOURCE_FLOW_RATE)
        Pump = get_sensor_data(coordinator, LC.C0043_PUMP_FLOW)
        if (T_out > T_in) and (T_heat_out > T_heat_in) and (Flow_WQ > 0) and Pump:
            return LuxOperationMode.cooling
    # endregion Workaround Detect active cooling operation mode

    # no changes needed, return sensor value
    return value


def state_as_number_or_none(state: State, default: float | None = None) -> float | None:
    """Try to coerce our state to a number.

    Raises ValueError if this is not possible.
    """
    if state is None:
        return default
    if state.state in (STATE_UNAVAILABLE):
        return default  # state.state
    result = state_as_number(state)
    return default if not isinstance(result, float) or result is None else result


async def async_get_mac_address(hass: HomeAssistant, host: str) -> str | None:
    """Get mac address from host name, IPv4 address, or IPv6 address."""
    # Help mypy, which has trouble with the async_add_executor_job + partial call
    mac_address: str | None
    # getmac has trouble using IPv6 addresses as the "hostname" parameter so
    # assume host is an IP address, then handle the case it's not.
    try:
        ip_addr = ip_address(host)
    except ValueError:
        mac_address = await hass.async_add_executor_job(
            partial(get_mac_address, hostname=host)
        )
    else:
        if ip_addr.version == 4:
            mac_address = await hass.async_add_executor_job(
                partial(get_mac_address, ip=host)
            )
        else:
            # Drop scope_id from IPv6 address by converting via int
            ip_addr = IPv6Address(int(ip_addr))
            mac_address = await hass.async_add_executor_job(
                partial(get_mac_address, ip6=str(ip_addr))
            )

    if not mac_address:
        return None

    return device_registry.format_mac(mac_address)

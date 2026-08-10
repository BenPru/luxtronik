"""Support for Luxtronik classes."""

# region Imports
from functools import partial
from ipaddress import IPv6Address, ip_address
from typing import Any

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
    PARSED_COUNT_ATTR,
    LuxCalculation as LC,
    LuxOperationMode,
    LuxParameter as LP,
    LuxStatus1Option,
    LuxStatus3Option,
    LuxVisibility as LV,
)
from .lux_overrides import UPSTREAM_MAX_DEFINED_INDEX
from .model import LuxtronikCoordinatorData

# endregion Imports


def _register_returned(group_data: Any, group: str, index: int) -> bool:
    """Did the controller actually return this register in its last read?

    The library's definition dict is static, so a definition existing proves
    nothing about the connected unit.  The recorded block length does: the
    controller returned indices 0..count-1 and nothing else, the block being
    positional and always dense.

    The conclusion is drawn only above upstream's own definition range, which
    is where every register this can affect lives.  Inside that range the
    pre-existing behaviour is kept, so a controller returning a shorter block
    than any we have seen - an old 1.x unit, or a read truncated mid-transfer,
    which the library swallows silently - cannot make entities disappear
    wholesale.

    Absence is deliberately not inferred from ``.value is None`` - a register
    that IS present reads ``None`` too when its datatype cannot decode the raw
    value (``SelectionBase`` returns ``None`` for an unrecognised code).
    """
    upstream_max = UPSTREAM_MAX_DEFINED_INDEX.get(group)
    if upstream_max is None or index <= upstream_max:
        return True
    parsed_count = getattr(group_data, PARSED_COUNT_ATTR, None)
    if not isinstance(parsed_count, int):
        # No count recorded: the object was built directly rather than through
        # a patched parse() (tests, diagnostics). Definition presence is all
        # we have, which is the behaviour this function replaced.
        return True
    if index >= parsed_count:
        LOGGER.debug(
            "Register %s index %d is beyond the %d values this controller "
            "returned - not creating its entity",
            group,
            index,
            parsed_count,
        )
        return False
    return True


def key_exists(
    coordinator: LuxtronikCoordinatorData, luxtronik_key: str | LP | LC | LV
) -> bool:
    """Check if the given Luxtronik key exists in the coordinator's data by matching item.name."""
    try:
        if luxtronik_key == LC.UNSET:
            return False
        key_str = str(luxtronik_key)
        if not key_str or "." not in key_str or "{" in key_str:
            return False

        group, sensor_id = key_str.split(".", 1)
        LOGGER.debug(
            "Checking key existence: %s (group: %s, sensor_id: %s)",
            key_str,
            group,
            sensor_id,
        )

        if group == CONF_PARAMETERS:
            group_data = coordinator.parameters
            items = group_data.parameters.items()
        elif group == CONF_CALCULATIONS:
            group_data = coordinator.calculations
            items = group_data.calculations.items()
        elif group == CONF_VISIBILITIES:
            group_data = coordinator.visibilities
            items = group_data.visibilities.items()
        else:
            return False

        index = next((i for i, item in items if item.name == sensor_id), None)
        if index is None:
            return False
        return _register_returned(group_data, group, index)
    except Exception as e:
        LOGGER.error("Error checking key existence: %s", e)
        return False


def get_sensor_data(
    coordinator: LuxtronikCoordinatorData,
    luxtronik_key: str | LP | LC | LV,
    warn_unset=True,
    raw_value=False,
) -> Any:
    """Get sensor data."""
    if coordinator is None:
        return None
    if luxtronik_key == LC.UNSET:
        return None
    if luxtronik_key is None or "." not in luxtronik_key:
        if warn_unset:
            LOGGER.warning(
                "Function get_sensor_data luxtronik_key %s is None", luxtronik_key
            )
        return None
    elif "{" in luxtronik_key:
        return None

    group, sensor_id = luxtronik_key.split(".", 1)

    if group == CONF_PARAMETERS:
        sensor = coordinator.parameters.get(sensor_id)
    elif group == CONF_CALCULATIONS:
        sensor = coordinator.calculations.get(sensor_id)
    elif group == CONF_VISIBILITIES:
        sensor = coordinator.visibilities.get(sensor_id)
    else:
        raise NotImplementedError
    if sensor is None:
        LOGGER.warning("Get_sensor %s (%s) returns None", sensor_id, luxtronik_key)
        return None
    value = sensor.value  # pyright: ignore[reportAttributeAccessIssue]
    return (
        value
        if raw_value
        else normalize_sensor_value(value, coordinator, luxtronik_key)
    )


def _derive_operation_mode(value: Any, coordinator: LuxtronikCoordinatorData) -> Any:
    """Derive the effective operation mode for C0080_STATUS.

    The Luxtronik controller's raw status word is unreliable in several
    documented cases (passive/active cooling reported as no_request, thermal
    disinfection reported as heating, heating reported while the compressor is
    off). Each ``if`` below is one such workaround. Returns ``value`` unchanged
    when no workaround applies.
    """
    status_line3_raw = get_sensor_data(
        coordinator, LC.C0119_STATUS_LINE_3, raw_value=True
    )

    if status_line3_raw == LuxStatus3Option.thermal_desinfection:
        return LuxOperationMode.domestic_water

    status_line1 = get_sensor_data(coordinator, LC.C0117_STATUS_LINE_1)
    status_line3 = get_sensor_data(coordinator, LC.C0119_STATUS_LINE_3)
    add_circ_pump = get_sensor_data(coordinator, LC.C0047_ADDITIONAL_CIRCULATION_PUMP)
    s1_workaround: list[str] = [
        LuxStatus1Option.heatpump_idle,
        LuxStatus1Option.pump_forerun,
        LuxStatus1Option.heatpump_coming,
    ]
    s3_workaround: list[str | None] = [
        LuxStatus3Option.no_request,
        LuxStatus3Option.unknown,
        LuxStatus3Option.none,
        LuxStatus3Option.grid_switch_on_delay,
        None,
    ]
    if (
        status_line1 in s1_workaround
        and status_line3 in s3_workaround
        and not add_circ_pump
    ):
        return LuxOperationMode.no_request

    if (
        status_line3
        in [
            LuxStatus3Option.no_request,
            LuxStatus3Option.cycle_lock,
            LuxStatus3Option.heating,
        ]
        and get_sensor_data(coordinator, LC.C0038_DHW_RECIRCULATION_PUMP)
        and get_sensor_data(coordinator, LC.C0048_ADDITIONAL_HEAT_GENERATOR)
    ):
        return LuxOperationMode.domestic_water

    if value == LuxOperationMode.no_request:
        if (
            status_line3_raw is not None
            and status_line3_raw == LuxStatus3Option.cooling
        ):
            return LuxOperationMode.cooling

        if (
            status_line3_raw is not None
            and status_line3_raw == LuxStatus3Option.heating
        ):
            T_in = get_sensor_data(coordinator, LC.C0010_FLOW_IN_TEMPERATURE)
            T_out = get_sensor_data(coordinator, LC.C0011_FLOW_OUT_TEMPERATURE)
            T_heat_in = get_sensor_data(
                coordinator, LC.C0204_HEAT_SOURCE_INPUT_TEMPERATURE
            )
            T_heat_out = get_sensor_data(
                coordinator, LC.C0024_HEAT_SOURCE_OUTPUT_TEMPERATURE
            )
            Flow_WQ = get_sensor_data(coordinator, LC.C0173_HEAT_SOURCE_FLOW_RATE)
            Pump = get_sensor_data(coordinator, LC.C0043_PUMP_FLOW)
            if (T_out > T_in) and (T_heat_out > T_heat_in) and (Flow_WQ > 0) and Pump:
                return LuxOperationMode.cooling

    if (
        value == LuxOperationMode.heating
        and not get_sensor_data(coordinator, LC.C0044_COMPRESSOR)
        and not get_sensor_data(coordinator, LC.C0048_ADDITIONAL_HEAT_GENERATOR)
    ):
        return LuxOperationMode.no_request

    return value


def normalize_sensor_value(
    value: Any,
    coordinator: LuxtronikCoordinatorData | None,
    sensor_id: str | LP | LC | LV,
) -> Any:
    """Normalize special Luxtronik sensor values."""
    # prevent dealing with None value, and skip unnecessary processing
    if value is None or coordinator is None or sensor_id is None:
        return value

    # Normalize all string values for translation safety across sensors.
    # Replace spaces and slashes and lower-case the value so Home Assistant
    # translations remain valid regardless of the originating sensor.
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

    if sensor_id == LC.C0080_STATUS:
        mode = _derive_operation_mode(value, coordinator)
        # Transition hold: the controller briefly reports no_request while
        # moving from normal DHW heating into thermal disinfection, even though
        # the DHW recirculation pump keeps running (issue #519). The coordinator
        # decides once per poll whether we are inside such a window; here we
        # only honour that decision. Scoped to no_request so a genuine switch to
        # cooling or heating is never masked.
        if mode == LuxOperationMode.no_request and coordinator.dhw_transition_hold:
            return LuxOperationMode.domestic_water
        return mode

    # no changes needed, return sensor value
    return value


def state_as_number_or_none(state: State, default: float | None = None) -> float | None:
    """Try to coerce our state to a number, returning default if not possible."""
    if state is None:
        return default
    if state.state == STATE_UNAVAILABLE:
        return default  # state.state
    try:
        result = state_as_number(state)
    except ValueError:
        return default
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


def convert_to_int_if_possible(value: str) -> int | str:
    try:
        return int(value)
    except ValueError:
        return value

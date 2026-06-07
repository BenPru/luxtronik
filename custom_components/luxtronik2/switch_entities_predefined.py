"""Luxtronik switch definitions."""

from homeassistant.const import EntityCategory

from .const import (
    UPDATE_INTERVAL_NORMAL,
    DeviceKey,
    LuxMode,
    LuxParameter as LP,
    LuxVisibility as LV,
    SensorKey,
)
from .model import LuxtronikSwitchDescription

SWITCHES: list[LuxtronikSwitchDescription] = [
    # Switch
    # ...
    # region Main heatpump
    LuxtronikSwitchDescription(
        luxtronik_key=LP.P0860_REMOTE_MAINTENANCE,
        key=SensorKey.REMOTE_MAINTENANCE,
        entity_category=EntityCategory.CONFIG,
    ),
    LuxtronikSwitchDescription(
        luxtronik_key=LP.P0869_EFFICIENCY_PUMP,
        key=SensorKey.EFFICIENCY_PUMP,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        # device_class=SensorDeviceClass.HEAT
    ),
    LuxtronikSwitchDescription(
        key=SensorKey.SMART_GRID_SWITCH,
        luxtronik_key=LP.P1030_SMART_GRID_SWITCH,
        entity_category=EntityCategory.CONFIG,
    ),
    LuxtronikSwitchDescription(
        luxtronik_key=LP.P1033_PUMP_HEAT_CONTROL,
        key=SensorKey.PUMP_HEAT_CONTROL,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        # device_class=SensorDeviceClass.HEAT
    ),
    LuxtronikSwitchDescription(
        key=SensorKey.ELECTRICAL_POWER_LIMITATION_SWITCH,
        luxtronik_key=LP.P1158_POWER_LIMIT_SWITCH,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        visibility=LV.V0357_ELECTRICAL_POWER_LIMITATION_SWITCH,
        # min_firmware_version_minor=FirmwareVersionMinor.minor_90,
    ),
    LuxtronikSwitchDescription(
        key=SensorKey.THERMAL_POWER_LIMITATION_SWITCH,
        luxtronik_key=LP.P1175_THERMAL_POWER_LIMIT_SWITCH,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        # min_firmware_version_minor=FirmwareVersionMinor.minor_90,
    ),
    # LuxtronikSwitchDescription(
    #     luxtronik_key=LP.P0870_AMOUNT_COUNTER_ACTIVE,
    #     key="amount_counter_active",
    #     icon="mdi:counter",
    #     entity_category=EntityCategory.CONFIG,
    # ),
    # endregion Main heatpump
    # region Heating
    LuxtronikSwitchDescription(
        device_key=DeviceKey.heating,
        luxtronik_key=LP.P0003_MODE_HEATING,
        key=SensorKey.HEATING,
        device_class=None,
        on_state=LuxMode.automatic,
        off_state=LuxMode.off,
        update_interval=UPDATE_INTERVAL_NORMAL,
    ),
    LuxtronikSwitchDescription(
        device_key=DeviceKey.heating,
        luxtronik_key=LP.P0049_PUMP_OPTIMIZATION,
        key=SensorKey.PUMP_OPTIMIZATION,
        entity_category=EntityCategory.CONFIG,
        visibility=LV.V0144_PUMP_OPTIMIZATION,
    ),
    LuxtronikSwitchDescription(
        device_key=DeviceKey.heating,
        luxtronik_key=LP.P0699_HEATING_THRESHOLD,
        key=SensorKey.HEATING_THRESHOLD,
        entity_category=EntityCategory.CONFIG,
    ),
    LuxtronikSwitchDescription(
        device_key=DeviceKey.heating,
        luxtronik_key=LP.P0678_VENTING_HUP_ACTIVE,
        key=SensorKey.PUMP_VENT_HUP,
        entity_category=EntityCategory.CONFIG,
        visibility=LV.V0163_PUMP_VENT_HUP,
    ),
    LuxtronikSwitchDescription(
        device_key=DeviceKey.heating,
        luxtronik_key=LP.P0158_VENTING_ACTIVE,
        key=SensorKey.PUMP_VENT_ACTIVE,
        entity_category=EntityCategory.CONFIG,
    ),
    # endregion Heating
    # region Domestic water
    LuxtronikSwitchDescription(
        device_key=DeviceKey.domestic_water,
        luxtronik_key=LP.P0004_MODE_DHW,
        key=SensorKey.DOMESTIC_WATER,
        device_class=None,
        on_state=LuxMode.automatic,
        on_states=[
            LuxMode.automatic,
            LuxMode.second_heatsource,
            LuxMode.party,
            LuxMode.holidays,
        ],
        off_state=LuxMode.off,
        update_interval=UPDATE_INTERVAL_NORMAL,
    ),
    # endregion Domestic water
    # region Cooling
    LuxtronikSwitchDescription(
        device_key=DeviceKey.cooling,
        luxtronik_key=LP.P0108_MODE_COOLING,
        key=SensorKey.COOLING,
        device_class=None,
        on_state=LuxMode.automatic,
        off_state=LuxMode.off,
        update_interval=UPDATE_INTERVAL_NORMAL,
    ),
    # endregion Cooling
]

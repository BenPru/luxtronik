"""Luxtronik switch definitions."""
from homeassistant.helpers.entity import EntityCategory

from .const import (
    UPDATE_INTERVAL_NORMAL,
    UPDATE_INTERVAL_VERY_SLOW,
    DeviceKey,
    LuxMode,
    LuxParameter as LP,
    LuxVisibility as LV,
    FirmwareVersionMinor,
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
        icon="mdi:remote-desktop",
        entity_category=EntityCategory.CONFIG,
    ),
    LuxtronikSwitchDescription(
        luxtronik_key=LP.P0869_EFFICIENCY_PUMP,
        key=SensorKey.EFFICIENCY_PUMP,
        icon="mdi:leaf-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        # device_class=SensorDeviceClass.HEAT
    ),
        LuxtronikSwitchDescription(
        key=SensorKey.SMART_GRID_SWITCH,
        luxtronik_key=LP.P1030_SMART_GRID_SWITCH,
        icon="mdi:grid",
        entity_category=EntityCategory.CONFIG,
    ),
    LuxtronikSwitchDescription(
        luxtronik_key=LP.P1033_PUMP_HEAT_CONTROL,
        key=SensorKey.PUMP_HEAT_CONTROL,
        icon="mdi:pump",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        # device_class=SensorDeviceClass.HEAT
    ),
    LuxtronikSwitchDescription(
        key=SensorKey.ELECTRICAL_POWER_LIMITATION_SWITCH,
        luxtronik_key=LP.P1158_POWER_LIMIT_SWITCH,
        icon="mdi:download-lock",
        entity_category=EntityCategory.CONFIG,
        visibility=LV.V0357_ELECTRICAL_POWER_LIMITATION_SWITCH,
        min_firmware_version_minor=FirmwareVersionMinor.minor_90,
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
        icon_by_state={True: "mdi:radiator", False: "mdi:radiator-off"},
        device_class=None,
        on_state=LuxMode.automatic.value,
        off_state=LuxMode.off.value,
        update_interval=UPDATE_INTERVAL_NORMAL,
    ),
    LuxtronikSwitchDescription(
        device_key=DeviceKey.heating,
        luxtronik_key=LP.P0049_PUMP_OPTIMIZATION,
        key=SensorKey.PUMP_OPTIMIZATION,
        icon="mdi:tune",
        entity_category=EntityCategory.CONFIG,
        visibility=LV.V0144_PUMP_OPTIMIZATION,
    ),
    LuxtronikSwitchDescription(
        device_key=DeviceKey.heating,
        luxtronik_key=LP.P0699_HEATING_THRESHOLD,
        key=SensorKey.HEATING_THRESHOLD,
        icon="mdi:download-outline",
        entity_category=EntityCategory.CONFIG,
    ),
    LuxtronikSwitchDescription(
        device_key=DeviceKey.heating,
        luxtronik_key=LP.P0678_VENTING_HUP_ACTIVE,
        key=SensorKey.PUMP_VENT_HUP,
        icon="mdi:pump",
        entity_category=EntityCategory.CONFIG,
        visibility=LV.V0163_PUMP_VENT_HUP,
    ),
        LuxtronikSwitchDescription(
        device_key=DeviceKey.heating,
        luxtronik_key=LP.P0158_VENTING_ACTIVE,
        key=SensorKey.PUMP_VENT_ACTIVE,
        icon="mdi:pump",
        entity_category=EntityCategory.CONFIG,
    ),
    # endregion Heating
    # region Domestic water
    LuxtronikSwitchDescription(
        device_key=DeviceKey.domestic_water,
        luxtronik_key=LP.P0004_MODE_DHW,
        key=SensorKey.DOMESTIC_WATER,
        icon_by_state={True: "mdi:water-boiler-auto", False: "mdi:water-boiler-off"},
        device_class=None,
        on_state=LuxMode.automatic.value,
        on_states=[
            LuxMode.automatic.value,
            LuxMode.second_heatsource.value,
            LuxMode.party.value,
            LuxMode.holidays.value,
        ],
        off_state=LuxMode.off.value,
        update_interval=UPDATE_INTERVAL_NORMAL,
    ),
    # endregion Domestic water
    # region Cooling
    LuxtronikSwitchDescription(
        device_key=DeviceKey.cooling,
        luxtronik_key=LP.P0108_MODE_COOLING,
        key=SensorKey.COOLING,
        icon="mdi:snowflake",
        entity_category=EntityCategory.CONFIG,
        device_class=None,
        on_state=LuxMode.automatic.value,
        off_state=LuxMode.off.value,
        update_interval=UPDATE_INTERVAL_NORMAL,
    ),
    # endregion Cooling
]

"""Luxtronik switch definitions."""
from homeassistant.helpers.entity import EntityCategory

from .const import (
    UPDATE_INTERVAL_NORMAL,
    DeviceKey,
    LuxMode,
    Parameter_SensorKey as LP,
    Visibility_SensorKey as LV,
)
from .model import LuxtronikSwitchDescription

SWITCHES: list[LuxtronikSwitchDescription] = [
    # Switch
    # ...
    # region Main heatpump
    LuxtronikSwitchDescription(
        luxtronik_key=LP.REMOTE_MAINTENANCE,
        icon="mdi:remote-desktop",
        entity_category=EntityCategory.CONFIG,
    ),
    LuxtronikSwitchDescription(
        luxtronik_key=LP.EFFICIENCY_PUMP,
        icon="mdi:leaf-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        # device_class=SensorDeviceClass.HEAT
    ),
    LuxtronikSwitchDescription(
        luxtronik_key=LP.PUMP_HEAT_CONTROL,
        icon="mdi:pump",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        # device_class=SensorDeviceClass.HEAT
    ),
    LuxtronikSwitchDescription(
        luxtronik_key=LP.SILENT_MODE,
        icon="mdi:volume-minus",
        entity_category=EntityCategory.CONFIG,
        visibility=LV.SILENT_MODE_TIME_MENU,
    ),
    # LuxtronikSwitchDescription(
    #     luxtronik_key=LP.AMOUNT_COUNTER_ACTIVE,
    #     key="amount_counter_active",
    #     icon="mdi:counter",
    #     entity_category=EntityCategory.CONFIG,
    # ),
    # endregion Main heatpump
    # region Heating
    LuxtronikSwitchDescription(
        key="heating",
        luxtronik_key=LP.MODE_HEATING,
        device_key=DeviceKey.heating,
        icon_by_state={True: "mdi:radiator", False: "mdi:radiator-off"},
        device_class=None,
        on_state=LuxMode.automatic.value,
        off_state=LuxMode.off.value,
        update_interval=UPDATE_INTERVAL_NORMAL,
    ),
    LuxtronikSwitchDescription(
        luxtronik_key=LP.PUMP_OPTIMIZATION,
        device_key=DeviceKey.heating,
        icon="mdi:tune",
        entity_category=EntityCategory.CONFIG,
        visibility=LV.PUMP_OPTIMIZATION,
    ),
    LuxtronikSwitchDescription(
        luxtronik_key=LP.HEATING_THRESHOLD,
        device_key=DeviceKey.heating,
        icon="mdi:download-outline",
        entity_category=EntityCategory.CONFIG,
    ),
    # endregion Heating
    # region Domestic water
    LuxtronikSwitchDescription(
        key="domestic_water",
        luxtronik_key=LP.MODE_DHW,
        device_key=DeviceKey.domestic_water,
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
    LuxtronikSwitchDescription(
        luxtronik_key=LP.DHW_RECIRCULATION_PUMP_DEAERATE,
        device_key=DeviceKey.domestic_water,
        icon_by_state={True: "mdi:pump", False: "mdi:pump-off"},
        device_class=None,
    ),
    # endregion Domestic water
    # region Cooling
    LuxtronikSwitchDescription(
        key="cooling",
        luxtronik_key=LP.MODE_COOLING,
        device_key=DeviceKey.cooling,
        icon="mdi:snowflake",
        entity_category=EntityCategory.CONFIG,
        device_class=None,
        on_state=LuxMode.automatic.value,
        off_state=LuxMode.off.value,
        update_interval=UPDATE_INTERVAL_NORMAL,
    ),
    # endregion Cooling
]

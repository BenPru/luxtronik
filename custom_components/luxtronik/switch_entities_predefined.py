"""All descriptions can be found here. Mostly the Boolean data types in the default instruction set of each category end up being a Switch."""
from homeassistant.helpers.entity import EntityCategory

from .const import DeviceKey, LuxMode, LuxParameter, LuxVisibility
from .model import LuxtronikSwitchDescription

SWITCHES: list[LuxtronikSwitchDescription] = [
    # Switch
    # ...
    # region Main heatpump
    LuxtronikSwitchDescription(
        luxtronik_key=LuxParameter.P0860_REMOTE_MAINTENANCE,
        key="remote_maintenance",
        icon="mdi:remote-desktop",
        entity_category=EntityCategory.CONFIG,
    ),
    LuxtronikSwitchDescription(
        luxtronik_key=LuxParameter.P0869_EFFICIENCY_PUMP,
        key="efficiency_pump",
        icon="mdi:leaf-circle",
        entity_category=EntityCategory.CONFIG,
        # device_class=SensorDeviceClass.HEAT
    ),
    LuxtronikSwitchDescription(
        luxtronik_key=LuxParameter.P1033_PUMP_HEAT_CONTROL,
        key="pump_heat_control",
        icon="mdi:pump",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        # device_class=SensorDeviceClass.HEAT
    ),
    # LuxtronikSwitchDescription(
    #     luxtronik_key=LuxParameter.P0870_AMOUNT_COUNTER_ACTIVE,
    #     key="amount_counter_active",
    #     icon="mdi:counter",
    #     entity_category=EntityCategory.CONFIG,
    # ),
    # endregion Main heatpump
    # region Heating
    LuxtronikSwitchDescription(
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0003_MODE_HEATING,
        key="heating",
        icon="mdi:radiator",
        icon_off="mdi:radiator-off",
        device_class=None,
        on_state=LuxMode.automatic.value,
        off_state=LuxMode.off.value,
    ),
    LuxtronikSwitchDescription(
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0049_PUMP_OPTIMIZATION,
        key="pump_optimization",
        icon="mdi:tune",
        entity_category=EntityCategory.CONFIG,
        visibility=LuxVisibility.V0144_PUMP_OPTIMIZATION,
    ),
    LuxtronikSwitchDescription(
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0699_HEATING_THRESHOLD,
        key="heating_threshold",
        icon="mdi:download-outline",
        entity_category=EntityCategory.CONFIG,
    ),
    # endregion Heating
    # region Domestic water
    LuxtronikSwitchDescription(
        device_key=DeviceKey.domestic_water,
        luxtronik_key=LuxParameter.P0004_MODE_DOMESTIC_WATER,
        key="domestic_water",
        icon="mdi:water-boiler",
        icon_on="mdi:water-boiler-auto",
        icon_off="mdi:water-boiler-off",
        device_class=None,
        on_state=LuxMode.automatic.value,
        on_states=[
            LuxMode.automatic.value,
            LuxMode.second_heatsource.value,
            LuxMode.party.value,
            LuxMode.holidays.value,
        ],
        off_state=LuxMode.off.value,
    ),
    # endregion Domestic water
    # region Cooling
    LuxtronikSwitchDescription(
        device_key=DeviceKey.cooling,
        luxtronik_key=LuxParameter.P0108_MODE_COOLING,
        key="cooling",
        icon="mdi:snowflake",
        entity_category=EntityCategory.CONFIG,
        device_class=None,
        on_state=LuxMode.automatic.value,
        off_state=LuxMode.off.value,
    ),
    # endregion Cooling
]

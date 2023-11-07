"""Luxtronik binary sensors definitions."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from .const import DeviceKey, Calculation_SensorKey as LC, Visibility_SensorKey as LV
from .model import LuxtronikBinarySensorEntityDescription

BINARY_SENSORS: list[LuxtronikBinarySensorEntityDescription] = [
    # region Main heatpump
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.EVU_UNLOCKED,
        icon="mdi:lock",
        device_class=BinarySensorDeviceClass.LOCK,
        visibility=LV.EVU_LOCKED,
    ),
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.COMPRESSOR,
        icon="mdi:arrow-collapse-all",
        device_class=BinarySensorDeviceClass.RUNNING,
        event_id_on_true="IMPULSE_START",
        event_id_on_false="IMPULSE_END",
    ),
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.COMPRESSOR2,
        icon="mdi:arrow-collapse-all",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.PUMP_FLOW,
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.COMPRESSOR_HEATER,
        icon="mdi:heat-wave",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.COMPRESSOR_HEATING,
    ),
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.DEFROST_VALVE,
        icon_by_state={True: "mdi:valve-open", False: "mdi:valve-closed"},
        device_class=BinarySensorDeviceClass.OPENING,
        visibility=LV.DEFROST_VALVE,
    ),
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.ADDITIONAL_HEAT_GENERATOR,
        icon="mdi:patio-heater",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.SECOND_HEAT_GENERATOR,
    ),
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.DISTURBANCE_OUTPUT,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.DEFROST_END_FLOW_OKAY,
        visibility=LV.DEFROST_END_FLOW_OKAY,
    ),
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.MOTOR_PROTECTION,
        visibility=LV.MOTOR_PROTECTION,
    ),
    # endregion Main heatpump
    # region Heating
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.CIRCULATION_PUMP_HEATING,
        device_key=DeviceKey.heating,
        icon="mdi:car-turbocharger",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.CIRCULATION_PUMP_HEATING,
    ),
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.ADDITIONAL_CIRCULATION_PUMP,
        device_key=DeviceKey.heating,
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.ADDITIONAL_CIRCULATION_PUMP,
    ),
    # endregion Heating
    # region Domestic water
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.DHW_RECIRCULATION_PUMP,
        device_key=DeviceKey.domestic_water,
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.DHW_RECIRCULATION_PUMP,
    ),
    # Special case: Same underlying sensor with different ha sensor!
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.DHW_CIRCULATION_PUMP,
        device_key=DeviceKey.domestic_water,
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.DHW_CIRCULATION_PUMP,
    ),
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.DHW_CIRCULATION_PUMP,
        device_key=DeviceKey.domestic_water,
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.DHW_CHARGING_PUMP,
    ),
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.SOLAR_PUMP,
        device_key=DeviceKey.domestic_water,
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.SOLAR,
    ),
    # endregion Domestic water
    # region Cooling
    LuxtronikBinarySensorEntityDescription(
        luxtronik_key=LC.APPROVAL_COOLING,
        device_key=DeviceKey.cooling,
        icon="mdi:lock",
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    # endregion Cooling
]

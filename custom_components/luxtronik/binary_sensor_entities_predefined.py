"""Luxtronik binary sensors definitions."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from .const import DeviceKey, LuxCalculation as LC, LuxVisibility as LV, SensorKey
from .model import LuxtronikBinarySensorEntityDescription

BINARY_SENSORS: list[LuxtronikBinarySensorEntityDescription] = [
    # region Main heatpump
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.EVU_UNLOCKED,
        luxtronik_key=LC.C0031_EVU_UNLOCKED,
        icon="mdi:lock",
        device_class=BinarySensorDeviceClass.LOCK,
        visibility=LV.V0121_EVU_LOCKED,
    ),
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.COMPRESSOR,
        luxtronik_key=LC.C0044_COMPRESSOR,
        icon="mdi:arrow-collapse-all",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.COMPRESSOR2,
        luxtronik_key=LC.C0045_COMPRESSOR2,
        icon="mdi:arrow-collapse-all",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.PUMP_FLOW,
        luxtronik_key=LC.C0043_PUMP_FLOW,
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.COMPRESSOR_HEATER,
        luxtronik_key=LC.C0182_COMPRESSOR_HEATER,
        icon="mdi:heat-wave",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.V0290_COMPRESSOR_HEATING,
    ),
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.DEFROST_VALVE,
        luxtronik_key=LC.C0037_DEFROST_VALVE,
        icon_by_state={True: "mdi:valve-open", False: "mdi:valve-closed"},
        device_class=BinarySensorDeviceClass.OPENING,
        visibility=LV.V0049_DEFROST_VALVE,
    ),
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.ADDITIONAL_HEAT_GENERATOR,
        luxtronik_key=LC.C0048_ADDITIONAL_HEAT_GENERATOR,
        icon="mdi:patio-heater",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.V0061_SECOND_HEAT_GENERATOR,
    ),
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.DISTURBANCE_OUTPUT,
        luxtronik_key=LC.C0049_DISTURBANCE_OUTPUT,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.DEFROST_END_FLOW_OKAY,
        luxtronik_key=LC.C0029_DEFROST_END_FLOW_OKAY,
        visibility=LV.V0041_DEFROST_END_FLOW_OKAY,
    ),
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.MOTOR_PROTECTION,
        luxtronik_key=LC.C0034_MOTOR_PROTECTION,
        visibility=LV.V0045_MOTOR_PROTECTION,
    ),
    # endregion Main heatpump
    # region Heating
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.CIRCULATION_PUMP_HEATING,
        luxtronik_key=LC.C0039_CIRCULATION_PUMP_HEATING,
        device_key=DeviceKey.heating,
        icon="mdi:car-turbocharger",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.V0052_CIRCULATION_PUMP_HEATING,
    ),
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.ADDITIONAL_CIRCULATION_PUMP,
        luxtronik_key=LC.C0047_ADDITIONAL_CIRCULATION_PUMP,
        device_key=DeviceKey.heating,
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.V0060_ADDITIONAL_CIRCULATION_PUMP,
    ),
    # endregion Heating
    # region Domestic water
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.DHW_RECIRCULATION_PUMP,
        luxtronik_key=LC.C0038_DHW_RECIRCULATION_PUMP,
        device_key=DeviceKey.domestic_water,
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.V0050_DHW_RECIRCULATION_PUMP,
    ),
    # Special case: Same underlying sensor with different ha sensor!
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.DHW_CIRCULATION_PUMP,
        luxtronik_key=LC.C0046_DHW_CIRCULATION_PUMP,
        device_key=DeviceKey.domestic_water,
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.V0059_DHW_CIRCULATION_PUMP,
    ),
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.DHW_CHARGING_PUMP,
        luxtronik_key=LC.C0046_DHW_CIRCULATION_PUMP,
        device_key=DeviceKey.domestic_water,
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.V0059A_DHW_CHARGING_PUMP,
    ),
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.SOLAR_PUMP,
        luxtronik_key=LC.C0052_SOLAR_PUMP,
        device_key=DeviceKey.domestic_water,
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        visibility=LV.V0250_SOLAR,
    ),
    # endregion Domestic water
    # region Cooling
    LuxtronikBinarySensorEntityDescription(
        key=SensorKey.APPROVAL_COOLING,
        luxtronik_key=LC.C0146_APPROVAL_COOLING,
        device_key=DeviceKey.cooling,
        icon="mdi:lock",
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    # endregion Cooling
]

"""Luxtronik sensors definitions."""

# region Imports
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)

from .const import (
    SECOND_TO_HOUR_FACTOR,
    DeviceKey,
    LuxCalculation as LC,
    LuxOperationMode,
    LuxParameter as LP,
    LuxSmartGridStatus,
    LuxStatus1Option,
    LuxStatus3Option,
    LuxSwitchoffReason,
    LuxVisibility as LV,
    SensorAttrFormat,
    SensorAttrKey as SA,
    SensorKey,
    UnitOfVolumeFlowRateExt,
)
from .model import (
    LuxtronikCopSensorDescription as cop_descr,
    LuxtronikEntityAttributeDescription as attr,
    LuxtronikIndexSensorDescription as descr_index,
    LuxtronikSensorDescription as descr,
    LuxtronikSumSensorDescription as sum_descr,
)

# endregion Imports

# What one count of the auxiliary heater's heat counters (parameters 1059 and
# 1140) is worth, per controller generation, on top of the /10 the Energy
# datatype they are registered with in lux_overrides already applies.
#
# Series 3 - 0.1 kWh per count, so nothing further. Measured, not read off a
#   unit note: energy divided by the aux heater's run time must equal the
#   rated element power in parameter 1025, which it does on five units
#   (MSW4-16, MSW2-6S, MSW2-9S, LW SEC 2; V3.79 through V3.92.3) at this
#   scale and puts them all at an impossible 0.89 kW element without it.
#   #490 applied the further /10 to everyone on one unverified display
#   comparison; #625 measured it away again.
# Series 2 - 0.01 kWh per count. An LD9 on V2.88.3 read 147140 counts against
#   1471.4 kWh on the controller's own web page, and the one earlier report
#   needing /100 also ran V2.88.3 (#752). Every unit behind the series-3
#   figure above is a series 3, so that sample could not have shown this.
#   It also puts 1059 back in line with the rest of its register family:
#   parameters 852/854/878/879, the other ID_Waermemenge_* counters, are
#   0.01 kWh on both generations (checked against calculations 151/152, which
#   are 0.1 kWh, on 21 diagnostics dumps). Series 3 is where 1059 leaves it.
# Series 1 - assumed to match series 2, never measured: there is no V1.x
#   diagnostics dump in the corpus at all. A controller line that used 0.01 kWh
#   on series 1, kept it on series 2 and changed to 0.1 on series 3 is a
#   plausible history; one that used 0.1, switched to 0.01, then switched back
#   is not. It also keeps series 1 inside the ID_Waermemenge_* family above.
#   Still an assumption, and the one to revisit first - tracked in #752.
#
# Listed exhaustively rather than as a single series-2 exception so that every
# generation states its scale where it can be checked. A generation missing
# from the mapping falls back to the description's own `factor`.
AUX_HEATER_ENERGY_FACTOR_BY_SERIES: dict[int, float] = {1: 0.1, 2: 0.1, 3: 1}

SENSORS_STATUS: list[descr] = [
    descr(
        key=SensorKey.STATUS,
        luxtronik_key=LC.C0080_STATUS,
        device_class=SensorDeviceClass.ENUM,
        extra_attributes=(
            attr(SA.EVU_FIRST_START_TIME, LC.UNSET, None, True),
            attr(SA.EVU_FIRST_END_TIME, LC.UNSET, None, True),
            attr(SA.EVU_SECOND_START_TIME, LC.UNSET, None, True),
            attr(SA.EVU_SECOND_END_TIME, LC.UNSET, None, True),
            attr(SA.EVU_DAYS, LC.UNSET, None, True),
        ),
        options=[e.value for e in LuxOperationMode],
    ),
    descr(
        key=SensorKey.SMART_GRID_STATUS,
        luxtronik_key=LC.UNSET,  # Calculated from EVU and EVU2 inputs
        device_class=SensorDeviceClass.ENUM,
        options=[e.value for e in LuxSmartGridStatus],
    ),
]

SENSORS_INDEX: list[descr_index] = [
    descr_index(
        key=SensorKey.SWITCHOFF_REASON,
        luxtronik_key=LP.P0716_0720_SWITCHOFF_REASON,
        luxtronik_key_timestamp=LP.P0721_0725_SWITCHOFF_TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[e.value for e in LuxSwitchoffReason],  # pyright: ignore[reportArgumentType]  # int values; converting both options and native_value to str is out of scope
    ),
]

SENSORS: list[descr] = [
    # region Main heatpump
    descr(
        key=SensorKey.STATUS_TIME,
        luxtronik_key=LC.C0120_STATUS_TIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_registry_visible_default=False,
        native_precision=0,
        extra_attributes=(
            attr(SA.STATUS_TEXT, LC.C0120_STATUS_TIME, SensorAttrFormat.HOUR_MINUTE),
            attr(SA.TIMER_HEATPUMP_ON, LC.C0067_TIMER_HEATPUMP_ON),
            attr(SA.TIMER_ADD_HEAT_GENERATOR_ON, LC.C0068_TIMER_ADD_HEAT_GENERATOR_ON),
            attr(SA.TIMER_SEC_HEAT_GENERATOR_ON, LC.C0069_TIMER_SEC_HEAT_GENERATOR_ON),
            attr(SA.TIMER_NET_INPUT_DELAY, LC.C0070_TIMER_NET_INPUT_DELAY),
            attr(SA.TIMER_SCB_OFF, LC.C0071_TIMER_SCB_OFF),
            attr(SA.TIMER_SCB_ON, LC.C0072_TIMER_SCB_ON),
            attr(SA.TIMER_COMPRESSOR_OFF, LC.C0073_TIMER_COMPRESSOR_OFF),
            attr(SA.TIMER_HC_ADD, LC.C0074_TIMER_HC_ADD),
            attr(SA.TIMER_HC_LESS, LC.C0075_TIMER_HC_LESS),
            attr(SA.TIMER_TDI, LC.C0076_TIMER_TDI),
            attr(SA.TIMER_BLOCK_DHW, LC.C0077_TIMER_BLOCK_DHW),
            attr(SA.TIMER_DEFROST, LC.C0141_TIMER_DEFROST),
            attr(SA.TIMER_HOT_GAS, LC.C0158_TIMER_HOT_GAS),
        ),
    ),
    descr(
        key=SensorKey.STATUS_LINE_1,
        luxtronik_key=LC.C0117_STATUS_LINE_1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_visible_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=[e.value for e in LuxStatus1Option],
    ),
    descr(
        key=SensorKey.STATUS_LINE_2,
        luxtronik_key=LC.C0118_STATUS_LINE_2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_visible_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=["since", "in"],
    ),
    descr(
        key=SensorKey.STATUS_LINE_3,
        luxtronik_key=LC.C0119_STATUS_LINE_3,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_visible_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=[e.value for e in LuxStatus3Option],
    ),
    descr(
        key=SensorKey.HEAT_SOURCE_INPUT_TEMPERATURE,
        luxtronik_key=LC.C0204_HEAT_SOURCE_INPUT_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    descr(
        key=SensorKey.OUTDOOR_TEMPERATURE,
        luxtronik_key=LC.C0015_OUTDOOR_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    descr(
        key=SensorKey.OUTDOOR_TEMPERATURE_AVERAGE,
        luxtronik_key=LC.C0016_OUTDOOR_TEMPERATURE_AVERAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    descr(
        key=SensorKey.COMPRESSOR1_IMPULSES,
        luxtronik_key=LC.C0057_COMPRESSOR1_IMPULSES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="\u2211",
        entity_registry_enabled_default=False,
        visibility=LV.V0081_COMPRESSOR1_IMPULSES,
    ),
    descr(
        key=SensorKey.COMPRESSOR1_OPERATION_HOURS,
        luxtronik_key=LC.C0056_COMPRESSOR1_OPERATION_HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        visibility=LV.V0080_COMPRESSOR1_OPERATION_HOURS,
        factor=SECOND_TO_HOUR_FACTOR,
        native_precision=2,
    ),
    descr(
        key=SensorKey.COMPRESSOR2_IMPULSES,
        luxtronik_key=LC.C0059_COMPRESSOR2_IMPULSES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="\u2211",
        entity_registry_enabled_default=False,
        visibility=LV.V0084_COMPRESSOR2_IMPULSES,
    ),
    descr(
        key=SensorKey.COMPRESSOR2_OPERATION_HOURS,
        luxtronik_key=LC.C0058_COMPRESSOR2_OPERATION_HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        visibility=LV.V0083_COMPRESSOR2_OPERATION_HOURS,
        factor=SECOND_TO_HOUR_FACTOR,
        native_precision=2,
    ),
    descr(
        key=SensorKey.OPERATION_HOURS,
        luxtronik_key=LC.C0063_OPERATION_HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        factor=SECOND_TO_HOUR_FACTOR,
        native_precision=2,
    ),
    descr(
        key=SensorKey.HEAT_AMOUNT_COUNTER,
        luxtronik_key=LC.C0154_HEAT_AMOUNT_COUNTER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        native_precision=1,
    ),
    descr(
        key=SensorKey.HEAT_AMOUNT_FLOW_RATE,
        luxtronik_key=LC.C0155_HEAT_AMOUNT_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfVolumeFlowRateExt.LITER_PER_HOUR,
        native_precision=1,
    ),
    descr(
        key=SensorKey.HEAT_SOURCE_FLOW_RATE,
        luxtronik_key=LC.C0173_HEAT_SOURCE_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfVolumeFlowRateExt.LITER_PER_HOUR,
        native_precision=1,
    ),
    descr(
        key=SensorKey.HOT_GAS_TEMPERATURE,
        luxtronik_key=LC.C0014_HOT_GAS_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        visibility=LV.V0027_HOT_GAS_TEMPERATURE,
    ),
    descr(
        key=SensorKey.SUCTION_COMPRESSOR_TEMPERATURE,
        luxtronik_key=LC.C0176_SUCTION_COMPRESSOR_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        visibility=LV.V0289_SUCTION_COMPRESSOR_TEMPERATURE,
    ),
    descr(
        key=SensorKey.SUCTION_EVAPORATOR_TEMPERATURE,
        luxtronik_key=LC.C0175_SUCTION_EVAPORATOR_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        visibility=LV.V0310_SUCTION_EVAPORATOR_TEMPERATURE,
    ),
    descr(
        key=SensorKey.COMPRESSOR_HEATING_TEMPERATURE,
        luxtronik_key=LC.C0177_COMPRESSOR_HEATING_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        visibility=LV.V0290_COMPRESSOR_HEATING,
    ),
    descr(
        key=SensorKey.OVERHEATING_TEMPERATURE,
        luxtronik_key=LC.C0178_OVERHEATING_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        visibility=LV.V0291_OVERHEATING_TEMPERATURE,
    ),
    descr(
        key=SensorKey.OVERHEATING_TARGET_TEMPERATURE,
        luxtronik_key=LC.C0179_OVERHEATING_TARGET_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        visibility=LV.V0291_OVERHEATING_TEMPERATURE,
    ),
    descr(
        key=SensorKey.HIGH_PRESSURE,
        luxtronik_key=LC.C0180_HIGH_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        visibility=LV.V0292_LIN_PRESSURE,
    ),
    descr(
        key=SensorKey.LOW_PRESSURE,
        luxtronik_key=LC.C0181_LOW_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        visibility=LV.V0292_LIN_PRESSURE,
    ),
    descr(
        key=SensorKey.ADDITIONAL_HEAT_GENERATOR_OPERATION_HOURS,
        luxtronik_key=LC.C0060_ADDITIONAL_HEAT_GENERATOR_OPERATION_HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        visibility=LV.V0086_ADDITIONAL_HEAT_GENERATOR_OPERATION_HOURS,
        factor=SECOND_TO_HOUR_FACTOR,
        native_precision=2,
    ),
    descr(
        key=SensorKey.ADDITIONAL_HEAT_GENERATOR2_OPERATION_HOURS,
        luxtronik_key=LC.C0061_ADDITIONAL_HEAT_GENERATOR2_OPERATION_HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        visibility=LV.V0087_ADDITIONAL_HEAT_GENERATOR2_OPERATION_HOURS,
        factor=SECOND_TO_HOUR_FACTOR,
        native_precision=2,
    ),
    descr(
        key=SensorKey.ADDITIONAL_HEAT_GENERATOR_ENERGY_P1059,
        luxtronik_key=LP.P1059_ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_active_formula="!= 0.0",
        visibility=LV.V0324_ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER,
        # Register unit differs by controller generation - see
        # AUX_HEATER_ENERGY_FACTOR_BY_SERIES for the measurements behind each.
        factor_by_firmware_series=AUX_HEATER_ENERGY_FACTOR_BY_SERIES,
        native_precision=1,
    ),
    descr(
        key=SensorKey.ADDITIONAL_HEAT_GENERATOR_ENERGY_P1140,
        luxtronik_key=LP.P1140_SECOND_HEAT_GENERATOR_AMOUNT_COUNTER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_active_formula="!= 0.0",
        # Shares 1059's scale, by analogy rather than by measurement: it is
        # the same physical element on the same controller, and no series-2
        # unit has been seen with 1140 counting yet. Giving it its own scale
        # would make a unit's total jump at the handover between the two.
        factor_by_firmware_series=AUX_HEATER_ENERGY_FACTOR_BY_SERIES,
        native_precision=1,
        # Despite the name this is not the second heat generator (ZWE2) - it
        # counts the same element as 1059, which stops advancing once this
        # one starts. Neither raw register is the figure a user wants, so
        # both defer to the total below rather than being enabled by
        # default. The key itself must not change: unique_id derives from it,
        # and renaming would orphan existing history. #733
        entity_registry_enabled_default=False,
    ),
    # The analog outputs are per mille of a 10 V full scale, so the library's
    # Voltage datatype (raw / 10) lands on 0-100 and `factor` supplies the
    # remaining tenth: raw 1000 -> 100.0 -> 10.0 V. Removing the factor (as
    # 2026.08.11 briefly did) reports an impossible 100 V; across 45
    # diagnostics dumps AnalogOut1-4 never exceed 100.0 and pile up on
    # 0.0 / 50.0 / 100.0. The analog *inputs* differ - AnalogIn3 reads 3.3 for
    # 3.3 V - which is what made this look like a scaling bug from either
    # side (#729).
    #
    # 0/50/100 is equally round read as percent, so the dumps cannot tell
    # volts from percent here; volts is kept because the controller
    # configures and displays these outputs as a 0-10 V signal. The
    # ventilation fan outputs below share the encoding but not that
    # reasoning, and are percent.
    descr(
        key=SensorKey.ANALOG_OUT1,
        luxtronik_key=LC.C0156_ANALOG_OUT1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        visibility=LV.V0248_ANALOG_OUT1,
        entity_registry_enabled_default=False,
        factor=0.1,
    ),
    descr(
        key=SensorKey.ANALOG_OUT2,
        luxtronik_key=LC.C0157_ANALOG_OUT2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        visibility=LV.V0249_ANALOG_OUT2,
        entity_registry_enabled_default=False,
        factor=0.1,
    ),
    descr(
        key=SensorKey.VENTILATION_SUPPLY_AIR_TEMPERATURE,
        device_key=DeviceKey.ventilation,
        luxtronik_key=LC.C0159_VENTILATION_SUPPLY_AIR_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    descr(
        key=SensorKey.VENTILATION_EXHAUST_AIR_TEMPERATURE,
        device_key=DeviceKey.ventilation,
        luxtronik_key=LC.C0160_VENTILATION_EXHAUST_AIR_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    # VZU/VAB are analog fan outputs, so they carry the modulation level a
    # binary sensor would discard. Same per-mille encoding as the analog
    # outputs above, but reported as percent rather than volts, and without
    # the factor: the value handed out is the undivided register, and #729's
    # controller displays 3.25 V for the 32.5 this integration shows. Labelled
    # V that would read as 32.5 volts - ten times the real output - while as
    # percent it is right, since the same point is 32.5 % of the 10 V scale.
    # Confirmed against that controller's web UI at three operating points
    # (32.5 / 50.0 / 62.5), each matching a configured stage below divided by
    # the unit size. Percent also keeps the number free of an assumed full
    # scale, which volts would not.
    descr(
        key=SensorKey.VENTILATION_SUPPLY_FAN,
        device_key=DeviceKey.ventilation,
        luxtronik_key=LC.C0164_VENTILATION_SUPPLY_FAN,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    descr(
        key=SensorKey.VENTILATION_EXHAUST_FAN,
        device_key=DeviceKey.ventilation,
        luxtronik_key=LC.C0165_VENTILATION_EXHAUST_FAN,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    # The four configured ventilation stages (DIN 1946-6: humidity
    # protection, reduced, nominal, intensive). The register is the airflow
    # in m3/h with no conversion - both the pinned library and upstream's
    # rewrite type these as Unknown/UINT32, so the raw value is what arrives.
    # #729's LWC407, configured for a 400 m3/h unit, reported 130 / 200 / 250
    # against fan outputs of 32.5 % / 50.0 % / 62.5 % at the same moments:
    # three operating points where stage / unit size lands exactly on the fan
    # output, which per mille of the fan setpoint would not do. Intensive was
    # never observed - that stage is not reachable through the mode parameter
    # on that controller - so it rides on the other three.
    #
    # Still read-only. That is one system, and a `number` entity would have to
    # commit to the scale before writing real airflow into someone's house;
    # a wrong unit on a sensor is a label, a wrong unit on a write is not.
    #
    # Gated on the ventilation device rather than the ID_Visi_Einst_Luf_*
    # flags: those are the same flag family that reads 0 on a working module,
    # which is why has_ventilation ignores them (see coordinator).
    descr(
        key=SensorKey.VENTILATION_STAGE_HUMIDITY_PROTECTION,
        device_key=DeviceKey.ventilation,
        luxtronik_key=LP.P0960_VENTILATION_STAGE_HUMIDITY_PROTECTION,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    ),
    descr(
        key=SensorKey.VENTILATION_STAGE_REDUCED,
        device_key=DeviceKey.ventilation,
        luxtronik_key=LP.P0961_VENTILATION_STAGE_REDUCED,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    ),
    descr(
        key=SensorKey.VENTILATION_STAGE_NOMINAL,
        device_key=DeviceKey.ventilation,
        luxtronik_key=LP.P0962_VENTILATION_STAGE_NOMINAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    ),
    descr(
        key=SensorKey.VENTILATION_STAGE_INTENSIVE,
        device_key=DeviceKey.ventilation,
        luxtronik_key=LP.P0963_VENTILATION_STAGE_INTENSIVE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    ),
    descr(
        key=SensorKey.CURRENT_HEAT_OUTPUT,
        luxtronik_key=LC.C0257_CURRENT_HEAT_OUTPUT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_registry_enabled_default=False,
        native_precision=0,
    ),
    descr(
        key=SensorKey.PUMP_FREQUENCY,
        luxtronik_key=LC.C0231_PUMP_FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        entity_registry_enabled_default=False,
    ),
    descr(
        key=SensorKey.PUMP_FLOW_DELTA_TARGET,
        luxtronik_key=LC.C0239_PUMP_FLOW_DELTA_TARGET,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        factor=0.1,
        entity_registry_enabled_default=False,
    ),
    descr(
        key=SensorKey.PUMP_FLOW_DELTA,
        luxtronik_key=LC.C0240_PUMP_FLOW_DELTA,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        factor=0.1,
        entity_registry_enabled_default=False,
    ),
    descr(
        key=SensorKey.CIRCULATION_PUMP_DELTA_TARGET,
        luxtronik_key=LC.C0242_CIRCULATION_PUMP_DELTA_TARGET,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        factor=0.1,
        entity_registry_enabled_default=False,
    ),
    descr(
        key=SensorKey.CIRCULATION_PUMP_DELTA,
        luxtronik_key=LC.C0243_CIRCULATION_PUMP_DELTA,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        factor=0.1,
        entity_registry_enabled_default=False,
    ),
    descr(
        key=SensorKey.HEAT_SOURCE_OUTPUT_TEMPERATURE,
        luxtronik_key=LC.C0024_HEAT_SOURCE_OUTPUT_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
        entity_active_formula="!= -50.0",
        visibility=LV.V0291_OVERHEATING_TEMPERATURE,
    ),
    descr(
        key=SensorKey.ERROR_REASON,
        luxtronik_key=LC.C0100_ERROR_REASON,
        extra_attributes=(
            attr(SA.TIMESTAMP, LC.C0095_ERROR_TIME),
            attr(SA.CODE, LC.C0100_ERROR_REASON),
            attr(SA.CAUSE, LC.C0100_ERROR_REASON),
            attr(SA.REMEDY, LC.C0100_ERROR_REASON),
        ),
    ),
    descr(
        key=SensorKey.CURRENT_POWER_CONSUMPTION,
        luxtronik_key=LC.C0268_CURRENT_POWER_CONSUMPTION,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_registry_enabled_default=False,
        native_precision=0,
    ),
    # endregion Main heatpump
    # region Heating
    descr(
        key=SensorKey.FLOW_IN_TEMPERATURE,
        luxtronik_key=LC.C0010_FLOW_IN_TEMPERATURE,
        device_key=DeviceKey.heating,
        entity_category=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        extra_attributes=(
            attr(
                SA.MAX_ALLOWED,
                LP.P0149_FLOW_IN_TEMPERATURE_MAX_ALLOWED,
                SensorAttrFormat.CELSIUS_TENTH,
            ),
        ),
    ),
    descr(
        key=SensorKey.FLOW_IN_CIRCUIT1_TEMPERATURE,
        luxtronik_key=LC.C0018_FLOW_IN_CIRCUIT1_TEMPERATURE,
        device_key=DeviceKey.heating,
        entity_category=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    descr(
        key=SensorKey.FLOW_IN_CIRCUIT2_TEMPERATURE,
        luxtronik_key=LC.C0019_FLOW_IN_CIRCUIT2_TEMPERATURE,
        device_key=DeviceKey.heating,
        entity_category=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    descr(
        key=SensorKey.FLOW_IN_CIRCUIT3_TEMPERATURE,
        luxtronik_key=LC.C0020_FLOW_IN_CIRCUIT3_TEMPERATURE,
        device_key=DeviceKey.heating,
        entity_category=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    descr(
        key=SensorKey.FLOW_IN_CIRCUIT1_TARGET_TEMPERATURE,
        luxtronik_key=LC.C0021_FLOW_IN_CIRCUIT1_TARGET_TEMPERATURE,
        device_key=DeviceKey.heating,
        entity_category=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    descr(
        key=SensorKey.FLOW_IN_CIRCUIT2_TARGET_TEMPERATURE,
        luxtronik_key=LC.C0022_FLOW_IN_CIRCUIT2_TARGET_TEMPERATURE,
        device_key=DeviceKey.heating,
        entity_category=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    descr(
        key=SensorKey.FLOW_IN_CIRCUIT3_TARGET_TEMPERATURE,
        luxtronik_key=LC.C0023_FLOW_IN_CIRCUIT3_TARGET_TEMPERATURE,
        device_key=DeviceKey.heating,
        entity_category=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    descr(
        key=SensorKey.FLOW_OUT_TEMPERATURE,
        luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
        device_key=DeviceKey.heating,
        entity_category=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    descr(
        key=SensorKey.FLOW_OUT_TEMPERATURE_TARGET,
        luxtronik_key=LC.C0012_FLOW_OUT_TEMPERATURE_TARGET,
        device_key=DeviceKey.heating,
        entity_category=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        extra_attributes=(
            attr(
                SA.SWITCH_GAP,
                LC.C0011_FLOW_OUT_TEMPERATURE,
                SensorAttrFormat.SWITCH_GAP,
            ),
        ),
    ),
    descr(
        key=SensorKey.OPERATION_HOURS_HEATING,
        luxtronik_key=LC.C0064_OPERATION_HOURS_HEATING,
        device_key=DeviceKey.heating,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        factor=SECOND_TO_HOUR_FACTOR,
        native_precision=2,
    ),
    descr(
        key=SensorKey.HEAT_AMOUNT_HEATING,
        luxtronik_key=LC.C0151_HEAT_AMOUNT_HEATING,
        device_key=DeviceKey.heating,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        native_precision=1,
    ),
    descr(
        key=SensorKey.HEAT_ENERGY_INPUT,
        luxtronik_key=LP.P1136_HEAT_ENERGY_INPUT,
        device_key=DeviceKey.heating,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        native_precision=2,
        # 0.01 kWh raw unit, applied by the Energy2 datatype this parameter is
        # registered with in lux_overrides - hence no factor. Scale measured
        # against the heat-quantity calculations in #734.
    ),
    descr(
        key=SensorKey.FLOW_OUT_TEMPERATURE_EXTERNAL,
        luxtronik_key=LC.C0013_FLOW_OUT_TEMPERATURE_EXTERNAL,
        device_key=DeviceKey.heating,
        entity_category=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        visibility=LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL,
    ),
    descr(
        key=SensorKey.ROOM_THERMOSTAT_TEMPERATURE,
        luxtronik_key=LC.C0227_ROOM_THERMOSTAT_TEMPERATURE,
        device_key=DeviceKey.heating,
        entity_category=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        visibility=LV.V0122_ROOM_THERMOSTAT,
    ),
    descr(
        key=SensorKey.ROOM_THERMOSTAT_TEMPERATURE_TARGET,
        luxtronik_key=LC.C0228_ROOM_THERMOSTAT_TEMPERATURE_TARGET,
        device_key=DeviceKey.heating,
        entity_category=None,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        visibility=LV.V0122_ROOM_THERMOSTAT,
    ),
    # endregion Heating
    # region Domestic water
    descr(
        key=SensorKey.DHW_TEMPERATURE,
        luxtronik_key=LC.C0017_DHW_TEMPERATURE,
        device_key=DeviceKey.domestic_water,
        entity_category=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    descr(
        key=SensorKey.DHW_OPERATION_HOURS,
        luxtronik_key=LC.C0065_OPERATION_HOURS_DHW,
        device_key=DeviceKey.domestic_water,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        factor=SECOND_TO_HOUR_FACTOR,
        native_precision=2,
    ),
    descr(
        key=SensorKey.DHW_HEAT_AMOUNT,
        luxtronik_key=LC.C0152_DHW_HEAT_AMOUNT,
        device_key=DeviceKey.domestic_water,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        native_precision=1,
    ),
    descr(
        key=SensorKey.DHW_ENERGY_INPUT,
        luxtronik_key=LP.P1137_DHW_ENERGY_INPUT,
        device_key=DeviceKey.domestic_water,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        native_precision=2,
        # 0.01 kWh raw unit, applied by the Energy2 datatype (see 1136 above).
    ),
    descr(
        key=SensorKey.SOLAR_COLLECTOR_TEMPERATURE,
        luxtronik_key=LC.C0026_SOLAR_COLLECTOR_TEMPERATURE,
        device_key=DeviceKey.domestic_water,
        entity_category=None,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        visibility=LV.V0038_SOLAR_COLLECTOR,
    ),
    descr(
        key=SensorKey.SOLAR_BUFFER_TEMPERATURE,
        luxtronik_key=LC.C0027_SOLAR_BUFFER_TEMPERATURE,
        device_key=DeviceKey.domestic_water,
        entity_category=None,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        visibility=LV.V0039_SOLAR_BUFFER,
    ),
    descr(
        key=SensorKey.OPERATION_HOURS_SOLAR,
        luxtronik_key=LP.P0882_SOLAR_OPERATION_HOURS,
        device_key=DeviceKey.domestic_water,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        factor=SECOND_TO_HOUR_FACTOR,
        native_precision=2,
        visibility=LV.V0038_SOLAR_COLLECTOR,
    ),
    # endregion Domestic water
    # region Cooling
    descr(
        key=SensorKey.OPERATION_HOURS_COOLING,
        luxtronik_key=LC.C0066_OPERATION_HOURS_COOLING,
        device_key=DeviceKey.cooling,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        factor=SECOND_TO_HOUR_FACTOR,
        native_precision=2,
    ),
    descr(
        key=SensorKey.COOLING_ENERGY_INPUT,
        luxtronik_key=LP.P1139_COOLING_ENERGY_INPUT,
        device_key=DeviceKey.cooling,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        native_precision=2,
        # 0.01 kWh raw unit, applied by the Energy2 datatype (see 1136 above).
        # This one reads 0.0 on every unit examined in #734, so its scale
        # follows its two siblings by analogy and is not itself measured.
    ),
    # endregion Cooling
]

# region COP (instantaneous, no external meter)
SENSORS_COP: list[cop_descr] = [
    cop_descr(
        key=SensorKey.COP_HEATING,
        device_key=DeviceKey.heating,
        state_class=SensorStateClass.MEASUREMENT,
        numerator_key=LC.C0257_CURRENT_HEAT_OUTPUT,
        denominator_key=LC.C0268_CURRENT_POWER_CONSUMPTION,
        required_status=LuxOperationMode.heating,
        icon="mdi:speedometer",
    ),
    cop_descr(
        key=SensorKey.COP_DHW,
        device_key=DeviceKey.domestic_water,
        state_class=SensorStateClass.MEASUREMENT,
        numerator_key=LC.C0257_CURRENT_HEAT_OUTPUT,
        denominator_key=LC.C0268_CURRENT_POWER_CONSUMPTION,
        required_status=LuxOperationMode.domestic_water,
        icon="mdi:speedometer",
    ),
]
# endregion COP

# region Totals
SENSORS_SUM: list[sum_descr] = [
    sum_descr(
        key=SensorKey.ADDITIONAL_HEAT_GENERATOR_ENERGY,
        summand_keys=(
            LP.P1059_ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER,
            LP.P1140_SECOND_HEAT_GENERATOR_AMOUNT_COUNTER,
        ),
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        # Deliberately not EntityCategory.DIAGNOSTIC: diagnostic entities
        # cannot be selected in the energy dashboard, which is the main thing
        # a lifetime kWh counter is for.
        #
        # Both summands share one scale, so the same mapping covers the total.
        factor_by_firmware_series=AUX_HEATER_ENERGY_FACTOR_BY_SERIES,
        native_precision=1,
    ),
]
# endregion Totals

"""Constants for the Luxtronik heatpump integration."""
# region Imports
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum, IntEnum, IntFlag, StrEnum
from itertools import chain
import logging
from typing import Final

import voluptuous as vol
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass

import homeassistant.helpers.config_validation as cv
from homeassistant.const import Platform, UnitOfElectricPotential, UnitOfEnergy, UnitOfFrequency, UnitOfPower, UnitOfPressure, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.typing import StateType

# endregion Imports

# region Constants Main
DOMAIN: Final = "luxtronik"
NICKNAME_PREFIX: Final = "Home Assistant"

LOGGER: Final[logging.Logger] = logging.getLogger(__package__)
PLATFORMS: list[str] = [
    Platform.WATER_HEATER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.UPDATE,
]
UPDATE_INTERVAL_FAST: Final = timedelta(seconds=10)
UPDATE_INTERVAL_NORMAL: Final = timedelta(minutes=1)
UPDATE_INTERVAL_SLOW: Final = timedelta(minutes=3)
UPDATE_INTERVAL_VERY_SLOW: Final = timedelta(minutes=5)


SECOUND_TO_HOUR_FACTOR: Final = 0.000277777777778
# endregion Constants Main

# region Conf
CONF_COORDINATOR: Final = "coordinator"

CONF_PARAMETERS: Final = "parameters"
CONF_CALCULATIONS: Final = "calculations"
CONF_VISIBILITIES: Final = "visibilities"

CONF_HA_SENSOR_PREFIX: Final = "ha_sensor_prefix"
CONF_HA_SENSOR_INDOOR_TEMPERATURE: Final = "ha_sensor_indoor_temperature"

CONF_LOCK_TIMEOUT: Final = "lock_timeout"
CONF_SAFE: Final = "safe"
CONF_MAX_DATA_LENGTH: Final = "max_data_length"

DEFAULT_HOST: Final = "wp-novelan"
DEFAULT_PORT: Final = 8889
DEFAULT_TIMEOUT: Final = 60.0
DEFAULT_MAX_DATA_LENGTH: Final = 10000


SERVICE_WRITE: Final = "write"
ATTR_PARAMETER: Final = "parameter"
ATTR_VALUE: Final = "value"

SERVICE_WRITE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PARAMETER): cv.string,
        vol.Required(ATTR_VALUE): vol.Any(cv.Number, cv.string),
    }
)
# endregion Conf

# region Lux Definitions


class UnitOfVolumeFlowRateExt(StrEnum):
    """Volume flow rate units."""

    LITER_PER_HOUR = "l/h"


class DeviceKey(StrEnum):
    """Device keys."""

    heatpump: Final = "heatpump"
    heating: Final = "heating"
    domestic_water: Final = "domestic_water"
    cooling: Final = "cooling"


class FirmwareVersionMinor(Enum):
    """Firmware minor versions."""

    minor_88: Final = 88


LUXTRONIK_HA_SIGNAL_UPDATE_ENTITY = "luxtronik_entry_update"

MIN_TIME_BETWEEN_UPDATES: Final = timedelta(seconds=10)
MIN_TIME_BETWEEN_UPDATES_DOWNLOAD_PORTAL: Final = timedelta(hours=1)
DOWNLOAD_PORTAL_URL: Final = (
    "https://www.heatpump24.com/software/fetchSoftware.php?softwareID="
)
FIRMWARE_UPDATE_MANUAL_EN = (
    "https://www.alpha-innotec.com/en/services/customer-support/software-center"
)
FIRMWARE_UPDATE_MANUAL_DE = (
    "https://www.alpha-innotec.com/de/services/kundendienst/software-center"
)
# endregion Constants Main

# region Conf
LANG_EN: Final = "en"
LANG_DE: Final = "de"


PRESET_SECOND_HEATSOURCE: Final = "second_heatsource"


class LuxOperationMode(Enum):
    """Lux Operation modes heating, hot water, ventilation etc."""

    heating: Final = 0
    domestic_water: Final = 1  # "hot water"
    swimming_pool_solar: Final = 2  # "swimming pool/solar"
    evu: Final = 3
    defrost: Final = 4
    no_request: Final = 5
    heating_external_source: Final = 6
    cooling: Final = 7

    defrost_air: Final = 99  # "Luftabtauen"


class LuxMode(IntEnum):
    """Luxmodes off etc."""

    automatic: Final = 0
    second_heatsource: Final = 1
    party: Final = 2
    holidays: Final = 3
    off: Final = 4


class LuxModeVentilation(IntEnum):
    """Luxmodes off etc."""

    automatic: Final = 0
    party: Final = 1
    moisture_protection: Final = 2
    off: Final = 3


class LuxStatus1Option(Enum):
    """LuxStatus1 option defrost etc."""

    heatpump_running: Final = 0
    heatpump_idle: Final = 1
    heatpump_coming: Final = 2
    heatpump_shutdown: Final = 101
    errorcode_slot_zero: Final = 3  # "errorcode slot 0"
    defrost: Final = 4
    witing_on_LIN_connection: Final = 5  # "witing on LIN connection"
    compressor_heating_up: Final = 6
    pump_forerun: Final = 7
    compressor_heater: Final = 102


class LuxStatus3Option(Enum):
    """LuxStatus3 option heating etc."""

    unknown: Final = 101
    none: Final = 102
    heating: Final = 0
    no_request: Final = 1
    grid_switch_on_delay: Final = 2
    cycle_lock: Final = 3
    lock_time: Final = 4
    domestic_water: Final = 5
    info_bake_out_program: Final = 6
    defrost: Final = 7
    pump_forerun: Final = 8
    thermal_desinfection: Final = 9
    cooling: Final = 10
    swimming_pool_solar: Final = 12  # "swimming pool/solar"
    heating_external_energy_source: Final = 13
    domestic_water_external_energy_source: Final = 14
    flow_monitoring: Final = 16  # if affected write: heatSourceDefrostLastTimeout - Umgebungs- und Wärmequellen-Temperaturen bei denen die Luftabtauung die maximale Dauer überschritten hat.
    second_heat_generator_1_active: Final = 17


class LuxMkTypes(Enum):
    """LuxMkTypes etc."""

    off: Final = 0
    discharge: Final = 1
    load: Final = 2
    cooling: Final = 3
    heating_cooling: Final = 4


class LuxRoomThermostatType(Enum):
    """LuxMkTypes etc."""

    none: Final = 0
    # TODO: Validate types:
    # RFV: Final = 1
    # RFV_K: Final = 2
    # RFV_DK: Final = 3
    # RBE: Final = 4
    # Smart: Final = 5


class LuxSwitchoffReason(Enum):
    """LuxSwitchoff reason etc."""

    undefined_0: Final = 0  # ???
    heatpump_error: Final = 1
    system_error: Final = 2
    evu_lock: Final = 3
    operation_mode_second_heat_generator: Final = 4
    air_defrost: Final = 5
    maximal_usage_temperature: Final = 6
    minimal_usage_temperature: Final = 7
    lower_usage_limit: Final = 8
    no_request: Final = 9
    undefined_10: Final = 10  # ???
    flow_rate: Final = 11  # Durchfluss
    undefined_12: Final = 12  # ???
    undefined_13: Final = 13  # ???
    undefined_14: Final = 14  # ???
    undefined_15: Final = 15  # ???
    undefined_16: Final = 16  # ???
    undefined_17: Final = 17  # ???
    undefined_18: Final = 18  # ???
    PV_max: Final = 19


LUX_STATE_ICON_MAP: Final[dict[StateType | date | datetime | Decimal, str]] = {
    LuxOperationMode.heating.value: "mdi:radiator",
    LuxOperationMode.domestic_water.value: "mdi:waves",
    LuxOperationMode.swimming_pool_solar.value: "mdi:pool",
    LuxOperationMode.evu.value: "mdi:power-plug-off",
    LuxOperationMode.defrost.value: "mdi:car-defrost-rear",
    LuxOperationMode.no_request.value: "mdi:hvac-off",  # "mdi:heat-pump-outline",  # "mdi:radiator-disabled",
    LuxOperationMode.heating_external_source.value: "mdi:patio-heater",
    LuxOperationMode.cooling.value: "mdi:air-conditioner",
    LuxOperationMode.defrost_air.value: "mdi:car-defrost-rear",
}

LUX_STATE_ICON_MAP_COOL: Final[dict[StateType | date | datetime | Decimal, str]] = {
    LuxOperationMode.swimming_pool_solar.value: "mdi:pool",
    LuxOperationMode.evu.value: "mdi:power-plug-off",
    LuxOperationMode.defrost.value: "mdi:car-defrost-rear",
    LuxOperationMode.no_request.value: "mdi:snowflake-off",
    LuxOperationMode.cooling.value: "mdi:air-conditioner",
    LuxOperationMode.defrost_air.value: "mdi:car-defrost-rear",
}

LUX_MODELS_ALPHA_INNOTEC = ["LWP", "LWV", "MSW", "SWC", "SWP"]
LUX_MODELS_NOVELAN = ["BW", "LA", "LD", "LI", "SI", "ZLW"]
LUX_MODELS_OTHER = ["CB", "CI", "CN", "CS"]
# endregion Lux Definitions

# region Mappings
HEATPUMP_CODE_TYPE_MAP: Final[dict[int, str]] = {
    0: "ERC",
    1: "SW1",
    2: "SW2",
    3: "WW1",
    4: "WW2",
    5: "L1I",
    6: "L2I",
    7: "L1A",
    8: "L2A",
    9: "KSW",
    10: "KLW",
    11: "SWC",
    12: "LWC",
    13: "L2G",
    14: "WZS",
    15: "L1I407",
    16: "L2I407",
    17: "L1A407",
    18: "L2A407",
    19: "L2G407",
    20: "LWC407",
    21: "L1AREV",
    22: "L2AREV",
    23: "WWC1",
    24: "WWC2",
    25: "L2G404",
    26: "WZW",
    27: "L1S",
    28: "L1H",
    29: "L2H",
    30: "WZWD",
    31: "ERC",
    40: "WWB_20",
    41: "LD5",
    42: "LD7",
    43: "SW 37_45",
    44: "SW 58_69",
    45: "SW 29_56",
    46: "LD5 (230V)",
    47: "LD7 (230 V)",
    48: "LD9",
    49: "LD5 REV",
    50: "LD7 REV",
    51: "LD5 REV 230V",
    52: "LD7 REV 230V",
    53: "LD9 REV 230V",
    54: "SW 291",
    55: "LW SEC",
    56: "HMD 2",
    57: "MSW 4",
    58: "MSW 6",
    59: "MSW 8",
    60: "MSW 10",
    61: "MSW 12",
    62: "MSW 14",
    63: "MSW 17",
    64: "MSW 19",
    65: "MSW 23",
    66: "MSW 26",
    67: "MSW 30",
    68: "MSW 4S",
    69: "MSW 6S",
    70: "MSW 8S",
    71: "MSW 10S",
    72: "MSW 13S",
    73: "MSW 16S",
    74: "MSW2-6S",
    75: "MSW4-16",
}
UNIT_STATE_CLASS_MAP: Final[dict[UnitOfTemperature|UnitOfPressure|UnitOfEnergy|UnitOfElectricPotential|UnitOfPower|UnitOfFrequency, SensorStateClass]] = {
    UnitOfTemperature.CELSIUS: SensorStateClass.MEASUREMENT,
    UnitOfElectricPotential.VOLT: SensorStateClass.MEASUREMENT,
    UnitOfPressure.BAR: SensorStateClass.MEASUREMENT,
    UnitOfEnergy.KILO_WATT_HOUR: SensorStateClass.TOTAL_INCREASING,
    UnitOfPower.WATT: SensorStateClass.MEASUREMENT,
    UnitOfFrequency.HERTZ: SensorStateClass.MEASUREMENT,
}
UNIT_DEVICE_CLASS_MAP: Final[dict[UnitOfTemperature|UnitOfTime|UnitOfElectricPotential|UnitOfPressure|UnitOfEnergy|UnitOfPower|UnitOfFrequency, SensorDeviceClass]] = {
    UnitOfTemperature.CELSIUS: SensorDeviceClass.TEMPERATURE,
    UnitOfTemperature.KELVIN: SensorDeviceClass.TEMPERATURE,
    UnitOfTime.MINUTES: SensorDeviceClass.DURATION,
    UnitOfElectricPotential.VOLT: SensorDeviceClass.VOLTAGE,
    UnitOfPressure.BAR: SensorDeviceClass.PRESSURE,
    UnitOfEnergy.KILO_WATT_HOUR: SensorDeviceClass.ENERGY,
    UnitOfPower.WATT: SensorDeviceClass.POWER,
    UnitOfFrequency.HERTZ: SensorDeviceClass.FREQUENCY,
}
UNIT_ICON_MAP: Final[dict[UnitOfTemperature|UnitOfEnergy, str]] = {
    UnitOfTemperature.CELSIUS: 'mdi:thermometer',
    UnitOfTemperature.KELVIN: 'mdi:thermometer',
    UnitOfEnergy.KILO_WATT_HOUR: 'mdi:lightning-bolt-circle',
}
UNIT_FACTOR_MAP: Final[dict[UnitOfTemperature|UnitOfTime|UnitOfElectricPotential|UnitOfEnergy, float]] = {
    UnitOfTemperature.CELSIUS: 0.1,
    UnitOfTemperature.KELVIN: 0.1,
    UnitOfTime.MINUTES: 1,
    UnitOfElectricPotential.VOLT: 0.01,
    UnitOfEnergy.KILO_WATT_HOUR: 0.1,
}
# endregion Mappings


# region Keys
# Write permissions
#
class Parameter_Static_SensorKey(IntEnum):
    SERIAL_NUMBER: Final = 874  # ID_WP_SerienNummer_DATUM
    SERIAL_NUMBER_MODEL: Final = 875  # ID_WP_SerienNummer_HEX
    MIXING_CIRCUIT1_TYPE: Final = 42  # ID_Einst_MK1Typ_akt
    MIXING_CIRCUIT2_TYPE: Final = 130  # ID_Einst_MK2Typ_akt
    MIXING_CIRCUIT3_TYPE: Final = 780  # ID_Einst_MK3Typ_akt

class Parameter_Calc_SensorKey(IntEnum):
    OPERATION_HOURS: Final = 668  # ID_Zaehler_BetrZeitWP                                       ": "16434619",
    OPERATION_HOURS_COMPRESSOR1: Final = 669  # ID_Zaehler_BetrZeitVD1                                      ": "16434619",
    OPERATION_HOURS_COMPRESSOR2: Final = 670  # ID_Zaehler_BetrZeitVD2                                      ": "0",
    OPERATION_HOURS_ADDITIONAL_HEAT_GENERATOR1: Final = 671  # ID_Zaehler_BetrZeitZWE1                                     ": "31051",
    OPERATION_HOURS_ADDITIONAL_HEAT_GENERATOR2: Final = 672  # ID_Zaehler_BetrZeitZWE2                                     ": "0",
    OPERATION_HOURS_ADDITIONAL_HEAT_GENERATOR3: Final = 673  # ID_Zaehler_BetrZeitZWE3                                     ": "0",
    IMPULSES_COMPRESSOR1: Final = 674  # ID_Zaehler_BetrZeitImpVD1                                   ": "12704",
    IMPULSES_COMPRESSOR2: Final = 675  # ID_Zaehler_BetrZeitImpVD2                                   ": "0",
    EZM_COMPRESSOR1: Final = 676  # ID_Zaehler_BetrZeitEZMVD1                                   ": "0",
    EZM_COMPRESSOR2: Final = 677  # ID_Zaehler_BetrZeitEZMVD2                                   ": "0",
    # P0716_0720_SWITCHOFF_REASON: Final = "parameters.ID_Switchoff_file_{ID}_0"  # e.g. ID_Switchoff_file_0_0 - ID_Switchoff_file_4_0
    SWITCHOFF_REASON: Final = 716  # ID_Switchoff_file_{ID}_0"  # e.g. ID_Switchoff_file_0_0 - ID_Switchoff_file_4_0
    SWITCHOFF_REASON_2: Final = 717
    SWITCHOFF_REASON_3: Final = 718
    SWITCHOFF_REASON_4: Final = 719
    SWITCHOFF_REASON_5: Final = 720
    # P0721_0725_SWITCHOFF_TIMESTAMP: Final = "parameters.ID_Switchoff_file_{ID}_1"  # e.g. ID_Switchoff_file_0_1 - ID_Switchoff_file_4_1
    SWITCHOFF_TIMESTAMP: Final = 721  # ID_Switchoff_file_{ID}_1  # e.g. ID_Switchoff_file_0_1 - ID_Switchoff_file_4_1
    SWITCHOFF_TIMESTAMP_2: Final = 722
    SWITCHOFF_TIMESTAMP_3: Final = 723
    SWITCHOFF_TIMESTAMP_4: Final = 724
    SWITCHOFF_TIMESTAMP_5: Final = 725
    OPERATION_HOURS_HEATING: Final = 728  # ID_Zaehler_BetrZeitHz                                       ": "14655095",
    OPERATION_HOURS_DHW: Final = 729  # ID_Zaehler_BetrZeitBW                                       ": "1779392",
    OPERATION_HOURS_COOLING: Final = 730  # ID_Zaehler_BetrZeitKue                                      ": "0",
    SU_FSTD_HEATING: Final = 731
    SU_FSTD_DHW: Final = 732
    SU_FSTD_SWIMMING_POOL: Final = 733
    SU_FSTD_MIXING_CIRCUIT1: Final = 734
    SU_FSTD_MIXING_CIRCUIT2: Final = 735
    IP_ADDRESS: Final = 750
    # Todo: Test reset --> can we write it?
    # "852  ID_Waermemenge_Seit                                         ": "2566896",
    # "853  ID_Waermemenge_WQ                                           ": "0",
    # "854  ID_Waermemenge_Hz                                           ": "3317260",
    # "855  ID_Waermemenge_WQ_ges                                       ": "0",
    #  "878  ID_Waermemenge_BW                                           ": "448200",
    #  "879  ID_Waermemenge_SW                                           ": "0",
    #  "880  ID_Waermemenge_Datum                                        ": "1483648906", <-- Unix timestamp!  5.1.2017
    SOLAR_OPERATION_HOURS: Final = 882  # ID_BSTD_Solar
    ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER: Final = 1059  # ID_Waermemenge_ZWE
    LAST_DEFROST_TIMESTAMP: Final = (
        1119  # Unknown_Parameter_1119  # 1685073431 -> 26.5.23 05:57
    )
    HEAT_ENERGY_INPUT: Final = 1136  # Unknown_Parameter_1136
    DHW_ENERGY_INPUT: Final = 1137  # Unknown_Parameter_1137
    # ? P1138_SWIMMING_POOL_ENERGY_INPUT: Final = "parameters.Unknown_Parameter_1138" -->
    # ? P1139_COOLING_ENERGY_INPUT: Final = "parameters.Unknown_Parameter_1139"
    # ? P1140_SECOND_HEAT_SOURCE_DHW_ENERGY_INPUT: Final = "parameters.Unknown_Parameter_1140"

class Parameter_Config_SensorKey(IntEnum):
    HEATING_CIRCUIT_CURVE1_TEMPERATURE: Final = 11  # ID_Einst_HzHwHKE_akt
    HEATING_CIRCUIT_CURVE2_TEMPERATURE: Final = 12  # ID_Einst_HzHKRANH_akt
    HEATING_CIRCUIT_CURVE_NIGHT_TEMPERATURE: Final = 13  # ID_Einst_HzHKRABS_akt
    # luxtronik*_heating_circuit2_curve*
    HEATING_CIRCUIT2_CURVE1_TEMPERATURE: Final = 14  # ID_Einst_HzMK1E_akt 260
    HEATING_CIRCUIT2_CURVE2_TEMPERATURE: Final = 15  # ID_Einst_HzMK1ANH_akt 290
    HEATING_CIRCUIT2_CURVE_NIGHT_TEMPERATURE: Final = 16  # ID_Einst_HzMK1ABS_akt 0
    HEATSOURCE_DEFROST_AIR_THRESHOLD_TEMPERATURE: Final = (
        44  # ID_Einst_TLAbt_akt" heatSourceDefrostAirThreshold  # "temp. air defrost"  7.0 C°
    )
    DHW_THERMAL_DESINFECTION_TARGET: Final = 47  # ID_Einst_LGST_akt
    PUMP_OPTIMIZATION: Final = 49  # ID_Einst_Popt_akt
    # P0033_ROOM_THERMOSTAT_TYPE: Final = "parameters.ID_Einst_RFVEinb_akt"  # != 0 --> Has_Room_Temp
    DHW_HYSTERESIS: Final = 74  # ID_Einst_BWS_Hyst_akt
    DHW_CHARGING_PUMP: Final = (
        85  # ID_Einst_BWZIP_akt  # has_domestic_water_circulation_pump int() != 1
    )
    #  "Return temperature limit" / "Rückl.-Begr." 50 35-70 C° step 1 -> Setting the maximum return setpoint temperatures in heating mode.
    HEATING_RETURN_TEMPERATURE_LIMIT: Final = 87  # ID_Einst_TRBegr_akt
    HEATING_HYSTERESIS: Final = 88  # ID_Einst_HRHyst_akt
    HEATING_MAX_FLOW_OUT_INCREASE_TEMPERATURE: Final = 89  # ID_Einst_TRErhmax_akt
    RELEASE_SECOND_HEAT_GENERATOR: Final = 90  # ID_Einst_ZWEFreig_akt
    HEATSOURCE_DEFROST_AIR_END_TEMPERATURE: Final = 98  # ID_Einst_TAbtEnd_akt heatSourceDefrostAirEnd
    COOLING_OUTDOOR_TEMP_THRESHOLD: Final = 110  # ID_Einst_KuehlFreig_akt
    HEATING_NIGHT_LOWERING_TO_TEMPERATURE: Final = 111  # ID_Einst_TAbsMin_akt thresholdTemperatureSetBack
    SOLAR_PUMP_ON_DIFFERENCE_TEMPERATURE: Final = 122  # ID_Einst_TDC_Ein_akt
    SOLAR_PUMP_OFF_DIFFERENCE_TEMPERATURE: Final = 123  # ID_Einst_TDC_Aus_akt
    SOLAR_PUMP_OFF_MAX_DIFFERENCE_TEMPERATURE_BOILER: Final = (
        124  # ID_Einst_TDC_Max_akt
    )
    COOLING_TARGET_TEMPERATURE_MK1: Final = 132  # ID_Sollwert_KuCft1_akt
    COOLING_TARGET_TEMPERATURE_MK2: Final = 133  # ID_Sollwert_KuCft2_akt
    FLOW_IN_TEMPERATURE_MAX_ALLOWED: Final = 149  # ID_Einst_TVLmax_akt
    HEATING_CIRCULATION_PUMP_DEAERATE: Final = 678  # ID_Einst_Entl_Typ_0 <- Name correct?
    DHW_CIRCULATION_PUMP_DEAERATE: Final = 684  # ID_Einst_Entl_Typ_6 hotWaterCircPumpDeaerate
    HEATING_THRESHOLD: Final = 699  # ID_Einst_Heizgrenze
    HEATING_THRESHOLD_TEMPERATURE: Final = 700  # ID_Einst_Heizgrenze_Temp thresholdHeatingLimit
    # luxtronik*_heating_circuit3_curve*
    HEATING_CIRCUIT3_CURVE1_TEMPERATURE: Final = 774  # ID_Einst_HzMK3E_akt  # 270
    HEATING_CIRCUIT3_CURVE2_TEMPERATURE: Final = 775  # ID_Einst_HzMK3ANH_akt  # 290
    HEATING_CIRCUIT3_CURVE_NIGHT_TEMPERATURE: Final = 776  # ID_Einst_HzMK3ABS_akt  # 0
    COOLING_START_DELAY_HOURS: Final = 850  # ID_Einst_Kuhl_Zeit_Ein_akt
    COOLING_STOP_DELAY_HOURS: Final = 851  # ID_Einst_Kuhl_Zeit_Aus_akt
    REMOTE_MAINTENANCE: Final = 860  # ID_Einst_Fernwartung_akt
    PUMP_OPTIMIZATION_TIME: Final = 864  # ID_Einst_Popt_Nachlauf_akt
    EFFICIENCY_PUMP_NOMINAL: Final = 867  # ID_Einst_Effizienzpumpe_Nominal_akt
    EFFICIENCY_PUMP_MINIMAL: Final = 868  # ID_Einst_Effizienzpumpe_Minimal_akt
    EFFICIENCY_PUMP: Final = 869  # ID_Einst_Effizienzpumpe_akt
    # P0870_AMOUNT_COUNTER_ACTIVE: Final = "parameters.ID_Einst_Waermemenge_akt" --> flowRate
    SOLAR_PUMP_MAX_TEMPERATURE_COLLECTOR: Final = 883  # ID_Einst_TDC_Koll_Max_akt
    COOLING_TARGET_TEMPERATURE_MK3: Final = 966  # ID_Sollwert_KuCft3_akt
    HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR: Final = 980  # ID_RBE_Einflussfaktor_RT_akt
    HEATING_MIN_FLOW_OUT_TEMPERATURE: Final = (
        979  # ID_Einst_Minimale_Ruecklaufsolltemperatur
    )
    RELEASE_TIME_SECOND_HEAT_GENERATOR: Final = 992  # ID_Einst_Freigabe_Zeit_ZWE
    HEATING_MAXIMUM_CIRCULATION_PUMP_SPEED: Final = 1032  # ID_Einst_P155_PumpHeat_Max
    PUMP_HEAT_CONTROL: Final = 1033  # ID_Einst_P155_PumpHeatCtrl

class Parameter_SensorKey(IntEnum):
    UNSET: Final = -1
    HEATING_TARGET_CORRECTION: Final = 1  # ID_Einst_WK_akt returnTemperatureSetBack
    DHW_TARGET_TEMPERATURE: Final = 2  # ID_Einst_BWS_akt hotWaterTemperatureTarget
    MODE_HEATING: Final = 3  # ID_Ba_Hz_akt
    MODE_DHW: Final = 4  # ID_Ba_Bw_akt opModeHotWater
    # P0036_SECOND_HEAT_GENERATOR: Final = "parameters.ID_Einst_ZWE1Art_akt"  #  = 1 --> Heating and domestic water - Is second heat generator activated 1=electrical heater
    # P0091_ "max. outdoor temp." 35 20-45
    # P0092  "min. outdoor temp." -20-10
    # MODE_COOLING: Automatic or Off
    MODE_COOLING: Final = 108  # ID_Einst_BA_Kuehl_akt
    # P0125_HEATING_EXTERNAL_ENERGY_SOURCE TEE heating External energy source  10k 1.0-15.0  0.5
    # P0126_DHW_EXTERNAL_ENERGY_SOURCE TEE DHW External energy source  5k 1.0-15.0  0.5
    # "min OT flow max": Heat source temperature-dependent adjustment of the flow temperature. The outside temperature, up to which the flow max.
    # temperature with the heat pump may be increased, is adjusted here. Below this outside temperature, the actual VL maximum
    # temperature of the heat pump will fall linearally to the value “low limit of applic.“.
    # P0862_ "min OT flow max" -2C° -20-5  1
    # "flow operation limit": Heat source temperature-dependent adjustment of the flow temperature. Here, the maximum forward flow temperature of the heat pump is set at an outside temperature of -20°C.
    # P0863_ "flow operation limit"  58C° 35-75  1

    MODE_VENTILATION: Final = 894  # ID_Einst_BA_Lueftung_akt opModeVentilation  "Automatic", "Party", "Holidays", "Off"
    # P0973_ "DHW temp. max." 65C° 30-65 0.5
    # "1060 ID_Waermemenge_Reset                                        ": "535051",
    # "1061 ID_Waermemenge_Reset_2                                      ": "0",
    SILENT_MODE: Final = 1087  # Unknown_Parameter_1087  # Silent mode On/Off

Parameter_All_SensorKey = IntEnum('Parameter_All_SensorKey', [(i.name, i.value) for i in chain(Parameter_Static_SensorKey, Parameter_Calc_SensorKey, Parameter_Config_SensorKey, Parameter_SensorKey)])

class Parameter_Write_Permission(IntFlag):
    READ_ONLY = 0
    OPERATION = 1  # -> Parameter_SensorKey
    CONFIG = 2  # -> Parameter_Config_SensorKey
    CALCULATION = 4  # -> Parameter_Calc_SensorKey
    STATIC = 8  # -> Parameter_Static_SensorKey
    UNKNOWN_PARAMS = 2^31  # Not in enum!

class Calculation_SensorKey(Enum):
    UNSET: Final = -1
    FLOW_IN_TEMPERATURE: Final = 10  # ID_WEB_Temperatur_TVL flowTemperature
    FLOW_OUT_TEMPERATURE: Final = 11  # ID_WEB_Temperatur_TRL returnTemperature
    FLOW_OUT_TEMPERATURE_TARGET: Final = 12  # ID_WEB_Sollwert_TRL_HZ returnTemperatureTarget
    FLOW_OUT_TEMPERATURE_EXTERNAL: Final = 13  # ID_WEB_Temperatur_TRL_ext returnTemperatureExtern
    HOT_GAS_TEMPERATURE: Final = 14  # ID_WEB_Temperatur_THG / hotGasTemperature
    OUTDOOR_TEMPERATURE: Final = 15  # ID_WEB_Temperatur_TA / ambientTemperature
    OUTDOOR_TEMPERATURE_AVERAGE: Final = 16  # ID_WEB_Mitteltemperatur / averageAmbientTemperature
    DHW_TEMPERATURE: Final = 17  # ID_WEB_Temperatur_TBW hotWaterTemperature
    HEAT_SOURCE_INPUT_TEMPERATURE: Final = 19  # ID_WEB_Temperatur_TWE heatSourceIN
    HEAT_SOURCE_OUTPUT_TEMPERATURE: Final = 20  # ID_WEB_Temperatur_TWA heatSourceOUT
    SOLAR_COLLECTOR_TEMPERATURE: Final = 26  # ID_WEB_Temperatur_TSK
    SOLAR_BUFFER_TEMPERATURE: Final = 27  # ID_WEB_Temperatur_TSS
    DEFROST_END_FLOW_OKAY: Final = 29  # ID_WEB_ASDin
    EVU_UNLOCKED: Final = 31  # ID_WEB_EVUin
    # C0032_HIGH_PRESSURE_OKAY: Final = "calculations.ID_WEB_HDin"  # True/False -> Hochdruck OK
    MOTOR_PROTECTION: Final = 34  # ID_WEB_MOTin
    DEFROST_VALVE: Final = 37  # ID_WEB_AVout
    DHW_RECIRCULATION_PUMP: Final = 38  # ID_WEB_BUPout
    CIRCULATION_PUMP_HEATING: Final = 39  # ID_WEB_HUPout
    # C0040_MIXER1_OPENED: Final = "calculations.ID_WEB_MA1out"  # True/False -> Mischer 1 auf
    # C0041_MIXER1_CLOSED: Final = "calculations.ID_WEB_MZ1out"  # True/False -> Mischer 1 zu
    PUMP_FLOW: Final = 43  # ID_WEB_VBOout
    COMPRESSOR: Final = 44  # ID_WEB_VD1out
    COMPRESSOR2: Final = 45  # ID_WEB_VD2out
    DHW_CIRCULATION_PUMP: Final = 46  # ID_WEB_ZIPout
    ADDITIONAL_CIRCULATION_PUMP: Final = 47  # ID_WEB_ZUPout
    ADDITIONAL_HEAT_GENERATOR: Final = 48  # ID_WEB_ZW1out
    DISTURBANCE_OUTPUT: Final = 49  # ID_WEB_ZW2SSTout
    # C0051: Final = "calculations.ID_WEB_FP2out"  # True/False -> FBH Umwälzpumpe 2
    SOLAR_PUMP: Final = 52  # ID_WEB_SLPout
    # C0054_MIXER2_CLOSED: Final = "calculations.ID_WEB_MZ2out"  # True/False -> Mischer 2 zu
    # C0055_MIXER2_OPENED: Final = "calculations.ID_WEB_MA2out"  # True/False -> Mischer 2 auf
    COMPRESSOR1_OPERATION_HOURS: Final = 56  # ID_WEB_Zaehler_BetrZeitVD1
    COMPRESSOR1_IMPULSES: Final = 57  # ID_WEB_Zaehler_BetrZeitImpVD1
    COMPRESSOR2_OPERATION_HOURS: Final = 58  # ID_WEB_Zaehler_BetrZeitVD2
    COMPRESSOR2_IMPULSES: Final = 59  # ID_WEB_Zaehler_BetrZeitImpVD2
    ADDITIONAL_HEAT_GENERATOR_OPERATION_HOURS: Final = 60  # ID_WEB_Zaehler_BetrZeitZWE1
    OPERATION_HOURS: Final = 63  # ID_WEB_Zaehler_BetrZeitWP
    OPERATION_HOURS_HEATING: Final = 64  # ID_WEB_Zaehler_BetrZeitHz
    DHW_OPERATION_HOURS: Final = 65  # ID_WEB_Zaehler_BetrZeitBW
    OPERATION_HOURS_COOLING: Final = 66  # ID_WEB_Zaehler_BetrZeitKue
    TIMER_HEATPUMP_ON: Final = 67  # ID_WEB_Time_WPein_akt
    TIMER_ADD_HEAT_GENERATOR_ON: Final = 68  # ID_WEB_Time_ZWE1_akt
    TIMER_SEC_HEAT_GENERATOR_ON: Final = 69  # ID_WEB_Time_ZWE2_akt
    TIMER_NET_INPUT_DELAY: Final = 70  # ID_WEB_Timer_EinschVerz
    TIMER_SCB_OFF: Final = 71  # ID_WEB_Time_SSPAUS_akt
    TIMER_SCB_ON: Final = 72  # ID_WEB_Time_SSPEIN_akt
    TIMER_COMPRESSOR_OFF: Final = 73  # ID_WEB_Time_VDStd_akt
    TIMER_HC_ADD: Final = 74  # ID_WEB_Time_HRM_akt
    TIMER_HC_LESS: Final = 75  # ID_WEB_Time_HRW_akt
    TIMER_TDI: Final = 76  # ID_WEB_Time_LGS_akt
    TIMER_BLOCK_DHW: Final = 77  # ID_WEB_Time_SBW_akt
    MODEL_CODE: Final = 78  # ID_WEB_Code_WP_akt
    # 79 bivalentLevel
    STATUS: Final = 80  # ID_WEB_WP_BZ_akt opStateHotWater opStateHeating
    FIRMWARE_VERSION: Final = 81  # ID_WEB_SoftStand
    ERROR_TIME: Final = 95  # ID_WEB_ERROR_Time0
    ERROR_REASON: Final = 100  # ID_WEB_ERROR_Nr0
    # TODO: !
    # C0105_ERROR_COUNTER: Final = "calculations.ID_WEB_AnzahlFehlerInSpeicher"
    STATUS_LINE_1: Final = 117  # ID_WEB_HauptMenuStatus_Zeile1 opStateHeatPump1
    STATUS_LINE_2: Final = 118  # ID_WEB_HauptMenuStatus_Zeile2 opStateHeatPump2
    STATUS_LINE_3: Final = 119  # ID_WEB_HauptMenuStatus_Zeile3 opStateHeatPump3
    STATUS_TIME: Final = 120  # ID_WEB_HauptMenuStatus_Zeit
    TIMER_DEFROST: Final = 141  # ID_WEB_Time_AbtIn
    APPROVAL_COOLING: Final = 146  # ID_WEB_FreigabKuehl
    HEAT_AMOUNT_HEATING: Final = 151  # ID_WEB_WMZ_Heizung
    DHW_HEAT_AMOUNT: Final = 152  # ID_WEB_WMZ_Brauchwasser
    HEAT_AMOUNT_COUNTER: Final = 154  # ID_WEB_WMZ_Seit"  # 25668.
    HEAT_AMOUNT_FLOW_RATE: Final = 155  # ID_WEB_WMZ_Durchfluss / flowRate --> param 870 != 0
    ANALOG_OUT1: Final = 156  # ID_WEB_AnalogOut1
    ANALOG_OUT2: Final = 157  # ID_WEB_AnalogOut2
    TIMER_HOT_GAS: Final = 158  # ID_WEB_Time_Heissgas
    VENTILATION_SUPPLY_AIR_TEMPERATURE: Final = 159  # ID_WEB_Temp_Lueftung_Zuluft VentSupplyAirTemperature
    VENTILATION_EXHAUST_AIR_TEMPERATURE: Final = 160  # ID_WEB_Temp_Lueftung_Abluft VentExhaustAirTemperature
    HEAT_SOURCE_FLOW_RATE: Final = 173  # ID_WEB_Durchfluss_WQ
    SUCTION_EVAPORATOR_TEMPERATURE: Final = 175  # ID_WEB_LIN_ANSAUG_VERDAMPFER
    SUCTION_COMPRESSOR_TEMPERATURE: Final = 176  # ID_WEB_LIN_ANSAUG_VERDICHTER
    COMPRESSOR_HEATING_TEMPERATURE: Final = 177  # ID_WEB_LIN_VDH
    OVERHEATING_TEMPERATURE: Final = 178  # ID_WEB_LIN_UH
    OVERHEATING_TARGET_TEMPERATURE: Final = 179  # ID_WEB_LIN_UH_Soll
    HIGH_PRESSURE: Final = 180  # ID_WEB_LIN_HD
    LOW_PRESSURE: Final = 181  # ID_WEB_LIN_ND
    COMPRESSOR_HEATER: Final = 182  # ID_WEB_LIN_VDH_out
    # C0187_CURRENT_OUTPUT: Final = "calculations.ID_WEB_SEC_Qh_Soll"
    # C0188_CURRENT_OUTPUT: Final = "calculations.ID_WEB_SEC_Qh_Ist"
    HEAT_SOURCE_INPUT_TEMPERATURE_2: Final = 204  # ID_WEB_Temperatur_TWE_2
    ROOM_THERMOSTAT_TEMPERATURE: Final = 227  # ID_WEB_RBE_RT_Ist
    ROOM_THERMOSTAT_TEMPERATURE_TARGET: Final = 228  # ID_WEB_RBE_RT_Soll
    PUMP_FREQUENCY: Final = 231  # ID_WEB_Freq_VD
    PUMP_FLOW_DELTA_TARGET: Final = 239  # Unknown_Calculation_239
    # 239: Kelvin("VBO_Temp_Spread_Soll"), / 10, measurement, delta - ait_hup_vbo_calculated
    PUMP_FLOW_DELTA: Final = 240  # Unknown_Calculation_240
    # 240: Kelvin("VBO_Temp_Spread_Ist"), / 10, measurement, delta - ait_vbo_delta
    # 241: Percent2("HUP_PWM"),
    CIRCULATION_PUMP_DELTA_TARGET: Final = 242  # Unknown_Calculation_242
    # 242: Kelvin("HUP_Temp_Spread_Soll"), / 10, measurement, delta - ait_hup_delta_calculated
    CIRCULATION_PUMP_DELTA: Final = 243  # Unknown_Calculation_243
    # 243: Kelvin("HUP_Temp_Spread_Ist"), / 10, measurement, delta - ait_hup_delta
    # 254 Flow Rate
    CURRENT_HEAT_OUTPUT: Final = 257  # Heat_Output
    # 258 RBE Version


class Visibility_SensorKey(Enum):
    UNSET: Final = -1
    VENTILATION: Final = 4  # ID_Visi_Schwimmbad <-- correct?
    # 6    ID_Visi_Lueftung
    COOLING: Final = 5  # ID_Visi_Kuhlung
    MK1: Final = 7  # ID_Visi_MK1
    MK2: Final = 8  # ID_Visi_MK2
    FLOW_IN_TEMPERATURE: Final = 23  # ID_Visi_Temp_Vorlauf
    FLOW_OUT_TEMPERATURE_EXTERNAL: Final = 24  # ID_Visi_Temp_Rucklauf
    HOT_GAS_TEMPERATURE: Final = 27  # ID_Visi_Temp_Heissgas
    DHW_TEMPERATURE: Final = 29  # ID_Visi_Temp_BW_Ist
    SOLAR_COLLECTOR: Final = 38  # ID_Visi_Temp_Solarkoll
    SOLAR_BUFFER: Final = 39  # ID_Visi_Temp_Solarsp
    DEFROST_END_FLOW_OKAY: Final = 41  # ID_Visi_IN_ASD
    EVU_IN: Final = 43  # ID_Visi_IN_EVU
    MOTOR_PROTECTION: Final = 45  # ID_Visi_IN_MOT
    DEFROST_VALVE: Final = 49  # ID_Visi_OUT_Abtauventil
    DHW_RECIRCULATION_PUMP: Final = 50  # ID_Visi_OUT_BUP
    CIRCULATION_PUMP_HEATING: Final = 52  # ID_Visi_OUT_HUP
    DHW_CIRCULATION_PUMP: Final = 59  # ID_Visi_OUT_ZIP
    DHW_CHARGING_PUMP: Final = -1  # V0059A_DHW_CHARGING_PUMP
    ADDITIONAL_CIRCULATION_PUMP: Final = 60  # ID_Visi_OUT_ZUP
    SECOND_HEAT_GENERATOR: Final = 61  # ID_Visi_OUT_ZWE1
    COMPRESSOR1_OPERATION_HOURS: Final = 80  # ID_Visi_Bst_BStdVD1
    COMPRESSOR1_IMPULSES: Final = 81  # ID_Visi_Bst_ImpVD1
    COMPRESSOR2_OPERATION_HOURS: Final = 83  # ID_Visi_Bst_BStdVD2
    COMPRESSOR2_IMPULSES: Final = 84  # ID_Visi_Bst_ImpVD2
    ADDITIONAL_HEAT_GENERATOR_OPERATION_HOURS: Final = 86  # ID_Visi_Bst_BStdZWE1
    HEATING_HYSTERESIS: Final = 93  # returnTemperatureHyst ID_Visi_Text_Abtauen <- correct?
    HEATSOURCE_DEFROST_AIR_THRESHOLD_TEMPERATURE: Final = 97  # ID_Visi_EinstTemp_Freig2VD <-- Bouni Luxtronik Name is wrong!
    HEATSOURCE_DEFROST_AIR_END_TEMPERATURE: Final = 105  # ID_Visi_EinstTemp_TWQmin
    EVU_LOCKED: Final = 121  # ID_Visi_SysEin_EVUSperre
    ROOM_THERMOSTAT: Final = 122  # ID_Visi_SysEin_Raumstation
    PUMP_OPTIMIZATION: Final = 144  # ID_Visi_SysEin_Pumpenoptim
    HEATING_CIRCULATION_PUMP_DEAERATE: Final = 161  # ID_Visi_SysEin_LaufzeitMk2 <-- Name correct?
    DHW_CIRCULATION_PUMP_DEAERATE: Final = 167  # ID_Visi_Enlt_MA1
    MK3: Final = 211  # ID_Visi_MK3
    TIMER_DEFROST: Final = 219  # ID_Visi_SysEin_Kuhl_Zeit_Ein <-- Bouni Luxtronik Name is wrong?
    EFFICIENCY_PUMP_NOMINAL: Final = 239  # ID_Visi_SysEin_EffizienzpumpeNom
    EFFICIENCY_PUMP_MINIMAL: Final = 240  # ID_Visi_SysEin_EffizienzpumpeMin
    ANALOG_OUT1: Final = 248  # ID_Visi_OUT_Analog_1
    ANALOG_OUT2: Final = 249  # ID_Visi_OUT_Analog_2
    SOLAR: Final = 250  # ID_Visi_Solar
    VENTILATION_SUPPLY_AIR_TEMPERATURE: Final = 264  # ID_Visi_Einst_Luf_Nennlueftung_akt VentSupplyAirTemperature
    VENTILATION_EXHAUST_AIR_TEMPERATURE: Final = 265  # ID_Visi_Einst_Luf_Intensivlueftung_akt VentExhaustAirTemperature
    SUCTION_COMPRESSOR_TEMPERATURE: Final = 289  # ID_Visi_LIN_ANSAUG_VERDICHTER
    COMPRESSOR_HEATING: Final = 290  # ID_Visi_LIN_VDH
    OVERHEATING_TEMPERATURE: Final = 291  # ID_Visi_LIN_UH
    LIN_PRESSURE: Final = 292  # ID_Visi_LIN_Druck
    SUCTION_EVAPORATOR_TEMPERATURE: Final = 310  # ID_Visi_LIN_ANSAUG_VERDAMPFER
    ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER: Final = 324  # ID_Visi_Waermemenge_ZWE
    SILENT_MODE_TIME_MENU: Final = 357  # Unknown_Parameter_357

LUX_PARAMETER_MK_SENSORS: Final = [
    Visibility_SensorKey.MK1,
    Visibility_SensorKey.MK2,
    Visibility_SensorKey.MK3,
]

# endregion Keys


# region Attr Keys
class SensorAttrFormat(Enum):
    """Luxtronik sensor attribute format."""

    HOUR_MINUTE = 1
    CELSIUS_TENTH = 2
    SWITCH_GAP = 3
    TIMESTAMP_LAST_OVER = 4

    DURATION = 11


class SensorAttrKey(StrEnum):
    """Luxtronik sensor attribute keys."""

    LUXTRONIK_KEY = "Luxtronik_Key"
    DESCRIPTION = "description"

    STATUS_TEXT = "status_text"
    LAST_THERMAL_DESINFECTION = "last_thermal_desinfection"
    SWITCH_GAP = "switch_gap"
    STATUS_RAW = "status_raw"
    EVU_FIRST_START_TIME = "EVU_first_start_time"
    EVU_FIRST_END_TIME = "EVU_first_end_time"
    EVU_SECOND_START_TIME = "EVU_second_start_time"
    EVU_SECOND_END_TIME = "EVU_second_end_time"
    EVU_MINUTES_UNTIL_NEXT_EVENT = "EVU_minutes_until_next_event"
    TIMESTAMP = "timestamp"
    CODE = "code"
    CAUSE = "cause"
    REMEDY = "remedy"
    MAX_ALLOWED = "max_allowed"

    TIMER_HEATPUMP_ON = "WP Seit (ID_WEB_Time_WPein_akt)"
    TIMER_ADD_HEAT_GENERATOR_ON = "ZWE1 seit (ID_WEB_Time_ZWE1_akt)"
    TIMER_SEC_HEAT_GENERATOR_ON = "ZWE2 seit (ID_WEB_Time_ZWE2_akt)"
    TIMER_NET_INPUT_DELAY = "Netzeinschaltverz\u00f6gerung (ID_WEB_Timer_EinschVerz)"
    TIMER_SCB_OFF = "Schaltspielsperre Aus-Zeit (ID_WEB_Time_SSPAUS_akt)"
    TIMER_SCB_ON = "Schaltspielsperre Ein-Zeit (ID_WEB_Time_SSPEIN_akt)"
    TIMER_COMPRESSOR_OFF = "VD-Stand (ID_WEB_Time_VDStd_akt)"
    TIMER_HC_ADD = "Heizungsregler Mehr-Zeit HRM-Zeit (ID_WEB_Time_HRM_akt)"
    TIMER_HC_LESS = "Heizungsregler Weniger-Zeit HRW-Stand (ID_WEB_Time_HRW_akt)"
    TIMER_TDI = "ID_WEB_Time_LGS_akt"
    TIMER_BLOCK_DHW = "Sperre WW? ID_WEB_Time_SBW_akt"
    TIMER_DEFROST = "Abtauen in ID_WEB_Time_AbtIn"
    TIMER_HOT_GAS = "ID_WEB_Time_Heissgas"

    # Defrost attributes
    DURATION = "DURATION"
    AMBIENT_TEMPERATURE = "AMBIENT_TEMPERATURE"
    HEAT_SOURCE_INPUT_TEMPERATURE = "HEAT_SOURCE_INPUT_TEMPERATURE"


# endregion Attr Keys

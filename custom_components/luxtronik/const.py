"""Constants for the Luxtronik heatpump integration."""

# region Imports
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
import logging
from typing import Final

from enum import StrEnum
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import Platform
from homeassistant.helpers.typing import StateType

# endregion Imports

# region Constants Main
DOMAIN: Final = "luxtronik2"
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

    minor_80: Final = 80
    minor_88: Final = 88
    minor_90: Final = 90


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


class LuxOperationMode(StrEnum):
    """Lux Operation modes heating, hot water etc."""

    heating: Final = "heating"  # 0
    domestic_water: Final = "hot water"  # 1
    swimming_pool_solar: Final = "swimming pool/solar"  # 2
    evu: Final = "evu"  # 3
    defrost: Final = "defrost"  # 4
    no_request: Final = "no request"  # 5
    heating_external_source: Final = "heating external source"  # 6
    cooling: Final = "cooling"  # 7


class LuxMode(StrEnum):
    """Luxmodes off etc."""

    off: Final = "Off"
    automatic: Final = "Automatic"
    second_heatsource: Final = "Second heatsource"
    party: Final = "Party"
    holidays: Final = "Holidays"


class LuxStatus1Option(StrEnum):
    """LuxStatus1 option defrost etc."""

    heatpump_running: Final = "heatpump running"
    heatpump_idle: Final = "heatpump idle"
    heatpump_coming: Final = "heatpump coming"
    heatpump_shutdown: Final = "heatpump shutdown"
    errorcode_slot_zero: Final = "errorcode slot 0"
    defrost: Final = "defrost"
    witing_on_LIN_connection: Final = "witing on LIN connection"
    compressor_heating_up: Final = "compressor heating up"
    pump_forerun: Final = "pump forerun"
    compressor_heater: Final = "compressor heater"


class LuxStatus3Option(StrEnum):
    """LuxStatus3 option heating etc."""

    unknown: Final = ("unknown",)
    none: Final = ("none",)
    heating: Final = ("heating",)
    no_request: Final = ("no request",)
    grid_switch_on_delay: Final = ("grid switch on delay",)
    cycle_lock: Final = ("cycle lock",)
    lock_time: Final = ("lock time",)
    domestic_water: Final = ("domestic water",)
    info_bake_out_program: Final = ("info bake out program",)
    defrost: Final = ("defrost",)
    pump_forerun: Final = ("pump forerun",)
    thermal_desinfection: Final = ("thermal desinfection",)
    cooling: Final = ("cooling",)
    swimming_pool_solar: Final = ("swimming pool/solar",)
    heating_external_energy_source: Final = ("heating external energy source",)
    domestic_water_external_energy_source: Final = (
        "domestic water external energy source",
    )
    flow_monitoring: Final = ("flow monitoring",)
    second_heat_generator_1_active: Final = ("second heat generator 1 active",)


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

    cycle_lock: Final = 0  # cycle_lock
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
    undefined_20: Final = 20  # ???
    undefined_21: Final = 21  # ???
    undefined_22: Final = 22  # ???
    undefined_23: Final = 23  # ???
    undefined_24: Final = 24  # ???
    undefined_25: Final = 25  # ???
    undefined_26: Final = 26  # ???
    undefined_27: Final = 27  # ???
    undefined_28: Final = 28  # ???
    undefined_29: Final = 29  # ???
    undefined_30: Final = 30  # ???
    undefined_31: Final = 31  # ???


LUX_STATE_ICON_MAP: Final[dict[StateType | date | datetime | Decimal, str]] = {
    LuxOperationMode.heating.value: "mdi:radiator",
    LuxOperationMode.domestic_water.value: "mdi:waves",
    LuxOperationMode.swimming_pool_solar.value: "mdi:pool",
    LuxOperationMode.evu.value: "mdi:power-plug-off",
    LuxOperationMode.defrost.value: "mdi:car-defrost-rear",
    LuxOperationMode.no_request.value: "mdi:hvac-off",  # "mdi:heat-pump-outline",  # "mdi:radiator-disabled",
    LuxOperationMode.heating_external_source.value: "mdi:patio-heater",
    LuxOperationMode.cooling.value: "mdi:air-conditioner",
}

LUX_STATE_ICON_MAP_COOL: Final[dict[StateType | date | datetime | Decimal, str]] = {
    LuxOperationMode.swimming_pool_solar.value: "mdi:pool",
    LuxOperationMode.evu.value: "mdi:power-plug-off",
    LuxOperationMode.defrost.value: "mdi:car-defrost-rear",
    LuxOperationMode.no_request.value: "mdi:snowflake-off",
    LuxOperationMode.cooling.value: "mdi:air-conditioner",
}

LUX_MODELS_ALPHA_INNOTEC = ["LWP", "LWV", "MSW", "SWC", "SWP"]
LUX_MODELS_NOVELAN = ["BW", "LA", "LD", "LI", "SI", "ZLW"]
LUX_MODELS_OTHER = ["CB", "CI", "CN", "CS"]
# endregion Lux Definitions

# region Lux parameters


class LuxParameter(StrEnum):
    """Luxtronik parameter ids."""

    UNSET: Final = "UNSET"
    P0001_HEATING_TARGET_CORRECTION: Final = "parameters.ID_Einst_WK_akt"
    P0105_DHW_TARGET_TEMPERATURE: Final = "parameters.ID_Soll_BWS_akt"
    P0003_MODE_HEATING: Final = "parameters.ID_Ba_Hz_akt"
    P0004_MODE_DHW: Final = "parameters.ID_Ba_Bw_akt"
    # luxtronik*_heating_curve*
    P0011_HEATING_CURVE_END_TEMPERATURE: Final = "parameters.ID_Einst_HzHwHKE_akt"
    P0012_HEATING_CURVE_PARALLEL_SHIFT_TEMPERATURE: Final = "parameters.ID_Einst_HzHKRANH_akt"
    P0013_HEATING_CURVE_NIGHT_TEMPERATURE: Final = (
        "parameters.ID_Einst_HzHKRABS_akt"
    )
    # luxtronik*_heating_curve_circuit1*
    P0014_HEATING_CURVE_CIRCUIT1_END_TEMPERATURE: Final = (
        "parameters.ID_Einst_HzMK1E_akt"  # 260
    )
    P0015_HEATING_CURVE_CIRCUIT1_PARALLEL_SHIFT_TEMPERATURE: Final = (
        "parameters.ID_Einst_HzMK1ANH_akt"  # 290
    )
    P0016_HEATING_CURVE_CIRCUIT1_NIGHT_TEMPERATURE: Final = (
        "parameters.ID_Einst_HzMK1ABS_akt"  # 0
    )
    # luxtronik*_heating_curve_circuit2*
    P0017_HEATING_CURVE_CIRCUIT2_END_TEMPERATURE: Final = (
        "parameters.ID_Einst_HzMK2E_akt"  # 260
    )
    P0018_HEATING_CURVE_CIRCUIT2_PARALLEL_SHIFT_TEMPERATURE: Final = (
        "parameters.ID_Einst_HzMK2ANH_akt"  # 290
    )
    P0019_HEATING_CURVE_CIRCUIT2_NIGHT_TEMPERATURE: Final = (
        "parameters.ID_Einst_HzMK2ABS_akt"  # 0
    )
    # luxtronik*_heating_curve_circuit3*
    P0020_HEATING_CURVE_CIRCUIT3_END_TEMPERATURE: Final = (
        "parameters.ID_Einst_HzMK3E_akt"  # 270
    )
    P0021_HEATING_CURVE_CIRCUIT3_PARALLEL_SHIFT_TEMPERATURE: Final = (
        "parameters.ID_Einst_HzMK3ANH_akt"  # 290
    )
    P0022_HEATING_CURVE_CIRCUIT3_NIGHT_TEMPERATURE: Final = (
        "parameters.ID_Einst_HzMK3ABS_akt"  # 0
    )
    # P0036_SECOND_HEAT_GENERATOR: Final = "parameters.ID_Einst_ZWE1Art_akt"  #  = 1 --> Heating and domestic water - Is second heat generator activated 1=electrical heater
    P0042_MIXING_CIRCUIT1_TYPE: Final = "parameters.ID_Einst_MK1Typ_akt"
    P0047_DHW_THERMAL_DESINFECTION_TARGET: Final = "parameters.ID_Einst_LGST_akt"
    P0049_PUMP_OPTIMIZATION: Final = "parameters.ID_Einst_Popt_akt"
    # P0033_ROOM_THERMOSTAT_TYPE: Final = "parameters.ID_Einst_RFVEinb_akt"  # != 0 --> Has_Room_Temp
    P0074_DHW_HYSTERESIS: Final = "parameters.ID_Einst_BWS_Hyst_akt"
    P0085_DHW_CHARGING_PUMP: Final = "parameters.ID_Einst_BWZIP_akt"  # has_domestic_water_circulation_pump int() != 1
    P0088_HEATING_HYSTERESIS: Final = "parameters.ID_Einst_HRHyst_akt"
    P0089_HEATING_MAX_FLOW_OUT_INCREASE_TEMPERATURE: Final = (
        "parameters.ID_Einst_TRErhmax_akt"
    )
    P0090_RELEASE_SECOND_HEAT_GENERATOR: Final = "parameters.ID_Einst_ZWEFreig_akt"
    P0093_HEAT_SOURCE_INPUT_TEMPERATURE_MIN: Final = "parameters.ID_Einst_TWQmin_akt"
    # MODE_COOLING: Automatic or Off
    P0108_MODE_COOLING: Final = "parameters.ID_Einst_BA_Kuehl_akt"
    P0110_COOLING_OUTDOOR_TEMP_THRESHOLD: Final = "parameters.ID_Einst_KuehlFreig_akt"
    P0111_HEATING_NIGHT_LOWERING_TO_TEMPERATURE: Final = (
        "parameters.ID_Einst_TAbsMin_akt"
    )
    P0122_SOLAR_PUMP_ON_DIFFERENCE_TEMPERATURE: Final = (
        "parameters.ID_Einst_TDC_Ein_akt"
    )
    P0123_SOLAR_PUMP_OFF_DIFFERENCE_TEMPERATURE: Final = (
        "parameters.ID_Einst_TDC_Aus_akt"
    )
    P0130_MIXING_CIRCUIT2_TYPE: Final = "parameters.ID_Einst_MK2Typ_akt"
    P0132_COOLING_TARGET_TEMPERATURE_MK1: Final = "parameters.ID_Sollwert_KuCft1_akt"
    P0133_COOLING_TARGET_TEMPERATURE_MK2: Final = "parameters.ID_Sollwert_KuCft2_akt"
    P0155_VENTING_TIME_HOURS: Final = "parameters.ID_Einst_Entl_time_akt"
    P0158_VENTING_ACTIVE: Final = "parameters.ID_Einst_Entl_akt"
    P0780_MIXING_CIRCUIT3_TYPE: Final = "parameters.ID_Einst_MK3Typ_akt"        
    P0149_FLOW_IN_TEMPERATURE_MAX_ALLOWED: Final = "parameters.ID_Einst_TVLmax_akt"
    P0289_SOLAR_PUMP_OFF_MAX_DIFFERENCE_TEMPERATURE_BOILER: Final = (
        "parameters.ID_Einst_TDC_Max_akt"
    )
    P0678_VENTING_HUP_ACTIVE: Final = "parameters.ID_Einst_Entl_Typ_0"
    P0699_HEATING_THRESHOLD: Final = "parameters.ID_Einst_Heizgrenze"
    P0700_HEATING_THRESHOLD_TEMPERATURE: Final = "parameters.ID_Einst_Heizgrenze_Temp"
    P0716_0720_SWITCHOFF_REASON: Final = "parameters.ID_Switchoff_file_{ID}_0"  # e.g. ID_Switchoff_file_0_0 - ID_Switchoff_file_4_0
    P0721_0725_SWITCHOFF_TIMESTAMP: Final = "parameters.ID_Switchoff_file_{ID}_1"  # e.g. ID_Switchoff_file_0_1 - ID_Switchoff_file_4_1
    P0850_COOLING_START_DELAY_HOURS: Final = "parameters.ID_Einst_Kuhl_Zeit_Ein_akt"
    P0851_COOLING_STOP_DELAY_HOURS: Final = "parameters.ID_Einst_Kuhl_Zeit_Aus_akt"
    P0860_REMOTE_MAINTENANCE: Final = "parameters.ID_Einst_Fernwartung_akt"
    P0864_PUMP_OPTIMIZATION_TIME: Final = "parameters.ID_Einst_Popt_Nachlauf_akt"
    P0867_EFFICIENCY_PUMP_NOMINAL: Final = (
        "parameters.ID_Einst_Effizienzpumpe_Nominal_akt"
    )
    P0868_EFFICIENCY_PUMP_MINIMAL: Final = (
        "parameters.ID_Einst_Effizienzpumpe_Minimal_akt"
    )
    P0869_EFFICIENCY_PUMP: Final = "parameters.ID_Einst_Effizienzpumpe_akt"
    # P0870_AMOUNT_COUNTER_ACTIVE: Final = "parameters.ID_Einst_Waermemenge_akt"
    P0874_SERIAL_NUMBER: Final = "parameters.ID_WP_SerienNummer_DATUM"
    P0875_SERIAL_NUMBER_MODEL: Final = "parameters.ID_WP_SerienNummer_HEX"

    # "852  ID_Waermemenge_Seit                                         ": "2566896",
    # "853  ID_Waermemenge_WQ                                           ": "0",
    # "854  ID_Waermemenge_Hz                                           ": "3317260",
    # "855  ID_Waermemenge_WQ_ges                                       ": "0",
    #  "878  ID_Waermemenge_BW                                           ": "448200",
    #  "879  ID_Waermemenge_SW                                           ": "0",
    #  "880  ID_Waermemenge_Datum                                        ": "1483648906", <-- Unix timestamp!  5.1.2017

    P0882_SOLAR_OPERATION_HOURS: Final = "parameters.ID_BSTD_Solar"
    P0883_SOLAR_PUMP_MAX_TEMPERATURE_COLLECTOR: Final = (
        "parameters.ID_Einst_TDC_Koll_Max_akt"
    )
    # P0894_VENTILATION_MODE: Final = "parameters.ID_Einst_BA_Lueftung_akt" # "Automatic", "Party", "Holidays", "Off"
    P0966_COOLING_TARGET_TEMPERATURE_MK3: Final = "parameters.ID_Sollwert_KuCft3_akt"
    P0979_HEATING_MIN_FLOW_OUT_TEMPERATURE: Final = (
        "parameters.ID_Einst_Minimale_Ruecklaufsolltemperatur"
    )
    P0980_HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR: Final = (
        "parameters.ID_RBE_Einflussfaktor_RT_akt"
    )
    P0992_RELEASE_TIME_SECOND_HEAT_GENERATOR: Final = (
        "parameters.ID_Einst_Freigabe_Zeit_ZWE"
    )
    P1032_HEATING_MAXIMUM_CIRCULATION_PUMP_SPEED: Final = (
        "parameters.ID_Einst_P155_PumpHeat_Max"
    )
    P1030_SMART_GRID_SWITCH: Final = (
        "parameters.ID_Einst_SmartGrid"
    )
    P1033_PUMP_HEAT_CONTROL: Final = "parameters.ID_Einst_P155_PumpHeatCtrl"
    P1059_ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER: Final = (
        "parameters.ID_Waermemenge_ZWE"
    )
    # "1060 ID_Waermemenge_Reset                                        ": "535051",
    # "1061 ID_Waermemenge_Reset_2                                      ": "0",
    P1087_SILENT_MODE: Final = "parameters.Unknown_Parameter_1087"  # Silent mode On/Off
    P1119_LAST_DEFROST_TIMESTAMP: Final = (
        "parameters.Unknown_Parameter_1119"  # 1685073431 -> 26.5.23 05:57
    )
    P1136_HEAT_ENERGY_INPUT: Final = "parameters.Unknown_Parameter_1136"
    P1137_DHW_ENERGY_INPUT: Final = "parameters.Unknown_Parameter_1137"
    # ? P1138_SWIMMING_POOL_ENERGY_INPUT: Final = "parameters.Unknown_Parameter_1138" -->
    P1139_COOLING_ENERGY_INPUT: Final = "parameters.Unknown_Parameter_1139"
    P1158_POWER_LIMIT_SWITCH: Final = "parameters.Unknown_Parameter_1158"
    P1159_POWER_LIMIT_VALUE: Final = "parameters.Unknown_Parameter_1159"
    P1140_SECOND_HEAT_GENERATOR_AMOUNT_COUNTER: Final = (
        "parameters.Unknown_Parameter_1140"
    )

# endregion Lux parameters

LUX_PARAMETER_MK_SENSORS: Final = [
    LuxParameter.P0042_MIXING_CIRCUIT1_TYPE,
    LuxParameter.P0130_MIXING_CIRCUIT2_TYPE,
    LuxParameter.P0780_MIXING_CIRCUIT3_TYPE,
]


# region Lux calculations
class LuxCalculation(StrEnum):
    """Luxtronik calculation ids."""

    UNSET: Final = "UNSET"
    C0010_FLOW_IN_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TVL"
    C0011_FLOW_OUT_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TRL"
    C0012_FLOW_OUT_TEMPERATURE_TARGET: Final = "calculations.ID_WEB_Sollwert_TRL_HZ"
    C0013_FLOW_OUT_TEMPERATURE_EXTERNAL: Final = (
        "calculations.ID_WEB_Temperatur_TRL_ext"
    )
    C0014_HOT_GAS_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_THG"
    C0015_OUTDOOR_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TA"
    C0016_OUTDOOR_TEMPERATURE_AVERAGE: Final = "calculations.ID_WEB_Mitteltemperatur"
    C0017_DHW_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TBW"
    C0018_FLOW_IN_CIRCUIT1_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TFB1"
    C0019_FLOW_IN_CIRCUIT2_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TFB2"
    C0020_FLOW_IN_CIRCUIT3_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TFB3"
    C0021_FLOW_IN_CIRCUIT1_TARGET_TEMPERATURE: Final = "calculations.ID_WEB_Sollwert_TVL_MK1"
    C0022_FLOW_IN_CIRCUIT2_TARGET_TEMPERATURE: Final = "calculations.ID_WEB_Sollwert_TVL_MK2"
    C0023_FLOW_IN_CIRCUIT3_TARGET_TEMPERATURE: Final = "calculations.ID_WEB_Sollwert_TVL_MK3"
    C0024_HEAT_SOURCE_OUTPUT_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TWA"
    C0026_SOLAR_COLLECTOR_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TSK"
    C0027_SOLAR_BUFFER_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TSS"
    C0029_DEFROST_END_FLOW_OKAY: Final = "calculations.ID_WEB_ASDin"
    C0031_EVU_UNLOCKED: Final = "calculations.ID_WEB_EVUin"
    # C0032_HIGH_PRESSURE_OKAY: Final = "calculations.ID_WEB_HDin"  # True/False -> Hochdruck OK
    C0034_MOTOR_PROTECTION: Final = "calculations.ID_WEB_MOTin"
    C0037_DEFROST_VALVE: Final = "calculations.ID_WEB_AVout"
    C0038_DHW_RECIRCULATION_PUMP: Final = "calculations.ID_WEB_BUPout"
    C0039_CIRCULATION_PUMP_HEATING: Final = "calculations.ID_WEB_HUPout"
    # C0040_MIXER1_OPENED: Final = "calculations.ID_WEB_MA1out"  # True/False -> Mischer 1 auf
    # C0041_MIXER1_CLOSED: Final = "calculations.ID_WEB_MZ1out"  # True/False -> Mischer 1 zu
    C0043_PUMP_FLOW: Final = "calculations.ID_WEB_VBOout"
    C0044_COMPRESSOR: Final = "calculations.ID_WEB_VD1out"
    C0045_COMPRESSOR2: Final = "calculations.ID_WEB_VD2out"
    C0046_DHW_CIRCULATION_PUMP: Final = "calculations.ID_WEB_ZIPout"
    C0047_ADDITIONAL_CIRCULATION_PUMP: Final = "calculations.ID_WEB_ZUPout"
    C0048_ADDITIONAL_HEAT_GENERATOR: Final = "calculations.ID_WEB_ZW1out"
    C0049_DISTURBANCE_OUTPUT: Final = "calculations.ID_WEB_ZW2SSTout"
    # C0051: Final = "calculations.ID_WEB_FP2out"  # True/False -> FBH Umwälzpumpe 2
    C0052_SOLAR_PUMP: Final = "calculations.ID_WEB_SLPout"
    # C0054_MIXER2_CLOSED: Final = "calculations.ID_WEB_MZ2out"  # True/False -> Mischer 2 zu
    # C0055_MIXER2_OPENED: Final = "calculations.ID_WEB_MA2out"  # True/False -> Mischer 2 auf
    C0056_COMPRESSOR1_OPERATION_HOURS: Final = "calculations.ID_WEB_Zaehler_BetrZeitVD1"
    C0057_COMPRESSOR1_IMPULSES: Final = "calculations.ID_WEB_Zaehler_BetrZeitImpVD1"
    C0058_COMPRESSOR2_OPERATION_HOURS: Final = "calculations.ID_WEB_Zaehler_BetrZeitVD2"
    C0059_COMPRESSOR2_IMPULSES: Final = "calculations.ID_WEB_Zaehler_BetrZeitImpVD2"
    C0060_ADDITIONAL_HEAT_GENERATOR_OPERATION_HOURS: Final = (
        "calculations.ID_WEB_Zaehler_BetrZeitZWE1"
    )
    C0061_ADDITIONAL_HEAT_GENERATOR2_OPERATION_HOURS: Final = (
        "calculations.ID_WEB_Zaehler_BetrZeitZWE2"
    )
    C0063_OPERATION_HOURS: Final = "calculations.ID_WEB_Zaehler_BetrZeitWP"
    C0064_OPERATION_HOURS_HEATING: Final = "calculations.ID_WEB_Zaehler_BetrZeitHz"
    C0065_DHW_OPERATION_HOURS: Final = "calculations.ID_WEB_Zaehler_BetrZeitBW"
    C0066_OPERATION_HOURS_COOLING: Final = "calculations.ID_WEB_Zaehler_BetrZeitKue"
    C0067_TIMER_HEATPUMP_ON: Final = "calculations.ID_WEB_Time_WPein_akt"
    C0068_TIMER_ADD_HEAT_GENERATOR_ON: Final = "calculations.ID_WEB_Time_ZWE1_akt"
    C0069_TIMER_SEC_HEAT_GENERATOR_ON: Final = "calculations.ID_WEB_Time_ZWE2_akt"
    C0070_TIMER_NET_INPUT_DELAY: Final = "calculations.ID_WEB_Timer_EinschVerz"
    C0071_TIMER_SCB_OFF: Final = "calculations.ID_WEB_Time_SSPAUS_akt"
    C0072_TIMER_SCB_ON: Final = "calculations.ID_WEB_Time_SSPEIN_akt"
    C0073_TIMER_COMPRESSOR_OFF: Final = "calculations.ID_WEB_Time_VDStd_akt"
    C0074_TIMER_HC_ADD: Final = "calculations.ID_WEB_Time_HRM_akt"
    C0075_TIMER_HC_LESS: Final = "calculations.ID_WEB_Time_HRW_akt"
    C0076_TIMER_TDI: Final = "calculations.ID_WEB_Time_LGS_akt"
    C0077_TIMER_BLOCK_DHW: Final = "calculations.ID_WEB_Time_SBW_akt"
    C0078_MODEL_CODE: Final = "calculations.ID_WEB_Code_WP_akt"
    C0080_STATUS: Final = "calculations.ID_WEB_WP_BZ_akt"
    C0081_FIRMWARE_VERSION: Final = "calculations.ID_WEB_SoftStand"
    C0095_ERROR_TIME: Final = "calculations.ID_WEB_ERROR_Time0"
    C0100_ERROR_REASON: Final = "calculations.ID_WEB_ERROR_Nr0"
    # TODO: !
    # C0105_ERROR_COUNTER: Final = "calculations.ID_WEB_AnzahlFehlerInSpeicher"
    C0117_STATUS_LINE_1: Final = "calculations.ID_WEB_HauptMenuStatus_Zeile1"
    C0118_STATUS_LINE_2: Final = "calculations.ID_WEB_HauptMenuStatus_Zeile2"
    C0119_STATUS_LINE_3: Final = "calculations.ID_WEB_HauptMenuStatus_Zeile3"
    C0120_STATUS_TIME: Final = "calculations.ID_WEB_HauptMenuStatus_Zeit"
    C0141_TIMER_DEFROST: Final = "calculations.ID_WEB_Time_AbtIn"
    C0146_APPROVAL_COOLING: Final = "calculations.ID_WEB_FreigabKuehl"
    C0151_HEAT_AMOUNT_HEATING: Final = "calculations.ID_WEB_WMZ_Heizung"
    C0152_DHW_HEAT_AMOUNT: Final = "calculations.ID_WEB_WMZ_Brauchwasser"
    C0154_HEAT_AMOUNT_COUNTER: Final = "calculations.ID_WEB_WMZ_Seit"  # 25668.9
    C0155_HEAT_AMOUNT_FLOW_RATE: Final = "calculations.ID_WEB_WMZ_Durchfluss"
    C0156_ANALOG_OUT1: Final = "calculations.ID_WEB_AnalogOut1"
    C0157_ANALOG_OUT2: Final = "calculations.ID_WEB_AnalogOut2"
    C0158_TIMER_HOT_GAS: Final = "calculations.ID_WEB_Time_Heissgas"
    C0173_HEAT_SOURCE_FLOW_RATE: Final = "calculations.ID_WEB_Durchfluss_WQ"
    C0175_SUCTION_EVAPORATOR_TEMPERATURE: Final = (
        "calculations.ID_WEB_LIN_ANSAUG_VERDAMPFER"
    )
    C0176_SUCTION_COMPRESSOR_TEMPERATURE: Final = (
        "calculations.ID_WEB_LIN_ANSAUG_VERDICHTER"
    )
    C0177_COMPRESSOR_HEATING_TEMPERATURE: Final = "calculations.ID_WEB_LIN_VDH"
    C0178_OVERHEATING_TEMPERATURE: Final = "calculations.ID_WEB_LIN_UH"
    C0179_OVERHEATING_TARGET_TEMPERATURE: Final = "calculations.ID_WEB_LIN_UH_Soll"
    C0180_HIGH_PRESSURE: Final = "calculations.ID_WEB_LIN_HD"
    C0181_LOW_PRESSURE: Final = "calculations.ID_WEB_LIN_ND"
    C0182_COMPRESSOR_HEATER: Final = "calculations.ID_WEB_LIN_VDH_out"
    # C0187_CURRENT_OUTPUT: Final = "calculations.ID_WEB_SEC_Qh_Soll"
    # C0188_CURRENT_OUTPUT: Final = "calculations.ID_WEB_SEC_Qh_Ist"
    C0204_HEAT_SOURCE_INPUT_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TWE"
    C0227_ROOM_THERMOSTAT_TEMPERATURE: Final = "calculations.ID_WEB_RBE_RT_Ist"
    C0228_ROOM_THERMOSTAT_TEMPERATURE_TARGET: Final = "calculations.ID_WEB_RBE_RT_Soll"
    C0231_PUMP_FREQUENCY: Final = "calculations.ID_WEB_Freq_VD"
    C0239_PUMP_FLOW_DELTA_TARGET: Final = "calculations.Unknown_Calculation_239"
    # 239: Kelvin("VBO_Temp_Spread_Soll"), / 10, measurement, delta - ait_hup_vbo_calculated
    C0240_PUMP_FLOW_DELTA: Final = "calculations.Unknown_Calculation_240"
    # 240: Kelvin("VBO_Temp_Spread_Ist"), / 10, measurement, delta - ait_vbo_delta
    # 241: Percent2("HUP_PWM"),
    C0242_CIRCULATION_PUMP_DELTA_TARGET: Final = "calculations.Unknown_Calculation_242"
    # 242: Kelvin("HUP_Temp_Spread_Soll"), / 10, measurement, delta - ait_hup_delta_calculated
    C0243_CIRCULATION_PUMP_DELTA: Final = "calculations.Unknown_Calculation_243"
    # 243: Kelvin("HUP_Temp_Spread_Ist"), / 10, measurement, delta - ait_hup_delta
    # 254 Flow Rate
    C0257_CURRENT_HEAT_OUTPUT: Final = "calculations.Heat_Output"
    # 258 RBE Version
    C0268_CURRENT_POWER_CONSUMPTION: Final = "calculations.Unknown_Calculation_268"


# endregion Lux calculations


# region visibilities
class LuxVisibility(StrEnum):
    """Luxtronik visibility ids."""

    UNSET: Final = "UNSET"
    V0005_COOLING: Final = "visibilities.ID_Visi_Kuhlung"
    V0007_MK1: Final = "visibilities.ID_Visi_MK1"
    V0008_MK2: Final = "visibilities.ID_Visi_MK2"
    V0009_MK3: Final = "visibilities.ID_Visi_MK3"
    V0023_FLOW_IN_TEMPERATURE: Final = "visibilities.ID_Visi_Temp_Vorlauf"
    V0024_FLOW_OUT_TEMPERATURE_EXTERNAL: Final = "visibilities.ID_Visi_Temp_Rucklauf"
    V0027_HOT_GAS_TEMPERATURE: Final = "visibilities.ID_Visi_Temp_Heissgas"
    V0029_DHW_TEMPERATURE: Final = "visibilities.ID_Visi_Temp_BW_Ist"
    V0038_SOLAR_COLLECTOR: Final = "visibilities.ID_Visi_Temp_Solarkoll"
    V0039_SOLAR_BUFFER: Final = "visibilities.ID_Visi_Temp_Solarsp"
    V0041_DEFROST_END_FLOW_OKAY: Final = "visibilities.ID_Visi_IN_ASD"
    V0043_EVU_IN: Final = "visibilities.ID_Visi_IN_EVU"
    V0045_MOTOR_PROTECTION: Final = "visibilities.ID_Visi_IN_MOT"
    V0049_DEFROST_VALVE: Final = "visibilities.ID_Visi_OUT_Abtauventil"
    V0050_DHW_RECIRCULATION_PUMP: Final = "visibilities.ID_Visi_OUT_BUP"
    V0052_CIRCULATION_PUMP_HEATING: Final = "visibilities.ID_Visi_OUT_HUP"
    V0059_DHW_CIRCULATION_PUMP: Final = "visibilities.ID_Visi_OUT_ZIP"
    V0059A_DHW_CHARGING_PUMP: Final = "V0059A_DHW_CHARGING_PUMP"
    V0060_ADDITIONAL_CIRCULATION_PUMP: Final = "visibilities.ID_Visi_OUT_ZUP"
    V0061_SECOND_HEAT_GENERATOR: Final = "visibilities.ID_Visi_OUT_ZWE1"
    V0080_COMPRESSOR1_OPERATION_HOURS: Final = "visibilities.ID_Visi_Bst_BStdVD1"
    V0081_COMPRESSOR1_IMPULSES: Final = "visibilities.ID_Visi_Bst_ImpVD1"
    V0083_COMPRESSOR2_OPERATION_HOURS: Final = "visibilities.ID_Visi_Bst_BStdVD2"
    V0084_COMPRESSOR2_IMPULSES: Final = "visibilities.ID_Visi_Bst_ImpVD2"
    V0086_ADDITIONAL_HEAT_GENERATOR_OPERATION_HOURS: Final = (
        "visibilities.ID_Visi_Bst_BStdZWE1"
    )
    V0087_ADDITIONAL_HEAT_GENERATOR2_OPERATION_HOURS: Final = (
        "visibilities.ID_Visi_Bst_BStdZWE2"
    )
    V0105_HEAT_SOURCE_INPUT_TEMPERATURE_MIN: Final = "visibilities.ID_Visi_EinstTemp_TWQmin"
    V0121_EVU_LOCKED: Final = "visibilities.ID_Visi_SysEin_EVUSperre"
    V0122_ROOM_THERMOSTAT: Final = "visibilities.ID_Visi_SysEin_Raumstation"
    V0144_PUMP_OPTIMIZATION: Final = "visibilities.ID_Visi_SysEin_Pumpenoptim"
    V0163_PUMP_VENT_HUP: Final = "visibilities.ID_Visi_Enlt_HUP"
    V0175_PUMP_VENT_TIMER_H: Final = "visibilities.ID_Visi_Enlt_Laufzeit"
    V0211_MK3: Final = "visibilities.ID_Visi_MK3"
    V0239_EFFICIENCY_PUMP_NOMINAL: Final = (
        "visibilities.ID_Visi_SysEin_EffizienzpumpeNom"
    )
    V0240_EFFICIENCY_PUMP_MINIMAL: Final = (
        "visibilities.ID_Visi_SysEin_EffizienzpumpeMin"
    )
    V0248_ANALOG_OUT1: Final = "visibilities.ID_Visi_OUT_Analog_1"
    V0249_ANALOG_OUT2: Final = "visibilities.ID_Visi_OUT_Analog_2"
    V0250_SOLAR: Final = "visibilities.ID_Visi_Solar"
    V0289_SUCTION_COMPRESSOR_TEMPERATURE: Final = (
        "visibilities.ID_Visi_LIN_ANSAUG_VERDICHTER"
    )
    V0290_COMPRESSOR_HEATING: Final = "visibilities.ID_Visi_LIN_VDH"
    V0291_OVERHEATING_TEMPERATURE: Final = "visibilities.ID_Visi_LIN_UH"
    V0292_LIN_PRESSURE: Final = "visibilities.ID_Visi_LIN_Druck"
    V0310_SUCTION_EVAPORATOR_TEMPERATURE: Final = (
        "visibilities.ID_Visi_LIN_ANSAUG_VERDAMPFER"
    )
    V0324_ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER: Final = (
        "visibilities.ID_Visi_Waermemenge_ZWE"
    )
    V0357_ELECTRICAL_POWER_LIMITATION_SWITCH: Final = "visibilities.Unknown_Parameter_357"


# endregion visibilities


# region Keys
class SensorKey(StrEnum):
    """Sensor keys."""

    STATUS = "status"
    STATUS_TIME = "status_time"
    STATUS_LINE_1 = "status_line_1"
    STATUS_LINE_2 = "status_line_2"
    STATUS_LINE_3 = "status_line_3"
    HEAT_SOURCE_INPUT_TEMPERATURE = "heat_source_input_temperature"
    HEAT_SOURCE_INPUT_TEMPERATURE_MIN = "heat_source_input_temperature_min"
    OUTDOOR_TEMPERATURE = "outdoor_temperature"
    OUTDOOR_TEMPERATURE_AVERAGE = "outdoor_temperature_average"
    COMPRESSOR1_IMPULSES = "compressor1_impulses"
    COMPRESSOR1_OPERATION_HOURS = "compressor1_operation_hours"
    COMPRESSOR2_IMPULSES = "compressor2_impulses"
    COMPRESSOR2_OPERATION_HOURS = "compressor2_operation_hours"
    OPERATION_HOURS = "operation_hours"
    HEAT_AMOUNT_COUNTER = "heat_amount_counter"
    HOT_GAS_TEMPERATURE = "hot_gas_temperature"
    SUCTION_COMPRESSOR_TEMPERATURE = "suction_compressor_temperature"
    SUCTION_EVAPORATOR_TEMPERATURE = "suction_evaporator_temperature"
    COMPRESSOR_HEATING_TEMPERATURE = "compressor_heating_temperature"
    OVERHEATING_TEMPERATURE = "overheating_temperature"
    OVERHEATING_TARGET_TEMPERATURE = "overheating_target_temperature"
    HIGH_PRESSURE = "high_pressure"
    LOW_PRESSURE = "low_pressure"
    ADDITIONAL_HEAT_GENERATOR_OPERATION_HOURS = (
        "additional_heat_generator_operation_hours"
    )
    ADDITIONAL_HEAT_GENERATOR2_OPERATION_HOURS = (
        "additional_heat_generator2_operation_hours"
    )
    ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER = (
        "additional_heat_generator_amount_counter"
    )
    SECOND_HEAT_GENERATOR_AMOUNT_COUNTER = "second_heat_generator_amount_counter"
    ANALOG_OUT1 = "analog_out1"
    ANALOG_OUT2 = "analog_out2"
    CURRENT_HEAT_OUTPUT = "current_heat_output"
    CURRENT_POWER_CONSUMPTION = "current_power_consumption"
    PUMP_FREQUENCY = "pump_frequency"
    PUMP_FLOW_DELTA_TARGET = "pump_flow_delta_target"
    PUMP_FLOW_DELTA = "pump_flow_delta"
    CIRCULATION_PUMP_DELTA_TARGET = "circulation_pump_delta_target"
    CIRCULATION_PUMP_DELTA = "circulation_pump_delta"
    HEAT_SOURCE_OUTPUT_TEMPERATURE = "heat_source_output_temperature"
    ERROR_REASON = "error_reason"
    FLOW_IN_TEMPERATURE = "flow_in_temperature"
    FLOW_IN_CIRCUIT1_TEMPERATURE = "flow_in_circuit1_temperature"
    FLOW_IN_CIRCUIT2_TEMPERATURE = "flow_in_circuit2_temperature"
    FLOW_IN_CIRCUIT3_TEMPERATURE = "flow_in_circuit3_temperature"
    FLOW_IN_CIRCUIT1_TARGET_TEMPERATURE = "flow_in_circuit1_target_temperature"
    FLOW_IN_CIRCUIT2_TARGET_TEMPERATURE = "flow_in_circuit2_target_temperature"
    FLOW_IN_CIRCUIT3_TARGET_TEMPERATURE = "flow_in_circuit3_target_temperature"
    FLOW_OUT_TEMPERATURE = "flow_out_temperature"
    FLOW_OUT_TEMPERATURE_TARGET = "flow_out_temperature_target"
    FLOW_OUT_TEMPERATURE_EXTERNAL = "flow_out_temperature_external"
    OPERATION_HOURS_HEATING = "operation_hours_heating"
    OPERATION_HOURS_COOLING = "operation_hours_cooling"
    HEAT_AMOUNT_HEATING = "heat_amount_heating"
    HEAT_AMOUNT_FLOW_RATE = "heat_amount_flow_rate"
    HEAT_SOURCE_FLOW_RATE = "heat_source_flow_rate"
    DHW_HEAT_AMOUNT = "dhw_heat_amount"
    HEAT_ENERGY_INPUT = "heat_energy_input"
    DHW_ENERGY_INPUT = "dhw_energy_input"
    COOLING_ENERGY_INPUT = "cooling_energy_input"
    DHW_TEMPERATURE = "dhw_temperature"
    SOLAR_COLLECTOR_TEMPERATURE = "solar_collector_temperature"
    SOLAR_BUFFER_TEMPERATURE = "solar_buffer_temperature"
    OPERATION_HOURS_SOLAR = "operation_hours_solar"
    DHW_OPERATION_HOURS = "dhw_operation_hours"
    REMOTE_MAINTENANCE = "remote_maintenance"
    EFFICIENCY_PUMP = "efficiency_pump"
    EFFICIENCY_PUMP_NOMINAL = "efficiency_pump_nominal"
    EFFICIENCY_PUMP_MINIMAL = "efficiency_pump_minimal"
    ELECTRICAL_POWER_LIMITATION_SWITCH = "electrical_power_limitation_switch"
    ELECTRICAL_POWER_LIMITATION_VALUE = "electrical_power_limitation_value"
    PUMP_HEAT_CONTROL = "pump_heat_control"
    HEATING = "heating"
    PUMP_OPTIMIZATION = "pump_optimization"
    HEATING_THRESHOLD = "heating_threshold"
    DOMESTIC_WATER = "domestic_water"
    COOLING = "cooling"
    RELEASE_SECOND_HEAT_GENERATOR = "release_second_heat_generator"
    RELEASE_TIME_SECOND_HEAT_GENERATOR = "release_time_second_heat_generator"
    HEATING_TARGET_CORRECTION = "heating_target_correction"
    PUMP_OPTIMIZATION_TIME = "pump_optimization_time"
    HEATING_THRESHOLD_TEMPERATURE = "heating_threshold_temperature"
    HEATING_MIN_FLOW_OUT_TEMPERATURE = "heating_min_flow_out_temperature"
    HEATING_CURVE_END_TEMPERATURE = "heating_curve_end_temperature"
    HEATING_CURVE_PARALLEL_SHIFT_TEMPERATURE = "heating_curve_parallel_shift_temperature"
    HEATING_CURVE_NIGHT_TEMPERATURE = "heating_curve_night_temperature"
    HEATING_CURVE_CIRCUIT1_END_TEMPERATURE = "heating_curve_circuit1_end_temperature"
    HEATING_CURVE_CIRCUIT1_PARALLEL_SHIFT_TEMPERATURE = "heating_curve_circuit1_parallel_shift_temperature"
    HEATING_CURVE_CIRCUIT1_NIGHT_TEMPERATURE = (
        "heating_curve_circuit1_night_temperature"
    )
    HEATING_CURVE_CIRCUIT2_END_TEMPERATURE = "heating_curve_circuit2_end_temperature"
    HEATING_CURVE_CIRCUIT2_PARALLEL_SHIFT_TEMPERATURE = "heating_curve_circuit2_parallel_shift_temperature"
    HEATING_CURVE_CIRCUIT2_NIGHT_TEMPERATURE = (
        "heating_curve_circuit2_night_temperature"
    )
    HEATING_CURVE_CIRCUIT3_END_TEMPERATURE = "heating_curve_circuit3_end_temperature"
    HEATING_CURVE_CIRCUIT3_PARALLEL_SHIFT_TEMPERATURE = "heating_curve_circuit3_parallel_shift_temperature"
    HEATING_CURVE_CIRCUIT3_NIGHT_TEMPERATURE = (
        "heating_curve_circuit3_night_temperature"
    )
    HEATING_NIGHT_LOWERING_TO_TEMPERATURE = "heating_night_lowering_to_temperature"
    HEATING_HYSTERESIS = "heating_hysteresis"
    HEATING_MAX_FLOW_OUT_INCREASE_TEMPERATURE = (
        "heating_max_flow_out_increase_temperature"
    )
    HEATING_MAXIMUM_CIRCULATION_PUMP_SPEED = "heating_maximum_circulation_pump_speed"
    HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR = "heating_room_temperature_impact_factor"
    DHW_TARGET_TEMPERATURE = "dhw_target_temperature"
    DHW_HYSTERESIS = "dhw_hysteresis"
    DHW_THERMAL_DESINFECTION_TARGET = "dhw_thermal_desinfection_target"
    SOLAR_PUMP_ON_DIFFERENCE_TEMPERATURE = "solar_pump_on_difference_temperature"
    SOLAR_PUMP_OFF_DIFFERENCE_TEMPERATURE = "solar_pump_off_difference_temperature"
    SOLAR_PUMP_OFF_MAX_DIFFERENCE_TEMPERATURE_BOILER = (
        "solar_pump_off_max_difference_temperature_boiler"
    )
    SOLAR_PUMP_MAX_TEMPERATURE_COLLECTOR = "solar_pump_max_temperature_collector"
    EVU_UNLOCKED = "evu_unlocked"
    COMPRESSOR = "compressor"
    COMPRESSOR2 = "compressor2"
    PUMP_FLOW = "pump_flow"
    CIRCULATION_PUMP_HEATING = "circulation_pump_heating"
    ADDITIONAL_CIRCULATION_PUMP = "additional_circulation_pump"
    DHW_RECIRCULATION_PUMP = "dhw_recirculation_pump"
    DHW_CIRCULATION_PUMP = "dhw_circulation_pump"
    DHW_CHARGING_PUMP = "dhw_charging_pump"
    SOLAR_PUMP = "solar_pump"
    COMPRESSOR_HEATER = "compressor_heater"
    DEFROST_VALVE = "defrost_valve"
    ADDITIONAL_HEAT_GENERATOR = "additional_heat_generator"
    DISTURBANCE_OUTPUT = "disturbance_output"
    DEFROST_END_FLOW_OKAY = "defrost_end_flow_okay"
    MOTOR_PROTECTION = "motor_protection"
    FIRMWARE = "firmware"
    APPROVAL_COOLING = "approval_cooling"
    ROOM_THERMOSTAT_TEMPERATURE = "room_thermostat_temperature"
    ROOM_THERMOSTAT_TEMPERATURE_TARGET = "room_thermostat_temperature_target"
    COOLING_START_DELAY_HOURS = "cooling_start_delay_hours"
    COOLING_STOP_DELAY_HOURS = "cooling_stop_delay_hours"
    COOLING_OUTDOOR_TEMP_THRESHOLD = "cooling_threshold_temperature"
    COOLING_TARGET_TEMPERATURE_MK1 = "cooling_target_temperature_mk1"
    COOLING_TARGET_TEMPERATURE_MK2 = "cooling_target_temperature_mk2"
    COOLING_TARGET_TEMPERATURE_MK3 = "cooling_target_temperature_mk3"
    SMART_GRID_SWITCH = "smartgrid"
    SWITCHOFF_REASON = "switchoff_reason"
    SILENT_MODE = "silent_mode"
    PUMP_VENT_HUP = "pump_vent_hup"
    PUMP_VENT_TIMER_H = "pump_vent_timer_h"
    PUMP_VENT_ACTIVE = "pump_vent_active"


# endregion Keys


# region Attr Keys
class SensorAttrFormat(Enum):
    """Luxtronik sensor attribute format."""

    HOUR_MINUTE = 1
    CELSIUS_TENTH = 2
    SWITCH_GAP = 3
    TIMESTAMP_LAST_OVER = 4


class SensorAttrKey(StrEnum):
    """Luxtronik sensor attribute keys."""

    LUXTRONIK_KEY = "Luxtronik_Key"

    STATUS_TEXT = "status_text"
    LAST_THERMAL_DESINFECTION = "last_thermal_desinfection"
    SWITCH_GAP = "switch_gap"
    STATUS_RAW = "status_raw"
    EVU_FIRST_START_TIME = "EVU_first_start_time"
    EVU_FIRST_END_TIME = "EVU_first_end_time"
    EVU_SECOND_START_TIME = "EVU_second_start_time"
    EVU_SECOND_END_TIME = "EVU_second_end_time"
    EVU_MINUTES_UNTIL_NEXT_EVENT = "EVU_minutes_until_next_event"
    EVU_DAYS = "EVU_days"
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


# endregion Attr Keys

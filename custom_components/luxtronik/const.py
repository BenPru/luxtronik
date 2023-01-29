"""Constants for the Luxtronik heatpump integration."""
# region Imports
from datetime import timedelta
from enum import Enum
import logging
from typing import Final

from homeassistant.backports.enum import StrEnum
from homeassistant.const import Platform

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

SECOUND_TO_HOUR_FACTOR: Final = 0.000277777777778
# endregion Constants Main

# region Conf
CONF_COORDINATOR: Final = "coordinator"

CONF_PARAMETERS: Final = "parameters"
CONF_CALCULATIONS: Final = "calculations"
CONF_VISIBILITIES: Final = "visibilities"

CONF_HA_SENSOR_PREFIX: Final = "ha_sensor_prefix"
CONF_CONTROL_MODE_HOME_ASSISTANT: Final = "control_mode_home_assistant"
CONF_HA_SENSOR_INDOOR_TEMPERATURE: Final = "ha_sensor_indoor_temperature"

CONF_LOCK_TIMEOUT: Final = "lock_timeout"
CONF_SAFE: Final = "safe"

DEFAULT_HOST: Final = "wp-novelan"
DEFAULT_PORT: Final = 8889
# endregion Conf

# region Lux Definitions


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
# endregion Constants Main

# region Conf
LANG_EN: Final = "en"
LANG_DE: Final = "de"
LANG_DEFAULT: Final = LANG_EN
LANGUAGES: Final = Enum("en", "de")
LANGUAGES_SENSOR_NAMES: Final = [LANG_EN, LANG_DE]


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


class LuxMkTypes(Enum):
    """LuxMkTypes etc."""

    off: Final = 0
    discharge: Final = 1
    load: Final = 2
    cooling: Final = 3
    heating_cooling: Final = 4


LUX_PARAMETER_MK_SENSORS: Final = [
    "parameters.ID_Einst_MK1Typ_akt",
    "parameters.ID_Einst_MK2Typ_akt",
    "parameters.ID_Einst_MK3Typ_akt",
]

class LuxRoomThermostatType(Enum):
    """LuxMkTypes etc."""

    none: Final = 0
    # TODO: Validate types:
    # RFV: Final = 1
    # RFV_K: Final = 2
    # RFV_DK: Final = 3
    # RBE: Final = 4
    # Smart: Final = 5



LUX_STATE_ICON_MAP: Final[dict[str, str]] = {
    LuxOperationMode.heating.value: "mdi:radiator",
    LuxOperationMode.domestic_water.value: "mdi:waves",
    LuxOperationMode.swimming_pool_solar.value: "mdi:pool",
    LuxOperationMode.evu.value: "mdi:power-plug-off",
    LuxOperationMode.defrost.value: "mdi:car-defrost-rear",
    LuxOperationMode.no_request.value: "mdi:heat-pump-outline",  # "mdi:radiator-disabled",
    LuxOperationMode.heating_external_source.value: "mdi:patio-heater",
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
    P0002_DOMESTIC_WATER_TARGET_TEMPERATURE: Final = "parameters.ID_Einst_BWS_akt"
    P0003_MODE_HEATING: Final = "parameters.ID_Ba_Hz_akt"
    P0004_MODE_DOMESTIC_WATER: Final = "parameters.ID_Ba_Bw_akt"
    P0011_HEATING_CIRCUIT_CURVE1_TEMPERATURE: Final = "parameters.ID_Einst_HzHwHKE_akt"
    P0012_HEATING_CIRCUIT_CURVE2_TEMPERATURE: Final = "parameters.ID_Einst_HzHKRANH_akt"
    P0013_HEATING_CIRCUIT_CURVE_NIGHT_TEMPERATURE: Final = (
        "parameters.ID_Einst_HzHKRABS_akt"
    )
    P0047_DOMESTIC_WATER_THERMAL_DESINFECTION_TARGET: Final = (
        "parameters.ID_Einst_LGST_akt"
    )
    P0049_PUMP_OPTIMIZATION: Final = "parameters.ID_Einst_Popt_akt"
    P0033_ROOM_THERMOSTAT_TYPE: Final = "parameters.ID_Einst_RFVEinb_akt"
    P0074_DOMESTIC_WATER_HYSTERESIS: Final = "parameters.ID_Einst_BWS_Hyst_akt"
    P0085_DOMESTIC_WATER_CHARGING_PUMP: Final = "parameters.ID_Einst_BWZIP_akt"
    P0088_HEATING_HYSTERESIS: Final = "parameters.ID_Einst_HRHyst_akt"
    P0089_HEATING_MAX_FLOW_OUT_INCREASE_TEMPERATURE: Final = (
        "parameters.ID_Einst_TRErhmax_akt"
    )
    P0090_RELEASE_SECOND_HEAT_GENERATOR: Final = "parameters.ID_Einst_ZWEFreig_akt"
    # MODE_COOLING: Automatic or Off
    P0108_MODE_COOLING: Final = "parameters.ID_Einst_BA_Kuehl_akt"
    P0111_HEATING_NIGHT_LOWERING_TO_TEMPERATURE: Final = (
        "parameters.ID_Einst_TAbsMin_akt"
    )
    P0122_SOLAR_PUMP_ON_DIFFERENCE_TEMPERATURE: Final = (
        "parameters.ID_Einst_TDC_Ein_akt"
    )
    P0123_SOLAR_PUMP_OFF_DIFFERENCE_TEMPERATURE: Final = (
        "parameters.ID_Einst_TDC_Aus_akt"
    )
    P0149_FLOW_IN_TEMPERATURE_MAX_ALLOWED: Final = "parameters.ID_Einst_TVLmax_akt"
    P0289_SOLAR_PUMP_OFF_MAX_DIFFERENCE_TEMPERATURE_BOILER: Final = (
        "parameters.ID_Einst_TDC_Max_akt"
    )
    P0699_HEATING_THRESHOLD: Final = "parameters.ID_Einst_Heizgrenze"
    P0700_HEATING_THRESHOLD_TEMPERATURE: Final = "parameters.ID_Einst_Heizgrenze_Temp"
    P0860_REMOTE_MAINTENANCE: Final = "parameters.ID_Einst_Fernwartung_akt"
    P0864_PUMP_OPTIMIZATION_TIME: Final = "parameters.ID_Einst_Popt_Nachlauf_akt"
    P0869_EFFICIENCY_PUMP: Final = "parameters.ID_Einst_Effizienzpumpe_akt"
    P0870_AMOUNT_COUNTER_ACTIVE: Final = "parameters.ID_Einst_Waermemenge_akt"
    P0874_SERIAL_NUMBER: Final = "parameters.ID_WP_SerienNummer_DATUM"
    P0875_SERIAL_NUMBER_MODEL: Final = "parameters.ID_WP_SerienNummer_HEX"
    P0882_SOLAR_OPERATION_HOURS: Final = "parameters.ID_BSTD_Solar"
    P0883_SOLAR_PUMP_MAX_TEMPERATURE_COLLECTOR: Final = (
        "parameters.ID_Einst_TDC_Koll_Max_akt"
    )
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
    P1033_PUMP_HEAT_CONTROL: Final = "parameters.ID_Einst_P155_PumpHeatCtrl"
    P1059_ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER: Final = (
        "parameters.ID_Waermemenge_ZWE"
    )
    P1136_HEAT_ENERGY_INPUT: Final = "parameters.Unknown_Parameter_1136"
    P1137_DOMESTIC_WATER_ENERGY_INPUT: Final = "parameters.Unknown_Parameter_1137"


# endregion Lux parameters

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
    C0017_DOMESTIC_WATER_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TBW"
    C0020_HEAT_SOURCE_OUTPUT_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TWA"
    C0026_SOLAR_COLLECTOR_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TSK"
    C0027_SOLAR_BUFFER_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TSS"
    C0031_EVU_UNLOCKED: Final = "calculations.ID_WEB_EVUin"
    C0037_DEFROST_VALVE: Final = "calculations.ID_WEB_AVout"
    C0038_DOMESTIC_WATER_RECIRCULATION_PUMP: Final = "calculations.ID_WEB_BUPout"
    C0039_CIRCULATION_PUMP_HEATING: Final = "calculations.ID_WEB_HUPout"
    C0043_PUMP_FLOW: Final = "calculations.ID_WEB_VBOout"
    C0044_COMPRESSOR: Final = "calculations.ID_WEB_VD1out"
    C0046_DOMESTIC_WATER_CIRCULATION_PUMP: Final = "calculations.ID_WEB_ZIPout"
    C0047_ADDITIONAL_CIRCULATION_PUMP: Final = "calculations.ID_WEB_ZUPout"
    C0048_ADDITIONAL_HEAT_GENERATOR: Final = "calculations.ID_WEB_ZW1out"
    C0049_DISTURBANCE_OUTPUT: Final = "calculations.ID_WEB_ZW2SSTout"
    C0052_SOLAR_PUMP: Final = "calculations.ID_WEB_SLPout"
    C0056_COMPRESSOR1_OPERATION_HOURS: Final = "calculations.ID_WEB_Zaehler_BetrZeitVD1"
    C0057_COMPRESSOR1_IMPULSES: Final = "calculations.ID_WEB_Zaehler_BetrZeitImpVD1"
    C0058_COMPRESSOR2_OPERATION_HOURS: Final = "calculations.ID_WEB_Zaehler_BetrZeitVD2"
    C0059_COMPRESSOR2_IMPULSES: Final = "calculations.ID_WEB_Zaehler_BetrZeitImpVD2"
    C0060_ADDITIONAL_HEAT_GENERATOR_OPERATION_HOURS: Final = (
        "calculations.ID_WEB_Zaehler_BetrZeitZWE1"
    )
    C0063_OPERATION_HOURS: Final = "calculations.ID_WEB_Zaehler_BetrZeitWP"
    C0064_OPERATION_HOURS_HEATING: Final = "calculations.ID_WEB_Zaehler_BetrZeitHz"
    C0065_DOMESTIC_WATER_OPERATION_HOURS: Final = (
        "calculations.ID_WEB_Zaehler_BetrZeitBW"
    )
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
    C0077_TIMER_BLOCK_DOMESTIC_WATER: Final = "calculations.ID_WEB_Time_SBW_akt"
    C0078_MODEL_CODE: Final = "calculations.ID_WEB_Code_WP_akt"
    C0080_STATUS: Final = "calculations.ID_WEB_WP_BZ_akt"
    C0081_FIRMWARE_VERSION: Final = "calculations.ID_WEB_SoftStand"
    C0117_STATUS_LINE_1: Final = "calculations.ID_WEB_HauptMenuStatus_Zeile1"
    C0118_STATUS_LINE_2: Final = "calculations.ID_WEB_HauptMenuStatus_Zeile2"
    C0119_STATUS_LINE_3: Final = "calculations.ID_WEB_HauptMenuStatus_Zeile3"
    C0120_STATUS_TIME: Final = "calculations.ID_WEB_HauptMenuStatus_Zeit"
    C0141_TIMER_DEFROST: Final = "calculations.ID_WEB_Time_AbtIn"
    C0146_APPROVAL_COOLING: Final = "calculations.ID_WEB_FreigabKuehl"
    C0151_HEAT_AMOUNT_HEATING: Final = "calculations.ID_WEB_WMZ_Heizung"
    C0152_HEAT_AMOUNT_DOMESTIC_WATER: Final = "calculations.ID_WEB_WMZ_Brauchwasser"
    C0154_HEAT_AMOUNT_COUNTER: Final = "calculations.ID_WEB_WMZ_Seit"
    C0156_ANALOG_OUT1: Final = "calculations.ID_WEB_AnalogOut1"
    C0157_ANALOG_OUT2: Final = "calculations.ID_WEB_AnalogOut2"
    C0158_TIMER_HOT_GAS: Final = "calculations.ID_WEB_Time_Heissgas"
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
    C0204_HEAT_SOURCE_INPUT_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TWE"
    C0227_ROOM_THERMOSTAT_TEMPERATURE: Final = "calculations.ID_WEB_RBE_RT_Ist"
    C0228_ROOM_THERMOSTAT_TEMPERATURE_TARGET: Final = "calculations.ID_WEB_RBE_RT_Soll"
    C0231_PUMP_FREQUENCY: Final = "calculations.ID_WEB_Freq_VD"
    C0257_CURRENT_HEAT_OUTPUT: Final = "calculations.Heat_Output"


# endregion Lux calculations

# region visibilities
class LuxVisibility(StrEnum):
    """Luxtronik visibility ids."""

    UNSET: Final = "UNSET"
    V0023_FLOW_IN_TEMPERATURE: Final = "visibilities.ID_Visi_Temp_Vorlauf"
    V0024_FLOW_OUT_TEMPERATURE_EXTERNAL: Final = "visibilities.ID_Visi_Temp_Rucklauf"
    V0027_HOT_GAS_TEMPERATURE: Final = "visibilities.ID_Visi_Temp_Heissgas"
    V0029_DOMESTIC_WATER_TEMPERATURE: Final = "visibilities.ID_Visi_Temp_BW_Ist"
    V0038_SOLAR_COLLECTOR: Final = "visibilities.ID_Visi_Temp_Solarkoll"
    V0039_SOLAR_BUFFER: Final = "visibilities.ID_Visi_Temp_Solarsp"
    V0043_EVU_IN: Final = "visibilities.ID_Visi_IN_EVU"
    V0049_DEFROST_VALVE: Final = "visibilities.ID_Visi_OUT_Abtauventil"
    V0050_DOMESTIC_WATER_RECIRCULATION_PUMP: Final = "visibilities.ID_Visi_OUT_BUP"
    V0052_CIRCULATION_PUMP_HEATING: Final = "visibilities.ID_Visi_OUT_HUP"
    V0059_DOMESTIC_WATER_CIRCULATION_PUMP: Final = "visibilities.ID_Visi_OUT_ZIP"
    V0059A_DOMESTIC_WATER_CHARGING_PUMP: Final = "v0059a_domestic_water_charging_pump"
    V0060_ADDITIONAL_CIRCULATION_PUMP: Final = "visibilities.ID_Visi_OUT_ZUP"
    V0061_SECOND_HEAT_GENERATOR: Final = "visibilities.ID_Visi_OUT_ZWE1"
    V0080_COMPRESSOR1_OPERATION_HOURS: Final = "visibilities.ID_Visi_Bst_BStdVD1"
    V0081_COMPRESSOR1_IMPULSES: Final = "visibilities.ID_Visi_Bst_ImpVD1"
    V0083_COMPRESSOR2_OPERATION_HOURS: Final = "visibilities.ID_Visi_Bst_BStdVD2"
    V0084_COMPRESSOR2_IMPULSES: Final = "visibilities.ID_Visi_Bst_ImpVD2"
    V0086_ADDITIONAL_HEAT_GENERATOR_OPERATION_HOURS: Final = (
        "visibilities.ID_Visi_Bst_BStdZWE1"
    )
    V0121_EVU_LOCKED: Final = "visibilities.ID_Visi_SysEin_EVUSperre"
    V0122_ROOM_THERMOSTAT: Final = "visibilities.ID_Visi_SysEin_Raumstation"
    V0144_PUMP_OPTIMIZATION: Final = "visibilities.ID_Visi_SysEin_Pumpenoptim"
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
    ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER = (
        "additional_heat_generator_amount_counter"
    )
    ANALOG_OUT1 = "analog_out1"
    ANALOG_OUT2 = "analog_out2"
    CURRENT_HEAT_OUTPUT = "current_heat_output"
    PUMP_FREQUENCY = "pump_frequency"
    HEAT_SOURCE_OUTPUT_TEMPERATURE = "heat_source_output_temperature"
    FLOW_IN_TEMPERATURE = "flow_in_temperature"
    FLOW_OUT_TEMPERATURE = "flow_out_temperature"
    FLOW_OUT_TEMPERATURE_TARGET = "flow_out_temperature_target"
    FLOW_OUT_TEMPERATURE_EXTERNAL = "flow_out_temperature_external"
    OPERATION_HOURS_HEATING = "operation_hours_heating"
    OPERATION_HOURS_COOLING = "operation_hours_cooling"
    HEAT_AMOUNT_HEATING = "heat_amount_heating"
    HEAT_AMOUNT_DOMESTIC_WATER = "heat_amount_domestic_water"
    HEAT_ENERGY_INPUT = "heat_energy_input"
    DOMESTIC_WATER_ENERGY_INPUT = "domestic_water_energy_input"
    DOMESTIC_WATER_TEMPERATURE = "domestic_water_temperature"
    SOLAR_COLLECTOR_TEMPERATURE = "solar_collector_temperature"
    SOLAR_BUFFER_TEMPERATURE = "solar_buffer_temperature"
    OPERATION_HOURS_SOLAR = "operation_hours_solar"
    OPERATION_HOURS_DOMESTIC_WATER = "operation_hours_domestic_water"
    REMOTE_MAINTENANCE = "remote_maintenance"
    EFFICIENCY_PUMP = "efficiency_pump"
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
    HEATING_CIRCUIT_CURVE1_TEMPERATURE = "heating_circuit_curve1_temperature"
    HEATING_CIRCUIT_CURVE2_TEMPERATURE = "heating_circuit_curve2_temperature"
    HEATING_CIRCUIT_CURVE_NIGHT_TEMPERATURE = "heating_circuit_curve_night_temperature"
    HEATING_NIGHT_LOWERING_TO_TEMPERATURE = "heating_night_lowering_to_temperature"
    HEATING_HYSTERESIS = "heating_hysteresis"
    HEATING_MAX_FLOW_OUT_INCREASE_TEMPERATURE = (
        "heating_max_flow_out_increase_temperature"
    )
    HEATING_MAXIMUM_CIRCULATION_PUMP_SPEED = "heating_maximum_circulation_pump_speed"
    HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR = "heating_room_temperature_impact_factor"
    DOMESTIC_WATER_TARGET_TEMPERATURE = "domestic_water_target_temperature"
    DOMESTIC_WATER_HYSTERESIS = "domestic_water_hysteresis"
    DOMESTIC_WATER_THERMAL_DESINFECTION_TARGET = (
        "domestic_water_thermal_desinfection_target"
    )
    SOLAR_PUMP_ON_DIFFERENCE_TEMPERATURE = "solar_pump_on_difference_temperature"
    SOLAR_PUMP_OFF_DIFFERENCE_TEMPERATURE = "solar_pump_off_difference_temperature"
    SOLAR_PUMP_OFF_MAX_DIFFERENCE_TEMPERATURE_BOILER = (
        "solar_pump_off_max_difference_temperature_boiler"
    )
    SOLAR_PUMP_MAX_TEMPERATURE_COLLECTOR = "solar_pump_max_temperature_collector"
    EVU_UNLOCKED = "evu_unlocked"
    COMPRESSOR = "compressor"
    PUMP_FLOW = "pump_flow"
    CIRCULATION_PUMP_HEATING = "circulation_pump_heating"
    ADDITIONAL_CIRCULATION_PUMP = "additional_circulation_pump"
    DOMESTIC_WATER_RECIRCULATION_PUMP = "domestic_water_recirculation_pump"
    DOMESTIC_WATER_CIRCULATION_PUMP = "domestic_water_circulation_pump"
    DOMESTIC_WATER_CHARGING_PUMP = "domestic_water_charging_pump"
    SOLAR_PUMP = "solar_pump"
    COMPRESSOR_HEATER = "compressor_heater"
    DEFROST_VALVE = "defrost_valve"
    ADDITIONAL_HEAT_GENERATOR = "additional_heat_generator"
    DISTURBANCE_OUTPUT = "disturbance_output"
    FIRMWARE = "firmware"
    APPROVAL_COOLING = "approval_cooling"


# endregion Keys

# region Attr Keys
class SensorAttrFormat(Enum):
    """Luxtronik sensor attribute format."""

    HOUR_MINUTE = 1
    CELSIUS_TENTH = 2


class SensorAttrKey(StrEnum):
    """Luxtronik sensor attribute keys."""

    LUXTRONIK_KEY = "Luxtronik_Key"
    LUXTRONIK_KEY_CURRENT_ACTION = "luxtronik_key_current_action"
    LUXTRONIK_KEY_TARGET_TEMPERATURE = "luxtronik_key_target_temperature"
    LUXTRONIK_KEY_CORRECTION_FACTOR = "luxtronik_key_correction_factor"
    LUXTRONIK_KEY_CORRECTION_TARGET = "luxtronik_key_correction_target"
    LUXTRONIK_KEY_CURRENT_TEMPERATURE = "luxtronik_key_current_temperature"
    LUXTRONIK_ACTION_HEATING = "luxtronik_action_heating"
    LUXTRONIK_KEY_TARGET_TEMPERATURE_HIGH = "luxtronik_key_target_temperature_high"
    LUXTRONIK_KEY_TARGET_TEMPERATURE_LOW = "luxtronik_key_target_temperature_low"

    STATUS_TEXT = "status_text"
    LAST_THERMAL_DESINFECTION = ""
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
    TIMER_NET_INPUT_DELAY = "Netzeinschaltverzögerung (ID_WEB_Timer_EinschVerz)"
    TIMER_SCB_OFF = "Schaltspielsperre Aus-Zeit (ID_WEB_Time_SSPAUS_akt)"
    TIMER_SCB_ON = "Schaltspielsperre Ein-Zeit (ID_WEB_Time_SSPEIN_akt)"
    TIMER_COMPRESSOR_OFF = "VD-Stand (ID_WEB_Time_VDStd_akt)"
    TIMER_HC_ADD = "Heizungsregler Mehr-Zeit HRM-Zeit (ID_WEB_Time_HRM_akt)"
    TIMER_HC_LESS = "Heizungsregler Weniger-Zeit HRW-Stand (ID_WEB_Time_HRW_akt)"
    TIMER_TDI = "ID_WEB_Time_LGS_akt"
    TIMER_BLOCK_DOMESTIC_WATER = "Sperre WW? ID_WEB_Time_SBW_akt"
    TIMER_DEFROST = "Abtauen in ID_WEB_Time_AbtIn"
    TIMER_HOT_GAS = "ID_WEB_Time_Heissgas"


# endregion Attr Keys

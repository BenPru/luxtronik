"""Shared fixtures for Luxtronik tests."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
import pytest

from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from custom_components.luxtronik2.model import LuxtronikCoordinatorData

# ---------------------------------------------------------------------------
# Helpers for building fake luxtronik library objects
# ---------------------------------------------------------------------------


class FakeSensorItem:
    """Minimal sensor item returned by the luxtronik library."""

    def __init__(self, name: str, value: Any):
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        return f"FakeSensorItem({self.name!r}, {self.value!r})"


class FakeSensorGroup:
    """Fake Parameters / Calculations / Visibilities container."""

    def __init__(self, data: dict[str, Any] | None = None):
        self._data: dict[str, FakeSensorItem] = {}
        if data:
            for key, value in data.items():
                self._data[key] = FakeSensorItem(key, value)

    def get(self, sensor_id: str) -> FakeSensorItem | None:
        return self._data.get(sensor_id)

    @property
    def parameters(self) -> dict[int, FakeSensorItem]:
        return {i: item for i, (_, item) in enumerate(self._data.items())}

    @property
    def calculations(self) -> dict[int, FakeSensorItem]:
        return self.parameters

    @property
    def visibilities(self) -> dict[int, FakeSensorItem]:
        return self.parameters

    def set(self, parameter: str, value: Any) -> None:
        if parameter in self._data:
            self._data[parameter].value = value
        else:
            self._data[parameter] = FakeSensorItem(parameter, value)

    @property
    def queue(self) -> dict:
        return {}

    @queue.setter
    def queue(self, val: dict) -> None:
        pass


def make_coordinator_data(
    parameters: dict[str, Any] | None = None,
    calculations: dict[str, Any] | None = None,
    visibilities: dict[str, Any] | None = None,
) -> LuxtronikCoordinatorData:
    """Build a LuxtronikCoordinatorData with fake sensor groups."""
    return LuxtronikCoordinatorData(
        parameters=FakeSensorGroup(parameters or {}),
        calculations=FakeSensorGroup(calculations or {}),
        visibilities=FakeSensorGroup(visibilities or {}),
    )


# ---------------------------------------------------------------------------
# Default data that mimics a typical heatpump
# ---------------------------------------------------------------------------

DEFAULT_PARAMETERS = {
    "ID_WP_SerienNummer_DATUM": 20230101,
    "ID_WP_SerienNummer_HEX": 255,
    "ID_Einst_BwTDI_akt_MO": 1,
    "ID_Ba_Hz_akt": "Automatic",
    "ID_Ba_Bw_akt": "Automatic",
    "ID_Einst_BWS_akt": 50.0,
    "ID_Einst_HzMKE1_akt": 0,
    "ID_Einst_HzMKE2_akt": 0,
    "ID_Einst_HzMKE3_akt": 0,
    "ID_Einst_Kuhl_Frei_akt": 0,
    "ID_Sollwert_KuCft1_akt": 20.0,
    "ID_Einst_Heizgrenze_akt": 20.0,
    "ID_Einst_BWS_Hyst_akt": 5.0,
    "ID_Einst_WK_akt": 0.0,
    "ID_Einst_ZWE_FreiAb_akt": 0,
    "ID_Einst_ZWE_FreiAb_Verzög_akt": 0,
    "ID_Einst_P085_0_BW_Ladepumpe": 0,
    "ID_Einst_SolBW_akt": 0,
    "ID_Einst_TDI_Solltemp_akt": 60.0,
    "ID_Einst_Fernwartung_akt": 0,
    "ID_Einst_Effizienzpumpe_akt": 0,
    "ID_Einst_Popt_akt": 0,
    "ID_Einst_P155_PumpHeatCtrl_akt": 0,
    "ID_Einst_Heizgrenze_Sollwert_akt": 1,
    "ID_Soll_BWS_akt": 50.0,
    "ID_Einst_HysHeworkaroundzung_akt": 5.0,
    "ID_Einst_P0088_Heizung_Hysterese": 5.0,
    "ID_Einst_LGST_SmartGrid_akt": 0,
}

DEFAULT_CALCULATIONS = {
    "ID_WEB_Temperatur_TVL": 30.0,
    "ID_WEB_Temperatur_TRL": 25.0,
    "ID_WEB_Temperatur_Sollwert": 28.0,
    "ID_WEB_Temperatur_TA": 15.0,
    "ID_WEB_Temperatur_TBW": 45.0,
    "ID_WEB_Frequenz_VD": 50.0,
    "ID_WEB_RBE_RT_Ist": 21.0,
    "ID_WEB_RBE_RT_Soll": 22.0,
    "ID_WEB_HasError": 0,
    "ID_WEB_WP_BZ_akt": "heating",
    "ID_WEB_SoftStand": "V3.90.1",
    "ID_WEB_Code_WP_akt": 27,
    "ID_WEB_Zaehler_BesijKom": 100,
    "ID_WEB_Zaehler_BetrZeitHz": 200,
    "ID_WEB_Zaehler_BetrZeitBW": 150,
    "ID_WEB_Zaehler_BetrZeitKue": 0,
    "ID_WEB_StatusLine_1": "heatpump_running",
    "ID_WEB_StatusLine_3": "heating",
    "ID_WEB_ERROR_Reason": 0,
    "ID_WEB_Timer_SCB_on": 100,
    "ID_WEB_Timer_SCB_off": 0,
    "ID_WEB_VD_Strom": 0,
    "ID_WEB_ZWE_Aufladepumpe": 0,
    "ID_WEB_Zaehler_BetrSoKue": 0,
    "ID_WEB_Temperatur_TSK": 40.0,
    "ID_WEB_Temperatur_TSS": 35.0,
    "ID_WEB_Temperatur_TFB1": 30.0,
    "ID_WEB_Laufzeit_VD1": 1000,
    "ID_WEB_Laufzeit_ZWE1": 0,
    "ID_WEB_Laufzeit_ZWE2": 0,
    "ID_WEB_Temperatur_TWE": 10.0,
    "ID_WEB_Temperatur_TWA": 8.0,
    "ID_WEB_Durchfluss_WQ": 0.0,
    "ID_WEB_LIN_VDH_Pumpe": False,
    "ID_WEB_EVUin": 0,
    "ID_WEB_HZIO_EVU2": 1,
}

DEFAULT_VISIBILITIES = {
    "ID_Visi_Solar_Kollektor": 0,
    "ID_Visi_Solar_Puffer": 0,
    "ID_Visi_Solar": 0,
    "ID_Visi_Zirkulationspumpe": 1,
    "ID_Visi_Kuhlung": 0,
}


@pytest.fixture
def default_coordinator_data() -> LuxtronikCoordinatorData:
    """Coordinator data with typical heatpump values."""
    return make_coordinator_data(
        parameters=DEFAULT_PARAMETERS.copy(),
        calculations=DEFAULT_CALCULATIONS.copy(),
        visibilities=DEFAULT_VISIBILITIES.copy(),
    )


@pytest.fixture
def mock_config_entry_data() -> dict[str, Any]:
    """Standard config entry data."""
    return {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: DEFAULT_PORT,
        CONF_TIMEOUT: DEFAULT_TIMEOUT,
        CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
        CONF_HA_SENSOR_PREFIX: DOMAIN,
    }

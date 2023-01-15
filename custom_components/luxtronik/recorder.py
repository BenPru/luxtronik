"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from .const import (ATTR_EXTRA_STATE_ATTRIBUTE_LAST_THERMAL_DESINFECTION,
                    ATTR_STATUS_TEXT, DOMAIN)


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude attributes from being recorded in the database."""
    return {
        ATTR_STATUS_TEXT,
        ATTR_EXTRA_STATE_ATTRIBUTE_LAST_THERMAL_DESINFECTION,
        'WP Seit (ID_WEB_Time_WPein_akt)',
        'ZWE1 seit (ID_WEB_Time_ZWE1_akt)',
        'ZWE2 seit (ID_WEB_Time_ZWE2_akt)',
        'Netzeinschaltv. (ID_WEB_Timer_EinschVerz)',
        'Schaltspielsperre SSP-Aus-Zeit (ID_WEB_Time_SSPAUS_akt)',
        'Schaltspielsperre SSP-Ein-Zeit (ID_WEB_Time_SSPEIN_akt)',
        'VD-Stand (ID_WEB_Time_VDStd_akt)',
        'Heizungsregler Mehr-Zeit HRM-Zeit (ID_WEB_Time_HRM_akt)',
        'Heizungsregler Weniger-Zeit HRW-Stand (ID_WEB_Time_HRW_akt)',
        'ID_WEB_Time_LGS_akt',
        'Sperre WW? ID_WEB_Time_SBW_akt',
        'Abtauen in ID_WEB_Time_AbtIn',
        'ID_WEB_Time_Heissgas',
        'switch_gap',
        f"sensor.{DOMAIN}_status_time",
        'status raw',
        'EVU first start time',
        'EVU first end time',
        'EVU second start time',
        'EVU second end time',
        'EVU minutes until next event',
        'timestamp',
        'code',
        'cause',
        'remedy',
        'max_allowed'
    }

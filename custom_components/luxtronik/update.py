"""Luxtronik Update platform."""
# region Imports
from __future__ import annotations

from datetime import datetime, timedelta
import re
import threading
from typing import Final

import requests

from homeassistant.components.update import (
    ENTITY_ID_FORMAT,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .base import LuxtronikEntity
from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    DOWNLOAD_PORTAL_URL,
    FIRMWARE_UPDATE_MANUAL_DE,
    FIRMWARE_UPDATE_MANUAL_EN,
    LANG_DE,
    LOGGER,
    DeviceKey,
    LuxCalculation,
    SensorKey,
)
from .coordinator import LuxtronikCoordinator
from .lux_helper import get_firmware_download_id, get_manufacturer_firmware_url_by_model
from .model import LuxtronikUpdateEntityDescription

# endregion Imports

MIN_TIME_BETWEEN_UPDATES: Final = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Luxtronik update platform."""

    LOGGER.debug("Setting up Luxtronik update entity")
    data: dict = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]
    await coordinator.async_config_entry_first_refresh()

    description = LuxtronikUpdateEntityDescription(
        luxtronik_key=LuxCalculation.C0081_FIRMWARE_VERSION,
        key=SensorKey.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
    )
    update_entity = LuxtronikUpdateEntity(
        entry=config_entry, coordinator=coordinator, description=description
    )
    entities = [update_entity]

    async_add_entities(entities, True)


class LuxtronikUpdateEntity(LuxtronikEntity, UpdateEntity):
    """Representation of Luxtronik."""

    entity_description: LuxtronikUpdateEntityDescription

    _attr_title = "Luxtronik Firmware Version"
    # INSTALL --> is needed to get a notification!!!
    _attr_supported_features: UpdateEntityFeature = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
    )
    __firmware_version_available = None
    __firmware_version_available_last_request = None

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikUpdateEntityDescription,
    ) -> None:
        """Initialize the Luxtronik."""
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=DeviceKey.heatpump,
        )
        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id
        self._request_available_firmware_version()

    @property
    def installed_version(self) -> str | None:
        """Return the current app version."""
        return self._attr_state

    @property
    def latest_version(self) -> str | None:
        """Return if there is an update."""
        if self.__firmware_version_available is None or self.installed_version is None:
            return None
        return self.__firmware_version_available[: len(self.installed_version)]

    def release_notes(self) -> str | None:
        """Build release notes."""
        download_id = get_firmware_download_id(self.installed_version)
        release_url = get_manufacturer_firmware_url_by_model(self.coordinator.model, download_id)
        download_url = f"{DOWNLOAD_PORTAL_URL}{download_id}"
        manual_url = (
            FIRMWARE_UPDATE_MANUAL_DE
            if self.hass.config.language == LANG_DE
            else FIRMWARE_UPDATE_MANUAL_EN
        )
        return (
            f'For your <a href="{release_url}" target="_blank" rel="noreferrer noopener">'
            f"{self.coordinator.manufacturer} {self.coordinator.model} (Download ID {download_id})</a> is "
            f'<a href="{download_url}" target="_blank" rel="noreferrer noopener">Firmware Version {self.__firmware_version_available}</a> available.<br>'
            f'<a href="{manual_url}" target="_blank" rel="noreferrer noopener">Firmware Update Instructions</a><br><br>'
            "The Install-Button downside has no function. It is only needed to notify in Home Assistant.<br><br>"
            "alpha innotec doesn't provide a changelog.<br>Please contact support for more information."
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Update sensor values."""
        if (
            self.__firmware_version_available_last_request is None
            or self.__firmware_version_available_last_request
            < datetime.utcnow().timestamp() - 3600
        ):
            self._request_available_firmware_version()

    def _request_available_firmware_version(self) -> None:
        def do_request_available_firmware_version(self, download_id: int):
            if download_id is None:
                self.__firmware_version_available = STATE_UNAVAILABLE
                return
            try:
                response = requests.get(
                    f"{DOWNLOAD_PORTAL_URL}{download_id}", timeout=30
                )
                header_content_disposition = response.headers["content-disposition"]
                filename = re.findall("filename=(.+)", header_content_disposition)[0]
                self.__firmware_version_available_last_request = (
                    datetime.utcnow().timestamp()
                )
                # Filename e.g.: wp2reg-V2.88.1-9086
                # Extract 'V2.88.1-9086' from 'wp2reg-V2.88.1-9086'. --> Split by -
                #                             'wpreg.V1.88.3-9717'   --> Split by .
                token = '-' if filename.count('-') > 1 else '.'
                self.__firmware_version_available = filename.split(token, 1)[1]
            except Exception:  # pylint: disable=broad-except
                LOGGER.warning(
                    "Could not request download portal firmware version",
                    exc_info=True,
                )
                self.__firmware_version_available = STATE_UNAVAILABLE

        download_id = get_firmware_download_id(self.installed_version)
        if download_id is not None:
            threading.Thread(
                target=do_request_available_firmware_version, args=(self, download_id)
            ).start()

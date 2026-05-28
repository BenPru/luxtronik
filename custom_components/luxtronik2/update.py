"""Luxtronik Update platform."""

# region Imports
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from typing import Final

from aiohttp import ClientTimeout
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from packaging.version import Version

from . import LuxtronikConfigEntry
from .base import LuxtronikEntity
from .const import (
    CHANGELOG_URL,
    CONF_HA_SENSOR_PREFIX,
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

PARALLEL_UPDATES = 0

MIN_TIME_BETWEEN_UPDATES: Final = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuxtronikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Luxtronik binary sensors dynamically through Luxtronik discovery."""

    coordinator = entry.runtime_data

    description = LuxtronikUpdateEntityDescription(
        luxtronik_key=LuxCalculation.C0081_FIRMWARE_VERSION,
        key=SensorKey.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
    )
    update_entity = LuxtronikUpdateEntity(
        entry=entry, coordinator=coordinator, description=description
    )
    entities = [update_entity]

    async_add_entities(entities, True)


class LuxtronikUpdateEntity(  # type: ignore  # pyright: ignore[reportIncompatibleVariableOverride]
    LuxtronikEntity[LuxtronikUpdateEntityDescription], UpdateEntity
):
    """Representation of Luxtronik firmware update entity."""

    _attr_title = "Luxtronik Firmware Version"
    _attr_supported_features: UpdateEntityFeature = (  # pyright: ignore[reportIncompatibleVariableOverride]
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
    )
    __firmware_version_available = None
    __firmware_version_changelog = None
    __firmware_version_available_last_request = None

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikUpdateEntityDescription,
    ) -> None:
        """Initialize the Luxtronik update entity."""
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=DeviceKey.heatpump,
        )
        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = f"update.{prefix}_{description.key}"
        self._attr_unique_id = self.entity_id

    async def async_added_to_hass(self) -> None:  # pragma: no cover
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        await self._request_available_firmware_version()

    @property
    def installed_version(self) -> str | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the currently installed firmware version."""
        return self._attr_state

    @property
    def latest_version(self) -> str | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the latest available firmware version."""
        if self.__firmware_version_available is None or self.installed_version is None:
            return None
        return self.__firmware_version_available.split("-")[0]

    @property
    def update_available(self) -> bool:
        """Return True if a newer firmware version is available."""
        if not self.latest_version or not self.installed_version:
            return False
        return self.version_is_newer(self.latest_version, self.installed_version)

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return True if latest_version is newer than installed_version."""

        def normalize(version: str) -> str:
            # Remove any leading non-digit characters
            return re.sub(r"^[^\d]+", "", version)

        try:
            return Version(normalize(latest_version)) > Version(
                normalize(installed_version)
            )
        except Exception:
            return False

    @staticmethod
    def extract_firmware_version(filename: str | None) -> str | None:
        """
        Extract firmware version from filename:
                # Filename e.g.: wp2reg-V2.88.1-9086
                # Extract 'V3.91.0' from 'wp2reg-V3.91.0_d0dc76bb'
                # Extract 'V2.88.1-9086' from 'wp2reg-V2.88.1-9086'
                # Extract 'V1.88.3-9717' from 'wpreg.V1.88.3-9717'
        """
        if not filename:
            return None
        match = re.search(r"[BV]\d+\.\d+\.\d+(?:-\d+)?", filename)
        return match.group(0) if match else None

    def release_notes(self) -> str | None:
        """Build release notes HTML."""
        download_id = get_firmware_download_id(self.installed_version)
        if download_id is None:
            return None
        release_url = get_manufacturer_firmware_url_by_model(
            self.coordinator.model, download_id
        )
        download_url = f"{DOWNLOAD_PORTAL_URL}{download_id}"
        manual_url = (
            FIRMWARE_UPDATE_MANUAL_DE
            if self.hass.config.language == LANG_DE
            else FIRMWARE_UPDATE_MANUAL_EN
        )
        return (
            f'For your <a href="{release_url}" target="_blank" rel="noreferrer noopener">'
            f"{self.coordinator.manufacturer} {self.coordinator.model} (Download ID {download_id})</a> a firmware update to "
            f'<a href="{download_url}" target="_blank" rel="noreferrer noopener">Firmware Version {self.__firmware_version_available}</a> is available.<br><br>'
            f'<a href="{manual_url}" target="_blank" rel="noreferrer noopener">Firmware Update Instructions</a><br><br>'
            "The Install button below has no function. It only exists to provide this notification in Home Assistant.<br><br>"
            "Please contact Alpha Innotec support for more information.<br><br>"
            f"Change Log:<br><br>{self.__firmware_version_changelog}<br><br>"
            "Please use Google Translate or similar, if necessary."
        )

    async def async_update(self) -> None:
        """Update the firmware version info."""
        if (
            self.__firmware_version_available_last_request is None
            or self.__firmware_version_available_last_request
            < datetime.now(UTC).timestamp() - MIN_TIME_BETWEEN_UPDATES.total_seconds()
        ):
            await self._request_available_firmware_version()

    async def _request_available_firmware_version(self) -> None:
        """Request the latest available firmware version from the download portal."""
        download_id = get_firmware_download_id(self.installed_version)
        if download_id is None:
            self.__firmware_version_available = STATE_UNAVAILABLE
            return

        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                f"{DOWNLOAD_PORTAL_URL}{download_id}", timeout=ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    raise Exception(f"HTTP error: {response.status}")

                header_content_disposition = response.headers.get(
                    "Content-Disposition", ""
                )
                filename_match = re.findall("filename=(.+)", header_content_disposition)
                filename = filename_match[0] if filename_match else None

                self.__firmware_version_available_last_request = datetime.now(
                    UTC
                ).timestamp()

                self.__firmware_version_available = self.extract_firmware_version(
                    filename
                )

            async with session.get(  # pragma: no cover
                f"{CHANGELOG_URL}{download_id}", timeout=ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    raise Exception(f"HTTP error: {response.status}")

                self.__firmware_version_changelog = await response.text()

        except Exception:
            LOGGER.warning(
                "Could not request download portal firmware version",
                exc_info=True,
            )
            self.__firmware_version_available = STATE_UNAVAILABLE

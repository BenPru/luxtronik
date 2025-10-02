from datetime import datetime, timedelta
import re
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import LuxtronikEntity
from .const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_COORDINATOR,
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

CHECK_INTERVAL = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Luxtronik update entity from config entry."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not data or CONF_COORDINATOR not in data:
        raise ConfigEntryNotReady

    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]

    description = LuxtronikUpdateEntityDescription(
        luxtronik_key=LuxCalculation.C0081_FIRMWARE_VERSION,
        key=SensorKey.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
    )

    async_add_entities(
        [LuxtronikUpdateEntity(entry=entry, coordinator=coordinator, description=description)],
        True,
    )


class LuxtronikUpdateEntity(LuxtronikEntity, UpdateEntity):
    """Representation of Luxtronik firmware update status."""

    entity_description: LuxtronikUpdateEntityDescription

    _attr_title = "Luxtronik Firmware Version"
    _attr_supported_features: UpdateEntityFeature = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
    )

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikUpdateEntityDescription,
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=DeviceKey.heatpump,
        )
        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = f"update.{prefix}_{description.key}"
        self._attr_unique_id = self.entity_id

        self._firmware_version_available: str | None = None
        self._last_check: datetime | None = None

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed firmware version."""
        return self._attr_state

    @property
    def latest_version(self) -> str | None:
        """Return the latest available firmware version."""
        if self._firmware_version_available is None or self.installed_version is None:
            return None
        return self._firmware_version_available[: len(self.installed_version)]

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return extra attributes for the update entity."""
        attributes = {}

        if self._last_check:
            attributes["last_firmware_check"] = self._last_check.isoformat()

        if self.installed_version:
            attributes["installed_version"] = self.installed_version

        if self.latest_version:
            attributes["latest_available_version"] = self.latest_version

        return attributes

    def release_notes(self) -> str | None:
        """Return release notes with links."""
        download_id = get_firmware_download_id(self.installed_version)
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
            f'For your {release_url}'
            f"{self.coordinator.manufacturer} {self.coordinator.model} (Download ID {download_id})</a> is "
            f'{download_url}Firmware Version {self._firmware_version_available}</a> available.<br>'
            f'{manual_url}Firmware Update Instructions</a><br><br>'
            "The Install button below has no function. It is only needed to trigger notifications in Home Assistant.<br><br>"
            "Alpha Innotec does not provide a changelog. Please contact support for more information."
        )

    async def async_update(self) -> None:
        """Check for firmware updates, rate-limited to once per hour."""
        now = datetime.utcnow()
        if self._last_check and now - self._last_check < CHECK_INTERVAL:
            return

        self._last_check = now
        await self._async_request_available_firmware_version()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await self.async_update()

    async def _async_request_available_firmware_version(self) -> None:
        """Request the latest firmware version using aiohttp."""
        download_id = get_firmware_download_id(self.installed_version)
        if download_id is None:
            self._firmware_version_available = STATE_UNAVAILABLE
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{DOWNLOAD_PORTAL_URL}{download_id}", timeout=30) as response:
                    header = response.headers.get("content-disposition", "")
                    filename = re.findall("filename=(.+)", header)[0] if "filename=" in header else ""
                    self._firmware_version_available = self.extract_firmware_version(filename)
        except Exception:
            LOGGER.warning("Could not request firmware version from download portal", exc_info=True)
            self._firmware_version_available = STATE_UNAVAILABLE

    @staticmethod
    def extract_firmware_version(filename: str) -> str | None:
        """Extract firmware version from filename."""
        match = re.search(r"V\d+\.\d+\.\d+(?:-\d+)?", filename)
        return match.group(0) if match else None



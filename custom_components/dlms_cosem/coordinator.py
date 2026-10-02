"""DataUpdateCoordinator for DLMS/COSEM integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from dlms_cosem import cosem
from dlms_cosem.client import DataResultError
from dlms_cosem.exceptions import CommunicationError, LocalDlmsProtocolError
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .dlms_cosem import DlmsConnection

_LOGGER = logging.getLogger(__name__)


class DlmsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data update coordinator for DLMS/COSEM."""

    connection: DlmsConnection

    def __init__(self, hass: HomeAssistant, connection: DlmsConnection) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=connection.entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.connection = connection
        self._tracked_attributes: dict[str, cosem.CosemAttribute] = {}

    @callback
    def async_register_attribute(
        self, key: str, attribute: cosem.CosemAttribute
    ) -> None:
        """Register an attribute to be polled."""
        self._tracked_attributes[key] = attribute

    @callback
    def async_unregister_attribute(self, key: str) -> None:
        """Unregister an attribute from being polled."""
        self._tracked_attributes.pop(key, None)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from DLMS meter."""
        if not self.connection.connected:
            try:
                await self.connection.async_connect()
            except (
                CommunicationError,
                LocalDlmsProtocolError,
                TimeoutError,
                OSError,
            ) as err:
                raise UpdateFailed(f"Error connecting to DLMS meter: {err}") from err

        data: dict[str, Any] = {}
        for key, attribute in list(self._tracked_attributes.items()):
            try:
                data[key] = await self.connection.async_get(attribute)
            except DataResultError as err:
                _LOGGER.debug(
                    "Unable to read attribute %s (%s): %s", key, attribute, err
                )
                data[key] = None
            except (
                CommunicationError,
                LocalDlmsProtocolError,
                TimeoutError,
                OSError,
            ) as err:
                await self.connection.async_close()
                raise UpdateFailed(
                    f"Communication error while reading {key}: {err}"
                ) from err

        return data

"""DataUpdateCoordinator for DLMS/COSEM integration."""

from __future__ import annotations

from datetime import timedelta
import logging
import random
import time
from typing import Any, NamedTuple

from dlms_cosem import cosem
from dlms_cosem.client import DataResultError
from dlms_cosem.exceptions import CommunicationError, LocalDlmsProtocolError
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .dlms_cosem import DlmsConnection

_LOGGER = logging.getLogger(__name__)

RETRY_AFTER = timedelta(minutes=1)


class TrackedAttribute(NamedTuple):
    """Represents a tracked COSEM attribute."""

    attribute: cosem.CosemAttribute
    scan_interval: timedelta | None = None


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
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.connection = connection
        self._tracked_attributes: dict[str, TrackedAttribute] = {}
        self._last_polled: dict[str, float] = {}

    @callback
    def async_register_attribute(
        self,
        key: str,
        attribute: cosem.CosemAttribute,
        scan_interval: timedelta | None = None,
    ) -> None:
        """Register an attribute to be polled."""
        if scan_interval is not None:
            # Introduce a random delay to avoid polling all throttled
            # entities at the same time.
            scan_interval += timedelta(
                seconds=random.randint(0, int(DEFAULT_SCAN_INTERVAL.total_seconds()))
            )

        self._tracked_attributes[key] = TrackedAttribute(attribute, scan_interval)

    @callback
    def async_unregister_attribute(self, key: str) -> None:
        """Unregister an attribute from being polled."""
        self._tracked_attributes.pop(key, None)
        self._last_polled.pop(key, None)

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and close connection."""
        await super().async_shutdown()
        await self.connection.async_close()

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

        data: dict[str, Any] = dict(self.data) if self.data else {}
        now = time.monotonic()
        for key, tracked in list(self._tracked_attributes.items()):
            if (
                key in data
                and tracked.scan_interval is not None
                and (now - self._last_polled.get(key, 0.0))
                < tracked.scan_interval.total_seconds()
            ):
                continue

            try:
                data[key] = await self.connection.async_get(tracked.attribute)
                self._last_polled[key] = now
            except DataResultError as err:
                _LOGGER.debug(
                    "Unable to read attribute %s (%s): %s", key, tracked.attribute, err
                )
                data[key] = None
                self._last_polled[key] = now
            except (
                CommunicationError,
                LocalDlmsProtocolError,
                TimeoutError,
                OSError,
            ) as err:
                await self.connection.async_close()
                raise UpdateFailed(
                    f"Communication error while reading {key}: {err}",
                    retry_after=RETRY_AFTER.total_seconds(),
                ) from err

        return data

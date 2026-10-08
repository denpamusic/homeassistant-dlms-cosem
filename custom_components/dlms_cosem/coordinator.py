"""DataUpdateCoordinator for DLMS/COSEM integration."""

from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any, Final, NamedTuple, override

from dlms_cosem import cosem
from dlms_cosem.client import DataResultError
from dlms_cosem.exceptions import CommunicationError, LocalDlmsProtocolError
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .dlms_cosem import DlmsConnection, DlmsStatistics

_LOGGER = logging.getLogger(__name__)

MAX_SLOW_ATTRIBUTES_PER_POLL: Final = 2

RETRY_INTERVALS: Final[list[timedelta]] = [
    DEFAULT_SCAN_INTERVAL,
    timedelta(minutes=1),
    timedelta(minutes=5),
]


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
        self._retry_attempt = 0

    @callback
    def async_register_attribute(
        self,
        key: str,
        attribute: cosem.CosemAttribute,
        scan_interval: timedelta | None = None,
    ) -> None:
        """Register an attribute to be polled."""
        self._tracked_attributes[key] = TrackedAttribute(attribute, scan_interval)

    @callback
    def async_unregister_attribute(self, key: str) -> None:
        """Unregister an attribute from being polled."""
        self._tracked_attributes.pop(key, None)
        self._last_polled.pop(key, None)

    async def _async_connect(self) -> None:
        """Connect to DLMS meter with retry backoff."""
        try:
            await self.connection.async_connect()
            self._retry_attempt = 0
        except (
            CommunicationError,
            LocalDlmsProtocolError,
            TimeoutError,
            OSError,
        ) as err:
            retry_after = RETRY_INTERVALS[self._retry_attempt]
            if self._retry_attempt < len(RETRY_INTERVALS) - 1:
                self._retry_attempt += 1
            raise UpdateFailed(
                f"Error connecting to DLMS meter: {err}",
                retry_after=retry_after.total_seconds(),
            ) from err

    async def _async_fetch_attribute(
        self, key: str, tracked: TrackedAttribute, now: float
    ) -> Any:
        """Fetch a single attribute and handle errors."""
        try:
            value = await self.connection.async_get(tracked.attribute)
            self._last_polled[key] = now
            return value
        except DataResultError as err:
            _LOGGER.debug(
                "Unable to read attribute %s (%s): %s", key, tracked.attribute, err
            )
            self._last_polled[key] = now
            return None
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

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from DLMS meter."""
        if not self.connection.connected:
            await self._async_connect()

        data: dict[str, Any] = dict(self.data) if self.data else {}
        now = time.monotonic()
        slow_attributes_polled = 0

        for key, tracked in list(self._tracked_attributes.items()):
            if key in data and tracked.scan_interval is not None:
                elapsed = now - self._last_polled.get(key, 0.0)
                if elapsed < tracked.scan_interval.total_seconds():
                    continue

                if slow_attributes_polled >= MAX_SLOW_ATTRIBUTES_PER_POLL:
                    continue

                slow_attributes_polled += 1

            data[key] = await self._async_fetch_attribute(key, tracked, now)

        return data

    @property
    def dlms_state(self) -> str:
        """Return the current DLMS association state."""
        return self.connection.dlms_state

    @property
    def statistics(self) -> DlmsStatistics:
        """Return connection statistics."""
        return self.connection.statistics

    @override
    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        await super().async_shutdown()
        await self.connection.async_close()

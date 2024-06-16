"""The DLMS integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from dlms_cosem.exceptions import CommunicationError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    EVENT_LOGGING_CHANGED,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
import structlog

from .const import CONF_HOST, SIGNAL_AVAILABLE
from .dlms_cosem import DlmsConnection

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

DEFAULT_LOGGER = structlog.make_filtering_bound_logger(logging.WARNING)
DEBUG_LOGGER = structlog.make_filtering_bound_logger(logging.DEBUG)

_LOGGER = logging.getLogger(__name__)

type DlmsCosemConfigEntry = ConfigEntry["DlmsCosemData"]


@callback
def _async_logging_changed(event: Event | None = None) -> None:
    """Handle logging change."""
    logger = DEBUG_LOGGER if _LOGGER.isEnabledFor(logging.DEBUG) else DEFAULT_LOGGER
    structlog.configure(wrapper_class=logger)


@dataclass
class DlmsCosemData:
    """Represents DLMS/COSEM integration runtime data."""

    connection: DlmsConnection


async def async_setup_entry(hass: HomeAssistant, entry: DlmsCosemConfigEntry) -> bool:
    """Set up DLMS connection from a config entry."""
    connection = DlmsConnection(hass, entry)
    structlog.configure(wrapper_class=DEFAULT_LOGGER)
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_LOGGING_CHANGED, _async_logging_changed)
    )

    try:
        await connection.async_connect()
    except CommunicationError as err:
        await connection.async_close()
        raise ConfigEntryNotReady(
            f"Timed out while connecting to {connection.entry.data[CONF_HOST]}"
        ) from err

    entry.runtime_data = DlmsCosemData(connection)

    async def _async_close_connection(event: Event | None = None) -> None:
        """Close DLMS connection on HA Stop."""
        await connection.async_close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close_connection)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_dispatcher_send(hass, SIGNAL_AVAILABLE, True)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DlmsCosemConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.connection.async_close()

    return unload_ok

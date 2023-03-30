"""The DLMS integration."""
from __future__ import annotations

from dlms_cosem.exceptions import CommunicationError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_HOST, DOMAIN
from .dlms_cosem import DlmsConnection, async_get_dlms_client

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DLMS connection from a config entry."""
    connection = DlmsConnection(
        hass,
        entry,
        async_get_dlms_client(entry.data),
    )

    async def async_close_connection(event=None):
        """Closes DLMS connection on HA Stop."""
        await connection.async_close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    try:
        await connection.async_setup()
    except CommunicationError as e:
        raise ConfigEntryNotReady(
            f"Timed out while connecting to {connection.entry.data[CONF_HOST]}"
        ) from e

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = connection
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        try:
            connection: DlmsConnection = hass.data[DOMAIN][entry.entry_id]
            await connection.async_close()
            hass.data[DOMAIN].pop(entry.entry_id)
        except KeyError:
            pass

    return unload_ok

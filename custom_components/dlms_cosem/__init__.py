"""The DLMS integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from dlms_cosem import cosem, enumerations
from dlms_cosem.exceptions import CommunicationError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from .const import CONF_HOST, DOMAIN, SIGNAL_CONNECTED
from .dlms_cosem import DlmsConnection

PLATFORMS: list[Platform] = [Platform.SENSOR]

MAX_RECONNECTS = 3


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DLMS connection from a config entry."""
    connection = DlmsConnection(hass, entry)

    try:
        await connection.async_setup()
    except CommunicationError as e:
        await connection.async_close()
        raise ConfigEntryNotReady(
            f"Timed out while connecting to {connection.entry.data[CONF_HOST]}"
        ) from e

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = connection

    async def _async_close_connection(event: Event | None = None) -> None:
        """Close DLMS connection on HA Stop."""
        await connection.async_close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close_connection)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_dispatcher_send(hass, SIGNAL_CONNECTED)
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

    return cast(bool, unload_ok)


@dataclass(frozen=True, kw_only=True, slots=True)
class CosemEntityDescription:
    """Describes the COSEM entity."""

    obis: cosem.Obis
    attribute: int
    interface: enumerations.CosemInterface


class CosemEntity(Entity):
    """Represents the COSEM entity."""

    connection: DlmsConnection
    entity_description: CosemEntityDescription
    _attr_cosem_attribute: cosem.CosemAttribute

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CONNECTED, self._connect_callback
            )
        )

    @callback
    def _connect_callback(self) -> None:
        """Schedule an update after connection."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def available(self) -> bool:
        """If entity is available."""
        if self.connection.reconnect_attempt:
            return self.connection.reconnect_attempt <= MAX_RECONNECTS

        return self.connection.connected

    @property
    def cosem_attribute(self) -> cosem.CosemAttribute:
        """Return the COSEM attribute instance."""
        return self._attr_cosem_attribute

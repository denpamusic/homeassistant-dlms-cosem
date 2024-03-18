"""The DLMS integration."""
from __future__ import annotations

import datetime as dt
from functools import cached_property
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
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import CONF_HOST, DEFAULT_ATTRIBUTE, DOMAIN, SIGNAL_AVAILABLE
from .dlms_cosem import DlmsConnection

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DLMS connection from a config entry."""
    connection = DlmsConnection(hass, entry)

    try:
        await connection.async_connect()
    except CommunicationError as err:
        await connection.async_close()
        raise ConfigEntryNotReady(
            f"Timed out while connecting to {connection.entry.data[CONF_HOST]}"
        ) from err

    async def _async_close_connection(event: Event | None = None) -> None:
        """Close DLMS connection on HA Stop."""
        await connection.async_close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close_connection)
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = connection
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_dispatcher_send(hass, SIGNAL_AVAILABLE, True)
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


def dlms_datetime_to_ha_datetime(dattim: dt.datetime) -> dt.datetime:
    """Convert timezone between DLMS and HA."""
    utcoffset = dattim.utcoffset()
    if utcoffset is None:
        return dattim

    local_tz = dt.timezone(offset=dt.timedelta(seconds=-utcoffset.total_seconds()))
    return dattim.replace(tzinfo=local_tz)


class CosemEntityDescription(EntityDescription):
    """Describes the COSEM entity."""

    attribute: int = DEFAULT_ATTRIBUTE
    interface: enumerations.CosemInterface
    obis: cosem.Obis


class CosemEntity(Entity):
    """Represents the COSEM entity."""

    _attr_has_entity_name = True
    connection: DlmsConnection
    entity_description: CosemEntityDescription

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_AVAILABLE, self._available_callback
            )
        )

    @callback
    def _available_callback(self, available: bool) -> None:
        """Mark entity as un/available and update ha state."""
        self._attr_available = available
        self.async_schedule_update_ha_state(force_refresh=True if available else False)

    @cached_property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return f"{self.connection.entry.unique_id}-{self.entity_description.key}"

    @cached_property
    def cosem_attribute(self) -> cosem.CosemAttribute:
        """Return the COSEM attribute."""
        return cosem.CosemAttribute(
            interface=self.entity_description.interface,
            instance=self.entity_description.obis,
            attribute=self.entity_description.attribute,
        )

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            name=f"{self.connection.manufacturer} {self.connection.model}",
            identifiers={(DOMAIN, self.connection.entry.unique_id)},
            manufacturer=self.connection.manufacturer,
            model=self.connection.model,
            serial_number=self.connection.equipment_id,
            sw_version=self.connection.sw_version,
        )

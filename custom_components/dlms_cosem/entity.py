"""Contains base DLMS/COSEM entity."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from dlms_cosem import cosem, enumerations
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import DEFAULT_ATTRIBUTE, DOMAIN, SIGNAL_AVAILABLE
from .dlms_cosem import DlmsConnection


@dataclass(frozen=True, kw_only=True)
class CosemEntityDescription(EntityDescription):
    """Describes the COSEM entity."""

    attribute: int = DEFAULT_ATTRIBUTE
    interface: enumerations.CosemInterface
    obis: cosem.Obis
    value_fn: Callable[[Any], Any]


class CosemEntity(Entity):
    """Represents the COSEM entity."""

    _attr_has_entity_name = True
    connection: DlmsConnection
    entity_description: CosemEntityDescription

    def __init__(self, connection: DlmsConnection, description: CosemEntityDescription):
        """Initialize the COSEM object."""
        self.connection = connection
        self.entity_description = description

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

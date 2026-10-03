"""Contains base DLMS/COSEM entity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import cached_property
from typing import Any

from dlms_cosem import cosem, enumerations
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_ATTRIBUTE, DOMAIN
from .coordinator import DlmsCoordinator


@dataclass(frozen=True, kw_only=True)
class CosemEntityDescription(EntityDescription):
    """Describes the COSEM entity."""

    attribute: int = DEFAULT_ATTRIBUTE
    interface: enumerations.CosemInterface
    obis: cosem.Obis
    scan_interval: timedelta | None = None
    value_fn: Callable[[Any], Any]


class CosemEntity(CoordinatorEntity[DlmsCoordinator]):
    """Represents the COSEM entity."""

    _attr_has_entity_name = True
    entity_description: CosemEntityDescription

    def __init__(
        self, coordinator: DlmsCoordinator, description: CosemEntityDescription
    ) -> None:
        """Initialize the COSEM object."""
        super().__init__(coordinator)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        self.coordinator.async_register_attribute(
            self.entity_description.key,
            self.cosem_attribute,
            self.entity_description.scan_interval,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        self.coordinator.async_unregister_attribute(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.get(self.entity_description.key) is not None
        )

    @cached_property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return f"{self.coordinator.connection.entry.unique_id}-{self.entity_description.key}"

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
        connection = self.coordinator.connection
        return DeviceInfo(
            name=f"{connection.manufacturer} {connection.model}",
            identifiers={(DOMAIN, connection.equipment_id)},
            manufacturer=connection.manufacturer,
            model=connection.model,
            serial_number=connection.equipment_id,
            sw_version=connection.sw_version,
        )

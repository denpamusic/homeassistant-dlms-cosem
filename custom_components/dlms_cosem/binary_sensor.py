"""Platform for the binary sensor integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from dlms_cosem import cosem, enumerations
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DlmsCosemConfigEntry
from .const import DEFAULT_SCAN_INTERVAL
from .dlms_cosem import async_extract_error_codes
from .entity import CosemEntity, CosemEntityDescription

SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CosemBinarySensorEntityDescription(
    CosemEntityDescription, BinarySensorEntityDescription
):
    """Describes the COSEM binary sensor entity."""

    interface: enumerations.CosemInterface = enumerations.CosemInterface.DATA


BINARY_SENSOR_TYPES: tuple[CosemBinarySensorEntityDescription, ...] = (
    CosemBinarySensorEntityDescription(
        key="self_test",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        obis=cosem.Obis(0, 0, 97, 97, 0),
        translation_key="self_test",
        value_fn=lambda x: any(byte for byte in x),
    ),
)


class CosemBinarySensor(CosemEntity, BinarySensorEntity):
    """Represents the COSEM binary sensor platform."""

    entity_description: CosemBinarySensorEntityDescription

    async def async_update(self) -> None:
        """Update entity state."""
        if response := await self.connection.async_get(self.cosem_attribute):
            self._attr_is_on = self.entity_description.value_fn(response)
            if self.entity_description.key == "self_test":
                self._attr_extra_state_attributes = (
                    {"error_codes": ", ".join(async_extract_error_codes(response))}
                    if self.is_on
                    else {}
                )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DlmsCosemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the binary sensor platform."""
    data = entry.runtime_data
    async_add_entities(
        CosemBinarySensor(data.connection, description)
        for description in BINARY_SENSOR_TYPES
    )
    return True

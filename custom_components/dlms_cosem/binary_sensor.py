"""Platform for the binary sensor integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import cast

from dlms_cosem import cosem, enumerations
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DlmsCosemConfigEntry
from .dlms_cosem import async_extract_error_codes
from .entity import CosemEntity, CosemEntityDescription


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
        scan_interval=timedelta(hours=1),
        translation_key="self_test",
        value_fn=lambda x: any(byte for byte in x),
    ),
)


class CosemBinarySensor(CosemEntity, BinarySensorEntity):
    """Represents the COSEM binary sensor platform."""

    entity_description: CosemBinarySensorEntityDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        raw_value = self.coordinator.data.get(self.entity_description.key)
        self._attr_is_on = self.entity_description.value_fn(raw_value)
        if self.entity_description.key == "self_test":
            error_codes = async_extract_error_codes(cast(bytes, raw_value))
            self._attr_extra_state_attributes = {"error_codes": ", ".join(error_codes)}
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DlmsCosemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        CosemBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_TYPES
    )
    return True

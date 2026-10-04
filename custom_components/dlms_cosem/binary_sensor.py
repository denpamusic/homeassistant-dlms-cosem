"""Platform for the binary sensor integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from dlms_cosem import cosem, enumerations
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .dlms_cosem import async_extract_error_codes
from .entity import CosemEntity, CosemEntityDescription

if TYPE_CHECKING:
    from . import DlmsCosemConfigEntry


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

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if (
            self.coordinator.data is not None
            and (raw := self.coordinator.data.get(self.entity_description.key))
            is not None
        ):
            return bool(self.entity_description.value_fn(raw))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if (
            self.entity_description.key == "self_test"
            and self.is_on
            and self.coordinator.data is not None
            and (raw := self.coordinator.data.get(self.entity_description.key))
            is not None
        ):
            return {"error_codes": ", ".join(async_extract_error_codes(raw))}
        return {}


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

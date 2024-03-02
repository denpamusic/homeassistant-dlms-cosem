"""Platform for the binary sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from dlms_cosem import cosem, enumerations
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigType
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from . import CosemEntity, CosemEntityDescription
from .const import DOMAIN
from .dlms_cosem import DlmsConnection, async_extract_error_codes

SCAN_INTERVAL = timedelta(seconds=15)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3)
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True, slots=True)
class CosemBinarySensorEntityDescription(
    BinarySensorEntityDescription, CosemEntityDescription
):
    """Describes the COSEM binary sensor entity."""

    interface: enumerations.CosemInterface = enumerations.CosemInterface.DATA
    value_fn: Callable[[Any], bool]


BINARY_SENSOR_TYPES: tuple[CosemBinarySensorEntityDescription, ...] = (
    CosemBinarySensorEntityDescription(
        key="self_test",
        translation_key="self_test",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        obis=cosem.Obis(0, 0, 97, 97, 0),
        value_fn=lambda x: any(byte for byte in x),
    ),
)


class CosemBinarySensor(CosemEntity, BinarySensorEntity):
    """Represents the COSEM binary sensor platform."""

    entity_description: CosemBinarySensorEntityDescription

    def __init__(
        self,
        connection: DlmsConnection,
        description: CosemBinarySensorEntityDescription,
    ):
        """Initialize the COSEM sensor object."""
        self.connection = connection
        self.entity_description = description

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Update entity state."""
        if response := await self.connection.async_get(self.cosem_attribute):
            self._attr_is_on = self.entity_description.value_fn(response)
            if self.entity_description.key == "self_test" and self.is_on:
                self._attr_extra_state_attributes = {
                    "error_codes": ", ".join(async_extract_error_codes(response))
                }


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the sensor platform."""
    connection: DlmsConnection = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        CosemBinarySensor(connection, description)
        for description in BINARY_SENSOR_TYPES
    )
    return True

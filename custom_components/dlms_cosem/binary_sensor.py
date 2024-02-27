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
from .const import DEFAULT_ATTRIBUTE, DOMAIN
from .dlms_cosem import DlmsConnection

SCAN_INTERVAL = timedelta(seconds=15)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3)
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True, slots=True)
class CosemBinarySensorEntityDescription(
    BinarySensorEntityDescription, CosemEntityDescription
):
    """Describes the COSEM binary sensor entity."""

    value_fn: Callable[[Any], bool]
    attribute: int = DEFAULT_ATTRIBUTE
    interface: enumerations.CosemInterface = enumerations.CosemInterface.DATA


BINARY_SENSOR_TYPES: tuple[CosemBinarySensorEntityDescription, ...] = (
    CosemBinarySensorEntityDescription(
        key="self_test",
        translation_key="self_test",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        obis=cosem.Obis(0, 0, 97, 97, 0),
        value_fn=lambda x: int.from_bytes(x) != 0,
    ),
)


class CosemBinarySensor(CosemEntity, BinarySensorEntity):
    """Represents the COSEM sensor platform."""

    _attr_has_entity_name = True
    entity_description: CosemBinarySensorEntityDescription

    def __init__(
        self,
        connection: DlmsConnection,
        description: CosemBinarySensorEntityDescription,
    ):
        """Initialize the COSEM sensor object."""
        self.connection = connection
        self.entity_description = description
        self._attr_cosem_attribute = cosem.CosemAttribute(
            interface=self.entity_description.interface,
            instance=self.entity_description.obis,
            attribute=self.entity_description.attribute,
        )
        self._attr_device_info = connection.device_info
        self._attr_unique_id = f"{connection.entry.unique_id}-{description.key}"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Update entity state."""
        if response := await self.connection.async_get(self.cosem_attribute):
            self._attr_is_on = self.entity_description.value_fn(response)
            if self.entity_description.key == "self_test":
                self._attr_extra_state_attributes = {
                    "error_code": int.from_bytes(response)
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

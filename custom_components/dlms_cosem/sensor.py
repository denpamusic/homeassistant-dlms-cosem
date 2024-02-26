"""Platform for the sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime as dt
from datetime import timedelta

from dlms_cosem import cosem, enumerations, time
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigType
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from . import CosemEntity, CosemEntityDescription
from .const import DEFAULT_ATTRIBUTE, DOMAIN
from .dlms_cosem import DlmsConnection

SCAN_INTERVAL = timedelta(seconds=15)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3)
PARALLEL_UPDATES = 1


def dlms_datetime_to_ha_datetime(dattim: dt.datetime) -> dt.datetime:
    """Convert timezone between DLMS and HA."""
    utcoffset = dattim.utcoffset()
    if utcoffset is None:
        return dattim

    local_tz = dt.timezone(offset=dt.timedelta(seconds=-utcoffset.total_seconds()))
    return dattim.replace(tzinfo=local_tz)


@dataclass(frozen=True, kw_only=True, slots=True)
class CosemSensorEntityDescription(SensorEntityDescription, CosemEntityDescription):
    """Describes the COSEM sensor entity."""

    value_fn: Callable
    attribute: int = DEFAULT_ATTRIBUTE
    interface: enumerations.CosemInterface = enumerations.CosemInterface.REGISTER


SENSOR_TYPES: tuple[CosemSensorEntityDescription, ...] = (
    CosemSensorEntityDescription(
        key="current_l1",
        translation_key="current_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        obis=cosem.Obis(1, 0, 31, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="current_l2",
        translation_key="current_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        obis=cosem.Obis(1, 0, 51, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="current_l3",
        translation_key="current_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        obis=cosem.Obis(1, 0, 71, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="voltage_l1",
        translation_key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        obis=cosem.Obis(1, 0, 32, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="voltage_l2",
        translation_key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        obis=cosem.Obis(1, 0, 52, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="voltage_l3",
        translation_key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        obis=cosem.Obis(1, 0, 72, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_power_total",
        translation_key="active_power_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        obis=cosem.Obis(1, 0, 1, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_power_l1",
        translation_key="active_power_l1",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        obis=cosem.Obis(1, 0, 21, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_power_l2",
        translation_key="active_power_l2",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        obis=cosem.Obis(1, 0, 41, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_power_l3",
        translation_key="active_power_l3",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        obis=cosem.Obis(1, 0, 61, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="power_factor_total",
        translation_key="power_factor_total",
        device_class=SensorDeviceClass.POWER_FACTOR,
        obis=cosem.Obis(1, 0, 13, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="power_factor_l1",
        translation_key="power_factor_l1",
        device_class=SensorDeviceClass.POWER_FACTOR,
        obis=cosem.Obis(1, 0, 33, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="power_factor_l2",
        translation_key="power_factor_l2",
        device_class=SensorDeviceClass.POWER_FACTOR,
        obis=cosem.Obis(1, 0, 53, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="power_factor_l3",
        translation_key="power_factor_l3",
        device_class=SensorDeviceClass.POWER_FACTOR,
        obis=cosem.Obis(1, 0, 73, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="active_energy_total",
        translation_key="active_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        obis=cosem.Obis(1, 0, 1, 8, 0),
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="active_energy_tariff1",
        translation_key="active_energy_tariff1",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        obis=cosem.Obis(1, 0, 1, 8, 1),
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="active_energy_tariff2",
        translation_key="active_energy_tariff2",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        obis=cosem.Obis(1, 0, 1, 8, 2),
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="frequency",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        obis=cosem.Obis(1, 0, 14, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_tariff",
        translation_key="active_tariff",
        icon="mdi:progress-clock",
        interface=enumerations.CosemInterface.DATA,
        obis=cosem.Obis(0, 0, 96, 14, 0),
        value_fn=lambda x: x,
    ),
    CosemSensorEntityDescription(
        key="internal_temperature",
        translation_key="internal_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        obis=cosem.Obis(0, 0, 96, 9, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda x: x,
    ),
    CosemSensorEntityDescription(
        key="local_time",
        translation_key="local_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        interface=enumerations.CosemInterface.CLOCK,
        obis=cosem.Obis(0, 0, 1, 0, 0),
        value_fn=lambda x: dlms_datetime_to_ha_datetime(time.datetime_from_bytes(x)[0]),
    ),
)


class CosemSensor(CosemEntity, SensorEntity):
    """Represents the COSEM sensor platform."""

    _attr_has_entity_name = True
    entity_description: CosemSensorEntityDescription

    def __init__(
        self, connection: DlmsConnection, description: CosemSensorEntityDescription
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
            self._attr_native_value = self.entity_description.value_fn(response)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the sensor platform."""
    connection: DlmsConnection = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        CosemSensor(connection, description) for description in SENSOR_TYPES
    )
    return True

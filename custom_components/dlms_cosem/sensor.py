"""Platform for the sensor integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from dlms_cosem import cosem, enumerations, time
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DlmsCosemConfigEntry
from .const import DEFAULT_SCAN_INTERVAL
from .dlms_cosem import async_dlms_datetime_to_ha_datetime
from .entity import CosemEntity, CosemEntityDescription

SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CosemSensorEntityDescription(CosemEntityDescription, SensorEntityDescription):
    """Describes the COSEM sensor entity."""

    interface: enumerations.CosemInterface = enumerations.CosemInterface.REGISTER


SENSOR_TYPES: tuple[CosemSensorEntityDescription, ...] = (
    CosemSensorEntityDescription(
        key="current_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        obis=cosem.Obis(1, 0, 31, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="current_l1",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="current_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        obis=cosem.Obis(1, 0, 51, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="current_l2",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="current_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        obis=cosem.Obis(1, 0, 71, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="current_l3",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        obis=cosem.Obis(1, 0, 32, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="voltage_l1",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        obis=cosem.Obis(1, 0, 52, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="voltage_l2",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        obis=cosem.Obis(1, 0, 72, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="voltage_l3",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_power_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        obis=cosem.Obis(1, 0, 1, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="active_power_total",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_power_l1",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        obis=cosem.Obis(1, 0, 21, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="active_power_l1",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_power_l2",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        obis=cosem.Obis(1, 0, 41, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="active_power_l2",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_power_l3",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        obis=cosem.Obis(1, 0, 61, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="active_power_l3",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="apparent_power_l1",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        obis=cosem.Obis(1, 0, 29, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="apparent_power_l1",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="apparent_power_l2",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        obis=cosem.Obis(1, 0, 49, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="apparent_power_l2",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="apparent_power_l3",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        obis=cosem.Obis(1, 0, 69, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="apparent_power_l3",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="apparent_power_total",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        obis=cosem.Obis(1, 0, 9, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="apparent_power_total",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="power_factor_total",
        device_class=SensorDeviceClass.POWER_FACTOR,
        obis=cosem.Obis(1, 0, 13, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="power_factor_total",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="power_factor_l1",
        device_class=SensorDeviceClass.POWER_FACTOR,
        obis=cosem.Obis(1, 0, 33, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="power_factor_l1",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="power_factor_l2",
        device_class=SensorDeviceClass.POWER_FACTOR,
        obis=cosem.Obis(1, 0, 53, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="power_factor_l2",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="power_factor_l3",
        device_class=SensorDeviceClass.POWER_FACTOR,
        obis=cosem.Obis(1, 0, 73, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="power_factor_l3",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="active_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        obis=cosem.Obis(1, 0, 1, 8, 0),
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        translation_key="active_energy_total",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="active_energy_tariff1",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        obis=cosem.Obis(1, 0, 1, 8, 1),
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        translation_key="active_energy_tariff1",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="active_energy_tariff2",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        obis=cosem.Obis(1, 0, 1, 8, 2),
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        translation_key="active_energy_tariff2",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        obis=cosem.Obis(1, 0, 14, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        translation_key="frequency",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_tariff",
        icon="mdi:progress-clock",
        interface=enumerations.CosemInterface.DATA,
        obis=cosem.Obis(0, 0, 96, 14, 0),
        translation_key="active_tariff",
        value_fn=lambda x: x,
    ),
    CosemSensorEntityDescription(
        key="internal_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        obis=cosem.Obis(0, 0, 96, 9, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        translation_key="internal_temperature",
        value_fn=lambda x: x,
    ),
    CosemSensorEntityDescription(
        key="uptime",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        obis=cosem.Obis(0, 0, 96, 8, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        translation_key="uptime",
        value_fn=lambda x: x,
    ),
    CosemSensorEntityDescription(
        key="local_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        interface=enumerations.CosemInterface.CLOCK,
        obis=cosem.Obis(0, 0, 1, 0, 0),
        translation_key="local_time",
        value_fn=lambda x: async_dlms_datetime_to_ha_datetime(
            time.datetime_from_bytes(x)[0]
        ),
    ),
    CosemSensorEntityDescription(
        key="clock_synced",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        interface=enumerations.CosemInterface.DATA,
        obis=cosem.Obis(0, 0, 96, 2, 12),
        translation_key="clock_synced",
        value_fn=lambda x: async_dlms_datetime_to_ha_datetime(
            time.datetime_from_bytes(x)[0]
        ),
    ),
    CosemSensorEntityDescription(
        key="front_cover_opened",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:meter-electric-outline",
        interface=enumerations.CosemInterface.DATA,
        obis=cosem.Obis(0, 0, 96, 20, 1),
        translation_key="front_cover_opened",
        value_fn=lambda x: async_dlms_datetime_to_ha_datetime(
            time.datetime_from_bytes(x)[0]
        ),
    ),
    CosemSensorEntityDescription(
        key="terminals_cover_opened",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:screwdriver",
        interface=enumerations.CosemInterface.DATA,
        obis=cosem.Obis(0, 0, 96, 20, 6),
        translation_key="terminals_cover_opened",
        value_fn=lambda x: async_dlms_datetime_to_ha_datetime(
            time.datetime_from_bytes(x)[0]
        ),
    ),
    CosemSensorEntityDescription(
        key="magnetic_field_detected",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:magnet-on",
        interface=enumerations.CosemInterface.DATA,
        obis=cosem.Obis(0, 0, 96, 20, 16),
        translation_key="magnetic_field_detected",
        value_fn=lambda x: async_dlms_datetime_to_ha_datetime(
            time.datetime_from_bytes(x)[0]
        ),
    ),
)


class CosemSensor(CosemEntity, SensorEntity):
    """Represents the COSEM sensor platform."""

    entity_description: CosemSensorEntityDescription

    async def async_update(self) -> None:
        """Update entity state."""
        if response := await self.connection.async_get(self.cosem_attribute):
            self._attr_native_value = self.entity_description.value_fn(response)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DlmsCosemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the sensor platform."""
    data = entry.runtime_data
    async_add_entities(
        CosemSensor(data.connection, description) for description in SENSOR_TYPES
    )
    return True

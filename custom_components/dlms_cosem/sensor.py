"""Platform for the sensor integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from microdlms import InterfaceClass, ObisCode

from . import DlmsCosemConfigEntry
from .dlms_cosem import parse_dlms_datetime
from .entity import CosemEntity, CosemEntityDescription


@dataclass(frozen=True, kw_only=True)
class CosemSensorEntityDescription(CosemEntityDescription, SensorEntityDescription):
    """Describes the COSEM sensor entity."""

    interface: InterfaceClass | int = InterfaceClass.REGISTER


SENSOR_TYPES: tuple[CosemSensorEntityDescription, ...] = (
    CosemSensorEntityDescription(
        key="current_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        obis=ObisCode(1, 0, 31, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="current_l1",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="current_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        obis=ObisCode(1, 0, 51, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="current_l2",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="current_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        obis=ObisCode(1, 0, 71, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="current_l3",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        obis=ObisCode(1, 0, 32, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="voltage_l1",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        obis=ObisCode(1, 0, 52, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="voltage_l2",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        obis=ObisCode(1, 0, 72, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="voltage_l3",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_power_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        obis=ObisCode(1, 0, 1, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="active_power_total",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_power_l1",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        obis=ObisCode(1, 0, 21, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="active_power_l1",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_power_l2",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        obis=ObisCode(1, 0, 41, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="active_power_l2",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_power_l3",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        obis=ObisCode(1, 0, 61, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="active_power_l3",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="apparent_power_l1",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        obis=ObisCode(1, 0, 29, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="apparent_power_l1",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="apparent_power_l2",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        obis=ObisCode(1, 0, 49, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="apparent_power_l2",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="apparent_power_l3",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        obis=ObisCode(1, 0, 69, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="apparent_power_l3",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="apparent_power_total",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        obis=ObisCode(1, 0, 9, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="apparent_power_total",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="power_factor_total",
        device_class=SensorDeviceClass.POWER_FACTOR,
        entity_registry_enabled_default=False,
        obis=ObisCode(1, 0, 13, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="power_factor_total",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="power_factor_l1",
        device_class=SensorDeviceClass.POWER_FACTOR,
        entity_registry_enabled_default=False,
        obis=ObisCode(1, 0, 33, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="power_factor_l1",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="power_factor_l2",
        device_class=SensorDeviceClass.POWER_FACTOR,
        entity_registry_enabled_default=False,
        obis=ObisCode(1, 0, 53, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="power_factor_l2",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="power_factor_l3",
        device_class=SensorDeviceClass.POWER_FACTOR,
        entity_registry_enabled_default=False,
        obis=ObisCode(1, 0, 73, 7, 0),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key="power_factor_l3",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="active_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        obis=ObisCode(1, 0, 1, 8, 0),
        scan_interval=timedelta(minutes=5),
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        translation_key="active_energy_total",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="active_energy_tariff1",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        obis=ObisCode(1, 0, 1, 8, 1),
        scan_interval=timedelta(minutes=5),
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        translation_key="active_energy_tariff1",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="active_energy_tariff2",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        obis=ObisCode(1, 0, 1, 8, 2),
        scan_interval=timedelta(minutes=5),
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        translation_key="active_energy_tariff2",
        value_fn=lambda x: x / 1000,
    ),
    CosemSensorEntityDescription(
        key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        obis=ObisCode(1, 0, 14, 7, 0),
        scan_interval=timedelta(minutes=5),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        translation_key="frequency",
        value_fn=lambda x: x / 100,
    ),
    CosemSensorEntityDescription(
        key="active_tariff",
        interface=InterfaceClass.DATA,
        obis=ObisCode(0, 0, 96, 14, 0),
        translation_key="active_tariff",
        value_fn=lambda x: x,
    ),
    CosemSensorEntityDescription(
        key="internal_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        obis=ObisCode(0, 0, 96, 9, 0),
        scan_interval=timedelta(minutes=5),
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
        obis=ObisCode(0, 0, 96, 8, 0),
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
        interface=InterfaceClass.CLOCK,
        obis=ObisCode(0, 0, 1, 0, 0),
        translation_key="local_time",
        value_fn=parse_dlms_datetime,
    ),
    CosemSensorEntityDescription(
        key="clock_synced",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        interface=InterfaceClass.DATA,
        obis=ObisCode(0, 0, 96, 2, 12),
        scan_interval=timedelta(hours=1),
        translation_key="clock_synced",
        value_fn=parse_dlms_datetime,
    ),
    CosemSensorEntityDescription(
        key="front_cover_opened",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        interface=InterfaceClass.DATA,
        obis=ObisCode(0, 0, 96, 20, 1),
        scan_interval=timedelta(hours=1),
        translation_key="front_cover_opened",
        value_fn=parse_dlms_datetime,
    ),
    CosemSensorEntityDescription(
        key="terminals_cover_opened",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        interface=InterfaceClass.DATA,
        obis=ObisCode(0, 0, 96, 20, 6),
        scan_interval=timedelta(hours=1),
        translation_key="terminals_cover_opened",
        value_fn=parse_dlms_datetime,
    ),
    CosemSensorEntityDescription(
        key="magnetic_field_detected",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        interface=InterfaceClass.DATA,
        obis=ObisCode(0, 0, 96, 20, 16),
        scan_interval=timedelta(hours=1),
        translation_key="magnetic_field_detected",
        value_fn=parse_dlms_datetime,
    ),
)


class CosemSensor(CosemEntity, SensorEntity):
    """Represents the COSEM sensor platform."""

    entity_description: CosemSensorEntityDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.entity_description.value_fn(
            self.coordinator.data.get(self.entity_description.key)
        )
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DlmsCosemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        CosemSensor(coordinator, description) for description in SENSOR_TYPES
    )
    return True

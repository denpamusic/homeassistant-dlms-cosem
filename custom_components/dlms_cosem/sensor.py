"""Platform for the sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from dlms_cosem import cosem, enumerations
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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .dlms_cosem import DlmsConnection

SCAN_INTERVAL = timedelta(seconds=15)
PARALLEL_UPDATES = 1


@dataclass
class DlmsEntityAdditionalKeys:
    """Additional keys for DLMS entity description."""

    obis: cosem.Obis
    value_fn: Callable


@dataclass
class DlmsSensorEntityDescription(SensorEntityDescription, DlmsEntityAdditionalKeys):
    """Describes DLMS sensor entity."""

    attribute: int = 2
    interface: enumerations.CosemInterface = enumerations.CosemInterface.REGISTER


SENSOR_TYPES: tuple[DlmsSensorEntityDescription, ...] = (
    DlmsSensorEntityDescription(
        key="current_l1",
        name="Current L1",
        obis=cosem.Obis(1, 0, 31, 7, 0),
        value_fn=lambda x: x / 1000,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    DlmsSensorEntityDescription(
        key="current_l2",
        name="Current L2",
        obis=cosem.Obis(1, 0, 51, 7, 0),
        value_fn=lambda x: x / 1000,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    DlmsSensorEntityDescription(
        key="current_l3",
        name="Current L3",
        obis=cosem.Obis(1, 0, 71, 7, 0),
        value_fn=lambda x: x / 1000,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    DlmsSensorEntityDescription(
        key="voltage_l1",
        name="Voltage L1",
        obis=cosem.Obis(1, 0, 32, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    DlmsSensorEntityDescription(
        key="voltage_l2",
        name="Voltage L2",
        obis=cosem.Obis(1, 0, 52, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    DlmsSensorEntityDescription(
        key="voltage_l3",
        name="Voltage L3",
        obis=cosem.Obis(1, 0, 72, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    DlmsSensorEntityDescription(
        key="active_power_total",
        name="Active power total",
        obis=cosem.Obis(1, 0, 1, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    DlmsSensorEntityDescription(
        key="active_power_l1",
        name="Active power L1",
        obis=cosem.Obis(1, 0, 21, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    DlmsSensorEntityDescription(
        key="active_power_l2",
        name="Active power L2",
        obis=cosem.Obis(1, 0, 41, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    DlmsSensorEntityDescription(
        key="active_power_l3",
        name="Active power L3",
        obis=cosem.Obis(1, 0, 61, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    DlmsSensorEntityDescription(
        key="power_factor_total",
        name="Power factor total",
        obis=cosem.Obis(1, 0, 13, 7, 0),
        value_fn=lambda x: x / 1000,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    DlmsSensorEntityDescription(
        key="power_factor_l1",
        name="Power factor L1",
        obis=cosem.Obis(1, 0, 33, 7, 0),
        value_fn=lambda x: x / 1000,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    DlmsSensorEntityDescription(
        key="power_factor_l2",
        name="Power factor L2",
        obis=cosem.Obis(1, 0, 53, 7, 0),
        value_fn=lambda x: x / 1000,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    DlmsSensorEntityDescription(
        key="power_factor_l3",
        name="Power factor L3",
        obis=cosem.Obis(1, 0, 73, 7, 0),
        value_fn=lambda x: x / 1000,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    DlmsSensorEntityDescription(
        key="active_energy_total",
        name="Active energy total",
        obis=cosem.Obis(1, 0, 1, 8, 0),
        value_fn=lambda x: x / 1000,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    DlmsSensorEntityDescription(
        key="active_energy_tariff1",
        name="Active energy tariff 1",
        obis=cosem.Obis(1, 0, 1, 8, 1),
        value_fn=lambda x: x / 1000,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    DlmsSensorEntityDescription(
        key="active_energy_tariff2",
        name="Active energy tariff 2",
        obis=cosem.Obis(1, 0, 1, 8, 2),
        value_fn=lambda x: x / 1000,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    DlmsSensorEntityDescription(
        key="frequency",
        name="Frequency",
        obis=cosem.Obis(1, 0, 14, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    DlmsSensorEntityDescription(
        key="internal_temperature",
        name="Internal temperature",
        obis=cosem.Obis(0, 0, 96, 9, 0),
        value_fn=lambda x: x,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
)


class DlmsSensor(SensorEntity):
    """Represents DLMS sensor platform."""

    _connection: DlmsConnection
    entity_description: DlmsSensorEntityDescription

    def __init__(
        self, connection: DlmsConnection, description: DlmsSensorEntityDescription
    ):
        """Initialize DLMS sensor object."""
        self._connection = connection
        self.entity_description = description

    def update(self) -> None:
        """Update entity state."""
        response = self._connection.get(
            cosem.CosemAttribute(
                interface=self.entity_description.interface,
                instance=self.entity_description.obis,
                attribute=self.entity_description.attribute,
            )
        )
        self._attr_native_value = (
            response if response is None else self.entity_description.value_fn(response)
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self._connection.device_info

    @property
    def unique_id(self) -> str:
        """A unique identifier for this entity."""
        return f"{self._connection.entry.unique_id}-{self.entity_description.key}"

    @property
    def available(self) -> bool:
        """If entity is available."""
        return not self._connection.disconnected.is_set()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the sensor platform."""
    connection: DlmsConnection = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        DlmsSensor(connection, description) for description in SENSOR_TYPES
    )

    return True

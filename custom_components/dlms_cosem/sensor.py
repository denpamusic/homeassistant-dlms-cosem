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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import DEFAULT_ATTRIBUTE, DOMAIN, SIGNAL_RECONNECTED
from .dlms_cosem import DlmsConnection

SCAN_INTERVAL = timedelta(seconds=15)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3)
PARALLEL_UPDATES = 1


@dataclass(kw_only=True, slots=True)
class CosemSensorEntityDescription(SensorEntityDescription):
    """Describes the COSEM sensor entity."""

    obis: cosem.Obis
    value_fn: Callable
    attribute: int = DEFAULT_ATTRIBUTE
    interface: enumerations.CosemInterface = enumerations.CosemInterface.REGISTER


SENSOR_TYPES: tuple[CosemSensorEntityDescription, ...] = (
    CosemSensorEntityDescription(
        key="current_l1",
        name="Current L1",
        obis=cosem.Obis(1, 0, 31, 7, 0),
        value_fn=lambda x: x / 1000,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    CosemSensorEntityDescription(
        key="current_l2",
        name="Current L2",
        obis=cosem.Obis(1, 0, 51, 7, 0),
        value_fn=lambda x: x / 1000,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    CosemSensorEntityDescription(
        key="current_l3",
        name="Current L3",
        obis=cosem.Obis(1, 0, 71, 7, 0),
        value_fn=lambda x: x / 1000,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    CosemSensorEntityDescription(
        key="voltage_l1",
        name="Voltage L1",
        obis=cosem.Obis(1, 0, 32, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    CosemSensorEntityDescription(
        key="voltage_l2",
        name="Voltage L2",
        obis=cosem.Obis(1, 0, 52, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    CosemSensorEntityDescription(
        key="voltage_l3",
        name="Voltage L3",
        obis=cosem.Obis(1, 0, 72, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    CosemSensorEntityDescription(
        key="active_power_total",
        name="Active power total",
        obis=cosem.Obis(1, 0, 1, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    CosemSensorEntityDescription(
        key="active_power_l1",
        name="Active power L1",
        obis=cosem.Obis(1, 0, 21, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    CosemSensorEntityDescription(
        key="active_power_l2",
        name="Active power L2",
        obis=cosem.Obis(1, 0, 41, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    CosemSensorEntityDescription(
        key="active_power_l3",
        name="Active power L3",
        obis=cosem.Obis(1, 0, 61, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    CosemSensorEntityDescription(
        key="power_factor_total",
        name="Power factor total",
        obis=cosem.Obis(1, 0, 13, 7, 0),
        value_fn=lambda x: x / 1000,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    CosemSensorEntityDescription(
        key="power_factor_l1",
        name="Power factor L1",
        obis=cosem.Obis(1, 0, 33, 7, 0),
        value_fn=lambda x: x / 1000,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    CosemSensorEntityDescription(
        key="power_factor_l2",
        name="Power factor L2",
        obis=cosem.Obis(1, 0, 53, 7, 0),
        value_fn=lambda x: x / 1000,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    CosemSensorEntityDescription(
        key="power_factor_l3",
        name="Power factor L3",
        obis=cosem.Obis(1, 0, 73, 7, 0),
        value_fn=lambda x: x / 1000,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    CosemSensorEntityDescription(
        key="active_energy_total",
        name="Active energy total",
        obis=cosem.Obis(1, 0, 1, 8, 0),
        value_fn=lambda x: x / 1000,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    CosemSensorEntityDescription(
        key="active_energy_tariff1",
        name="Active energy tariff 1",
        obis=cosem.Obis(1, 0, 1, 8, 1),
        value_fn=lambda x: x / 1000,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    CosemSensorEntityDescription(
        key="active_energy_tariff2",
        name="Active energy tariff 2",
        obis=cosem.Obis(1, 0, 1, 8, 2),
        value_fn=lambda x: x / 1000,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    CosemSensorEntityDescription(
        key="frequency",
        name="Frequency",
        obis=cosem.Obis(1, 0, 14, 7, 0),
        value_fn=lambda x: x / 100,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    CosemSensorEntityDescription(
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


class CosemSensor(SensorEntity):
    """Represents the COSEM sensor platform."""

    _attr_cosem_attribute: cosem.CosemAttribute
    _connection: DlmsConnection
    entity_description: CosemSensorEntityDescription

    def __init__(
        self, connection: DlmsConnection, description: CosemSensorEntityDescription
    ):
        """Initialize the COSEM sensor object."""
        self._connection = connection
        self.entity_description = description
        self._attr_device_info = connection.device_info
        self._attr_unique_id = f"{connection.entry.unique_id}-{description.key}"
        self._attr_cosem_attribute = cosem.CosemAttribute(
            interface=self.entity_description.interface,
            instance=self.entity_description.obis,
            attribute=self.entity_description.attribute,
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Update entity state."""
        response = await self._connection.async_get(self.cosem_attribute)
        self._attr_native_value = (
            response if response is None else self.entity_description.value_fn(response)
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RECONNECTED, self._reconnect_callback
            )
        )
        await super().async_added_to_hass()

    @callback
    def _reconnect_callback(self) -> None:
        """Schedules update after the reconnect."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def available(self) -> bool:
        """If entity is available."""
        return not self._connection.disconnected.is_set()

    @property
    def cosem_attribute(self) -> cosem.CosemAttribute:
        """Returns COSEM attribute instance."""
        return self._attr_cosem_attribute


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the sensor platform."""
    connection: DlmsConnection = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [CosemSensor(connection, description) for description in SENSOR_TYPES],
        update_before_add=True,
    )
    return True

"""Test DLMS/COSEM sensor platform."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlms_cosem.coordinator import DlmsCoordinator
from custom_components.dlms_cosem.sensor import (
    SENSOR_TYPES,
    CosemSensor,
    async_setup_entry,
)

from .const import MOCK_COSEM_DATA


async def test_sensor_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: DlmsCoordinator,
) -> None:
    """Test setting up sensor platform from config entry."""
    mock_config_entry.runtime_data = mock_coordinator
    async_add_entities = MagicMock()

    result = await async_setup_entry(hass, mock_config_entry, async_add_entities)
    assert result is True
    async_add_entities.assert_called_once()
    entities = list(async_add_entities.call_args[0][0])
    assert len(entities) == len(SENSOR_TYPES)
    assert all(isinstance(entity, CosemSensor) for entity in entities)


async def test_sensor_value_transformations(
    hass: HomeAssistant,
    mock_coordinator: DlmsCoordinator,
) -> None:
    """Test value_fn transformations and coordinator updates for all sensor types."""
    mock_coordinator.data = dict(MOCK_COSEM_DATA)

    for desc in SENSOR_TYPES:
        sensor = CosemSensor(mock_coordinator, desc)
        sensor.hass = hass

        with patch.object(sensor, "async_write_ha_state") as mock_write:
            sensor._handle_coordinator_update()
            mock_write.assert_called_once()

        raw = MOCK_COSEM_DATA[desc.key]
        native_val = sensor.native_value
        assert native_val is not None

        # Verify transformation logic
        if desc.key in ("current_l1", "current_l2", "current_l3"):
            assert native_val == raw / 1000
        elif desc.key in (
            "voltage_l1",
            "voltage_l2",
            "voltage_l3",
            "active_power_total",
            "active_power_l1",
            "active_power_l2",
            "active_power_l3",
            "apparent_power_l1",
            "apparent_power_l2",
            "apparent_power_l3",
            "apparent_power_total",
            "frequency",
        ):
            assert native_val == raw / 100
        elif desc.key in (
            "power_factor_total",
            "power_factor_l1",
            "power_factor_l2",
            "power_factor_l3",
            "active_energy_total",
            "active_energy_tariff1",
            "active_energy_tariff2",
        ):
            assert native_val == raw / 1000
        elif desc.key in ("active_tariff", "internal_temperature", "uptime"):
            assert native_val == raw
        elif desc.key in (
            "local_time",
            "clock_synced",
            "front_cover_opened",
            "terminals_cover_opened",
            "magnetic_field_detected",
        ):
            assert isinstance(native_val, dt.datetime)

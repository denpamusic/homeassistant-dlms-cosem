"""Test DLMS/COSEM binary sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlms_cosem.binary_sensor import (
    BINARY_SENSOR_TYPES,
    CosemBinarySensor,
    async_setup_entry,
)
from custom_components.dlms_cosem.coordinator import DlmsCoordinator


async def test_binary_sensor_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: DlmsCoordinator,
) -> None:
    """Test setting up binary sensor platform from config entry."""
    mock_config_entry.runtime_data = mock_coordinator
    async_add_entities = MagicMock()

    result = await async_setup_entry(hass, mock_config_entry, async_add_entities)
    assert result is True
    async_add_entities.assert_called_once()
    entities = list(async_add_entities.call_args[0][0])
    assert len(entities) == len(BINARY_SENSOR_TYPES)
    assert isinstance(entities[0], CosemBinarySensor)


async def test_binary_sensor_update_with_error(
    hass: HomeAssistant,
    mock_coordinator: DlmsCoordinator,
) -> None:
    """Test binary sensor coordinator update with error present."""
    desc = BINARY_SENSOR_TYPES[0]
    sensor = CosemBinarySensor(mock_coordinator, desc)
    sensor.hass = hass

    mock_coordinator.data = {"self_test": b"\x01"}
    with patch.object(sensor, "async_write_ha_state") as mock_write:
        sensor._handle_coordinator_update()
        assert sensor.is_on is True
        assert sensor.extra_state_attributes == {"error_codes": "E-01"}
        mock_write.assert_called_once()


async def test_binary_sensor_update_without_error(
    hass: HomeAssistant,
    mock_coordinator: DlmsCoordinator,
) -> None:
    """Test binary sensor coordinator update with no error present."""
    desc = BINARY_SENSOR_TYPES[0]
    sensor = CosemBinarySensor(mock_coordinator, desc)
    sensor.hass = hass

    mock_coordinator.data = {"self_test": b"\x00"}
    with patch.object(sensor, "async_write_ha_state") as mock_write:
        sensor._handle_coordinator_update()
        assert sensor.is_on is False
        assert sensor.extra_state_attributes == {"error_codes": ""}
        mock_write.assert_called_once()

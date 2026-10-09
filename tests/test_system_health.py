"""Test DLMS/COSEM system health platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.system_health import SystemHealthRegistration
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlms_cosem.const import DOMAIN
from custom_components.dlms_cosem.coordinator import DlmsCoordinator
from custom_components.dlms_cosem.system_health import (
    async_register,
    system_health_info,
)

from .const import MOCK_ENTRY_DATA


async def test_system_health_register(hass: HomeAssistant) -> None:
    """Test system health registration."""
    registration = MagicMock(spec=SystemHealthRegistration)
    registration.async_register_info = MagicMock()

    async_register(hass, registration)
    registration.async_register_info.assert_called_once_with(system_health_info)


async def test_system_health_no_entries(hass: HomeAssistant) -> None:
    """Test system health info with no loaded entries."""
    data = await system_health_info(hass)
    assert data == {}


async def test_system_health_single_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: DlmsCoordinator,
) -> None:
    """Test system health info with a single loaded entry."""
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    mock_config_entry.runtime_data = mock_coordinator

    data = await system_health_info(hass)
    assert data["connected"] is True
    assert data["dlms_state"] == "associated"
    assert data["tracked_attributes"] == 0
    assert data["slow_attributes"] == 0
    assert data["requests_count"] == 0
    assert data["successful_reads"] == 0
    assert data["failed_reads"] == 0
    assert data["connection_losses"] == 0
    assert data["connection_loss_at"] == "never"


async def test_system_health_multiple_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: DlmsCoordinator,
) -> None:
    """Test system health info with multiple loaded entries."""
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    mock_config_entry.runtime_data = mock_coordinator

    mock_connection2 = MagicMock()
    mock_connection2.connected = False
    mock_connection2.dlms_state = "disconnected"
    mock_connection2.statistics = MagicMock(
        requests_count=5,
        successful_reads=4,
        failed_reads=1,
        connection_losses=2,
        connection_loss_at="never",
    )
    mock_coordinator2 = DlmsCoordinator(hass, mock_connection2)

    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        title="Meter 2",
        unique_id="87654321",
    )
    entry2.add_to_hass(hass)
    entry2.mock_state(hass, ConfigEntryState.LOADED)
    entry2.runtime_data = mock_coordinator2

    data = await system_health_info(hass)
    assert "Mock Title: True, Meter 2: False" in data["connected"]
    assert "Mock Title: associated, Meter 2: disconnected" in data["dlms_state"]

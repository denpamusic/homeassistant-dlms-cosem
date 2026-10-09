"""Test the DLMS/COSEM data coordinator."""

from __future__ import annotations

from datetime import timedelta
import time
from unittest.mock import AsyncMock, MagicMock

from dlms_cosem.client import DataResultError
from dlms_cosem.exceptions import CommunicationError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest

from custom_components.dlms_cosem.const import (
    COSEM_EQUIPMENT_ID,
    COSEM_LOGICAL_DEVICE_NAME,
    COSEM_SOFTWARE_PACKAGE,
    DEFAULT_SCAN_INTERVAL,
)
from custom_components.dlms_cosem.coordinator import (
    MAX_SLOW_ATTRIBUTES_PER_POLL,
    RETRY_INTERVALS,
    DlmsCoordinator,
    TrackedAttribute,
)


async def test_coordinator_init(
    hass: HomeAssistant, mock_connection: MagicMock
) -> None:
    """Test coordinator initialization and basic properties."""
    coordinator = DlmsCoordinator(hass, mock_connection)
    assert coordinator.update_interval == DEFAULT_SCAN_INTERVAL
    assert coordinator.tracked_attributes_count == 0
    assert coordinator.slow_attributes_count == 0
    assert coordinator.dlms_state == "associated"
    assert coordinator.statistics is mock_connection.statistics


async def test_coordinator_register_unregister_attribute(
    hass: HomeAssistant, mock_connection: MagicMock
) -> None:
    """Test registering and unregistering attributes."""
    coordinator = DlmsCoordinator(hass, mock_connection)

    # Register fast attribute (no scan interval)
    coordinator.async_register_attribute("fast_attr", COSEM_EQUIPMENT_ID)
    assert coordinator.tracked_attributes_count == 1
    assert coordinator.slow_attributes_count == 0

    # Register slow attribute
    coordinator.async_register_attribute(
        "slow_attr", COSEM_SOFTWARE_PACKAGE, scan_interval=timedelta(minutes=5)
    )
    assert coordinator.tracked_attributes_count == 2
    assert coordinator.slow_attributes_count == 1

    # Register very slow attribute
    coordinator.async_register_attribute(
        "very_slow_attr", COSEM_LOGICAL_DEVICE_NAME, scan_interval=timedelta(hours=1)
    )
    assert coordinator.tracked_attributes_count == 3
    assert coordinator.slow_attributes_count == 2

    # Unregister attribute
    coordinator.async_unregister_attribute("slow_attr")
    assert coordinator.tracked_attributes_count == 2
    assert coordinator.slow_attributes_count == 1

    # Unregister nonexistent attribute should not error
    coordinator.async_unregister_attribute("nonexistent")
    assert coordinator.tracked_attributes_count == 2


async def test_coordinator_connect_backoff(
    hass: HomeAssistant, mock_connection: MagicMock
) -> None:
    """Test connection retry backoff logic."""
    coordinator = DlmsCoordinator(hass, mock_connection)
    mock_connection.async_connect = AsyncMock(
        side_effect=CommunicationError("Connection error")
    )

    # Attempt 0 -> retry after 30s
    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_connect()
    assert exc_info.value.retry_after == RETRY_INTERVALS[0].total_seconds()
    assert coordinator._retry_attempt == 1

    # Attempt 1 -> retry after 1m
    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_connect()
    assert exc_info.value.retry_after == RETRY_INTERVALS[1].total_seconds()
    assert coordinator._retry_attempt == 2

    # Attempt 2 -> retry after 5m
    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_connect()
    assert exc_info.value.retry_after == RETRY_INTERVALS[2].total_seconds()
    assert coordinator._retry_attempt == 2  # capped at max interval

    # Attempt 3 -> capped at 5m
    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_connect()
    assert exc_info.value.retry_after == RETRY_INTERVALS[2].total_seconds()

    # Success resets retry attempt to 0
    mock_connection.async_connect = AsyncMock(return_value=None)
    await coordinator._async_connect()
    assert coordinator._retry_attempt == 0


async def test_coordinator_fetch_attribute_data_result_error(
    hass: HomeAssistant, mock_connection: MagicMock
) -> None:
    """Test fetch attribute when meter returns DataResultError."""
    coordinator = DlmsCoordinator(hass, mock_connection)
    tracked = TrackedAttribute(COSEM_EQUIPMENT_ID)
    mock_connection.async_get = AsyncMock(
        side_effect=DataResultError("Object not found")
    )

    now = time.monotonic()
    result = await coordinator._async_fetch_attribute("key", tracked, now)
    assert result is None
    assert coordinator._last_polled["key"] == now


async def test_coordinator_fetch_attribute_connection_error(
    hass: HomeAssistant, mock_connection: MagicMock
) -> None:
    """Test fetch attribute when connection error occurs."""
    coordinator = DlmsCoordinator(hass, mock_connection)
    tracked = TrackedAttribute(COSEM_EQUIPMENT_ID)
    mock_connection.async_get = AsyncMock(
        side_effect=CommunicationError("Socket closed")
    )

    now = time.monotonic()
    with pytest.raises(UpdateFailed):
        await coordinator._async_fetch_attribute("key", tracked, now)

    mock_connection.async_close.assert_awaited_once()


async def test_coordinator_update_data_loop(
    hass: HomeAssistant, mock_connection: MagicMock
) -> None:
    """Test coordinator polling loop with fast and throttled slow attributes."""
    coordinator = DlmsCoordinator(hass, mock_connection)
    mock_connection.connected = False

    # Attributes setup
    coordinator.async_register_attribute("fast_1", COSEM_EQUIPMENT_ID)
    coordinator.async_register_attribute(
        "slow_1", COSEM_SOFTWARE_PACKAGE, scan_interval=timedelta(minutes=5)
    )
    coordinator.async_register_attribute(
        "slow_2", COSEM_LOGICAL_DEVICE_NAME, scan_interval=timedelta(minutes=5)
    )
    coordinator.async_register_attribute(
        "slow_3", COSEM_EQUIPMENT_ID, scan_interval=timedelta(minutes=5)
    )

    mock_connection.async_get = AsyncMock(return_value="val")

    # First update: all attributes fetched because data is initially empty
    data1 = await coordinator._async_update_data()
    assert mock_connection.async_connect.awaited
    assert data1["fast_1"] == "val"
    assert data1["slow_1"] == "val"
    assert data1["slow_2"] == "val"
    assert data1["slow_3"] == "val"
    coordinator.data = data1

    # Second update immediately: fast_1 fetched, slow attributes skipped (not elapsed)
    mock_connection.async_get.reset_mock()
    data2 = await coordinator._async_update_data()
    assert mock_connection.async_get.call_count == 1
    assert data2["fast_1"] == "val"

    # Simulate slow attributes overdue
    now = time.monotonic()
    coordinator._last_polled["slow_1"] = now - 400
    coordinator._last_polled["slow_2"] = now - 400
    coordinator._last_polled["slow_3"] = now - 400

    # Third update: fast_1 + max 2 slow attributes fetched (slow budget = 2)
    mock_connection.async_get.reset_mock()
    await coordinator._async_update_data()
    # fast_1 (1) + slow_1 (1) + slow_2 (1) = 3 calls, slow_3 skipped
    assert mock_connection.async_get.call_count == 1 + MAX_SLOW_ATTRIBUTES_PER_POLL


async def test_coordinator_shutdown(
    hass: HomeAssistant, mock_connection: MagicMock
) -> None:
    """Test coordinator shutdown closes DLMS connection."""
    coordinator = DlmsCoordinator(hass, mock_connection)
    await coordinator.async_shutdown()
    mock_connection.async_close.assert_awaited_once()

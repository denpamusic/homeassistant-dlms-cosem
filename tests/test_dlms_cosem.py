"""Test DLMS/COSEM connection and protocol utilities."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from dlms_cosem.client import DataResultError
from dlms_cosem.exceptions import CommunicationError
from dlms_cosem.security import LowLevelSecurityAuthentication
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlms_cosem.const import (
    COSEM_EQUIPMENT_ID,
    DEFAULT_MODEL,
    DEFAULT_RETRIES,
    DEFAULT_RETRY_DELAY,
)
from custom_components.dlms_cosem.dlms_cosem import (
    NEVER,
    DlmsClient,
    DlmsConnection,
    DlmsStatistics,
    _load_flag_ids,
    async_decode_flag_id,
    async_decode_logical_device_name,
    async_dlms_datetime_to_ha_datetime,
    async_extract_error_codes,
)

from .const import MOCK_CONFIG_DATA, MOCK_ENTRY_DATA


def test_dlms_statistics() -> None:
    """Test DlmsStatistics dataclass initialization and reset."""
    stats = DlmsStatistics()
    assert stats.requests_count == 0
    assert stats.successful_reads == 0
    assert stats.failed_reads == 0
    assert stats.connection_losses == 0
    assert stats.connection_loss_at == NEVER

    stats.requests_count = 10
    stats.successful_reads = 8
    stats.failed_reads = 2
    stats.connection_losses = 1
    stats.connection_loss_at = dt.datetime.now(dt.UTC)

    stats.reset_transfer_statistics()
    assert stats.requests_count == 0
    assert stats.successful_reads == 0
    assert stats.failed_reads == 0
    assert stats.connection_losses == 1
    assert stats.connection_loss_at != NEVER


async def test_flag_ids_decoding(hass: HomeAssistant) -> None:
    """Test decoding FLAG IDs and logical device names."""
    flag_ids = _load_flag_ids()
    assert isinstance(flag_ids, dict)
    assert "INC" in flag_ids

    # Known flag ID
    mfr = await async_decode_flag_id(hass, "INC")
    assert mfr == flag_ids["INC"]

    # Unknown flag ID raises KeyError
    with pytest.raises(KeyError):
        await async_decode_flag_id(hass, "QQQ")

    # Decode logical device name with formatter (INC)
    mfr, model = await async_decode_logical_device_name(hass, "INC236000000")
    assert mfr == "Incotex"
    assert model == "Mercury 236"

    # Known manufacturer without custom formatter
    mfr, model = await async_decode_logical_device_name(hass, "LGZ123456789")
    assert mfr == "EYKON AG"
    assert model == DEFAULT_MODEL

    # Unknown manufacturer
    mfr, model = await async_decode_logical_device_name(hass, "QQQ999999999")
    assert mfr == "Unknown"
    assert model == DEFAULT_MODEL


def test_extract_error_codes() -> None:
    """Test bitwise extraction of DLMS error codes."""
    # Zero bytes -> no errors
    assert async_extract_error_codes(b"\x00") == []

    # Single bit
    assert async_extract_error_codes(b"\x01") == ["E-01"]

    # Multiple bits
    assert async_extract_error_codes(b"\x05") == ["E-01", "E-03"]

    # Custom prefix
    assert async_extract_error_codes(b"\x02", prefix="ERR-") == ["ERR-02"]

    # Multi-byte bit mask
    assert async_extract_error_codes(b"\x01\x00") == ["E-09"]


def test_dlms_datetime_to_ha_datetime() -> None:
    """Test timezone conversion between DLMS and Home Assistant."""
    # Naive datetime
    naive = dt.datetime(2026, 10, 9, 12, 0, 0)
    assert async_dlms_datetime_to_ha_datetime(naive) == naive

    # Datetime with positive UTC offset (e.g. +03:00)
    # DLMS specification inverts the offset convention
    offset = dt.timezone(dt.timedelta(hours=3))
    aware = dt.datetime(2026, 10, 9, 12, 0, 0, tzinfo=offset)
    converted = async_dlms_datetime_to_ha_datetime(aware)
    expected_tz = dt.timezone(dt.timedelta(hours=-3))
    assert converted.tzinfo == expected_tz


async def test_dlms_client_lifecycle(hass: HomeAssistant) -> None:
    """Test DlmsClient connection, properties, and disconnection."""
    client = DlmsClient(
        hass=hass,
        port="/dev/ttyUSB0",
        password="password",
        physical_address=1,
        read_delay=50,
        read_timeout=5,
    )

    assert bool(client.connected) is False
    assert client.dlms_state == "disconnected"
    assert isinstance(client.authentication, LowLevelSecurityAuthentication)

    mock_blocking = MagicMock()
    mock_blocking.connect = MagicMock()
    mock_blocking.associate = MagicMock()
    mock_blocking.disconnect = MagicMock()
    mock_blocking.release_association = MagicMock()
    mock_blocking.dlms_connection.state.current_state = "ASSOCIATED"

    with patch(
        "custom_components.dlms_cosem.dlms_cosem.BlockingDlmsClient",
        return_value=mock_blocking,
    ):
        await client.async_connect()
        assert bool(client.connected) is True
        assert client.dlms_state == "associated"

        # Calling connect again when already connected is a no-op
        await client.async_connect()

        # Disconnect
        await client.async_disconnect()
        assert bool(client.connected) is False
        assert client.dlms_state == "disconnected"

        # Disconnect when already disconnected is a no-op
        await client.async_disconnect()


async def test_dlms_client_async_get(hass: HomeAssistant) -> None:
    """Test DlmsClient async_get success and error handling."""
    client = DlmsClient(
        hass=hass,
        port="/dev/ttyUSB0",
        password="password",
        physical_address=1,
        read_delay=10,
        read_timeout=5,
    )

    # When client is not connected, async_get returns None
    assert await client.async_get(COSEM_EQUIPMENT_ID) is None

    mock_blocking = MagicMock()
    mock_blocking.dlms_connection.state.current_state = "ASSOCIATED"
    # Return A-XDR encoded uint32: 42
    mock_blocking.get = MagicMock(return_value=b"\x06\x00\x00\x00\x2a")

    client.client = mock_blocking

    # Successful read
    result = await client.async_get(COSEM_EQUIPMENT_ID)
    assert result == 42
    assert client.statistics.requests_count == 1
    assert client.statistics.successful_reads == 1
    assert client.statistics.failed_reads == 0

    # DataResultError handling
    mock_blocking.get = MagicMock(side_effect=DataResultError("Object undefined"))
    with pytest.raises(DataResultError):
        await client.async_get(COSEM_EQUIPMENT_ID)
    assert client.statistics.requests_count == 2
    assert client.statistics.successful_reads == 1
    assert client.statistics.failed_reads == 1
    assert client.statistics.connection_losses == 0

    # Other exception (communication failure)
    mock_blocking.get = MagicMock(side_effect=CommunicationError("Connection broken"))
    with pytest.raises(CommunicationError):
        await client.async_get(COSEM_EQUIPMENT_ID)
    assert client.statistics.requests_count == 3
    assert client.statistics.failed_reads == 2
    assert client.statistics.connection_losses == 1
    assert client.statistics.connection_loss_at != NEVER


async def test_dlms_connection(hass: HomeAssistant) -> None:
    """Test DlmsConnection wrapper class."""
    entry = MockConfigEntry(
        domain="dlms_cosem",
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345678",
    )
    entry.add_to_hass(hass)

    conn = DlmsConnection(hass, entry)
    assert not conn.connected
    assert conn.dlms_state == "disconnected"
    assert conn.manufacturer == "Incotex"
    assert conn.model == "Mercury 236"
    assert conn.sw_version == "1.0.0"
    assert conn.equipment_id == "12345678"
    assert isinstance(conn.statistics, DlmsStatistics)

    with (
        patch.object(
            conn.client, "async_connect", new_callable=AsyncMock
        ) as mock_connect,
        patch.object(
            conn.client, "async_disconnect", new_callable=AsyncMock
        ) as mock_disconnect,
        patch.object(
            conn.client, "async_get", new_callable=AsyncMock, return_value=123
        ),
    ):
        await conn.async_connect()
        mock_connect.assert_awaited_once()

        val = await conn.async_get(COSEM_EQUIPMENT_ID)
        assert val == 123

        # Close when not connected
        await conn.async_close()
        mock_disconnect.assert_not_awaited()

        # Close when connected
        conn.client.client = MagicMock()  # makes conn.connected True
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await conn.async_close()
            mock_disconnect.assert_awaited_once()
            mock_sleep.assert_awaited_once()


async def test_dlms_connection_async_check(hass: HomeAssistant) -> None:
    """Test DlmsConnection.async_check static method."""
    with patch.object(
        DlmsClient, "async_connect", new_callable=AsyncMock
    ) as mock_connect:
        client = await DlmsConnection.async_check(hass, dict(MOCK_CONFIG_DATA))
        assert isinstance(client, DlmsClient)
        mock_connect.assert_awaited_once()


async def test_dlms_client_retries_and_timeout(hass: HomeAssistant) -> None:
    """Test DlmsClient retries configuration and async_get total timeout calculation."""
    client = DlmsClient(
        hass=hass,
        port="/dev/ttyUSB0",
        password="password",
        physical_address=1,
        read_delay=10,
        read_timeout=5,
        retries=2,
        retry_delay=0.5,
    )
    assert client._retries == 2
    assert client._retry_delay == 0.5

    # Check defaults
    client_default = DlmsClient(
        hass=hass,
        port="/dev/ttyUSB0",
        password="password",
        physical_address=1,
        read_delay=10,
    )
    assert client_default._retries == DEFAULT_RETRIES
    assert client_default._retry_delay == DEFAULT_RETRY_DELAY

    mock_blocking = MagicMock()
    mock_blocking.get = MagicMock(return_value=b"\x06\x00\x00\x00\x01")
    client.client = mock_blocking

    with patch("asyncio.timeout") as mock_timeout:
        mock_timeout.return_value.__aenter__ = AsyncMock()
        mock_timeout.return_value.__aexit__ = AsyncMock()
        await client.async_get(COSEM_EQUIPMENT_ID)
        # Expected total_timeout: 5 * (2 + 1) + (0.5 * 2) + 2 = 15 + 1.0 + 2 = 18.0
        mock_timeout.assert_called_once_with(18.0)

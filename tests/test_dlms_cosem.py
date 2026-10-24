"""Test DLMS/COSEM connection and protocol utilities."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlms_cosem.const import (
    CONF_HARDWARE_INTERFACE,
    CONF_READ_DELAY,
    CONF_READ_TIMEOUT,
    CONF_RETRIES,
    CONF_RETRY_DELAY,
    COSEM_EQUIPMENT_ID,
    DEFAULT_MODEL,
    DEFAULT_PHYSICAL_ADDRESS,
    DEFAULT_READ_DELAY,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_RETRIES,
    DEFAULT_RETRY_DELAY,
    HardwareInterface,
)
from custom_components.dlms_cosem.dlms_cosem import (
    INTERFACE_CONFIG,
    NEVER,
    DlmsConnection,
    DlmsStatistics,
    _load_flag_ids,
    async_decode_flag_id,
    async_decode_logical_device_name,
    async_extract_error_codes,
    async_get_dlms_client,
    parse_dlms_datetime,
)
from microdlms import CommunicationError, DataAccessError, DataAccessResult

from .const import MOCK_ENTRY_DATA


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


def test_parse_dlms_datetime() -> None:
    """Test parsing DLMS 12-byte date-time octet strings."""
    assert parse_dlms_datetime(None) is None
    assert parse_dlms_datetime(b"") is None

    # Valid DLMS datetime: 2026-10-10 19:23:35 UTC+3 (deviation = 180 min = 0x00B4)
    data = bytes.fromhex("07ea0a0a061317230000b400")
    result = parse_dlms_datetime(data)
    assert result is not None
    assert result.year == 2026
    assert result.month == 10
    assert result.day == 10
    assert result.hour == 19
    assert result.minute == 23
    assert result.second == 35
    assert result.tzinfo == dt.timezone(dt.timedelta(minutes=180))

    # Unspecified date returns None
    unspecified = bytes.fromhex("ffffffffffffffff0000b400")
    assert parse_dlms_datetime(unspecified) is None


async def test_async_get_dlms_client() -> None:
    """Test async_get_dlms_client helper creates and connects client."""
    mock_async_client = MagicMock()
    mock_async_client.connect = AsyncMock()

    with patch(
        "custom_components.dlms_cosem.dlms_cosem.AsyncMeterClient",
        return_value=mock_async_client,
    ) as mock_cls:
        client = await async_get_dlms_client(
            port="/dev/ttyUSB0",
            password="password",
            physical_address=1,
            timeout=5,
        )
        assert client is mock_async_client
        mock_cls.assert_called_once_with(
            port="/dev/ttyUSB0",
            password="password",
            server_physical_address=1,
            timeout=5,
        )
        mock_async_client.connect.assert_awaited_once()

        # Test defaults
        mock_cls.reset_mock()
        await async_get_dlms_client(port="/dev/ttyUSB0")
        mock_cls.assert_called_once_with(
            port="/dev/ttyUSB0",
            password="111111",
            server_physical_address=DEFAULT_PHYSICAL_ADDRESS,
            timeout=DEFAULT_READ_TIMEOUT,
        )


async def test_dlms_connection_lifecycle(hass: HomeAssistant) -> None:
    """Test DlmsConnection connection, properties, and disconnection."""
    entry = MockConfigEntry(
        domain="dlms_cosem",
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345678",
    )
    entry.add_to_hass(hass)

    conn = DlmsConnection(hass, entry)

    assert bool(conn.connected) is False
    assert conn.dlms_state == "disconnected"
    assert conn.port == "/dev/ttyUSB0"
    assert conn.password == "111111"
    assert conn.physical_address == 1
    assert conn.hardware_config == INTERFACE_CONFIG[HardwareInterface.OPTICAL]
    assert conn.read_delay == 0.25
    assert conn.read_timeout == 5
    assert conn.manufacturer == "Incotex"
    assert conn.model == "Mercury 236"
    assert conn.sw_version == "1.0.0"
    assert conn.equipment_id == "12345678"
    assert isinstance(conn.statistics, DlmsStatistics)

    mock_async_client = MagicMock()
    mock_async_client.connect = AsyncMock()
    mock_async_client.disconnect = AsyncMock()
    mock_async_client.is_connected = True
    mock_async_client.session.state.name = "ASSOCIATED"

    with patch(
        "custom_components.dlms_cosem.dlms_cosem.async_get_dlms_client",
        new_callable=AsyncMock,
        return_value=mock_async_client,
    ) as mock_get_client:
        await conn.async_connect()
        assert bool(conn.connected) is True
        assert conn.dlms_state == "associated"
        mock_get_client.assert_awaited_once_with(
            port="/dev/ttyUSB0",
            password="111111",
            physical_address=1,
            timeout=5,
        )

        # Calling connect again when already connected is a no-op
        await conn.async_connect()
        mock_get_client.assert_awaited_once()

        # Disconnect
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await conn.async_disconnect()
            assert bool(conn.connected) is False
            assert conn.dlms_state == "disconnected"
            mock_async_client.disconnect.assert_awaited_once()
            mock_sleep.assert_awaited_once()

        # Disconnect when already disconnected is a no-op
        await conn.async_disconnect()


async def test_dlms_connection_async_get(hass: HomeAssistant) -> None:
    """Test DlmsConnection async_get success and error handling."""
    entry = MockConfigEntry(
        domain="dlms_cosem",
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345678",
    )
    entry.add_to_hass(hass)

    conn = DlmsConnection(hass, entry)

    # When client is not connected, async_get returns None
    assert await conn.async_get(COSEM_EQUIPMENT_ID) is None

    mock_async = MagicMock()
    mock_async.get = AsyncMock(return_value=42)
    conn.client = mock_async

    # Successful read
    result = await conn.async_get(COSEM_EQUIPMENT_ID)
    assert result == 42
    assert conn.statistics.requests_count == 1
    assert conn.statistics.successful_reads == 1
    assert conn.statistics.failed_reads == 0

    # DataAccessError handling
    mock_async.get = AsyncMock(
        side_effect=DataAccessError(
            DataAccessResult.OBJECT_UNDEFINED, "Object undefined"
        )
    )
    with pytest.raises(DataAccessError):
        await conn.async_get(COSEM_EQUIPMENT_ID)
    assert conn.statistics.requests_count == 2
    assert conn.statistics.successful_reads == 1
    assert conn.statistics.failed_reads == 1
    assert conn.statistics.connection_losses == 0

    # Other exception (communication failure)
    mock_async.get = AsyncMock(side_effect=CommunicationError("Connection broken"))
    with pytest.raises(CommunicationError):
        await conn.async_get(COSEM_EQUIPMENT_ID)
    assert conn.statistics.requests_count == 3
    assert conn.statistics.failed_reads == 2
    assert conn.statistics.connection_losses == 1
    assert conn.statistics.connection_loss_at != NEVER


async def test_dlms_connection_retries_and_timeout(hass: HomeAssistant) -> None:
    """Test DlmsConnection retries configuration and async_get timeout."""
    entry = MockConfigEntry(
        domain="dlms_cosem",
        data=dict(MOCK_ENTRY_DATA),
        options={
            CONF_READ_DELAY: 0.1,
            CONF_READ_TIMEOUT: 15,
            CONF_RETRIES: 2,
            CONF_RETRY_DELAY: 0.5,
        },
        unique_id="12345678",
    )
    entry.add_to_hass(hass)

    conn = DlmsConnection(hass=hass, entry=entry)
    assert conn.retries == 2
    assert conn.retry_delay == 0.5
    assert conn.read_delay == 0.1
    assert conn.read_timeout == 15

    # Check defaults
    entry_default = MockConfigEntry(
        domain="dlms_cosem",
        data=dict(MOCK_ENTRY_DATA),
        unique_id="87654321",
    )
    conn_default = DlmsConnection(hass=hass, entry=entry_default)
    assert conn_default.retries == DEFAULT_RETRIES
    assert conn_default.retry_delay == DEFAULT_RETRY_DELAY

    mock_async = MagicMock()
    mock_async.get = AsyncMock(return_value=1)
    conn.client = mock_async

    await conn.async_get(COSEM_EQUIPMENT_ID)
    mock_async.get.assert_awaited_once_with(
        COSEM_EQUIPMENT_ID,
        retries=2,
        retry_delay=0.5,
        timeout=15,
    )

    # Test default fallback when entry data is missing values (defaults to OPTICAL)
    entry_empty = MockConfigEntry(domain="dlms_cosem", data={})
    conn_empty = DlmsConnection(hass=hass, entry=entry_empty)
    assert conn_empty.physical_address == DEFAULT_PHYSICAL_ADDRESS
    assert conn_empty.read_delay == 0.25
    assert conn_empty.read_timeout == 5

    # Test fallback when hardware interface is unknown
    entry_unknown_hw = MockConfigEntry(
        domain="dlms_cosem",
        data={CONF_HARDWARE_INTERFACE: "unknown"},
    )
    conn_unknown_hw = DlmsConnection(hass=hass, entry=entry_unknown_hw)
    assert conn_unknown_hw.hardware_config is None
    assert conn_unknown_hw.read_delay == DEFAULT_READ_DELAY
    assert conn_unknown_hw.read_timeout == DEFAULT_READ_TIMEOUT

    # Test options overriding
    entry_with_options = MockConfigEntry(
        domain="dlms_cosem",
        data={**MOCK_ENTRY_DATA, CONF_RETRIES: 4, CONF_RETRY_DELAY: 1.5},
        options={
            CONF_READ_DELAY: 0.1,
            CONF_READ_TIMEOUT: 7.0,
            CONF_RETRIES: 5,
            CONF_RETRY_DELAY: 2.0,
        },
    )
    conn_options = DlmsConnection(hass=hass, entry=entry_with_options)
    assert conn_options.read_delay == 0.1
    assert conn_options.read_timeout == 7.0
    assert conn_options.retries == 5
    assert conn_options.retry_delay == 2.0

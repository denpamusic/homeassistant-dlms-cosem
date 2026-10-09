"""Test the DLMS/COSEM component setup and entry lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from dlms_cosem.exceptions import CommunicationError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_LOGGING_CHANGED
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlms_cosem import (
    DEBUG_LOGGER,
    DEFAULT_LOGGER,
    _async_logging_changed,
    async_migrate_entry,
    async_setup_entry,
)
from custom_components.dlms_cosem.const import (
    CONF_PORT,
    CONF_READ_DELAY,
    DEFAULT_READ_DELAY,
    DOMAIN,
)
from custom_components.dlms_cosem.coordinator import DlmsCoordinator

from .const import MOCK_ENTRY_DATA


async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test successful setup of DLMS config entry."""
    with patch(
        "custom_components.dlms_cosem.DlmsConnection",
        return_value=mock_connection,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, DlmsCoordinator)
    mock_connection.async_connect.assert_awaited_once()


async def test_async_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test setup failure when DLMS connection fails."""
    mock_connection.async_connect = AsyncMock(
        side_effect=CommunicationError("Connection failed")
    )
    with (
        patch(
            "custom_components.dlms_cosem.DlmsConnection",
            return_value=mock_connection,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        mock_config_entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
        await async_setup_entry(hass, mock_config_entry)

    mock_connection.async_close.assert_awaited_once()


async def test_async_logging_changed() -> None:
    """Test logging level change callback."""
    with (
        patch(
            "custom_components.dlms_cosem._LOGGER.isEnabledFor",
            return_value=True,
        ),
        patch("structlog.configure") as mock_configure,
    ):
        _async_logging_changed()
        mock_configure.assert_called_once_with(wrapper_class=DEBUG_LOGGER)

    with (
        patch(
            "custom_components.dlms_cosem._LOGGER.isEnabledFor",
            return_value=False,
        ),
        patch("structlog.configure") as mock_configure,
    ):
        _async_logging_changed()
        mock_configure.assert_called_once_with(wrapper_class=DEFAULT_LOGGER)


async def test_async_logging_changed_bus_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test logging changed event fired on bus."""
    with (
        patch(
            "custom_components.dlms_cosem.DlmsConnection",
            return_value=mock_connection,
        ),
        patch("structlog.configure") as mock_configure,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_LOGGING_CHANGED)
        await hass.async_block_till_done()

    assert mock_configure.call_count >= 1


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test unloading a config entry."""
    with patch(
        "custom_components.dlms_cosem.DlmsConnection",
        return_value=mock_connection,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED

    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED


async def test_async_migrate_entry(hass: HomeAssistant) -> None:
    """Test entry migration across versions."""
    # Major version > 1 should return False
    entry_v2 = MockConfigEntry(
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        version=2,
        minor_version=0,
    )
    entry_v2.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry_v2) is False

    # Minor version 1 -> 3
    entry_v1_1 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: "/dev/ttyUSB0"},
        version=1,
        minor_version=1,
    )
    entry_v1_1.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry_v1_1) is True
    assert entry_v1_1.minor_version == 3
    assert entry_v1_1.data[CONF_READ_DELAY] == DEFAULT_READ_DELAY

    # Minor version 2 with host/port -> 3
    entry_v1_2 = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.100", CONF_PORT: 4059, CONF_READ_DELAY: 250},
        version=1,
        minor_version=2,
    )
    entry_v1_2.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry_v1_2) is True
    assert entry_v1_2.minor_version == 3
    assert entry_v1_2.data[CONF_PORT] == "socket://192.168.1.100:4059"
    assert "host" not in entry_v1_2.data

    # Minor version 2 with host and non-int port
    entry_v1_2_str = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.100", CONF_PORT: "socket://192.168.1.100:4059"},
        version=1,
        minor_version=2,
    )
    entry_v1_2_str.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry_v1_2_str) is True
    assert entry_v1_2_str.minor_version == 3

    # Minor version 3 without changes
    entry_v1_3 = MockConfigEntry(
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        version=1,
        minor_version=3,
    )
    entry_v1_3.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry_v1_3) is True
    assert entry_v1_3.minor_version == 3

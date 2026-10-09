"""Global fixtures for DLMS/COSEM integration tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlms_cosem.const import DOMAIN
from custom_components.dlms_cosem.coordinator import DlmsCoordinator
from custom_components.dlms_cosem.dlms_cosem import DlmsConnection, DlmsStatistics

from .const import MOCK_COSEM_DATA, MOCK_ENTRY_DATA


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Enable custom integrations for all tests."""
    return


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock DLMS/COSEM config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345678",
        version=1,
        minor_version=3,
        entry_id="mock_entry_id",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_connection(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MagicMock:
    """Create a mock DLMS connection."""
    conn = MagicMock(spec=DlmsConnection)
    conn.entry = mock_config_entry
    conn.hass = hass
    conn.connected = True
    conn.dlms_state = "associated"
    conn.statistics = DlmsStatistics()
    conn.manufacturer = "Incotex"
    conn.model = "Mercury 236"
    conn.sw_version = "1.0.0"
    conn.equipment_id = "12345678"

    conn.async_connect = AsyncMock()
    conn.async_close = AsyncMock()

    async def _mock_get(attribute: object) -> object:
        for key, val in MOCK_COSEM_DATA.items():
            attr_repr = str(attribute)
            if key in attr_repr:
                return val
        return 100

    conn.async_get = AsyncMock(side_effect=_mock_get)
    return conn


@pytest.fixture
def mock_coordinator(
    hass: HomeAssistant, mock_connection: MagicMock
) -> DlmsCoordinator:
    """Create a mock DLMS coordinator."""
    coordinator = DlmsCoordinator(hass, mock_connection)
    coordinator.data = dict(MOCK_COSEM_DATA)
    return coordinator

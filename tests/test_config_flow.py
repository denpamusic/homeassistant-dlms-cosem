"""Test the DLMS/COSEM config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from dlms_cosem.exceptions import CommunicationError
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlms_cosem.config_flow import CannotConnect, validate_input
from custom_components.dlms_cosem.const import (
    CONF_PASSWORD,
    CONF_PHYSICAL_ADDRESS,
    CONF_PORT,
    CONF_READ_DELAY,
    COSEM_EQUIPMENT_ID,
    COSEM_LOGICAL_DEVICE_NAME,
    COSEM_SOFTWARE_PACKAGE,
    DOMAIN,
)
from custom_components.dlms_cosem.dlms_cosem import DlmsClient

from .const import MOCK_CONFIG_DATA, MOCK_ENTRY_DATA


@pytest.fixture
def mock_flow_client() -> MagicMock:
    """Create a mock DLMS client for config flow."""
    client = MagicMock(spec=DlmsClient)
    client.connected = True
    client.async_connect = AsyncMock()
    client.async_disconnect = AsyncMock()

    async def _mock_get(attribute: object) -> object:
        if attribute == COSEM_LOGICAL_DEVICE_NAME:
            return b"INC236000000"
        if attribute == COSEM_EQUIPMENT_ID:
            return "12345678"
        if attribute == COSEM_SOFTWARE_PACKAGE:
            return "1.0.0"
        return "mock_val"

    client.async_get = AsyncMock(side_effect=_mock_get)
    return client


async def test_validate_input_success(
    hass: HomeAssistant, mock_flow_client: MagicMock
) -> None:
    """Test successful input validation."""
    with patch(
        "custom_components.dlms_cosem.dlms_cosem.DlmsConnection.async_check",
        return_value=mock_flow_client,
    ):
        result = await validate_input(hass, dict(MOCK_CONFIG_DATA))
        assert result is mock_flow_client


async def test_validate_input_failure(hass: HomeAssistant) -> None:
    """Test failed input validation."""
    with (
        patch(
            "custom_components.dlms_cosem.dlms_cosem.DlmsConnection.async_check",
            side_effect=CommunicationError("Failed"),
        ),
        pytest.raises(CannotConnect),
    ):
        await validate_input(hass, dict(MOCK_CONFIG_DATA))


async def test_flow_user_form(hass: HomeAssistant) -> None:
    """Test initial user form presentation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_flow_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test user step with connection failure."""
    with patch(
        "custom_components.dlms_cosem.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=dict(MOCK_CONFIG_DATA),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_unknown_exception(hass: HomeAssistant) -> None:
    """Test user step with unexpected exception."""
    with patch(
        "custom_components.dlms_cosem.config_flow.validate_input",
        side_effect=RuntimeError("Unexpected"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=dict(MOCK_CONFIG_DATA),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_flow_user_success(
    hass: HomeAssistant, mock_flow_client: MagicMock
) -> None:
    """Test full successful config flow through identify to entry creation."""
    with (
        patch(
            "custom_components.dlms_cosem.config_flow.validate_input",
            return_value=mock_flow_client,
        ),
        patch(
            "custom_components.dlms_cosem.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=dict(MOCK_CONFIG_DATA),
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "identify"

        # Advance progress task
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Incotex Mercury 236"
        assert result["data"][CONF_PORT] == "/dev/ttyUSB0"
        assert result["result"].unique_id == "12345678"


async def test_flow_identify_failure(
    hass: HomeAssistant, mock_flow_client: MagicMock
) -> None:
    """Test identify step error handling."""
    mock_flow_client.async_get = AsyncMock(
        side_effect=CommunicationError("Communication failed")
    )
    with patch(
        "custom_components.dlms_cosem.config_flow.validate_input",
        return_value=mock_flow_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=dict(MOCK_CONFIG_DATA),
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "identify_failed"


async def test_flow_already_configured(
    hass: HomeAssistant, mock_flow_client: MagicMock
) -> None:
    """Test abort when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345678",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.dlms_cosem.config_flow.validate_input",
        return_value=mock_flow_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=dict(MOCK_CONFIG_DATA),
        )
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_reconfigure_form(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow displays form with suggested values."""
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_flow_reconfigure_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
) -> None:
    """Test reconfigure flow handles cannot connect error."""
    mock_config_entry.runtime_data = mock_coordinator

    result = await mock_config_entry.start_reconfigure_flow(hass)
    with patch(
        "custom_components.dlms_cosem.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=dict(MOCK_CONFIG_DATA),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_reconfigure_unknown_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
) -> None:
    """Test reconfigure flow handles unexpected exception."""
    mock_config_entry.runtime_data = mock_coordinator

    result = await mock_config_entry.start_reconfigure_flow(hass)
    with patch(
        "custom_components.dlms_cosem.config_flow.validate_input",
        side_effect=RuntimeError("Boom"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=dict(MOCK_CONFIG_DATA),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_flow_reconfigure_client_get_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
    mock_flow_client: MagicMock,
) -> None:
    """Test reconfigure flow handles error reading equipment ID."""
    mock_config_entry.runtime_data = mock_coordinator
    mock_flow_client.async_get = AsyncMock(side_effect=CommunicationError("Read error"))

    result = await mock_config_entry.start_reconfigure_flow(hass)
    with patch(
        "custom_components.dlms_cosem.config_flow.validate_input",
        return_value=mock_flow_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=dict(MOCK_CONFIG_DATA),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_reconfigure_unique_id_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
    mock_flow_client: MagicMock,
) -> None:
    """Test reconfigure flow aborts on unique ID mismatch."""
    mock_config_entry.runtime_data = mock_coordinator
    mock_flow_client.async_get = AsyncMock(return_value="DIFFERENT_SERIAL")

    result = await mock_config_entry.start_reconfigure_flow(hass)
    with patch(
        "custom_components.dlms_cosem.config_flow.validate_input",
        return_value=mock_flow_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=dict(MOCK_CONFIG_DATA),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


async def test_flow_reconfigure_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
    mock_flow_client: MagicMock,
) -> None:
    """Test successful reconfigure flow."""
    mock_config_entry.runtime_data = mock_coordinator

    result = await mock_config_entry.start_reconfigure_flow(hass)
    new_data = {
        CONF_PORT: "/dev/ttyUSB1",
        CONF_PASSWORD: "new_password",
        CONF_PHYSICAL_ADDRESS: 2,
        CONF_READ_DELAY: 300,
    }

    with patch(
        "custom_components.dlms_cosem.config_flow.validate_input",
        return_value=mock_flow_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=new_data,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_PORT] == "/dev/ttyUSB1"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"
    assert mock_config_entry.data[CONF_PHYSICAL_ADDRESS] == 2
    assert mock_config_entry.data[CONF_READ_DELAY] == 300
    mock_flow_client.async_disconnect.assert_awaited()

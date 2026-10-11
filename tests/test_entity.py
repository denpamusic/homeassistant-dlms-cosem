"""Test DLMS/COSEM entity base class and description."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.dlms_cosem.const import DOMAIN
from custom_components.dlms_cosem.coordinator import DlmsCoordinator
from custom_components.dlms_cosem.entity import CosemEntity, CosemEntityDescription
from microdlms import InterfaceClass, ObisCode


async def test_cosem_entity_description() -> None:
    """Test CosemEntityDescription cached property."""
    desc = CosemEntityDescription(
        key="test_key",
        interface=InterfaceClass.DATA,
        obis=ObisCode(0, 0, 96, 1, 0),
        attribute=2,
        scan_interval=timedelta(minutes=5),
        value_fn=lambda x: x,
    )

    attr = desc.cosem_attribute
    assert attr.interface == InterfaceClass.DATA
    assert attr.obis == ObisCode(0, 0, 96, 1, 0)
    assert attr.attribute == 2


async def test_cosem_entity_lifecycle(
    hass: HomeAssistant, mock_coordinator: DlmsCoordinator
) -> None:
    """Test CosemEntity lifecycle callbacks and properties."""
    desc = CosemEntityDescription(
        key="test_metric",
        interface=InterfaceClass.REGISTER,
        obis=ObisCode(1, 0, 1, 8, 0),
        scan_interval=timedelta(seconds=60),
        value_fn=lambda x: x * 2,
    )

    entity = CosemEntity(mock_coordinator, desc)
    entity.hass = hass

    # Unique ID and device info
    assert entity.unique_id == "12345678-test_metric"
    device_info = entity.device_info
    assert device_info["identifiers"] == {(DOMAIN, "12345678")}
    assert device_info["manufacturer"] == "Incotex"
    assert device_info["model"] == "Mercury 236"
    assert device_info["serial_number"] == "12345678"
    assert device_info["sw_version"] == "1.0.0"
    assert device_info["name"] == "Incotex Mercury 236"

    # Added to hass
    with patch.object(mock_coordinator, "async_register_attribute") as mock_reg:
        await entity.async_added_to_hass()
        mock_reg.assert_called_once_with(
            "test_metric", desc.cosem_attribute, timedelta(seconds=60)
        )

    # Will remove from hass
    with patch.object(mock_coordinator, "async_unregister_attribute") as mock_unreg:
        await entity.async_will_remove_from_hass()
        mock_unreg.assert_called_once_with("test_metric")

"""Contains constants for the DLMS integration."""
from __future__ import annotations

from typing import Final

from dlms_cosem import cosem, enumerations

DOMAIN: Final = "dlms_cosem"

# Attributes
ATTR_DATA: Final = "data"
ATTR_EQUIPMENT_ID: Final = "equipment_id"

# Configuration
CONF_HOST: Final = "host"
CONF_PASSWORD: Final = "password"
CONF_PHYSICAL_ADDRESS: Final = "physical_address"
CONF_PORT: Final = "port"

# Defaults
DEFAULT_ATTRIBUTE: Final = 2
DEFAULT_MODEL: Final = "Smart meter"
DEFAULT_PASSWORD: Final = "111111"
DEFAULT_PORT: Final = 23
DEFAULT_SCAN_INTERVAL: Final = 15  # seconds

# Dispatcher signals
SIGNAL_AVAILABLE: Final = "available"

# COSEM attributes
COSEM_EQUIPMENT_ID = cosem.CosemAttribute(
    interface=enumerations.CosemInterface.DATA,
    instance=cosem.Obis(0, 0, 96, 1, 0),
    attribute=DEFAULT_ATTRIBUTE,
)
COSEM_LOGICAL_DEVICE_NAME = cosem.CosemAttribute(
    interface=enumerations.CosemInterface.DATA,
    instance=cosem.Obis(0, 0, 42, 0, 0),
    attribute=DEFAULT_ATTRIBUTE,
)
COSEM_SOFTWARE_PACKAGE = cosem.CosemAttribute(
    interface=enumerations.CosemInterface.DATA,
    instance=cosem.Obis(0, 0, 96, 1, 2),
    attribute=DEFAULT_ATTRIBUTE,
)

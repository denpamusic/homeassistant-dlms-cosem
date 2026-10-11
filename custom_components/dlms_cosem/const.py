"""Contains constants for the DLMS integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from microdlms import CosemAttribute, InterfaceClass, ObisCode

DOMAIN: Final = "dlms_cosem"

# Attributes
ATTR_EQUIPMENT_ID: Final = "equipment_id"

# Configuration
CONF_PASSWORD: Final = "password"
CONF_PHYSICAL_ADDRESS: Final = "physical_address"
CONF_PORT: Final = "port"
CONF_READ_DELAY: Final = "read_delay"

# Defaults
DEFAULT_ATTRIBUTE: Final = 2
DEFAULT_MODEL: Final = "Smart meter"
DEFAULT_PASSWORD: Final = "111111"
DEFAULT_READ_DELAY: Final = 250  # milliseconds
DEFAULT_RETRIES: Final = 3
DEFAULT_RETRY_DELAY: Final = 0.5  # seconds
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=30)

# COSEM attributes
COSEM_EQUIPMENT_ID = CosemAttribute(
    interface=InterfaceClass.DATA,
    obis=ObisCode(0, 0, 96, 1, 0),
    attribute=DEFAULT_ATTRIBUTE,
)
COSEM_LOGICAL_DEVICE_NAME = CosemAttribute(
    interface=InterfaceClass.DATA,
    obis=ObisCode(0, 0, 42, 0, 0),
    attribute=DEFAULT_ATTRIBUTE,
)
COSEM_SOFTWARE_PACKAGE = CosemAttribute(
    interface=InterfaceClass.DATA,
    obis=ObisCode(0, 0, 96, 1, 2),
    attribute=DEFAULT_ATTRIBUTE,
)

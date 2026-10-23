"""Contains constants for the DLMS integration."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum, unique
from typing import Final

from microdlms import CosemAttribute, InterfaceClass, ObisCode

DOMAIN: Final = "dlms_cosem"

# Attributes
ATTR_EQUIPMENT_ID: Final = "equipment_id"

# Configuration
CONF_PASSWORD: Final = "password"
CONF_PHYSICAL_ADDRESS: Final = "physical_address"
CONF_PORT: Final = "port"
CONF_HARDWARE_INTERFACE: Final = "hardware_interface"
CONF_READ_DELAY: Final = "read_delay"
CONF_READ_TIMEOUT: Final = "read_timeout"
CONF_RETRIES: Final = "retries"
CONF_RETRY_DELAY: Final = "retry_delay"


# Enums
@unique
class HardwareInterface(StrEnum):
    """Represents a hardware interface type."""

    OPTICAL = "optical"
    RS485 = "rs485"
    ETHERNET = "ethernet"
    CELLULAR = "cellular"


# Defaults
DEFAULT_ATTRIBUTE: Final = 2
DEFAULT_MODEL: Final = "Smart meter"
DEFAULT_PASSWORD: Final = "111111"
DEFAULT_PHYSICAL_ADDRESS: Final = 1
DEFAULT_HARDWARE_INTERFACE: Final = HardwareInterface.OPTICAL
DEFAULT_READ_DELAY: Final = 0.25  # seconds
DEFAULT_READ_TIMEOUT: Final = 10.0  # seconds
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

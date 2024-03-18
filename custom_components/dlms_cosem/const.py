"""Contains constants for the DLMS integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "dlms_cosem"

# Attributes
ATTR_DATA: Final = "data"
ATTR_EQUIPMENT_ID: Final = "equipment_id"

# Configuration
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_PASSWORD: Final = "password"
CONF_PHYSICAL_ADDRESS: Final = "physical_address"

# Defaults
DEFAULT_PORT: Final = 23
DEFAULT_PASSWORD: Final = "111111"
DEFAULT_MODEL: Final = "Smart meter"
DEFAULT_ATTRIBUTE: Final = 2
DEFAULT_SCAN_INTERVAL: Final = 15  # seconds

# Dispatcher signals
SIGNAL_AVAILABLE: Final = "available"

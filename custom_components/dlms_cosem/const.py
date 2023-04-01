"""Contains constants for the DLMS integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "dlms_cosem"

# Attributes
ATTR_DATA: Final = "data"

# Configuration
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_PASSWORD: Final = "password"
CONF_PHYSICAL_ADDRESS: Final = "physical_address"

# Configuration defaults
DEFAULT_PORT: Final = 23
DEFAULT_PASSWORD: Final = "111111"

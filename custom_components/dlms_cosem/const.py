"""Contains constants for DLMS integration."""
from __future__ import annotations

from enum import Enum, unique
from typing import Final

DOMAIN: Final = "dlms_cosem"

# Attributes
ATTR_DATA: Final = "data"

# Configuration.
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_PASSWORD: Final = "password"
CONF_PHYSICAL_ADDRESS: Final = "physical_address"

# Defaults.
DEFAULT_PORT: Final = 23
DEFAULT_PASSWORD: Final = "111111"


@unique
class Manufacturer(Enum):
    """Contains manufacturer codes."""

    INC = "Incotex"

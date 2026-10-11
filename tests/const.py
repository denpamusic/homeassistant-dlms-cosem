"""Constants for DLMS/COSEM integration tests."""

from __future__ import annotations

import datetime as dt
from typing import Any, Final

from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, ATTR_SW_VERSION

from custom_components.dlms_cosem.const import (
    CONF_PASSWORD,
    CONF_PHYSICAL_ADDRESS,
    CONF_PORT,
    CONF_READ_DELAY,
)

ATTR_EQUIPMENT_ID: Final = "equipment_id"

MOCK_DATETIME = dt.datetime(2026, 10, 9, 15, 0, 0, tzinfo=dt.UTC)
MOCK_DATETIME_BYTES = bytes.fromhex("07ea0a09ff0f000000000000")

MOCK_CONFIG_DATA: Final[dict[str, Any]] = {
    CONF_PORT: "/dev/ttyUSB0",
    CONF_PASSWORD: "111111",
    CONF_PHYSICAL_ADDRESS: 1,
    CONF_READ_DELAY: 250,
}

MOCK_DEVICE_DATA: Final[dict[str, Any]] = {
    ATTR_EQUIPMENT_ID: "12345678",
    ATTR_MANUFACTURER: "Incotex",
    ATTR_MODEL: "Mercury 236",
    ATTR_SW_VERSION: "1.0.0",
}

MOCK_ENTRY_DATA: Final[dict[str, Any]] = {
    **MOCK_CONFIG_DATA,
    **MOCK_DEVICE_DATA,
}

MOCK_COSEM_DATA: Final[dict[str, Any]] = {
    "current_l1": 1234,
    "current_l2": 2345,
    "current_l3": 3456,
    "voltage_l1": 23000,
    "voltage_l2": 23100,
    "voltage_l3": 22900,
    "active_power_total": 50000,
    "active_power_l1": 10000,
    "active_power_l2": 20000,
    "active_power_l3": 20000,
    "apparent_power_l1": 11000,
    "apparent_power_l2": 21000,
    "apparent_power_l3": 21000,
    "apparent_power_total": 53000,
    "power_factor_total": 950,
    "power_factor_l1": 940,
    "power_factor_l2": 950,
    "power_factor_l3": 960,
    "active_energy_total": 1234567,
    "active_energy_tariff1": 1000000,
    "active_energy_tariff2": 234567,
    "frequency": 5000,
    "active_tariff": 1,
    "internal_temperature": 25,
    "uptime": 3600,
    "local_time": MOCK_DATETIME_BYTES,
    "clock_synced": MOCK_DATETIME_BYTES,
    "front_cover_opened": MOCK_DATETIME_BYTES,
    "terminals_cover_opened": MOCK_DATETIME_BYTES,
    "magnetic_field_detected": MOCK_DATETIME_BYTES,
    "self_test": b"\x01\x00",
}

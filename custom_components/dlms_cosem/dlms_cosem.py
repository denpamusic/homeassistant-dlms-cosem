"""Contains the DLMS connection class."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import datetime as dt
from functools import cache, cached_property
import json
from pathlib import Path
from typing import Any, Final, Literal, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, ATTR_SW_VERSION
from homeassistant.core import HomeAssistant, callback

from microdlms import (
    AsyncMeterClient,
    CommunicationError,
    CosemAttribute,
    CosemDateTime,
    DataAccessError,
    ProtocolError,
)

from .const import (
    ATTR_EQUIPMENT_ID,
    CONF_HARDWARE_INTERFACE,
    CONF_PASSWORD,
    CONF_PHYSICAL_ADDRESS,
    CONF_PORT,
    CONF_READ_DELAY,
    CONF_READ_TIMEOUT,
    CONF_RETRIES,
    CONF_RETRY_DELAY,
    DEFAULT_HARDWARE_INTERFACE,
    DEFAULT_MODEL,
    DEFAULT_PASSWORD,
    DEFAULT_PHYSICAL_ADDRESS,
    DEFAULT_READ_DELAY,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_RETRIES,
    DEFAULT_RETRY_DELAY,
    HardwareInterface,
)

LOGICAL_CLIENT_ADDRESS: Final = 32
LOGICAL_SERVER_ADDRESS: Final = 1

DISCONNECT_DELAY: Final = dt.timedelta(seconds=3)

CONNECTION_ERRORS = (CommunicationError, ProtocolError, TimeoutError, OSError)

LOGICAL_DEVICE_NAME_FORMATTER: dict[str, Callable[[str], str]] = {
    "INC": lambda x: f"Mercury {x[3:6]}",
}

NEVER: Final = "never"


@dataclass(slots=True, kw_only=True)
class DlmsStatistics:
    """Contains DLMS statistics."""

    requests_count: int = 0
    successful_reads: int = 0
    failed_reads: int = 0
    connection_loss_at: dt.datetime | Literal["never"] = NEVER
    connection_losses: int = 0

    def reset_transfer_statistics(self) -> None:
        """Reset transfer statistics."""
        self.requests_count = 0
        self.successful_reads = 0
        self.failed_reads = 0


@cache
def _load_flag_ids() -> dict[str, str]:
    """Load flag IDs from the JSON file."""
    file_path = Path(__file__).with_name("dlms_flagids.json")
    return cast(dict[str, str], json.loads(file_path.read_text(encoding="utf-8")))


async def async_decode_flag_id(hass: HomeAssistant, flag_id: str) -> str:
    """Decode the flag id."""
    flag_ids = await hass.async_add_executor_job(_load_flag_ids)
    return flag_ids[flag_id]


async def async_decode_logical_device_name(
    hass: HomeAssistant, logical_device_name: str
) -> tuple[str, str]:
    """Decode logical device name."""
    flag_id = logical_device_name[0:3]

    try:
        manufacturer = await async_decode_flag_id(hass, flag_id)
    except KeyError:
        manufacturer = "Unknown"

    if formatter := LOGICAL_DEVICE_NAME_FORMATTER.get(flag_id, None):
        model = formatter(logical_device_name)
    else:
        model = DEFAULT_MODEL

    return manufacturer, model


@callback
def async_extract_error_codes(error_code: bytes, prefix: str = "E-") -> list[str]:
    """Extract the error code list from bytes."""
    error_length = len(error_code) * 8
    error_number = int.from_bytes(error_code, byteorder="big")
    return [
        f"{prefix}{(index + 1):02d}"
        for index in range(0, error_length - 1)
        if error_number & (1 << index)
    ]


@callback
def parse_dlms_datetime(data: bytes | None) -> dt.datetime | None:
    """Parse DLMS 12-byte date-time octet string into Python datetime."""
    if not data:
        return None
    return CosemDateTime.from_bytes(data).as_datetime()


async def async_get_dlms_client(
    port: str,
    password: str = DEFAULT_PASSWORD,
    physical_address: int = DEFAULT_PHYSICAL_ADDRESS,
    timeout: float = DEFAULT_READ_TIMEOUT,
) -> AsyncMeterClient:
    """Create and connect a DLMS AsyncMeterClient."""
    client = AsyncMeterClient(
        port=port,
        password=password,
        server_physical_address=physical_address,
        timeout=timeout,
    )
    await client.connect()
    return client


@dataclass(frozen=True, kw_only=True)
class HardwareConfig:
    """Represents timeout and delay config for hardware interface."""

    timeout: float  # seconds
    delay: float = 0.0  # seconds


INTERFACE_CONFIG: dict[HardwareInterface, HardwareConfig] = {
    HardwareInterface.OPTICAL: HardwareConfig(timeout=5, delay=0.25),
    HardwareInterface.RS485: HardwareConfig(timeout=1, delay=0.05),
    HardwareInterface.ETHERNET: HardwareConfig(timeout=0.5),
    HardwareInterface.CELLULAR: HardwareConfig(timeout=10.0),
}


class DlmsConnection:
    """Represents a DLMS connection."""

    _retries: int = DEFAULT_RETRIES
    _retry_delay: float = DEFAULT_RETRY_DELAY
    client: AsyncMeterClient | None
    entry: ConfigEntry
    hass: HomeAssistant
    statistics: DlmsStatistics

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize a new DLMS/COSEM connection."""
        self.entry = entry
        self.hass = hass
        self.client = None
        self.statistics = DlmsStatistics()

    @cached_property
    def port(self) -> str:
        """Return the port."""
        return cast(str, self.entry.data[CONF_PORT])

    @cached_property
    def password(self) -> str:
        """Return the password."""
        return cast(str, self.entry.data.get(CONF_PASSWORD, DEFAULT_PASSWORD))

    @cached_property
    def physical_address(self) -> int:
        """Return the physical address."""
        return cast(
            int, self.entry.data.get(CONF_PHYSICAL_ADDRESS, DEFAULT_PHYSICAL_ADDRESS)
        )

    @cached_property
    def hardware_config(self) -> HardwareConfig | None:
        """Return the hardware configuration."""
        hardware_interface = cast(
            HardwareInterface,
            self.entry.data.get(CONF_HARDWARE_INTERFACE, DEFAULT_HARDWARE_INTERFACE),
        )
        return INTERFACE_CONFIG.get(hardware_interface)

    @property
    def read_delay(self) -> float:
        """Return the read delay in seconds."""
        if read_delay := self.entry.options.get(
            CONF_READ_DELAY, self.entry.data.get(CONF_READ_DELAY)
        ):
            return cast(float, read_delay)

        if self.hardware_config:
            return self.hardware_config.delay

        return DEFAULT_READ_DELAY

    @property
    def read_timeout(self) -> float:
        """Return the read attempt timeout in seconds."""
        if read_timeout := self.entry.options.get(
            CONF_READ_TIMEOUT, self.entry.data.get(CONF_READ_TIMEOUT)
        ):
            return cast(float, read_timeout)

        if self.hardware_config:
            return self.hardware_config.timeout

        return DEFAULT_READ_TIMEOUT

    @cached_property
    def retries(self) -> int:
        """Return the number of retries."""
        return cast(
            int,
            self.entry.options.get(
                CONF_RETRIES,
                self.entry.data.get(CONF_RETRIES, DEFAULT_RETRIES),
            ),
        )

    @cached_property
    def retry_delay(self) -> float:
        """Return the retry delay in seconds."""
        return cast(
            float,
            self.entry.options.get(
                CONF_RETRY_DELAY,
                self.entry.data.get(CONF_RETRY_DELAY, DEFAULT_RETRY_DELAY),
            ),
        )

    @cached_property
    def manufacturer(self) -> str:
        """Return the manufacturer."""
        return cast(str, self.entry.data[ATTR_MANUFACTURER])

    @cached_property
    def model(self) -> str:
        """Return the model."""
        return cast(str, self.entry.data[ATTR_MODEL])

    @cached_property
    def sw_version(self) -> str:
        """Return the software version."""
        return cast(str, self.entry.data[ATTR_SW_VERSION])

    @cached_property
    def equipment_id(self) -> str:
        """Return the serial number."""
        return cast(str, self.entry.data[ATTR_EQUIPMENT_ID])

    async def async_connect(self) -> None:
        """Initiate the connection and associate the client."""
        if not self.client:
            self.client = await async_get_dlms_client(
                port=self.port,
                password=self.password,
                physical_address=self.physical_address,
                timeout=self.read_timeout,
            )
            self.statistics.reset_transfer_statistics()

    async def async_get(self, attribute: CosemAttribute) -> Any:
        """Get the COSEM attribute and decode it."""
        if not self.client:
            return None

        self.statistics.requests_count += 1
        try:
            result = await self.client.get(
                attribute,
                retries=self.retries,
                retry_delay=self.retry_delay,
                timeout=self.read_timeout,
            )
            self.statistics.successful_reads += 1
            await asyncio.sleep(self.read_delay)
            return result
        except DataAccessError:
            self.statistics.failed_reads += 1
            raise
        except Exception:
            self.statistics.failed_reads += 1
            self.statistics.connection_losses += 1
            self.statistics.connection_loss_at = dt.datetime.now(dt.UTC)
            raise

    async def async_disconnect(self) -> None:
        """Disconnect the connection."""
        if self.client:
            await self.client.disconnect()
            self.client = None
            await asyncio.sleep(DISCONNECT_DELAY.total_seconds())

    @property
    def connected(self) -> bool:
        """Return whether client is connected."""
        return self.client is not None and self.client.is_connected

    @property
    def dlms_state(self) -> str:
        """Return the current DLMS association state."""
        if self.client:
            return self.client.session.state.name.lower()
        return "disconnected"

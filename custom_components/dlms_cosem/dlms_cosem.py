"""Contains the DLMS connection class."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, MutableMapping
from contextlib import suppress
from dataclasses import dataclass
import datetime as dt
from functools import cache, cached_property
import json
from pathlib import Path
from typing import Any, Final, Literal, cast

from dlms_cosem import a_xdr, cosem
from dlms_cosem.client import (
    DataResultError,
    DlmsClient as BlockingDlmsClient,
    DlmsConnectionSettings,
)
from dlms_cosem.exceptions import CommunicationError, LocalDlmsProtocolError
from dlms_cosem.io import HdlcTransport, IoImplementation, SerialXIO
from dlms_cosem.security import (
    AuthenticationMethodManager,
    LowLevelSecurityAuthentication,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, ATTR_SW_VERSION
from homeassistant.core import HomeAssistant, callback

from .const import (
    ATTR_DATA,
    ATTR_EQUIPMENT_ID,
    CONF_PASSWORD,
    CONF_PHYSICAL_ADDRESS,
    CONF_PORT,
    CONF_READ_DELAY,
    DEFAULT_MODEL,
)

LOGICAL_CLIENT_ADDRESS: Final = 32
LOGICAL_SERVER_ADDRESS: Final = 1

READ_TIMEOUT: Final = 10  # seconds
DISCONNECT_DELAY: Final = 3  # seconds

CONNECTION_ERRORS = (CommunicationError, LocalDlmsProtocolError, TimeoutError, OSError)

LOGICAL_DEVICE_NAME_FORMATTER: dict[str, Callable[[str], str]] = {
    "INC": lambda x: f"Mercury {x[3:6]}",
}

A_XDR_DECODER = a_xdr.AXdrDecoder(
    encoding_conf=a_xdr.EncodingConf(
        attributes=[a_xdr.Sequence(attribute_name=ATTR_DATA)]
    )
)

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
def async_dlms_datetime_to_ha_datetime(dattim: dt.datetime) -> dt.datetime:
    """Convert timezone between DLMS and HA."""
    utcoffset = dattim.utcoffset()
    if utcoffset is None:
        return dattim

    local_tz = dt.timezone(offset=dt.timedelta(seconds=-utcoffset.total_seconds()))
    return dattim.replace(tzinfo=local_tz)


class DlmsClient:
    """Represents a DLMS client."""

    _password: bytes
    _physical_address: int
    _port: str
    _read_delay: int
    _read_timeout: int = READ_TIMEOUT
    client: BlockingDlmsClient | None
    statistics: DlmsStatistics
    hass: HomeAssistant

    def __init__(
        self,
        hass: HomeAssistant,
        port: str,
        password: str,
        physical_address: int,
        read_delay: int,
        read_timeout: int = READ_TIMEOUT,
    ) -> None:
        """Initialize a new async DLMS client."""
        self._password = bytes(password, encoding="utf-8")
        self._physical_address = physical_address
        self._port = port
        self._read_delay = read_delay
        self._read_timeout = read_timeout
        self.client = None
        self.statistics = DlmsStatistics()
        self.hass = hass

    async def async_connect(self) -> None:
        """Initiate the connection and associate the client."""
        if not self.client:
            self.client = BlockingDlmsClient(
                transport=HdlcTransport(
                    client_logical_address=LOGICAL_CLIENT_ADDRESS,
                    server_logical_address=LOGICAL_SERVER_ADDRESS,
                    server_physical_address=self._physical_address,
                    io=self.io,
                ),
                authentication=self.authentication,
                connection_settings=DlmsConnectionSettings(use_rlrq_rlre=False),
            )
            for job in (self.client.connect, self.client.associate):
                await self.hass.async_add_executor_job(job)

            self.statistics.reset_transfer_statistics()

    async def async_get(self, attribute: cosem.CosemAttribute) -> Any:
        """Get the COSEM attribute and decode it."""

        def _get_cosem_attribute(
            client: BlockingDlmsClient, attribute: cosem.CosemAttribute
        ) -> Any:
            """Get the COSEM attribute."""
            response = client.get(attribute)
            return A_XDR_DECODER.decode(response)[ATTR_DATA]

        if not self.client:
            return None

        self.statistics.requests_count += 1
        try:
            async with asyncio.timeout(self._read_timeout):
                result = await self.hass.async_add_executor_job(
                    _get_cosem_attribute, self.client, attribute
                )
            self.statistics.successful_reads += 1
            await asyncio.sleep(self._read_delay / 1000)
            return result
        except DataResultError:
            self.statistics.failed_reads += 1
            raise
        except Exception:
            self.statistics.failed_reads += 1
            self.statistics.connection_losses += 1
            self.statistics.connection_loss_at = dt.datetime.now(dt.UTC)
            raise

    async def async_disconnect(self) -> None:
        """Close the connection."""
        if self.client:
            for job in (
                self.client.release_association,
                self.client.disconnect,
                self.client.transport.io.disconnect,
            ):
                with suppress(Exception):
                    await self.hass.async_add_executor_job(job)

            self.client = None

    @property
    def connected(self) -> bool:
        """Return whether client is connected."""
        return self.client is not None

    @property
    def dlms_state(self) -> str:
        """Return the current DLMS association state."""
        if self.client:
            return str(self.client.dlms_connection.state.current_state).lower()
        return "disconnected"

    @cached_property
    def io(self) -> IoImplementation:
        """Return the IO implementation."""
        return SerialXIO(port_url=self._port, timeout=self._read_timeout)

    @cached_property
    def authentication(self) -> AuthenticationMethodManager:
        """Return the authentication method manager."""
        return LowLevelSecurityAuthentication(secret=self._password)


class DlmsConnection:
    """Represents DLMS connection."""

    client: DlmsClient
    entry: ConfigEntry
    hass: HomeAssistant

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize a new DLMS/COSEM connection."""
        self.client = DlmsClient(
            hass,
            port=entry.data[CONF_PORT],
            password=entry.data[CONF_PASSWORD],
            physical_address=entry.data[CONF_PHYSICAL_ADDRESS],
            read_delay=entry.data[CONF_READ_DELAY],
        )
        self.entry = entry
        self.hass = hass

    @property
    def connected(self) -> bool:
        """Return whether connection is active."""
        return self.client.connected

    @property
    def dlms_state(self) -> str:
        """Return the current DLMS association state."""
        return self.client.dlms_state

    @property
    def statistics(self) -> DlmsStatistics:
        """Return the connection statistics."""
        return self.client.statistics

    async def async_connect(self) -> None:
        """Initialize the connection."""
        await self.client.async_connect()

    async def async_close(self) -> None:
        """Close the connection."""
        if self.client.connected:
            await self.client.async_disconnect()
            await asyncio.sleep(DISCONNECT_DELAY)

    async def async_get(self, attribute: cosem.CosemAttribute) -> Any:
        """Get the COSEM attribute."""
        return await self.client.async_get(attribute)

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

    @staticmethod
    async def async_check(
        hass: HomeAssistant, data: MutableMapping[str, Any]
    ) -> DlmsClient:
        """Check DLMS meter connection."""
        client = DlmsClient(
            hass,
            port=data[CONF_PORT],
            password=data[CONF_PASSWORD],
            physical_address=data[CONF_PHYSICAL_ADDRESS],
            read_delay=data[CONF_READ_DELAY],
        )
        await client.async_connect()
        return client

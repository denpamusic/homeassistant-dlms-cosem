"""Contains the DLMS connection class."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, MutableMapping
from contextlib import suppress
from datetime import datetime, timedelta
from functools import cache, cached_property
import logging
from pathlib import Path
from typing import Any, Final, cast

import aiofiles
from dlms_cosem import a_xdr, cosem
from dlms_cosem.client import DlmsClient as BlockingDlmsClient
from dlms_cosem.io import BlockingTcpIO, HdlcTransport, IoImplementation
from dlms_cosem.security import (
    AuthenticationMethodManager,
    LowLevelSecurityAuthentication,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, ATTR_SW_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
import ijson
import structlog

from .const import (
    ATTR_DATA,
    ATTR_EQUIPMENT_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PHYSICAL_ADDRESS,
    CONF_PORT,
    DEFAULT_MODEL,
    DOMAIN,
    SIGNAL_AVAILABLE,
)

LOGICAL_CLIENT_ADDRESS: Final = 32
LOGICAL_SERVER_ADDRESS: Final = 1

RECONNECT_INTERVAL: Final = timedelta(seconds=3)

TIMEOUT: Final = 5

LOGICAL_DEVICE_NAME_FORMATTER: dict[str, Callable[[str], str]] = {
    "INC": lambda x: f"Mercury {x[3:6]}",
}

A_XDR_DECODER = a_xdr.AXdrDecoder(
    encoding_conf=a_xdr.EncodingConf(
        attributes=[a_xdr.Sequence(attribute_name=ATTR_DATA)]
    )
)

_LOGGER = logging.getLogger(__name__)

# Setup structlog for the dlms-cosem package.
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING)
)


@cache
async def async_decode_flag_id(flag_id: str) -> str:
    """Decode the flag id."""
    dlms_flag_ids_file = Path(__file__).with_name("dlms_flagids.json")

    async with aiofiles.open(dlms_flag_ids_file, mode="rb") as f:
        async for key, value in ijson.kvitems_async(f, ""):
            if key == flag_id:
                return cast(str, value)

    raise KeyError


@cache
async def async_decode_logical_device_name(logical_device_name: str) -> tuple[str, str]:
    """Decode logical device name."""
    flag_id = logical_device_name[0:3]
    model = DEFAULT_MODEL

    try:
        manufacturer = await async_decode_flag_id(flag_id)
    except KeyError:
        return "unknown", model

    return manufacturer, (
        LOGICAL_DEVICE_NAME_FORMATTER[flag_id](logical_device_name)
        if flag_id in LOGICAL_DEVICE_NAME_FORMATTER
        else model
    )


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


class DlmsClient:
    """Represents a DLMS client."""

    _host: str
    _password: bytes
    _physical_address: int
    _port: str
    _timeout: int = TIMEOUT
    client: BlockingDlmsClient | None
    hass: HomeAssistant

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        password: str,
        physical_address: int,
        port: int,
        timeout: int = TIMEOUT,
    ) -> None:
        """Initialize a new async DLMS client."""
        self._host = host
        self._password = bytes(password, encoding="utf-8")
        self._physical_address = physical_address
        self._port = port
        self._timeout = timeout
        self.client = None
        self.hass = hass

    async def async_connect(self) -> None:
        """Add an executor job to initiate the connection."""

        def _connect_and_associate() -> None:
            """Initiate connection and perform association."""
            self.client.connect()
            self.client.associate()

        if not self.client:
            self.client = BlockingDlmsClient(
                transport=HdlcTransport(
                    client_logical_address=LOGICAL_CLIENT_ADDRESS,
                    server_logical_address=LOGICAL_SERVER_ADDRESS,
                    server_physical_address=self._physical_address,
                    io=self.io,
                ),
                authentication=self.authentication,
            )
            await self.hass.async_add_executor_job(_connect_and_associate)

    async def async_get(self, attribute: cosem.CosemAttribute) -> Any:
        """Add an executor job to get the COSEM attribute and decode it."""

        def _get_attibute() -> Any:
            """Get the COSEM attribute and decode it."""
            response = self.client.get(attribute)
            return A_XDR_DECODER.decode(response)[ATTR_DATA]

        if not self.client:
            return None

        async with self.hass.timeout.async_timeout(TIMEOUT, DOMAIN):
            return await self.hass.async_add_executor_job(_get_attibute)

    async def async_disconnect(self) -> None:
        """Add an executor job to close the connection.

        Separate IO disconnect is needed here because when
        _async_disconnect() is called while client timeouts during get
        request, client state becomes corrupted and client cannot
        recover and do RLRQ or graceful disconnect.
        """

        def _disconnect() -> None:
            """Close the connection."""
            for func in (
                self.client.release_association,
                self.client.disconnect,
                self.client.transport.io.disconnect,
            ):
                with suppress(Exception):
                    # Ignore any exceptions on disconnect.
                    func()

        if self.client:
            await self.hass.async_add_executor_job(_disconnect)
            self.client = None

    @cached_property
    def io(self) -> IoImplementation:
        """Return the IO implementation."""
        return BlockingTcpIO(host=self._host, port=self._port, timeout=self._timeout)

    @cached_property
    def authentication(self) -> AuthenticationMethodManager:
        """Return the authentication method manager."""
        return LowLevelSecurityAuthentication(secret=self._password)


class DlmsConnection:
    """Represents DLMS connection."""

    _update_semaphore: asyncio.Semaphore
    client: DlmsClient
    entry: ConfigEntry
    hass: HomeAssistant

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize a new DLMS/COSEM connection."""
        self._update_semaphore = asyncio.Semaphore(1)
        self.client = DlmsClient(
            hass,
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            password=entry.data[CONF_PASSWORD],
            physical_address=entry.data[CONF_PHYSICAL_ADDRESS],
        )
        self.entry = entry
        self.hass = hass

    async def async_connect(self) -> None:
        """Initialize the connection."""
        await self.client.async_connect()

    async def async_close(self) -> None:
        """Close the connection."""
        await self.client.async_disconnect()

    async def async_get(self, attribute: cosem.CosemAttribute) -> Any:
        """Get the attribute or initiate reconnect on failure."""
        async with self._update_semaphore:
            try:
                return await self.client.async_get(attribute)
            except Exception as err:
                async_dispatcher_send(self.hass, SIGNAL_AVAILABLE, False)
                await self._connection_error(err)

    async def _connection_error(self, err: Exception) -> None:
        """Log error and schedule a reconnect attempt."""
        if isinstance(err, TimeoutError):
            _LOGGER.warning("Connection timed out, retrying in the background")
        else:
            _LOGGER.warning("Connection lost, retrying in the background: %s", err)

        await self.async_close()
        async_call_later(self.hass, RECONNECT_INTERVAL, self._reconnect)

    async def _reconnect(self, event_time: datetime) -> None:
        """Try to reconnect on connection failure."""
        try:
            await self.async_connect()
        except Exception as err:
            await self._connection_error(err)
        else:
            async_dispatcher_send(self.hass, SIGNAL_AVAILABLE, True)

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

    @classmethod
    async def async_check(
        cls, hass: HomeAssistant, data: MutableMapping[str, Any]
    ) -> DlmsClient:
        """Check DLMS meter connection."""
        client = DlmsClient(
            hass,
            host=data[CONF_HOST],
            port=data[CONF_PORT],
            password=data[CONF_PASSWORD],
            physical_address=data[CONF_PHYSICAL_ADDRESS],
        )
        await client.async_connect()
        return client

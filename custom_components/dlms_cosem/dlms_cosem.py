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
from dlms_cosem import a_xdr, cosem, enumerations
from dlms_cosem.client import DlmsClient
from dlms_cosem.io import BlockingTcpIO, HdlcTransport
from dlms_cosem.security import LowLevelSecurityAuthentication
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
    DEFAULT_ATTRIBUTE,
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

_LOGGER = logging.getLogger(__name__)

# Setup structlog for the dlms-cosem package.
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING)
)


@cache
def async_get_lls_authentication(password: str) -> LowLevelSecurityAuthentication:
    """Get the Low Level Security authentication."""
    return LowLevelSecurityAuthentication(secret=bytes(password, encoding="utf-8"))


def async_get_dlms_client(data: MutableMapping[str, Any]) -> DlmsClient:
    """Get the DLMS client."""
    return DlmsClient(
        authentication=async_get_lls_authentication(data[CONF_PASSWORD]),
        transport=HdlcTransport(
            client_logical_address=LOGICAL_CLIENT_ADDRESS,
            server_logical_address=LOGICAL_SERVER_ADDRESS,
            server_physical_address=data[CONF_PHYSICAL_ADDRESS],
            io=BlockingTcpIO(
                host=data[CONF_HOST], port=data[CONF_PORT], timeout=TIMEOUT
            ),
        ),
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


LOGICAL_DEVICE_NAME = cosem.CosemAttribute(
    interface=enumerations.CosemInterface.DATA,
    instance=cosem.Obis(0, 0, 42, 0, 0),
    attribute=DEFAULT_ATTRIBUTE,
)


async def async_get_logical_device_name(hass: HomeAssistant, client: DlmsClient) -> str:
    """Get the logical device name."""
    data: bytes = await _async_get_attribute(hass, client, LOGICAL_DEVICE_NAME)
    return data.decode(encoding="utf-8")


SOFTWARE_PACKAGE = cosem.CosemAttribute(
    interface=enumerations.CosemInterface.DATA,
    instance=cosem.Obis(0, 0, 96, 1, 2),
    attribute=DEFAULT_ATTRIBUTE,
)


async def async_get_sw_version(hass: HomeAssistant, client: DlmsClient) -> str:
    """Get the software version."""
    return cast(str, await _async_get_attribute(hass, client, SOFTWARE_PACKAGE))


EQUIPMENT_ID = cosem.CosemAttribute(
    interface=enumerations.CosemInterface.DATA,
    instance=cosem.Obis(0, 0, 96, 1, 0),
    attribute=DEFAULT_ATTRIBUTE,
)


async def async_get_equipment_id(hass: HomeAssistant, client: DlmsClient) -> str:
    """Get the equipment identifier."""
    return cast(str, await _async_get_attribute(hass, client, EQUIPMENT_ID))


async def _async_connect(hass: HomeAssistant, client: DlmsClient) -> None:
    """Add an executor job to initiate the connection."""

    def _connect() -> None:
        """Initiate the connection."""
        client.connect()
        client.associate()

    await hass.async_add_executor_job(_connect)


async def _async_disconnect(hass: HomeAssistant, client: DlmsClient) -> None:
    """Add an executor job to close the connection."""

    def _disconnect() -> None:
        """Close the connection."""
        for func in (
            client.release_association,
            client.disconnect,
            client.transport.io.disconnect,
        ):
            with suppress(Exception):
                # Ignore any exceptions on disconnect.
                func()

    await hass.async_add_executor_job(_disconnect)


A_XDR_DECODER = a_xdr.AXdrDecoder(
    encoding_conf=a_xdr.EncodingConf(
        attributes=[a_xdr.Sequence(attribute_name=ATTR_DATA)]
    )
)


async def _async_get_attribute(
    hass: HomeAssistant, client: DlmsClient, attribute: cosem.CosemAttribute
) -> Any:
    """Add an executor job to get the COSEM attribute and decode it."""

    def _get_attibute() -> Any:
        """Get the COSEM attribute and decode it."""
        response = client.get(attribute)
        return A_XDR_DECODER.decode(response)[ATTR_DATA]

    async with hass.timeout.async_timeout(TIMEOUT, DOMAIN):
        return await hass.async_add_executor_job(_get_attibute)


@callback
def _async_log_connection_error(err: Exception):
    """Log connection error."""
    if isinstance(err, TimeoutError):
        _LOGGER.warning("Connection timed out, retrying in the background")
    else:
        _LOGGER.warning("Connection lost, retrying in the background: %s", err)


class DlmsConnection:
    """Represents DLMS connection."""

    _update_semaphore: asyncio.Semaphore
    client: DlmsClient | None
    connected: bool
    entry: ConfigEntry
    hass: HomeAssistant

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize a new DLMS/COSEM connection."""
        self._update_semaphore = asyncio.Semaphore(1)
        self.client = None
        self.connected = False
        self.entry = entry
        self.hass = hass

    async def async_connect(self) -> None:
        """Connect to the DLMS server."""
        if not self.connected:
            self.client = async_get_dlms_client(self.entry.data)
            await _async_connect(self.hass, self.client)
            self.connected = True

    async def _reconnect(self, event_time: datetime) -> None:
        """Try to reconnect on connection failure."""
        try:
            await self.async_connect()
        except Exception as err:
            await self.async_close()
            _async_log_connection_error(err)
            async_call_later(self.hass, RECONNECT_INTERVAL, self._reconnect)
        else:
            async_dispatcher_send(self.hass, SIGNAL_AVAILABLE, True)

    async def async_get(self, attribute: cosem.CosemAttribute) -> Any:
        """Get the attribute or initiate reconnect on failure."""
        await self._update_semaphore.acquire()
        try:
            if self.connected:
                return await _async_get_attribute(self.hass, self.client, attribute)

        except Exception as err:
            await self.async_close()
            _async_log_connection_error(err)
            async_dispatcher_send(self.hass, SIGNAL_AVAILABLE, False)
            async_call_later(self.hass, RECONNECT_INTERVAL, self._reconnect)
        finally:
            self._update_semaphore.release()

    async def async_close(self) -> None:
        """Close the connection."""
        self.connected = False
        if self.client:
            await _async_disconnect(self.hass, self.client)
            self.client = None

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
        client = async_get_dlms_client(data)
        await _async_connect(hass, client)
        return client

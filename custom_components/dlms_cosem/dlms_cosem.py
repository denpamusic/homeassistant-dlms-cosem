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
from homeassistant.core import HomeAssistant
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
    SIGNAL_CONNECTED,
)

DLMS_FLAG_IDS_FILE: Final = "dlms_flagids.json"
LOGICAL_CLIENT_ADDRESS: Final = 32
LOGICAL_SERVER_ADDRESS: Final = 1
RECONNECT_INTERVAL: Final = timedelta(seconds=3)
UPDATE_TIMEOUT: Final = timedelta(seconds=5)

LOGICAL_DEVICE_NAME_FORMATTER: dict[str, Callable[[str], str]] = {
    "INC": lambda x: f"Mercury {x[3:6]}",
}

A_XDR_DECODER = a_xdr.AXdrDecoder(
    encoding_conf=a_xdr.EncodingConf(
        attributes=[a_xdr.Sequence(attribute_name=ATTR_DATA)]
    )
)

LOGICAL_DEVICE_NAME = cosem.CosemAttribute(
    interface=enumerations.CosemInterface.DATA,
    instance=cosem.Obis(0, 0, 42, 0, 0),
    attribute=DEFAULT_ATTRIBUTE,
)

SOFTWARE_PACKAGE = cosem.CosemAttribute(
    interface=enumerations.CosemInterface.DATA,
    instance=cosem.Obis(0, 0, 96, 1, 2),
    attribute=DEFAULT_ATTRIBUTE,
)

EQUIPMENT_ID = cosem.CosemAttribute(
    interface=enumerations.CosemInterface.DATA,
    instance=cosem.Obis(0, 0, 96, 1, 0),
    attribute=DEFAULT_ATTRIBUTE,
)

# Requests should be sent sequentially
_PARALLEL_SEMAPHORE = asyncio.Semaphore(1)

_LOGGER = logging.getLogger(__name__)

# Setup structlog for the dlms-cosem package.
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING)
)


def async_get_dlms_client(data: MutableMapping[str, Any]) -> DlmsClient:
    """Get DLMS client."""
    tcp_io = BlockingTcpIO(host=data[CONF_HOST], port=data[CONF_PORT], timeout=10)
    hdlc_transport = HdlcTransport(
        client_logical_address=LOGICAL_CLIENT_ADDRESS,
        server_logical_address=LOGICAL_SERVER_ADDRESS,
        server_physical_address=data[CONF_PHYSICAL_ADDRESS],
        io=tcp_io,
    )
    low_level_security_authentication = LowLevelSecurityAuthentication(
        secret=bytes(data[CONF_PASSWORD], encoding="utf-8")
    )
    return DlmsClient(
        transport=hdlc_transport,
        authentication=low_level_security_authentication,
    )


@cache
async def async_decode_flag_id(flag_id: str) -> str:
    """Decode the flag id."""
    dlms_flag_ids_file = Path(__file__).with_name(DLMS_FLAG_IDS_FILE)

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


def async_extract_error_codes(error_code: bytes, prefix: str = "E-") -> list[str]:
    """Extract the error code list from bytes."""
    error_length = len(error_code) * 8
    error_number = int.from_bytes(error_code, byteorder="big")
    return [
        f"{prefix}{(index + 1):02d}"
        for index in range(0, error_length - 1)
        if error_number & (1 << index)
    ]


async def async_get_logical_device_name(hass: HomeAssistant, client: DlmsClient) -> str:
    """Get the logical device name."""
    data = cast(
        bytes,
        await hass.async_add_executor_job(_get_attribute, client, LOGICAL_DEVICE_NAME),
    )
    return data.decode(encoding="utf-8")


async def async_get_sw_version(hass: HomeAssistant, client: DlmsClient) -> str:
    """Get the software version."""
    return cast(
        str, await hass.async_add_executor_job(_get_attribute, client, SOFTWARE_PACKAGE)
    )


async def async_get_equipment_id(hass: HomeAssistant, client: DlmsClient) -> str:
    """Get the equipment identifier."""
    return cast(
        str, await hass.async_add_executor_job(_get_attribute, client, EQUIPMENT_ID)
    )


def _connect_and_associate(client: DlmsClient) -> None:
    """Connect and associate the client."""
    client.connect()
    client.associate()


def _get_attribute(client: DlmsClient, attribute: cosem.CosemAttribute) -> Any:
    """Get COSEM attribute."""
    response = client.get(attribute)
    data = A_XDR_DECODER.decode(response)
    return data[ATTR_DATA]


class DlmsConnection:
    """Represents DLMS connection."""

    client: DlmsClient | None
    connected: bool
    entry: ConfigEntry
    reconnect_attempt: int
    hass: HomeAssistant

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize a new DLMS/COSEM connection."""
        self.client = None
        self.connected = False
        self.entry = entry
        self.reconnect_attempt = -1
        self.hass = hass

    async def async_connect(self) -> None:
        """Connect to the DLMS server."""
        self.client = async_get_dlms_client(self.entry.data)
        await self.hass.async_add_executor_job(_connect_and_associate, self.client)
        self.reconnect_attempt = 0
        self.connected = True

    async def _reconnect(self, event_time: datetime) -> None:
        """Try to reconnect on connection failure."""
        self.reconnect_attempt += 1
        await self._async_disconnect()

        try:
            await self.async_connect()
        except Exception as err:
            _LOGGER.warning(
                "Re-connection attempt failed, retrying in the background: %s", err
            )
            async_call_later(self.hass, RECONNECT_INTERVAL, self._reconnect)
        else:
            async_dispatcher_send(self.hass, SIGNAL_CONNECTED)

    async def _async_disconnect(self) -> None:
        """Add executor job to disassociate and disconnect the client."""

        def _disconnect() -> None:
            """Disassociate and disconnect the client."""
            if self.client:
                disconnect_fn = ("release_association", "disconnect")
                for func in disconnect_fn:
                    with suppress(Exception):
                        getattr(self.client, func)()

                self.client = None

        await self.hass.async_add_executor_job(_disconnect)

    async def async_get(self, attribute: cosem.CosemAttribute) -> Any:
        """Get the attribute."""
        try:
            async with _PARALLEL_SEMAPHORE:
                return (
                    None
                    if not self.connected
                    else await asyncio.wait_for(
                        self.hass.async_add_executor_job(
                            _get_attribute, self.client, attribute
                        ),
                        timeout=UPDATE_TIMEOUT.total_seconds(),
                    )
                )
        except TimeoutError:
            _LOGGER.warning("Connection timed out, retrying in the background")
        except Exception as err:
            _LOGGER.warning("Connection lost, retrying in the background: %s", err)

        self.connected = False
        async_call_later(self.hass, RECONNECT_INTERVAL, self._reconnect)

    async def async_close(self) -> None:
        """Close the connection."""
        await self._async_disconnect()
        self.connected = False
        self.reconnect_attempt = -1

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
        await hass.async_add_executor_job(_connect_and_associate, client)
        return client

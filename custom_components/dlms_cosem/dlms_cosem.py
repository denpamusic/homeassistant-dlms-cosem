"""Contains the DLMS connection class."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, MutableMapping
from contextlib import suppress
from datetime import timedelta
from functools import cache, cached_property
import logging
from pathlib import Path
from typing import Any, Final, cast

import aiofiles
from dlms_cosem import a_xdr, cosem, enumerations
from dlms_cosem.client import DlmsClient
from dlms_cosem.exceptions import CommunicationError
from dlms_cosem.io import BlockingTcpIO, HdlcTransport
from dlms_cosem.security import LowLevelSecurityAuthentication
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, ATTR_SW_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
import ijson
import structlog

from .const import (
    ATTR_DATA,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PHYSICAL_ADDRESS,
    CONF_PORT,
    DEFAULT_ATTRIBUTE,
    DEFAULT_MODEL,
    DOMAIN,
    SIGNAL_RECONNECTED,
)

DLMS_FLAG_IDS_FILE: Final = "dlms_flagids.json"
LOGICAL_CLIENT_ADDRESS: Final = 32
LOGICAL_SERVER_ADDRESS: Final = 1
RECONNECT_INTERVAL: Final = timedelta(seconds=3)

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
    disconnected: asyncio.Event
    entry: ConfigEntry
    _reconnect_task: asyncio.Task[None] | None
    _hass: HomeAssistant

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize a new DLMS/COSEM connection."""
        self.client = async_get_dlms_client(entry.data)
        self.disconnected = asyncio.Event()
        self.entry = entry
        self._reconnect_task = None
        self._hass = hass

    async def async_setup(self) -> None:
        """Set up DLMS connection."""
        await self.async_connect()
        self._reconnect_task = asyncio.create_task(self._async_reconnect_on_failure())

    async def async_connect(self) -> None:
        """Asynchronously connect to the DLMS server."""
        await self._hass.async_add_executor_job(_connect_and_associate, self.client)

    async def _async_reconnect_on_failure(self) -> None:
        """Task to initiate reconnect on the connection failure."""
        reconnect_interval = RECONNECT_INTERVAL.total_seconds()
        while await self.disconnected.wait():
            await self._async_ensure_disconnect()
            _LOGGER.warning("Connection lost, reconnecting...")
            try:
                self.client = async_get_dlms_client(self.entry.data)
                await self.async_connect()
                self.disconnected.clear()
                async_dispatcher_send(self._hass, SIGNAL_RECONNECTED)
            except CommunicationError:
                _LOGGER.warning(
                    "Reconnect attempt failed, retrying in %d seconds...",
                    reconnect_interval,
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
            finally:
                await asyncio.sleep(reconnect_interval)

    async def _async_ensure_disconnect(self) -> None:
        """Asynchronously ensure that client is disconnected."""
        await self._hass.async_add_executor_job(self._ensure_disconnect)

    def _ensure_disconnect(self) -> None:
        """Ensure that client is disconnected."""
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                # Ensure that IO is disconnected on any errors.
                with suppress(Exception):
                    self.client.transport.io.disconnect()

            self.client = None

    def get(self, attribute: cosem.CosemAttribute) -> Any:
        """Get the attribute."""
        if not self.disconnected.is_set():
            try:
                return _get_attribute(self.client, attribute)
            except Exception:  # pylint: disable=broad-except
                self.disconnected.set()

        return None

    async def async_get(self, attribute: cosem.CosemAttribute) -> Any:
        """Asynchronously get the attribute."""
        return await self._hass.async_add_executor_job(self.get, attribute)

    def close(self) -> None:
        """Close connection."""
        if self._reconnect_task:
            # Cancel reconnect task.
            self._reconnect_task.cancel()

        self._ensure_disconnect()
        self.disconnected.set()

    async def async_close(self) -> None:
        """Asynchronously closes the connection."""
        await self._hass.async_add_executor_job(self.close)

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            name=f"{self.manufacturer} {self.model}",
            identifiers={(DOMAIN, self.entry.unique_id)},
            manufacturer=self.manufacturer,
            model=self.model,
            sw_version=self.sw_version,
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

    @classmethod
    async def async_check(
        cls, hass: HomeAssistant, data: MutableMapping[str, Any]
    ) -> DlmsClient:
        """Check DLMS meter connection."""
        client = async_get_dlms_client(data)
        await hass.async_add_executor_job(_connect_and_associate, client)
        return client

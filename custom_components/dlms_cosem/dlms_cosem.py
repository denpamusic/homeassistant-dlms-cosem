"""Contains the DLMS connection class."""
from __future__ import annotations

import asyncio
from collections.abc import MutableMapping
from datetime import timedelta
import logging
from pathlib import Path
from typing import Any, Final

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

AXDR_DECODER = a_xdr.AXdrDecoder(
    encoding_conf=a_xdr.EncodingConf(
        # pylint: disable=abstract-class-instantiated
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
    """Gets the DLMS client."""
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


async def async_decode_flag_id(flag_id: str) -> str:
    """Decodes flag id."""
    dlms_flag_ids_file = Path(__file__).with_name(DLMS_FLAG_IDS_FILE)

    async with aiofiles.open(dlms_flag_ids_file, encoding="utf-8") as f:
        async for key, value in ijson.kvitems_async(f, ""):
            if key == flag_id:
                return value

    raise KeyError


async def async_decode_logical_device_name(logical_device_name: str) -> tuple[str, str]:
    """Decodes logical device name."""
    flag_id = logical_device_name[0:3]
    model = DEFAULT_MODEL

    try:
        manufacturer = await async_decode_flag_id(flag_id)
    except KeyError:
        return "unknown", model

    if flag_id == "INC":
        model = f"Mercury {logical_device_name[3:6]}"

    return manufacturer, model


async def async_get_logical_device_name(hass: HomeAssistant, client: DlmsClient) -> str:
    """Gets the logical device name."""
    data = await hass.async_add_executor_job(
        _get_attribute, client, LOGICAL_DEVICE_NAME
    )
    return data.decode("utf-8")


async def async_get_sw_version(hass: HomeAssistant, client: DlmsClient) -> str:
    """Gets the software version."""
    return await hass.async_add_executor_job(_get_attribute, client, SOFTWARE_PACKAGE)


async def async_get_equipment_id(hass: HomeAssistant, client: DlmsClient) -> str:
    """Gets the equipment identifier."""
    return await hass.async_add_executor_job(_get_attribute, client, EQUIPMENT_ID)


def _connect_and_associate(client: DlmsClient):
    """Connects and associates the client."""
    client.connect()
    client.associate()


def _get_attribute(client: DlmsClient, attribute: cosem.CosemAttribute):
    """Gets COSEM attribute."""
    response = client.get(attribute)
    data = AXDR_DECODER.decode(response)
    return data[ATTR_DATA]


class DlmsConnection:
    """Represents DLMS connection."""

    client: DlmsClient
    disconnected: asyncio.Event
    entry: ConfigEntry
    _reconnect_task: asyncio.Task | None
    _hass: HomeAssistant

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.client = async_get_dlms_client(entry.data)
        self.disconnected = asyncio.Event()
        self.entry = entry
        self._reconnect_task = None
        self._hass = hass

    async def async_setup(self) -> None:
        """Setup the DLMS connection."""
        await self.async_connect()
        self._reconnect_task = asyncio.create_task(self._reconnect_on_failure())

    async def async_connect(self) -> None:
        """Asyncronously connect to the DLMS server."""
        await self._hass.async_add_executor_job(_connect_and_associate, self.client)

    async def _reconnect_on_failure(self) -> None:
        """Task to initiate reconnect on the connection failure."""
        reconnect_interval = RECONNECT_INTERVAL.total_seconds()
        while True:
            await self.disconnected.wait()
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

    def get(self, attribute: cosem.CosemAttribute):
        """Get the attribute."""
        if not self.disconnected.is_set():
            try:
                return _get_attribute(self.client, attribute)
            except Exception:  # pylint: disable=broad-except
                self.disconnected.set()

        return None

    async def async_get(self, attribute: cosem.CosemAttribute):
        """Asyncronously get the attribute."""
        return await self._hass.async_add_executor_job(self.get, attribute)

    def close(self) -> None:
        """Closes the connection."""
        if self._reconnect_task:
            # Cancel reconnect task.
            self._reconnect_task.cancel()

        try:
            self.client.disconnect()
        except Exception:  # pylint: disable=broad-except
            # Ignore errors on disconnect.
            pass

        self.disconnected.set()

    async def async_close(self):
        """Asyncronously closes the connection."""
        await self._hass.async_add_executor_job(self.close)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            name=f"{self.manufacturer} {self.model}",
            identifiers={(DOMAIN, self.entry.unique_id)},
            manufacturer=self.manufacturer,
            model=self.model,
            sw_version=self.sw_version,
        )

    @property
    def manufacturer(self) -> str:
        """Gets the manufacturer."""
        return self.entry.data[ATTR_MANUFACTURER]

    @property
    def model(self) -> str:
        """Gets the model."""
        return self.entry.data[ATTR_MODEL]

    @property
    def sw_version(self) -> str:
        """Gets the software version."""
        return self.entry.data[ATTR_SW_VERSION]

    @classmethod
    async def async_check(
        cls, hass: HomeAssistant, data: MutableMapping[str, Any]
    ) -> DlmsClient:
        """Checks connection to the DLMS meter."""
        client = async_get_dlms_client(data)
        await hass.async_add_executor_job(_connect_and_associate, client)
        return client

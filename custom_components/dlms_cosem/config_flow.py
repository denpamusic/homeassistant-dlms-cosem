"""Config flow for DLMS integration."""
from __future__ import annotations

import asyncio
from collections.abc import MutableMapping
import logging
from typing import Any

from dlms_cosem.client import DlmsClient
from dlms_cosem.exceptions import CommunicationError, LocalDlmsProtocolError
from homeassistant import config_entries
from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, ATTR_SW_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PHYSICAL_ADDRESS,
    CONF_PORT,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DOMAIN,
)
from .dlms_cosem import (
    DlmsConnection,
    async_decode_logical_device_name,
    async_get_equipment_id,
    async_get_logical_device_name,
    async_get_sw_version,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_PHYSICAL_ADDRESS): cv.positive_int,
        vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: HomeAssistant, data: MutableMapping[str, Any]
) -> DlmsClient:
    """Validate the user input allows us to connect.
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        client = await DlmsConnection.async_check(hass, data)
    except (CommunicationError, LocalDlmsProtocolError) as communtication_error:
        raise CannotConnect from communtication_error

    return client


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DLMS integration."""

    VERSION = 1

    def __init__(self) -> None:
        self.client: DlmsClient | None = None
        self.equipment_id: str | None = None
        self.identify_task: asyncio.Task | None = None
        self.init_info: MutableMapping[str, Any] = {}
        self.logical_device_name: str | None = None
        self.manufacturer: str | None = None
        self.model: str | None = None

    async def async_step_user(
        self, user_input: MutableMapping[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            self.client = await validate_input(self.hass, user_input)
            self.init_info = user_input
            return await self.async_step_identify()
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_identify(self, user_input=None) -> FlowResult:
        """Handle the identify step."""

        async def _identify_device():
            try:
                self.manufacturer, self.model = await async_decode_logical_device_name(
                    await async_get_logical_device_name(self.hass, self.client)
                )
                self.equipment_id = await async_get_equipment_id(self.hass, self.client)
                sw_version = await async_get_sw_version(self.hass, self.client)
                self.init_info.update(
                    {
                        ATTR_MANUFACTURER: self.manufacturer,
                        ATTR_MODEL: self.model,
                        ATTR_SW_VERSION: sw_version,
                    }
                )

            finally:
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
                )

        if not self.identify_task:
            self.identify_task = self.hass.async_create_task(_identify_device())
            return self.async_show_progress(
                step_id="identify",
                progress_action="identify_device",
            )

        try:
            await asyncio.wait_for(self.identify_task, timeout=10)
        except (asyncio.TimeoutError, CommunicationError):
            return self.async_show_progress_done(next_step_id="identify_failed")
        finally:
            self.identify_task = None

        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_finish(self, user_input=None) -> FlowResult:
        """Finish the integration config."""
        if self.client:
            await self.hass.async_add_executor_job(self.client.disconnect)

        if self.equipment_id:
            await self._async_set_unique_id(self.equipment_id)

        return self.async_create_entry(
            title=f"{self.manufacturer} {self.model} ({self.equipment_id})",
            data=self.init_info,
        )

    async def async_step_identify_failed(self, user_input=None) -> FlowResult:
        """Handle issues that need transition await from progress step."""
        return self.async_abort(reason="identify_failed")

    async def _async_set_unique_id(self, equipment_id: str) -> None:
        """Set the config entry's unique ID (based on equipment
        identifier)."""
        await self.async_set_unique_id(equipment_id)
        self._abort_if_unique_id_configured()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

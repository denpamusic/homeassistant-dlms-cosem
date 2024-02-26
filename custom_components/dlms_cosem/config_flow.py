"""Config flow for DLMS integration."""
from __future__ import annotations

import asyncio
from collections.abc import MutableMapping
import logging
from operator import itemgetter
from typing import Any, Final

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
    ATTR_EQUIPMENT_ID,
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

DEVICE_INFO_GETTER = itemgetter(ATTR_MANUFACTURER, ATTR_MODEL, ATTR_EQUIPMENT_ID)
IDENTIFY_TIMEOUT: Final = 10

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


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for DLMS integration."""

    VERSION = 1

    client: DlmsClient
    init_info: dict[str, Any]
    identify_task: asyncio.Task[None] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
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

    async def async_step_identify(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the identify step."""

        if self.identify_task is None:
            self.identify_task = self.hass.async_create_task(
                self._async_identify_device()
            )

        if not self.identify_task.done():
            return self.async_show_progress(
                step_id="identify",
                progress_action="identify_device",
                progress_task=self.identify_task,
            )

        try:
            await asyncio.wait_for(self.identify_task, timeout=IDENTIFY_TIMEOUT)
        except (TimeoutError, CommunicationError) as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="identify_failed")
        finally:
            self.identify_task = None

        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Finish the integration config."""
        await self.hass.async_add_executor_job(self.client.disconnect)
        manufacturer, model, equipment_id = DEVICE_INFO_GETTER(self.init_info)
        await self._async_set_unique_id(equipment_id)

        return self.async_create_entry(
            title=f"{manufacturer} {model} ({equipment_id})",
            data=self.init_info,
        )

    async def async_step_identify_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle issues that need transition await from progress step."""
        return self.async_abort(reason="identify_failed")

    async def _async_set_unique_id(self, uid: str) -> None:
        """Set the config entry's unique ID (based on UID)."""
        await self.async_set_unique_id(uid)
        self._abort_if_unique_id_configured()

    async def _async_identify_device(self) -> None:
        """Identify the device."""
        manufacturer, model = await async_decode_logical_device_name(
            await async_get_logical_device_name(self.hass, self.client)
        )
        equipment_id = await async_get_equipment_id(self.hass, self.client)
        sw_version = await async_get_sw_version(self.hass, self.client)
        self.init_info.update(
            {
                ATTR_EQUIPMENT_ID: equipment_id,
                ATTR_MANUFACTURER: manufacturer,
                ATTR_MODEL: model,
                ATTR_SW_VERSION: sw_version,
            }
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

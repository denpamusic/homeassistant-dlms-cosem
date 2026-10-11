"""Config flow for DLMS integration."""

from __future__ import annotations

import asyncio
from collections.abc import MutableMapping
import logging
from operator import itemgetter
from typing import Any, Final, cast

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, ATTR_SW_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import SerialPortSelector
import probatio

from microdlms import CommunicationError

from . import DlmsCosemConfigEntry
from .const import (
    ATTR_EQUIPMENT_ID,
    CONF_PASSWORD,
    CONF_PHYSICAL_ADDRESS,
    CONF_PORT,
    CONF_READ_DELAY,
    COSEM_EQUIPMENT_ID,
    COSEM_LOGICAL_DEVICE_NAME,
    COSEM_SOFTWARE_PACKAGE,
    DEFAULT_PASSWORD,
    DEFAULT_READ_DELAY,
    DOMAIN,
)
from .dlms_cosem import (
    CONNECTION_ERRORS,
    DlmsClient,
    DlmsConnection,
    async_decode_logical_device_name,
)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_PORT): SerialPortSelector(),
        probatio.Required(CONF_PHYSICAL_ADDRESS): cv.positive_int,
        probatio.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        probatio.Required(CONF_READ_DELAY, default=DEFAULT_READ_DELAY): probatio.All(
            probatio.Coerce(int), probatio.Range(min=50, max=500)
        ),
    }
)

DEVICE_INFO_GETTER = itemgetter(ATTR_MANUFACTURER, ATTR_MODEL, ATTR_EQUIPMENT_ID)
IDENTIFY_TIMEOUT: Final = 10  # seconds

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: HomeAssistant, data: MutableMapping[str, Any]
) -> DlmsClient:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        client = await DlmsConnection.async_check(hass, data)
    except CONNECTION_ERRORS as err:
        raise CannotConnect from err

    return client


class DlmsCosemConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DLMS integration."""

    VERSION = 1
    MINOR_VERSION = 3

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.client: DlmsClient | None = None
        self.init_info: dict[str, Any] = {}
        self.identify_task: asyncio.Task[None] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguring an existing entry."""
        errors: dict[str, str] = {}
        entry: DlmsCosemConfigEntry = self._get_reconfigure_entry()

        if user_input is not None:
            coordinator = entry.runtime_data
            await coordinator.async_shutdown()

            try:
                client = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                try:
                    equipment_id = await client.async_get(COSEM_EQUIPMENT_ID)
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(equipment_id)
                    self._abort_if_unique_id_mismatch(reason="unique_id_mismatch")
                    await client.async_disconnect()
                    await asyncio.sleep(user_input[CONF_READ_DELAY] / 1000)
                    return self.async_update_reload_and_abort(
                        entry, data_updates=user_input
                    )
                finally:
                    if client.connected:
                        await client.async_disconnect()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    async def async_step_identify(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Identify the device."""
        if not self.identify_task:
            self.identify_task = self.hass.async_create_task(
                self._async_identify_device(), eager_start=False
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
    ) -> ConfigFlowResult:
        """Finish the integration config."""
        client = cast(DlmsClient, self.client)
        await client.async_disconnect()
        manufacturer, model, equipment_id = DEVICE_INFO_GETTER(self.init_info)
        await self._async_set_unique_id(equipment_id)
        return self.async_create_entry(
            title=f"{manufacturer} {model}", data=self.init_info
        )

    async def async_step_identify_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle issues that need transition await from progress step."""
        return self.async_abort(reason="identify_failed")

    async def _async_set_unique_id(self, uid: str) -> None:
        """Set the config entry's unique ID (based on UID)."""
        await self.async_set_unique_id(uid)
        self._abort_if_unique_id_configured()

    async def _async_identify_device(self) -> None:
        """Identify the device."""
        client = cast(DlmsClient, self.client)
        raw_device_name = await client.async_get(COSEM_LOGICAL_DEVICE_NAME)
        logical_device_name = (
            raw_device_name.decode(encoding="utf-8")
            if isinstance(raw_device_name, bytes)
            else str(raw_device_name)
        )
        manufacturer, model = await async_decode_logical_device_name(
            self.hass, logical_device_name
        )
        equipment_id = await client.async_get(COSEM_EQUIPMENT_ID)
        sw_version = await client.async_get(COSEM_SOFTWARE_PACKAGE)
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

"""The DLMS integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_PORT, CONF_READ_DELAY, DEFAULT_READ_DELAY
from .coordinator import DlmsCoordinator
from .dlms_cosem import CONNECTION_ERRORS, DlmsConnection

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

_LOGGER = logging.getLogger(__name__)

type DlmsCosemConfigEntry = ConfigEntry["DlmsCoordinator"]


async def async_setup_entry(hass: HomeAssistant, entry: DlmsCosemConfigEntry) -> bool:
    """Set up DLMS connection from a config entry."""
    connection = DlmsConnection(hass, entry)

    try:
        await connection.async_connect()
    except CONNECTION_ERRORS as err:
        await connection.async_close()
        raise ConfigEntryNotReady(
            f"Timed out while connecting to {connection.entry.data[CONF_PORT]}"
        ) from err

    coordinator = DlmsCoordinator(hass, connection)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    hass.async_create_background_task(
        coordinator.async_refresh(), "dlms_cosem-initial-refresh"
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DlmsCosemConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: DlmsCosemConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        # Downstream downgrade or unsupported major version
        return False

    if config_entry.version == 1 and config_entry.minor_version < 2:
        new_data = {**config_entry.data}
        new_data[CONF_READ_DELAY] = DEFAULT_READ_DELAY

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, minor_version=2
        )

    if config_entry.version == 1 and config_entry.minor_version < 3:
        new_data = {**config_entry.data}
        if "host" in new_data:
            host = new_data.pop("host")
            port = new_data.get(CONF_PORT)
            if isinstance(port, int):
                new_data[CONF_PORT] = f"socket://{host}:{port}"

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, minor_version=3
        )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True

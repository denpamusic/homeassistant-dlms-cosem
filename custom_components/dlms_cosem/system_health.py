"""Provide info to system health."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

if TYPE_CHECKING:
    from . import DlmsCosemConfigEntry


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


def _get_entry_info(entry: DlmsCosemConfigEntry) -> dict[str, Any]:
    """Get system health info for a single config entry."""
    coordinator = entry.runtime_data
    stats = coordinator.statistics
    return {
        "connected": coordinator.connection.connected,
        "dlms_state": coordinator.dlms_state,
        "requests_count": stats.requests_count,
        "successful_reads": stats.successful_reads,
        "failed_reads": stats.failed_reads,
        "connection_losses": stats.connection_losses,
        "connection_loss_at": stats.connection_loss_at,
    }


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    entries: list[DlmsCosemConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )
    if not entries:
        return {}

    if len(entries) == 1:
        return _get_entry_info(entries[0])

    data: dict[str, dict[str, Any]] = {}
    for entry in entries:
        title = entry.title or entry.entry_id
        for key, value in _get_entry_info(entry).items():
            data.setdefault(key, {})[title] = value

    return {
        key: ", ".join(f"{title}: {val}" for title, val in values.items())
        for key, values in data.items()
    }

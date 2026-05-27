"""The Google dLight integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .client import DlightClient
from .const import (
    CONF_DEVICE_ID,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
)
from .coordinator import DlightCoordinator

PLATFORMS = [Platform.LIGHT]

type DlightConfigEntry = ConfigEntry[DlightCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DlightConfigEntry) -> bool:
    """Set up dLight from a config entry."""
    client = DlightClient(
        entry.data[CONF_HOST],
        entry.data[CONF_DEVICE_ID],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
    )
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = DlightCoordinator(hass, entry, client, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DlightConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: DlightConfigEntry) -> None:
    """Reload the entry when options change (e.g. scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)

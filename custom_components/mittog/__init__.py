"""MitTog — live DSB/Banedanmark departure boards for Home Assistant."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import MitTogConfigEntry, MitTogCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MitTogConfigEntry) -> bool:
    """Set up one station from a config entry."""
    coordinator = MitTogCoordinator(hass, entry)
    await coordinator.async_start()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Subentries (watched departures) are added/removed through the entry's
    # update listeners; a reload is the simplest way to pick them up.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: MitTogConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MitTogConfigEntry) -> bool:
    """Unload a station."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.async_stop()
    return unload_ok

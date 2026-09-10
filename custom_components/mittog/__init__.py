"""MitTog — live DSB/Banedanmark departure boards for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CARD_URL, DOMAIN, VERSION
from .coordinator import MitTogConfigEntry, MitTogCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

_FRONTEND_KEY = f"{DOMAIN}_frontend_registered"


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve mittog-card.js from the integration and load it on dashboards.

    The card ships inside the integration rather than as a separate HACS
    frontend plugin, so it updates in lockstep with the attributes it draws.
    """
    if hass.data.get(_FRONTEND_KEY):
        return
    hass.data[_FRONTEND_KEY] = True

    source = Path(__file__).parent / "www" / "mittog-card.js"
    if not source.is_file():
        _LOGGER.warning("mittog-card.js is missing at %s; the card will not load", source)
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(source), cache_headers=False)]
    )
    # Version query so a browser does not keep serving the previous card.
    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")


async def async_setup_entry(hass: HomeAssistant, entry: MitTogConfigEntry) -> bool:
    """Set up one station from a config entry."""
    await _async_register_card(hass)
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

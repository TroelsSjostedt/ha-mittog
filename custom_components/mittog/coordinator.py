"""Push coordinator wrapping one MitTogClient."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import MitTogClient
from .const import CONF_STATION, CONF_STATION_NAME, DOMAIN
from .model import Board, station_name

_LOGGER = logging.getLogger(__name__)

FIRST_BOARD_TIMEOUT = 20
# How long a dropped connection may last before entities go unavailable.
UNAVAILABLE_AFTER = 120
# Re-evaluate time-dependent state (departed grace, "upcoming") even when the
# board itself hasn't changed.
REEVALUATE_INTERVAL = timedelta(minutes=5)

type MitTogConfigEntry = ConfigEntry[MitTogCoordinator]


class MitTogCoordinator(DataUpdateCoordinator[Board]):
    """Holds the live board for one station and fans updates out to entities."""

    config_entry: MitTogConfigEntry

    def __init__(self, hass: HomeAssistant, entry: MitTogConfigEntry) -> None:
        self.station: str = entry.data[CONF_STATION]
        self.station_name: str = entry.data.get(CONF_STATION_NAME) or station_name(self.station) or self.station
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {self.station}",
            update_interval=None,
        )
        self.client = MitTogClient(
            async_get_clientsession(hass),
            self.station,
            on_board=self._handle_board,
            on_status=self._handle_status,
        )
        self._first_board = asyncio.Event()
        self._unavailable_handle = None
        self._unsub_reevaluate = None

    @property
    def connected(self) -> bool:
        return self.client.connected

    async def async_start(self) -> None:
        """Connect and wait for the first board; raise ConfigEntryNotReady on failure."""
        self.client.start()
        try:
            async with asyncio.timeout(FIRST_BOARD_TIMEOUT):
                await self._first_board.wait()
        except TimeoutError as err:
            await self.client.stop()
            raise ConfigEntryNotReady(
                f"No departure board received for {self.station} within {FIRST_BOARD_TIMEOUT}s"
            ) from err
        self._unsub_reevaluate = async_track_time_interval(
            self.hass, self._reevaluate, REEVALUATE_INTERVAL
        )

    async def async_stop(self) -> None:
        if self._unsub_reevaluate is not None:
            self._unsub_reevaluate()
            self._unsub_reevaluate = None
        self._cancel_unavailable_timer()
        await self.client.stop()

    @callback
    def _handle_board(self, board: Board) -> None:
        self._first_board.set()
        self.async_set_updated_data(board)

    @callback
    def _handle_status(self, connected: bool) -> None:
        if connected:
            self._cancel_unavailable_timer()
            if not self.last_update_success and self.data is not None:
                # Back online; re-publish what we have until a fresh board arrives.
                self.async_set_updated_data(self.data)
            return
        if self._unavailable_handle is None:
            self._unavailable_handle = async_call_later(
                self.hass, UNAVAILABLE_AFTER, self._mark_unavailable
            )

    @callback
    def _mark_unavailable(self, _now) -> None:
        self._unavailable_handle = None
        if not self.client.connected:
            self.async_set_update_error(
                ConnectionError(f"{self.station}: no connection for {UNAVAILABLE_AFTER}s")
            )

    @callback
    def _cancel_unavailable_timer(self) -> None:
        if self._unavailable_handle is not None:
            self._unavailable_handle()
            self._unavailable_handle = None

    @callback
    def _reevaluate(self, _now) -> None:
        if self.last_update_success:
            self.async_update_listeners()

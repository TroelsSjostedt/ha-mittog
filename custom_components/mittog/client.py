"""Websocket client for the MitTog departure feed.

Keeps one connection per station open, reconnects with backoff, and hands
every *changed* board to a callback. Only depends on aiohttp so it can be
exercised outside Home Assistant.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
import random

import aiohttp

from .const import (
    WS_IDLE_TIMEOUT,
    WS_ORIGIN,
    WS_RECONNECT_MAX,
    WS_RECONNECT_MIN,
    WS_URL,
)
from .model import Board, parse_board

_LOGGER = logging.getLogger(__name__)

BoardCallback = Callable[[Board], None]
StatusCallback = Callable[[bool], None]


class MitTogClient:
    """Long-lived websocket connection to one station's departure board."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        station: str,
        on_board: BoardCallback,
        on_status: StatusCallback | None = None,
    ) -> None:
        self._session = session
        self.station = station.upper()
        self._on_board = on_board
        self._on_status = on_status
        self._task: asyncio.Task[None] | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._last_trains: str | None = None
        self.connected = False
        self.board: Board | None = None

    @property
    def url(self) -> str:
        return WS_URL.format(station=self.station)

    def start(self) -> None:
        """Start the background connection loop."""
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(
                self._run(), name=f"mittog-{self.station}"
            )

    async def stop(self) -> None:
        """Stop the loop and close the socket."""
        task, self._task = self._task, None
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def fetch_once(self, timeout: float = 15) -> Board:
        """Open a connection, wait for one board, close. Used by config flow."""
        async with self._session.ws_connect(
            self.url, headers={"Origin": WS_ORIGIN}, heartbeat=30
        ) as ws:
            async with asyncio.timeout(timeout):
                while True:
                    msg = await ws.receive()
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        return parse_board(json.loads(msg.data))
                    if msg.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.ERROR,
                    ):
                        raise ConnectionError(f"websocket closed: {msg.type}")

    async def _run(self) -> None:
        backoff = WS_RECONNECT_MIN
        while True:
            try:
                await self._connect_and_listen()
                backoff = WS_RECONNECT_MIN
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, OSError) as err:
                _LOGGER.warning(
                    "%s: connection lost (%s), reconnecting in %ss", self.station, err, backoff
                )
            except Exception:  # noqa: BLE001 - keep the loop alive no matter what
                _LOGGER.exception("%s: unexpected error, reconnecting in %ss", self.station, backoff)
            self._set_connected(False)
            await asyncio.sleep(backoff + random.uniform(0, 2))
            backoff = min(backoff * 2, WS_RECONNECT_MAX)

    async def _connect_and_listen(self) -> None:
        _LOGGER.debug("%s: connecting to %s", self.station, self.url)
        async with self._session.ws_connect(
            self.url, headers={"Origin": WS_ORIGIN}, heartbeat=30
        ) as ws:
            self._ws = ws
            try:
                while True:
                    async with asyncio.timeout(WS_IDLE_TIMEOUT.total_seconds()):
                        msg = await ws.receive()
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        self._handle_text(msg.data)
                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSING,
                        aiohttp.WSMsgType.CLOSED,
                    ):
                        raise ConnectionError("server closed the connection")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        raise ConnectionError(f"websocket error: {ws.exception()}")
            finally:
                self._ws = None

    def _handle_text(self, text: str) -> None:
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            _LOGGER.warning("%s: discarding non-JSON message", self.station)
            return
        self._set_connected(True)
        # The server re-sends the whole board every ~5 s with a fresh
        # "Created" stamp; only the train list matters for change detection.
        trains = json.dumps((message.get("data") or {}).get("Trains"), sort_keys=True)
        if trains == self._last_trains:
            return
        self._last_trains = trains
        self.board = parse_board(message)
        try:
            self._on_board(self.board)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("%s: board callback failed", self.station)

    def _set_connected(self, value: bool) -> None:
        if value == self.connected:
            return
        self.connected = value
        _LOGGER.info("%s: %s", self.station, "connected" if value else "disconnected")
        if self._on_status is not None:
            self._on_status(value)

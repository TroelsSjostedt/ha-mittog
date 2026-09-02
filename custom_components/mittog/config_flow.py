"""Config flow: one entry per station, one subentry per watched departure."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigEntryState,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)

from .client import MitTogClient
from .const import (
    CONF_DIRECTION,
    CONF_STATION,
    CONF_STATION_NAME,
    CONF_TIME,
    DIRECTIONS,
    DOMAIN,
    SUBENTRY_DEPARTURE,
)
from .model import Board, station_name

_LOGGER = logging.getLogger(__name__)


def _board_preview(board: Board | None) -> str:
    """Short list of upcoming trains, so the user can see which direction is which."""
    if board is None:
        return "—"
    lines = []
    for t in board.upcoming()[:8]:
        dest = station_name(t.destination) or "?"
        lines.append(f"{t.scheduled:%H:%M} → {dest} ({t.direction})")
    return "\n".join(lines) if lines else "—"


class MitTogConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a station."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_DEPARTURE: DepartureSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            code = user_input[CONF_STATION].strip().upper()
            await self.async_set_unique_id(code)
            self._abort_if_unique_id_configured()
            client = MitTogClient(async_get_clientsession(self.hass), code, lambda _b: None)
            try:
                board = await client.fetch_once()
            except (aiohttp.ClientError, ConnectionError, TimeoutError, OSError):
                _LOGGER.debug("Could not fetch board for %s", code, exc_info=True)
                errors["base"] = "cannot_connect"
            else:
                if not board.trains:
                    errors["base"] = "no_trains"
                else:
                    name = (user_input.get(CONF_STATION_NAME) or "").strip() or (
                        station_name(code) or code
                    )
                    return self.async_create_entry(
                        title=name,
                        data={CONF_STATION: code, CONF_STATION_NAME: name},
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION, default=(user_input or {}).get(CONF_STATION, "")): TextSelector(),
                vol.Optional(CONF_STATION_NAME, default=(user_input or {}).get(CONF_STATION_NAME, "")): TextSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class DepartureSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure a watched departure."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._async_step_form(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._async_step_form(user_input)

    async def _async_step_form(
        self, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        entry = self._get_entry()
        station = entry.data[CONF_STATION]
        reconfigure = self.source == SOURCE_RECONFIGURE
        current = dict(self._get_reconfigure_subentry().data) if reconfigure else {}
        if reconfigure:
            current[CONF_NAME] = self._get_reconfigure_subentry().title
        errors: dict[str, str] = {}

        if user_input is not None:
            hhmm = str(user_input[CONF_TIME])[:5]
            direction = user_input[CONF_DIRECTION]
            name = user_input[CONF_NAME].strip() or f"{station} {hhmm}"
            unique_id = f"{station}_{hhmm}_{direction}"
            data = {CONF_TIME: hhmm, CONF_DIRECTION: direction}
            if reconfigure:
                return self.async_update_and_abort(
                    entry,
                    self._get_reconfigure_subentry(),
                    title=name,
                    data=data,
                    unique_id=unique_id,
                )
            return self.async_create_entry(title=name, data=data, unique_id=unique_id)

        board: Board | None = None
        if entry.state is ConfigEntryState.LOADED:
            board = entry.runtime_data.data
        if board is None:
            client = MitTogClient(async_get_clientsession(self.hass), station, lambda _b: None)
            try:
                board = await client.fetch_once()
            except (aiohttp.ClientError, ConnectionError, TimeoutError, OSError):
                board = None

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=current.get(CONF_NAME, "")): TextSelector(),
                vol.Required(CONF_TIME, default=f"{current.get(CONF_TIME, '07:00')}:00"): TimeSelector(),
                vol.Required(CONF_DIRECTION, default=current.get(CONF_DIRECTION, DIRECTIONS[0])): SelectSelector(
                    SelectSelectorConfig(
                        options=DIRECTIONS,
                        mode=SelectSelectorMode.LIST,
                        translation_key="direction",
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="reconfigure" if reconfigure else "user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "station": entry.title,
                "preview": _board_preview(board),
            },
        )

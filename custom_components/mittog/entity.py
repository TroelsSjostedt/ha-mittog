"""Base entities."""

from __future__ import annotations

from datetime import time

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DIRECTION, CONF_TIME, DOMAIN
from .coordinator import MitTogCoordinator
from .model import Train


def station_device_info(coordinator: MitTogCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.station)},
        name=coordinator.station_name,
        manufacturer="Banedanmark",
        model="MitTog afgangstavle",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=f"https://mittog.dk/da/{coordinator.station}",
    )


class MitTogStationEntity(CoordinatorEntity[MitTogCoordinator]):
    """Entity attached to the station device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MitTogCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = station_device_info(coordinator)


class MitTogDepartureEntity(CoordinatorEntity[MitTogCoordinator]):
    """Entity attached to a watched departure (a config subentry)."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MitTogCoordinator, subentry: ConfigSubentry, key: str
    ) -> None:
        super().__init__(coordinator)
        self.subentry = subentry
        hh, mm = str(subentry.data[CONF_TIME])[:5].split(":")
        self.watch_time = time(int(hh), int(mm))
        self.watch_direction: str = subentry.data[CONF_DIRECTION]
        self._attr_unique_id = f"{subentry.subentry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Banedanmark",
            model=f"Afgang {self.watch_time:%H:%M} {self.watch_direction}",
            via_device=(DOMAIN, coordinator.station),
        )

    @property
    def train(self) -> Train | None:
        """The watched train, if currently on the board."""
        board = self.coordinator.data
        if board is None:
            return None
        return board.find_departure(self.watch_time, self.watch_direction)

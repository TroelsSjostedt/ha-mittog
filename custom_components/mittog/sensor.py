"""Sensors: station board + watched departures."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SUBENTRY_DEPARTURE
from .coordinator import MitTogConfigEntry
from .entity import MitTogDepartureEntity, MitTogStationEntity
from .model import Train, train_attributes, train_summary

STATUS_OPTIONS = ["ikke_i_feed", "planlagt", "til_tiden", "forsinket", "aflyst", "afgaaet"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MitTogConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([NextDepartureSensor(coordinator)])
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_DEPARTURE:
            continue
        async_add_entities(
            [
                DepartureSensor(coordinator, subentry),
                DelaySensor(coordinator, subentry),
                TrackSensor(coordinator, subentry),
                CarsSensor(coordinator, subentry),
                StatusSensor(coordinator, subentry),
            ],
            config_subentry_id=subentry.subentry_id,
        )


class NextDepartureSensor(MitTogStationEntity, SensorEntity):
    """Next departure from the station, with the whole board as attributes."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "naeste_afgang")

    @property
    def native_value(self) -> datetime | None:
        upcoming = self.coordinator.data.upcoming() if self.coordinator.data else []
        return upcoming[0].expected if upcoming else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        board = self.coordinator.data
        upcoming = board.upcoming() if board else []
        return {
            "station": self.coordinator.station,
            "afgange": [train_summary(t) for t in upcoming[:10]],
            "opdateret": board.created if board else None,
        }


class DepartureSensor(MitTogDepartureEntity, SensorEntity):
    """Expected departure time of the watched train, with everything as attributes."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, subentry) -> None:
        super().__init__(coordinator, subentry, "afgang")

    @property
    def native_value(self) -> datetime | None:
        train = self.train
        return train.expected if train else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        base = {
            "station": self.coordinator.station,
            "overvaaget_tid": self.watch_time.strftime("%H:%M"),
            "overvaaget_retning": self.watch_direction,
        }
        train = self.train
        if train is None:
            return {**base, "status": "ikke_i_feed"}
        return {**base, **train_attributes(train)}


class DelaySensor(MitTogDepartureEntity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-alert-outline"

    def __init__(self, coordinator, subentry) -> None:
        super().__init__(coordinator, subentry, "forsinkelse")

    @property
    def native_value(self) -> int | None:
        train = self.train
        if train is None or train.cancelled:
            return None
        return train.delay_minutes


class TrackSensor(MitTogDepartureEntity, SensorEntity):
    _attr_icon = "mdi:sign-direction"

    def __init__(self, coordinator, subentry) -> None:
        super().__init__(coordinator, subentry, "spor")

    @property
    def native_value(self) -> str | None:
        train = self.train
        return train.track if train else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        train = self.train
        if train is None:
            return {}
        return {
            "spor_oprindeligt": train.track_original,
            "spor_forrige": train.track_previous,
            "spor_aendret": train.track_changed,
        }


class CarsSensor(MitTogDepartureEntity, SensorEntity):
    _attr_icon = "mdi:train-car"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, subentry) -> None:
        super().__init__(coordinator, subentry, "vogne")

    @property
    def native_value(self) -> int | None:
        train = self.train
        return len(train.cars) if train else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        train = self.train
        if train is None:
            return {}
        attrs = train_attributes(train)
        return {
            k: attrs[k]
            for k in ("vogne", "togsaet", "togsaet_antal", "foerste_klasse", "stillezone", "cykler")
        }


class StatusSensor(MitTogDepartureEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUS_OPTIONS
    _attr_icon = "mdi:train"

    def __init__(self, coordinator, subentry) -> None:
        super().__init__(coordinator, subentry, "status")

    @property
    def native_value(self) -> str:
        train: Train | None = self.train
        return train.status if train else "ikke_i_feed"

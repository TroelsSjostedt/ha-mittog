"""Data model for the MitTog departure feed.

Pure Python, no Home Assistant imports — this module is unit-tested against
recorded feed messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from itertools import groupby
from typing import Any
from zoneinfo import ZoneInfo

from .const import (
    DELAY_THRESHOLD_MIN,
    DEPARTED_GRACE,
    STATION_ALIASES,
    STATION_NAMES,
    UNIT_TYPES,
)

TZ = ZoneInfo("Europe/Copenhagen")

# The feed uses "01-01-0001 00:00:00" (and the ISO variant) for "not set".
_TS_FORMAT = "%d-%m-%Y %H:%M:%S"
_SENTINEL_PREFIXES = ("01-01-0001", "0001-01-01")


def parse_ts(value: str | None) -> datetime | None:
    """Parse a feed timestamp into an aware datetime, or None if unset."""
    if not value or value.startswith(_SENTINEL_PREFIXES):
        return None
    try:
        return datetime.strptime(value, _TS_FORMAT).replace(tzinfo=TZ)
    except ValueError:
        return None


def station_name(code: str | None) -> str | None:
    """Human name for a Banedanmark station code, falling back to the code."""
    if not code:
        return None
    code = STATION_ALIASES.get(code, code)
    return STATION_NAMES.get(code, code)


@dataclass(frozen=True)
class Car:
    """One car (door number as shown on the platform display)."""

    number: str
    services: tuple[str, ...]

    @property
    def first_class(self) -> bool:
        return "FirstClass" in self.services

    @property
    def quiet_zone(self) -> bool:
        return "QuietZone" in self.services

    @property
    def bicycles(self) -> bool:
        return "BicycleCoaches" in self.services


@dataclass(frozen=True)
class Unit:
    """One train set / vehicle in the consist, in platform order."""

    unit_type: str
    unit_id: str | None
    destination: str | None
    cars: tuple[Car, ...]
    not_accessible: bool
    remarks: tuple[str, ...]

    @property
    def label(self) -> str:
        return UNIT_TYPES.get(self.unit_type, self.unit_type)


@dataclass(frozen=True)
class Train:
    """One row on the departure board."""

    train_id: str
    product: str
    scheduled: datetime
    estimated: datetime | None
    direction: str
    track: str | None
    track_previous: str | None
    track_original: str | None
    cancelled: bool
    departed: datetime | None
    information_type: str
    remark: str
    units: tuple[Unit, ...]

    @property
    def has_forecast(self) -> bool:
        return self.estimated is not None

    @property
    def expected(self) -> datetime:
        """Best known departure time."""
        return self.estimated or self.scheduled

    @property
    def delay_minutes(self) -> int | None:
        """Delay in whole minutes, None while there is no forecast.

        Rounded, not truncated: the platform displays round 1:48 up to 2 min,
        and a card that disagrees with the sign above the track is worse than
        useless. Confirmed against Vordingborg on 7 Sep 2026.
        """
        if self.estimated is None:
            return None
        return max(0, round((self.estimated - self.scheduled).total_seconds() / 60))

    @property
    def is_delayed(self) -> bool:
        return (self.delay_minutes or 0) >= DELAY_THRESHOLD_MIN

    @property
    def track_changed(self) -> bool:
        return bool(self.track_original) and self.track_original != self.track

    @property
    def destination(self) -> str | None:
        """Destination code of the first unit (units may split en route)."""
        for unit in self.units:
            if unit.destination:
                return unit.destination
        return None

    @property
    def cars(self) -> tuple[Car, ...]:
        return tuple(car for unit in self.units for car in unit.cars)

    @property
    def car_numbers(self) -> list[str]:
        return [car.number for car in self.cars]

    @property
    def consist(self) -> str:
        """Compact description: '2 × IC3', 'Lokomotiv + 4 × Dobbeltdækker'."""
        parts: list[str] = []
        for label, run in groupby(unit.label for unit in self.units):
            n = len(list(run))
            parts.append(label if n == 1 else f"{n} × {label}")
        return " + ".join(parts)

    @property
    def status(self) -> str:
        """Single-word status suitable for an enum sensor."""
        if self.cancelled:
            return "aflyst"
        if self.departed is not None:
            return "afgaaet"
        if self.estimated is None:
            return "planlagt"
        if self.is_delayed:
            return "forsinket"
        return "til_tiden"

    @property
    def name(self) -> str:
        return f"{self.product} {self.train_id}".strip()


@dataclass(frozen=True)
class Board:
    """A full departure board for one station."""

    station: str
    created: str | None
    trains: tuple[Train, ...] = field(default_factory=tuple)

    def find_departure(
        self, at: time, direction: str, now: datetime | None = None
    ) -> Train | None:
        """Find the watched departure: scheduled time-of-day + direction.

        Picks the earliest matching train that has not departed more than
        DEPARTED_GRACE ago, so a departed train stays visible for a while and
        tomorrow's train takes over once it appears in the feed.
        """
        now = now or datetime.now(TZ)
        cutoff = now - DEPARTED_GRACE
        candidates = [
            t
            for t in self.trains
            if t.direction == direction
            and (t.scheduled.hour, t.scheduled.minute) == (at.hour, at.minute)
            and t.expected >= cutoff
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda t: t.scheduled)

    def upcoming(self, now: datetime | None = None) -> list[Train]:
        """Trains that have not departed yet, in order of expected departure."""
        now = now or datetime.now(TZ)
        return sorted(
            (t for t in self.trains if t.departed is None and t.expected >= now - timedelta(minutes=1)),
            key=lambda t: t.expected,
        )


def _parse_unit(raw: dict[str, Any]) -> Unit:
    cars = tuple(
        Car(number=str(d.get("Number") or ""), services=tuple(d.get("Services") or ()))
        for d in raw.get("Doors") or ()
    )
    remarks = tuple(str(r) for r in raw.get("Remarks") or () if r)
    return Unit(
        unit_type=str(raw.get("UnitType") or ""),
        unit_id=raw.get("UnitId"),
        destination=raw.get("DestinationStationId"),
        cars=cars,
        not_accessible=bool(raw.get("NotAccessibleToPassengers")),
        remarks=remarks,
    )


def _parse_train(raw: dict[str, Any]) -> Train | None:
    scheduled = parse_ts(raw.get("ScheduleTimeDeparture")) or parse_ts(raw.get("ScheduleTime"))
    if scheduled is None:
        return None
    return Train(
        train_id=str(raw.get("PublicTrainId") or raw.get("TrainId") or ""),
        product=str(raw.get("Product") or ""),
        scheduled=scheduled,
        estimated=parse_ts(raw.get("EstimatedTimeDeparture")),
        direction=str(raw.get("DepartureDirection") or ""),
        track=raw.get("TrackCurrent") or None,
        track_previous=raw.get("TrackPrevious") or None,
        track_original=raw.get("TrackOriginal") or None,
        cancelled=bool(raw.get("IsCancelled") or raw.get("IsCancelledDeparture")),
        departed=parse_ts(raw.get("TrainDeparted")),
        information_type=str(raw.get("InformationType") or ""),
        remark=str(raw.get("Remark") or ""),
        units=tuple(_parse_unit(u) for u in raw.get("Routes") or ()),
    )


def parse_board(message: dict[str, Any]) -> Board:
    """Parse one websocket message into a Board."""
    data = message.get("data") or {}
    trains = tuple(
        t for t in (_parse_train(raw) for raw in data.get("Trains") or ()) if t is not None
    )
    return Board(
        station=str(data.get("StationId") or ""),
        created=data.get("Created"),
        trains=trains,
    )


def train_summary(train: Train) -> dict[str, Any]:
    """Compact dict for attributes on the station board sensor."""
    return {
        "tog": train.name,
        "planlagt": train.scheduled.strftime("%H:%M"),
        "forventet": train.expected.strftime("%H:%M") if train.has_forecast else None,
        "forsinkelse_min": train.delay_minutes,
        "spor": train.track,
        "retning": train.direction,
        "destination": station_name(train.destination),
        "aflyst": train.cancelled,
        "vogne": train.car_numbers,
        "togsaet": train.consist,
    }


def train_attributes(train: Train) -> dict[str, Any]:
    """Full attribute set for a watched departure."""
    first_class = [c.number for c in train.cars if c.first_class]
    quiet = [c.number for c in train.cars if c.quiet_zone]
    bikes = [c.number for c in train.cars if c.bicycles]
    return {
        "tog": train.name,
        "tognummer": train.train_id,
        "produkt": train.product,
        "planlagt": train.scheduled.isoformat(),
        "forventet": train.expected.isoformat(),
        "prognose": train.has_forecast,
        "forsinkelse_min": train.delay_minutes,
        "forsinket": train.is_delayed,
        "aflyst": train.cancelled,
        "afgaaet": train.departed is not None,
        "status": train.status,
        "spor": train.track,
        "spor_oprindeligt": train.track_original,
        "spor_aendret": train.track_changed,
        "retning": train.direction,
        "destination": station_name(train.destination),
        "destination_kode": train.destination,
        "togsaet": train.consist,
        "togsaet_antal": len(train.units),
        "vogne": train.car_numbers,
        "vogne_antal": len(train.cars),
        "foerste_klasse": first_class,
        "stillezone": quiet,
        "cykler": bikes,
        "bemaerkning": train.remark or None,
        "informationstype": train.information_type,
    }

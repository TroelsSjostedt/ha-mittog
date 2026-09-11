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
    BUS_LINES,
    DELAY_THRESHOLD_MIN,
    DEPARTED_GRACE,
    PRODUCT_COLORS,
    PRODUCT_LABELS,
    PRODUCT_OPERATORS,
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


def product_label(code: str | None) -> str:
    """What the platform display calls this product.

    The feed carries Banedanmark's internal code; every sign, announcement and
    app shows something else — "RØ" is printed as "Re". The mapping is
    mittog.dk's own, taken from the same bundle as the station table.
    """
    if not code:
        return ""
    return PRODUCT_LABELS.get(code, code)


def bus_line(line_name: str | None) -> tuple[str, str, str] | None:
    """The coloured line a replacement bus runs, or None if it has no line.

    Matched case-insensitively, the way mittog.dk matches it — the feed's
    casing is not guaranteed and is not worth depending on.
    """
    if not line_name:
        return None
    return BUS_LINES.get(line_name.strip().lower())


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
class Stop:
    """One station on a unit's onward route, with its expected time."""

    code: str
    expected: datetime | None
    cancelled: bool

    @property
    def name(self) -> str:
        return station_name(self.code) or self.code


@dataclass(frozen=True)
class Unit:
    """One train set / vehicle in the consist, in platform order."""

    unit_type: str
    unit_id: str | None
    destination: str | None
    cars: tuple[Car, ...]
    not_accessible: bool
    remarks: tuple[str, ...]
    stops: tuple[Stop, ...] = ()

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
    line_name: str | None = None
    operator: str | None = None

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
    def stops(self) -> tuple[Stop, ...]:
        """Onward route of the FRONT unit.

        Stops are per-unit because a train can split en route; the front unit
        is the one the platform display draws first, so its route is the one a
        passenger reads. `splits` says when the other units disagree.
        """
        for unit in self.units:
            if unit.stops:
                return unit.stops
        return ()

    @property
    def splits(self) -> bool:
        """True when the units do not all run to the same destination."""
        seen = {u.destination for u in self.units if u.destination}
        return len(seen) > 1

    @property
    def front_car(self) -> str | None:
        """Car number at the front, in the direction of travel.

        The feed lists cars train-relative, front first. Verified against the
        platform display at Vordingborg on 7 Sep 2026 (RO 1273, 22-21-12-11
        toward Nykobing F, car 22 physically at the front).
        """
        numbers = self.car_numbers
        return numbers[0] if numbers else None

    @property
    def rear_car(self) -> str | None:
        numbers = self.car_numbers
        return numbers[-1] if numbers else None

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
        label = product_label(self.product)
        if self.product == "TRAINBUS":
            # A replacement bus has an internal run number, not a train number
            # anyone announces — showing it would only look like a train. What
            # it does have is a coloured line, and that is what is painted on
            # the bus and printed on the sign.
            line = bus_line(self.line_name)
            return f"{line[0]} {label.lower()}" if line else label
        return f"{label} {self.train_id}".strip()

    @property
    def line(self) -> str | None:
        """Name of the coloured bus line, e.g. "Rød"."""
        line = bus_line(self.line_name)
        return line[0] if line else None

    @property
    def colors(self) -> tuple[str | None, str | None]:
        """Badge background and text colour, as the platform sign uses them."""
        line = bus_line(self.line_name)
        if line:
            return line[1], line[2]
        return PRODUCT_COLORS.get(self.product, (None, None))


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
    stops = tuple(
        Stop(
            code=str(st.get("StationId") or ""),
            expected=parse_ts(st.get("ExpectedDateTime")),
            cancelled=bool(st.get("IsCancelled")),
        )
        for st in raw.get("Stations") or ()
        if st.get("StationId")
    )
    return Unit(
        unit_type=str(raw.get("UnitType") or ""),
        unit_id=raw.get("UnitId"),
        destination=raw.get("DestinationStationId"),
        cars=cars,
        not_accessible=bool(raw.get("NotAccessibleToPassengers")),
        remarks=remarks,
        stops=stops,
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
        line_name=raw.get("LineName") or None,
        operator=(raw.get("TOC") or None) if raw.get("TOC") != "Ukendt" else None,
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
        "produkt_navn": product_label(train.product),
        "operatoer": train.operator or PRODUCT_OPERATORS.get(train.product),
        "produkt_farve": train.colors[0],
        "produkt_tekstfarve": train.colors[1],
        "linje": train.line,
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
        "forende": train.front_car,
        "bagende": train.rear_car,
        "stop": [
            {
                "station": s.name,
                "kode": s.code,
                "forventet": s.expected.isoformat() if s.expected else None,
                "aflyst": s.cancelled,
            }
            for s in train.stops
        ],
        "deler_sig": train.splits,
        "bemaerkning": train.remark or None,
        "informationstype": train.information_type,
    }

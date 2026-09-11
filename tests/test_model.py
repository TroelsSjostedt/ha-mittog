"""Unit tests for the feed parser. Run: .venv/bin/python -m pytest tests/"""
import json
from datetime import datetime, time, timedelta


from mittog.model import TZ, Train, _parse_train, parse_board, product_label, parse_ts, station_name, train_attributes, train_summary  # noqa: E402

import pathlib
FIX = pathlib.Path(__file__).resolve().parent / "fixtures"


def load(station):
    return parse_board(json.loads((FIX / f"{station}.json").read_text()))


def test_parse_ts():
    assert parse_ts("01-01-0001 00:00:00") is None
    assert parse_ts("0001-01-01T00:00:00") is None
    assert parse_ts(None) is None
    assert parse_ts("02-09-2026 11:30:00") == datetime(2026, 9, 2, 11, 30, tzinfo=TZ)


def test_vo_board():
    b = load("VO")
    assert b.station == "VO"
    assert len(b.trains) == 20
    t = b.trains[0]
    assert t.name == "Re 4837"
    assert t.scheduled.strftime("%H:%M") == "11:30"
    assert t.has_forecast and t.delay_minutes == 0 and t.status == "til_tiden"
    assert t.track == "3" and not t.track_changed
    assert t.destination == "NF"
    assert t.consist == "IC3" and t.car_numbers == ["12", "11"]
    assert t.cars[1].first_class and t.cars[0].bicycles
    later = b.trains[4]
    assert later.estimated is None and later.status == "planlagt" and later.delay_minutes is None
    assert later.expected == later.scheduled


def test_nel_delay_and_consist():
    b = load("NEL")
    t = next(x for x in b.trains if x.train_id == "2424")
    assert t.delay_minutes == 3 and t.is_delayed and t.status == "forsinket"
    assert t.consist == "2 × IC3" and t.car_numbers == ["11", "12", "22", "21"]
    dd = next(x for x in b.trains if x.train_id == "4445")
    assert dd.car_numbers == ["1", "14", "13", "12", "11"]
    assert dd.units[0].label == "Lokomotiv"
    assert dd.consist == "Lokomotiv + 4 × Dobbeltdækker"
    ic = next(x for x in b.trains if x.train_id == "826")
    assert len(ic.units) == 2 and ic.destination == "HGL"
    assert station_name("HGL") == "Østerport" and station_name("HG") == "Helsingør"


def test_find_departure():
    b = load("VO")
    now = datetime(2026, 9, 2, 11, 0, tzinfo=TZ)
    down = b.find_departure(time(11, 30), "DOWN", now)
    up = b.find_departure(time(11, 30), "UP", now)
    assert down.train_id == "4828" and up.train_id == "4837"
    assert b.find_departure(time(6, 55), "DOWN", now) is None
    late = datetime(2026, 9, 2, 12, 45, tzinfo=TZ)
    assert b.find_departure(time(11, 30), "DOWN", late) is None
    within = datetime(2026, 9, 2, 12, 15, tzinfo=TZ)
    assert b.find_departure(time(11, 30), "DOWN", within).train_id == "4828"


def test_upcoming_and_attributes():
    b = load("NEL")
    now = datetime(2026, 9, 2, 11, 30, tzinfo=TZ)
    up = b.upcoming(now)
    assert [t.train_id for t in up[:3]] == ["843", "2424", "50222"]  # sorted by expected, 822 (est 11:26) gone
    t = up[1]
    attrs = train_attributes(t)
    assert attrs["forsinkelse_min"] == 3 and attrs["vogne"] == ["11", "12", "22", "21"]
    assert attrs["foerste_klasse"] == ["11"] and attrs["stillezone"] == ["11", "21"]
    assert attrs["destination"] == "København H"
    s = train_summary(t)
    assert s["forventet"] == "11:40" and s["planlagt"] == "11:37"


def test_delay_rounds_to_nearest_minute():
    """1:48 late is 2 minutes on the platform display, not 1."""
    sched = datetime(2026, 9, 7, 6, 55, 0, tzinfo=TZ)
    for secs, expected in ((0, 0), (29, 0), (31, 1), (108, 2), (-60, 0)):
        t = Train(
            train_id="1208",
            product="RØ",
            scheduled=sched,
            estimated=sched + timedelta(seconds=secs),
            direction="DOWN",
            track="2",
            track_previous=None,
            track_original=None,
            cancelled=False,
            departed=None,
            information_type="NORMAL",
            remark=None,
            units=[],
        )
        assert t.delay_minutes == expected, f"{secs}s -> {t.delay_minutes}, want {expected}"


def test_stops_come_from_the_front_unit():
    """The stop list is per-unit; the front unit's route is the one shown."""
    board = load("NEL")
    train = next(t for t in board.trains if t.train_id == "822")
    codes = [s.code for s in train.stops]
    assert codes[:3] == ["KH", "KN", "KK"]
    assert train.stops[0].name == "København H"
    assert train.stops[0].expected is not None
    attrs = train_attributes(train)
    assert attrs["stop"][0]["station"] == "København H"
    assert attrs["stop"][0]["kode"] == "KH"
    assert attrs["stop"][0]["aflyst"] is False


def test_front_and_rear_car_follow_feed_order():
    """vogne[0] is the front — confirmed on the platform at Vordingborg."""
    board = load("NEL")
    train = next(t for t in board.trains if t.train_id == "2424")
    assert train.car_numbers == ["11", "12", "22", "21"]
    assert train.front_car == "11"
    assert train.rear_car == "21"
    attrs = train_attributes(train)
    assert attrs["forende"] == "11" and attrs["bagende"] == "21"


def test_product_labels_match_the_platform_display():
    """The feed says RØ; every sign, app and announcement says Re."""
    assert product_label("RØ") == "Re"
    assert product_label("IC") == "IC"
    assert product_label("XP") == "ST"          # Snälltåget
    assert product_label("TRAINBUS") == "Togbus"
    assert product_label("ØD") == "L"           # Lokaltog
    assert product_label("ZZZ") == "ZZZ"        # unknown code passes through
    assert product_label(None) == ""


def test_train_name_uses_the_label():
    board = load("NEL")
    train = next(t for t in board.trains if t.train_id == "2424")
    assert train.product == "RØ"
    assert train.name == "Re 2424"
    attrs = train_attributes(train)
    assert attrs["tog"] == "Re 2424"
    assert attrs["produkt"] == "RØ"             # raw code kept
    assert attrs["produkt_navn"] == "Re"
    assert attrs["operatoer"] == "DSB"
    assert attrs["produkt_farve"] == "#50AE30"


def _bus(line_name):
    """A replacement-bus row shaped like the feed's."""
    return _parse_train({
        "PublicTrainId": "2012721",
        "Product": "TRAINBUS",
        "ScheduleTimeDeparture": "10-09-2026 22:25:00",
        "EstimatedTimeDeparture": "01-01-0001 00:00:00",
        "DepartureDirection": "DOWN",
        "TrackCurrent": "?",
        "Remark": "Busterminal foran stationen",
        "InformationType": "NORMAL",
        "LineName": line_name,
        "TOC": "DSB",
        "Routes": [{"DestinationStationId": "NÆ", "Stations": [
            {"StationId": "NÆ", "ExpectedDateTime": "10-09-2026 23:10:00"}]}],
    })


def test_bus_line_gives_the_bus_a_colour_and_a_name():
    """A togbus runs a coloured line, not a train number."""
    red = _bus("rød")
    assert red.line == "Rød"
    assert red.name == "Rød togbus"
    assert red.colors == ("#F03C1F", "#FFF")

    # The feed's casing is not guaranteed; mittog.dk lowercases before matching.
    assert _bus("Blå").line == "Blå"
    assert _bus("TURKIS").name == "Turkis togbus"

    plain = _bus(None)
    assert plain.line is None
    assert plain.name == "Togbus"
    assert plain.colors == ("#767680", "#FFF")

    attrs = train_attributes(red)
    assert attrs["tog"] == "Rød togbus" and attrs["linje"] == "Rød"
    assert attrs["produkt_farve"] == "#F03C1F"
    assert attrs["operatoer"] == "DSB"
    assert attrs["vogne"] == []          # buses report no composition
    assert attrs["stop"][0]["station"] == "Næstved"

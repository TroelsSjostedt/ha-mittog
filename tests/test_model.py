"""Unit tests for the feed parser. Run: .venv/bin/python -m pytest tests/"""
import json
from datetime import datetime, time


from mittog.model import TZ, parse_board, parse_ts, train_attributes, train_summary  # noqa: E402

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
    assert t.name == "RØ 4837"
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
    assert t.consist == "IC3 + IC3" and t.car_numbers == ["11", "12", "22", "21"]
    dd = next(x for x in b.trains if x.train_id == "4445")
    assert dd.car_numbers == ["1", "14", "13", "12", "11"]
    assert dd.units[0].label == "Lokomotiv"
    ic = next(x for x in b.trains if x.train_id == "826")
    assert len(ic.units) == 2 and ic.destination == "HGL"


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

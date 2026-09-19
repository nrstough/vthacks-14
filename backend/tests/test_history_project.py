"""Projection into the horizon (A8, A16): dates, weekends, and the balance cutoff."""

from __future__ import annotations

import datetime

from app.history.detect import Row, detect_streams
from app.history.payee import payee_key
from app.history.project import project
from tests.fixtures import histories as H

END = datetime.date(2026, 9, 18)
AS_OF = datetime.date(2026, 9, 19)


def rows(dicts):
    ordered = sorted(dicts, key=lambda r: r["date"])
    return [
        Row(i, datetime.date.fromisoformat(r["date"]), r["amount_cents"], r["description"], payee_key(r["description"]))
        for i, r in enumerate(ordered)
    ]


def one(dicts, history_end=END):
    streams, _ = detect_streams(rows(dicts), history_end)
    assert len(streams) == 1, [(s.kind, s.cadence) for s in streams]
    return streams[0]


def dates(stream, as_of=AS_OF, days=30, posted=frozenset()):
    projected, withheld = project(stream, as_of, as_of + datetime.timedelta(days=days - 1), set(posted))
    return [d for _id, d, _amount in projected], withheld


def test_a_weekly_stream_lands_on_its_anchor_weekday_inside_the_window():
    stream = one(H.weekly_income(END, weeks=20, weekday=1))
    days, _ = dates(stream)
    assert days and all(d.weekday() == 1 for d in days)
    assert len(days) == 4
    assert min(days) >= AS_OF and max(days) <= AS_OF + datetime.timedelta(days=29)


def test_nothing_is_ever_projected_before_as_of():
    # The solver does not reject a row dated before as_of; it silently ignores
    # it. So a mistake here is invisible rather than loud.
    stream = one(H.weekly_income(END, weeks=20, weekday=1))
    days, _ = dates(stream)
    assert all(d >= AS_OF for d in days)


def test_a_biweekly_stream_keeps_its_period_when_the_last_date_is_off_anchor():
    # Stepping the interval first and snapping to the anchor afterwards can
    # move the first date by up to six days, sometimes behind as_of, which
    # silently deletes a paycheck from the fortnight.
    data = H.biweekly_income(END, periods=12, weekday=4)
    data[-1] = H.row(datetime.date.fromisoformat(data[-1]["date"]) - datetime.timedelta(days=2), "PIEDMONT LABS INC", 86000)
    stream = one(data)
    days, _ = dates(stream, days=28)
    assert len(days) == 2, days
    assert all(d.weekday() == 4 for d in days)
    assert (days[1] - days[0]).days == 14


def test_income_on_a_weekend_moves_forward_and_a_bill_moves_back():
    bill = one(H.monthly_bill(datetime.date(2026, 1, 20), 8, 20, -5000, "ZZQ7K4 HOLDINGS", weekend_shift=False))
    days, _ = dates(bill, as_of=datetime.date(2026, 9, 1), days=45)
    assert days and all(d.weekday() < 5 for d in days)
    # 2026-09-20 is a Sunday, so the bill is taken on the Friday before.
    assert datetime.date(2026, 9, 18) in days

    income = one(H.weekly_income(END, weeks=20, weekday=5))
    days, _ = dates(income)
    assert days and all(d.weekday() < 5 for d in days)
    assert all(d.weekday() == 0 for d in days), "Saturday pay lands the following Monday, never the Friday before"


def test_a_monthly_anchor_at_the_month_end_is_clamped_per_month():
    stream = one(H.monthly_bill(datetime.date(2025, 10, 31), 11, 31, -7000, "ZZQ7K4 HOLDINGS", weekend_shift=False))
    days, _ = dates(stream, as_of=datetime.date(2026, 9, 19), days=45)
    assert days
    for d in days:
        assert d.day >= 28


def test_a_lapsed_stream_projects_nothing():
    stream = one(H.monthly_bill(datetime.date(2025, 6, 1), 9, 1, -8000, "OLD GYM LLC", weekend_shift=False))
    assert not stream.active
    days, _ = dates(stream)
    assert days == []


def test_income_expected_today_is_withheld_and_named():
    # opening_balance_cents is the balance INCLUDING everything posted today.
    # If today's pay posted it is already counted; if it has not posted,
    # counting it is a guess in the optimistic direction.
    tuesday = datetime.date(2026, 9, 22)
    stream = one(H.weekly_income(datetime.date(2026, 9, 15), weeks=20, weekday=1), history_end=tuesday)
    days, withheld = dates(stream, as_of=tuesday)
    assert withheld is True
    assert tuesday not in days
    assert days, "later paydays are still projected"


def test_a_bill_due_today_is_projected_unless_the_export_already_shows_it():
    monday = datetime.date(2026, 9, 21)
    data = H.monthly_bill(datetime.date(2026, 1, 21), 9, 21, -4500, "ZZQ7K4 HOLDINGS", weekend_shift=False)
    stream = one(data, history_end=monday)
    days, _ = dates(stream, as_of=monday)
    assert monday in days

    # Unless the export already carries it: the balance the person typed
    # includes everything posted today, so charging it again is a double count.
    key = stream.rows[0].key
    days_posted, _ = dates(stream, as_of=monday, posted={key})
    assert monday not in days_posted


def test_a_semimonthly_stream_lands_twice_a_month():
    stream = one(H.semimonthly_income(datetime.date(2025, 10, 1), months=12), history_end=datetime.date(2026, 9, 30))
    # 35 days, not 31: the month-end occurrence falls on a Saturday here and
    # income moves FORWARD off a weekend, so it lands in early November.
    days, _ = dates(stream, as_of=datetime.date(2026, 10, 1), days=35)
    assert len(days) == 2, days
    assert 10 <= (days[1] - days[0]).days <= 20


def test_projection_crosses_a_year_boundary():
    stream = one(H.weekly_income(datetime.date(2026, 12, 29), weeks=20, weekday=1), history_end=datetime.date(2026, 12, 29))
    days, _ = dates(stream, as_of=datetime.date(2026, 12, 30), days=21)
    assert days and any(d.year == 2027 for d in days)
    assert all(d.weekday() == 1 for d in days)

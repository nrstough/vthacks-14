"""The residual split and assumed everyday spending (A4, A5)."""

from __future__ import annotations

import datetime

from app.history.detect import Row, detect_streams
from app.history.payee import payee_key
from app.history.residual import assumed_rows, daily_outflow
from tests.fixtures import histories as H

END = datetime.date(2026, 9, 18)
AS_OF = datetime.date(2026, 9, 19)


def rows(dicts):
    ordered = sorted(dicts, key=lambda r: r["date"])
    return [
        Row(i, datetime.date.fromisoformat(r["date"]), r["amount_cents"], r["description"], payee_key(r["description"]))
        for i, r in enumerate(ordered)
    ]


def test_detected_rows_plus_the_residual_equal_the_original_totals():
    # By transaction, never by subtracting one total from another: a
    # subtraction lets a month with a big bill produce negative "everyday
    # spending", and the clip that hides it also hides the bug.
    checked = 0
    shapes = set()
    for seed in range(300):
        # The seed moves the payday weekday, the amounts and the bills' days
        # of month, so this exercises detection 300 different ways rather
        # than the same account 300 times.
        data = H.realistic(months=4, seed=seed)
        data += H.everyday_spending(END - datetime.timedelta(days=60), END, seed=seed)
        parsed = rows(data)
        streams, _ = detect_streams(parsed, END)
        used = {r.index for s in streams for r in s.rows}
        start = min(r.date for r in parsed)
        series, _ = daily_outflow(parsed, used, start, END)

        by_day: dict[datetime.date, int] = {}
        for row in parsed:
            if row.amount_cents < 0:
                by_day[row.date] = by_day.get(row.date, 0) - row.amount_cents
        stream_by_day: dict[datetime.date, int] = {}
        for stream in streams:
            for row in stream.rows:
                if row.amount_cents < 0:
                    stream_by_day[row.date] = stream_by_day.get(row.date, 0) - row.amount_cents

        for day in set(by_day) | set(series):
            assert series.get(day, 0) + stream_by_day.get(day, 0) == by_day.get(day, 0), day
        shapes.add(tuple(sorted((s.kind, s.cadence, s.anchor) for s in streams)))
        checked += 1
    assert checked == 300, "the loop must actually run; an empty one asserts nothing"
    assert len(shapes) > 20, f"the fixture must actually vary; only {len(shapes)} distinct accounts"


def test_every_day_of_the_history_is_present_and_quiet_days_are_counted():
    start = END - datetime.timedelta(days=13)
    data = [H.row(start, "KROGER #1", -2500), H.row(END, "KROGER #2", -2500)]
    series, imputed = daily_outflow(rows(data), set(), start, END)
    assert len(series) == 14
    assert imputed == 12
    assert all(v == 0 for d, v in series.items() if d not in (start, END))


def test_the_assumed_amount_is_the_same_weekday_median_over_eight_weeks():
    start = END - datetime.timedelta(days=55)
    data = []
    for i in range(56):
        day = start + datetime.timedelta(days=i)
        data.append(H.row(day, f"KROGER #{i}", -(6000 if day.weekday() == 5 else 2000)))
    series, _ = daily_outflow(rows(data), set(), start, END)
    assumed = assumed_rows(series, END, AS_OF, AS_OF + datetime.timedelta(days=13))
    amounts = {d.weekday(): -a for _id, d, a in assumed}
    assert amounts[5] == 6000
    assert all(v == 2000 for w, v in amounts.items() if w != 5)


def test_one_large_purchase_does_not_become_everyday_spending():
    # A $900 laptop through a MEAN would reappear as ~$112 every Tuesday for
    # the whole horizon — about $500 of invented spending.
    start = END - datetime.timedelta(days=55)
    data = [H.row(start + datetime.timedelta(days=i), f"KROGER #{i}", -2500) for i in range(56)]
    data.append(H.row(END - datetime.timedelta(days=7), "ONE OFF LAPTOP", -90000))
    series, _ = daily_outflow(rows(data), set(), start, END)
    assumed = assumed_rows(series, END, AS_OF, AS_OF + datetime.timedelta(days=13))
    assert max(-a for _id, _d, a in assumed) == 2500


def test_assumed_rows_stay_inside_the_window_and_cover_a_long_horizon():
    start = END - datetime.timedelta(days=55)
    data = [H.row(start + datetime.timedelta(days=i), f"KROGER #{i}", -2500) for i in range(56)]
    series, _ = daily_outflow(rows(data), set(), start, END)
    horizon_end = AS_OF + datetime.timedelta(days=29)
    assumed = assumed_rows(series, END, AS_OF, horizon_end)
    assert len(assumed) == 30
    assert all(AS_OF <= d <= horizon_end for _id, d, _a in assumed)


def test_too_little_history_assumes_nothing_rather_than_guessing_from_three_weeks():
    start = END - datetime.timedelta(days=20)
    data = [H.row(start + datetime.timedelta(days=i), f"KROGER #{i}", -2500) for i in range(21)]
    series, _ = daily_outflow(rows(data), set(), start, END)
    assert assumed_rows(series, END, AS_OF, AS_OF + datetime.timedelta(days=13)) == []


def test_a_weekday_with_no_spending_produces_no_row():
    start = END - datetime.timedelta(days=55)
    data = [
        H.row(start + datetime.timedelta(days=i), f"KROGER #{i}", -2500)
        for i in range(56)
        if (start + datetime.timedelta(days=i)).weekday() != 6
    ]
    series, _ = daily_outflow(rows(data), set(), start, END)
    assumed = assumed_rows(series, END, AS_OF, AS_OF + datetime.timedelta(days=13))
    assert all(d.weekday() != 6 for _id, d, _a in assumed)
    assert len(assumed) == 12


def test_assumed_rows_are_deterministic():
    start = END - datetime.timedelta(days=55)
    data = [H.row(start + datetime.timedelta(days=i), f"KROGER #{i}", -(2500 + i)) for i in range(56)]
    series, _ = daily_outflow(rows(data), set(), start, END)
    first = assumed_rows(series, END, AS_OF, AS_OF + datetime.timedelta(days=13))
    second = assumed_rows(series, END, AS_OF, AS_OF + datetime.timedelta(days=13))
    assert first == second

"""Detection by rhythm (A3), with a counterfactual for every guard.

The rule this file exists to protect: a guard nothing can fail is not a
guard. Where the spec names one — three occurrences, lapsed, the amount
bound, peer transfers — there is a test that FAILS when it is removed.
"""

from __future__ import annotations

import datetime

import pytest

from app.candidates.lexicon import classify
from app.history import detect as D
from app.history.detect import Row, detect_streams
from app.history.project import project
from app.history.payee import payee_key
from tests.fixtures import histories as H

END = datetime.date(2026, 9, 18)


def rows(dicts: list[dict]) -> list[Row]:
    ordered = sorted(dicts, key=lambda r: r["date"])
    return [
        Row(i, datetime.date.fromisoformat(r["date"]), r["amount_cents"], r["description"], payee_key(r["description"]))
        for i, r in enumerate(ordered)
    ]


def only(streams, kind=None, cadence=None):
    found = [s for s in streams if (kind is None or s.kind == kind) and (cadence is None or s.cadence == cadence)]
    assert len(found) == 1, f"expected one, got {[(s.kind, s.cadence, s.anchor) for s in found]}"
    return found[0]


# --------------------------------------------------------------------------
# the premise: rhythm, not keywords


def test_income_with_no_keyword_anywhere_is_still_detected():
    # Nathan's own export never contains the word PAYROLL, and neither do
    # most. A keyword detector finds nothing here; that is the whole reason
    # detection is cadence-based.
    data = H.weekly_income(END, weeks=30, description="ACME WIDGETS LLC")
    streams, _ = detect_streams(rows(data), END)
    assert only(streams, kind="income").cadence == "weekly"


def test_a_keyword_only_classifier_finds_nothing_on_the_same_rows():
    data = H.weekly_income(END, weeks=30, description="ACME WIDGETS LLC")
    assert all(classify(r["description"]).category == "unknown" for r in data)


# --------------------------------------------------------------------------
# cadences


def test_weekly_pay_survives_a_weekday_wobble_and_two_skipped_weeks():
    # A student who does not work over an exam week has not lost their job.
    # Treating the 14-day gap as a broken cadence would drop their income and
    # then tell them they need outside cash.
    data = H.weekly_income(END, weeks=30, skip=(9, 17))
    stream = only(detect_streams(rows(data), END)[0], kind="income")
    assert stream.cadence == "weekly"
    assert stream.active
    assert stream.occurrences == 28


def test_biweekly_pay_is_not_read_as_weekly():
    data = H.biweekly_income(END, periods=20)
    assert only(detect_streams(rows(data), END)[0], kind="income").cadence == "biweekly"


def test_semimonthly_pay_is_not_read_as_biweekly():
    # Its gaps (13-18 days) overlap biweekly's almost exactly. A gap test
    # calls this "every 14 days" and then drifts off both anchors inside one
    # month, so the cadence is decided by WHERE in the month instead.
    data = H.semimonthly_income(datetime.date(2025, 10, 1), months=12)
    stream = only(detect_streams(rows(data), datetime.date(2026, 9, 30))[0], kind="income")
    assert stream.cadence == "semimonthly"
    assert 15 in stream.anchor_doms
    assert max(stream.anchor_doms) >= 28


def test_a_weekend_shifted_monthly_bill_stays_monthly():
    # Its day of month moves around, but the two "phases" are days apart, not
    # a fortnight. Calling it semimonthly would bill the person twice a month.
    data = H.monthly_bill(datetime.date(2025, 10, 1), 12, 1, -120000, "OAKWOOD PROPERTIES")
    stream = only(detect_streams(rows(data), END)[0], kind="bill")
    assert stream.cadence == "monthly"
    assert len(stream.anchor_doms) == 1


def test_a_monthly_bill_on_a_fixed_day_is_detected():
    data = H.monthly_bill(datetime.date(2026, 1, 15), 8, 15, -1599, "NETFLIX.COM", weekend_shift=False)
    stream = only(detect_streams(rows(data), END)[0], kind="bill")
    assert (stream.cadence, stream.anchor_doms) == ("monthly", (15,))


# --------------------------------------------------------------------------
# anchors and amounts


def test_the_anchor_follows_a_payday_that_moved_weekday():
    # Two years of Tuesdays then three months of Thursdays: an anchor taken
    # over all history says Tuesday, and every projected payday — including
    # the one the screen names — is two days early.
    data = H.weekly_income(END, weeks=30, weekday=1, moved_weekday=3, moved_after=22)
    stream = only(detect_streams(rows(data), END)[0], kind="income")
    assert stream.anchor == "Thursday"


def test_amount_drift_is_one_stream_at_the_recent_amount():
    data = H.monthly_bill(
        datetime.date(2025, 10, 1), 12, 5, -3499, "PLANET FIT CLUB FEES",
        weekend_shift=False, drift_after=8, drift_to=-3699,
    )
    stream = only(detect_streams(rows(data), END)[0], kind="bill")
    assert stream.occurrences == 12
    # The last eight, trimmed: four at the old price and four at the new.
    assert -3699 <= stream.amount_cents <= -3499


def test_two_subscriptions_at_one_merchant_are_two_streams():
    data = H.monthly_bill(datetime.date(2026, 1, 3), 8, 3, -1599, "NETFLIX.COM", weekend_shift=False)
    data += H.monthly_bill(datetime.date(2026, 1, 20), 8, 20, -2299, "NETFLIX.COM", weekend_shift=False)
    streams, _ = detect_streams(rows(data), END)
    assert len(streams) == 2
    assert sorted(s.amount_cents for s in streams) == [-2299, -1599]


def test_two_employers_are_both_projected():
    data = H.weekly_income(END, weeks=20, weekday=1, description="ACME WIDGETS LLC")
    data += H.biweekly_income(END, periods=10, weekday=4, description="PIEDMONT LABS INC")
    streams, _ = detect_streams(rows(data), END)
    income = [s for s in streams if s.kind == "income"]
    assert sorted(s.cadence for s in income) == ["biweekly", "weekly"]


# --------------------------------------------------------------------------
# guards, each with its counterfactual


def test_two_occurrences_are_not_a_stream():
    data = [
        H.row(datetime.date(2026, 8, 3), "RARE CHARGE CO", -4000),
        H.row(datetime.date(2026, 9, 3), "RARE CHARGE CO", -4000),
    ]
    assert detect_streams(rows(data), END)[0] == []


def test_the_minimum_occurrence_guard_is_load_bearing(monkeypatch):
    data = [
        H.row(datetime.date(2026, 8, 3), "RARE CHARGE CO", -4000),
        H.row(datetime.date(2026, 9, 3), "RARE CHARGE CO", -4000),
    ]
    monkeypatch.setattr(D, "MIN_OCCURRENCES", 2)
    assert detect_streams(rows(data), END)[0] != [], "removing the guard must change the answer"


def test_a_stopped_stream_is_detected_but_not_active():
    # Detected, because its rows must still leave the residual; inactive, so
    # nothing is projected from it.
    data = H.monthly_bill(datetime.date(2025, 6, 1), 9, 1, -8000, "OLD GYM LLC", weekend_shift=False)
    stream = only(detect_streams(rows(data), END)[0], kind="bill")
    assert stream.last_seen == datetime.date(2026, 2, 1)
    assert not stream.active


def test_a_bill_silent_for_forty_days_is_still_active():
    data = H.monthly_bill(datetime.date(2025, 11, 9), 10, 9, -8000, "CURRENT GYM LLC", weekend_shift=False)
    stream = only(detect_streams(rows(data), END)[0], kind="bill")
    assert (END - stream.last_seen).days == 40
    assert stream.active


def test_the_lapse_guard_is_load_bearing(monkeypatch):
    data = H.monthly_bill(datetime.date(2025, 6, 1), 9, 1, -8000, "OLD GYM LLC", weekend_shift=False)
    monkeypatch.setattr(D, "LAPSE_INTERVALS_BILL", 99.0)
    assert only(detect_streams(rows(data), END)[0], kind="bill").active


def test_peer_transfers_are_never_income():
    # Money that may not come is money a plan must not count on.
    data = H.peer_transfers(datetime.date(2026, 1, 1), END)
    streams, unscheduled = detect_streams(rows(data), END)
    assert [s for s in streams if s.kind == "income"] == []
    assert len(unscheduled) == len(data)


def test_an_income_amount_that_swings_too_far_is_not_a_stream():
    data = H.weekly_income(END, weeks=20, amount=1000, jitter_cents=200000, seed=5)
    streams, unscheduled = detect_streams(rows(data), END)
    assert [s for s in streams if s.kind == "income"] == []
    assert unscheduled


def test_the_income_amount_bound_is_load_bearing(monkeypatch):
    data = H.weekly_income(END, weeks=20, amount=1000, jitter_cents=200000, seed=5)
    monkeypatch.setattr(D, "CV_MAX_INCOME", 99.0)
    assert [s for s in detect_streams(rows(data), END)[0] if s.kind == "income"]


def test_a_bill_holds_a_tighter_amount_bound_than_income():
    assert D.CV_MAX_BILL < D.CV_MAX_INCOME


# --------------------------------------------------------------------------
# the whole account, and determinism


def test_a_realistic_account_finds_every_planted_stream():
    data = H.realistic()
    streams, unscheduled = detect_streams(rows(data), END)
    income = [s for s in streams if s.kind == "income"]
    bills = [s for s in streams if s.kind == "bill"]
    spending = [s for s in streams if s.kind == "discretionary"]
    assert len(income) == 1 and income[0].cadence == "weekly"
    assert sorted(s.amount_cents for s in bills) == [-120000, -3499, -1599]
    # The planted Saturday grocery run recurs and is worth projecting, but it
    # is spending, not a bill, and the label has to say which.
    assert [s.cadence for s in spending] == ["weekly"]
    assert spending[0].category == "groceries"
    assert unscheduled, "the planted peer transfers must be reported, not silently dropped"


def test_detection_is_deterministic():
    data = H.realistic()
    first = detect_streams(rows(data), END)[0]
    second = detect_streams(rows(data), END)[0]
    assert [(s.kind, s.cadence, s.anchor, s.amount_cents, s.occurrences) for s in first] == [
        (s.kind, s.cadence, s.anchor, s.amount_cents, s.occurrences) for s in second
    ]


def test_original_row_indexes_survive_a_newest_first_export():
    # Detection sorts; `source_row_indexes` has to point back at the rows the
    # caller sent, or the screen labels the wrong transactions.
    data = sorted(H.realistic(), key=lambda r: r["date"], reverse=True)
    numbered = [
        Row(i, datetime.date.fromisoformat(r["date"]), r["amount_cents"], r["description"], payee_key(r["description"]))
        for i, r in enumerate(data)
    ]
    streams, _ = detect_streams(numbered, END)
    assert streams
    for stream in streams:
        for member in stream.rows:
            assert data[member.index]["description"] == member.description
            assert data[member.index]["amount_cents"] == member.amount_cents


def test_a_weekly_grocery_run_is_spending_and_not_a_bill():
    # It recurs, so it is worth projecting; it is not a bill, so the untick
    # list must not present it as one.
    data = [
        H.row(datetime.date(2026, 6, 6) + datetime.timedelta(days=7 * i), f"KROGER #{380 + i}", -6000 - i)
        for i in range(14)
    ]
    stream = only(detect_streams(rows(data), END)[0])
    assert (stream.kind, stream.category, stream.cadence) == ("discretionary", "groceries", "weekly")
    assert "Groceries" in stream.label


def test_an_unrecognised_recurring_outflow_is_treated_as_a_bill():
    # Conservative on purpose: the candidate generator refuses to offer
    # changes to an unrecognised bill, and guessing that someone's unknown
    # recurring charge is expendable is not this product's call.
    data = H.monthly_bill(datetime.date(2026, 1, 8), 8, 8, -4200, "ZZQ7K4 HOLDINGS", weekend_shift=False)
    stream = only(detect_streams(rows(data), END)[0])
    assert (stream.kind, stream.category) == ("bill", "unknown")


def test_several_charges_from_one_payee_on_one_day_are_not_a_stream():
    # A payee that bills several times a day is a transfer app or a shopping
    # habit, not a scheduled payment.
    data = []
    for week in range(12):
        day = datetime.date(2026, 6, 2) + datetime.timedelta(days=7 * week)
        for i in range(2):
            data.append(H.row(day, "VENMO CASHOUT", 5000 + i))
    streams, unscheduled = detect_streams(rows(data), END)
    assert streams == []
    assert len(unscheduled) == len(data)


def test_the_same_day_guard_is_load_bearing(monkeypatch):
    data = []
    for week in range(12):
        day = datetime.date(2026, 6, 2) + datetime.timedelta(days=7 * week)
        for i in range(2):
            data.append(H.row(day, "VENMO CASHOUT", 5000 + i))
    # Collapse same-day rows without flagging it, and the guard is gone.
    real = D._collapse_same_day
    monkeypatch.setattr(D, "_collapse_same_day", lambda rs: (real(rs)[0], False))
    assert detect_streams(rows(data), END)[0], "removing the guard must change the answer"


def test_a_lapsed_bill_inside_the_baseline_window_leaves_the_residual():
    # A WEEKLY bill, so it actually lapses inside the 56-day window: two
    # intervals is fourteen days, and its last payment is thirty ago. Its
    # rows must still leave everyday spending — a $200 charge that stopped
    # last month is not $25 a week of groceries — while nothing is projected.
    from app.history.residual import assumed_rows, daily_outflow

    start = END - datetime.timedelta(days=90)
    data = [H.row(start + datetime.timedelta(days=i), f"KROGER #{i}", -2500) for i in range(91)]
    stopped = END - datetime.timedelta(days=30)
    data += [
        H.row(stopped - datetime.timedelta(days=7 * i), "OAKWOOD PROPERTIES", -20000) for i in range(8)
    ]
    parsed = rows(data)
    streams, _ = detect_streams(parsed, END)
    bill = only([s for s in streams if s.amount_cents == -20000])
    assert bill.cadence == "weekly"
    assert not bill.active, f"last seen {bill.last_seen}, {(END - bill.last_seen).days} days before the end"

    projected, _e, _p = project(bill, END + datetime.timedelta(days=1), END + datetime.timedelta(days=14))
    assert projected == [], "a lapsed stream projects nothing"

    used = {r.index for s in streams for r in s.rows}
    series, _ = daily_outflow(parsed, used, start, END)
    assumed = assumed_rows(series, END, END + datetime.timedelta(days=1), END + datetime.timedelta(days=14))
    assert max(-a for _i, _d, a in assumed) == 2500, "the stopped bill must not become everyday spending"

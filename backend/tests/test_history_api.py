"""POST /api/accounts/import end to end (A6, A7, A9, A12, A13, A16, A17)."""

from __future__ import annotations

import copy
import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas import MAX_SCHED, SolveRequest
from app.solver.solve import solve
from tests.fixtures import histories as H

END = datetime.date(2026, 9, 18)
AS_OF = "2026-09-21"


@pytest.fixture
def client():
    return TestClient(create_app(None))


def body(rows=None, **over):
    payload = {
        "rows": rows if rows is not None else H.realistic(),
        "as_of": AS_OF,
        "opening_balance_cents": 41000,
        "buffer_cents": 2500,
    }
    payload.update(over)
    return payload


def imported(client, **over):
    r = client.post("/api/accounts/import", json=body(**over))
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------
# the happy path


def test_an_import_returns_a_schedule_the_solver_accepts(client):
    out = imported(client)
    request = SolveRequest.model_validate(
        {
            "as_of": out["as_of"],
            "horizon_end": out["horizon_end"],
            "opening_balance_cents": out["opening_balance_cents"],
            "buffer_cents": out["buffer_cents"],
            "scheduled": out["scheduled"],
            "candidates": out["candidates"],
            "locks": {"in": [], "out": []},
        }
    )
    result = solve(request)
    assert result.tier in (1, 2, 3)
    assert out["source"] == "import"


def test_the_provenance_says_where_every_number_came_from(client):
    out = imported(client)
    p = out["provenance"]
    assert p["assumed_method"] == "same_weekday_8_week_median"
    assert p["weeks_used_for_assumed"] == 8
    assert p["history_days"] > 56
    assert p["rows_used"] > 0
    assert p["next_payday"] >= out["as_of"]
    assert p["pay_cadence"] == "weekly"
    assert p["imputed_zero_days"] >= 0
    assert p["unscheduled_inflow_count"] > 0, "the planted peer transfers must be reported"


def test_ids_are_unique_and_assumed_rows_are_marked(client):
    out = imported(client)
    ids = [t["id"] for t in out["scheduled"]]
    assert len(ids) == len(set(ids))
    assumed = [t for t in out["scheduled"] if t["id"].startswith("f_")]
    assert assumed
    assert {t["id"] for t in assumed} == set(out["provenance"]["assumed_ids"])
    for row in assumed:
        assert row["kind"] == "discretionary" and row["recurring"] is False
        assert row["description"].startswith("Everyday spending (assumed")
        assert row["amount_cents"] < 0


# --------------------------------------------------------------------------
# A7: no candidate may ever target an assumed row


def test_no_candidate_targets_an_assumed_row(client):
    out = imported(client)
    assumed = set(out["provenance"]["assumed_ids"])
    assert out["candidates"], "the fixture must produce candidates or this proves nothing"
    assert all(c["target_txn_id"] not in assumed for c in out["candidates"])
    assert all(not c["target_txn_id"].startswith("f_") for c in out["candidates"])


def test_removing_the_exemption_is_caught_before_anything_ships(monkeypatch):
    # Take the guard away and the pipeline fails loudly rather than quietly
    # handing the generator rows it must never see. The other half of this
    # pair proves the generator really would offer them.
    import datetime as _dt

    import app.history as history
    from app.schemas import ImportRequest

    monkeypatch.setattr(history, "is_assumed", lambda _txn_id: False)
    request = ImportRequest.model_validate(body())
    with pytest.raises(AssertionError, match="drifted apart"):
        history.import_account(request, _dt.date.fromisoformat(AS_OF))


def test_the_generator_really_would_offer_an_assumed_row():
    # The other half: the hazard is real, not hypothetical.
    from app.candidates import generate
    from app.schemas import CandidatesRequest

    assumed_row = {
        "id": "f_20260921",
        "date": AS_OF,
        "description": "Everyday spending (assumed from your last 8 weeks)",
        "amount_cents": -2500,
        "kind": "discretionary",
        "recurring": False,
    }
    leaked = generate(
        CandidatesRequest.model_validate(
            {"as_of": AS_OF, "horizon_end": "2026-10-20", "scheduled": [assumed_row], "limit": 18}
        )
    )
    assert leaked.candidates, "if this stops being true the exemption is no longer needed"
    assert leaked.candidates[0].target_txn_id == "f_20260921"


# --------------------------------------------------------------------------
# A16: the balance cutoff


def test_income_expected_today_is_not_counted_twice(client):
    tuesday = "2026-09-22"
    rows = H.weekly_income(datetime.date.fromisoformat(tuesday), weeks=20, weekday=1)
    rows += H.everyday_spending(datetime.date.fromisoformat(tuesday) - datetime.timedelta(days=60), datetime.date.fromisoformat(tuesday))
    out = imported(client, rows=rows, as_of=tuesday)
    assert out["provenance"]["income_not_counted_today"], "an occurrence due today must be withheld and named"
    assert all(t["date"] != tuesday or t["kind"] != "income" for t in out["scheduled"])


def test_rows_dated_after_today_are_rejected_and_named(client):
    rows = H.realistic()
    rows.append(H.row(datetime.date(2026, 12, 25), "FUTURE CO", -5000))
    out = imported(client, rows=rows)
    reasons = [r["reason"] for r in out["provenance"]["rejected_rows"]]
    assert reasons.count("after_as_of") == 1


def test_a_history_older_than_three_years_is_rejected_and_named(client):
    rows = H.realistic()
    rows.append(H.row(datetime.date(2019, 1, 1), "ANCIENT CO", -5000))
    out = imported(client, rows=rows)
    assert "older_than_3_years" in [r["reason"] for r in out["provenance"]["rejected_rows"]]


def test_a_stale_export_says_how_stale(client):
    out = imported(client, as_of="2026-10-05")
    assert out["provenance"]["stale_days"] == 17


# --------------------------------------------------------------------------
# A6: hostile input is a 422, never a 500


def test_a_bad_field_names_itself(client):
    r = client.post("/api/accounts/import", json=body(opening_balance_cents=200.5))
    assert r.status_code == 422
    detail = r.json()["detail"][0]
    assert detail["loc"][0] == "body"
    assert detail["loc"][1] == "opening_balance_cents"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b.pop("opening_balance_cents"),
        lambda b: b.update(rows=[]),
        lambda b: b.update(rows=[{"date": "2026-13-45", "description": "X", "amount_cents": -1}]),
        lambda b: b.update(rows=[{"date": "2026-01-01", "description": "X", "amount_cents": 0}]),
        lambda b: b.update(rows=[{"date": "2026-01-01", "description": "X", "amount_cents": 1.5}]),
        lambda b: b.update(rows=[{"date": "2026-01-01", "description": "X", "amount_cents": True}]),
        lambda b: b.update(rows=[{"date": "2026-01-01", "description": "", "amount_cents": -1}]),
        lambda b: b.update(rows=[{"date": "9999-12-31", "description": "X", "amount_cents": -1}]),
        lambda b: b.update(rows=[{"date": "2026-01-01", "description": "X", "amount_cents": -1, "extra": 1}]),
        lambda b: b.update(horizon_days=0),
        lambda b: b.update(horizon_days=400),
        lambda b: b.update(as_of="not-a-date"),
        lambda b: b.update(buffer_cents=-1),
        lambda b: b.update(rows="a string"),
    ],
)
def test_no_malformed_request_escapes_as_a_server_error(client, mutate):
    payload = body()
    mutate(payload)
    r = client.post("/api/accounts/import", json=payload)
    assert r.status_code == 422, r.text


def test_all_rows_rejected_is_a_422_and_not_a_crash(client):
    r = client.post(
        "/api/accounts/import",
        json=body(rows=[H.row(datetime.date(2030, 1, 1), "FUTURE CO", -100)]),
    )
    assert r.status_code == 422
    assert "no usable history" in str(r.json()["detail"]).lower()


def test_more_rows_than_the_cap_is_a_422(client):
    row = H.row(datetime.date(2026, 1, 1), "X", -100)
    r = client.post("/api/accounts/import", json=body(rows=[row] * 20001))
    assert r.status_code == 422


def test_a_row_at_the_amount_cap_does_not_overflow_the_response(client):
    rows = H.realistic()
    rows += H.monthly_bill(datetime.date(2026, 1, 4), 8, 4, -(10**8), "ZZQ7K4 HOLDINGS", weekend_shift=False)
    r = client.post("/api/accounts/import", json=body(rows=rows))
    assert r.status_code == 200, r.text


# --------------------------------------------------------------------------
# A9: bounds


def test_assumed_rows_give_way_first_when_the_window_is_full(monkeypatch, client):
    # An assumed row is an estimate; a detected charge is a fact about the
    # account. The estimate is what gets dropped.
    import app.history as history

    monkeypatch.setattr(history, "MAX_SCHED", 20)
    out = imported(client)
    assert len(out["scheduled"]) <= 20
    assert out["provenance"]["truncated_assumed_rows"] > 0
    assert [t for t in out["scheduled"] if not t["id"].startswith("f_")]


def test_too_many_detected_rows_alone_is_a_422_not_a_500(monkeypatch, client):
    import app.history as history

    monkeypatch.setattr(history, "MAX_SCHED", 2)
    r = client.post("/api/accounts/import", json=body())
    assert r.status_code == 422
    assert "recurring charges" in str(r.json()["detail"])


# --------------------------------------------------------------------------
# A12/A13: the golden account, and determinism


def test_a_handful_of_transactions_is_not_a_history(client):
    # Answering "sufficient" over one transaction is worse than refusing.
    rows = [H.row(datetime.date(2026, 9, 1) + datetime.timedelta(days=i), f"KROGER #{i}", -2500) for i in range(3)]
    r = client.post("/api/accounts/import", json=body(rows=rows))
    assert r.status_code == 422
    assert "not enough history" in str(r.json()["detail"]).lower()


def test_a_daily_total_too_large_to_plan_is_refused_not_a_500(client):
    # Rows are capped, but a DAY is the sum of its rows, and the median of
    # those sums has to fit a scheduled amount. This was a 500 on input the
    # schema had already accepted.
    end = datetime.date(2026, 9, 18)
    rows = []
    day = end - datetime.timedelta(days=55)
    while day <= end:
        for i in range(1001 if day.weekday() == 1 else 1):
            rows.append(H.row(day, f"BIG {i % 7}", -(10**8)))
        day += datetime.timedelta(days=1)
    r = client.post("/api/accounts/import", json=body(rows=rows, as_of="2026-09-19"))
    assert r.status_code == 422, r.status_code
    assert "too large to plan" in str(r.json()["detail"])


def test_a_raw_string_row_and_broken_json_are_both_422(client):
    # Two FastAPI error shapes the privacy handler has to survive:
    # model_attributes_type echoes the row, and json_invalid carries a `ctx`
    # holding an exception object that a naive re-encode turns into a 500.
    r = client.post("/api/accounts/import", json=body(rows=["a string"]))
    assert r.status_code == 422
    assert all(set(d) <= {"type", "loc", "msg"} for d in r.json()["detail"])

    r = client.post(
        "/api/accounts/import",
        content=b'{"rows": [ , ], "opening_balance_cents": 1}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422
    assert all("ctx" not in d for d in r.json()["detail"])


def test_too_little_history_still_returns_the_streams_it_found(client):
    # A5 through the route, not only the unit: under 56 days the response
    # says it assumed nothing AND still carries the bills.
    end = datetime.date(2026, 9, 18)
    rows = H.monthly_bill(datetime.date(2026, 8, 3), 2, 3, -4500, "ZZQ7K4 HOLDINGS", weekend_shift=False)
    rows += H.monthly_bill(datetime.date(2026, 8, 10), 2, 10, -1599, "NETFLIX.COM", weekend_shift=False)
    rows += [H.row(end - datetime.timedelta(days=i), f"KROGER #{i}", -2500) for i in range(30)]
    out = imported(client, rows=rows, as_of="2026-09-19")
    assert out["provenance"]["history_days"] < 56
    assert out["provenance"]["assumed_method"] is None
    assert out["provenance"]["assumed_ids"] == []
    assert not [t for t in out["scheduled"] if t["id"].startswith("f_")]


def test_the_next_payday_is_right_across_a_year_boundary(client):
    end = datetime.date(2026, 12, 29)
    rows = H.weekly_income(end, weeks=30, weekday=1)
    rows += H.everyday_spending(end - datetime.timedelta(days=90), end)
    out = imported(client, rows=rows, as_of="2026-12-30")
    payday = out["provenance"]["next_payday"]
    assert payday is not None
    assert datetime.date.fromisoformat(payday).year == 2027
    assert datetime.date.fromisoformat(payday).weekday() == 1


def test_the_golden_account_is_pinned(client):
    out = imported(client)
    streams = out["streams"]
    kinds = sorted(s["kind"] for s in streams)
    assert kinds == ["bill", "bill", "bill", "discretionary", "income"]
    income = next(s for s in streams if s["kind"] == "income")
    assert (income["cadence"], income["anchor"]) == ("weekly", "Tuesday")
    assert out["provenance"]["next_payday"] == "2026-09-22"
    assert sorted(s["amount_cents"] for s in streams if s["kind"] == "bill") == [-120000, -3499, -1599]
    # Rent is protected, so nothing is ever offered against it; the gym, the
    # subscription and the weekly grocery run are all changeable.
    assert len(out["candidates"]) == 10
    rent = next(s for s in streams if s["amount_cents"] == -120000)
    offered_against = {c["target_txn_id"] for c in out["candidates"]}
    assert offered_against.isdisjoint(rent["projected_ids"]), "rent must never be offered"
    assert out["meta"]["protected"]

    request = SolveRequest.model_validate(
        {
            "as_of": out["as_of"],
            "horizon_end": out["horizon_end"],
            "opening_balance_cents": out["opening_balance_cents"],
            "buffer_cents": out["buffer_cents"],
            "scheduled": out["scheduled"],
            "candidates": out["candidates"],
            "locks": {"in": [], "out": []},
        }
    )
    result = solve(request)
    assert (result.tier, len(result.plan)) == (3, 3)


def test_the_same_export_twice_gives_the_same_answer(client):
    first = imported(client)
    second = imported(client)
    assert first == second


def test_source_row_indexes_point_at_the_rows_the_caller_sent(client):
    rows = sorted(H.realistic(), key=lambda r: r["date"], reverse=True)
    out = imported(client, rows=rows)
    assert out["streams"]
    for stream in out["streams"]:
        assert stream["source_row_indexes"]
        for index in stream["source_row_indexes"]:
            assert 0 <= index < len(rows)
        # every row of one stream is the same payee in the ORIGINAL list
        payees = {rows[i]["description"].split("#")[0].strip() for i in stream["source_row_indexes"]}
        assert len(payees) == 1, payees


def test_out_of_order_rows_are_sorted_and_duplicates_are_kept(client):
    rows = H.realistic()
    duplicate = H.row(datetime.date(2026, 8, 4), "KROGER #380", -2500)
    rows = [duplicate, duplicate] + rows
    out = imported(client, rows=rows)
    assert out["provenance"]["rows_used"] == len(rows)
    dates = [t["date"] for t in out["scheduled"]]
    assert dates == sorted(dates)


def test_a_bill_from_the_next_month_pulled_back_over_a_weekend_is_not_lost(client):
    # A rent charge anchored to the 1st of NOVEMBER lands on Friday
    # October 30 and belongs in a window that ends October 31. Generating
    # only up to the window's own last month drops it, and the person is
    # shown a fortnight with their rent missing.
    rows = H.monthly_bill(datetime.date(2025, 11, 1), 11, 1, -100000, "OAKWOOD PROPERTIES")
    rows += H.everyday_spending(datetime.date(2026, 7, 1), datetime.date(2026, 10, 17))
    out = imported(client, rows=rows, as_of="2026-10-18", horizon_days=14)
    assert out["horizon_end"] == "2026-10-31"
    rent = next(s for s in out["streams"] if s["amount_cents"] == -100000)
    assert rent["projected_ids"], "the rent must appear in the window"
    dates = [t["date"] for t in out["scheduled"] if t["id"] in rent["projected_ids"]]
    assert dates == ["2026-10-30"], dates


def test_two_subscriptions_at_one_merchant_do_not_suppress_each_other(client):
    # They share a payee key. Suppressing today's charge by payee drops the
    # one that has not been taken along with the one that has.
    today = datetime.date(2026, 9, 21)
    # The $15.99 one runs through today; the $22.99 one stopped in August,
    # so only the first has already been taken.
    rows = H.monthly_bill(datetime.date(2026, 1, 21), 9, 21, -1599, "NETFLIX.COM", weekend_shift=False)
    rows += H.monthly_bill(datetime.date(2026, 2, 21), 7, 21, -2299, "NETFLIX.COM", weekend_shift=False)
    rows += H.everyday_spending(datetime.date(2026, 6, 1), today)
    out = imported(client, rows=rows, as_of=today.isoformat())
    streams = {s["amount_cents"]: s for s in out["streams"] if s["amount_cents"] in (-1599, -2299)}
    assert len(streams) == 2, [s["amount_cents"] for s in out["streams"]]
    dated = {t["id"]: t["date"] for t in out["scheduled"]}
    # The $15.99 one posted today and must not be charged again; the $22.99
    # one last posted in August and is still to come.
    posted_today = [d for i, d in dated.items() if i in streams[-1599]["projected_ids"] and d == today.isoformat()]
    still_due = [d for i, d in dated.items() if i in streams[-2299]["projected_ids"] and d == today.isoformat()]
    assert posted_today == []
    assert still_due == [today.isoformat()]


def test_the_cadence_belongs_to_the_stream_that_pays_next(client):
    # Two employers: the busiest is weekly, but the next payday belongs to
    # the fortnightly one. Reporting the busiest stream's cadence beside that
    # date tells the person the wrong thing about their own pay.
    end = datetime.date(2026, 9, 18)
    rows = H.weekly_income(end - datetime.timedelta(days=40), weeks=30, weekday=0, description="ACME WIDGETS LLC")
    rows += H.biweekly_income(end, periods=12, weekday=4, description="PIEDMONT LABS INC")
    rows += H.everyday_spending(end - datetime.timedelta(days=90), end)
    out = imported(client, rows=rows, as_of="2026-09-21")
    p = out["provenance"]
    owner = [
        s
        for s in out["streams"]
        if s["kind"] == "income"
        and p["next_payday"] in [t["date"] for t in out["scheduled"] if t["id"] in s["projected_ids"]]
    ]
    assert len(owner) == 1, [s["label"] for s in owner]
    assert p["pay_cadence"] == owner[0]["cadence"]
    # And the two employers really do differ, or this proves nothing.
    assert len({s["cadence"] for s in out["streams"] if s["kind"] == "income"}) == 2


def test_a_history_of_only_bills_is_not_called_too_short(client):
    # Seven months of recurring bills and no card spending: the method DID
    # apply, it just found nothing. Saying "not enough history" would be
    # false, and saying every day was quiet would be too.
    rows = H.monthly_bill(datetime.date(2026, 2, 1), 8, 1, -120000, "OAKWOOD PROPERTIES")
    rows += H.monthly_bill(datetime.date(2026, 2, 15), 8, 15, -1599, "NETFLIX.COM", weekend_shift=False)
    rows += H.monthly_bill(datetime.date(2026, 2, 8), 8, 8, -3499, "PLANET FIT CLUB FEES", weekend_shift=False)
    out = imported(client, rows=rows, as_of="2026-09-21")
    p = out["provenance"]
    assert p["history_days"] > 56
    assert p["assumed_method"] == "same_weekday_8_week_median", "the method applied; it found nothing"
    assert p["assumed_ids"] == []
    assert p["imputed_zero_days"] < p["history_days"], "days with a bill are not days with nothing"


def test_quiet_days_are_days_with_no_transaction_at_all(client):
    end = datetime.date(2026, 9, 18)
    rows = H.monthly_bill(datetime.date(2026, 3, 1), 7, 1, -120000, "OAKWOOD PROPERTIES", weekend_shift=False)
    rows += [H.row(end - datetime.timedelta(days=i), f"KROGER #{i}", -2500) for i in range(0, 60, 2)]
    out = imported(client, rows=rows, as_of="2026-09-19")
    p = out["provenance"]
    # A quiet day is one with NO transaction, so the count is the history's
    # length minus the number of distinct dates the export touches — rent
    # days included, even though rent is removed from the residual.
    touched = {r["date"] for r in rows}
    assert p["imputed_zero_days"] == p["history_days"] - len(touched)
    assert p["imputed_zero_days"] < p["history_days"]


@pytest.mark.parametrize("amount", [float("inf"), float("-inf"), float("nan")])
def test_a_nonfinite_amount_is_a_422(client, amount):
    # A6 names nonfinite amounts explicitly. JSON has no literal for them, so
    # they arrive as the bare tokens a lax encoder emits.
    import json

    payload = json.dumps(
        {"rows": [{"date": "2026-01-01", "description": "X", "amount_cents": amount}], "opening_balance_cents": 1}
    )
    r = client.post("/api/accounts/import", content=payload, headers={"Content-Type": "application/json"})
    assert r.status_code == 422, r.status_code


def test_the_lower_calendar_boundary(client):
    rows = [H.row(datetime.date(1970, 1, 1), f"OLD CO {i}", -100) for i in range(12)]
    r = client.post("/api/accounts/import", json=body(rows=rows, as_of="2026-09-21"))
    # Valid dates, but three years is the lookback, so every row is rejected.
    assert r.status_code == 422
    assert "no usable history" in str(r.json()["detail"]).lower()

    r = client.post(
        "/api/accounts/import",
        json=body(rows=[H.row(datetime.date(1969, 12, 31), "TOO OLD", -100)]),
    )
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][-1] == "date"


def test_a_transfer_app_paying_twice_a_day_is_never_income(client):
    # Two payouts the same day in two different sizes. Splitting by amount
    # first gives each size a clean one-per-day series, so the account grows
    # two "weekly income streams" and the plan counts on money that may
    # never come.
    rows = []
    for week in range(12):
        day = datetime.date(2026, 6, 2) + datetime.timedelta(days=7 * week)
        rows.append(H.row(day, "VENMO CASHOUT", 5000))
        rows.append(H.row(day, "VENMO CASHOUT", 15000))
    rows += H.everyday_spending(datetime.date(2026, 6, 1), datetime.date(2026, 9, 18))
    out = imported(client, rows=rows, as_of="2026-09-21")
    assert [s for s in out["streams"] if s["kind"] == "income"] == []
    assert out["provenance"]["unscheduled_inflow_count"] == 24
    assert out["provenance"]["next_payday"] is None
    assert not [t for t in out["scheduled"] if t["kind"] == "income"]


def _semimonthly_rows(months, description="BLUE RIDGE CAFE", amount=61000):
    """The 15th and the last day of each month, income shifted off weekends."""
    import calendar

    out = []
    for year, month in months:
        for day in (15, calendar.monthrange(year, month)[1]):
            when = datetime.date(year, month, day)
            while when.weekday() >= 5:
                when += datetime.timedelta(days=1)
            out.append(H.row(when, description, amount))
    return out


def test_month_end_income_lands_on_the_month_end_not_a_day_early(client):
    # A numeric mode loses month-end: the 30th recurs more often than the
    # 31st across a year, and projecting the 30th into a 31-day month pays
    # the person a day EARLY. Early is the direction that invents cash.
    months = [(2025, 10), (2025, 11), (2025, 12), (2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5), (2026, 6)]
    rows = _semimonthly_rows(months)
    rows += H.everyday_spending(datetime.date(2026, 4, 1), datetime.date(2026, 6, 30))
    out = imported(client, rows=rows, as_of="2026-07-01", horizon_days=45)
    income = [s for s in out["streams"] if s["kind"] == "income"]
    assert len(income) == 1 and income[0]["cadence"] == "semimonthly"
    ids = set(income[0]["projected_ids"])
    dates = sorted(t["date"] for t in out["scheduled"] if t["id"] in ids)
    # 2026-08-15 is a Saturday, so August's mid-month pay moves FORWARD to
    # the 17th, past the end of a 45-day window.
    assert dates == ["2026-07-15", "2026-07-31"], dates


def test_month_end_income_clamps_into_a_short_month(client):
    # February has no 30th or 31st. The anchor must clamp, and the 15th must
    # not move with it.
    months = [(2025, 8), (2025, 9), (2025, 10), (2025, 11), (2025, 12), (2026, 1)]
    rows = _semimonthly_rows(months)
    rows += H.everyday_spending(datetime.date(2025, 11, 1), datetime.date(2026, 1, 31))
    out = imported(client, rows=rows, as_of="2026-02-01", horizon_days=28)
    income = [s for s in out["streams"] if s["kind"] == "income"]
    assert len(income) == 1
    ids = set(income[0]["projected_ids"])
    dates = sorted(t["date"] for t in out["scheduled"] if t["id"] in ids)
    # 02-02 is JANUARY's month end: the 31st was a Saturday and income moves
    # forward. 02-16 is February's 15th, a Sunday, likewise. February's own
    # month end is a Saturday and lands 03-02, past the window.
    assert dates == ["2026-02-02", "2026-02-16"], dates


def test_a_bill_on_the_twenty_eighth_is_not_dragged_to_the_month_end(client):
    # Only February makes the 28th a month end, so the month-end rule must
    # not fire on this stream.
    rows = H.monthly_bill(datetime.date(2025, 11, 28), 10, 28, -4200, "ZZQ7K4 HOLDINGS", weekend_shift=False)
    rows += H.everyday_spending(datetime.date(2026, 6, 1), datetime.date(2026, 8, 31))
    out = imported(client, rows=rows, as_of="2026-09-01", horizon_days=40)
    bill = next(s for s in out["streams"] if s["amount_cents"] == -4200)
    ids = set(bill["projected_ids"])
    dates = sorted(t["date"] for t in out["scheduled"] if t["id"] in ids)
    assert dates and all(d.endswith("-28") for d in dates), dates

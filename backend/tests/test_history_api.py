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


def test_the_exemption_is_load_bearing(monkeypatch):
    # Remove the filter and the generator offers "skip this charge" against
    # spending the product invented on the person's behalf.
    from app.candidates import generate
    from app.candidates.policy import UNKNOWN_DISCRETIONARY
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
    assert UNKNOWN_DISCRETIONARY, "policy must still offer something for unknown discretionary rows"
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


def test_the_golden_account_is_pinned(client):
    out = imported(client)
    streams = out["streams"]
    kinds = sorted(s["kind"] for s in streams)
    assert kinds == ["bill", "bill", "bill", "discretionary", "income"]
    income = next(s for s in streams if s["kind"] == "income")
    assert (income["cadence"], income["anchor"]) == ("weekly", "Tuesday")
    assert out["provenance"]["next_payday"] == "2026-09-22"
    assert sorted(s["amount_cents"] for s in streams if s["kind"] == "bill") == [-120000, -3499, -1599]

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
    assert solve(request).tier == 3


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

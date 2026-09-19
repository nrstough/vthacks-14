"""The HTTP surface of POST /api/candidates.

The endpoint shares SolveRequest's validators rather than copying them, so the
422 table below is really asking whether that sharing held: a field order that
drifted would make the span checks silently stop running, and the only visible
symptom would be a request this endpoint accepts and /api/solve rejects.
"""

from __future__ import annotations

import copy
import statistics
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas import CENTS_ABS, MAX_FREE, Candidate, CandidatesResponse
from tests.fixtures.scenarios import AS_OF, HORIZON_END, SCHEDULED


def body(**overrides):
    base = {"as_of": AS_OF, "horizon_end": HORIZON_END, "scheduled": copy.deepcopy(SCHEDULED)}
    return {**base, **overrides}


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(None))


@pytest.fixture(scope="module")
def client_with_site(tmp_path_factory):
    site = tmp_path_factory.mktemp("dist")
    (site / "index.html").write_text("<!doctype html><title>app</title>")
    return TestClient(create_app(site))


def test_the_demo_account_answers_over_http(client):
    r = client.post("/api/candidates", json=body())
    assert r.status_code == 200
    payload = r.json()
    assert len(payload["candidates"]) == 14
    assert payload["meta"]["rows_considered"] == 13


def _mutate(**changes):
    raw = body()
    for key, value in changes.items():
        raw[key] = value
    return raw


@pytest.mark.parametrize(
    ("raw", "field"),
    [
        (_mutate(nonsense=1), "nonsense"),
        (_mutate(as_of="20260919"), "as_of"),
        (_mutate(as_of=20260919), "as_of"),
        (_mutate(horizon_end="2026-09-18"), "horizon_end"),
        (_mutate(horizon_end="2027-12-31"), "horizon_end"),
        (_mutate(limit=0), "limit"),
        (_mutate(limit=61), "limit"),
        (_mutate(limit=None), "limit"),
        (_mutate(limit="18"), "limit"),
        (_mutate(limit=18.0), "limit"),
    ],
)
def test_a_bad_request_names_the_field(client, raw, field):
    r = client.post("/api/candidates", json=raw)
    assert r.status_code == 422
    detail = r.json()["detail"][0]
    assert detail["loc"][0] == "body"
    assert detail["loc"][1] == field


def test_a_float_amount_is_refused(client):
    raw = body()
    raw["scheduled"][0]["amount_cents"] = -11.99
    r = client.post("/api/candidates", json=raw)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][1] == "scheduled"


def test_two_transactions_may_not_share_an_id(client):
    raw = body()
    raw["scheduled"][1]["id"] = raw["scheduled"][0]["id"]
    r = client.post("/api/candidates", json=raw)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][1] == "scheduled"


def test_more_rows_than_the_limit_allows_is_refused(client):
    raw = body(scheduled=[
        {"id": f"t_{i:05d}", "date": "2026-09-22", "description": "KROGER #382",
         "amount_cents": -4000, "kind": "discretionary", "recurring": False}
        for i in range(2001)
    ])
    r = client.post("/api/candidates", json=raw)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][1] == "scheduled"


def test_an_omitted_limit_is_the_one_every_fallback_can_answer(client):
    raw = body()
    assert "limit" not in raw
    r = client.post("/api/candidates", json=raw)
    assert len(r.json()["candidates"]) <= MAX_FREE


def test_an_account_with_nothing_in_it_is_an_answer_not_an_error(client):
    r = client.post("/api/candidates", json=body(scheduled=[]))
    assert r.status_code == 200
    assert r.json() == {
        "candidates": [],
        "meta": {"rows_considered": 0, "protected": [], "unrecognised": [],
                 "not_actionable": [], "truncated": False},
    }


def test_every_field_at_its_maximum_still_answers(client):
    # The class of defect that once made a legal request a 500.
    scheduled = [{
        "id": "t_pay", "date": "2026-09-19", "description": "HARRIS TEETER PAYROLL",
        "amount_cents": CENTS_ABS, "kind": "income", "recurring": True,
    }]
    for i in range(1999):
        scheduled.append({
            "id": f"t_{i:05d}", "date": f"2026-09-{19 + i % 12:02d}",
            "description": "KROGER #382", "amount_cents": -CENTS_ABS,
            "kind": "discretionary", "recurring": False,
        })
    r = client.post("/api/candidates", json={
        "as_of": "2026-09-19", "horizon_end": "2027-09-18", "scheduled": scheduled,
    })
    assert r.status_code == 200
    assert len(r.json()["candidates"]) <= MAX_FREE


def test_serving_the_site_does_not_swallow_the_endpoint(client_with_site):
    # A StaticFiles mount at "/" registered first answers 405 here.
    r = client_with_site.post("/api/candidates", json=body())
    assert r.status_code == 200
    assert client_with_site.get("/").status_code == 200


def test_every_item_is_something_the_solver_would_accept(client):
    payload = client.post("/api/candidates", json=body()).json()
    CandidatesResponse.model_validate(payload)
    for item in payload["candidates"]:
        Candidate.model_validate(item)


def test_two_processes_of_the_app_answer_identically(client):
    first = TestClient(create_app(None)).post("/api/candidates", json=body())
    second = TestClient(create_app(None)).post("/api/candidates", json=body())
    assert first.content == second.content


def test_the_health_check_and_the_solver_still_answer(client):
    assert client.get("/health").json() == {"ok": True}
    assert client.post("/api/solve", json={
        "as_of": AS_OF, "horizon_end": HORIZON_END, "opening_balance_cents": 20_000,
        "buffer_cents": 2_500, "scheduled": SCHEDULED, "candidates": [],
        "locks": {"in": [], "out": []}, "previous_plan": [],
    }).status_code == 200


@pytest.mark.perf
def test_two_thousand_rows_with_long_descriptions(client):
    # Descriptions are unbounded, and matching walks their tokens.
    noise = "MISCELLANEOUS PURCHASE AUTHORISATION REFERENCE " * 40
    scheduled = [{
        "id": f"t_{i:05d}", "date": f"2026-09-{19 + i % 12:02d}",
        "description": f"KROGER #382 {noise}", "amount_cents": -4000,
        "kind": "discretionary", "recurring": False,
    } for i in range(2000)]
    raw = {"as_of": "2026-09-19", "horizon_end": "2026-10-02", "scheduled": scheduled}
    client.post("/api/candidates", json=raw)
    times = []
    for _ in range(5):
        started = time.perf_counter()
        r = client.post("/api/candidates", json=raw)
        times.append((time.perf_counter() - started) * 1000)
    assert r.status_code == 200
    median = statistics.median(times)
    print(f"\n2000 rows x {len(noise)}-char descriptions: {median:.0f} ms")
    assert median < 2000

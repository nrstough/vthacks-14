"""The HTTP surface.

Two things here have bitten real deployments and are pinned deliberately: a
static mount registered before the routes swallows them whole, and a validation
error that escapes as a 500 tells the client nothing it can act on.
"""

from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.fixtures import planted
from tests.fixtures.scenarios import SCENARIOS


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(None))


@pytest.fixture(scope="module")
def client_with_site(tmp_path_factory):
    """The built frontend is gitignored, so the mount is tested against a stand-in."""
    site = tmp_path_factory.mktemp("dist")
    (site / "index.html").write_text("<!doctype html><title>app</title>")
    (site / "app.js").write_text("console.log(1)")
    return TestClient(create_app(site))


def test_health_is_a_plain_yes(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_each_demo_account_solves_over_http(client, name):
    r = client.post("/api/solve", json=SCENARIOS[name])
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] in (1, 2, 3)
    assert len(body["balances"]) == 14
    assert body["meta"]["solver"] in ("cp-sat", "brute-force")


def test_a_bad_request_names_the_field(client):
    bad = copy.deepcopy(SCENARIOS["clears"])
    bad["opening_balance_cents"] = 200.5
    r = client.post("/api/solve", json=bad)
    assert r.status_code == 422
    detail = r.json()["detail"][0]
    assert detail["loc"][0] == "body"
    assert detail["loc"][1:], "a 422 with no field path is not actionable"
    assert detail["loc"][1] == "opening_balance_cents"


def test_no_malformed_request_escapes_as_a_server_error(client):
    """Every rejection is the client's to fix, and says so."""
    broken = [
        {},
        {"as_of": "2026-09-19"},
        {**SCENARIOS["clears"], "horizon_end": "nope"},
        {**SCENARIOS["clears"], "scheduled": "not a list"},
        {**SCENARIOS["clears"], "locks": {"in": ["ghost"], "out": []}},
        {**SCENARIOS["clears"], "surprise": True},
        {**SCENARIOS["clears"], "candidates": None},
    ]
    for payload in broken:
        r = client.post("/api/solve", json=payload)
        assert r.status_code == 422, payload
        assert r.json()["detail"][0]["loc"][0] == "body"


def test_an_engine_that_cannot_answer_is_a_503_not_a_500(client, monkeypatch):
    """The request was fine; the service could not answer it exactly. That is a
    different thing from a crash, and the client can retry or fall back."""
    import app.solver.solve as solve_module
    from app.solver.errors import EngineUnavailable

    def refuse(*_args, **_kwargs):
        raise EngineUnavailable("no engine could answer")

    monkeypatch.setattr(solve_module, "solve", refuse)
    monkeypatch.setattr("app.main.solve", refuse)
    r = client.post("/api/solve", json=SCENARIOS["clears"])
    assert r.status_code == 503
    assert "detail" in r.json()
    assert "infeasib" not in r.json()["detail"].lower()


def test_the_dev_server_may_call_across_origins(client):
    r = client.options(
        "/api/solve",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_the_site_is_served_without_swallowing_the_api(client_with_site):
    """A mount at "/" registered before the routes answers 404 for /health and
    405 for /api/solve, and the failure looks like a routing mystery."""
    assert client_with_site.get("/health").json() == {"ok": True}
    assert client_with_site.post("/api/solve", json=SCENARIOS["gap"]).status_code == 200
    assert client_with_site.get("/").status_code == 200
    assert "app" in client_with_site.get("/").text
    assert client_with_site.get("/app.js").status_code == 200


def test_without_a_built_site_the_api_still_works(client):
    assert client.get("/").status_code == 404
    assert client.post("/api/solve", json=SCENARIOS["clears"]).status_code == 200


def test_locking_a_change_changes_the_answer(client):
    """The interaction the demo turns on: rule something out, re-solve."""
    before = client.post("/api/solve", json=SCENARIOS["clears"]).json()
    assert "c_card_min" in [p["candidate_id"] for p in before["plan"]]

    ruled_out = {**SCENARIOS["clears"], "locks": {"in": [], "out": ["c_card_min"]}}
    after = client.post("/api/solve", json=ruled_out).json()
    assert "c_card_min" not in [p["candidate_id"] for p in after["plan"]]
    assert len(after["plan"]) > len(before["plan"]), "it was load-bearing, so more is needed"
    assert after["meta"]["candidates_considered"] == 10


def test_a_pinned_change_comes_back(client):
    pinned = {**SCENARIOS["clears"], "locks": {"in": ["c_netflix"], "out": []}}
    body = client.post("/api/solve", json=pinned).json()
    assert "c_netflix" in [p["candidate_id"] for p in body["plan"]]


def test_the_previous_plan_travels_with_the_request(client):
    """There is no session: steadiness comes from the client sending back what
    it was last shown."""
    first = client.post("/api/solve", json=planted.IDENTICAL_PAIR).json()
    assert [p["candidate_id"] for p in first["plan"]] == ["c_a"]
    again = client.post("/api/solve", json=planted.IDENTICAL_PAIR_REMEMBERED).json()
    assert [p["candidate_id"] for p in again["plan"]] == ["c_b"]

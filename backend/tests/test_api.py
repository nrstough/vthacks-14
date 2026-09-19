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


def test_a_large_but_legal_account_is_answered_not_crashed(client):
    """The regression for a 500 on a perfectly valid request.

    Balances and running totals are sums across the horizon, so they leave the
    range any single input field is allowed to occupy. Bounding the server's own
    output by the input bound made it reject its own answer, past the error
    handler, as a 500 — on two values that break no rule.
    """
    cap = 10**11
    raw = {
        "as_of": "2026-03-01",
        "horizon_end": "2026-03-02",
        "opening_balance_cents": -cap,
        "buffer_cents": 0,
        "scheduled": [
            {"id": "t_1", "date": "2026-03-01", "description": "X",
             "amount_cents": -1, "kind": "bill", "recurring": False},
            # A second charge at the cap, with a change that covers it, so the
            # plan is non-empty and the certificate rows are built too. Without
            # a candidate here, per_item stays empty and one of the widened
            # fields is never constructed by the test at all.
            {"id": "t_2", "date": "2026-03-02", "description": "Y",
             "amount_cents": -cap, "kind": "bill", "recurring": False},
        ],
        "candidates": [
            {"id": "c_a", "label": "Y", "detail": "Y", "action": "skip",
             "target_txn_id": "t_2", "freed_cents": cap,
             "effective_date": "2026-03-02", "recharge_date": None,
             "lead_time_days": 0, "pain": 1},
        ],
        "locks": {"in": [], "out": []},
        "previous_plan": [],
    }
    r = client.post("/api/solve", json=raw)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tier"] == 3
    assert body["balances"][0]["baseline_cents"] == -cap - 1
    # The certificate row is larger than any single input field is allowed to be.
    assert [p["candidate_id"] for p in body["plan"]] == ["c_a"]
    assert body["certificate"]["per_item"][0]["worst_shortfall_cents"] == 2 * cap + 1


def test_the_worst_case_the_input_limits_allow_is_answered(client):
    """The other end of the same argument: every cap at its maximum at once."""
    from app.schemas import CENTS_ABS, MAX_SCHED

    scheduled = [
        {"id": f"t_{i:04d}", "date": "2026-03-01", "description": "X",
         "amount_cents": -CENTS_ABS, "kind": "bill", "recurring": False}
        for i in range(MAX_SCHED)
    ]
    raw = {"as_of": "2026-03-01", "horizon_end": "2027-02-28",
           "opening_balance_cents": -CENTS_ABS, "buffer_cents": 0,
           "scheduled": scheduled, "candidates": [],
           "locks": {"in": [], "out": []}, "previous_plan": []}
    r = client.post("/api/solve", json=raw)
    assert r.status_code == 200, r.text[:400]
    assert r.json()["tier"] == 3


def test_a_broken_solver_install_falls_back_rather_than_crashing(client, monkeypatch):
    """A wheel whose native library will not load is a real failure mode, and it
    does not raise ImportError."""
    import app.solver.solve as solve_module

    for failure in (
        ImportError("No module named 'ortools'"),
        OSError("dlopen(libortools.dylib): image not found"),
        AttributeError("module 'ortools.sat' has no attribute 'python'"),
    ):
        monkeypatch.setattr(
            solve_module, "load_cpsat", lambda exc=failure: (_ for _ in ()).throw(exc)
        )
        r = client.post("/api/solve", json=SCENARIOS["clears"])
        assert r.status_code == 200, f"{failure!r} -> {r.status_code}"
        assert r.json()["meta"]["solver"] == "brute-force"


def test_a_refusal_never_leaks_the_solver_s_vocabulary(client, monkeypatch):
    """The banned words apply to the error body as much as to the plan.

    The constraint solver's own status names are diagnostics, and one of them is
    the single word this product never shows anyone. They belong in the log.
    """
    from ortools.sat.python import cp_model

    monkeypatch.setattr(
        cp_model.CpSolver, "solve", lambda self, m, *a, **k: cp_model.INFEASIBLE
    )

    raw = copy.deepcopy(SCENARIOS["clears"])
    # More changes than exhaustive search will take on, so there is no fallback
    # and the refusal is the actual response.
    from app.schemas import MAX_FREE

    for i in range(MAX_FREE + 1):
        raw["scheduled"].append({
            "id": f"t_x{i:02d}", "date": "2026-09-23", "description": "X",
            "amount_cents": -1000, "kind": "discretionary", "recurring": False,
        })
        raw["candidates"].append({
            "id": f"c_x{i:02d}", "label": "X", "detail": "X", "action": "skip",
            "target_txn_id": f"t_x{i:02d}", "freed_cents": 1000,
            "effective_date": "2026-09-23", "recharge_date": None,
            "lead_time_days": 0, "pain": 1,
        })

    r = client.post("/api/solve", json=raw)
    assert r.status_code == 503
    detail = r.json()["detail"].lower()
    for word in ("infeasib", "guarantee", "unknown", "model_invalid"):
        assert word not in detail, f"{word!r} reached the user: {detail!r}"

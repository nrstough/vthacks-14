"""Generated candidates, fed straight back into the solver.

The generator's output is only ever used as a solve request, so the property
that matters is not that a Candidate validates on its own but that the whole set
validates *against its own account* — freed against the charge it targets, dates
against the window. A generator bug otherwise shows up as a 200 here and a 422
on the client's very next call, with nothing naming this module.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.candidates import generate
from app.main import create_app
from app.schemas import CENTS_ABS, MAX_FREE, CandidatesRequest, SolveRequest
from app.solver.solve import Settings, solve
from tests.conftest import requires_node
from tests.fixtures.accounts import solve_request, windows
from tests.fixtures.scenarios import AS_OF, HORIZON_END, SCENARIOS, SCHEDULED
from tests.test_parity import assert_agrees
import tests.test_invariants as inv

WINDOWS = windows(300)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(None))


def candidates_for(win):
    return [c.model_dump() for c in generate(CandidatesRequest.model_validate(win)).candidates]


def demo_cases():
    """The three shipped presets, with generated candidates instead of the fixture's."""
    win = {"as_of": AS_OF, "horizon_end": HORIZON_END, "scheduled": SCHEDULED}
    generated = candidates_for(win)
    for name, raw in SCENARIOS.items():
        yield name, {**raw, "candidates": generated}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_each_demo_preset_solves_on_generated_candidates(client, name):
    case = dict(demo_cases())[name]
    r = client.post("/api/solve", json=case)
    assert r.status_code == 200, r.text
    assert r.json()["tier"] in (1, 2, 3)


def test_every_generated_set_is_a_legal_solve_request():
    for i, win in enumerate(WINDOWS):
        raw = solve_request(win, candidates_for(win))
        SolveRequest.model_validate(raw)  # raises on any cross-field violation


def test_the_biggest_account_the_schema_allows_still_solves(client):
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
    win = {"as_of": "2026-09-19", "horizon_end": "2027-09-18", "scheduled": scheduled}
    # An explicit opening at the input bound: the trough of this account is far
    # outside what a request may carry.
    raw = solve_request(win, candidates_for(win), opening=CENTS_ABS)
    assert client.post("/api/solve", json=raw).status_code == 200


def _engines_agree(raw):
    req = SolveRequest.model_validate(raw)
    cpsat = solve(req, Settings(force_engine="cp-sat")).model_dump()
    brute = solve(req, Settings(force_engine="brute-force")).model_dump()
    assert cpsat["plan"] == brute["plan"]
    assert cpsat["tier"] == brute["tier"]
    assert cpsat["certificate"]["per_item"] == brute["certificate"]["per_item"]


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_both_engines_agree_on_each_demo_preset(name):
    # The presets go through the default engine everywhere else; this is the only
    # place the exhaustive one is made to answer for them.
    _engines_agree(dict(demo_cases())[name])


def test_both_engines_agree_on_fifty_generated_accounts():
    # Brute force is 2^n over the horizon, so the gate takes the accounts it can
    # enumerate quickly — but it takes fifty of them, scanning as far through the
    # windows as it needs rather than filtering fifty down to whatever is left.
    # The whole set at the cap runs under -m perf.
    qualifying = []
    for win in WINDOWS:
        generated = candidates_for(win)
        if len(generated) <= 14:
            qualifying.append(solve_request(win, generated))
        if len(qualifying) == 50:
            break
    assert len(qualifying) == 50, f"only {len(qualifying)} accounts were small enough"
    for raw in qualifying:
        _engines_agree(raw)


@requires_node
def test_the_reference_solver_agrees_on_generated_accounts(oracle):
    cases = [raw for _, raw in demo_cases()]
    for win in WINDOWS[:100]:
        generated = candidates_for(win)
        # The reference solver is exhaustive and refuses above twenty.
        assert len(generated) <= MAX_FREE
        cases.append(solve_request(win, generated))
    theirs = oracle(cases)
    for raw, their in zip(cases, theirs):
        ours = solve(SolveRequest.model_validate(raw)).model_dump()
        assert_agrees(raw, ours, their)


@requires_node
def test_an_account_where_nothing_may_be_changed_agrees_too(oracle):
    # Every row protected, so the plan is empty at tier 3 — the one place this
    # service deliberately words the certificate differently.
    scheduled = [
        {"id": "t_rent", "date": "2026-09-22", "description": "MARKET ST PROPERTIES LLC",
         "amount_cents": -90_000, "kind": "bill", "recurring": True},
        {"id": "t_card", "date": "2026-09-24", "description": "CHASE CARD EPAY 8812",
         "amount_cents": -12_844, "kind": "bill", "recurring": True},
    ]
    win = {"as_of": "2026-09-19", "horizon_end": "2026-10-02", "scheduled": scheduled}
    generated = candidates_for(win)
    assert generated == []
    raw = solve_request(win, generated, opening=1_000)
    ours = solve(SolveRequest.model_validate(raw)).model_dump()
    assert ours["tier"] == 3 and ours["plan"] == []
    assert_agrees(raw, ours, oracle([raw])[0])


def test_the_response_properties_hold_on_generated_accounts():
    checks = [
        inv.test_chart_matches_the_request,
        inv.test_reported_shortfall_and_tier_follow_from_the_balances,
        inv.test_certificate_rows_are_reproducible,
        inv.test_external_cash_actually_closes_the_gap,
        inv.test_no_transaction_is_changed_two_ways,
        inv.test_strictly_needed_matches_the_certificate,
        inv.test_the_plan_is_described_consistently_everywhere,
        inv.test_plan_is_ordered_by_the_day_you_must_act,
        inv.test_paydays_are_marked,
    ]
    for win in WINDOWS[:50]:
        raw = solve_request(win, candidates_for(win))
        res = solve(SolveRequest.model_validate(raw)).model_dump()
        for check in checks:
            check((raw, res))


def test_an_override_survives_the_account_being_generated_again(client):
    win = next(w for w in WINDOWS if len(candidates_for(w)) >= 2)
    first = candidates_for(win)
    pinned = first[0]["id"]
    assert pinned in {c["id"] for c in candidates_for(win)}
    raw = solve_request(win, first, opening=0, locks={"in": [pinned], "out": []})
    r = client.post("/api/solve", json=raw)
    assert r.status_code == 200, r.text
    assert pinned in [item["candidate_id"] for item in r.json()["plan"]]


def test_candidates_go_stale_when_the_day_moves_under_them():
    # Documented, not incidental: the client must send one as_of to both
    # endpoints and re-fetch candidates whenever it changes.
    win = {
        "as_of": "2026-09-19", "horizon_end": "2026-10-02",
        "scheduled": [{
            "id": "t_today", "date": "2026-09-19", "description": "DOORDASH*CHIPOTLE",
            "amount_cents": -3_180, "kind": "discretionary", "recurring": False,
        }],
    }
    generated = candidates_for(win)
    assert generated and generated[0]["effective_date"] == "2026-09-19"
    tomorrow = {**win, "as_of": "2026-09-20"}
    with pytest.raises(ValidationError) as caught:
        SolveRequest.model_validate(solve_request(tomorrow, generated, opening=0))
    assert caught.value.errors()[0]["loc"][0] == "candidates"


def test_no_generated_deferral_ever_recharges_past_the_horizon():
    # True by construction, and worth pinning so nobody later claims these
    # accounts cover the past-horizon branch. tests/gen.py covers that.
    for win in WINDOWS:
        for c in candidates_for(win):
            if c["recharge_date"] is not None:
                assert c["recharge_date"] <= win["horizon_end"]


@pytest.mark.perf
def test_both_engines_agree_across_every_generated_account():
    import time
    started = time.perf_counter()
    checked = 0
    for win in WINDOWS:
        generated = candidates_for(win)
        if len(generated) > MAX_FREE:
            continue
        req = SolveRequest.model_validate(solve_request(win, generated))
        cpsat = solve(req, Settings(force_engine="cp-sat")).model_dump()
        brute = solve(req, Settings(force_engine="brute-force")).model_dump()
        assert cpsat["plan"] == brute["plan"]
        checked += 1
    print(f"\ncp-sat == brute force on {checked} generated accounts "
          f"in {time.perf_counter() - started:.1f} s")

"""Engine behaviour when things do not go well.

The happy path is covered by parity and the objective tests. What matters here
is what the service says when the search does not finish: it must stop claiming
a proof it does not have, and it must never quietly substitute a guess.
"""

from __future__ import annotations

import json

import pytest
from ortools.sat.python import cp_model

from app.schemas import SolveRequest
from app.solver.errors import EngineUnavailable
from app.solver.solve import Settings, solve
from app.solver.wording import BANNED, OPTIMALITY_CLAIMS
from tests.fixtures import planted
from tests.fixtures.scenarios import SCENARIOS

CPSAT = Settings(force_engine="cp-sat")


def run(raw: dict, settings: Settings | None = CPSAT):
    return solve(SolveRequest.model_validate(raw), settings)


def all_strings(payload) -> list[str]:
    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, dict):
        return [s for v in payload.values() for s in all_strings(v)]
    if isinstance(payload, list):
        return [s for v in payload for s in all_strings(v)]
    return []


def downgrade_to_feasible(monkeypatch):
    """Run the real solve, then report it as unproven.

    Wrapping rather than replacing matters: a stub that merely returns FEASIBLE
    leaves no solution behind, so every later `value()` call would read garbage
    and the test would pass for the wrong reason.
    """
    real = cp_model.CpSolver.solve

    def wrapper(self, model, *args, **kwargs):
        status = real(self, model, *args, **kwargs)
        return cp_model.FEASIBLE if status == cp_model.OPTIMAL else status

    monkeypatch.setattr(cp_model.CpSolver, "solve", wrapper)


def test_an_unproven_search_says_so(monkeypatch):
    downgrade_to_feasible(monkeypatch)
    res = run(SCENARIOS["clears"])
    assert res.meta.status == "FEASIBLE"
    assert res.certificate.minimal_proven is False
    assert res.meta.solver == "cp-sat"
    # The plan must still be a real plan, verified against the ledger.
    assert res.tier == 1
    assert [b.with_plan_cents for b in res.balances][-1] >= 0


def test_an_unproven_search_drops_the_claims_it_cannot_support(monkeypatch):
    downgrade_to_feasible(monkeypatch)
    res = run(SCENARIOS["gap"])
    assert res.certificate.minimal_proven is False
    text = " ".join(all_strings(json.loads(res.model_dump_json())))
    for claim in OPTIMALITY_CLAIMS:
        assert claim not in text, f"unproven response still claims: {claim}"
    # It should still be useful: the gap and its deadline are facts, not claims.
    assert "$27.62" in res.verdict
    assert res.external_cash_needed is not None


def test_a_proven_search_does_make_the_claim():
    """Counterfactual for the test above: the wording is conditional, not absent."""
    res = run(SCENARIOS["gap"])
    assert res.certificate.minimal_proven is True
    assert "No combination of these changes" in res.verdict
    assert "This is the best partial plan" in res.qualifier


def test_running_out_of_time_mid_tiebreak_keeps_the_plan(monkeypatch):
    """The last stage only orders ties; losing it must not lose the answer."""
    real = cp_model.CpSolver.solve
    calls = {"n": 0}

    def wrapper(self, model, *args, **kwargs):
        calls["n"] += 1
        status = real(self, model, *args, **kwargs)
        return cp_model.UNKNOWN if calls["n"] > 7 else status

    monkeypatch.setattr(cp_model.CpSolver, "solve", wrapper)

    res = run(planted.IDENTICAL_PAIR)
    assert calls["n"] > 7, "the tiebreak stage did not run"
    assert res.meta.status == "FEASIBLE"
    assert res.certificate.minimal_proven is False
    assert len(res.plan) == 1, "still a valid, complete plan"
    assert res.tier == 1


def test_a_failed_first_stage_falls_back_rather_than_guessing(monkeypatch):
    monkeypatch.setattr(cp_model.CpSolver, "solve", lambda self, m, *a, **k: cp_model.UNKNOWN)
    res = run(SCENARIOS["clears"], Settings())
    assert res.meta.solver == "brute-force"
    assert res.meta.status == "OPTIMAL"
    assert len(res.plan) == 3


def test_a_failed_first_stage_with_no_fallback_refuses(monkeypatch):
    monkeypatch.setattr(cp_model.CpSolver, "solve", lambda self, m, *a, **k: cp_model.UNKNOWN)
    with pytest.raises(EngineUnavailable):
        run(SCENARIOS["clears"], CPSAT)


def test_no_budget_at_all_is_refused_not_approximated():
    with pytest.raises(EngineUnavailable):
        run(SCENARIOS["clears"], Settings(force_engine="cp-sat", total_budget_s=-1.0))


def test_the_tiebreak_picks_the_smallest_id_set_at_scale():
    """Forty interchangeable changes, three needed.

    Enumeration cannot reach this size, so it is the case where the constraint
    solver is doing something exhaustive search could not — and it still has to
    land on the same answer the rule predicts.
    """
    scheduled = [{"id": "t_hit", "date": "2026-03-02", "description": "HIT",
                  "amount_cents": -30_000, "kind": "bill", "recurring": False}]
    candidates = []
    for i in range(40):
        scheduled.append({"id": f"t_{i:02d}", "date": "2026-03-02", "description": "X",
                          "amount_cents": -10_000, "kind": "discretionary", "recurring": False})
        candidates.append({"id": f"c_{i:02d}", "label": "X", "detail": "X", "action": "skip",
                           "target_txn_id": f"t_{i:02d}", "freed_cents": 10_000,
                           "effective_date": "2026-03-01", "recharge_date": None,
                           "lead_time_days": 0, "pain": 2})
    # Do nothing: 0 | -(30_000 + 40*10_000). Each change frees 10_000, and the
    # balance needs exactly 43 of them to reach zero... so instead make the
    # charges land after the horizon and only the 30_000 bite.
    scheduled = [s if s["id"] == "t_hit" else {**s, "date": "2026-03-09"} for s in scheduled]
    raw = {"as_of": "2026-03-01", "horizon_end": "2026-03-03", "opening_balance_cents": 0,
           "buffer_cents": 0, "scheduled": scheduled, "candidates": candidates,
           "locks": {"in": [], "out": []}, "previous_plan": []}

    res = run(raw)
    assert res.tier == 1
    assert [p.candidate_id for p in res.plan] == ["c_00", "c_01", "c_02"]
    assert res.certificate.minimal_proven is True


def test_repeat_solves_are_byte_identical():
    """A request answered two ways is a trust problem before it is a bug."""
    for name, raw in SCENARIOS.items():
        baseline = run(raw).model_dump_json(exclude={"meta"})
        for _ in range(10):
            assert run(raw).model_dump_json(exclude={"meta"}) == baseline, name


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_the_forbidden_words_never_appear(name):
    for settings in (CPSAT, Settings(force_engine="brute-force")):
        text = " ".join(all_strings(json.loads(run(SCENARIOS[name], settings).model_dump_json())))
        for word in BANNED:
            assert word not in text.lower(), f"{name}: {word!r} reached the user"

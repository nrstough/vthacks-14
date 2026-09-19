"""Differential test against the frontend's reference solver.

The reference is executed as TypeScript under Node, not ported, so the two
implementations share no code and agreement is evidence rather than tautology.

There is exactly one intended disagreement, asserted rather than tolerated: see
`_is_known_departure`.
"""

from __future__ import annotations

import json

import pytest

from app.schemas import SolveRequest
from app.solver.solve import Settings, solve
from tests.conftest import requires_node
from tests.fixtures.scenarios import SCENARIOS
from tests.gen import instances

RANDOM_N = 50

# Reported by each side separately and not part of the agreement: which engine
# answered, and how long it took.
IGNORED_META = ("solver", "wall_ms")


def _normalise(payload: dict) -> dict:
    d = json.loads(json.dumps(payload))
    for key in IGNORED_META:
        d["meta"].pop(key, None)
    return d


def assert_agrees(request: dict, ours: dict, theirs: dict) -> None:
    """Every field, with no exceptions.

    There used to be one: the reference solver said "the schedule already
    clears" for any empty plan, which is false at tier 3, where the plan is
    empty because nothing could be changed in time. Both implementations now
    say the same true thing, so the exception is gone — and with it the risk of
    it quietly covering a second divergence.
    """
    ours, theirs = _normalise(ours), _normalise(theirs)
    for key in theirs:
        if ours.get(key) == theirs[key]:
            continue
        raise AssertionError(
            f"{key} differs\n  ours:   {json.dumps(ours.get(key))[:600]}\n"
            f"  theirs: {json.dumps(theirs[key])[:600]}\n"
            f"  request: {json.dumps(request)[:900]}"
        )


def _solve(raw: dict, settings: Settings | None = None) -> dict:
    return solve(SolveRequest.model_validate(raw), settings).model_dump()


@requires_node
@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_demo_accounts_match_the_reference(name, oracle):
    raw = SCENARIOS[name]
    assert_agrees(raw, _solve(raw), oracle([raw])[0])


@requires_node
def test_random_instances_match_the_reference(oracle):
    reqs = instances(RANDOM_N)
    expected = oracle(reqs)
    for raw, theirs in zip(reqs, expected):
        assert_agrees(raw, _solve(raw), theirs)


@requires_node
def test_the_departure_actually_fires(oracle):
    """Guard the guard: if no instance exercised it, the exemption above is
    silently excusing something else."""
    reqs = instances(RANDOM_N)
    fired = sum(
        1
        for raw, theirs in zip(reqs, oracle(reqs))
        if theirs["tier"] == 3 and not theirs["plan"]
    )
    assert fired > 0, "no tier-3 empty-plan instance in the sample"


def test_engines_agree_on_the_demo_accounts():
    """Whatever engine is default must match exhaustive search."""
    for name, raw in SCENARIOS.items():
        brute = _solve(raw, Settings(force_engine="brute-force"))
        default = _solve(raw)
        assert _normalise(brute) == _normalise(default), name


def test_random_instances_agree_between_engines():
    for i, raw in enumerate(instances(RANDOM_N)):
        brute = _normalise(_solve(raw, Settings(force_engine="brute-force")))
        default = _normalise(_solve(raw))
        assert brute == default, f"instance {i}"


def test_fallback_when_ortools_is_missing(monkeypatch):
    """A machine without OR-Tools still answers, exactly."""
    import app.solver.solve as solve_module

    def no_ortools():
        raise ImportError("no ortools here")

    monkeypatch.setattr(solve_module, "load_cpsat", no_ortools)
    for name, raw in SCENARIOS.items():
        fallback = _solve(raw)
        assert fallback["meta"]["solver"] == "brute-force", name
        assert _normalise(fallback) == _normalise(_solve(raw, Settings(force_engine="brute-force")))


def test_refuses_rather_than_guesses_when_no_engine_can_answer(monkeypatch):
    """Too many candidates for enumeration and no CP-SAT: refuse loudly.

    The failure mode this forbids is a heuristic answer that looks exactly like
    a proven one in the response.
    """
    import app.solver.solve as solve_module
    from app.schemas import MAX_FREE
    from app.solver.errors import EngineUnavailable

    monkeypatch.setattr(solve_module, "load_cpsat", lambda: (_ for _ in ()).throw(ImportError()))

    raw = SCENARIOS["clears"]
    txns = list(raw["scheduled"])
    candidates = []
    for i in range(MAX_FREE + 1):
        txns.append({
            "id": f"t_x{i:02d}", "date": "2026-09-23", "description": "X",
            "amount_cents": -1000, "kind": "discretionary", "recurring": False,
        })
        candidates.append({
            "id": f"c_x{i:02d}", "label": "X", "detail": "X", "action": "skip",
            "target_txn_id": f"t_x{i:02d}", "freed_cents": 1000,
            "effective_date": "2026-09-23", "recharge_date": None,
            "lead_time_days": 0, "pain": 1,
        })
    big = {**raw, "scheduled": txns, "candidates": candidates}

    with pytest.raises(EngineUnavailable):
        _solve(big)


@requires_node
def test_the_planted_cases_match_the_reference_too(oracle):
    """The hand-built instances are where this service's rules are pinned, so
    they are also where a disagreement would matter most."""
    from tests.fixtures import planted

    cases = {
        name: value
        for name, value in vars(planted).items()
        if name.isupper() and isinstance(value, dict) and "as_of" in value
    }
    assert len(cases) >= 13, "planted fixtures went missing"
    reqs = [cases[n] for n in sorted(cases)]
    for raw, theirs in zip(reqs, oracle(reqs)):
        assert_agrees(raw, _solve(raw), theirs)

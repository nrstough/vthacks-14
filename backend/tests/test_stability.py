"""Does the answer hold still?

A plan that changes completely because the balance moved by a dollar is a
trust problem before it is a correctness one — the user cannot tell the
difference between "the maths changed" and "the tool is guessing". The research
measured a 21% plan-flip rate per dollar before mitigation and 1% after; the
mitigations that survive here are the cushion, the deterministic tiebreak, and
remembering the plan the user was last shown.
"""

from __future__ import annotations

import json

import pytest

from app.schemas import SolveRequest
from app.solver.solve import Settings, solve
from tests.fixtures.scenarios import SCENARIOS

SWEEP_CENTS = range(-4_000, 4_001, 100)  # plus or minus forty dollars, a dollar at a time


def stable_part(res) -> str:
    """The whole response bar the one field that is allowed to vary.

    Excluding all of `meta` would also stop comparing which engine answered and
    how many changes it considered, which is exactly the kind of drift a
    determinism test is for.
    """
    payload = res.model_dump()
    payload["meta"].pop("wall_ms")
    return json.dumps(payload, sort_keys=True)


def plans_across_a_sweep(base: dict, *, remember: bool) -> list[tuple[str, ...]]:
    plans: list[tuple[str, ...]] = []
    previous: list[str] = []
    for delta in SWEEP_CENTS:
        raw = {
            **base,
            "opening_balance_cents": base["opening_balance_cents"] + delta,
            "previous_plan": previous if remember else [],
        }
        res = solve(SolveRequest.model_validate(raw))
        ids = tuple(p.candidate_id for p in res.plan)
        plans.append(ids)
        previous = list(ids)
    return plans


def flip_rate(plans: list[tuple[str, ...]]) -> float:
    flips = sum(1 for a, b in zip(plans, plans[1:]) if a != b)
    return flips / (len(plans) - 1)


def test_a_dollar_either_way_rarely_changes_the_advice():
    plans = plans_across_a_sweep(SCENARIOS["clears"], remember=True)
    rate = flip_rate(plans)
    print(f"\nplan changes across {len(plans)} one-dollar steps: {rate:.1%}")
    assert rate <= 0.15, f"the plan flips on {rate:.0%} of one-dollar steps"


def test_remembering_the_last_plan_makes_it_steadier():
    """Counterfactual for the hysteresis term: without it, the same sweep churns
    at least as much."""
    with_memory = flip_rate(plans_across_a_sweep(SCENARIOS["clears"], remember=True))
    without = flip_rate(plans_across_a_sweep(SCENARIOS["clears"], remember=False))
    assert with_memory <= without


def test_the_same_request_gives_the_same_answer_every_time():
    for name, raw in SCENARIOS.items():
        first = stable_part(solve(SolveRequest.model_validate(raw)))
        for _ in range(10):
            assert stable_part(solve(SolveRequest.model_validate(raw))) == first, name


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_both_engines_stay_in_step_across_the_sweep(name):
    """A stability guarantee that only one engine keeps is not a guarantee."""
    base = SCENARIOS[name]
    for delta in range(-2_000, 2_001, 500):
        raw = {**base, "opening_balance_cents": base["opening_balance_cents"] + delta}
        req = SolveRequest.model_validate(raw)
        a = solve(req, Settings(force_engine="cp-sat"))
        b = solve(req, Settings(force_engine="brute-force"))
        assert [p.candidate_id for p in a.plan] == [p.candidate_id for p in b.plan]
        assert a.tier == b.tier

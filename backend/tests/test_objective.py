"""What the solver optimises, checked one rule at a time.

Each test uses a planted instance whose answer was worked out by hand, and most
of them fail if the rule under test is removed — a guard nothing can violate is
not tested, it is decoration.
"""

from __future__ import annotations

import pytest

from app.schemas import SolveRequest
from app.solver.solve import Settings, solve
from tests.fixtures import planted

ENGINES = [Settings(force_engine="cp-sat"), Settings(force_engine="brute-force")]
ENGINE_IDS = ["cp-sat", "brute-force"]


def run(raw: dict, settings: Settings | None = None):
    return solve(SolveRequest.model_validate(raw), settings)


def ids(res) -> list[str]:
    return sorted(p.candidate_id for p in res.plan)


@pytest.fixture(params=ENGINES, ids=ENGINE_IDS)
def engine(request):
    return request.param


def test_timing_beats_size(engine):
    """The change that arrives in time wins over the change that frees more."""
    res = run(planted.GREEDY_FAILS, engine)
    assert ids(res) == planted.GREEDY_FAILS_PLAN
    assert res.tier == 1
    # And the bigger, later change genuinely could not have done the job alone.
    alone = run({**planted.GREEDY_FAILS, "locks": {"in": ["c_big"], "out": ["c_small"]}}, engine)
    assert alone.tier == 3


def test_reaching_the_cushion_outranks_making_fewer_changes(engine):
    """Two changes are taken because one cannot reach the cushion."""
    res = run(planted.CUSHION_ONLY, engine)
    assert ids(res) == planted.CUSHION_ONLY_PLAN
    assert res.tier == 1


def test_cushion_size_does_not_outrank_making_fewer_changes(engine):
    """The counterfactual for the term above: with the cushion unreachable, the
    solver must stop padding and return the smallest set that clears zero."""
    unreachable = {**planted.CUSHION_ONLY, "buffer_cents": 10_000_000}
    res = run(unreachable, engine)
    assert res.plan == [], "nothing is needed to clear zero here"
    assert res.tier == 2


def test_a_change_that_only_protects_the_cushion_is_not_called_load_bearing(engine):
    res = run(planted.CUSHION_ONLY, engine)
    assert res.certificate.irredundant is False
    assert [p.strictly_needed for p in res.plan] == [False, False]
    assert res.certificate.sentence == (
        "Every change here is keeping you above the cushion, not above zero."
    )


def test_gentler_plan_wins_among_equally_small_ones(engine):
    res = run(planted.PAIN_BREAKS_THE_TIE, engine)
    assert ids(res) == ["c_b"], "c_b hurts less for the same money"


def test_ties_are_broken_the_same_way_every_time(engine):
    first = run(planted.IDENTICAL_PAIR, engine)
    assert ids(first) == ["c_a"], "lowest id, deterministically"
    for _ in range(10):
        assert ids(run(planted.IDENTICAL_PAIR, engine)) == ["c_a"]


def test_the_plan_prefers_what_the_user_was_already_shown(engine):
    """Same account, same tie — but the user is already looking at c_b."""
    assert ids(run(planted.IDENTICAL_PAIR, engine)) == ["c_a"]
    assert ids(run(planted.IDENTICAL_PAIR_REMEMBERED, engine)) == ["c_b"]


def test_one_transaction_is_never_changed_two_ways(engine):
    """Taking both would free $120 from a $100 charge and call it clear."""
    res = run(planted.SAME_TXN_TWICE, engine)
    assert len(res.plan) == 1
    assert res.tier == 3
    assert res.shortfall.worst_cents == 4_000


def test_two_pins_on_one_transaction_are_absorbed_not_refused(engine):
    res = run(planted.BOTH_PINNED_SAME_TXN, engine)
    assert ids(res) == ["c_a"], "lower id honoured"
    assert res.meta.excluded_locked_in == ["c_b"]


def test_a_change_that_cannot_be_actioned_in_time_is_not_offered(engine):
    res = run(planted.LEAD_TIME_BOUNDARY, engine)
    assert ids(res) == ["c_ok"], "c_late needs three days' notice and has two"
    assert res.meta.candidates_considered == 1
    assert res.tier == 3, "the charge c_late would have covered still lands"


def test_money_put_off_past_the_horizon_does_not_come_back(engine):
    res = run(planted.DEFER_PAST_HORIZON, engine)
    assert ids(res) == ["c_a"]
    assert res.tier == 1
    assert [b.with_plan_cents for b in res.balances] == [5_000, 0, 0]


def test_the_last_day_of_the_horizon_counts(engine):
    """A dip on the final day is a real dip, not an edge to round away."""
    res = run(planted.PAYDAY_EVE, engine)
    assert ids(res) == ["c_a"]
    assert res.tier == 1
    assert res.balances[-1].with_plan_cents == 0


def test_the_deadline_is_the_first_day_you_go_under(engine):
    """Not the deepest day: money that arrives after you have already bounced is
    no use."""
    res = run(planted.TWO_EQUAL_DIPS, engine)
    assert res.tier == 3
    assert res.shortfall.worst_date == "2026-03-02"
    assert res.external_cash_needed is not None
    assert res.external_cash_needed.by_date == "2026-03-02"


def test_the_gap_is_named_when_nothing_can_close_it(engine):
    res = run(planted.TIER3_EVERYTHING, engine)
    assert res.tier == 3
    assert ids(res) == planted.TIER3_EVERYTHING_PLAN
    assert res.external_cash_needed is not None
    assert res.external_cash_needed.amount_cents == 6_000
    assert res.external_cash_needed.by_date == "2026-03-02"


def test_an_empty_plan_at_tier_three_does_not_claim_the_account_clears(engine):
    res = run(planted.TIER3_NOTHING_AVAILABLE, engine)
    assert res.plan == []
    assert res.tier == 3
    assert res.certificate.irredundant is False
    assert "already clears" not in res.certificate.sentence
    assert res.certificate.sentence.startswith("Nothing here can be changed in time")
    assert "$100.00" in res.certificate.sentence


def test_nothing_to_do_is_said_plainly(engine):
    """An account that needs no help should not be handed a plan."""
    easy = {**planted.GREEDY_FAILS, "opening_balance_cents": 10_000_000}
    res = run(easy, engine)
    assert res.plan == []
    assert res.tier == 1
    assert res.certificate.sentence == "No changes needed. The schedule already clears."
    assert "no changes" in res.verdict.lower()


@pytest.mark.parametrize(
    "case",
    [
        planted.GREEDY_FAILS,
        planted.CUSHION_ONLY,
        planted.TIER3_EVERYTHING,
        planted.SAME_TXN_TWICE,
        planted.IDENTICAL_PAIR,
        planted.LEAD_TIME_BOUNDARY,
        planted.DEFER_PAST_HORIZON,
        planted.TWO_EQUAL_DIPS,
        planted.PAYDAY_EVE,
        planted.BOTH_PINNED_SAME_TXN,
        planted.TIER3_NOTHING_AVAILABLE,
    ],
)
def test_both_engines_agree_on_every_planted_case(case):
    a = run(case, Settings(force_engine="cp-sat")).model_dump()
    b = run(case, Settings(force_engine="brute-force")).model_dump()
    for d in (a, b):
        d["meta"].pop("solver")
        d["meta"].pop("wall_ms")
    assert a == b

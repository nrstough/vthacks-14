"""The proof, and the sentence that renders it.

The certificate is the demo's best moment and its biggest liability: a claim
like "remove any one and you go under on the 24th" is checkable by anyone in the
room. So each number is verified by hand here, and the branch that used to be
vacuously true is pinned specifically.
"""

from __future__ import annotations

from app.schemas import SolveRequest
from app.solver.solve import solve
from app.solver.wording import CUSHION_ONLY_REASON, CUSHION_ONLY_REASON_GAP
from tests.fixtures import planted
from tests.fixtures.scenarios import SCENARIOS


def run(raw: dict):
    return solve(SolveRequest.model_validate(raw))


def test_every_row_is_reported_for_a_change_in_the_plan():
    res = run(SCENARIOS["clears"])
    assert [i.candidate_id for i in res.certificate.per_item] == [p.candidate_id for p in res.plan]


def test_the_numbers_are_the_hand_computed_ones():
    """clears: $200 opening, plan is skip DoorDash, cancel the gym, pay the card
    minimum. Dropping the card minimum is the worst of the three."""
    res = run(SCENARIOS["clears"])
    assert res.tier == 1
    by_id = {i.candidate_id: i for i in res.certificate.per_item}
    assert by_id["c_card_min"].worst_shortfall_cents == 5_326
    assert by_id["c_card_min"].worst_date == "2026-09-24"
    # The plan itself never goes under, so the marginal cost is the whole dip.
    assert by_id["c_card_min"].marginal_cents == 5_326
    assert res.certificate.irredundant is True
    assert "$53.26" in res.certificate.sentence
    assert "Sep 24" in res.certificate.sentence


def test_a_change_that_only_guards_the_cushion_is_not_claimed_as_load_bearing():
    res = run(planted.CUSHION_ONLY)
    assert res.certificate.irredundant is False
    assert all(i.marginal_cents == 0 and i.marginal_days == 0 for i in res.certificate.per_item)
    assert all(p.strictly_needed is False for p in res.plan)
    assert all(p.reason == CUSHION_ONLY_REASON for p in res.plan)


def test_at_tier_three_a_cushion_only_row_talks_about_the_gap():
    """The other half of the wording split, end to end.

    "Here for the cushion, not to clear zero" is true of a plan that clears
    zero. At tier 3 nothing clears zero, so the row says the only thing its zero
    marginals prove: taking it out would not widen the gap. The fixture has to
    pin the change in — see `planted.TIER3_CUSHION_ONLY` for why no freely
    chosen tier 3 plan can contain a zero-marginal row.
    """
    res = run(planted.TIER3_CUSHION_ONLY)
    assert res.tier == 3
    assert res.plan, "the pinned change must reach the plan"
    assert any(p.reason == CUSHION_ONLY_REASON_GAP for p in res.plan)
    assert all(p.reason != CUSHION_ONLY_REASON for p in res.plan)


def test_at_tier_three_the_proof_is_marginal_not_absolute():
    """The old test asked whether the plan-minus-one went below zero. At tier 3
    the plan is already below zero, so that was true of every change and the
    certificate was a tautology printed as a proof."""
    res = run(SCENARIOS["gap"])
    assert res.tier == 3
    assert res.shortfall.worst_cents == 2_762
    for item in res.certificate.per_item:
        # The claim about each row is the DIFFERENCE it makes to a plan that is
        # already underwater, not the absolute depth without it.
        assert item.marginal_cents == item.worst_shortfall_cents - res.shortfall.worst_cents
        assert item.marginal_cents > 0 or item.marginal_days > 0
    assert res.certificate.irredundant is True
    assert "does not clear on its own" in res.certificate.sentence
    assert "$80.00" in res.certificate.sentence


def test_a_change_can_earn_its_place_by_days_alone():
    """Not every load-bearing change makes the deepest day deeper.

    On the gap account, dropping the Amazon order leaves the worst day exactly
    where it was and adds two more days below zero. Judged on depth alone it
    would look like padding; it is not, and the certificate has to say so — the
    fee is charged per day underwater, not per dollar.
    """
    res = run(SCENARIOS["gap"])
    amzn = next(i for i in res.certificate.per_item if i.candidate_id == "c_amzn")
    assert amzn.marginal_cents == 0
    assert amzn.marginal_days == 2
    assert next(p for p in res.plan if p.candidate_id == "c_amzn").strictly_needed is True
    # And the whole certificate turns on it: judged on depth alone, this plan
    # would not be irredundant at all.
    assert res.certificate.irredundant is True
    depth_only = [i for i in res.certificate.per_item if i.marginal_cents > 0]
    assert len(depth_only) < len(res.certificate.per_item)


def test_the_worst_row_named_in_the_sentence_is_the_worst_row():
    for name in SCENARIOS:
        res = run(SCENARIOS[name])
        if not res.certificate.per_item:
            continue
        worst = max(res.certificate.per_item, key=lambda i: i.marginal_cents)
        amount = worst.marginal_cents if res.tier == 3 else worst.worst_shortfall_cents
        cents = f"${amount // 100:,}.{amount % 100:02d}"
        assert cents in res.certificate.sentence, name


def test_an_empty_plan_proves_nothing():
    res = run(planted.TIER3_NOTHING_AVAILABLE)
    assert res.plan == []
    assert res.certificate.per_item == []
    assert res.certificate.irredundant is False


def test_reasons_read_differently_when_the_plan_does_not_clear():
    clears = run(SCENARIOS["clears"])
    assert all("under on" in p.reason for p in clears.plan)
    gap = run(SCENARIOS["gap"])
    assert all("the gap grows to" in p.reason for p in gap.plan)


def test_dropping_a_change_is_worse_than_the_plan_for_every_load_bearing_row():
    for name in SCENARIOS:
        res = run(SCENARIOS[name])
        for item, plan_item in zip(res.certificate.per_item, res.plan):
            assert plan_item.strictly_needed == (
                item.marginal_cents > 0 or item.marginal_days > 0
            ), name


def test_equally_costly_changes_resolve_to_the_first_in_plan_order():
    """When two changes cost exactly the same to drop, which one the sentence
    talks about must come from the plan's order, not from whichever the solver
    happened to visit first."""
    from app.schemas import SolveRequest as Req
    from app.solver.assemble import plan_sort_key
    from app.solver.certificate import build
    from app.solver.dates import day_range
    from app.solver.eligibility import split
    from app.solver.simulate import simulate

    req = Req.model_validate(planted.EQUAL_MARGINALS)
    days = day_range(req.as_of, req.horizon_end)
    chosen = sorted(split(req).free, key=plan_sort_key)
    cert = build(req, chosen, days, simulate(req, chosen, days))

    marginals = [i.marginal_cents for i in cert.per_item]
    assert marginals[0] == marginals[1], "the fixture no longer produces a tie"
    assert cert.worst_item is not None
    assert cert.worst_item.candidate_id == cert.per_item[0].candidate_id
    assert cert.worst_item.candidate_id == "c_a"

"""Every string the user can see.

Someone reading this is already having a bad week. The product's job is to be
exact without being cruel, and to promise nothing it has not checked — so the
banned words are checked everywhere, on every branch, rather than trusted to
review.
"""

from __future__ import annotations

import json
import sys

import pytest

from app.schemas import SolveRequest
from app.solver.solve import Settings, solve
from app.solver.wording import BANNED, OPTIMALITY_CLAIMS
from tests.fixtures import planted
from tests.fixtures.scenarios import SCENARIOS
from tests.gen import instances

ALL_CASES = (
    [(f"scenario:{k}", v) for k, v in SCENARIOS.items()]
    + [(n, getattr(planted, n)) for n in dir(planted) if n.isupper() and isinstance(getattr(planted, n), dict)]
    + [(f"random:{i}", r) for i, r in enumerate(instances(40))]
)


def strings_of(payload) -> list[str]:
    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, dict):
        return [s for v in payload.values() for s in strings_of(v)]
    if isinstance(payload, list):
        return [s for v in payload for s in strings_of(v)]
    return []


def user_facing(raw: dict, settings: Settings | None = None) -> list[str]:
    res = solve(SolveRequest.model_validate(raw), settings)
    body = json.loads(res.model_dump_json())
    # Ids and dates are data, not prose; the strings that matter are the ones
    # written for a person to read.
    #
    # Enumerated deliberately rather than swept over every string in the body.
    # Transaction ids are caller text and may legally carry a banned substring —
    # test_candidates_policy.py uses "guaranteed_1" on purpose — and `detail`
    # quotes the merchant's own descriptor, which is the user's statement line
    # rather than a claim this product is making. `label` is written by us, so it
    # belongs here. That is the distinction: our words, not their data.
    return [
        body["verdict"],
        body["qualifier"],
        body["certificate"]["sentence"],
        *[p["reason"] for p in body["plan"]],
        *[p["label"] for p in body["plan"]],
    ]


@pytest.mark.parametrize("name,raw", ALL_CASES, ids=[c[0] for c in ALL_CASES])
def test_the_banned_words_never_appear(name, raw):
    for text in user_facing(raw):
        lowered = text.lower()
        for word in BANNED:
            assert word not in lowered, f"{name}: {word!r} in {text!r}"


@pytest.mark.parametrize("name,raw", ALL_CASES, ids=[c[0] for c in ALL_CASES])
def test_nothing_is_ever_left_blank(name, raw):
    for text in user_facing(raw):
        assert text.strip(), f"{name}: empty string reached the user"
        assert not text.startswith(" ")
        assert "None" not in text, f"{name}: a null leaked into prose: {text!r}"
        assert "$-" not in text, f"{name}: malformed money in {text!r}"


def test_sufficiency_is_stated_conditionally():
    """"Sufficient under the schedule shown" is true. "You will not overdraft"
    is not, and the difference survives one question from a judge."""
    res = solve(SolveRequest.model_validate(SCENARIOS["clears"]))
    assert "Sufficient under the schedule shown" in res.qualifier


def test_the_verdict_counts_the_changes_in_words():
    res = solve(SolveRequest.model_validate(SCENARIOS["clears"]))
    assert "three changes" in res.verdict
    one = solve(SolveRequest.model_validate(planted.IDENTICAL_PAIR))
    assert "one change" in one.verdict and "one changes" not in one.verdict


def test_the_tier_three_verdict_leads_with_the_number_and_the_date():
    res = solve(SolveRequest.model_validate(SCENARIOS["gap"]))
    assert res.verdict.startswith("You need $27.62 more by Sep 24.")


def test_an_account_with_nothing_to_fix_is_not_handed_a_plan():
    easy = {**SCENARIOS["clears"], "opening_balance_cents": 5_000_000}
    res = solve(SolveRequest.model_validate(easy))
    assert res.plan == []
    assert "no changes" in res.verdict.lower()


def test_both_engines_word_things_identically():
    """Wording drift between engines would surface mid-demo as the plan changing
    its mind about itself."""
    for name, raw in SCENARIOS.items():
        a = user_facing(raw, Settings(force_engine="cp-sat"))
        b = user_facing(raw, Settings(force_engine="brute-force"))
        assert a == b, name


# --------------------------------------------------------------------------
# The certificate's claim about the changes it does not name.
#
# Found by the frontend lane on the demo's own 1:45 beat: with the card minimum
# ruled out, the sentence named one change and said "The rest hold the cushion"
# while three of seven were load-bearing.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "raw"), ALL_CASES, ids=[c[0] for c in ALL_CASES])
def test_the_certificate_never_calls_a_load_bearing_change_optional(name, raw):
    from app.solver.objective import load_bearing

    res = solve(SolveRequest.model_validate(raw))
    carrying = [i for i in res.certificate.per_item if load_bearing(i)]
    if "The rest hold the cushion" in res.certificate.sentence:
        assert len(carrying) == 1, (
            f"{name}: the sentence says the rest hold the cushion, but "
            f"{len(carrying)} changes are load-bearing"
        )


def test_the_demo_beat_says_how_many_changes_are_load_bearing():
    from app.solver.objective import load_bearing
    from tests.fixtures.scenarios import request as make

    raw = make(20_000, 2_500)
    raw["locks"] = {"in": [], "out": ["c_card_min"]}
    res = solve(SolveRequest.model_validate(raw))
    carrying = [i for i in res.certificate.per_item if load_bearing(i)]
    assert len(res.plan) == 7 and len(carrying) == 3
    assert res.certificate.sentence.startswith("Three of these seven changes are load-bearing.")
    assert "The rest hold the cushion" not in res.certificate.sentence


def test_one_load_bearing_change_still_says_the_rest_hold_the_cushion():
    # The original wording is correct in the one case it was written for, and
    # the fix must not lose it.
    for _, raw in ALL_CASES:
        from app.solver.objective import load_bearing

        res = solve(SolveRequest.model_validate(raw))
        carrying = [i for i in res.certificate.per_item if load_bearing(i)]
        if len(carrying) == 1 and len(res.plan) > 1 and res.certificate.per_item and res.tier < 3:
            if not res.certificate.irredundant:
                assert "The rest hold the cushion" in res.certificate.sentence
                return
    pytest.skip("no case in the corpus has exactly one load-bearing change in a larger plan")


def test_a_cushion_only_reason_never_reads_as_not_needed():
    """A change with zero marginals is in the plan for a reason.

    "Not needed to clear zero" is the sentence the left-out list already makes,
    and reading it on a row the solver chose is how the plan reads as padding.
    At tier 3 it is worse than confusing: nothing clears zero there, so the
    claim is about a thing that never happens. Zero marginals prove only that
    removing the change leaves the worst day exactly where it is, and the two
    sentences say that and no more.
    """
    from app.schemas import CertificateItem
    from app.solver.wording import CUSHION_ONLY_REASON, CUSHION_ONLY_REASON_GAP, plan_reason

    item = CertificateItem(
        candidate_id="c_a",
        worst_shortfall_cents=0,
        worst_date=None,
        marginal_cents=0,
        marginal_days=0,
    )
    assert plan_reason(item, plan_clears_zero=True) == CUSHION_ONLY_REASON
    assert plan_reason(item, plan_clears_zero=False) == CUSHION_ONLY_REASON_GAP

    for text in (CUSHION_ONLY_REASON, CUSHION_ONLY_REASON_GAP):
        lowered = text.lower()
        assert "not needed" not in lowered, text
        for word in BANNED:
            assert word not in lowered, text
        for claim in OPTIMALITY_CLAIMS:
            assert claim.lower() not in lowered, text


def test_an_empty_plan_at_tier_three_does_not_claim_the_schedule_clears():
    # Every candidate ruled out: the plan is empty because nothing could be
    # changed, not because nothing needed to be.
    from tests.fixtures.scenarios import CANDIDATES, request as make

    raw = make(6_000, 2_500)
    raw["locks"] = {"in": [], "out": sorted(c["id"] for c in CANDIDATES)}
    res = solve(SolveRequest.model_validate(raw))
    assert res.tier == 3 and res.plan == []
    assert "already clears" not in res.certificate.sentence
    assert res.certificate.sentence.startswith("Nothing here can be changed in time")


# The counterfactual. It must call user_facing(), not rebuild its field list:
# an inline copy passes even when the production sweep stops checking the field,
# which is precisely the failure it is supposed to detect.
@pytest.mark.parametrize("field", ["verdict", "qualifier", "certificate.sentence", "reason", "label"])
def test_removing_a_field_from_the_sweep_would_be_caught(field, monkeypatch):
    poison = "gu" + "aranteed"  # character-split so this file does not trip bundle.test.ts
    real = solve(SolveRequest.model_validate(SCENARIOS["clears"]))

    import app.solver.solve as solve_mod

    def poisoned(req, settings=None):
        res = real.model_copy(deep=True)
        if field == "certificate.sentence":
            res.certificate.sentence = poison
        elif field in ("reason", "label"):
            assert res.plan, "this scenario must produce a plan for the case to mean anything"
            setattr(res.plan[0], field, poison)
        else:
            setattr(res, field, poison)
        return res

    monkeypatch.setattr(solve_mod, "solve", poisoned)
    monkeypatch.setattr(sys.modules[__name__], "solve", poisoned)
    texts = user_facing(SCENARIOS["clears"])
    assert any(word in t.lower() for t in texts for word in BANNED), (
        f"user_facing() does not surface {field}, so the sweep cannot see a banned word there"
    )

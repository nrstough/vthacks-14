"""Every string the user can see.

Someone reading this is already having a bad week. The product's job is to be
exact without being cruel, and to promise nothing it has not checked — so the
banned words are checked everywhere, on every branch, rather than trusted to
review.
"""

from __future__ import annotations

import json

import pytest

from app.schemas import SolveRequest
from app.solver.solve import Settings, solve
from app.solver.wording import BANNED
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
    return [
        body["verdict"],
        body["qualifier"],
        body["certificate"]["sentence"],
        *[p["reason"] for p in body["plan"]],
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

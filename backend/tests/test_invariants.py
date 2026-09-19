"""Properties the response must satisfy on its own terms.

These deliberately import nothing from `app.solver`. Parity against a reference
implementation cannot catch a rule both implementations get wrong the same way,
which is exactly what happened to the one-change-per-transaction rule before it
existed. So the arithmetic here is rebuilt from the request and the response,
using only the contract's description of what the fields mean.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.schemas import SolveRequest
from app.solver.solve import solve
from tests.fixtures.scenarios import SCENARIOS
from tests.gen import instances


def _planted() -> list[tuple[str, dict]]:
    """Every hand-built case, so the properties are checked on exactly the
    instances where the rules are pinned."""
    from tests.fixtures import planted

    return sorted(
        (f"planted:{name}", value)
        for name, value in vars(planted).items()
        if name.isupper() and isinstance(value, dict) and "as_of" in value
    )


CASES = (
    [("scenario:" + k, v) for k, v in SCENARIOS.items()]
    + _planted()
    + [(f"random:{i}", r) for i, r in enumerate(instances(50))]
)


def days_of(req: dict) -> list[str]:
    start = date.fromisoformat(req["as_of"])
    end = date.fromisoformat(req["horizon_end"])
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def walk(req: dict, chosen_ids: set[str], extra: tuple[str, int] | None = None) -> list[int]:
    """End-of-day balances, rebuilt from the request alone."""
    by_id = {c["id"]: c for c in req["candidates"]}
    delta: dict[str, int] = {}
    for t in req["scheduled"]:
        delta[t["date"]] = delta.get(t["date"], 0) + t["amount_cents"]
    for cid in chosen_ids:
        c = by_id[cid]
        delta[c["effective_date"]] = delta.get(c["effective_date"], 0) + c["freed_cents"]
        if c["recharge_date"]:
            delta[c["recharge_date"]] = delta.get(c["recharge_date"], 0) - c["freed_cents"]
    if extra:
        when, amount = extra
        delta[when] = delta.get(when, 0) + amount

    out, running = [], req["opening_balance_cents"]
    for d in days_of(req):
        running += delta.get(d, 0)
        out.append(running)
    return out


@pytest.fixture(scope="module", params=CASES, ids=[c[0] for c in CASES])
def case(request):
    raw = request.param[1]
    return raw, solve(SolveRequest.model_validate(raw)).model_dump()


def test_chart_matches_the_request(case):
    """(a) Both series on the chart are what the request says they are."""
    raw, res = case
    ids = {p["candidate_id"] for p in res["plan"]}
    assert [b["baseline_cents"] for b in res["balances"]] == walk(raw, set())
    assert [b["with_plan_cents"] for b in res["balances"]] == walk(raw, ids)
    assert [b["date"] for b in res["balances"]] == days_of(raw)


def test_reported_shortfall_and_tier_follow_from_the_balances(case):
    """(b) The headline numbers are not asserted, they are derived."""
    raw, res = case
    balances = walk(raw, {p["candidate_id"] for p in res["plan"]})
    worst = max((-b for b in balances if b < 0), default=0)
    assert res["shortfall"]["worst_cents"] == worst
    assert res["shortfall"]["total_cents"] == sum(-b for b in balances if b < 0)

    expected_tier = 3 if worst > 0 else (2 if min(balances) < raw["buffer_cents"] else 1)
    assert res["tier"] == expected_tier


def test_certificate_rows_are_reproducible(case):
    """(c) Every claim about dropping a change can be re-derived."""
    raw, res = case
    ids = {p["candidate_id"] for p in res["plan"]}
    plan_balances = walk(raw, ids)
    plan_worst = max((-b for b in plan_balances if b < 0), default=0)
    plan_days_under = sum(1 for b in plan_balances if b < 0)

    for item in res["certificate"]["per_item"]:
        without = walk(raw, ids - {item["candidate_id"]})
        worst = max((-b for b in without if b < 0), default=0)
        assert item["worst_shortfall_cents"] == worst
        assert item["marginal_cents"] == worst - plan_worst
        assert item["marginal_days"] == sum(1 for b in without if b < 0) - plan_days_under


def test_external_cash_actually_closes_the_gap(case):
    """(d) The tier-3 promise is the useful one; it has to be true."""
    raw, res = case
    if res["tier"] != 3:
        assert res["external_cash_needed"] is None
        return
    need = res["external_cash_needed"]
    assert need is not None
    ids = {p["candidate_id"] for p in res["plan"]}
    with_cash = walk(raw, ids, extra=(need["by_date"], need["amount_cents"]))
    assert min(with_cash) >= 0, "the stated amount, on the stated day, does not clear zero"

    # And it is not padded: a cent less leaves the account under.
    short = walk(raw, ids, extra=(need["by_date"], need["amount_cents"] - 1))
    assert min(short) < 0, "less than the stated amount would have done"


def test_no_transaction_is_changed_two_ways(case):
    """(e) Otherwise a plan can free more from a charge than the charge is worth."""
    raw, res = case
    target_of = {c["id"]: c["target_txn_id"] for c in raw["candidates"]}
    targets = [target_of[p["candidate_id"]] for p in res["plan"]]
    assert len(targets) == len(set(targets))

    # Stronger: what the plan frees from any one transaction never exceeds it.
    freed_of = {c["id"]: c["freed_cents"] for c in raw["candidates"]}
    amount_of = {t["id"]: abs(t["amount_cents"]) for t in raw["scheduled"]}
    for p in res["plan"]:
        assert freed_of[p["candidate_id"]] <= amount_of[target_of[p["candidate_id"]]]


def test_strictly_needed_matches_the_certificate(case):
    """(f) The badge the UI renders means what the certificate says."""
    _, res = case
    per_item = {i["candidate_id"]: i for i in res["certificate"]["per_item"]}
    for p in res["plan"]:
        item = per_item[p["candidate_id"]]
        assert p["strictly_needed"] == (item["marginal_cents"] > 0 or item["marginal_days"] > 0)
    assert res["certificate"]["irredundant"] == (
        bool(res["plan"]) and all(p["strictly_needed"] for p in res["plan"])
    )


def test_the_plan_is_described_consistently_everywhere(case):
    """(g) Plan, chart markers and certificate name the same set of changes."""
    _, res = case
    ids = [p["candidate_id"] for p in res["plan"]]
    assert len(ids) == len(set(ids))
    assert [i["candidate_id"] for i in res["certificate"]["per_item"]] == ids
    marked = [cid for b in res["balances"] for cid in b["changes_here"]]
    assert sorted(marked) == sorted(ids)
    by_date = {p["candidate_id"]: p["date"] for p in res["plan"]}
    for b in res["balances"]:
        for cid in b["changes_here"]:
            assert by_date[cid] == b["date"]


def test_plan_is_ordered_by_the_day_you_must_act(case):
    _, res = case
    keys = [(p["date"], p["candidate_id"]) for p in res["plan"]]
    assert keys == sorted(keys)


def test_paydays_are_marked(case):
    raw, res = case
    paydays = {t["date"] for t in raw["scheduled"] if t["kind"] == "income"}
    for b in res["balances"]:
        assert b["is_payday"] == (b["date"] in paydays)

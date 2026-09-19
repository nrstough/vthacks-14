"""The product generation profile and POST /api/accounts/sample.

The test profile in app/accounts/profiles.py is pinned byte-for-byte elsewhere.
This is the other one: the account a judge is actually shown. Its requirements
are behavioural rather than exact, so each is asserted over many seeds rather
than one, and each is written so that removing the behaviour fails it.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.accounts.product import PAYROLL, sample_account
from app.candidates import generate
from app.main import create_app
from app.schemas import CENTS_ABS, MAX_SCHED, CandidatesRequest, SolveRequest
from app.solver.solve import solve

SEEDS = range(120)


def window_of(account: dict) -> dict:
    return {k: account[k] for k in ("as_of", "horizon_end", "scheduled")}


def paydays(account: dict) -> list[dict]:
    return [t for t in account["scheduled"] if t["kind"] == "income" and t["amount_cents"] > 0]


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(None))


# ---- the shape the schema demands ----


@pytest.mark.parametrize("seed", SEEDS)
def test_every_generated_account_is_a_valid_request(seed):
    account = sample_account(seed=seed)
    CandidatesRequest.model_validate(window_of(account))
    assert len(account["scheduled"]) <= MAX_SCHED
    assert abs(account["opening_balance_cents"]) <= CENTS_ABS


@pytest.mark.parametrize("seed", SEEDS)
def test_no_float_ever_touches_money(seed):
    account = sample_account(seed=seed)
    for value in (account["opening_balance_cents"], account["buffer_cents"]):
        assert type(value) is int
    for txn in account["scheduled"]:
        # `type is int` rather than isinstance: bool is a subclass of int and
        # would slip through, and so would anything that merely rounds cleanly.
        assert type(txn["amount_cents"]) is int, txn


@pytest.mark.parametrize("seed", SEEDS)
def test_ids_are_unique_and_match_the_contract(seed):
    ids = [t["id"] for t in sample_account(seed=seed)["scheduled"]]
    assert len(ids) == len(set(ids))


# ---- the behaviour that makes it a product account ----


def test_pay_never_lands_on_a_weekend():
    """Payroll skips the weekend. Remove _business_day and this fails."""
    offenders = [
        (seed, t["date"])
        for seed in SEEDS
        for t in paydays(sample_account(seed=seed))
        if date.fromisoformat(t["date"]).weekday() >= 5
    ]
    assert offenders == []


def test_pay_is_not_on_exact_multiples_of_the_cadence():
    """Jitter has to be real jitter.

    A fixed cadence produces one interval length for every account. If the
    business-day adjustment and the drift are both removed, the set below
    collapses to a single value and this fails.
    """
    intervals: set[int] = set()
    for seed in SEEDS:
        days = sorted(date.fromisoformat(t["date"]) for t in paydays(sample_account(seed=seed)))
        intervals.update((b - a).days for a, b in zip(days, days[1:]))
    assert len(intervals) > 1, intervals


def test_amounts_are_heavy_tailed_rather_than_uniform():
    """The tail has to be visible in the data, not just in the code.

    A uniform draw over each merchant's own range cannot put the 99th percentile
    far above the median. The banded draw can, and does.
    """
    amounts = sorted(
        -t["amount_cents"]
        for seed in SEEDS
        for t in sample_account(seed=seed)["scheduled"]
        if t["amount_cents"] < 0
    )
    median = amounts[len(amounts) // 2]
    p99 = amounts[int(len(amounts) * 0.99)]
    assert p99 > median * 4, f"p99={p99} median={median}"


@pytest.mark.parametrize("seed", SEEDS)
def test_there_is_always_a_dip_before_the_first_payday(seed):
    """The whole point: an account with nothing to solve is not a demo.

    Counted strictly before the first payday, because the payroll credit lands on
    that day and would cancel the dip we planted.
    """
    account = sample_account(seed=seed)
    first = min(t["date"] for t in paydays(account))
    before = [t for t in account["scheduled"] if t["date"] < first and t["amount_cents"] < 0]

    # Without this the test is vacuous. Four seeds in 300 drew every charge on or
    # after the first payday; the loop below then walked an empty range and
    # asserted `opening < buffer` against an opening the generator had already
    # clamped to 0. It passed, and the account it passed on had nothing to solve.
    assert before, f"seed {seed}: no charges before the first payday, so no dip is possible"

    balance = account["opening_balance_cents"]
    trough = balance
    for txn in sorted(account["scheduled"], key=lambda t: t["date"]):
        if txn["date"] >= first:
            break
        balance += txn["amount_cents"]
        trough = min(trough, balance)
    assert trough < account["buffer_cents"], f"seed {seed}: trough {trough}"


@pytest.mark.parametrize("seed", SEEDS)
def test_every_account_reaches_a_payday(seed):
    assert paydays(sample_account(seed=seed)), f"seed {seed} has no income"
    assert all(t["description"] == PAYROLL for t in paydays(sample_account(seed=seed)))


def test_the_same_seed_gives_the_same_account():
    assert sample_account(seed=99) == sample_account(seed=99)
    assert sample_account(seed=99) != sample_account(seed=100)


# ---- it has to survive the rest of the pipeline ----


@pytest.mark.parametrize("seed", list(SEEDS)[:40])
def test_a_generated_account_solves_end_to_end(seed):
    account = sample_account(seed=seed)
    candidates = generate(CandidatesRequest.model_validate(window_of(account)))
    body = {
        "as_of": account["as_of"],
        "horizon_end": account["horizon_end"],
        "opening_balance_cents": account["opening_balance_cents"],
        "buffer_cents": account["buffer_cents"],
        "scheduled": account["scheduled"],
        "candidates": [c.model_dump() for c in candidates.candidates],
        "locks": {"in": [], "out": []},
        "previous_plan": [],
    }
    res = solve(SolveRequest.model_validate(body))
    assert res.tier in (1, 2, 3)


@pytest.mark.parametrize("seed", list(SEEDS)[:25])
def test_locking_a_returned_candidate_does_not_422(seed):
    """The client rule the contract documents, exercised on generated data."""
    account = sample_account(seed=seed)
    candidates = generate(CandidatesRequest.model_validate(window_of(account)))
    if not candidates.candidates:
        pytest.skip("no candidates for this seed")
    body = {
        "as_of": account["as_of"],
        "horizon_end": account["horizon_end"],
        "opening_balance_cents": account["opening_balance_cents"],
        "buffer_cents": account["buffer_cents"],
        "scheduled": account["scheduled"],
        "candidates": [c.model_dump() for c in candidates.candidates],
        "locks": {"in": [candidates.candidates[0].id], "out": []},
        "previous_plan": [],
    }
    solve(SolveRequest.model_validate(body))


# ---- the endpoint ----


def test_the_endpoint_answers_and_is_not_shadowed_by_the_static_mount(client):
    """A route registered below the StaticFiles mount answers 405, silently.

    main.py says so in a comment; nothing tested it for a fourth route until now.
    """
    r = client.post("/api/accounts/sample", json={})
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "modelled"


def test_the_seed_comes_back_so_the_account_can_be_regenerated(client):
    first = client.post("/api/accounts/sample", json={}).json()
    again = client.post("/api/accounts/sample", json={"seed": first["seed"]}).json()
    assert again == first


def test_the_response_says_it_is_modelled(client):
    """Not decoration. Nothing downstream may present this as a bank's data."""
    body = client.post("/api/accounts/sample", json={"seed": 1}).json()
    assert body["source"] == "modelled"


def test_the_horizon_is_bounded(client):
    assert client.post("/api/accounts/sample", json={"horizon_days": 13}).status_code == 422
    assert client.post("/api/accounts/sample", json={"horizon_days": 46}).status_code == 422
    assert client.post("/api/accounts/sample", json={"horizon_days": 45}).status_code == 200


def test_an_unknown_field_is_refused(client):
    assert client.post("/api/accounts/sample", json={"nope": 1}).status_code == 422


def test_the_sample_feeds_the_other_two_endpoints_unchanged(client):
    """The response shape is the contract's, so no translation step exists to
    drift out of step."""
    account = client.post("/api/accounts/sample", json={"seed": 5}).json()
    cands = client.post(
        "/api/candidates",
        json={k: account[k] for k in ("as_of", "horizon_end", "scheduled")},
    )
    assert cands.status_code == 200, cands.text
    solved = client.post(
        "/api/solve",
        json={
            "as_of": account["as_of"],
            "horizon_end": account["horizon_end"],
            "opening_balance_cents": account["opening_balance_cents"],
            "buffer_cents": account["buffer_cents"],
            "scheduled": account["scheduled"],
            "candidates": cands.json()["candidates"],
            "locks": {"in": [], "out": []},
        },
    )
    assert solved.status_code == 200, solved.text
    assert solved.json()["tier"] in (1, 2, 3)


def test_most_seeds_produce_a_plan_worth_looking_at():
    """The dip test proves a dip exists; it does not prove one can be fixed.

    A tier-3 empty plan is a legitimate and important outcome — it is the `gap`
    scenario, and naming the shortfall honestly is half this product's point. But
    a generator that produced them often would be a poor demo, and the dip test
    alone cannot see the difference. Measured at the time of writing: 21 of 300.
    """
    solved = 0
    empty = []
    for seed in range(60):
        account = sample_account(seed=seed)
        candidates = generate(CandidatesRequest.model_validate(window_of(account)))
        body = {
            **{k: account[k] for k in
               ("as_of", "horizon_end", "opening_balance_cents", "buffer_cents", "scheduled")},
            "candidates": [c.model_dump() for c in candidates.candidates],
            "locks": {"in": [], "out": []},
            "previous_plan": [],
        }
        res = solve(SolveRequest.model_validate(body))
        if res.plan:
            solved += 1
        else:
            empty.append((seed, res.tier))
            # An empty plan is only honest at tier 3. At tier 1 or 2 it would mean
            # the account never needed anything, which the dip rules out.
            assert res.tier == 3, f"seed {seed}: empty plan at tier {res.tier}"
    assert solved >= 48, f"only {solved}/60 seeds produced a plan; empty: {empty}"


# ---- as_of: the field the contract documents and nothing exercised ----
#
# Every endpoint test above sends {}, {"seed": n} or {"horizon_days": n}. Not one
# passed as_of, so a validator calling a one-argument helper with two arguments
# shipped as a hard 500 on a documented field, under 1979 passing tests.


def test_an_explicit_as_of_is_honoured(client):
    body = client.post("/api/accounts/sample", json={"seed": 3, "as_of": "2026-03-02"}).json()
    assert body["as_of"] == "2026-03-02"
    assert body["horizon_end"] == "2026-03-31"
    assert all(t["date"] >= "2026-03-02" for t in body["scheduled"])


def test_as_of_changes_the_account(client):
    a = client.post("/api/accounts/sample", json={"seed": 3, "as_of": "2026-03-02"}).json()
    b = client.post("/api/accounts/sample", json={"seed": 3, "as_of": "2026-07-06"}).json()
    assert a["scheduled"][0]["date"] != b["scheduled"][0]["date"]


def test_a_malformed_as_of_is_a_422_not_a_500(client):
    for bad in ["20260919", "2026-9-19", "not a date", "2026-13-01", ""]:
        r = client.post("/api/accounts/sample", json={"seed": 1, "as_of": bad})
        assert r.status_code == 422, f"{bad!r} gave {r.status_code}"


def test_as_of_and_a_seed_together_still_reproduce(client):
    args = {"seed": 77, "as_of": "2026-05-04"}
    assert client.post("/api/accounts/sample", json=args).json() == \
           client.post("/api/accounts/sample", json=args).json()


def test_an_as_of_on_a_weekend_still_puts_pay_on_a_business_day(client):
    # 2026-05-02 is a Saturday.
    body = client.post("/api/accounts/sample", json={"seed": 8, "as_of": "2026-05-02"}).json()
    pay = [t for t in body["scheduled"] if t["kind"] == "income" and t["amount_cents"] > 0]
    assert pay
    assert all(date.fromisoformat(t["date"]).weekday() < 5 for t in pay)


def test_an_as_of_with_no_room_for_the_horizon_is_422_not_500(client):
    """9999-12-31 is a valid date. Adding the horizon to it is an OverflowError,
    which reaches the client as an unhandled 500 rather than a refused request."""
    for bad in ["9999-12-31", "9999-12-01"]:
        r = client.post("/api/accounts/sample", json={"seed": 1, "as_of": bad})
        assert r.status_code == 422, f"{bad} gave {r.status_code}"


def test_a_far_future_as_of_that_does_fit_still_works(client):
    r = client.post("/api/accounts/sample", json={"seed": 1, "as_of": "9999-10-01"})
    assert r.status_code == 200, r.text


def test_the_earliest_dates_are_accepted(client):
    r = client.post("/api/accounts/sample", json={"seed": 1, "as_of": "0001-01-01"})
    assert r.status_code == 200, r.text

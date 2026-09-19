"""Tier boundaries and the tier-3 promise.

The boundaries are exact to the cent because that is where a person's experience
changes: at the cushion they are fine, a cent below it they are one surprise
away, a cent below zero they are paying a fee.
"""

from __future__ import annotations

import pytest

from app.schemas import SolveRequest
from app.solver.solve import solve
from tests.fixtures.planted import req, txn


def tier_for(opening: int, buffer: int = 5_000) -> int:
    """One charge, no changes available: the tier is a pure function of where
    the balance lands."""
    raw = req(days_end="02", opening=opening, buffer=buffer,
              scheduled=[txn("t_1", "02", -10_000)], candidates=[])
    return solve(SolveRequest.model_validate(raw)).tier


@pytest.mark.parametrize(
    "opening,expected,why",
    [
        (15_001, 1, "a cent above the cushion"),
        (15_000, 1, "exactly the cushion still counts as reaching it"),
        (14_999, 2, "a cent short of the cushion"),
        (10_001, 2, "barely positive"),
        (10_000, 2, "exactly zero is not below zero"),
        (9_999, 3, "a cent below zero is an overdraft"),
    ],
)
def test_tier_boundaries_are_exact_to_the_cent(opening, expected, why):
    assert tier_for(opening) == expected, why


def test_a_cushion_of_zero_collapses_tier_two():
    """With no cushion asked for, reaching zero is reaching the cushion."""
    raw = req(days_end="02", opening=10_000, buffer=0,
              scheduled=[txn("t_1", "02", -10_000)], candidates=[])
    assert solve(SolveRequest.model_validate(raw)).tier == 1


def test_external_cash_is_only_offered_when_it_is_needed():
    for opening, expects_cash in [(15_000, False), (12_000, False), (5_000, True)]:
        raw = req(days_end="02", opening=opening, buffer=5_000,
                  scheduled=[txn("t_1", "02", -10_000)], candidates=[])
        res = solve(SolveRequest.model_validate(raw))
        assert (res.external_cash_needed is not None) is expects_cash


def test_the_amount_asked_for_is_exactly_what_is_missing():
    raw = req(days_end="02", opening=5_000, buffer=0,
              scheduled=[txn("t_1", "02", -10_000)], candidates=[])
    res = solve(SolveRequest.model_validate(raw))
    assert res.external_cash_needed is not None
    assert res.external_cash_needed.amount_cents == 5_000
    assert res.external_cash_needed.by_date == "2026-03-02"
    assert res.shortfall.worst_cents == 5_000
    assert res.shortfall.total_cents == 5_000


def test_total_shortfall_adds_up_every_day_underwater():
    """Worst is the deepest day; total is the whole hole, which is what a run of
    fees is actually priced on."""
    raw = req(days_end="04", opening=0, buffer=0,
              scheduled=[txn("t_1", "02", -1_000), txn("t_2", "03", -1_000)], candidates=[])
    res = solve(SolveRequest.model_validate(raw))
    # balances: 0 | -10.00 | -20.00 | -20.00
    assert res.shortfall.worst_cents == 2_000
    assert res.shortfall.total_cents == 1_000 + 2_000 + 2_000


def test_the_deadline_is_the_first_breach_not_the_worst_one():
    raw = req(days_end="04", opening=0, buffer=0,
              scheduled=[txn("t_1", "02", -1_000), txn("t_2", "04", -9_000)], candidates=[])
    res = solve(SolveRequest.model_validate(raw))
    assert res.external_cash_needed is not None
    assert res.external_cash_needed.by_date == "2026-03-02"
    assert res.shortfall.worst_date == "2026-03-04"
    assert res.external_cash_needed.amount_cents == 10_000

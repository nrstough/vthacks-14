"""Test-side account helpers.

The merchant table and the generation primitives now live in
`app/accounts/` — `deploy.sh` ships `backend/app/` and nothing else from the
backend, so the product could not reach them here. They are re-exported below so
the eight call sites in this suite, and the subprocess source string in
`test_candidates_policy.py`, keep working unchanged.

What stays here is test-harness shape rather than product shape:
`opening_for_mixed_tiers` parks a balance near the do-nothing trough so tiers 2
and 3 get exercised, and `solve_request` fabricates `locks`/`previous_plan`
defaults and a test cushion. Neither belongs in a tree that gets deployed.

Generation is byte-identical across the move; `test_accounts_golden.py` proves it.
"""

from __future__ import annotations

import random
from typing import Any

from app.accounts.merchants import MERCHANTS
from app.accounts.profiles import window, windows

__all__ = ["MERCHANTS", "window", "windows", "opening_for_mixed_tiers", "solve_request"]


def opening_for_mixed_tiers(win: dict[str, Any], rng: random.Random | None = None) -> int:
    """A balance near the do-nothing trough, so tiers 2 and 3 get exercised.

    Clamped to the schema's input bound: a horizon full of charges at the cap
    puts the raw trough far outside what a request may carry, and an unclamped
    figure would 422 on the balance before the candidates were looked at.
    """
    from app.schemas import CENTS_ABS

    rng = rng or random.Random(0)
    delta: dict[str, int] = {}
    for t in win["scheduled"]:
        delta[t["date"]] = delta.get(t["date"], 0) + t["amount_cents"]
    running = 0
    trough = 0
    for day in sorted(delta):
        if win["as_of"] <= day <= win["horizon_end"]:
            running += delta[day]
            trough = min(trough, running)
    return max(-CENTS_ABS, min(CENTS_ABS, -trough + rng.randrange(-20_000, 20_000)))


def solve_request(
    win: dict[str, Any],
    candidates: list[dict[str, Any]],
    opening: int | None = None,
    buffer_cents: int = 2500,
    locks: dict[str, list[str]] | None = None,
    previous_plan: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "as_of": win["as_of"],
        "horizon_end": win["horizon_end"],
        "opening_balance_cents": opening if opening is not None else opening_for_mixed_tiers(win),
        "buffer_cents": buffer_cents,
        "scheduled": win["scheduled"],
        "candidates": candidates,
        "locks": locks or {"in": [], "out": []},
        "previous_plan": previous_plan or [],
    }

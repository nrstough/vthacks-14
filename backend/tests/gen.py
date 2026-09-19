"""Random but schema-valid requests, for differential testing.

Seeded, so a failure is reproducible from its index alone. The shapes it
deliberately produces are the ones that have historically diverged between two
implementations of the same rules: several candidates on one transaction, two
changes landing on the same day, deferrals that pay back after the horizon ends,
pinned changes that have missed their lead time, and a previously-shown plan
containing an id that is no longer on offer.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

KINDS = ("bill", "discretionary")
ACTIONS = ("skip", "downgrade", "cancel")


def instance(rng: random.Random) -> dict[str, Any]:
    as_of = date(2026, 1, 1) + timedelta(days=rng.randrange(0, 365))
    horizon = rng.randrange(7, 46)
    horizon_end = as_of + timedelta(days=horizon - 1)

    def day(lo: int = 0, hi: int | None = None) -> date:
        return as_of + timedelta(days=rng.randrange(lo, horizon if hi is None else hi))

    scheduled: list[dict[str, Any]] = []
    # Income, roughly fortnightly, so there is a payday to plan towards.
    pay = rng.randrange(0, min(14, horizon))
    while pay < horizon:
        scheduled.append({
            "id": f"t_{len(scheduled):02d}",
            "date": (as_of + timedelta(days=pay)).isoformat(),
            "description": "PAYROLL",
            "amount_cents": rng.randrange(40_000, 160_000),
            "kind": "income",
            "recurring": True,
        })
        pay += rng.randrange(13, 16)

    for _ in range(rng.randrange(4, 18)):
        scheduled.append({
            "id": f"t_{len(scheduled):02d}",
            "date": day().isoformat(),
            "description": rng.choice(["KROGER #382", "SHELL OIL", "NETFLIX.COM", "DOORDASH*X"]),
            "amount_cents": -rng.randrange(500, 40_000),
            "kind": rng.choice(KINDS),
            "recurring": rng.random() < 0.4,
        })
    # A couple of rows outside the horizon: legal, and the solver must ignore them.
    for _ in range(rng.randrange(0, 3)):
        scheduled.append({
            "id": f"t_{len(scheduled):02d}",
            "date": (horizon_end + timedelta(days=rng.randrange(1, 20))).isoformat(),
            "description": "LATER",
            "amount_cents": -rng.randrange(500, 20_000),
            "kind": "bill",
            "recurring": False,
        })

    outflows = [t for t in scheduled if t["amount_cents"] < 0 and t["date"] <= horizon_end.isoformat()]
    candidates: list[dict[str, Any]] = []
    for i in range(rng.randrange(4, 15)):
        # Targets are drawn with replacement, so one transaction routinely has
        # two or three competing changes and the one-per-transaction rule bites.
        target = rng.choice(outflows)
        effective = day()
        action = rng.choice(ACTIONS) if rng.random() > 0.25 else "defer"
        recharge = None
        if action == "defer":
            # Sometimes lands past the horizon, where the money never comes back
            # inside the window being planned.
            recharge = effective + timedelta(days=rng.randrange(1, horizon + 10))
        candidates.append({
            "id": f"c_{i:02d}",
            "label": f"Change {i}",
            "detail": target["description"],
            "action": action,
            "target_txn_id": target["id"],
            "freed_cents": rng.randrange(0, abs(target["amount_cents"]) + 1),
            "effective_date": effective.isoformat(),
            "recharge_date": recharge.isoformat() if recharge else None,
            "lead_time_days": rng.randrange(0, 6),
            "pain": rng.randrange(1, 6),
        })

    ids = [c["id"] for c in candidates]
    rng.shuffle(ids)
    n_in = rng.randrange(0, 3)
    n_out = rng.randrange(0, 3)
    locks = {"in": sorted(ids[:n_in]), "out": sorted(ids[n_in : n_in + n_out])}

    previous = sorted(rng.sample(ids, rng.randrange(0, min(4, len(ids)) + 1)))
    if rng.random() < 0.5:
        # An id the user was shown before that is no longer on offer. It still
        # counts against hysteresis, as a constant both engines must agree on.
        previous = sorted([*previous, "c_gone"])

    opening = _opening_for_mixed_tiers(rng, scheduled, as_of, horizon)
    return {
        "as_of": as_of.isoformat(),
        "horizon_end": horizon_end.isoformat(),
        "opening_balance_cents": opening,
        "buffer_cents": rng.choice([0, 2500, 10_000]),
        "scheduled": scheduled,
        "candidates": candidates,
        "locks": locks,
        "previous_plan": previous,
    }


def _opening_for_mixed_tiers(
    rng: random.Random, scheduled: list[dict[str, Any]], as_of: date, horizon: int
) -> int:
    """Pick a starting balance near the do-nothing trough.

    Left uniform, almost every instance would be comfortably solvable and the
    tier-2 and tier-3 branches would go untested.
    """
    delta: dict[str, int] = {}
    for t in scheduled:
        delta[t["date"]] = delta.get(t["date"], 0) + t["amount_cents"]
    running = 0
    trough = 0
    for i in range(horizon):
        running += delta.get((as_of + timedelta(days=i)).isoformat(), 0)
        trough = min(trough, running)
    return -trough + rng.randrange(-20_000, 20_000)


def instances(n: int, seed: int = 20260919) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    return [instance(rng) for _ in range(n)]

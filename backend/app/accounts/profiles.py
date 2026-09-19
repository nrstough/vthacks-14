"""Generation profiles over the merchant table.

`window()` is the ORIGINAL test profile, moved here verbatim from
`backend/tests/fixtures/accounts.py`. It is consumed through the fixture shim by
six property tests in `test_candidates_policy.py`, by the whole of
`test_candidates_roundtrip.py`, and by the perf comparison that runs both solver
engines over every generated account.

Its RNG call sequence is a contract, pinned by
`backend/tests/test_accounts_golden.py`. Do not reorder the draws, do not hoist
the `rng.random()` probability gates, do not change the default seed, and do not
touch `MERCHANTS`. Any of those resamples all 300 accounts, and every one of
those tests would keep passing while testing something else.

The product profile is deliberately a SEPARATE function rather than a flag on
this one. The product needs business-day pay with jitter, heavy-tailed amounts
and a planted dip; the test profile must not move. One table, two declared
profiles.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

from app.accounts.merchants import MERCHANTS

def window(rng: random.Random) -> dict[str, Any]:
    as_of = date(2026, 1, 1) + timedelta(days=rng.randrange(0, 365))
    span = rng.randrange(14, 46)
    horizon_end = as_of + timedelta(days=span - 1)
    scheduled: list[dict[str, Any]] = []

    def add(day: date, description: str, cents: int, kind: str, recurring: bool) -> None:
        scheduled.append({
            "id": f"t_{len(scheduled):03d}",
            "date": day.isoformat(),
            "description": description,
            "amount_cents": cents,
            "kind": kind,
            "recurring": recurring,
        })

    cadence = rng.choice((7, 14))
    payday = rng.randrange(0, cadence)
    while payday < span:
        add(as_of + timedelta(days=payday), "HARRIS TEETER PAYROLL",
            rng.randrange(40_000, 160_000), "income", True)
        payday += cadence

    for _ in range(rng.randrange(4, 25)):
        description, kind, recurring, low, high = rng.choice(MERCHANTS)
        add(as_of + timedelta(days=rng.randrange(0, span)), description,
            -rng.randrange(low, high + 1), kind, recurring)

    # A clawback after a charge: an income row that is not a payday.
    if rng.random() < 0.3:
        add(as_of + timedelta(days=rng.randrange(0, span)), "PAYROLL ADJUSTMENT",
            -rng.randrange(1_000, 20_000), "income", False)

    # Legal rows the generator must ignore.
    if rng.random() < 0.5:
        add(as_of - timedelta(days=rng.randrange(1, 30)), "KROGER #382", -4_000,
            "discretionary", False)
    if rng.random() < 0.5:
        add(horizon_end + timedelta(days=rng.randrange(1, 30)), "NETFLIX.COM", -2_299,
            "bill", True)

    # Two charges alike in everything the label can see.
    if rng.random() < 0.25:
        twin_day = as_of + timedelta(days=rng.randrange(0, span))
        for _ in range(2):
            add(twin_day, "KROGER #382", -5_000, "discretionary", False)

    rng.shuffle(scheduled)
    for i, row in enumerate(scheduled):
        row["id"] = f"t_{i:03d}"

    return {"as_of": as_of.isoformat(), "horizon_end": horizon_end.isoformat(), "scheduled": scheduled}


def windows(n: int, seed: int = 20260919) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    return [window(rng) for _ in range(n)]

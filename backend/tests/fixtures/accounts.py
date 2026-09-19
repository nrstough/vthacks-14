"""Realistic accounts for the candidate generator.

`gen.py` produces schema-valid noise to compare two solvers on. This produces
something a person would recognise: real statement descriptors, a payroll
cadence, and the shapes that have caused trouble — a clawback dated after a
charge, rows just outside the window, and two charges identical in everything
but their id.

Seeded, so a failure is reproducible from its index.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

# (description, kind, recurring, low cents, high cents). Covers every changeable
# category, every protected one, both flavours of unrecognised row, and the
# strings that classified wrongly during review.
MERCHANTS: tuple[tuple[str, str, bool, int, int], ...] = (
    ("DOORDASH*CHIPOTLE", "discretionary", False, 1200, 4800),
    ("UBER EATS", "discretionary", False, 1500, 5200),
    ("STARBUCKS #0714", "discretionary", False, 400, 1200),
    ("KROGER #382", "discretionary", False, 3500, 12000),
    ("HARRIS TEETER 0291", "discretionary", False, 2800, 9500),
    ("SAM'S CLUB #6314", "discretionary", False, 4000, 15000),
    ("SHELL OIL 57442891", "discretionary", False, 2500, 7500),
    ("WAWA 8832", "discretionary", False, 2000, 6000),
    ("WATER ST TAVERN", "discretionary", False, 1800, 7000),
    ("PANERA BREAD #601", "discretionary", False, 900, 2600),
    ("NETFLIX.COM", "bill", True, 1599, 2299),
    ("SPOTIFY USA", "bill", True, 1199, 1699),
    ("PLANET FIT CLUB FEES", "bill", True, 1000, 4999),
    ("CORE POWER YOGA", "bill", True, 8900, 15900),
    ("ADOBE *CREATIVE CLD", "bill", True, 999, 5999),
    ("AMZN MKTP US*2K41Z", "discretionary", False, 1500, 9000),
    ("TARGET 00021456", "discretionary", False, 2000, 11000),
    ("UBER TRIP 4A2K", "discretionary", False, 800, 3400),
    ("AMC ONLINE 4421", "discretionary", False, 1400, 4200),
    ("GREAT CLIPS #2201", "discretionary", False, 1800, 4000),
    # Protected.
    ("CHASE CARD EPAY 8812", "bill", True, 5000, 40000),
    ("MARKET ST PROPERTIES LLC", "bill", True, 80000, 160000),
    ("DOMINION ENERGY", "bill", True, 4000, 18000),
    ("VERIZON WIRELESS PMT", "bill", True, 4500, 11000),
    ("GEICO INSURANCE PMT", "bill", True, 6000, 18000),
    ("NELNET STUDENT LOAN", "bill", True, 9000, 30000),
    ("CVS PHARMACY #4417", "discretionary", False, 800, 6000),
    ("VIRGINIA TECH BURSAR", "bill", True, 50000, 200000),
    ("ZELLE TO J SMITH", "discretionary", False, 2000, 15000),
    ("ATM WITHDRAWAL 0042", "discretionary", False, 2000, 20000),
    ("GAP INSURANCE PREMIUM", "bill", True, 1500, 4500),
    ("TARGET OPTICAL 118", "discretionary", False, 5000, 25000),
    # Unrecognised: one the caller calls discretionary, one it does not.
    ("BLACKSBURG SUNDRIES 77", "discretionary", False, 1200, 6500),
    ("QUARRY LN ASSOC 4412", "bill", True, 3000, 12000),
    ("CAFÉ MÉLANGE ☕", "discretionary", False, 600, 2200),
    ("GUARANTEED AUTO PROTECTION", "discretionary", False, 2500, 9000),
)


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

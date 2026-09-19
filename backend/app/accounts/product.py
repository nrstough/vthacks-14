"""The product generation profile: an account a person would recognise.

Deliberately separate from `window()` in `profiles.py`. That one is the test
profile, its RNG call sequence is pinned by `test_accounts_golden.py`, and six
property tests plus the cross-engine perf comparison are run against its output.
Adding a flag to it would have put all of that at risk for a cosmetic reason.

What this profile does that the test profile does not:

  * pay lands on a business day, with jitter, rather than on exact multiples of
    the cadence — real payroll skips weekends and drifts by a day
  * amounts are heavy-tailed rather than uniform: most charges are small, a few
    are not, which is what makes a plan interesting to look at
  * a dip before the first payday is planted on purpose, so there is always
    something to solve

No float touches money. The heavy tail is drawn by picking a magnitude band and
then drawing uniformly inside it, which is integer arithmetic throughout; a
lognormal would have meant multiplying cents by a float and rounding, and this
project does not do that anywhere.

Every account this produces is marked `source="modelled"` at the response
boundary. It is not bank data and must never be presented as any.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

from app.accounts.merchants import MERCHANTS
from app.schemas import CENTS_ABS, MAX_SCHED

# Bands and their weights. Most charges are small; the tail is thin and real.
# Expressed as (weight, low multiplier pct, high multiplier pct) applied to the
# merchant's own range, so a grocery run stays a grocery run and only its size
# moves. Integer percentages, floored — no float, ever.
_BANDS: tuple[tuple[int, int, int], ...] = (
    (70, 60, 110),    # the ordinary week
    (22, 110, 180),
    (7, 180, 320),
    (1, 320, 600),    # the one that ruins a month
)
_WEIGHT_TOTAL = sum(b[0] for b in _BANDS)

# A payday needs room in front of it for the dip to be visible.
_MIN_DAYS_TO_FIRST_PAY = 6

PAYROLL = "HARRIS TEETER PAYROLL"


def _business_day(day: date, rng: random.Random) -> date:
    """Move a payday off the weekend, the way payroll actually does.

    Friday when it would land on Saturday or Sunday, plus an occasional day of
    drift. Never forward past the weekend: money arriving late is a different
    product problem and not one this profile is modelling.
    """
    if day.weekday() == 5:      # Saturday
        day -= timedelta(days=1)
    elif day.weekday() == 6:    # Sunday
        day -= timedelta(days=2)
    elif rng.random() < 0.15:
        day -= timedelta(days=1)
        if day.weekday() >= 5:
            day -= timedelta(days=day.weekday() - 4)
    return day


def _heavy_tailed(low: int, high: int, rng: random.Random) -> int:
    """A charge in cents, drawn from a banded distribution. Integers only."""
    roll = rng.randrange(_WEIGHT_TOTAL)
    for weight, lo_pct, hi_pct in _BANDS:
        if roll < weight:
            base = rng.randrange(low, high + 1)
            return max(1, base * rng.randrange(lo_pct, hi_pct + 1) // 100)
        roll -= weight
    raise AssertionError("bands do not sum to their own total")


def sample_account(
    seed: int | None = None,
    as_of: date | None = None,
    horizon_days: int = 30,
) -> dict[str, Any]:
    """One modelled account, reproducible from its seed.

    The seed is returned alongside the account so anything a person sees on
    screen can be regenerated exactly from the response alone.
    """
    if seed is None:
        seed = random.randrange(0, 2**31)
    rng = random.Random(seed)
    as_of = as_of or date(2026, 9, 19)
    span = horizon_days
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

    # Payroll first, so the charges can be placed relative to it.
    cadence = rng.choice((7, 14))
    first_pay = _MIN_DAYS_TO_FIRST_PAY + rng.randrange(0, 5)
    paydays: list[date] = []
    offset = first_pay
    while offset < span:
        day = _business_day(as_of + timedelta(days=offset), rng)
        if day >= as_of:
            paydays.append(day)
            add(day, PAYROLL, rng.randrange(95_000, 185_000), "income", True)
        offset += cadence

    # A horizon with no payday has nothing to reach, so the dip has no meaning.
    if not paydays:
        day = _business_day(as_of + timedelta(days=min(first_pay, span - 1)), rng)
        paydays.append(day)
        add(day, PAYROLL, rng.randrange(95_000, 185_000), "income", True)

    first_payday = min(paydays)

    # Charges. The count is held well clear of MAX_FREE candidates: the
    # exhaustive engine is 2^n and the perf suite already has 34 accounts sitting
    # at the cap. A denser profile would make that run grow without anything
    # failing — it would simply take longer every time, which is the worst way to
    # lose an afternoon.
    for _ in range(rng.randrange(12, 23)):
        description, kind, recurring, low, high = rng.choice(MERCHANTS)
        add(
            as_of + timedelta(days=rng.randrange(0, span)),
            description,
            -_heavy_tailed(low, high, rng),
            kind,
            recurring,
        )

    # The planted dip. Work out what leaves STRICTLY before the first payday,
    # then choose an opening balance that carries the account under the cushion
    # on the way there. Computed rather than guessed, so it holds for every seed.
    #
    # Strictly before, not on-or-before: the payroll credit lands on the payday
    # itself, so counting that day's charges would have the income cancel the dip
    # we are trying to plant. That error left 28 of 200 seeds with nothing to
    # solve, which is the one thing this profile exists to guarantee.
    before = sum(
        -t["amount_cents"]
        for t in scheduled
        if t["amount_cents"] < 0 and date.fromisoformat(t["date"]) < first_payday
    )
    buffer_cents = 2_500
    shortfall = rng.randrange(2_000, 9_000)
    opening = max(0, before + buffer_cents - shortfall)

    scheduled.sort(key=lambda t: (t["date"], t["description"]))
    for i, row in enumerate(scheduled):
        row["id"] = f"t_{i:03d}"

    assert len(scheduled) <= MAX_SCHED
    return {
        "seed": seed,
        "as_of": as_of.isoformat(),
        "horizon_end": horizon_end.isoformat(),
        "opening_balance_cents": min(opening, CENTS_ABS),
        "buffer_cents": buffer_cents,
        "scheduled": scheduled,
        "source": "modelled",
    }

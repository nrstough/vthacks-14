"""Synthetic bank exports, for testing detection against known rhythms.

Separate from `profiles.window()`, which only ever produces a FORWARD window:
nothing in the repo generated PAST transactions before this, and detection has
nothing to detect without them. Its RNG sequence is its own, so changing
anything here cannot move the generator's pinned golden hash.
"""

from __future__ import annotations

import datetime
import random

MONDAY, FRIDAY = 0, 4


def _back_to_weekday(day: datetime.date) -> datetime.date:
    while day.weekday() > FRIDAY:
        day -= datetime.timedelta(days=1)
    return day


def row(day: datetime.date, description: str, amount_cents: int) -> dict:
    return {"date": day.isoformat(), "description": description, "amount_cents": amount_cents}


def weekly_income(
    end: datetime.date,
    weeks: int = 40,
    weekday: int = 1,
    amount: int = 42000,
    jitter_cents: int = 6000,
    skip: tuple[int, ...] = (),
    moved_weekday: int | None = None,
    moved_after: int = 10**6,
    seed: int = 11,
    description: str = "ACME WIDGETS LLC",
) -> list[dict]:
    """Hours-based weekly pay: a stable weekday, an amount that wobbles."""
    rng = random.Random(seed)
    out = []
    for i in range(weeks):
        if i in skip:
            continue
        want = weekday if i < moved_after else (moved_weekday if moved_weekday is not None else weekday)
        day = end - datetime.timedelta(days=7 * (weeks - 1 - i))
        day += datetime.timedelta(days=(want - day.weekday()) % 7 - 7 if (want - day.weekday()) % 7 > 3 else (want - day.weekday()) % 7)
        out.append(row(day, description, amount + rng.randrange(0, jitter_cents)))
    return out


def biweekly_income(
    end: datetime.date, periods: int = 20, weekday: int = FRIDAY, amount: int = 86000, description: str = "PIEDMONT LABS INC"
) -> list[dict]:
    out = []
    for i in range(periods):
        day = end - datetime.timedelta(days=14 * (periods - 1 - i))
        day += datetime.timedelta(days=(weekday - day.weekday()) % 7 - 7)
        out.append(row(day, description, amount))
    return out


def semimonthly_income(
    first: datetime.date, months: int = 12, amount: int = 61000, description: str = "BLUE RIDGE CAFE"
) -> list[dict]:
    """The 15th and the last day of the month: the shape a gap test gets wrong."""
    out = []
    year, month = first.year, first.month
    for _ in range(months):
        import calendar

        last = calendar.monthrange(year, month)[1]
        out.append(row(datetime.date(year, month, 15), description, amount))
        out.append(row(datetime.date(year, month, last), description, amount))
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return out


def monthly_bill(
    first: datetime.date,
    months: int,
    day_of_month: int,
    amount: int,
    description: str,
    weekend_shift: bool = True,
    drift_after: int | None = None,
    drift_to: int | None = None,
) -> list[dict]:
    import calendar

    out = []
    year, month = first.year, first.month
    for i in range(months):
        last = calendar.monthrange(year, month)[1]
        day = datetime.date(year, month, min(day_of_month, last))
        if weekend_shift:
            day = _back_to_weekday(day)
        value = amount if drift_after is None or i < drift_after else (drift_to or amount)
        out.append(row(day, description, value))
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return out


def everyday_spending(
    start: datetime.date, end: datetime.date, seed: int = 23, weekday_cents: int = 2500, weekend_cents: int = 6000
) -> list[dict]:
    """The residual: groceries and coffee, never the same merchant string twice."""
    rng = random.Random(seed)
    out = []
    day = start
    while day <= end:
        if day.weekday() == 6:
            day += datetime.timedelta(days=1)
            continue
        base = weekend_cents if day.weekday() == 5 else weekday_cents
        out.append(row(day, f"KROGER #{380 + rng.randrange(0, 9)}", -(base + rng.randrange(0, 400))))
        day += datetime.timedelta(days=1)
    return out


def peer_transfers(start: datetime.date, end: datetime.date, seed: int = 47) -> list[dict]:
    """Irregular inflows, sometimes several a day. Never income."""
    rng = random.Random(seed)
    out = []
    day = start
    while day <= end:
        if rng.random() < 0.08:
            for _ in range(rng.randrange(1, 4)):
                out.append(row(day, "VENMO CASHOUT", rng.randrange(500, 14000)))
        day += datetime.timedelta(days=1)
    return out


def realistic(
    end: datetime.date = datetime.date(2026, 9, 18), months: int = 9, seed: int = 0
) -> list[dict]:
    """A whole account: weekly pay, rent, two subscriptions, spending, transfers.

    `seed` moves the payday weekday, the amounts and the bills' days of month,
    so a loop over seeds exercises DETECTION and not only the residual.
    """
    # Seed 0 is the fixed account the golden test pins; any other seed moves
    # the payday weekday, the amounts and the bills' days of month.
    rng = random.Random(seed)
    vary = seed != 0
    start = end - datetime.timedelta(days=30 * months)
    rows: list[dict] = []
    rows += weekly_income(
        end,
        weeks=4 * months,
        weekday=rng.randrange(0, 5) if vary else 1,
        amount=30000 + rng.randrange(0, 40000) if vary else 42000,
        seed=seed if vary else 11,
    )
    rows += monthly_bill(
        start, months, 1 + rng.randrange(0, 5) if vary else 1,
        -(90000 + rng.randrange(0, 60000)) if vary else -120000, "OAKWOOD PROPERTIES",
    )
    rows += monthly_bill(start, months, 10 + rng.randrange(0, 8) if vary else 12, -3499, "PLANET FIT CLUB FEES", weekend_shift=False)
    rows += monthly_bill(start, months, 15 + rng.randrange(0, 8) if vary else 15, -1599, "NETFLIX.COM", weekend_shift=False)
    rows += everyday_spending(start, end, seed=seed if vary else 23)
    rows += peer_transfers(start, end, seed=seed if vary else 47)
    return sorted(rows, key=lambda r: r["date"])

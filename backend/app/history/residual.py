"""Everyday spending: what is left after every recurring payee is removed.

The split is BY TRANSACTION, never by subtracting one total from another. A
subtraction would let a month with a large bill produce negative "everyday
spending", which a clip to zero would then hide; removing rows cannot.

The statistic is the same-weekday median over eight weeks, not the mean. The
mean is what turns one $900 laptop into $112 of predicted spending on that
weekday for the whole horizon, which is both wrong and the kind of wrong a
person notices immediately.
"""

from __future__ import annotations

import datetime

from .money import median_cents

CONTEXT_DAYS = 56
WEEKS = 8
ASSUMED_PREFIX = "f_"
ASSUMED_DESCRIPTION = "Everyday spending (assumed from your last 8 weeks)"


def daily_outflow(
    rows: list,
    used_indexes: set[int],
    history_start: datetime.date,
    history_end: datetime.date,
) -> tuple[dict[datetime.date, int], int]:
    """Positive cents of non-recurring outflow per day, with every day present.

    A quiet day is a zero-spend day, because a bank export is complete for the
    range it covers. That assumption is stated on screen and the count of such
    days is returned so it can be.
    """
    series: dict[datetime.date, int] = {}
    day = history_start
    while day <= history_end:
        series[day] = 0
        day += datetime.timedelta(days=1)
    for row in rows:
        if row.index in used_indexes or row.amount_cents >= 0:
            continue
        if row.date in series:
            series[row.date] += -row.amount_cents
    imputed = sum(1 for value in series.values() if value == 0)
    return series, imputed


def assumed_rows(
    series: dict[datetime.date, int],
    history_end: datetime.date,
    as_of: datetime.date,
    horizon_end: datetime.date,
) -> list[tuple[str, datetime.date, int]]:
    """One row per horizon day, at that weekday's median over the last 8 weeks.

    Returns [] when there is not 56 days of history: an estimate from three
    weeks is not the estimate this says it is, and saying so is better than
    quietly using a shorter window.
    """
    window_start = history_end - datetime.timedelta(days=CONTEXT_DAYS - 1)
    if window_start not in series:
        return []

    by_weekday: dict[int, list[int]] = {w: [] for w in range(7)}
    day = window_start
    while day <= history_end:
        by_weekday[day.weekday()].append(series[day])
        day += datetime.timedelta(days=1)

    out: list[tuple[str, datetime.date, int]] = []
    day = as_of
    while day <= horizon_end:
        values = by_weekday[day.weekday()]
        amount = median_cents(values) if values else 0
        if amount > 0:
            out.append((f"{ASSUMED_PREFIX}{day.isoformat().replace('-', '')}", day, -amount))
        day += datetime.timedelta(days=1)
    return out

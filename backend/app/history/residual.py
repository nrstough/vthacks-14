"""Everyday spending: what is left after every recurring payee is removed.

The split is BY TRANSACTION, never by subtracting one total from another. A
subtraction would let a month with a large bill produce negative "everyday
spending", which a clip to zero would then hide; removing rows cannot.

The statistic is the same-weekday 60th percentile over eight weeks.

Not the mean: one $900 laptop becomes $112 of predicted spending on that
weekday for the whole horizon, which is wrong in a way a person notices at
once.

Not the median either, which is where this started. Measured across 692
rolling windows of a real two-year account, the median under-predicted the
next fortnight's spending 71% of the time, by an average of $115. For a
tool whose purpose is to say when money will run out, under-predicting
spending is the direction that tells someone they are fine when they are
not. The 60th percentile is just as immune to a single large purchase, cuts
the under-prediction to 52% of windows and $37, and has a smaller error
besides. The evidence is in
`docs/reports/2026-09-20_forecast-evaluation.md`.
"""

from __future__ import annotations

import datetime

from app.schemas import CENTS_ABS

from .errors import ImportRefused
from .money import percentile_cents

CONTEXT_DAYS = 56
WEEKS = 8
# See the module docstring: the 50th under-predicts spending, and that is
# the unsafe direction for this product.
ASSUMED_PERCENTILE = 0.6
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
    active: set[datetime.date] = set()
    for row in rows:
        if row.date in series:
            active.add(row.date)
        if row.index in used_indexes or row.amount_cents >= 0:
            continue
        if row.date in series:
            series[row.date] += -row.amount_cents
    # Days with NO transaction at all, not days whose only transaction was a
    # bill. Counting the latter tells someone with eleven monthly bills that
    # they spent nothing on all 71 days of their history.
    imputed = sum(1 for day in series if day not in active)
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
        amount = percentile_cents(values, ASSUMED_PERCENTILE) if values else 0
        # A DAY's total is the sum of its rows, and only the rows are capped.
        # Enough max-size rows on one weekday push the median past what a
        # scheduled amount may hold, and the response model then rejects a
        # request that was perfectly valid on the way in — a 500 on good
        # input. Refuse here, where the number can be named.
        if amount > CENTS_ABS:
            raise ImportRefused(
                "The everyday spending in this history is too large to plan over. "
                "Check the export is a single account in one currency."
            )
        if amount > 0:
            out.append((f"{ASSUMED_PREFIX}{day.isoformat().replace('-', '')}", day, -amount))
        day += datetime.timedelta(days=1)
    return out

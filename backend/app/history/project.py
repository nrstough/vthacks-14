"""Turn a detected stream into the rows it will produce in the horizon.

Three rules here are not obvious and each came from a review finding:

1. **Snap, then step, then clip.** Stepping the interval from the last
   occurrence and only then snapping to the anchor weekday can move the first
   projected date by up to six days — sometimes behind `as_of`, which silently
   deletes a paycheck from a fortnight's plan.
2. **Weekends move income later and bills earlier.** A bill debited on the
   Friday before is money already gone; income credited on the Monday after is
   money not yet there. Rounding either one the other way invents cash.
3. **Income expected today is not projected.** `opening_balance_cents` is the
   balance including everything posted through today. If today's pay posted it
   is already in that number, and projecting it again counts it twice; if it
   has not posted, counting it is a guess in the optimistic direction. Either
   way it is left out and named, so the screen can say so.
"""

from __future__ import annotations

import datetime

from .detect import Stream
from .workdays import next_business_day, on_day_of_month, previous_business_day


def _shift_for_kind(d: datetime.date, kind: str) -> datetime.date:
    return next_business_day(d) if kind == "income" else previous_business_day(d)


def _snap_to_weekday(d: datetime.date, weekday: int) -> datetime.date:
    """Nearest date with that weekday, ties going forward."""
    delta = (weekday - d.weekday()) % 7
    return d + datetime.timedelta(days=delta if delta <= 3 else delta - 7)


def _weekly_dates(stream: Stream, as_of: datetime.date, horizon_end: datetime.date) -> list[datetime.date]:
    interval = 7 if stream.cadence == "weekly" else 14
    assert stream.anchor_weekday is not None
    cursor = _snap_to_weekday(stream.last_seen, stream.anchor_weekday)
    while cursor < as_of:
        cursor += datetime.timedelta(days=interval)
    out: list[datetime.date] = []
    while cursor <= horizon_end:
        out.append(cursor)
        cursor += datetime.timedelta(days=interval)
    return out


def _monthly_dates(stream: Stream, as_of: datetime.date, horizon_end: datetime.date) -> list[datetime.date]:
    """Every candidate occurrence from a month either side of the window.

    Both margins matter, and the far one is easy to lose: a bill anchored to
    the 1st of the month AFTER the window is pulled back over a weekend onto
    the last Friday of the window and belongs in the plan. Generating only up
    to the window's own last month drops it, and the person is shown a
    fortnight with their rent missing.
    """
    out: list[datetime.date] = []
    year, month = as_of.year, as_of.month
    if month == 1:
        year, month = year - 1, 12
    else:
        month -= 1
    for _ in range(18):  # a hard bound; the break below is the real end
        for day in stream.anchor_doms:
            out.append(on_day_of_month(year, month, day))
        if (year, month) > (horizon_end.year, horizon_end.month):
            break
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return out


def project(
    stream: Stream,
    as_of: datetime.date,
    horizon_end: datetime.date,
) -> tuple[list[tuple[str, datetime.date, int]], bool]:
    """Returns (rows as (id, date, amount), whether an occurrence today was withheld).

    Whether a bill due today was already taken is answered from THIS stream's
    own rows, not from the payee. Two subscriptions at one merchant share a
    payee key, so a key-based test silently suppresses the $22.99 one because
    the $15.99 one posted this morning.
    """
    if not stream.active:
        return [], False

    if stream.cadence in ("weekly", "biweekly"):
        raw = _weekly_dates(stream, as_of, horizon_end)
    else:
        raw = _monthly_dates(stream, as_of, horizon_end)

    seen: set[datetime.date] = set()
    withheld = False
    out: list[tuple[str, datetime.date, int]] = []
    for d in sorted(raw):
        shifted = _shift_for_kind(d, stream.kind)
        if shifted < as_of or shifted > horizon_end or shifted in seen:
            continue
        if shifted == as_of:
            if stream.kind == "income":
                withheld = True
                continue
            if any(row.date == as_of for row in stream.rows):
                continue
        seen.add(shifted)
        out.append(("", shifted, stream.amount_cents))
    return out, withheld

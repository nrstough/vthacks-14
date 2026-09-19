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


def _assign_to_occurrences(
    history: list[datetime.date],
    occurrences: list[datetime.date],
    stream: Stream,
) -> set[datetime.date]:
    """Which occurrences the export has already paid.

    Every posted row is matched to the occurrence it is NEAREST to, and an
    occurrence counts as paid only if some row chose it. Ties go to the
    earlier occurrence.

    A half-open period test fails in both directions and each failure is a
    missing row in the plan. Rent due on the 1st but paid on the 3rd sits
    inside the window ending at the NEXT 1st, so next month's rent
    disappears; and a fixed day count cannot express a period at all,
    because February to March is 28 days. Nearest-occurrence matching
    tolerates jitter either way without ever letting one payment settle a
    period it does not belong to.

    A row further than half an interval from every occurrence matches none
    of them: it is a one-off at that payee, not a payment of this stream.
    """
    if not occurrences:
        return set()
    half = datetime.timedelta(days=stream.interval_days) / 2
    paid: set[datetime.date] = set()
    for when in history:
        nearest = min(occurrences, key=lambda o: (abs(o - when), o))
        if abs(nearest - when) <= half:
            paid.add(nearest)
    return paid


def _snap_to_weekday(d: datetime.date, weekday: int) -> datetime.date:
    """Nearest date with that weekday, ties going forward."""
    delta = (weekday - d.weekday()) % 7
    return d + datetime.timedelta(days=delta if delta <= 3 else delta - 7)


# A weekend shift moves a date by at most three days, so candidates from
# this far outside the window can still land inside it.
MARGIN = datetime.timedelta(days=4)


def _weekly_dates(stream: Stream, as_of: datetime.date, horizon_end: datetime.date) -> list[datetime.date]:
    """Candidates from a few days either side of the window.

    Clipping to the window BEFORE the weekend shift loses real occurrences at
    both ends: a Sunday-anchored bill dated the 4th is taken on Friday the
    2nd and belongs in a window ending the 2nd, and Saturday income dated the
    19th arrives Monday the 21st and belongs in a window starting the 20th.
    Generate wide, shift, then clip — `project` does the clipping.
    """
    interval = 7 if stream.cadence == "weekly" else 14
    assert stream.anchor_weekday is not None
    cursor = _snap_to_weekday(stream.last_seen, stream.anchor_weekday)
    while cursor < as_of - MARGIN:
        cursor += datetime.timedelta(days=interval)
    out: list[datetime.date] = []
    while cursor <= horizon_end + MARGIN:
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
) -> tuple[list[tuple[str, datetime.date, int]], bool, bool]:
    """Returns (rows, income expected today but not yet posted, income already
    posted for a period inside the window).

    Both flags are about income the person will look for and not find, and
    they need different sentences: one has not arrived, the other is already
    in the balance they typed.

    Whether a charge was already taken is answered from THIS stream's own
    rows, not from the payee. Two subscriptions at one merchant share a
    payee key, so a key-based test silently suppresses the $22.99 one
    because the $15.99 one posted this morning.
    """
    if not stream.active:
        return [], False, False

    if stream.cadence in ("weekly", "biweekly"):
        raw = _weekly_dates(stream, as_of, horizon_end)
    else:
        raw = _monthly_dates(stream, as_of, horizon_end)

    history = [row.date for row in stream.rows]
    ordered = sorted(raw)
    posted = _assign_to_occurrences(history, [_shift_for_kind(d, stream.kind) for d in ordered], stream)

    seen: set[datetime.date] = set()
    expected_today = False
    posted_early = False
    out: list[tuple[str, datetime.date, int]] = []
    for index, d in enumerate(ordered):
        shifted = _shift_for_kind(d, stream.kind)
        if shifted < as_of or shifted > horizon_end or shifted in seen:
            continue
        if shifted in posted:
            # Already in the balance the person typed. Two different facts
            # for income, and the screen says different things about them.
            if stream.kind == "income":
                posted_early = True
            continue
        if shifted == as_of and stream.kind == "income":
            # Not yet posted, and counting it is a guess in the optimistic
            # direction; the balance the person typed is the truth.
            expected_today = True
            continue
        seen.add(shifted)
        out.append(("", shifted, stream.amount_cents))
    return out, expected_today, posted_early

"""Calendar helpers the projector needs. Named `workdays`, not `calendar`, so
the stdlib module of that name stays importable from inside this package."""

from __future__ import annotations

import calendar
import datetime

WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def weekday_name(d: datetime.date) -> str:
    return WEEKDAY_NAMES[d.weekday()]


def is_weekend(d: datetime.date) -> bool:
    return d.weekday() >= 5


def previous_business_day(d: datetime.date) -> datetime.date:
    """Saturday and Sunday fall back to Friday.

    The direction is deliberate and is chosen per kind by the caller: a BILL
    that lands on a weekend is taken earlier, because a bank that debits on
    Friday and a plan that expects Monday differ by the two days someone would
    have spent the money.
    """
    while is_weekend(d):
        d -= datetime.timedelta(days=1)
    return d


def next_business_day(d: datetime.date) -> datetime.date:
    """Saturday and Sunday move forward to Monday.

    INCOME only. Moving income earlier would make cash appear on a day it is
    not there, which is the one rounding direction this product must never
    take.
    """
    while is_weekend(d):
        d += datetime.timedelta(days=1)
    return d


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def add_months(d: datetime.date, n: int) -> datetime.date:
    """Move by whole months, clamping the day to the target month's length."""
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return datetime.date(year, month, min(d.day, days_in_month(year, month)))


def on_day_of_month(year: int, month: int, day: int) -> datetime.date:
    """`day` may be 31 for a stream anchored to the month end; clamp it."""
    return datetime.date(year, month, min(day, days_in_month(year, month)))

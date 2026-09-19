"""Calendar and money formatting.

Dates are `datetime.date` internally and YYYY-MM-DD strings at the boundary.
There is deliberately no `datetime` anywhere in this package: the constraints
live at midnight, which is exactly where a timezone would corrupt them.

`money` and `short_date` mirror frontend/src/lib/format.ts character for
character, because the parity tests compare rendered prose.
"""

from __future__ import annotations

from datetime import date, timedelta

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def parse(iso: str) -> date:
    return date.fromisoformat(iso)


def to_iso(d: date) -> str:
    return d.isoformat()


def day_range(as_of: str, horizon_end: str) -> list[date]:
    """Every day of the horizon, both ends inclusive."""
    start, end = parse(as_of), parse(horizon_end)
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def days_between(a: str, b: str) -> int:
    return (parse(b) - parse(a)).days


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    magnitude = abs(cents)
    return f"{sign}${magnitude // 100:,}.{magnitude % 100:02d}"


def short_date(iso: str) -> str:
    _, month, day = (int(part) for part in iso.split("-"))
    return f"{_MONTHS[month - 1]} {day}"

"""Calendar arithmetic.

An off-by-one here does not look like a bug, it looks like an overdraft — either
one invented on a day that was fine, or one hidden on the day it actually
happens. The horizon is inclusive at both ends, and the boundaries that get this
wrong in practice are month ends, February, and the days clocks change.
"""

from __future__ import annotations

import subprocess

import pytest

from app.solver.dates import day_range, days_between, money, short_date, to_iso
from tests.conftest import requires_node


@pytest.mark.parametrize(
    "as_of,horizon_end,expected",
    [
        ("2026-09-19", "2026-09-19", 1),  # a single day is a legal horizon
        ("2026-09-19", "2026-10-02", 14),
        ("2026-09-29", "2026-10-02", 4),  # across a 30-day month end
        ("2026-01-30", "2026-02-02", 4),  # across a 31-day month end
        ("2027-02-27", "2027-03-02", 4),  # February, not a leap year
        ("2028-02-27", "2028-03-02", 5),  # February, leap year
        ("2026-10-25", "2026-11-08", 15),  # spans the end of daylight saving
        ("2026-12-30", "2027-01-02", 4),  # across a year end
    ],
)
def test_horizon_length_is_inclusive_at_both_ends(as_of, horizon_end, expected):
    days = day_range(as_of, horizon_end)
    assert len(days) == expected
    assert to_iso(days[0]) == as_of
    assert to_iso(days[-1]) == horizon_end


def test_days_are_consecutive_with_no_gaps_or_repeats():
    """The 25-hour day at the end of daylight saving is still one day."""
    days = day_range("2026-10-25", "2026-11-08")
    assert len(set(days)) == len(days)
    assert [to_iso(d) for d in days][:3] == ["2026-10-25", "2026-10-26", "2026-10-27"]
    assert "2026-11-01" in [to_iso(d) for d in days]


@pytest.mark.parametrize(
    "a,b,expected",
    [("2026-09-19", "2026-09-19", 0), ("2026-09-19", "2026-09-22", 3),
     ("2026-02-28", "2026-03-01", 1), ("2028-02-28", "2028-03-01", 2)],
)
def test_days_between(a, b, expected):
    assert days_between(a, b) == expected


@pytest.mark.parametrize(
    "cents,expected",
    [(0, "$0.00"), (5, "$0.05"), (745, "$7.45"), (-4100, "-$41.00"),
     (100_000, "$1,000.00"), (-1_234_567, "-$12,345.67"), (99, "$0.99")],
)
def test_money_formatting(cents, expected):
    assert money(cents) == expected


@pytest.mark.parametrize(
    "iso,expected",
    [("2026-09-24", "Sep 24"), ("2026-01-01", "Jan 1"), ("2026-12-31", "Dec 31")],
)
def test_short_date_formatting(iso, expected):
    assert short_date(iso) == expected


@requires_node
def test_formatting_matches_the_frontend_character_for_character():
    """These strings are compared against the reference solver's prose, so a
    thousands separator or a leading zero out of step would surface as a
    mysterious parity failure somewhere else entirely."""
    cases = [0, 5, 99, 745, -4100, 100_000, -1_234_567, 2762]
    dates = ["2026-09-24", "2026-01-01", "2026-12-31", "2026-03-02"]
    script = (
        "import {money, shortDate} from "
        "'../../../frontend/src/lib/format.ts';"
        f"console.log(JSON.stringify({{m: {cases}.map(money), d: {dates!r}.map(shortDate)}}))"
    ).replace("'", '"')
    out = subprocess.run(
        ["node", "--no-warnings", "--experimental-strip-types", "--input-type=module", "-e", script],
        capture_output=True, text=True, cwd=__import__("pathlib").Path(__file__).parent / "oracle",
    )
    assert out.returncode == 0, out.stderr
    import json

    theirs = json.loads(out.stdout)
    assert [money(c) for c in cases] == theirs["m"]
    assert [short_date(d) for d in dates] == theirs["d"]

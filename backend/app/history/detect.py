"""Find the recurring payees in a bank export, by rhythm rather than by name.

Nathan's own export never contains the word PAYROLL. Neither do most: a
student's pay arrives as a company name, a landlord's rent as a person's. So
nothing here matches keywords to decide WHETHER a row recurs — the lexicon is
consulted only to LABEL what the rhythm already found.

What a stream is: one payee, at least three occurrences, a cadence its gaps
actually fit, an anchor (a weekday, or one or two days of the month) taken
from its recent behaviour, and amounts stable enough for its kind. Income is
allowed to wobble because hours-based pay does; a bill is not, because a
"bill" whose amount swings by half is a shopping habit.
"""

from __future__ import annotations

import datetime
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from app.candidates.lexicon import PROTECTED, UNKNOWN_CATEGORY, classify
from app.schemas import CENTS_ABS

from .errors import ImportRefused
from .labels import stream_label
from .money import coefficient_of_variation, trimmed_mean_cents
from .workdays import weekday_name
from .payee import payee_key

MIN_OCCURRENCES = 3
# A recurring outflow is a BILL only if it behaves like one. A weekly grocery
# run is real, predictable and worth projecting, but it is not a bill, and
# showing it in the untick list as one would misdescribe the person's account.
# Anything unrecognised is treated as a bill, which is the conservative side:
# the candidate generator refuses to offer changes to an unrecognised bill.
BILL_LIKE = PROTECTED + ("streaming", "gym", "software")
# Hours-based pay swings; a bill that swings is not a bill.
CV_MAX_INCOME = 0.5
CV_MAX_BILL = 0.15
# A stream is lapsed when its silence is longer than this many intervals.
# Income gets more rope: a student who does not work over an exam week has not
# lost their job, and dropping their pay from the plan is the expensive error.
LAPSE_INTERVALS_INCOME = 3.0
LAPSE_INTERVALS_BILL = 2.0
# Two amounts this far apart at one payee are two different subscriptions
# rather than one that drifted.
BIMODAL_RATIO = 0.75
# A cadence fits when its MEDIAN gap picks a band and most gaps are
# CONSISTENT with that band's interval. Consistent means "near a whole number
# of intervals", not "near one interval": a student who does not work over an
# exam week leaves a 14-day gap in a weekly stream, and calling that a broken
# cadence deletes their income from the plan and then tells them they need
# outside cash. A wobble of a day or two either side is the same payday moved,
# not a different rhythm.
IN_BAND_FRACTION = 0.75
MAX_MISSED_PERIODS = 3
GAP_BANDS: tuple[tuple[str, int, int, int, int], ...] = (
    # name, median-band low, high, nominal interval, tolerance per interval
    ("weekly", 6, 8, 7, 2),
    ("biweekly", 13, 16, 14, 2),
    ("monthly", 27, 34, 30, 4),
)
# Day-of-month clustering: two charges this many days apart are the same
# anchor shifted by a weekend, not two different anchors.
DOM_ADJACENT = 3
DOM_MODULUS = 31
SEMIMONTHLY_MIN_SEPARATION = 10
SEMIMONTHLY_MAX_SEPARATION = 20
SEMIMONTHLY_MONTH_COVERAGE = 0.6
ANCHOR_WINDOW = 8


@dataclass(frozen=True)
class Row:
    """A request row with its ORIGINAL index carried through every step.

    Detection sorts, groups and filters; `source_row_indexes` on the response
    has to point back at `request.rows` as the caller sent it. Carrying the
    index in the row is the only way that survives a sort.
    """

    index: int
    date: datetime.date
    amount_cents: int
    description: str
    key: str


@dataclass
class Stream:
    kind: str
    category: str
    label: str
    cadence: str
    anchor: str
    anchor_weekday: int | None
    anchor_doms: tuple[int, ...]
    amount_cents: int
    occurrences: int
    last_seen: datetime.date
    active: bool
    rows: list[Row] = field(default_factory=list)

    @property
    def interval_days(self) -> int:
        return {"weekly": 7, "biweekly": 14, "semimonthly": 15, "monthly": 30}[self.cadence]


def weekday_name_of(index: int) -> str:
    """Monday is 0, the same convention `date.weekday()` uses."""
    return weekday_name(datetime.date(2024, 1, 1) + datetime.timedelta(days=index))


def _ordinal(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return f"{day}th"
    return f"{day}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th') }".replace(" ", "")


def _circular_distance(a: int, b: int) -> int:
    raw = abs(a - b)
    return min(raw, DOM_MODULUS - raw)


def _cluster_days_of_month(days: list[int]) -> list[list[int]]:
    """Single-linkage clustering of days of month, wrapping past the month end.

    Wrapping matters: a bill due on the 1st that the bank takes on the previous
    business day appears as the 31st, the 1st and the 2nd. Those are one
    anchor, and a linear clustering would call the 31st a second one.
    """
    unique = sorted(set(days))
    if not unique:
        return []
    clusters: list[list[int]] = [[unique[0]]]
    for day in unique[1:]:
        if _circular_distance(clusters[-1][-1], day) <= DOM_ADJACENT:
            clusters[-1].append(day)
        else:
            clusters.append([day])
    # The first and last clusters may meet across the month boundary.
    if len(clusters) > 1 and _circular_distance(clusters[-1][-1], clusters[0][0]) <= DOM_ADJACENT:
        clusters[0] = clusters.pop() + clusters[0]
    return clusters


def _mode_day_of_month(days: list[int]) -> int:
    counts = Counter(days)
    top = max(counts.values())
    # Ties break to the LARGER day: a month-end bill that lands on the 30th and
    # the 31st is anchored to the end of the month, and clamping later is safe
    # where clamping earlier silently moves it into the previous period.
    return max(d for d, n in counts.items() if n == top)


def _split_bimodal(rows: list[Row]) -> list[list[Row]]:
    """Two subscriptions at one merchant are two streams, not one average.

    Sort the amounts, cut at the largest relative gap, and accept the split
    only when both sides look like their own stream: at least three members,
    each within 15% of that side's median.
    """
    if len(rows) < 2 * MIN_OCCURRENCES:
        return [rows]
    ordered = sorted(rows, key=lambda r: abs(r.amount_cents))
    best_at, best_ratio = None, 1.0
    for i in range(MIN_OCCURRENCES - 1, len(ordered) - MIN_OCCURRENCES):
        low, high = abs(ordered[i].amount_cents), abs(ordered[i + 1].amount_cents)
        if low == 0:
            continue
        ratio = low / high
        if ratio < best_ratio:
            best_at, best_ratio = i, ratio
    if best_at is None or best_ratio > BIMODAL_RATIO:
        return [rows]
    sides = [ordered[: best_at + 1], ordered[best_at + 1 :]]
    for side in sides:
        amounts = sorted(abs(r.amount_cents) for r in side)
        median = amounts[len(amounts) // 2]
        if median == 0 or any(abs(a - median) > 0.15 * median for a in amounts):
            return [rows]
    return sides


def _collapse_same_day(rows: list[Row]) -> tuple[list[tuple[datetime.date, int, list[Row]]], bool]:
    by_day: dict[datetime.date, list[Row]] = defaultdict(list)
    for row in rows:
        by_day[row.date].append(row)
    multi = any(len(v) > 1 for v in by_day.values())
    collapsed = [(d, sum(r.amount_cents for r in by_day[d]), by_day[d]) for d in sorted(by_day)]
    return collapsed, multi


def _consistent(gap: int, nominal: int, tolerance: int) -> bool:
    """Is this gap one period, or a small number of periods, of `nominal`?"""
    return any(abs(gap - nominal * k) <= tolerance for k in range(1, MAX_MISSED_PERIODS + 1))


def _fit_gap_cadence(dates: list[datetime.date]) -> str | None:
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    if not gaps:
        return None
    ordered = sorted(gaps)
    median = ordered[len(ordered) // 2]
    for name, low, high, nominal, tolerance in GAP_BANDS:
        if low <= median <= high:
            good = sum(1 for g in gaps if _consistent(g, nominal, tolerance))
            if good / len(gaps) >= IN_BAND_FRACTION:
                return name
    return None


def _fit_semimonthly(dates: list[datetime.date]) -> tuple[int, int] | None:
    """Twice a month is decided by WHERE in the month, never by gap length.

    Its gaps (13–18 days) overlap biweekly's almost exactly, so a gap test
    calls a 15th-and-month-end payroll "every 14 days" and then drifts off both
    anchors within one month. Two day-of-month anchors, far enough apart not to
    be one anchor shifted by a weekend, and both actually recurring month after
    month, is what makes it semimonthly.
    """
    if len(dates) < 2 * MIN_OCCURRENCES:
        return None
    clusters = _cluster_days_of_month([d.day for d in dates])
    if len(clusters) != 2:
        return None
    first, second = clusters
    counts = Counter(d.day for d in dates)
    if sum(counts[d] for d in first) < MIN_OCCURRENCES or sum(counts[d] for d in second) < MIN_OCCURRENCES:
        return None
    anchor_a, anchor_b = _mode_day_of_month(first), _mode_day_of_month(second)
    separation = _circular_distance(anchor_a, anchor_b)
    if not (SEMIMONTHLY_MIN_SEPARATION <= separation <= SEMIMONTHLY_MAX_SEPARATION):
        return None
    months = {(d.year, d.month) for d in dates}
    both = 0
    for year, month in months:
        in_month = [d.day for d in dates if (d.year, d.month) == (year, month)]
        if any(d in first for d in in_month) and any(d in second for d in in_month):
            both += 1
    if both / len(months) < SEMIMONTHLY_MONTH_COVERAGE:
        return None
    return tuple(sorted((anchor_a, anchor_b)))  # type: ignore[return-value]


def detect_streams(rows: list[Row], history_end: datetime.date) -> tuple[list[Stream], list[Row]]:
    """Returns (streams, rows that are inflows belonging to no stream).

    The second list is money that arrived irregularly — a friend paying you
    back. It is reported and never planned around: a plan that counts on a
    transfer that may not come is worse than one that does not.
    """
    groups: dict[tuple[int, str], list[Row]] = defaultdict(list)
    for row in rows:
        groups[(1 if row.amount_cents > 0 else -1, row.key)].append(row)

    streams: list[Stream] = []
    unscheduled: list[Row] = []

    for (sign, _key), group in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        base_kind = "income" if sign > 0 else "bill"
        for cluster in _split_bimodal(group):
            kind = base_kind
            if len(cluster) < MIN_OCCURRENCES:
                if kind == "income":
                    unscheduled.extend(cluster)
                continue
            collapsed, multi_per_day = _collapse_same_day(cluster)
            dates = [d for d, _amount, _rows in collapsed]
            if len(dates) < MIN_OCCURRENCES or multi_per_day:
                # Several charges from one payee on one day is a shopping
                # pattern or a peer-transfer app, not a scheduled payment.
                if kind == "income":
                    unscheduled.extend(cluster)
                continue

            doms = _fit_semimonthly(dates)
            cadence = "semimonthly" if doms else _fit_gap_cadence(dates)
            if cadence is None:
                if kind == "income":
                    unscheduled.extend(cluster)
                continue

            recent_amounts = [amount for _d, amount, _r in collapsed[-ANCHOR_WINDOW:]]
            cv = coefficient_of_variation(recent_amounts)
            if cv > (CV_MAX_INCOME if kind == "income" else CV_MAX_BILL):
                if kind == "income":
                    unscheduled.extend(cluster)
                continue

            recent_dates = dates[-ANCHOR_WINDOW:]
            anchor_weekday: int | None = None
            anchor_doms: tuple[int, ...] = ()
            if cadence in ("weekly", "biweekly"):
                anchor_weekday = Counter(d.weekday() for d in recent_dates).most_common(1)[0][0]
                anchor = weekday_name_of(anchor_weekday)
            elif cadence == "semimonthly":
                anchor_doms = doms or ()
                anchor = f"the {_ordinal(anchor_doms[0])} and {_ordinal(anchor_doms[1])}"
            else:
                anchor_doms = (_mode_day_of_month([d.day for d in recent_dates]),)
                anchor = f"the {_ordinal(anchor_doms[0])}"

            amount = trimmed_mean_cents(recent_amounts)
            # Ballast, not a live guard: no input reaches it today, because a
            # cluster with two rows on one day is already rejected above, so
            # every value here is a single row capped three orders of
            # magnitude below this bound. It exists because the day-sum path
            # in residual.py DID overflow and this is the same shape; if the
            # same-day rule is ever relaxed, this is what stops a 500.
            if abs(amount) > CENTS_ABS:
                raise ImportRefused(
                    "One recurring charge in this history is too large to plan over. "
                    "Check the export is a single account in one currency."
                )

            last_seen = dates[-1]
            interval = {"weekly": 7, "biweekly": 14, "semimonthly": 15, "monthly": 30}[cadence]
            lapse_after = interval * (LAPSE_INTERVALS_INCOME if kind == "income" else LAPSE_INTERVALS_BILL)
            active = (history_end - last_seen).days <= lapse_after

            # The lexicon labels what the rhythm found; it never decides
            # whether something recurs. Its brand name is discarded.
            category = classify(cluster[0].description).category
            if kind == "income":
                category = UNKNOWN_CATEGORY
            elif category != UNKNOWN_CATEGORY and category not in BILL_LIKE:
                kind = "discretionary"

            streams.append(
                Stream(
                    kind=kind,
                    category=category,
                    label=stream_label(kind, category, cadence),
                    cadence=cadence,
                    anchor=anchor,
                    anchor_weekday=anchor_weekday,
                    anchor_doms=anchor_doms,
                    amount_cents=amount,
                    occurrences=len(dates),
                    last_seen=last_seen,
                    active=active,
                    rows=sorted(cluster, key=lambda r: (r.date, r.index)),
                )
            )

    streams.sort(key=lambda s: (s.kind != "income", s.kind, min(r.date for r in s.rows), s.label))
    return streams, sorted(unscheduled, key=lambda r: r.index)

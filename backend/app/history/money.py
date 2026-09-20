"""Integer cents in, integer cents out. No float touches money here.

Every average in this package rounds exactly once, half to even, through
Decimal. Half-even rather than half-up because these are averages of many
values rather than a price: half-up biases every tie upward, and a per-weekday
estimate repeated across a horizon turns that bias into real dollars.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN

_ONE = Decimal(1)


def mean_cents(values: list[int]) -> int:
    if not values:
        raise ValueError("mean of no values")
    return int((Decimal(sum(values)) / Decimal(len(values))).quantize(_ONE, rounding=ROUND_HALF_EVEN))


def median_cents(values: list[int]) -> int:
    """Median, and for an even count the half-even mean of the middle two.

    The median rather than the mean is what keeps one $900 laptop in the
    history from becoming $112 of "everyday spending" on that weekday for the
    whole horizon.
    """
    if not values:
        raise ValueError("median of no values")
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return mean_cents([ordered[mid - 1], ordered[mid]])


def percentile_cents(values: list[int], fraction: float) -> int:
    """Linear-interpolated percentile, rounded once, half to even.

    Used for the everyday-spending estimate at the 60th percentile rather
    than the 50th. Measured on a real two-year account: the median
    under-predicted the next fortnight's spending 71% of the time, by $115,
    and under-predicting spending is the direction that tells someone they
    are fine when they are not. The 60th cuts that to 52% and $37 while
    staying just as immune to a single large purchase, and its error is
    smaller as well ($147 against $155).
    """
    if not values:
        raise ValueError("percentile of no values")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between 0 and 1")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = Decimal(str(fraction)) * (len(ordered) - 1)
    lower = int(position)
    if lower >= len(ordered) - 1:
        return ordered[-1]
    weight = position - lower
    exact = Decimal(ordered[lower]) + (Decimal(ordered[lower + 1]) - Decimal(ordered[lower])) * weight
    return int(exact.quantize(_ONE, rounding=ROUND_HALF_EVEN))


def trimmed_mean_cents(values: list[int]) -> int:
    """Drop one high and one low, then average — but only from five values up.

    Below five, trimming throws away too much of the evidence: at n=4 it is the
    mean of two, at n=3 the mean of one.
    """
    if not values:
        raise ValueError("mean of no values")
    if len(values) >= 5:
        ordered = sorted(values)
        return mean_cents(ordered[1:-1])
    return mean_cents(values)


def coefficient_of_variation(values: list[int]) -> float:
    """Population stdev over |mean|. Zero when the mean is zero or n < 2.

    |mean|, because these amounts are signed: outflows are negative and a
    negative denominator would make every bill look perfectly stable.
    """
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return (variance**0.5) / abs(mean)

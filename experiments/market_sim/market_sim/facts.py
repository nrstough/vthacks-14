"""Stylized facts: the properties real daily returns share, measured.

The list follows Cont (2001), "Empirical properties of asset returns:
stylized facts and statistical issues". Each check has a numeric threshold
so it can fail. The thresholds were set against two references measured on
the same footing, daily log returns:

| Fact | S&P 500, 1999-2018 | Gaussian, same length |
|---|---:|---:|
| excess kurtosis | 8.17 | -0.10 |
| Hill tail index, top 5% | 2.93 | 6.39 |
| largest abs ACF of returns, lags 1-10 | 0.070 | (small) |
| ACF of abs returns, lag 1 | 0.244 | -0.028 |
| ACF of abs returns, mean of lags 1-50 | 0.232 | (about 0) |
| leverage, mean corr(r[t], abs r[t+k]), k 1-10 | -0.083 | -0.000 |
| skewness | -0.20 | 0.02 |
| excess kurtosis of 5-day sums | 4.14 | (about 0) |

Each threshold sits between the two columns with room on both sides, so a
real index passes and a Gaussian fails. A fact the Gaussian passes too is
the absence of linear autocorrelation, which is about what returns lack.
Its control is an AR(1) series instead.

Aggregational Gaussianity is checked on weekly sums only. Monthly sums give
about 240 observations in twenty years, and one crisis month dominates them:
the S&P sample's monthly excess kurtosis is 7.04, higher than its weekly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Fact:
    name: str
    value: float
    rule: str
    passed: bool


def acf(x: np.ndarray, lags) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    denom = (x * x).sum()
    return np.array([(x[:-k] * x[k:]).sum() / denom for k in lags])


def skewness(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float) - np.mean(x)
    return float((x**3).mean() / (x**2).mean() ** 1.5)


def excess_kurtosis(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float) - np.mean(x)
    return float((x**4).mean() / (x**2).mean() ** 2 - 3)


def hill_tail_index(x: np.ndarray, tail: float = 0.05) -> float:
    """Hill estimate of the tail exponent of |x| from its largest `tail` share.

    Real daily returns sit near 3, the "cubic law". A Gaussian has no power
    tail, and on a fixed share the estimate drifts high, about 6 here.
    """
    a = np.sort(np.abs(np.asarray(x, dtype=float)))[::-1]
    k = max(int(len(a) * tail), 2)
    return float(1 / np.mean(np.log(a[:k] / a[k])))


def leverage(x: np.ndarray, max_lag: int = 10) -> float:
    """Mean correlation between today's return and later absolute returns.

    Negative when a fall raises future volatility more than a rise does.
    """
    x = np.asarray(x, dtype=float)
    return float(np.mean([np.corrcoef(x[:-k], np.abs(x[k:]))[0, 1] for k in range(1, max_lag + 1)]))


def aggregate(x: np.ndarray, days: int) -> np.ndarray:
    n = len(x) // days
    return np.asarray(x[: n * days]).reshape(n, days).sum(axis=1)


def check_index(r: np.ndarray) -> list[Fact]:
    """The single-series facts, for an index or a market factor."""
    r = np.asarray(r, dtype=float)
    kurt = excess_kurtosis(r)
    hill = hill_tail_index(r)
    lin = float(np.abs(acf(r, range(1, 11))).max())
    vol_acf = acf(np.abs(r), range(1, 51))
    lev = leverage(r)
    skew = skewness(r)
    kurt5 = excess_kurtosis(aggregate(r, 5))
    return [
        Fact("fat tails", kurt, "excess kurtosis > 1", kurt > 1),
        Fact("power-law tail", hill, "Hill index (top 5%) < 5", hill < 5),
        Fact("no linear autocorrelation", lin, "max |ACF(r)|, lags 1-10, < 0.1", lin < 0.1),
        Fact("volatility clustering", float(vol_acf[0]), "ACF(|r|) at lag 1 > 0.1", vol_acf[0] > 0.1),
        Fact(
            "slow decay of clustering",
            float(vol_acf.mean()),
            "mean ACF(|r|), lags 1-50, > 0.05",
            vol_acf.mean() > 0.05,
        ),
        Fact("leverage effect", lev, "mean corr(r[t], |r[t+k]|), k 1-10, < -0.02", lev < -0.02),
        Fact("gain/loss asymmetry", skew, "skewness < -0.1", skew < -0.1),
        Fact(
            "aggregational Gaussianity",
            kurt5,
            "5-day excess kurtosis < 1-day",
            kurt5 < kurt,
        ),
    ]


def pairwise_correlation(returns: np.ndarray) -> float:
    c = np.corrcoef(returns, rowvar=False)
    n = len(c)
    return float((c.sum() - n) / (n * (n - 1)))


def crisis_correlation(returns: np.ndarray, window: int = 21) -> tuple[float, float]:
    """Average pairwise correlation on turbulent days and on calm days.

    A day's turbulence is the volatility of the equal-weight index over the
    `window` days before it, excluding the day itself. With the day included,
    picking big-move days would raise measured correlation even in a market
    where it never changes. Turbulent is the top fifth of days, calm the
    bottom half.
    """
    returns = np.asarray(returns, dtype=float)
    index = returns.mean(axis=1)
    trailing = np.full(len(index), np.nan)
    for t in range(window, len(index)):
        trailing[t] = index[t - window : t].std()
    valid = ~np.isnan(trailing)
    hi, lo = np.quantile(trailing[valid], [0.8, 0.5])
    turbulent = valid & (trailing >= hi)
    calm = valid & (trailing <= lo)
    return pairwise_correlation(returns[turbulent]), pairwise_correlation(returns[calm])


def check_cross_section(returns: np.ndarray) -> Fact:
    turbulent, calm = crisis_correlation(returns)
    rise = turbulent - calm
    return Fact(
        "correlations rise in turbulence",
        rise,
        "pairwise correlation, turbulent minus calm days, > 0.05",
        rise > 0.05,
    )

"""Two ways to trade the signals: the oracle's, and the plain one.

The oracle is the ceiling. It knows which signals are real, each one's IC on
each day, and every stock's conditional volatility; it trades only the
idiosyncratic part of returns, as if every factor were hedged perfectly and
for free. No strategy built from `Market.returns` and `Market.signals` can
expect to beat it, so it is the score every other strategy is graded against.
"""

from __future__ import annotations

import math

import numpy as np

from .config import TRADING_DAYS
from .simulate import Market


def annualized_sharpe(daily: np.ndarray) -> float:
    sd = daily.std(ddof=1)
    return float(daily.mean() / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else 0.0


def oracle_returns(market: Market) -> np.ndarray:
    """Daily P&L of the oracle, from day 1 on.

    The weight on stock i is its alpha over its idiosyncratic variance, the
    mean-variance optimum when the residuals are independent across stocks.
    """
    t = market.truth
    weights = t.alpha[1:] / t.idio_vol[1:] ** 2
    return (weights * t.idio_return[1:]).sum(axis=1)


def oracle_sharpe_theory(ic: np.ndarray, n_assets: int) -> float:
    """The oracle's annualized Sharpe ratio in the population, from the IC path.

    On a day where the real signals' squared ICs sum to q, the oracle's P&L
    has mean N*q and variance N*q*(1 + q). This holds because each stock's
    combined signal is Normal(0, q) and the noise has unit variance. Across
    days the law of total variance adds the spread of the daily means. For
    small q this is the fundamental law of active management: IC times the
    square root of breadth.
    """
    q = (np.asarray(ic) ** 2).sum(axis=0)[1:]
    mean_by_day = n_assets * q
    var_by_day = n_assets * q * (1 + q)
    variance = var_by_day.mean() + mean_by_day.var()
    if variance == 0:
        return 0.0
    return float(mean_by_day.mean() / math.sqrt(variance) * math.sqrt(TRADING_DAYS))


def signal_returns(signal: np.ndarray, returns: np.ndarray) -> np.ndarray:
    """Daily returns of trading one signal the plain way, from day 1 on.

    Hold yesterday's signal, demeaned across stocks and scaled to one dollar
    gross, against today's returns. No volatility scaling, no factor hedge, no
    costs: what someone with only the public data would try first.
    """
    held = signal[:-1] - signal[:-1].mean(axis=1, keepdims=True)
    gross = np.abs(held).sum(axis=1, keepdims=True)
    weights = np.divide(held, gross, out=np.zeros_like(held), where=gross > 0)
    return (weights * returns[1:]).sum(axis=1)

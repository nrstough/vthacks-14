"""The stochastic building blocks: a Markov chain, GJR-GARCH, AR(1).

Each takes its random draws as a whole array up front rather than one at a
time inside the loop. That keeps a component's draws the same whatever the
other components do, which is what lets two runs share their noise.
"""

from __future__ import annotations

import math

import numpy as np

from .config import GarchConfig


def stationary(transition: np.ndarray) -> np.ndarray:
    """The long-run share of days spent in each regime."""
    p = np.asarray(transition, dtype=float)
    k = len(p)
    a = p.T - np.eye(k)
    a[-1] = 1.0
    b = np.zeros(k)
    b[-1] = 1.0
    return np.linalg.solve(a, b)


def markov_chain(transition: np.ndarray, n_days: int, rng: np.random.Generator) -> np.ndarray:
    """A regime path that starts from the stationary distribution."""
    p = np.asarray(transition, dtype=float)
    k = len(p)
    u = rng.random(n_days)
    cum = np.cumsum(p, axis=1)
    path = np.empty(n_days, dtype=np.int64)
    # side="right" and the clamp keep a draw that lands on a rounding error
    # in the last cumulative sum inside the matrix.
    path[0] = min(int(np.searchsorted(np.cumsum(stationary(p)), u[0], side="right")), k - 1)
    for t in range(1, n_days):
        path[t] = min(int(np.searchsorted(cum[path[t - 1]], u[t], side="right")), k - 1)
    return path


def standardized_t(rng: np.random.Generator, df: float, shape: tuple[int, ...]) -> np.ndarray:
    """Student-t draws rescaled to unit variance; Gaussian when df is infinite."""
    if math.isinf(df):
        return rng.standard_normal(shape)
    return rng.standard_t(df, shape) * math.sqrt((df - 2) / df)


def garch_omega(target_var: np.ndarray, garch: GarchConfig, jump_var: np.ndarray | float = 0.0) -> np.ndarray:
    """Solve omega so the long-run total variance lands on `target_var`.

    With jumps feeding the recursion, the stationary diffusive variance s
    satisfies s * (1 - persistence) = omega + a * jump_var, where a is the
    average weight on a squared shock, and the total is s + jump_var.
    Treating jumps as negative half the time makes this approximate when
    jumps are present and exact when they are not.
    """
    a = garch.alpha + garch.gamma / 2
    omega = (target_var - jump_var) * (1 - garch.persistence) - a * jump_var
    if np.any(omega <= 0):
        # Jumps feed the recursion, so persistence amplifies their variance.
        raise ValueError(
            "jumps carry more variance than the target volatility leaves room for: "
            "lower the jump rate or size, raise the target volatility, or lower GARCH persistence"
        )
    return omega


def gjr_garch(
    z: np.ndarray,
    omega: np.ndarray,
    regimes: np.ndarray,
    garch: GarchConfig,
    extra: np.ndarray | None = None,
    start_var: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Run GJR-GARCH over `z`, shape (days, series), with omega set by regime.

    `omega` has shape (regimes, series). `extra` is added to each shock after
    scaling, so a jump moves the next day's variance like any other shock.
    Returns the shocks and the conditional volatility, both (days, series).
    Day 0 starts at `start_var`, by default the long-run variance of its
    regime with no jumps.
    """
    n_days, n_series = z.shape
    sigma2 = np.empty((n_days, n_series))
    eps = np.empty((n_days, n_series))
    sigma2[0] = omega[regimes[0]] / (1 - garch.persistence) if start_var is None else start_var
    for t in range(n_days):
        if t:
            prev = eps[t - 1]
            weight = garch.alpha + garch.gamma * (prev < 0)
            sigma2[t] = omega[regimes[t]] + weight * prev * prev + garch.beta * sigma2[t - 1]
        eps[t] = np.sqrt(sigma2[t]) * z[t]
        if extra is not None:
            eps[t] += extra[t]
    return eps, np.sqrt(sigma2)


def ar1(n_days: int, n_series: int, half_life_days: float, rng: np.random.Generator) -> np.ndarray:
    """Unit-variance stationary AR(1) per series, started in its stationary law."""
    phi = 0.5 ** (1 / half_life_days)
    shocks = rng.standard_normal((n_days, n_series))
    out = np.empty_like(shocks)
    out[0] = shocks[0]
    scale = math.sqrt(1 - phi * phi)
    for t in range(1, n_days):
        out[t] = phi * out[t - 1] + scale * shocks[t]
    return out

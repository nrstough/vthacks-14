"""Parameters for one simulated market, with defaults near US large-cap equities.

Rates are annual unless a name says otherwise; the simulator converts them at
252 trading days a year. The defaults are hand-set, not fitted. The market
factor's GARCH and jump settings were picked from a handful of candidates by
how often forty simulated 20-year paths land inside the S&P 500's bootstrap
bands, and tuning stopped there on purpose: chasing the last few points on one
20-year sample is the overfitting this package exists to catch. `report.py`
measures the fit; calibration is a separate, later step.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

TRADING_DAYS = 252


@dataclass(frozen=True)
class GarchConfig:
    """GJR-GARCH(1,1) with Student-t innovations.

    sigma2[t] = omega + (alpha + gamma * [eps[t-1] < 0]) * eps[t-1]**2 + beta * sigma2[t-1]

    `gamma` is the extra weight a negative shock gets, which is what produces
    the leverage effect. `omega` is not a parameter: it is solved per regime so
    that the long-run variance lands on the regime's target volatility.
    `t_df = math.inf` gives Gaussian innovations.
    """

    alpha: float
    gamma: float
    beta: float
    t_df: float

    @property
    def persistence(self) -> float:
        # Innovations are symmetric, so a shock is negative half the time.
        return self.alpha + self.gamma / 2 + self.beta

    def validate(self, where: str) -> None:
        if min(self.alpha, self.gamma, self.beta) < 0:
            raise ValueError(f"{where}: GARCH alpha, gamma and beta must be non-negative")
        if self.persistence >= 1:
            raise ValueError(f"{where}: GARCH persistence {self.persistence:.4f} must be below 1")
        if not self.t_df > 2:
            raise ValueError(f"{where}: t_df must exceed 2 for the variance to exist")


@dataclass(frozen=True)
class RegimeConfig:
    """A hidden Markov chain. Row i of `transition` is the chance of moving
    from regime i to each regime on any one day."""

    names: tuple[str, ...] = ("calm", "turbulent")
    # Calm lasts about 333 trading days on average, turbulence about 100.
    transition: tuple[tuple[float, ...], ...] = ((0.997, 0.003), (0.01, 0.99))

    @property
    def n(self) -> int:
        return len(self.names)


@dataclass(frozen=True)
class MarketFactorConfig:
    """The index-like common factor every stock loads on."""

    # Target long-run volatility in each regime, jumps included.
    annual_vol: tuple[float, ...] = (0.13, 0.30)
    # Expected log return in each regime. Jumps are compensated, so this is
    # the mean including them.
    annual_drift: tuple[float, ...] = (0.12, -0.20)
    # Nearly all of the shock weight sits on falls, as in published GJR fits
    # to the S&P 500; it is what produces the leverage effect.
    garch: GarchConfig = field(
        default_factory=lambda: GarchConfig(alpha=0.0, gamma=0.14, beta=0.91, t_df=8.0)
    )
    jumps_per_year: tuple[float, ...] = (0.5, 2.0)
    jump_mean: float = -0.03
    jump_sd: float = 0.02


@dataclass(frozen=True)
class SectorConfig:
    """Zero-drift sector factors. Stock i belongs to sector i % n_sectors."""

    n_sectors: int = 5
    annual_vol: tuple[float, ...] = (0.08, 0.14)
    garch: GarchConfig = field(
        default_factory=lambda: GarchConfig(alpha=0.04, gamma=0.04, beta=0.92, t_df=6.0)
    )


@dataclass(frozen=True)
class StockConfig:
    n_assets: int = 50
    beta_mean: float = 1.0
    beta_sd: float = 0.25
    beta_bounds: tuple[float, float] = (0.3, 2.0)
    # Idiosyncratic volatility is lognormal across stocks around this median.
    idio_vol_median: float = 0.20
    idio_vol_log_sd: float = 0.3
    # Idiosyncratic volatility rises less than the market's in turbulence,
    # which is what makes correlations climb in a crisis.
    idio_regime_multiplier: tuple[float, ...] = (1.0, 1.3)
    garch: GarchConfig = field(
        default_factory=lambda: GarchConfig(alpha=0.05, gamma=0.05, beta=0.90, t_df=5.0)
    )


@dataclass(frozen=True)
class SignalConfig:
    """One real, planted signal. This is the answer key.

    `ic` is the correlation between the signal at the close of day t-1 and
    the idiosyncratic return on day t divided by that day's conditional
    idiosyncratic volatility. It is exact in the population, and it is the
    quantity a strategy is trying to find.
    """

    ic: float
    # The signal is a unit-variance AR(1) per stock with this half-life.
    half_life_days: float = 5.0
    # Regimes in which the signal works; None means all of them.
    active_regimes: tuple[int, ...] | None = None
    # Crowding: the IC halves every this many days. None means it never decays.
    ic_half_life_days: float | None = None


@dataclass(frozen=True)
class MarketConfig:
    n_days: int = 10 * TRADING_DAYS
    regimes: RegimeConfig = field(default_factory=RegimeConfig)
    market: MarketFactorConfig = field(default_factory=MarketFactorConfig)
    sectors: SectorConfig = field(default_factory=SectorConfig)
    stocks: StockConfig = field(default_factory=StockConfig)
    signals: tuple[SignalConfig, ...] = (SignalConfig(ic=0.01),)
    # Signals with no predictive power, shuffled in among the real ones.
    n_decoys: int = 19
    # None copies the real signals' half-lives in turn, so a decoy cannot be
    # told apart by its autocorrelation. With no real signals it falls back
    # to five days.
    decoy_half_life_days: float | None = None

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        k = self.regimes.n
        if self.n_days < 2:
            raise ValueError("n_days must be at least 2")
        if len(self.regimes.transition) != k or any(len(row) != k for row in self.regimes.transition):
            raise ValueError(f"transition must be {k}x{k}, one row and column per regime name")
        for row in self.regimes.transition:
            if any(p < 0 or p > 1 for p in row) or not math.isclose(sum(row), 1.0, abs_tol=1e-9):
                raise ValueError(f"each transition row must be probabilities summing to 1, got {row}")
        # The first day's regime is drawn from the long-run distribution, so
        # there has to be exactly one. Two regimes that never reach each other
        # are two separate markets: simulate them separately.
        p = np.array(self.regimes.transition, dtype=float)
        if np.linalg.matrix_rank(p.T - np.eye(k)) != k - 1:
            raise ValueError("the regime chain has more than one closed set of regimes, so no single long run")
        per_regime = {
            "market.annual_vol": self.market.annual_vol,
            "market.annual_drift": self.market.annual_drift,
            "market.jumps_per_year": self.market.jumps_per_year,
            "sectors.annual_vol": self.sectors.annual_vol,
            "stocks.idio_regime_multiplier": self.stocks.idio_regime_multiplier,
        }
        for name, values in per_regime.items():
            if len(values) != k:
                raise ValueError(f"{name} needs one value per regime ({k}), got {len(values)}")
        if any(v <= 0 for v in self.market.annual_vol + self.sectors.annual_vol):
            raise ValueError("volatilities must be positive")
        if any(m <= 0 for m in self.stocks.idio_regime_multiplier):
            raise ValueError("idio_regime_multiplier must be positive")
        if any(j < 0 for j in self.market.jumps_per_year) or self.market.jump_sd < 0:
            raise ValueError("jump rates and jump_sd must be non-negative")
        if any(j / TRADING_DAYS > 1 for j in self.market.jumps_per_year):
            raise ValueError("at most one jump a day: jumps_per_year must not exceed 252")
        self.market.garch.validate("market")
        self.sectors.garch.validate("sectors")
        self.stocks.garch.validate("stocks")
        if self.sectors.n_sectors < 0:
            raise ValueError("n_sectors must be non-negative")
        if self.stocks.n_assets < 2:
            raise ValueError("n_assets must be at least 2")
        lo, hi = self.stocks.beta_bounds
        if not lo <= hi:
            raise ValueError("beta_bounds must be (low, high)")
        if self.stocks.idio_vol_median <= 0 or self.stocks.idio_vol_log_sd < 0:
            raise ValueError("idio_vol_median must be positive and idio_vol_log_sd non-negative")
        if self.n_decoys < 0:
            raise ValueError("n_decoys must be non-negative")
        if self.decoy_half_life_days is not None and self.decoy_half_life_days <= 0:
            raise ValueError("decoy_half_life_days must be positive")
        for s in self.signals:
            if not -1 < s.ic < 1:
                raise ValueError(f"ic must lie strictly between -1 and 1, got {s.ic}")
            if s.half_life_days <= 0:
                raise ValueError("half_life_days must be positive")
            if s.ic_half_life_days is not None and s.ic_half_life_days <= 0:
                raise ValueError("ic_half_life_days must be positive")
            if s.active_regimes is not None and any(r not in range(k) for r in s.active_regimes):
                raise ValueError(f"active_regimes must index the {k} regimes, got {s.active_regimes}")
        # The signals' shares of idiosyncratic variance are carved out of one
        # unit, so together they must leave room for noise.
        if sum(s.ic**2 for s in self.signals) >= 1:
            raise ValueError("the squared ICs must sum to less than 1")

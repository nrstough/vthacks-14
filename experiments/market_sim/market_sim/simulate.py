"""Assemble one market: a common factor, sectors, stocks and planted signals.

Timing is the contract a strategy depends on, so it is stated once here:

* `returns[t]` is the log return over trading day t.
* `signals[j, t]` is known at the close of day t. It may be used to trade
  day t + 1 and never day t.
* The regime for day t is drawn at the close of day t - 1. A strategy never
  sees it; the answer key's expected returns condition on it.

`Market.returns` and `Market.signals` are what a strategy may look at.
Everything in `Market.truth` is the answer key.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import TRADING_DAYS, MarketConfig
from .processes import ar1, garch_omega, gjr_garch, markov_chain, standardized_t

# One independent random stream per component, spawned in this order.
# Append new components at the end: inserting one shifts every stream after
# it, and every market generated after the change becomes a different
# market while every test keeps passing.
STREAMS = ("regimes", "market", "jumps", "sectors", "loadings", "idio", "signals", "decoys", "shuffle")

DEFAULT_DECOY_HALF_LIFE = 5.0


@dataclass(frozen=True)
class AnswerKey:
    regimes: np.ndarray  # (days,) regime index for each day
    real_signals: tuple[int, ...]  # where each configured signal sits in Market.signals
    ic: np.ndarray  # (real signals, days) IC in force for day t's return; zero on day 0
    expected_return: np.ndarray  # (days, assets) E[returns[t] | everything known at the close of t-1]
    alpha: np.ndarray  # (days, assets) the part of expected_return the signals supply
    market_return: np.ndarray  # (days,)
    market_vol: np.ndarray  # (days,) conditional volatility, jumps included
    sector_of: np.ndarray  # (assets,)
    sector_return: np.ndarray  # (days, sectors)
    sector_vol: np.ndarray  # (days, sectors)
    betas: np.ndarray  # (assets,)
    idio_return: np.ndarray  # (days, assets) alpha plus idiosyncratic noise
    idio_vol: np.ndarray  # (days, assets) conditional idiosyncratic volatility


@dataclass(frozen=True)
class Market:
    config: MarketConfig
    seed: int
    returns: np.ndarray  # (days, assets)
    signals: np.ndarray  # (signals, days, assets), real and decoy, shuffled
    truth: AnswerKey

    @property
    def prices(self) -> np.ndarray:
        """Price paths starting at 100."""
        return 100 * np.exp(np.cumsum(self.returns, axis=0))


def _streams(seed: int) -> dict[str, np.random.SeedSequence]:
    return dict(zip(STREAMS, np.random.SeedSequence(seed).spawn(len(STREAMS))))


def _rng(seq: np.random.SeedSequence) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(seq))


def simulate(config: MarketConfig | None = None, seed: int = 0) -> Market:
    cfg = config or MarketConfig()
    n_days, n_assets = cfg.n_days, cfg.stocks.n_assets
    streams = _streams(seed)

    regimes = markov_chain(np.array(cfg.regimes.transition), n_days, _rng(streams["regimes"]))

    market, market_vol = _market_factor(cfg, regimes, streams)
    sector_of, sector_return, sector_vol = _sectors(cfg, regimes, streams)
    betas, idio_target = _loadings(cfg, streams)

    # Idiosyncratic volatility runs on the noise draw alone, before the
    # signals take their share. So a change of IC moves no volatility path,
    # and two markets that differ only in IC share all of their noise.
    g = cfg.stocks.garch
    multiplier = np.array(cfg.stocks.idio_regime_multiplier)[:, None]
    idio_var = (multiplier * idio_target[None, :]) ** 2 / TRADING_DAYS
    z_idio = standardized_t(_rng(streams["idio"]), g.t_df, (n_days, n_assets))
    noise, idio_vol = gjr_garch(z_idio, garch_omega(idio_var, g), regimes, g)

    real, ic = _real_signals(cfg, regimes, streams)
    # Day t's alpha comes from the signal known at the close of day t-1.
    combined = np.zeros((n_days, n_assets))
    for k, panel in enumerate(real):
        combined[1:] += ic[k, 1:, None] * panel[:-1]
    share = (ic**2).sum(axis=0)
    alpha = idio_vol * combined
    idio_return = alpha + np.sqrt(1 - share)[:, None] * noise

    returns = betas * market[:, None] + sector_return[:, sector_of] + idio_return
    drift = np.array(cfg.market.annual_drift)[regimes] / TRADING_DAYS
    expected_return = betas * drift[:, None] + alpha

    signals, real_index = _panel(cfg, real, streams)

    truth = AnswerKey(
        regimes=regimes,
        real_signals=real_index,
        ic=ic,
        expected_return=expected_return,
        alpha=alpha,
        market_return=market,
        market_vol=market_vol,
        sector_of=sector_of,
        sector_return=sector_return,
        sector_vol=sector_vol,
        betas=betas,
        idio_return=idio_return,
        idio_vol=idio_vol,
    )
    return Market(config=cfg, seed=seed, returns=returns, signals=signals, truth=truth)


def _market_factor(cfg: MarketConfig, regimes: np.ndarray, streams) -> tuple[np.ndarray, np.ndarray]:
    m = cfg.market
    n_days = cfg.n_days
    target = np.array(m.annual_vol) ** 2 / TRADING_DAYS
    p_jump = np.array(m.jumps_per_year) / TRADING_DAYS
    # Variance of one day's jump term: Bernoulli(p) times Normal(mean, sd).
    jump_var = p_jump * (m.jump_mean**2 + m.jump_sd**2) - (p_jump * m.jump_mean) ** 2

    # Arrival and size are drawn for every day, jump or not, so the jump
    # draws never depend on the regime path.
    rng_j = _rng(streams["jumps"])
    arrival = rng_j.random(n_days)
    size = m.jump_mean + m.jump_sd * rng_j.standard_normal(n_days)
    p_today = p_jump[regimes]
    # Compensated, so the jump term has mean zero and the drift is the mean.
    jumps = np.where(arrival < p_today, size, 0.0) - p_today * m.jump_mean

    omega = garch_omega(target, m.garch, jump_var)[:, None]
    z = standardized_t(_rng(streams["market"]), m.garch.t_df, (n_days, 1))
    start = (target - jump_var)[regimes[0]]
    eps, sigma = gjr_garch(z, omega, regimes, m.garch, extra=jumps[:, None], start_var=np.array([start]))

    drift = np.array(m.annual_drift)[regimes] / TRADING_DAYS
    vol = np.sqrt(sigma[:, 0] ** 2 + jump_var[regimes])
    return drift + eps[:, 0], vol


def _sectors(cfg: MarketConfig, regimes: np.ndarray, streams) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    s = cfg.sectors
    n_days, n_assets = cfg.n_days, cfg.stocks.n_assets
    if s.n_sectors == 0:
        # A single all-zero column keeps the indexing below uniform.
        return np.zeros(n_assets, dtype=np.int64), np.zeros((n_days, 1)), np.zeros((n_days, 1))
    target = np.array(s.annual_vol) ** 2 / TRADING_DAYS
    omega = np.repeat(garch_omega(target, s.garch)[:, None], s.n_sectors, axis=1)
    z = standardized_t(_rng(streams["sectors"]), s.garch.t_df, (n_days, s.n_sectors))
    eps, sigma = gjr_garch(z, omega, regimes, s.garch)
    return np.arange(n_assets) % s.n_sectors, eps, sigma


def _loadings(cfg: MarketConfig, streams) -> tuple[np.ndarray, np.ndarray]:
    st = cfg.stocks
    rng = _rng(streams["loadings"])
    betas = np.clip(st.beta_mean + st.beta_sd * rng.standard_normal(st.n_assets), *st.beta_bounds)
    idio_target = st.idio_vol_median * np.exp(st.idio_vol_log_sd * rng.standard_normal(st.n_assets))
    return betas, idio_target


def _real_signals(cfg: MarketConfig, regimes: np.ndarray, streams) -> tuple[list[np.ndarray], np.ndarray]:
    n_days, n_assets = cfg.n_days, cfg.stocks.n_assets
    # One child stream per signal, so adding a second signal leaves the
    # first one exactly as it was.
    seqs = streams["signals"].spawn(len(cfg.signals))
    days = np.arange(n_days)
    panels, ic = [], np.zeros((len(cfg.signals), n_days))
    for k, (spec, seq) in enumerate(zip(cfg.signals, seqs)):
        panels.append(ar1(n_days, n_assets, spec.half_life_days, _rng(seq)))
        on = np.ones(n_days) if spec.active_regimes is None else np.isin(regimes, spec.active_regimes)
        decay = 1.0 if spec.ic_half_life_days is None else 0.5 ** (days / spec.ic_half_life_days)
        ic[k] = spec.ic * on * decay
    # Day 0 has no prior close to have formed a signal at.
    ic[:, 0] = 0.0
    return panels, ic


def _panel(cfg: MarketConfig, real: list[np.ndarray], streams) -> tuple[np.ndarray, tuple[int, ...]]:
    n_days, n_assets = cfg.n_days, cfg.stocks.n_assets
    seqs = streams["decoys"].spawn(cfg.n_decoys)
    decoys = []
    for d, seq in enumerate(seqs):
        if cfg.decoy_half_life_days is not None:
            half_life = cfg.decoy_half_life_days
        elif cfg.signals:
            half_life = cfg.signals[d % len(cfg.signals)].half_life_days
        else:
            half_life = DEFAULT_DECOY_HALF_LIFE
        decoys.append(ar1(n_days, n_assets, half_life, _rng(seq)))
    every = real + decoys
    if not every:
        return np.zeros((0, n_days, n_assets)), ()
    order = _rng(streams["shuffle"]).permutation(len(every))
    panel = np.stack([every[i] for i in order])
    position = np.argsort(order)
    return panel, tuple(int(position[k]) for k in range(len(real)))

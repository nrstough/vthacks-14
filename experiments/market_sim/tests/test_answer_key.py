"""The answer key has to be right, or every grade built on it is wrong.

These are statistical checks on fixed seeds: deterministic, so they cannot
flake, with tolerances of about four standard errors so that an honest
change to the draws does not trip them.
"""

import dataclasses

import numpy as np
import pytest

from market_sim import (
    MarketConfig,
    SignalConfig,
    StockConfig,
    annualized_sharpe,
    oracle_returns,
    oracle_sharpe_theory,
    signal_returns,
    simulate,
)

CFG = MarketConfig(
    n_days=2520, stocks=StockConfig(n_assets=50), signals=(SignalConfig(ic=0.05),), n_decoys=5
)


def pooled_ic(signal, idio_return, idio_vol):
    """Correlation of yesterday's signal with today's vol-scaled residual."""
    x = signal[:-1].ravel()
    y = (idio_return[1:] / idio_vol[1:]).ravel()
    return np.corrcoef(x, y)[0, 1], 1 / np.sqrt(len(x))


def test_the_planted_ic_is_what_the_data_shows():
    m = simulate(CFG, seed=11)
    ic, se = pooled_ic(m.signals[m.truth.real_signals[0]], m.truth.idio_return, m.truth.idio_vol)
    assert ic == pytest.approx(0.05, abs=4 * se)


def test_the_ic_is_exact_even_when_it_is_large():
    # At a realistic IC the noise rescaling is invisible, so a strong signal
    # is what shows the residual keeps unit variance and the IC stays exact.
    m = simulate(dataclasses.replace(CFG, signals=(SignalConfig(ic=0.6),)), seed=15)
    t = m.truth
    ic, se = pooled_ic(m.signals[t.real_signals[0]], t.idio_return, t.idio_vol)
    assert ic == pytest.approx(0.6, abs=4 * se)
    assert np.var(t.idio_return[1:] / t.idio_vol[1:]) == pytest.approx(1.0, abs=0.02)


def test_decoys_predict_nothing():
    m = simulate(CFG, seed=11)
    real = set(m.truth.real_signals)
    for j in range(len(m.signals)):
        if j in real:
            continue
        ic, se = pooled_ic(m.signals[j], m.truth.idio_return, m.truth.idio_vol)
        assert abs(ic) < 4 * se, j


def test_what_is_left_after_alpha_is_unpredictable():
    m = simulate(CFG, seed=12)
    t = m.truth
    signal = m.signals[t.real_signals[0]]
    ic, se = pooled_ic(signal, t.idio_return - t.alpha, t.idio_vol)
    assert abs(ic) < 4 * se


def test_a_regime_gated_signal_works_only_in_its_regime():
    cfg = dataclasses.replace(CFG, n_days=5040, signals=(SignalConfig(ic=0.05, active_regimes=(0,)),))
    m = simulate(cfg, seed=13)
    t = m.truth
    signal = m.signals[t.real_signals[0]]
    calm = t.regimes[1:] == 0
    x, y = signal[:-1], t.idio_return[1:] / t.idio_vol[1:]
    ic_calm = np.corrcoef(x[calm].ravel(), y[calm].ravel())[0, 1]
    ic_turb = np.corrcoef(x[~calm].ravel(), y[~calm].ravel())[0, 1]
    assert ic_calm == pytest.approx(0.05, abs=4 / np.sqrt(calm.sum() * 50))
    assert abs(ic_turb) < 4 / np.sqrt((~calm).sum() * 50)


def test_oracle_theory_matches_the_fundamental_law_for_a_constant_ic():
    ic = np.full((1, 1000), 0.02)
    # IC times root breadth, annualized, with the exact (1 + q) correction.
    q = 0.02**2
    assert oracle_sharpe_theory(ic, 50) == pytest.approx(np.sqrt(50 * q / (1 + q)) * np.sqrt(252))


def test_the_oracle_earns_its_theoretical_sharpe_on_average():
    cfg = dataclasses.replace(CFG, n_days=1260, signals=(SignalConfig(ic=0.02),), n_decoys=0)
    realized = [annualized_sharpe(oracle_returns(simulate(cfg, seed=s))) for s in range(30)]
    theory = oracle_sharpe_theory(simulate(cfg, seed=0).truth.ic, 50)
    se = np.std(realized, ddof=1) / np.sqrt(len(realized))
    assert np.mean(realized) == pytest.approx(theory, abs=4 * se)


def test_the_oracle_pnl_has_the_daily_mean_and_variance_the_theory_states():
    # Sharpe ratios are blind to scale; the daily moments are not.
    cfg = dataclasses.replace(CFG, signals=(SignalConfig(ic=0.02),), n_decoys=0)
    pnl = oracle_returns(simulate(cfg, seed=16))
    q, n = 0.02**2, 50
    assert pnl.mean() == pytest.approx(n * q, abs=4 * np.sqrt(n * q * (1 + q) / len(pnl)))
    assert pnl.var() == pytest.approx(n * q * (1 + q), rel=0.1)


def test_the_oracle_beats_the_plain_strategy_on_the_same_signal():
    m = simulate(CFG, seed=14)
    oracle = annualized_sharpe(oracle_returns(m))
    plain = annualized_sharpe(signal_returns(m.signals[m.truth.real_signals[0]], m.returns))
    assert oracle > plain > 0


def test_the_plain_strategy_trades_yesterdays_signal_against_todays_return():
    returns = np.array([[0.0, 0.0], [0.01, -0.01], [0.02, 0.0]])
    signal = np.array([[1.0, -1.0], [-1.0, 1.0], [5.0, 5.0]])
    # Day 1 holds day 0's signal: +0.5 / -0.5, earning 0.005 + 0.005.
    # Day 2 holds day 1's signal: -0.5 / +0.5, earning -0.01.
    assert signal_returns(signal, returns) == pytest.approx([0.01, -0.01])

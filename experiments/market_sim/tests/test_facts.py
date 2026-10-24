"""The simulator reproduces the stylized facts, and the checks have teeth.

A check that a Gaussian also passes proves nothing, so every fact the
default market is held to has a negative control that must fail it.
"""

import numpy as np
import pytest

from market_sim import MarketConfig, StockConfig, simulate
from market_sim.facts import check_cross_section, check_index, crisis_correlation

N = 2520


def facts_by_name(series):
    return {f.name: f for f in check_index(series)}


@pytest.fixture(scope="module")
def default_markets():
    return [simulate(seed=s) for s in range(10)]


@pytest.fixture(scope="module")
def market_factor_facts():
    # The market factor has its own streams, so these are the default
    # market's factors; leaving out the stocks and signals makes forty cheap.
    cfg = MarketConfig(n_days=N, stocks=StockConfig(n_assets=2), signals=(), n_decoys=0)
    return [facts_by_name(simulate(cfg, seed=s).truth.market_return) for s in range(40)]


# Minimums sit about three binomial standard errors below the pass rate
# measured over 200 ten-year paths, so an honest change to the draws does not
# trip them and a broken mechanism does.
@pytest.mark.parametrize(
    "fact, measured, minimum",
    [
        ("fat tails", 1.000, 0.9),
        ("power-law tail", 1.000, 0.9),
        ("volatility clustering", 1.000, 0.9),
        ("slow decay of clustering", 1.000, 0.9),
        ("leverage effect", 0.995, 0.9),
        # Real returns fail these two in some stretches too: the S&P 500's
        # block bootstrap passes them 90% and 78% of the time over 20 years.
        ("no linear autocorrelation", 0.905, 0.75),
        ("aggregational Gaussianity", 0.810, 0.6),
    ],
)
def test_the_default_market_factor_shows_the_fact(market_factor_facts, fact, measured, minimum):
    assert np.mean([row[fact].passed for row in market_factor_facts]) >= minimum


def test_gain_loss_asymmetry_points_the_right_way_on_average(market_factor_facts):
    # The weakest fact, passing in 47% of ten-year paths. Innovations are
    # symmetric, so the downside skew comes only from leverage and rare
    # negative jumps, and it is noisy path to path.
    assert np.median([row["gain/loss asymmetry"].value for row in market_factor_facts]) < 0


def test_correlations_rise_in_turbulence(default_markets):
    assert all(check_cross_section(m.returns).passed for m in default_markets)


def test_single_stocks_have_fat_tails_and_clustering(default_markets):
    m = default_markets[0]
    for i in range(0, 50, 10):
        facts = facts_by_name(m.returns[:, i])
        assert facts["fat tails"].passed and facts["volatility clustering"].passed, i


def test_a_gaussian_fails_every_fact_about_tails_clustering_and_leverage():
    gaussian = np.random.default_rng(0).standard_normal(N) * 0.01
    facts = facts_by_name(gaussian)
    for name in ("fat tails", "power-law tail", "volatility clustering", "slow decay of clustering", "leverage effect"):
        assert not facts[name].passed, name


def test_an_autocorrelated_series_fails_the_no_autocorrelation_fact():
    rng = np.random.default_rng(1)
    x = np.zeros(N)
    shocks = rng.standard_normal(N)
    for t in range(1, N):
        x[t] = 0.3 * x[t - 1] + shocks[t]
    assert not facts_by_name(x)["no linear autocorrelation"].passed


def test_fat_tails_without_clustering_pass_one_and_fail_the_other():
    t4 = np.random.default_rng(2).standard_t(4, N)
    facts = facts_by_name(t4)
    assert facts["fat tails"].passed
    assert not facts["volatility clustering"].passed


def test_a_market_whose_correlation_never_changes_fails_the_crisis_fact():
    rng = np.random.default_rng(3)
    common = rng.standard_normal((N, 1))
    panel = 0.5 * common + rng.standard_normal((N, 30))
    turbulent, calm = crisis_correlation(panel)
    assert abs(turbulent - calm) < 0.05
    assert not check_cross_section(panel).passed

import math

import numpy as np
import pytest

from market_sim.config import GarchConfig
from market_sim.facts import excess_kurtosis
from market_sim.processes import ar1, garch_omega, gjr_garch, markov_chain, standardized_t, stationary


def rng(seed=0):
    return np.random.default_rng(seed)


def test_stationary_distribution_of_the_default_chain():
    p = np.array([[0.997, 0.003], [0.01, 0.99]])
    # Share of time turbulent = 0.003 / (0.003 + 0.01).
    assert stationary(p) == pytest.approx([10 / 13, 3 / 13])


def test_a_long_chain_spends_the_stationary_share_in_each_regime_and_moves_at_the_stated_rate():
    p = np.array([[0.95, 0.05], [0.10, 0.90]])
    path = markov_chain(p, 200_000, rng())
    assert np.bincount(path, minlength=2) / len(path) == pytest.approx(stationary(p), abs=0.01)
    leaving_0 = np.mean(path[1:][path[:-1] == 0] == 1)
    leaving_1 = np.mean(path[1:][path[:-1] == 1] == 0)
    assert leaving_0 == pytest.approx(0.05, abs=0.003)
    assert leaving_1 == pytest.approx(0.10, abs=0.005)


def test_a_chain_with_an_absorbing_regime_ends_up_there():
    # Regime 1 drains into regime 0 and never returns: the long run is all 0.
    p = np.array([[1.0, 0.0], [0.5, 0.5]])
    assert stationary(p) == pytest.approx([1.0, 0.0])
    assert np.all(markov_chain(p, 500, rng(3)) == 0)


def test_standardized_t_has_unit_variance_and_infinite_df_is_gaussian():
    draws = standardized_t(rng(), 6.0, (400_000,))
    assert draws.var() == pytest.approx(1.0, abs=0.02)
    assert excess_kurtosis(draws) > 1.5  # population value 3 for t(6)
    gaussian = standardized_t(rng(), math.inf, (400_000,))
    assert excess_kurtosis(gaussian) == pytest.approx(0.0, abs=0.05)


def test_constant_variance_when_garch_is_switched_off():
    g = GarchConfig(alpha=0.0, gamma=0.0, beta=0.0, t_df=math.inf)
    z = standardized_t(rng(), g.t_df, (100_000, 1))
    eps, sigma = gjr_garch(z, np.array([[1e-4]]), np.zeros(100_000, dtype=np.int64), g)
    assert np.all(sigma == pytest.approx(0.01))
    assert eps.std() == pytest.approx(0.01, rel=0.01)


@pytest.mark.parametrize("t_df", [math.inf, 8.0])
def test_long_run_variance_lands_on_the_target(t_df):
    g = GarchConfig(alpha=0.03, gamma=0.10, beta=0.90, t_df=t_df)
    target = np.array([0.16**2 / 252])
    z = standardized_t(rng(1), t_df, (400_000, 1))
    eps, _ = gjr_garch(z, garch_omega(target, g)[:, None], np.zeros(400_000, dtype=np.int64), g)
    assert eps.var() == pytest.approx(target[0], rel=0.05)


def test_a_fall_raises_tomorrows_variance_more_than_a_rise_of_the_same_size():
    g = GarchConfig(alpha=0.02, gamma=0.10, beta=0.85, t_df=math.inf)
    omega = np.array([[1e-5, 1e-5]])
    z = np.array([[-3.0, 3.0], [0.0, 0.0]])
    _, sigma = gjr_garch(z, omega, np.zeros(2, dtype=np.int64), g)
    assert sigma[1, 0] > sigma[1, 1]


def test_omega_refuses_jumps_bigger_than_the_target_allows():
    g = GarchConfig(alpha=0.03, gamma=0.10, beta=0.90, t_df=6.0)
    with pytest.raises(ValueError, match="jumps carry more variance"):
        garch_omega(np.array([1e-4]), g, jump_var=np.array([2e-4]))


def test_ar1_is_unit_variance_with_the_stated_half_life():
    x = ar1(200_000, 2, half_life_days=5.0, rng=rng())
    assert x.var(axis=0) == pytest.approx([1.0, 1.0], abs=0.03)
    lag5 = np.corrcoef(x[:-5, 0], x[5:, 0])[0, 1]
    assert lag5 == pytest.approx(0.5, abs=0.02)

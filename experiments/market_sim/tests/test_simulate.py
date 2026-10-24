import dataclasses

import numpy as np
import pytest

from market_sim import STREAMS, MarketConfig, SectorConfig, SignalConfig, StockConfig, simulate

SMALL = MarketConfig(n_days=300, stocks=StockConfig(n_assets=12), n_decoys=4)


def test_shapes_and_finiteness():
    m = simulate(SMALL, seed=1)
    assert m.returns.shape == (300, 12)
    assert m.signals.shape == (5, 300, 12)
    t = m.truth
    assert t.regimes.shape == (300,)
    assert t.ic.shape == (1, 300)
    for name in ("expected_return", "alpha", "idio_return", "idio_vol"):
        assert getattr(t, name).shape == (300, 12), name
    assert t.sector_return.shape == (300, 5)
    for arr in (m.returns, m.signals, t.expected_return, t.idio_vol, t.market_vol):
        assert np.all(np.isfinite(arr))
    assert np.all(t.idio_vol > 0) and np.all(t.market_vol > 0)


def test_prices_start_from_100_and_follow_the_returns():
    m = simulate(SMALL, seed=1)
    assert m.prices[0] == pytest.approx(100 * np.exp(m.returns[0]))
    assert np.log(m.prices[-1] / m.prices[0]) == pytest.approx(m.returns[1:].sum(axis=0))


def test_same_seed_same_market_and_a_new_seed_a_new_one():
    a, b, c = simulate(SMALL, seed=7), simulate(SMALL, seed=7), simulate(SMALL, seed=8)
    assert np.array_equal(a.returns, b.returns)
    assert np.array_equal(a.signals, b.signals)
    assert not np.array_equal(a.returns, c.returns)


def test_the_stream_order_is_pinned():
    # Appending is safe; inserting or reordering resamples every market.
    assert STREAMS == ("regimes", "market", "jumps", "sectors", "loadings", "idio", "signals", "decoys", "shuffle")


def test_more_decoys_leave_the_market_and_the_earlier_decoys_unchanged():
    few = simulate(dataclasses.replace(SMALL, n_decoys=3), seed=2)
    many = simulate(dataclasses.replace(SMALL, n_decoys=9), seed=2)
    assert np.array_equal(few.returns, many.returns)
    assert np.array_equal(few.truth.expected_return, many.truth.expected_return)
    real_few = few.signals[few.truth.real_signals[0]]
    real_many = many.signals[many.truth.real_signals[0]]
    assert np.array_equal(real_few, real_many)
    # Every panel in the smaller set appears unchanged in the larger one.
    for panel in few.signals:
        assert any(np.array_equal(panel, other) for other in many.signals)


def test_changing_the_ic_shares_all_of_the_noise():
    weak = simulate(dataclasses.replace(SMALL, signals=(SignalConfig(ic=0.0),)), seed=3)
    strong = simulate(dataclasses.replace(SMALL, signals=(SignalConfig(ic=0.05),)), seed=3)
    for name in ("regimes", "market_return", "market_vol", "sector_return", "idio_vol", "betas"):
        assert np.array_equal(getattr(weak.truth, name), getattr(strong.truth, name)), name
    assert np.array_equal(weak.signals, strong.signals)
    assert not np.array_equal(weak.returns, strong.returns)
    assert np.all(weak.truth.alpha == 0)


def test_a_second_real_signal_leaves_the_first_unchanged():
    one = simulate(dataclasses.replace(SMALL, signals=(SignalConfig(ic=0.03),)), seed=4)
    two = simulate(dataclasses.replace(SMALL, signals=(SignalConfig(ic=0.03), SignalConfig(ic=0.02))), seed=4)
    first_one = one.signals[one.truth.real_signals[0]]
    first_two = two.signals[two.truth.real_signals[0]]
    assert np.array_equal(first_one, first_two)


def test_alpha_on_day_t_comes_from_the_signal_known_at_the_close_of_day_t_minus_1():
    m = simulate(dataclasses.replace(SMALL, signals=(SignalConfig(ic=0.04),)), seed=5)
    t = m.truth
    signal = m.signals[t.real_signals[0]]
    assert np.all(t.alpha[0] == 0)
    expected = t.idio_vol[1:] * t.ic[0, 1:, None] * signal[:-1]
    assert t.alpha[1:] == pytest.approx(expected)


def test_expected_return_is_beta_times_regime_drift_plus_alpha():
    m = simulate(SMALL, seed=6)
    t = m.truth
    drift = np.array(SMALL.market.annual_drift)[t.regimes] / 252
    assert t.expected_return == pytest.approx(t.betas * drift[:, None] + t.alpha)


def test_the_drift_is_the_mean_with_jumps_included():
    from market_sim import MarketFactorConfig, RegimeConfig

    # Ten 3% crashes a year would cost 30% a year if the jumps were not
    # compensated; the factor's mean must still be the stated drift.
    cfg = MarketConfig(
        n_days=50_000,
        regimes=RegimeConfig(names=("only",), transition=((1.0,),)),
        market=MarketFactorConfig(annual_vol=(0.40,), annual_drift=(0.05,), jumps_per_year=(10.0,)),
        sectors=SectorConfig(annual_vol=(0.08,)),
        stocks=StockConfig(n_assets=2, idio_regime_multiplier=(1.0,)),
        signals=(),
        n_decoys=0,
    )
    market = simulate(cfg, seed=11).truth.market_return
    assert market.mean() == pytest.approx(0.05 / 252, abs=4 * market.std() / np.sqrt(len(market)))
    assert market.std() * np.sqrt(252) == pytest.approx(0.40, rel=0.1)


def test_returns_are_the_sum_of_their_parts():
    m = simulate(SMALL, seed=6)
    t = m.truth
    rebuilt = t.betas * t.market_return[:, None] + t.sector_return[:, t.sector_of] + t.idio_return
    assert m.returns == pytest.approx(rebuilt)


def test_ic_is_zero_on_day_0_and_outside_its_regimes_and_halves_on_schedule():
    cfg = dataclasses.replace(
        SMALL,
        n_days=2000,
        signals=(SignalConfig(ic=0.04, active_regimes=(0,)), SignalConfig(ic=0.04, ic_half_life_days=100)),
    )
    m = simulate(cfg, seed=7)
    gated, decaying = m.truth.ic
    assert gated[0] == 0 and decaying[0] == 0
    assert np.all(gated[1:][m.truth.regimes[1:] == 1] == 0)
    assert np.all(gated[1:][m.truth.regimes[1:] == 0] == 0.04)
    assert decaying[100] == pytest.approx(0.02)
    assert decaying[300] == pytest.approx(0.005)


def test_the_answer_key_points_at_the_real_signal_wherever_the_shuffle_put_it():
    positions = {simulate(SMALL, seed=s).truth.real_signals[0] for s in range(20)}
    assert len(positions) > 1


def test_decoys_copy_the_real_half_life_by_default():
    cfg = dataclasses.replace(SMALL, n_days=20_000, signals=(SignalConfig(ic=0.0, half_life_days=20.0),))
    m = simulate(cfg, seed=8)
    for panel in m.signals:
        lag20 = np.corrcoef(panel[:-20, 0], panel[20:, 0])[0, 1]
        assert lag20 == pytest.approx(0.5, abs=0.06)


def test_no_sectors_and_no_signals_still_simulate():
    cfg = MarketConfig(n_days=200, sectors=SectorConfig(n_sectors=0), signals=(), n_decoys=0)
    m = simulate(cfg, seed=9)
    assert m.signals.shape == (0, 200, 50)
    assert m.truth.real_signals == ()
    assert np.all(m.truth.alpha == 0)


@pytest.mark.parametrize(
    "change, message",
    [
        (dict(n_days=1), "n_days"),
        (dict(signals=(SignalConfig(ic=0.8), SignalConfig(ic=0.7))), "squared ICs"),
        (dict(signals=(SignalConfig(ic=0.01, active_regimes=(2,)),)), "active_regimes"),
        (dict(n_decoys=-1), "n_decoys"),
        (dict(stocks=StockConfig(n_assets=1)), "n_assets"),
    ],
)
def test_bad_configs_are_refused(change, message):
    with pytest.raises(ValueError, match=message):
        dataclasses.replace(MarketConfig(), **change)


def test_a_transition_row_that_does_not_sum_to_one_is_refused():
    from market_sim import RegimeConfig

    with pytest.raises(ValueError, match="summing to 1"):
        MarketConfig(regimes=RegimeConfig(transition=((0.9, 0.2), (0.1, 0.9))))


def test_two_regimes_that_never_meet_are_refused():
    from market_sim import RegimeConfig

    with pytest.raises(ValueError, match="more than one closed set"):
        MarketConfig(regimes=RegimeConfig(transition=((1.0, 0.0), (0.0, 1.0))))


def test_a_single_regime_market_simulates():
    from market_sim import MarketFactorConfig, RegimeConfig

    cfg = MarketConfig(
        n_days=500,
        regimes=RegimeConfig(names=("only",), transition=((1.0,),)),
        market=MarketFactorConfig(annual_vol=(0.16,), annual_drift=(0.06,), jumps_per_year=(0.0,)),
        sectors=SectorConfig(annual_vol=(0.08,)),
        stocks=StockConfig(idio_regime_multiplier=(1.0,)),
    )
    m = simulate(cfg, seed=10)
    assert np.all(m.truth.regimes == 0)
    assert np.all(np.isfinite(m.returns))


def test_explosive_garch_is_refused():
    from market_sim import GarchConfig, MarketFactorConfig

    with pytest.raises(ValueError, match="persistence"):
        MarketConfig(market=MarketFactorConfig(garch=GarchConfig(alpha=0.1, gamma=0.1, beta=0.9, t_df=6.0)))

# A market with an answer key — October 24, 2026

| Check | Measured result | Verdict |
|---|---|---|
| Planted signal | IC 0.0100 planted, 0.0103 measured (SE 0.0028), seed 20261024 | Answer key holds |
| Oracle ceiling | Sharpe 1.12 in theory, 1.14 realized; 60-seed mean 1.07 (SE 0.06) | Closed form matches |
| Stylized facts | 8 checks on 40 simulated 20-year paths against the S&P 500, 1999-2018 | 5 of 8 pass in every path |
| Weakest fact | Gain/loss asymmetry: skew passes in 55% of 20-year paths; the S&P's own bootstrap passes 85% | Known gap, documented |
| Decoy problem | 1 year of history: the best of 19 worthless signals has median Sharpe 1.80; the real signal wins 21% of the time | The thing to build tests against |
| Tests | 58 passing in about 12 s; 7 injected bugs, each one caught; 1 real bug found | Pass |

**Verdict: fit to grade strategies against known truth on synthetic data. It is not a calibrated model of any real market, and nothing measured here is a claim about one.**

## What it is for

A backtest on real data cannot tell you whether a strategy found something or fit noise, because nobody
knows the right answer. This simulator does: every market comes with the signals that really predict
returns, how strongly they predict them each day, and the best Sharpe ratio any strategy could expect to
earn from them. A strategy, or a test that claims to detect overfit strategies, can then be graded
against the truth instead of against another backtest.

```python
from market_sim import simulate, signal_returns, annualized_sharpe

market = simulate(seed=1)          # ten years, fifty stocks, twenty signals
market.returns                     # (2520, 50) daily log returns: what a strategy sees
market.signals                     # (20, 2520, 50) one real signal hidden among nineteen decoys
market.truth.real_signals          # (8,) where the real one is: the answer key
market.truth.ic                    # its IC on every day
annualized_sharpe(signal_returns(market.signals[3], market.returns))
```

Run it from this directory with the repo's venv (NumPy only, no SciPy):

```bash
../../.venv/bin/pytest -q                                  # 58 tests, about 12 s
../../.venv/bin/python report.py --sp500 sp500.csv.gz      # every number in this file
```

The S&P 500 file is `arch/data/sp500/sp500.csv.gz` inside the `arch` wheel on PyPI (NCSA licence). It is
not committed; `report.py` runs without it and drops the real-data columns.

## The model

Daily log returns for N stocks:

```
r[t, i] = beta[i] * m[t] + s[t, sector(i)] + u[t, i]
```

- **Regimes.** A hidden Markov chain, calm and turbulent by default. Calm lasts about 333 trading days on
  average, turbulence about 100, and the long-run share of turbulent days is 23%.
- **Market factor `m`.** Regime-dependent drift, plus GJR-GARCH(1,1) with Student-t(8) innovations, plus
  compensated jumps, so the drift is the mean with the jumps included. A jump also feeds the variance
  recursion, so a crash raises the next day's volatility like any large fall. Each regime's omega is
  solved so its long-run variance lands on a target volatility (13% calm, 30% turbulent).
- **Sectors `s`.** Five zero-drift GJR-GARCH factors.
- **Idiosyncratic `u`.** GJR-GARCH-t(5) per stock, with lognormal volatility across stocks (median 20%).
  In turbulence it rises by 1.3 times while the market's rises by 2.3, which is what makes correlations
  climb in a crisis.
- **Planted signals.** Each real signal is a unit-variance AR(1) per stock (five-day half-life by
  default). It enters the next day's idiosyncratic return as

  ```
  u[t, i] = vol[t, i] * ( sum_k ic[k, t] * a[k, t-1, i] + sqrt(1 - sum_k ic[k, t]^2) * z[t, i] )
  ```

  so the correlation between a signal and the next day's vol-scaled residual is exactly `ic`, at any
  size. An IC can be switched off in some regimes or set to halve on a schedule (crowding).
- **Decoys.** The same AR(1), with the real signals' half-lives, and no effect on returns. They are
  shuffled in with the real ones.

### Timing is the contract

- `returns[t]` is the return over day t.
- `signals[j, t]` is known at the close of day t. It may trade day t+1, never day t.
- The regime for day t is drawn at the close of day t-1. Strategies never see it; the answer key's
  expected returns condition on it.

A persistent signal is correlated with same-day returns through its own past, so "check that the
signal does not predict today" is not a look-ahead test. The structural tests pin the timing directly.

### The answer key

`market.truth` holds the regime path, every factor and its conditional volatility, the betas, the IC of
each real signal on each day, and `expected_return[t]`: the expectation of `returns[t]` given everything
known at the close of t-1.

The **oracle** knows all of that and trades only the idiosyncratic part, as if every factor were hedged
perfectly and for free, with weights alpha over variance. On a day when the real signals' squared ICs sum
to q, its P&L has mean N·q and variance N·q·(1+q). Over time, the law of total variance gives a
closed-form Sharpe ratio, `oracle_sharpe_theory`. For a small constant IC this is the fundamental law of
active management, IC times the square root of breadth: 0.01 × √50 × √252 = 1.12 by default. No
strategy built from the public data can expect to beat it.

## How close it is to a real market

Forty simulated market-factor paths of 5,030 days, the length of the S&P sample, against the S&P 500
from 1999 to 2018. The band is the 5th to 95th percentile of the index's own statistic over 200
block-bootstrap resamples (250-day blocks). Thresholds sit between the real index and a Gaussian control
(`market_sim/facts.py`). Every fact except the absence of autocorrelation has a Gaussian that fails it,
and that one fact's control is an AR(1) series.

| Fact | S&P 500 | its 90% band | Simulated median | Sim in band | Sim passes | Gaussian |
|---|---:|---|---:|---:|---:|---:|
| fat tails (excess kurtosis) | 8.169 | 2.926 to 11.529 | 9.146 | 65% | 100% | -0.100 |
| power-law tail (Hill, top 5%) | 2.932 | 2.468 to 3.836 | 2.823 | 82% | 100% | 6.393 |
| no linear autocorrelation | 0.070 | 0.042 to 0.107 | 0.046 | 60% | 98% | 0.023 |
| volatility clustering (ACF of abs r, lag 1) | 0.244 | 0.156 to 0.305 | 0.285 | 60% | 100% | -0.028 |
| slow decay (mean ACF, lags 1-50) | 0.232 | 0.117 to 0.273 | 0.195 | 90% | 100% | 0.002 |
| leverage effect | -0.083 | -0.097 to -0.063 | -0.058 | 40% | 100% | -0.000 |
| gain/loss asymmetry (skew) | -0.205 | -0.394 to -0.019 | -0.173 | 48% | 55% | 0.020 |
| aggregational Gaussianity (5-day kurtosis) | 4.141 | 1.803 to 11.246 | 6.237 | 80% | 75% | -0.040 |

**Read "in band" against 75%, not 100%.** The band is centred on the one real sample, not on the truth.
If the simulator were the true process and both sides had equal noise, it would land in the band about
75% of the time.

What the table says:

- **Leverage is weaker than real**, at -0.058 against -0.083. It passes the threshold in every path but
  lands in the real band 40% of the time.
- **Skew is the weakest fact.** Innovations are symmetric, so the downside skew comes only from leverage
  and rare negative jumps. Skewed-t innovations are the fix if it matters.
- **The market factor has no autocorrelation at all.** The real index's lag-1 value was -0.07 over this
  period.

The defaults were picked from a handful of candidates by in-band share, and tuning stopped there.
Pushing further on one 20-year sample is the overfitting this package is meant to catch. Calibration is a
separate step (see Next).

Across stocks, the average pairwise correlation is 0.42 over ten default markets (0.28 to 0.59). It is
higher on turbulent days than on calm ones in every one of the ten (0.26 higher at seed 20261024).

## The decoy problem

A hundred default markets, each with one real signal (oracle Sharpe 1.12) and nineteen decoys. Each
signal is traded the plain way: hold yesterday's demeaned signal at one dollar gross, with no factor
hedge. The winner is the highest in-sample Sharpe ratio.

| History | Real signal wins | Real signal, median Sharpe | Best decoy, median Sharpe |
|---|---:|---:|---:|
| 1 year | 21% | 0.88 | 1.80 |
| 3 years | 40% | 0.85 | 1.03 |
| 5 years | 56% | 0.90 | 0.77 |
| 10 years | 77% | 0.88 | 0.58 |

With a year of data, the best of nineteen signals with no skill typically backtests at a Sharpe ratio of
1.80. That is above the ceiling the real signal can reach. Even with ten years, the wrong signal wins
almost a quarter of the time.

This is a teaser, not a study. The overfitting tests (Deflated Sharpe Ratio, Probability of Backtest
Overfitting, White's Reality Check, Hansen's SPA) exist to catch exactly these wrong winners. Whether
they do, at what false-alarm rate, and how much history they need, is what this simulator was built to
measure.

## Reproducibility

- **One stream per component.** Every component draws from its own child of
  `SeedSequence(seed)`: regimes, market, jumps, sectors, loadings, idiosyncratic noise, signals,
  decoys and the shuffle. The order of `STREAMS` is pinned by a test. Append new components to the
  end: inserting one resamples every market generated afterwards, and every test would keep passing
  while testing something else.
- **Common random numbers.** Markets that differ only in IC, or in the number of decoys or signals,
  share every other draw. Idiosyncratic volatility runs on the noise draw before the signals take their
  share, so even the volatility paths are identical. A power study can compare IC 0 against IC 0.02 on
  the same noise, which cuts the variance of the difference.
- **Prefix stability.** Adding a decoy or a second real signal leaves the earlier ones exactly as they
  were.

## Tests

58 tests in about twelve seconds, all on fixed seeds, so they cannot flake. Statistical tolerances
are about four standard errors. Pass-rate minimums sit about three binomial standard errors below rates
measured over 200 paths, so an honest change to the draws does not trip them. To check that the tests
can fail, seven bugs were injected one at a time. Each was caught:

| Injected bug | Caught by |
|---|---|
| alpha uses the same day's signal (look-ahead) | `test_alpha_on_day_t_comes_from_the_signal_known_at_the_close_of_day_t_minus_1`, `test_the_ic_is_exact_even_when_it_is_large` |
| jumps not compensated | `test_the_drift_is_the_mean_with_jumps_included` |
| no leverage term in the market GARCH | `test_the_default_market_factor_shows_the_fact[leverage effect]` |
| oracle weights alpha/vol instead of alpha/variance | `test_the_oracle_pnl_has_the_daily_mean_and_variance_the_theory_states` |
| noise not rescaled, so the IC is not exact | `test_the_ic_is_exact_even_when_it_is_large` |
| crisis window includes the day it classifies | `test_a_market_whose_correlation_never_changes_fails_the_crisis_fact` |
| the `STREAMS` order changed | `test_the_stream_order_is_pinned`, and nothing else |

The first round caught only two of the first five. The three that slipped through each became a test.
The suite also found one real bug: a regime chain with two closed sets of regimes crashed with a
singular matrix. The config now refuses it with a message that says why
(`test_two_regimes_that_never_meet_are_refused`).

## What it does not do

- **No order book**: no spreads, no market impact, no transaction costs. A strategy's Sharpe ratio here
  is before costs, which flatters fast signals.
- **No calibration.** The defaults are hand-set near US large caps, and the stock-level settings were
  never compared with real stocks at all.
- **The IC is defined on vol-scaled residuals.** A conventional IC on raw returns will read somewhat
  lower.
- **Fixed universe**: no listings, delistings or survivorship, no earnings days, no news.
- **Regimes are a two-state Markov chain** with geometric durations. A regime change moves omega, not
  the variance itself, so the variance closes half the gap to the new level in about 34 trading days
  (persistence 0.98). Real crises can arrive faster. Large falls and jumps carry most of the fast
  moves.
- **One real signal by default.** Many weak, correlated signals are configurable, but nothing here
  measures that case yet.

## Next

1. **Test the overfit tests.** Use these markets to measure the false-alarm rate and power of the
   Deflated Sharpe Ratio, PBO via CSCV, White's Reality Check and Hansen's SPA. Vary the number of
   trials, the history length, how fat the tails are and how correlated the trials are. `arch` already
   implements Reality Check and SPA.
2. **Calibrate properly.** Fit the market parameters by simulated method of moments against the facts
   above, with common random numbers across candidate parameters, and hold back a period it never sees.
3. **Skewed-t innovations**, if gain/loss asymmetry turns out to matter for the study.

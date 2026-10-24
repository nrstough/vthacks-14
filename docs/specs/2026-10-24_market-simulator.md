# Run spec — market simulator with an answer key (2026-10-24)

Branch `claude/market-simulator-overfit-uku9eh`, off `main` at `c8d0732`. Frozen after commit;
later corrections go in a dated note at the end, never by rewriting a line above.

## Problem

The direction raised on 2026-10-24: evaluation is where AI and ML trading research is weakest, and a
market simulator, or a test that catches overfit strategies, is a real contribution. Of the five options
put to Nathan, he picked the simulator.

A backtest on real data cannot say whether a strategy found something or fit noise, because nobody knows
the right answer. The simulator's job is to be a market that does know: planted signals with an exact IC,
hidden among decoys, and a closed-form ceiling to grade against. It is the instrument for the
overfit-test study that follows. It is not that study.

## What was verified before building

- **Outside data access.** Stooq, FRED and Yahoo are refused by this session's egress proxy. PyPI and
  GitHub raw are reachable. The `arch` wheel on PyPI (NCSA licence) ships
  `arch/data/sp500/sp500.csv.gz`: 5,031 daily S&P 500 closes, 1999-01-04 to 2018-12-31. It is the
  real-data reference. Not committed: `*.csv` is gitignored, and redistributing index data is not this
  repo's to decide.
- **The reference's stylized facts**, measured on daily log returns before any threshold was written:
  excess kurtosis 8.17, Hill index 2.93, largest absolute ACF over lags 1-10 0.070, ACF of absolute
  returns 0.244 at lag 1 and 0.168 at lag 50, leverage -0.083, skew -0.20, and 5-day kurtosis 4.14. The
  same statistics on a Gaussian of equal length were measured as the negative control.
- **The reference is noisy too.** In a 250-day block bootstrap it passes the skew check 85% of the time,
  aggregational Gaussianity 78% and no-autocorrelation 90%. So the simulator is held to pass rates across
  seeds, never to every seed passing.
- **The gap is open at the instrument level.** No independent study turned up that compares the false
  alarm rate and power of DSR, PBO, Reality Check and SPA on simulated markets with a known truth. Tools
  implement them side by side; none validate them. Three searches is not a literature review, and
  Hansen (2005) already compares SPA with Reality Check by simulation, so the study needs a proper search
  first.

## Decisions

**D1 — `experiments/market_sim/`, self-contained.** Not wired into the app, the API contract or the
backend gate; it carries its own `pytest.ini`. It can move to its own repository unchanged. A new
repository is outward-facing and was not asked for.

**D2 — NumPy only.** SciPy was deliberately removed from this repo (`backend/requirements.txt`
explains why), and nothing here needs it.

**D3 — Return level, not order book.** ABIDES already simulates limit order books. The study needs
returns with realistic tails, clustering and regimes, with known alpha, and many cheap paths: about 0.2 s
for a default ten-year market and 0.04 s for the market factor alone.

**D4 — IC on vol-scaled residuals.** The signal enters the next day's idiosyncratic return as
`vol * (ic * a + sqrt(1 - ic^2) * z)`, so the correlation is exact at any size and the oracle's Sharpe
ratio has a closed form, N·q over the root of N·q·(1+q). A conventional raw-return IC reads lower, and
the README says so.

**D5 — One random stream per component, order pinned.** This is the `MERCHANTS` lesson from
`docs/features/accounts.md`: an index-based draw sequence is a contract nobody can see. Idiosyncratic
volatility runs on the noise before the signals take their share, so markets that differ only in IC share
all of their noise, volatility paths included. These are common random numbers for the power study.

**D6 — Timing stated once and tested structurally.** A signal at the close of t trades t+1. The regime for
t is drawn at the close of t-1. A persistent signal correlates with same-day returns through its own past,
so a "does it predict today" check would be wrong, and the tests pin the alpha identity directly.

**D7 — Hand tuning stopped on purpose.** The market GARCH and jumps were picked from a handful of
candidates by in-band share against the S&P bootstrap, and no further. A perfect simulator scores about
75% in band, not 100%, because the band is centred on the one real sample. Tuning further on one 20-year
sample is the failure this package exists to measure. Simulated method of moments is the next step.

## Checks

```bash
cd experiments/market_sim && ../../.venv/bin/pytest -q     # 58 passed, about 12 s
../../.venv/bin/python report.py --sp500 <path to sp500.csv.gz>
```

Seven bugs were injected one at a time, and each was caught. The table is in the README. The suite also
found one real crash before commit: a regime chain with two closed sets of regimes. The backend gate is
untouched, and nothing under `backend/` or `frontend/` changed.

## Out of scope

The overfit-test study itself. Calibration. Skewed-t innovations. Transaction costs and market impact.
Any claim about a real market.

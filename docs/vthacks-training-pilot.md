# Residual-spending neural pilot — September 19, 2026

| Check | Measured result | Verdict |
|---|---|---|
| Data | 26,700 windows; 2,700 synthetic accounts; 0 real accounts | Pipeline experiment only |
| Features / targets | Every row: 99 float64 features, 14 float64 daily outflow targets | Matches loader |
| Numeric integrity | 0 nonfinite numeric values; 0 negative targets | Pass |
| Empty / constant histories | 0 all-zero or constant histories | Pass |
| Exact duplicates / group leakage | 0 duplicate history-target rows; 0 accounts shared between splits | Pass |
| Context | All 56 days; 0 windows below required context | Pass, fixed-window design |
| Calendar coverage | All 26,400 ordinary windows start on weekday 0; 28 constant calendar features | Restricts applicability |
| Stress design | 300 new accounts; weekday 6 start plus abrupt spend change | Confounded diagnostic |
| Training / evaluation | 3 seeds; 2.05 seconds total, excluding generation/audit | Completed locally |
| Network vs weekday baseline | 14-day MAE $103.26 vs $103.16 | No demonstrated advantage |

**Verdict: acceptable for a synthetic pipeline smoke test; do not promote as the default or claim real-world forecasting accuracy.** The dataset was not changed after review.

## Provenance and task

No bank export or Nessie API records were used. `run.py generate` simulates 224-day spending histories using seed 20260919. Spending has steady, sparse, and bursty regimes, weekly effects, a latent payday-cycle effect, mild trends, and nonnegative gamma-distributed purchases with some zero-spend days. Targets are simulated subsequent observations, not human-labeled data or observations of actual people. USD is an artificial unit chosen by this generator.

Known bills, income, and transfers are excluded by construction. This does not validate the real-world recurrence detector or residual extraction. There are no missing feed days, pending-to-posted transitions, merchant descriptors, refund corrections, or short-history accounts. Every window is intentionally trimmed to 56 days; there is no fallback-to-full-series path. Regime-specific context lengths are therefore also exactly 56.

The numeric arrays contain features (`x`), future daily spending (`y`), history-derived scale, account group, forecast origin, historical spending, two baseline forecasts, and a regime tag. Metadata does not feed the model except history, calendar, and scale. Full observed shapes/dtypes are in `review.json`.

| Split | Accounts | Windows | Steady accounts | Sparse accounts | Bursty accounts |
|---|---:|---:|---:|---:|---:|
| train | 1,800 | 19,800 | 600 | 612 | 588 |
| validation | 300 | 3,300 | 95 | 113 | 92 |
| test | 300 | 3,300 | 101 | 99 | 100 |
| stress | 300 | 300 | 94 | 96 | 110 |

These are distinct accounts across splits, but eleven windows from the same ordinary account share history. Do not treat 3,300 test windows as 3,300 independent people. Target intervals within each account are disjoint; the feature windows overlap.

## Per-output training target audit

These are regression targets, so classification-label accuracy is not applicable. Zero-spend frequency and positive counts are reported separately for each of the 14 outputs. Full values for every split are in `audit.json` and `review.json`.

| Forecast day | Zero-spend fraction | Positive targets | Mean synthetic outflow |
|---|---:|---:|---:|
| 1 | 40.32% | 11,817 | $20.56 |
| 2 | 41.15% | 11,653 | $20.39 |
| 3 | 41.02% | 11,679 | $20.38 |
| 4 | 40.59% | 11,763 | $20.48 |
| 5 | 40.94% | 11,693 | $20.48 |
| 6 | 40.54% | 11,774 | $30.74 |
| 7 | 40.42% | 11,796 | $30.76 |
| 8 | 40.68% | 11,745 | $20.54 |
| 9 | 40.58% | 11,765 | $20.33 |
| 10 | 40.67% | 11,747 | $20.45 |
| 11 | 40.19% | 11,843 | $20.85 |
| 12 | 40.35% | 11,810 | $21.01 |
| 13 | 41.50% | 11,583 | $30.33 |
| 14 | 40.73% | 11,735 | $30.87 |

All features were replayed from strictly pre-origin history and calendar values. Scales matched a replay from history. Every target interval fits within its source series. Across all six split pairs, account overlap and exact history-target duplication are both zero. Training/validation/test regime proportions differ modestly from random sampling; this is not a demographic representativeness claim.

## Model and training

The MLP uses 99 inputs → 64 ReLU units → 32 ReLU units → 14 softplus outputs (8,942 parameters). Inputs are 56 scaled daily lags, 14 weekday-history means, 28 future-calendar sine/cosine values, and log spending scale. Feature standardization is fit on training data only. Targets are normalized by max(recent 28-day mean, $5). Softplus enforces nonnegative predictions. This is point regression, not a quantile model.

Training uses Adam, normalized squared error, batches of 256, learning rate 0.001, and gradient-norm clipping at 5. Each of seeds 11, 23, and 47 has a 60-epoch cap and stops after ten epochs without improvement in validation 14-day total MAE. The seed and epoch are selected on validation only. Test and stress are evaluated after this selection; no tuning followed inspection of their results.

| Seed | Best epoch | Epochs run | Validation 14-day MAE | Training seconds |
|---|---:|---:|---:|---:|
| 11 | 6 | 16 | $103.94 | 0.602 |
| 23 | 9 | 19 | $104.80 | 0.715 |
| 47 | 5 | 15 | $104.32 | 0.563 |

Selected seed 11. Measured complete training-command elapsed time: 2.049 seconds. Environment: Python 3.14.7, NumPy 2.5.3; local CPU implementation with BLAS thread limits set to two. This timing includes gradient checks, runs, evaluation, and model writes; it excludes generation and dataset auditing. No GPU, paid compute, model download, or ongoing overnight job.

Validation of the implementation: 24 numerical finite-difference gradient checks, maximum absolute error 5.29e-12; serialized weights reproduced predictions exactly; all evaluated predictions were finite, nonnegative, and correctly shaped. A warm single-record forward pass averaged 0.0065 ms across 1,000 repetitions. That excludes loading, preprocessing, HTTP, and the solver; it is not an app latency measurement.

## Held-out results

MAE is mean absolute error. The total metrics compare each predicted 7-/14-day sum against its realized synthetic sum; they are not sums of daily absolute errors. Lower is better.

| Test model | Daily MAE | 7-day total MAE | 14-day total MAE | Mean 14-day underprediction |
|---|---:|---:|---:|---:|
| neural | $22.56 | $70.49 | $103.26 | $54.18 |
| recent_28day_mean | $23.04 | $73.84 | $113.43 | $56.90 |
| weekday_8week_mean | $23.38 | $70.01 | $103.16 | $51.76 |

The network improves 14-day MAE by about 9% against the recent average but is about $0.10 worse than the weekday baseline. It also has worse mean 14-day underprediction than the weekday baseline. Its lower daily MAE does not establish better overdraft decisions. No statistical significance, interval calibration, or solver-level benefit was measured.

| Stress model | Daily MAE | 14-day total MAE |
|---|---:|---:|
| neural | $39.44 | $315.65 |
| recent_28day_mean | $36.68 | $329.98 |
| weekday_8week_mean | $36.84 | $328.93 |

An unpredictable step change in future spending produces large errors. The stress set also changes the forecast start weekday, which was absent from training. Its apparently better neural total MAE cannot be assigned to successful shock prediction: these factors are confounded.

## Limitations and next decision

1. No real financial holdout exists. The ordinary splits share the same authored generator family; a pass does not establish transfer to humans.
2. Ordinary forecast origins are 70, 84, …, 210 (all weekday 0). Feature columns 70–97 are constant within these splits. Stress origins are 160 (weekday 6). General weekday coverage needs a separately versioned dataset; this one remains intact.
3. No calibrated uncertainty, missing-data handling, recent regime-change adaptation, or robust cold start was tested.
4. Forecast comparisons have no account-level confidence intervals and no downstream decision-cost evaluation. A slightly better validation score is not grounds to claim superiority.
5. Real target extraction could leak future recurrence information or double count known bills. This pilot assumes perfect separation and cannot detect those application errors.

**Next:** keep the weekday baseline available; prepare a versioned dataset with all start weekdays and a new untouched holdout; add a regularized linear baseline and independent data; evaluate account-level uncertainty and actual plan outcomes. Do not spend additional epochs on this exact dataset hoping to establish real-world usefulness. No further training is running.

## Reproduce and retain artifacts

Project location: `experiments/residual_forecast/`. The accompanying ZIP retains code, the synthetic data, selected and per-seed checkpoints, predictions, and reports. `review.json` records SHA-256 hashes of the original scripts, data, weights, and numerical reports. Data/weights are ignored by git locally to avoid accidental large commits; do not delete them before copying the ZIP or confirming it is retained. No private data or API keys are included.

Run the commands from the experiment directory with an interpreter providing NumPy (the project venv was used). For a new run, copy the directory first: rerunning generation/training overwrites its local artifacts.

```bash
export OPENBLAS_NUM_THREADS=2
export VECLIB_MAXIMUM_THREADS=2
export OMP_NUM_THREADS=2
python run.py generate
python run.py audit
python run.py train
python review.py
```

The original data verdict was train for a synthetic pipeline test only. The broader review narrows any interpretation of that result; it does not authorize deployment or alter the preserved dataset.

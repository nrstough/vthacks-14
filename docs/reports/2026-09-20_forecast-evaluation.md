# The trained ensemble, scored on a real account

2026-09-20, branch `ensemble-eval`. Reproduce with:

```bash
R=/Users/nathanstough/Documents/Codex/worktrees/vthacks-forecast
PYTHONDONTWRITEBYTECODE=1 "$R/forecasting/.venv-v3/bin/python" backend/tools/forecast_parity.py
SAFE_TO_SPEND_CSV=~/Downloads/Checking-2.csv .venv/bin/python backend/tools/forecast_eval.py
```

## What was run

The three direct small checkpoints (seeds 11, 23, 47) from the research
lane's frozen v3 study, averaged with equal weight, plus the tiny, medium
and large seed-11 checkpoints for comparison — six models and one ensemble.
Against them, the product's own forecast: the same-weekday statistic over
the person's last eight weeks.

The account is one real consented export, 1,060 posted rows, 2024-08-19 to
2026-09-18. The two recurring income streams are detected and removed, and
what is left is the everyday-spending series the app already computes. A
56-day context and a 14-day target roll across it: **692 windows**, heavily
overlapping, so the effective sample is far smaller than that number.

## Parity first

An unchecked reimplementation of someone else's model produces confident
numbers with no way to tell whose they are. `backend/app/forecast/` runs
the checkpoints in NumPy — PyTorch is 200 MB and needs a wheel for the
box's exact Python — and `tools/forecast_parity.py` checks it against the
Torch reference on the frozen checkpoints themselves.

| Checked | Worst disagreement |
|---|---|
| forward pass, all four sizes, six input shapes each | 7.7e-06 |
| the three-model ensemble | 3.7e-07 |
| preprocessing against `corpus.transform_input_arrays`, five history shapes | 8.0e-07 |

All inside the handoff's tolerance of 1e-5. Every number below therefore
belongs to the research lane's models, not to a lookalike.

## Result: the ensemble loses to the baseline, on every profile

Error is the mean absolute error of the 14-day total, in dollars.

| Profile reference | Ensemble of three | vs baseline |
|---|---:|---:|
| ibm / USD | $155.70 | −5.6% |
| moneydata / SOURCE_NATIVE | $159.65 | −8.3% |
| berka / SOURCE_NATIVE | $177.19 | −20.2% |
| mindweave / USD | $177.45 | −20.4% |
| cofinfad / COP | $178.28 | −20.9% |

The baseline scores **$147.39**. No model beats it under any profile. The
single best individual result was seed 23 under the IBM reference at
$153.23, still 4% worse.

**The profile is why, and it is not a detail.** These models take one
auxiliary feature that compares the account's own scale to a reference for
its source, currency and channel. Five references exist. A US checking
account is not one of them, so every row above is the ensemble running on a
profile it was never trained for — and the spread across the five, **13% of
the mean**, is the size of the guess. That is the finding, not a caveat on
it.

## The evaluation changed the product

The baseline was the same-weekday **median**. Across the 692 windows it
under-predicted the next fortnight's spending **71% of the time, by $115**
on average. For a tool whose whole claim is that it will not tell you that
you are fine when you are not, under-predicting spending is the wrong
direction to be wrong in.

| Same-weekday statistic | 14-day MAE | Bias | Under-predicts | One $900 purchase |
|---|---:|---:|---:|---|
| median (was shipped) | $154.57 | −$115.41 | 71% | ignores it, correctly |
| **60th percentile (now shipped)** | **$147.39** | **−$37.42** | **52%** | ignores it, correctly |
| mean | $152.15 | +$5.34 | 43% | $569 where the truth is $350 |
| 75th percentile | $199.97 | +$128.77 | 26% | ignores it, correctly |

The 60th percentile beats the median on error, on bias and on how often it
reassures wrongly, and it is just as immune to a single large purchase —
which is what ruled the mean out. That change is committed with this
evaluation.

## What this is not

One account. Overlapping windows. A profile none of the models was trained
on. It is a check, not a validation, and it cannot become one until there
is a modern multi-account checking dataset to validate against — which,
searched properly, does not publicly exist.

It is, however, consistent with what the research lane already measured on
its own data: the ensemble beat its baseline there by 0.41% with a
confidence interval spanning zero, and never met the 5% promotion gate.
Nothing here contradicts that, and nothing here promotes it.

## Where the code sits

- `backend/app/forecast/runtime.py` — the checkpoints in NumPy.
- `backend/app/forecast/preprocess.py` — the transform, in NumPy.
- `backend/tools/forecast_parity.py` — the Torch check. Run it before
  trusting any change to either file.
- `backend/tools/forecast_eval.py` — this evaluation.

Nothing is wired to a route and nothing is shipped to the app. The
`POST /api/forecast` endpoint the handoff describes is not built, and on
this evidence there is nothing to serve from it.

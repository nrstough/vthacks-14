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

## Round two: the anchored models

Hours after the above, the follow-up study finished and its winning recipe is
different in kind. `anchor_prefix_mae` is **personalised by construction**:

```
prediction = the person's own normalised weekday baseline + a learned correction, clamped at zero
```

Its output head is initialised to zeros, so an untrained anchored model *is* the
baseline. It never has to learn the person's level or weekly rhythm — it learns
only what the baseline gets wrong. That is exactly the objection that sank the
direct models, answered in the architecture.

On the study's own validation it scores **1.1834 against a baseline of 1.3494, a
12.3% win**, where the direct recipes managed 0.4%. All three seeds land within
0.001 of each other.

Parity was re-run first. The tensors are identical in name and shape to the
direct models, but the forward pass is not — the anchored path takes the
baseline and clamps, with no softplus — so loading them the old way runs cleanly
and returns numbers that differ by 1.8 in normalised units. Nine anchored
checkpoints, four baseline shapes each, worst disagreement 8.0e-06.

### Every size, every seed, on the real account

14-day total MAE against the shipped baseline's **$147.39**, at the best of the
five profile references:

| Family | Daily MAE | 14-day MAE | Profile spread | vs baseline |
|---|---:|---:|---:|---:|
| **anchor large ×3** | $26.96 | **$154.55** | **3%** | **−4.9%** |
| anchor small ×3 | $26.45 | $155.27 | 7% | −5.4% |
| anchor medium ×3 | $26.60 | $158.31 | 4% | −7.4% |
| direct small ×3 | $29.96 | $155.70 | 13% | −5.6% |
| direct medium ×3 | $30.73 | $163.22 | 11% | −10.7% |
| direct tiny ×3 | $30.50 | $165.97 | 14% | −12.6% |

**The anchoring plainly works.** Daily error drops from about $30 to about $26,
and the spread across profile references — the size of the guess made by handing
the model a reference that is not its own — falls from 11–14% to **3–7%**. That
is what you would expect from a model that is handed the person's own level
instead of inferring it.

**It still does not beat the baseline.** The best anchored ensemble is 4.9%
worse on the fortnight's total. The 12.3% win on the research corpus did not
reproduce on a real account, which is the same shape as the original
0.41%-with-an-interval-spanning-zero story, one level up.

### On seeds: they are not chosen

Three seeds are three runs of one recipe differing only in random
initialisation. Picking the best of them on the data being scored is selection on
the test set, and it is how a 4.9% loss becomes a reported win: `anchor large`
ranges $153.75 to $156.70 across its seeds, and the best single seed at $153.75
is still worse than the baseline. Every figure above is the equal-weight mean of
the three seeds' **predictions** — which is not the same as the mean of their
scores, and not the same as their best.

## What this is not

One account. Overlapping windows. A profile none of the models was trained
on. It is a check, not a validation, and it cannot become one until there
is a modern multi-account checking dataset to validate against — which,
searched properly, does not publicly exist.

It is, however, consistent with what the research lane measured on its own
data twice over. The direct ensemble beat its baseline there by 0.41% with a
confidence interval spanning zero. The anchored recipe beat it by 12.3% — and
neither margin survived contact with a real account. Nothing here promotes
either of them.

The anchored result is still worth keeping: it is a large, stable improvement
over the direct models and it improves for a reason anyone can state. If a
modern multi-account checking dataset ever becomes available, anchoring on the
person's own baseline is the shape to train.

## Where the code sits

- `backend/app/forecast/runtime.py` — the checkpoints in NumPy.
- `backend/app/forecast/preprocess.py` — the transform, in NumPy.
- `backend/tools/forecast_parity.py` — the Torch check. Run it before
  trusting any change to either file.
- `backend/tools/forecast_eval.py` — this evaluation.

Nothing is wired to a route and nothing is shipped to the app. The
`POST /api/forecast` endpoint the handoff describes is not built, and on
this evidence there is nothing to serve from it.

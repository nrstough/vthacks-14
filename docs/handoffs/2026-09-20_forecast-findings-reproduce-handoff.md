# Handoff — reproduce the forecast findings (2026-09-20)

**Purpose of this chat:** Independently reproduce the three forecast findings
below from the commits and scripts already on disk, and then settle the one
open product question: where on the safety/nuisance curve the shipped forecast
should sit. Everything needed is committed. Nothing needs retraining.

## Context

Safe to Spend plans from a person's own bank export. It detects recurring
income and bills by cadence, removes them, and assumes everyday spending for
the horizon from the person's own last eight weeks — the **same-weekday 60th
percentile**. That assumption is what the three findings are about.

Two families of trained models exist in the Codex research lane and both were
evaluated against that baseline on one real two-year export (1,060 rows).

**Finding 1 — the models lose, and the anchored ones lose by less.**
14-day total MAE, baseline **$147.39**, best profile reference per family:

| Family | Daily MAE | 14-day MAE | Profile spread | vs baseline |
|---|---:|---:|---:|---:|
| anchor large ×3 | $26.96 | $154.55 | 3% | −4.9% |
| anchor small ×3 | $26.45 | $155.27 | 7% | −5.4% |
| direct small ×3 | $29.96 | $155.70 | 13% | −5.6% |
| direct tiny ×3 | $30.50 | $165.97 | 14% | −12.6% |

The anchored recipe is **personalised by construction**: its prediction is the
person's own normalised weekday baseline plus a learned correction, clamped at
zero, with the output head initialised to zeros so an untrained model *is* the
baseline. It works — daily error falls from ~$30 to ~$26 and the spread across
profile references falls from 11–14% to 3–7% — but it still does not beat the
thing it is anchored to. On the study's own corpus it wins 12.3%; that did not
reproduce here.

**Finding 2 — MAE was the wrong test.** It treats over- and under-prediction
as equal, and this product does not. Rescored as two costs per fortnight over
692 windows: *unwarned* spending the plan missed, and *nuisance* spending it
expected that never came.

**Finding 3 — every model lands ON the baseline's tradeoff curve.** The
baseline's percentile is a dial between those two costs. Matched at equal
nuisance, the best model leaves $81.87 unwarned where the baseline leaves
$79.01. No model buys a tradeoff the dial does not already give — per person,
with no training data, no profile reference and no checkpoint to ship.

## Working branch / worktree

`ensemble-eval` in `/Users/nathanstough/Desktop/vthacks-ensemble`, clean at
`858c92b`. Branches off `history-import`; everything through `38e61f3` is
already merged to `main` and deployed to https://safetospend.study.

`.venv` and `frontend/node_modules` are symlinks into
`/Users/nathanstough/Desktop/VT Hacks` and do not come with a worktree.
Other sessions are live in other worktrees — `git worktree list` before
anything branch-sensitive, explicit paths in `git add`, `git switch` never
`checkout`. `CLAUDE.md` is binding.

## Environment / setup

```bash
cd /Users/nathanstough/Desktop/vthacks-ensemble
git branch --show-current                      # expect ensemble-eval
export R=/Users/nathanstough/Documents/Codex/worktrees/vthacks-forecast
```

Two interpreters, deliberately:

- `.venv/bin/python` — the app (3.14, numpy 2.5.3, **no torch**). Runtime and
  evaluation.
- `"$R/forecasting/.venv-v3/bin/python"` — the research env (3.11, torch
  2.14.0). **Parity reference only.**

The research worktree is **read-only**. Its `forecasting/` tree is fingerprinted
by the frozen study; adding even one file changes the study's identity. Import
from it, never write to it.

## What to do next

### 1. Reproduce parity. Nothing below counts until this passes

```bash
PYTHONDONTWRITEBYTECODE=1 "$R/forecasting/.venv-v3/bin/python" backend/tools/forecast_parity.py
```

Expect **PARITY PASSED**. It checks the NumPy runtime against Torch on four
model sizes × six input shapes, the three-model ensemble, the preprocessing
against `corpus.transform_input_arrays` on five history shapes, and nine
anchored checkpoints × four baseline shapes. Worst disagreement ~8.0e-06
against a 1e-5 tolerance.

It also asserts the two forward paths genuinely differ (~1.8 in normalised
units). That matters: the anchored checkpoints have tensors identical in name
and shape to the direct ones, so loading them the old way runs cleanly and
returns the wrong numbers.

### 2. Reproduce the evaluation

```bash
SAFE_TO_SPEND_CSV=~/Downloads/Checking-2.csv .venv/bin/python backend/tools/forecast_eval.py
```

Expect: 1,060 rows, 2024-08-19 to 2026-09-18, **692 rolling windows**, baseline
14-day MAE **$147.39**, and the per-family table above.

### 3. Reproduce the tradeoff curve

Finding 3 was computed in an ad-hoc script and is recorded in the report but
**is not yet a committed tool**. Write it as one, in
`backend/tools/forecast_tradeoff.py`, so it can be re-run:

For each predictor, over the same 692 windows, with `miss = actual − predicted`:

- unwarned = `clip(miss, 0, None).mean()`
- nuisance = `clip(−miss, 0, None).mean()`

Sweep the baseline percentile 0.40 to 0.90, then place each model ensemble on
that curve by interpolating the baseline's unwarned cost at the model's
nuisance cost. Expected numbers to reproduce:

| Point | Unwarned | Nuisance |
|---|---:|---:|
| baseline p50 | $134.99 | $19.58 |
| baseline p60 (shipped) | $92.41 | $54.98 |
| baseline p64 | $75.60 | $76.27 |
| baseline p70 | $55.29 | $113.09 |
| baseline p80 | $21.65 | $230.73 |
| anchor large ×3 | $81.87 | $72.67 |
| direct small ×3 | $81.58 | $74.12 |

And the weighted optima, where N is how many nuisance dollars one unwarned
dollar is worth: N=1 → p60, N=2 → p68, N=3 → p74, N=5 → p78, N=10 → p85.

### 4. Settle the open product question

**"50-50" has three different answers and they are not the same point.** The
next chat should put these to Nathan plainly and then implement his choice:

- **Equal weight in the loss** (an unwarned dollar costs the same as a nuisance
  dollar) → **p60**, which is exactly what ships today.
- **Equal expected cost in dollars** → **p64** ($75.60 against $76.27).
- **Wrong half the time in each direction** → **p63** (47% under).

They are close, and any of the three is defensible. What is NOT neutral is the
1:1 weighting itself: this product's stated stance is that the two failures are
not equal — an unwarned overdraft is a $35 fee, a false warning is mild
annoyance. At 2:1 the answer is **p68**; at 3:1, **p74**.

Whatever is chosen, change `ASSUMED_PERCENTILE` in
`backend/app/history/residual.py`, update the `same_weekday_8_week_p60`
literal in `backend/app/schemas.py`, `backend/app/history/__init__.py` and
`frontend/src/types.ts`, and the wording in `frontend/src/lib/history.ts` and
`frontend/src/lib/accounts.ts`. The literal is closed, so the type checker and
the tests will find every site.

### 5. State the limits in whatever you write

One account. Overlapping windows, so 692 is not 692 independent observations.
No profile reference matches a US checking account. It is a check, not a
validation, and it cannot become one until a modern multi-account checking
dataset exists — searched properly, none publicly does.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

- **Parity:** `PYTHONDONTWRITEBYTECODE=1 "$R/forecasting/.venv-v3/bin/python" backend/tools/forecast_parity.py`
  → **PARITY PASSED**, worst ~8.0e-06.
- **Backend:** `.venv/bin/pytest backend/ -q` → **2291 passed, 10 deselected**.
  Use the bare command: a `-m` on the command line REPLACES `pytest.ini`'s
  `addopts` and puts the live Nessie probe on the network.
- **Frontend:** `cd frontend && npm run lint && npm run build && npm test`
  → lint clean, **305 passed**. Build before test; `bundle.test.ts` reads
  `dist/`. Export `npm_config_cache="/Users/nathanstough/Desktop/VT Hacks/.npm-cache"`.
- **Evaluation:** as in step 2 → 692 windows, baseline $147.39.
- **At risk: `~/Downloads/Checking-2.csv`** — the real bank export. **NOT
  archived, must never be committed.** `*.csv` is gitignored; keep it so. No
  report, commit or log may contain a payee or a row.
- **At risk: `$R/forecasting/artifacts/forecast-v3/`** and
  **`forecast-small-followup/`** — the checkpoints, `selection.json`, per-run
  `validation-predictions.npz`. **NOT archived.** Read-only. Do not clean.
- **In flight:** the research lane may still be running. Check read-only with
  `ps -p 95706,95707,95733 -o pid,state,lstart,command`. **Do not signal,
  resume, retire or clean any of those processes.**
- **Unpushed:** `main` is **93+ commits ahead of origin** and the repo
  `nrstough/vthacks-14` is still **PRIVATE**. Both are Nathan's calls.

## Analytical notes

- **Why the direct models lose:** pooled over five foreign sources (1990s
  Czech, Colombian withdrawals, IBM synthetic card, two single entities), and
  they learn a person's level only through one profile feature that has no
  value for a US checking account. The 13% spread across references is the
  size of that guess.
- **Why anchoring helps but is not enough:** it hands the model the level and
  rhythm for free, so the spread collapses to 3–7% and daily error drops. But
  the residual it is left to learn is mostly noise, and there is little there.
- **Why a simple baseline is hard to beat:** short horizon, high noise, strong
  weekly seasonality, per-entity level. Seasonal-naive baselines are famously
  strong on exactly that shape.
- **"primary" in the study's own numbers** is a normalised cumulative-prefix
  absolute error, not dollars. Not comparable to the evaluation's dollar MAE;
  only direction carries across.
- **No predictor makes this safe.** At p80, 18% of fortnights still overspend
  the estimate, by $122 on average. That is why the screen calls it an
  assumption and why the fallback wording exists.

## Pointers

- `docs/reports/2026-09-20_forecast-evaluation.md` — all three findings, with
  method. Update this rather than starting a new report.
- `backend/app/forecast/runtime.py`, `preprocess.py` — the NumPy runtime.
- `backend/tools/forecast_parity.py`, `forecast_eval.py` — the two tools.
- `$R/forecasting/small_followup/models.py:37-49` — the anchored forward pass.
- `$R/forecasting/artifacts/forecast-small-followup/selection.json` — the
  study's own scores (`anchor_prefix_mae` 1.1834 vs baseline 1.3494).
- `docs/features/history-import.md` — where the shipped forecast is described.
- `CLAUDE.md` — working agreement. Binding.
- Memory: `ensemble-evaluated-on-real-account`,
  `vthacks-forecast-data-ceiling`, `history-import-lane`,
  `main-merged-and-deployed-2026-09-20`.

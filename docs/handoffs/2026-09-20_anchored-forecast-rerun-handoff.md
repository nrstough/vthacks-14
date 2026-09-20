# Handoff — re-run the forecast evaluation with the ANCHORED models (2026-09-20)

**Purpose of this chat:** Re-run the real-account forecast evaluation using the
follow-up study's `anchor_prefix_mae` checkpoints, which finished a few hours ago
and score **12.3% better than the baseline** where the models I already evaluated
scored **0.4%** and then lost outright on real data. Extend the NumPy runtime to
the anchored forward pass, re-run parity against Torch, then re-run the
evaluation. Do not trust a single number until parity passes.

## Context

The app ships a deterministic forecast: for each day of the horizon, the
same-weekday **60th percentile** of the person's last eight weeks. That is what
everyday spending in the plan is.

Yesterday I ran the research lane's **direct** models (`direct_small_seed_{11,23,47}`,
the equal-weight three-model ensemble from the Fable handoff) against that
baseline on Nathan's real two-year export. The ensemble **lost under every one of
the five profile references**, by 5.6% at best and 21% at worst. Full write-up and
numbers: `docs/reports/2026-09-20_forecast-evaluation.md`. That evaluation also
moved the shipped statistic off the median, because the median under-predicted
spending in 71% of windows.

**What changed.** The follow-up study finished and its winning recipe is
different in kind. From
`forecasting/artifacts/forecast-small-followup/selection.json`, against the
frozen baseline of **1.349398800**:

| Recipe | Mean individual primary | vs baseline |
|---|---:|---:|
| `anchor_prefix_mae` | **1.1833549862197081** | **+12.3%** |
| `anchor_mse` | 1.3541449945877517 | +0.4% |
| `direct_mse` (what I evaluated) | 1.3548197271791809 | +0.4% |

All three `anchor_prefix_mae` seeds land within 0.001 of each other (1.182840,
1.183366, 1.183860), which is a good sign rather than one lucky seed. Medium and
large versions completed as well.

**Why it is plausibly better, and why this is the interesting part.** The
anchored recipe is personalised by construction. Its forward pass is

```
prediction = normalized weekday baseline + learned correction, clamped at zero
```

so the network never has to learn the person's level or their weekly rhythm — it
gets both from their own history and learns only the baseline's error. Its output
head is initialised to zeros, so it *starts* as exactly the baseline. That is
precisely the objection that sank the direct models: those were pooled over five
foreign sources and had to infer a person's scale through one crude profile
feature that does not exist for a US checking account.

## Working branch / worktree

`ensemble-eval` in `/Users/nathanstough/Desktop/vthacks-ensemble` — **clean**,
`38e61f3`. It branches off `history-import`, and everything through `38e61f3` is
already merged into `main` and deployed. Continue on this branch; do not create
another worktree.

`.venv` and `frontend/node_modules` are symlinks into
`/Users/nathanstough/Desktop/VT Hacks` and do not come with a worktree.

**Other sessions are live.** `git worktree list` before anything branch-sensitive.
At the time of writing `chat-acts` and `export-import` were both held by other
sessions. Per `CLAUDE.md`: explicit paths in `git add`, `git switch` never
`checkout`, and check the branch every time.

## Environment / setup

```bash
cd /Users/nathanstough/Desktop/vthacks-ensemble
git branch --show-current            # expect ensemble-eval
```

Two interpreters, deliberately:

```bash
# the APP env (Python 3.14, numpy 2.5.3, no torch) — runtime and evaluation
.venv/bin/python

# the RESEARCH env (Python 3.11, torch 2.14.0) — the parity reference only
R=/Users/nathanstough/Documents/Codex/worktrees/vthacks-forecast
"$R/forecasting/.venv-v3/bin/python"
```

The research worktree is **read-only**. Its `forecasting/` tree is fingerprinted
by the frozen study; adding even one file there changes the study's identity.
Import from it, never write to it.

## What to do next

### 1. Teach the loader the new artifact version

`backend/app/forecast/runtime.py` pins `ARTIFACT_VERSION = "pooled-forecast-v3-1"`.
The follow-up checkpoints carry `personal-followup-1`. Verified by hand: the
**tensor names, shapes and parameter count are byte-identical** to the v3 small
model, so nothing else about loading changes. Accept both versions and record
which one a checkpoint came from.

### 2. Add the anchored forward pass

Reference: `$R/forecasting/small_followup/models.py:37-49`.

```python
# direct_mse      -> softplus(head(...))            (what runtime.forward does today)
# anchor_*        -> where(baseline + raw >= 0, baseline + raw, 0)
```

`raw` is the head output **without** softplus. So the anchored path needs the
linear head output, then adds the baseline, then a ReLU-style clamp — not
softplus. Getting this wrong still produces plausible numbers, which is exactly
why step 3 is not optional.

**The baseline it adds is already computed.** It is the same-weekday **eight-week
MEAN**, normalized by scale — `forecasting/v3/baselines.py:11-15`, divided by
`scale`. In `backend/app/forecast/preprocess.py::scale_and_raw` that quantity is
`weekday_future / scale[:, None]`, which is **the first 14 columns of the RAW
auxiliary array, before standardisation**. Return it alongside, rather than
recomputing it and risking a second definition drifting from the first.

Note it is the MEAN, not the 60th percentile the product displays. The model was
trained against the mean; feed it the mean.

### 3. Re-run parity. Nothing counts until this passes

```bash
R=/Users/nathanstough/Documents/Codex/worktrees/vthacks-forecast
PYTHONDONTWRITEBYTECODE=1 "$R/forecasting/.venv-v3/bin/python" backend/tools/forecast_parity.py
```

Expected today: **PARITY PASSED**, worst disagreement ~8e-06 against a 1e-5
tolerance, over four model sizes, six input shapes each, the ensemble, and the
preprocessing.

Extend it to the anchored checkpoints. The Torch reference for those is
`forecasting/small_followup/models.py`'s `Forecast`, not `v3/models.py`'s
`PooledTransformer`, and its `forward` takes a third argument, `baseline`. Add at
least one case with a baseline of zeros and one with a large baseline, because
the clamp only bites when `baseline + raw` goes negative.

### 4. Re-run the evaluation

```bash
SAFE_TO_SPEND_CSV=~/Downloads/Checking-2.csv .venv/bin/python backend/tools/forecast_eval.py
```

Add the anchored checkpoints to its model list. Keep the five profile references:
the anchored models still take the profile feature, so the spread across
references is still the honest measure of how much is being guessed.

**The number to beat is $147.39** — the shipped baseline's mean absolute error on
the 14-day total, over 692 rolling windows. The direct ensemble managed $155.70
at its best.

### 5. Then decide, and say which

- If the anchored models beat $147.39 by a margin that survives the profile
  spread (13% of the mean for the direct ensemble), that is a real result on real
  data and worth shipping behind the existing fallback.
- If they do not, say so as plainly as the last report did and leave the baseline
  alone. A 12.3% win on the research corpus that does not reproduce on a real
  account is itself the finding, and it is the same shape as the original
  0.41%-with-an-interval-spanning-zero story.

Either way, update `docs/reports/2026-09-20_forecast-evaluation.md` rather than
starting a new report, and correct
`docs/features/history-import.md`'s limitation paragraph if the conclusion moves.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

- **Parity:** `PYTHONDONTWRITEBYTECODE=1 "$R/forecasting/.venv-v3/bin/python" backend/tools/forecast_parity.py`
  → **PARITY PASSED**, worst ~8e-06. This is the gate on every number below it.
- **Backend:** `.venv/bin/pytest backend/ -q` → **2291 passed, 10 deselected**.
  Use the bare command: a `-m` on the command line REPLACES `pytest.ini`'s
  `addopts` and puts the live Nessie probe on the network.
- **Frontend:** `cd frontend && npm run lint && npm run build && npm test` →
  lint clean, **305 passed**. Build before test; `bundle.test.ts` reads `dist/`.
  Export `npm_config_cache="/Users/nathanstough/Desktop/VT Hacks/.npm-cache"`.
- **Evaluation:** `SAFE_TO_SPEND_CSV=~/Downloads/Checking-2.csv .venv/bin/python backend/tools/forecast_eval.py`
  → baseline 14-day MAE **$147.39** over **692 windows**; direct ensemble
  $155.70 (ibm/USD) to $178.28 (cofinfad/COP).
- **At risk: `~/Downloads/Checking-2.csv`** — Nathan's real bank export, 1,060
  rows. **NOT archived, must never be committed.** `*.csv` is gitignored; keep it
  that way. Nothing in any report or commit may contain a payee or a row.
- **At risk: `$R/forecasting/artifacts/forecast-small-followup/`** — the new
  checkpoints, `selection.json`, per-run `validation-predictions.npz`.
  **NOT archived.** Read-only. Do not clean.
- **At risk: `$R/forecasting/artifacts/forecast-v3/`** — the original frozen
  study. **NOT archived.** Same rules.
- **In flight:** the research lane may still be running. Check read-only with
  `ps -p 95706,95707,95733 -o pid,state,lstart,command`. **Do not signal,
  resume or clean any of those processes.**
- **Unpushed:** `main` is **93 commits ahead of origin** and the repo is still
  **PRIVATE**. Both are Nathan's calls, not this chat's.

## Analytical notes

- **Why the direct models lost, in one line:** pooled over five foreign sources,
  and they learn a person's level only through one profile feature that has no
  value for a US checking account. The spread across the five references was 13%
  of the mean — that spread is the size of the guess.
- **Why the anchored ones might not:** they are handed the person's own baseline
  and learn only its error. Same reason the baseline is hard to beat is the
  reason adding to it is a better shape.
- **What "primary" means** in the study's numbers: a normalized
  cumulative-prefix absolute error, not dollars. It is not comparable to the
  evaluation's dollar MAE; only the *direction* carries across.
- **The evaluation is one account with overlapping windows.** 692 windows is not
  692 independent observations. It is a check, not a validation, and it cannot
  become one until a modern multi-account checking dataset exists — searched
  properly, none does. See the memory note.
- **The product does not depend on any of this.** The shipped forecast is the
  deterministic 60th percentile, it needs no training data, and it works for
  anyone with eight weeks of history.

## Pointers

- `docs/reports/2026-09-20_forecast-evaluation.md` — the previous evaluation, its
  method and its numbers. Update this file, do not replace it.
- `backend/app/forecast/runtime.py`, `preprocess.py` — the NumPy runtime.
- `backend/tools/forecast_parity.py`, `forecast_eval.py` — the two scripts.
- `$R/forecasting/small_followup/models.py` — the anchored architecture.
- `$R/forecasting/artifacts/forecast-small-followup/selection.json` — the scores.
- `docs/features/history-import.md` — where the shipped forecast is described.
- `CLAUDE.md` — working agreement. Binding.
- Memory: `ensemble-evaluated-on-real-account`, `vthacks-forecast-data-ceiling`,
  `history-import-lane`, `main-merged-and-deployed-2026-09-20`.

# Handoff — isolated spending forecast (2026-09-19)

**Purpose of the next chat:** review and integrate the completed v1 predictor/adapter within its accounting limits, or implement the designed v2 MLP/TCN/GRU/tiny-Transformer comparison without altering another agent's worktree. Nathan also asked about cross-source self-supervised pretraining; its design is recorded separately, not implemented.

## Context

Overdraft Guard is Nathan's solo VTHacks14 project. The existing exact solver and API are another workstream's responsibility. This branch acquired and audited IBM TabFormer synthetic card histories and MoneyData's real single-person ledger; compared recent/weekday/ridge controls with a three-seed 8,942-parameter MLP; saved reproducible models and forecasts; and tested a standalone adapter against the unchanged solver. Both neural candidates failed the promotion gate. Every saved artifact remains experimental.

Nedbank access update after v1 packaging: the user verified Zindi, Codex observed that the verification banner disappeared, and the final rules dialog was identified. The user then clicked final acceptance and reported that Zindi refused joining because the challenge had ended. That rejection is user-reported; Codex did not independently capture its error dialog. No acceptance was performed by Codex and no Nedbank records were downloaded or trained. Do not repeatedly ask the user to verify or accept again. Obtain another authorized source or organizer-provided access, without bypassing the access restriction. Keep authentication tokens out of documentation.

## Working branch / worktree

Branch `codex/spending-forecast`, worktree `/Users/nathanstough/Documents/Codex/worktrees/vthacks-forecast`. Base is `c6ef8fafc5d982cd2e3b7f4c09710bdc4f545c1b`; setup checkpoint `ffc7ba1`; frozen implementation checkpoint `2a57973`. Subsequent commits contain acquisition, audits, adapter, reporting and artifact validation. Inspect `git log` and `git status --short` before work. Only explicit owned paths should be staged; never sweep other work into a commit.

Owned paths are `forecasting/`, `docs/forecasting/`, and the preserved pilot in `experiments/residual_forecast/`. Do not edit the source checkout `/Users/nathanstough/Desktop/VT Hacks`, other agents' branches, existing solver/schema/API/frontend, candidate generation, Nessie or deployment. No merge/push/deploy has been performed or authorized by this goal. Scope is recorded in `goal.md` and `deadline-and-ownership.md`.

## Environment / setup

The dedicated interpreter is `forecasting/.venv/bin/python`, Python3.14.7, with dependencies pinned in `forecasting/requirements.txt`. It was created from the existing interpreter and installed from the read-only source wheel cache; no shared environment changed. From this worktree root:

```sh
forecasting/.venv/bin/python -m forecasting.predict --model forecasting/artifacts/ibm-public-v1/default.json --history forecasting/artifacts/ibm-public-v1/example-history.json
PYTHONPATH="$PWD:$PWD/backend" forecasting/.venv/bin/python -m forecasting.examples.solver_adapter
```

Use `forecasting/README.md` for acquisition/preparation/training commands. A training run requires unchanged processed data/audit/policy fingerprints and a new run ID; it refuses overwriting an existing directory. Reproducing v1 is not a new independent test or permission to tune on its final results.

## What to do next

1. Read the model card and data audit before selecting an integration. IBM's model emits `card_spending` and is deliberately rejected by the checking adapter. MoneyData's model emits total posted outflow with unknown `SOURCE_NATIVE` currency and is also blocked from currency-specific integration. Neither is validated residual spending.
2. Coordinate with Claude's recurrence and candidate generator. Supply observed history and known schedules with evidence of non-overlap. Forecasted aggregates must never become invented cancellation candidates. If those prerequisites are not satisfied, use the labelled synthetic adapter example and keep the real-data claims at benchmark level.
3. For v2, freeze a new config/split before selection. Required candidates: MLP, TCN, GRU and the requested tiny Transformer (32 dimensions, two heads, two layers, approximately18.7k parameters), all three seeds, strong simple baselines. The full design is in `architecture-bakeoff.md`; it has not been implemented or run. Old test outcomes cannot be advertised as fresh evidence.
4. If testing SSL transfer, use `transfer-learning-design.md`. Split before any pretraining; exclude final people/periods even when labels are hidden. Source-balanced sampling and separate target semantics matter. Logs do not provide the recommendation/action/outcome rewards needed to justify RL on the tiny dataset.
5. Review current app branch/API before any later merge. The source handoff's `main` branch label and “at most one candidate per transaction” restriction were stale: current code permits alternatives but selects at most one for a target. The backend owner controls actual integration and deployment.

## IMPORTANT — tests & at-risk artifacts

From the forecast worktree:

```sh
PYTHONPATH="$PWD:$PWD/backend" forecasting/.venv/bin/python -m pytest forecasting/tests -q
PYTHONPATH="$PWD:$PWD/backend" '/Users/nathanstough/Desktop/VT Hacks/.venv/bin/python' -m pytest backend -q -m 'not perf'
PYTHONPATH="$PWD:$PWD/backend" forecasting/.venv/bin/python -m forecasting.examples.solver_adapter
```

- Forecast tests: **133 passed** (0.95s on the last complete run). Covers acquisition, preprocessing, gradient check, metrics, metadata/serialization, chronology/missingness and adapter behavior.
- Backend regression gate: **977 passed, six performance tests deselected**, one upstream deprecation warning,5.84s. Existing backend is unchanged. The source interpreter is read-only and supplies FastAPI/TestClient dependencies absent from the minimal forecast environment.
- Solver example: minimum balance 7,000 cents schedule-only;3,500 with synthetic500c/day residual;−3,500 with1,500c/day. No candidate actions are fabricated.
- **At risk / Git-ignored:** `forecasting/data/raw/` contains the278.6MB IBM archive, both MoneyData originals, licenses and source metadata. `forecasting/data/processed/` contains NPZ windows and numeric audits/manifests. `forecasting/artifacts/{ibm,moneydata}-public-v1/` contains trained checkpoints, final predictions, exact policy, results and examples. Preserve them; do not clean before verifying the archive described in `retention.json`.
- **Environment:** `forecasting/.venv/` is not archived; recreate using pinned requirements and available trusted wheels. The shared source `wheels/` directory is outside this branch and was not changed.
- **Prior pilot:** `experiments/residual_forecast/` is preserved, with binaries ignored; its existing archive is `/Users/nathanstough/Documents/Codex/2026-09-18/i-x20/outputs/residual-forecast-pilot.zip`.
- **In flight at packaging:** no training/download jobs, cloud runs, scheduled tasks or PRs from this workstream. Later access update: Zindi refused registration to the closed challenge after the user's verification/acceptance attempt; all TCN/GRU/Transformer/SSL work remains design-only.

## Analytical notes

IBM:24.39M raw rows,26,579/5,822/5,481 windows, disjoint users and2016/17/18 target years. Default weekday baseline final14-dayMAE434.19 versus selectedMLP438.19; paired95% improvement interval[−10.00,+2.10]. ThreeMLPseedfits totaled2.35seconds. This is synthetic USD card activity, not a checking ledger.

MoneyData:6,567 rows from one person;96/24/24 temporal windows. Default ridge(alpha100)14-dayMAE989.74 versus selectedMLP1,055.41 source-nativeunits. The workbook has2,621day/monthswaps, so the checked author CSV is used. An84,000-unit transfer shifts validation. Currency remains unverified and weekend purchases post Monday.

The predictor needs exactly56consecutive observed daily rows. Missing dates/unknown observations are rejected, not filled with zeros. Training datasets necessarily assumed completeness inside the observed source span; this unresolved limitation is disclosed. No known-bill exclusion, calibrated uncertainty, probability of solvency or learned preference model is delivered.

An independent review fixed exact-policy-byte preservation and strict predictor artifact validation. The IBM run originally saved reformatted policy JSON; the original hash-matching bytes were restored with a packaging note and the original reformatted copy retained. No result/weight changed and no training rerun occurred.

## Pointers

`model-card.md`, `data-audit.md`, `acquisition.md`, `source-manifest.json`, `adapter.md`, `goal.md`, `deadline-and-ownership.md`, `architecture-bakeoff.md`, `transfer-learning-design.md`, `retention.json`, and `forecasting/README.md`.

# Goal: an evaluated spending forecast ready for integration

Established September 19, 2026 at Nathan's request. This is the scope of the dedicated Codex forecasting workstream, separate from the agents implementing the backend and frontend.

**Objective:** acquire and audit the best accessible licensed transaction histories; compare a small neural network against strong simple forecasts; deliver a reproducible predictor and a standalone adapter compatible with the existing cash-flow solver. Keep the baseline as the default when the network does not establish a reliable advantage.

## Isolation and ownership

- Branch: `codex/spending-forecast`.
- Worktree: `/Users/nathanstough/Documents/Codex/worktrees/vthacks-forecast`.
- Starting commit: `c6ef8fafc5d982cd2e3b7f4c09710bdc4f545c1b`, the inspected committed backend tip.
- Other active trees: `/Users/nathanstough/Desktop/VT Hacks` on `backend`; `/Users/nathanstough/Desktop/vthacks-frontend` on `frontend`.
- Owned paths: new `forecasting/` implementation, tests, local data/artifacts, `docs/forecasting/` documentation, and the preserved `experiments/residual_forecast/` pilot copy.
- The original README edit and untracked experiment in the backend tree stay intact. The new worktree starts from committed code; it does not sweep in another agent's uncommitted changes.
- Use a dedicated environment for new dependencies. Reading the original interpreter or wheel cache is fine; installing into a shared environment is outside this workstream.

The workstream consumes the existing solver and schema as dependencies. It does not change the solver objective, API schema, endpoint, frontend, candidate generator, recurrence detector, Nessie integration, or deployment. Its tests may import and call the existing solver in this worktree. A later integration change can be reviewed and merged by the owning workstream.

This authorization schedules isolated forecasting work; it does not change the other agents' release gates or reserve their time. No merge, push, public release, cloud rental, or financial action is part of this goal.

## Deliverables and acceptance criteria

### 1. Audited data with a defensible target

Try Nedbank/Zindi first, beginning with the dictionary and README. Record source/version, access terms, real or synthetic provenance, hashes, units/currency, timestamp semantics, user/account relationships, and all exclusions. Count usable accounts, observations, date coverage, duplicates, missingness, and available 56-day context plus 14-day target windows from the actual data.

Use only licensed public data or data separately authorized for this purpose. Do not use Nathan's private bank export as an implicit fallback. Do not turn a currency amount into USD merely by relabeling it. Keep acquisition failures explicit and retain raw sources unchanged.

Target: 14 daily outflow estimates from at least 56 prior observed days. Call the output *residual spending* only when known-bill exclusion has been validated using information available at each forecast date. Otherwise report the benchmark as total posted outflow or card spending, whichever the source actually supports.

### 2. Evaluation fixed before final results

Create a versioned evaluation configuration before model selection. Group related accounts/cards by person, separate held-out people where possible, respect chronological cutoffs, and cover all forecast start weekdays. Fit preprocessing on training data only. Preserve a final holdout that is not used for tuning.

Compare a recent-28-day average, an eight-week weekday average, a regularized linear model, and one small neural network with three initializations. Select model settings and the strongest baseline using validation data. Compare that selected baseline against the selected neural model on the final test.

Report daily MAE, 7-/14-day cumulative-spending MAE, signed bias, average underprediction, and measured preprocessing/training/inference times. Use customer-level bootstrap uncertainty rather than pretending overlapping windows are independent. With a single-person case study, report that limitation and use an appropriate temporal analysis instead of a population claim.

The original synthetic pilot stays unchanged and is not a fresh holdout. It scored $103.26 versus $103.16 for the weekday baseline on its artificial 14-day target; it did not justify neural promotion.

### 3. Explicit model-selection outcome

Precommitted neural promotion gate for a representative multi-customer evaluation:

- At least 5% lower 14-day total MAE than the validation-selected strongest baseline on the final holdout.
- A 95% customer-bootstrap interval for the paired improvement excludes zero in the network's favor.
- Mean 14-day underprediction is no more than 5% higher than the baseline; if baseline underprediction is zero, the network must not increase it.
- No preprocessing leakage or unresolved validity issue that invalidates the comparison.

These are project acceptance thresholds, not universal scientific rules or a guarantee of financial safety. Synthetic-only or single-person results do not establish production promotion even if numerical thresholds pass. If the gate fails, ship the baseline as the default and retain the neural candidate as experimental. **An honest negative result satisfies the research goal.**

### 4. Reproducible predictor

Deliver acquisition, preprocessing, audit, training, and evaluation commands; saved preprocessing/model artifacts; explicit model/version metadata; a model card; and a readable results report. Include targeted tests for chronology, grouping, amount/date normalization, deterministic inference, serialization, and failure handling.

Inputs must distinguish missing observations from genuine zero spending. Outputs are dated point estimates with provenance and a clear target definition. No probability-of-solvency or confidence-band claims without a separately validated method.

### 5. Standalone solver adapter

Provide a small callable interface and example that take a forecast plus supplied known scheduled events and produce a valid existing `SolveRequest` without changing its schema.

- Forecast rows use stable IDs, ISO dates, negative integer-cent amounts, an explicit rounding rule, and `kind: discretionary`.
- Preserve the input's known events, user protections, supplied candidates, and previous-plan semantics.
- Keep model/provenance metadata in a sidecar: the current API rejects unknown fields.
- Do not add forecast spending that overlaps supplied known events. A total-spend benchmark cannot be silently appended to an already complete schedule; require a validated residual target or an explicitly non-overlapping application.
- Do not create skip/cancel candidates against aggregate predictions. Forecasted ordinary spending is not evidence that a specific future payment can be cancelled.
- Validate the example against the frozen request schema and call the existing solver in this worktree. Demonstrate that different forecast assumptions produce appropriately conditional schedules/results.

No frontend wiring is necessary to finish this workstream. The deliverable is an integration-ready package with an executable example, not an unreviewed change to another agent's app.

## Work sequence

1. Acquire a small sample and establish provenance, target, and usable history coverage.
2. Freeze preprocessing/splits/metrics; implement baselines and independent validation.
3. Train the small network, evaluate the selected models once on the final holdout, and record the promotion decision.
4. Package the selected predictor, implement the standalone adapter, and run targeted plus relevant integration checks.
5. Commit only owned files, write an integration handoff and results report, and leave the branch ready for review.

Independent data inspection, evaluation review, and adapter design may run in parallel. Assign subagents distinct files/directories and bounded tasks; dataset edits and final holdout evaluation remain coordinated by the root agent.

## Access contingencies and completion

If Nedbank requires unavailable login/user action, record the exact step and continue with independent work. MoneyData offers a real single-person case study; IBM TabFormer is the larger synthetic fallback. Their accounting semantics and domain differ, so report results separately.

The goal can complete with an audited synthetic benchmark and real-data access limitation, provided the predictor, adapter, tests, artifacts, and evidence report are delivered and clearly marked **not validated for real-world promotion**. Do not claim inaccessible real data was tested. A missing dependency that prevents even this scoped result remains an explicit blocker.

Completion means the owned branch contains reproducible code, data provenance/audit, frozen evaluation, measured comparisons, a model-selection decision, saved artifacts with retention instructions, a tested solver-compatible example, and a concise integration handoff. Achieving a better neural score, merging into another branch, or deploying the product is not required.

## Supporting records

### User-requested follow-on design, September 19

During execution Nathan asked for a realistic deadline plan, a conflict check against Claude's solver handoff, and a designed architecture bake-off. The design includes MLP, TCN, GRU and a **required tiny Transformer**, with a fair baseline comparison and fresh test policy. Nathan then proposed self-supervised transfer and assigned source roles: IBM/TabFormer (one dataset) for synthetic pretraining/control, audited Nedbank for real multi-customer fine-tuning/evaluation, and MoneyData only as an external one-person case study in the proposed v2—not training, SSL, fine-tuning or model selection. Preserve the already completed source-specific MoneyData v1 benchmark as historical evidence; do not pretend it was never fitted or evaluated.

These design requests are delivered in `architecture-bakeoff.md`, `transfer-learning-design.md`, and `deadline-and-ownership.md`. They do not mean the extra architectures or pretraining runs have been executed. The v1 acceptance criteria above remain the implemented deliverable, and any execution of the new study must freeze a separate configuration and honor the latest source roles.

In the worktree, read `docs/vthacks-dataset-research.md`, `docs/vthacks-training-pilot.md`, `docs/vthacks-product-and-training-plan.md`, `docs/api-contract.md`, and `docs/features/solver.md`. The older handoff's branch label says `main`; live git inspection shows the source checkout is now `backend`.

The first pilot's complete archive is retained at `/Users/nathanstough/Documents/Codex/2026-09-18/i-x20/outputs/residual-forecast-pilot.zip`; its copied raw data and checkpoints are ignored by git in `experiments/residual_forecast/`. Source code, manifests, audits, and result summaries can be committed without the large binaries. Do not clean these run directories until their archives and hashes are verified.

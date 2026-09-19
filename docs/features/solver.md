# Feature: solver core

Living document. Updated with every change to the solver. Run specs:
`docs/specs/2026-09-19_solver-core.md` (first). Restored Sat 01:50 after a parallel
session overwrote it; that session's draft is preserved at
`docs/specs/2026-09-19_backend-solver-service.SUPERSEDED.md`.

## What it does

Given a dated schedule of income and outflows, an opening balance, a cushion, and a set
of candidate changes (skip / defer / downgrade / cancel, each freeing a known amount on
a known date), return the fewest changes that keep the end-of-day balance above zero
through the horizon, prove that none can be removed, and — when no set suffices — say
exactly how much external cash is needed and by when.

Prescriptive, exact, stateless. Not a forecast, not a model. The solver trusts dated
inputs: payday business-day adjustment, month-end cadence, and transfer netting happen
upstream in candidate generation (`docs/features/candidates.md`) / recurring detection
(later run spec).

## Contract

`POST /api/solve` — `docs/api-contract.md`. Integer cents, `YYYY-MM-DD` strings, horizon
inclusive both ends, `opening_balance_cents` = available balance at the start of `as_of`.

## Objective (lexicographic, minimised in order)

1. days below zero
2. worst shortfall below zero
3. buffer-missed flag — 0 if every day ≥ `buffer_cents`, else 1
4. cardinality — number of changes
5. below-buffer exposure — Σ max(0, buffer − balance)
6. pain — Σ candidate pain (1..5)
7. hysteresis — symmetric difference against `previous_plan`
8. sorted candidate-id tuple (deterministic; the optimum is unique)

Consequence: the plan is the smallest set at every tier. If any set holds the cushion,
the smallest such set wins (tier 1); otherwise the smallest set that clears zero (tier
2); otherwise the plan with the fewest fee-days and shallowest dip (tier 3). On the three shipped
fixtures this coincides with the stand-in's older order, so the difference is
visible only across a sweep: over openings from $30 to $300 the two orders pick
different plans in 76 of 271 cases, and this one never picks more changes —
fewer in 72 of them, and the same number in the other 4, where only the
tiebreak differs.

## Constraints

- At most one chosen candidate per `target_txn_id`. A search constraint in both engines,
  not a validation rule: offering two competing changes on one transaction is legal input,
  and the generator does it on purpose (`docs/features/candidates.md`).
- `freed_cents ≤ |target transaction amount|` (validation, 422).
- Lead time: a candidate is actionable iff `effective_date − as_of ≥ lead_time_days`.
- Locks: out → never chosen; in → always chosen when actionable; in-but-past-lead-time →
  excluded and listed in `meta.excluded_locked_in`.

## Engines

- **CP-SAT** (OR-Tools 9.15): balances are linear expressions; days-below-zero and the
  buffer flag via half-reified enforcement literals; worst shortfall and exposure via
  epigraph variables. One solve per objective term, each term's found value pinned as a
  bound for the next; term 8 by sequential assumption-fixing in ascending-id order. Total budget 6 s split
  across stages; `num_workers=1`, `random_seed=0`. Only `x` is read back; every term is
  recomputed by simulation and asserted equal. Any stage `FEASIBLE` →
  `meta.status="FEASIBLE"`, `certificate.minimal_proven=false`, wording drops "fewest".
- **Brute force** fallback: exact over ≤ 18 free candidates; refuses above (HTTP 503).
  Taken whenever OR-Tools cannot be loaded for any reason, or any of the seven numeric
  stages returns UNKNOWN or INFEASIBLE, or the budget runs out during them. The single
  exception is the id tiebreak: by then all seven numeric terms are proven, so losing it
  costs the ordering among tied plans, not the plan, and the response says
  `minimal_proven: false` rather than starting again.
- The TypeScript stand-in `frontend/src/solver/mockSolver.ts` implements the same
  objective and is run through Node as an independent oracle (`backend/tests/oracle/`).

## Tiers

| Tier | Condition (with-plan balance) | Output |
|---|---|---|
| 1 | ≥ buffer every day | plan + certificate |
| 2 | ≥ 0 every day, < buffer somewhere | plan + certificate, "no room left" wording |
| 3 | < 0 somewhere | best partial plan + `external_cash_needed {amount, by_date}` |

The word *infeasible* never appears. Wording says "sufficient under the schedule shown",
never "guaranteed". With zero changes at tier 3 the wording states the gap, not "clears".

## Certificate

For each chosen item, remove it and re-simulate. Report the absolute worst dip and its
date, plus `marginal_cents` (how much deeper than the plan itself) and `marginal_days`.
An item is load-bearing iff either marginal is > 0; `irredundant` iff all are. This is
marginal rather than absolute because "plan-minus-one goes below zero" is vacuously true
at tier 3. `plan[].strictly_needed` mirrors load-bearing for the UI.

## Ordering rules (shared with the oracle)

`plan` sorted by (`date`, `candidate_id`) in code-point order; `certificate.per_item` in
plan order; `changes_here` and `meta.excluded_locked_in` sorted; `worst_date` and the
"tightest day" are the first day of their extremum; `external_cash_needed.by_date` is the
first day below zero (the day the money must be there), while `amount_cents` covers the
deepest dip.

## Stability

Cushion (`buffer_cents`), hysteresis via `previous_plan`, single worker, fixed seed,
unique optimum. Deficit rounding was considered and dropped. Hints are warm starts only,
never fixed.

## Pain scores — V1 and V2

V1: pain is an input (category defaults from candidate generation —
`backend/app/candidates/policy.py`, documented in `docs/features/candidates.md`); the user corrects it
with lock toggles, which re-solve instantly. **V2 (roadmap):** learn pain scores from
lock/override behaviour across users with a small model. Learning belongs on the
estimation side (pain, recurrence, income timing); the decision stays exact. There are
no counterfactual action labels to train a decision model on, and a learned decision
cannot prove minimality or name the binding day.

## Known gaps

- One `freed_cents` on one `effective_date` per candidate: a cancel that removes two
  billings in the horizon must be expressed as two candidates. The generator does this,
  one per occurrence; see `docs/features/candidates.md`.
- Limits: horizon ≤ 366 days, ≤ 60 candidates, ≤ 2000 scheduled rows, |cents| ≤ 10^11.
- The frontend's `as_of` comes from a browser `Date`; the backend never touches time.

## Tests

`backend/tests/` — see the run spec's acceptance criteria. Gate:
`.venv/bin/pytest backend/ -q -m "not perf"`. Perf numbers: `-m perf`, reported not gating.

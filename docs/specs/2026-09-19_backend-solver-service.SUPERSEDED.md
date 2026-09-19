> **SUPERSEDED Sat 2026-09-19 ~01:50.** Written by the frontend session in parallel. Nathan decided the solver-core session builds the whole backend; the active run spec is `2026-09-19_solver-core.md`. Kept for the ideas it contributed (one candidate per transaction, freed <= |amount|, candidate generation as a later run spec).

# Run spec — backend solver service

**Change:** `backend-solver-service` · **Date:** 2026-09-19 · **Branch:** `main`
**Status:** planned (execution pending plan approval)

Frozen after commit. Do not edit later; add a dated note instead.

---

## Problem

The product's claim is that the returned plan is exactly minimal and provably
so. Nothing in the repo delivers that claim. `backend/` holds a requirements
file and nothing else. The running demo is a brute-force stand-in inside the
frontend (`frontend/src/solver/mockSolver.ts`), exact only because its
candidate list is eleven hand-written items.

Separately, those eleven candidate moves were authored by hand. A real
account has no such list, so the service cannot currently answer for an
account it has not seen.

## Solution

Stand up the FastAPI service the frozen contract describes, with a CP-SAT
core, plus a deterministic rule-based step that turns transactions into
candidate moves. Point the frontend at it. Keep the TypeScript stand-in in
the tree as an independent exact oracle for differential testing.

## Scope

**In:** candidate generation, the CP-SAT solver, tier and certificate
derivation, the FastAPI service, a synthetic account generator, the Python
oracle, the test suite, and the frontend swap from in-process call to fetch.

**Out, by the user's decision on 2026-09-19:** the Capital One Nessie
integration, on the grounds that the infrastructure does not exist yet; and
recurring-charge detection, which travels with the bank work.

## Design decisions

- **D1 — CP-SAT is the only engine.** The earlier design named a
  dependency-free pseudo-polynomial DP as a fallback against an OR-Tools
  install failure. OR-Tools is installed and verified in `.venv`, and a second
  engine doubles the differential-testing surface for no demo benefit. The
  fallback is deferred, not cancelled. *Deviation from the frozen design;
  flagged for approval at the plan stop.*
- **D2 — The TypeScript stand-in becomes a test oracle, not a fallback.** It
  is ported to Python and used to cross-check CP-SAT. It is independent of the
  new code, which is what makes the check meaningful.
- **D3 — The objective is strictly lexicographic.** Implementation chosen in
  the plan. A weighted sum is only acceptable if it is proven to preserve
  strict ordering at the problem's value ranges.
- **D4 — Determinism is a product requirement, not a nicety.** Single worker,
  fixed seed, fixed time limit. Byte-identical repeat solves are an acceptance
  criterion, because the memo measured a 21% plan-flip rate under small input
  jitter before mitigation.
- **D5 — At most one candidate per target transaction may be selected.**
  Enforced twice: generation emits at most one per transaction, and the model
  carries the constraint regardless of what the caller sends. Needs no new
  contract field, since `target_txn_id` already exists. The guarantee is
  recorded in the contract document.
- **D6 — Minimality is claimed only on a proven-optimal solve.** A
  feasible-but-unproven result must not be described as smallest.
- **D7 — Candidate generation is rule-based and deterministic.** No model, no
  randomness, stable ordering.
- **D8 — One process, one port.** The service serves the built frontend as
  static files alongside the API.

## Acceptance criteria

| # | Criterion |
|---|---|
| AC1 | CP-SAT and the ported oracle return identical objective vectors and identical chosen-candidate sets across 2,000 random instances |
| AC2 | Twenty repeat solves of one request are byte-identical |
| AC3 | The three committed sample accounts return the same tier, plan membership and certificate sentence through the API as the stand-in returns today |
| AC4 | No response selects two candidates sharing a `target_txn_id`, and no candidate frees more than its target transaction's absolute amount |
| AC5 | Irredundancy is claimed only where brute force confirms no proper subset of the plan also clears zero |
| AC6 | A balance exactly equal to the buffer is tier 1; a tier 3 response names an amount and date which, added, makes the plan clear, verified by re-solving |
| AC7 | The word "infeasible" appears in no user-visible string across 500 generated responses |
| AC8 | Inclusive horizon, day-zero balance, payday-eve and payday endings, and 28, 30 and 31 day month spans are each asserted |
| AC9 | Malformed dates, a reversed horizon, a negative buffer, float money and an unknown `target_txn_id` are each rejected with a clear error, never silently coerced |
| AC10 | The service serves the built frontend and the API from one process on one port |
| AC11 | Slider drags are debounced, and an out-of-order response never paints a stale plan |

## Tests

Full failure-mode inventory is in the P2 record: roughly 84 tests across
candidate generation (22), the solver (30), tier and certificate (14), the
service (12) and frontend integration (6).

```bash
.venv/bin/pytest backend/ -q
```

```bash
cd frontend && npm run build && npm run lint
```

**Regression** means any of: the differential test disagreeing on even one
instance, repeat solves differing, a certificate claiming irredundancy that
brute force contradicts, or any sample account changing tier.

## Documents this change edits

- `docs/specs/backend-solver-service.md` (this file)
- `docs/features/solver.md`
- `docs/api-contract.md`, adding the one-candidate-per-transaction guarantee
- `README.md`, layout and how to run the service

## Results

Filled at execution.

- Test results: _pending_
- Claude critique verdict: _pending_
- Codex audit scorecard: _pending_

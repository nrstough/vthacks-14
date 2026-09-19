# Run spec — solver core + `/api/solve`

Created: Sat 2026-09-19 ~01:15 · Branch: `main` · Pipeline: `/plan-review` (deep)
Status: **planned** (frozen at commit; do not edit after)

## Problem

The product's claim is that it returns the *fewest* dated spending changes that keep the
daily balance above zero until payday, and proves it. No backend exists. The frontend
(other session) already builds against `docs/api-contract.md` with a brute-force
TypeScript stand-in (`frontend/src/solver/mockSolver.ts`). This change implements the
real solver in Python to that contract, proven against the stand-in as an independent
oracle, and exposes it at `POST /api/solve`.

## Scope

**In:** request/response schemas (strict), date/horizon arithmetic, balance simulation,
candidate eligibility (lead time, locks), exact solve (CP-SAT primary, brute-force
fallback), lexicographic objective, tiers, external-cash figure, irredundancy
certificate, response assembly, FastAPI app (`/health`, `/api/solve`, static mount),
fixtures, ~100 tests, oracle parity harness, docs.

**Out:** Nessie client, recurring detection, synthetic account *generator* (fixtures are
hand-planted here), frontend changes beyond the D1 patch to `mockSolver.ts`, deploy.

## Design decisions

- **D1 — Objective order** (lexicographic, all minimised):
  1. days below zero · 2. worst shortfall below zero · 3. buffer-missed flag (0/1) ·
  4. cardinality · 5. below-buffer exposure (Σ max(0, buffer − balance)) · 6. pain ·
  7. hysteresis (symmetric difference vs `previous_plan`) · 8. sorted candidate-id tuple.
  Rationale: "smallest set" is true at every tier and the contract's tier definitions
  follow directly. Note (corrected Sat 01:20 after independent brute force): on the three
  shipped fixtures D1 and the oracle's current order pick the same plans — `tight`
  genuinely needs 8 of 11 (all seven pre-payday candidates are required to clear Sep 24
  by $7.38). D1 differs only when a smaller set clears zero but a larger one holds the
  cushion; AC5's per-level counterfactual tests must use planted instances.
- **D2 — Deficit rounding: dropped.** Not implemented, no config knob.
- **D3 — Engines.** Primary: OR-Tools CP-SAT, `num_workers=1`, `random_seed=0`,
  `max_time_in_seconds=2.0` per stage. Fallback when `ortools` cannot be imported:
  exhaustive brute force over free candidates, refused above 18 free candidates with
  `EngineUnavailable` (never a heuristic). The memo's DP is not used: it cannot express
  the 8-term objective or deferrals.
- **D4 — Lexicographic by sequential solves.** One CP-SAT solve per objective term; after
  each, the term's optimum is added as an upper-bound constraint. No weighted sums (no
  dominance/overflow risk). If any stage returns `FEASIBLE` (time limit), `meta.status =
  "FEASIBLE"` and `certificate.minimal_proven = false`; the plan is still returned.
- **D5 — Contract additions (additive only).** Request: `previous_plan: string[] = []`
  (hysteresis input; the server is stateless). Response: `meta.excluded_locked_in:
  string[]` (sorted), `certificate.minimal_proven: bool`, `certificate.per_item[].
  marginal_cents`, `.marginal_days`, `plan[].strictly_needed: bool`. Schemas are strict
  (`extra="forbid"`).
- **D6 — Locks.** Unknown ids in `locks` → 422. Same id in both → 422. Locked-out never
  chosen. Locked-in candidates are taken in ascending-id order and kept only if they do
  not duplicate an earlier forced candidate's `target_txn_id`; free candidates exclude any
  txn held by a forced one. Locked-in ids not forced (past lead time, or duplicate txn)
  are listed sorted in `meta.excluded_locked_in` (oracle lines 197–205, 385–388).
- **D7 — Certificate is marginal (amended Sat 02:15 to match oracle 8dca802).** For each
  chosen item i, re-simulate the plan without it: `worst_shortfall_cents`, `worst_date`,
  `marginal_cents = worst_without − worst_with_plan`, `marginal_days = dbz_without −
  dbz_with_plan`. An item is load-bearing iff `marginal_cents > 0 or marginal_days > 0`;
  `irredundant` = all load-bearing; `worst_item` = first strict max of `marginal_cents` in
  plan order. Rationale: the absolute test ("plan-minus-one goes below zero") is vacuously
  true at tier 3. `plan[i].strictly_needed` = load-bearing.
- **D8 — Oracle parity harness.** `backend/tests/oracle/dump.ts` executed via
  `node --experimental-strip-types` (Node 22.17 present, no installs). Structural fields
  compared; prose compared only for containment of the money/date.
- **D9 — Dates.** `datetime.date` only; no `datetime`, no timezones. Horizon inclusive on
  both ends. `opening_balance_cents` is the balance at the *start* of `as_of`; a
  transaction dated `as_of` is applied once.
- **D10 — Deferral semantics** (match oracle): `+freed_cents` on `effective_date`,
  `−freed_cents` on `recharge_date`; a recharge after `horizon_end` never returns within
  the horizon.
- **D11 — Module layout.** `backend/app/{main.py, schemas.py}`,
  `backend/app/solver/{dates.py, simulate.py, eligibility.py, objective.py,
  engine_cpsat.py, engine_brute.py, certificate.py, tiers.py, wording.py, assemble.py,
  solve.py}`, `backend/tests/{conftest.py, fixtures/, oracle/, test_*.py}`,
  `backend/pytest.ini`.

## What will change

- Create everything under `backend/app/` and `backend/tests/`.
- Edit `frontend/src/solver/mockSolver.ts`: `scoreOf` order per D1, sorted-id tiebreak,
  `previousPlan` unchanged. **Only after the frontend session has committed its work.**
- Edit `docs/api-contract.md`: Objective section per D1; D5 additive fields.
- Create `docs/features/solver.md`; update `README.md`, `docs/prize-strategy.md`.

## Acceptance criteria (each maps to a test in P2)

- AC1 Strict validation: every malformed input class in P2-A → 422 with a field path.
- AC2 Horizon arithmetic exact across 1-day, month-end, non-leap Feb, DST spans.
- AC3 Accounting identity holds per day; defer semantics per D10; day-0 applied once.
- AC4 Lead-time boundary inclusive (`effective − as_of ≥ lead`); locks per D6.
- AC5 Plan is minimal-cardinality subject to D1 order; each objective level pinned by a
  counterfactual instance; planted greedy-fails instance beats greedy.
- AC6 CP-SAT ≡ brute force on 100 random instances (cuttable to 30); Python ≡ TS oracle on 3 fixtures + 50
  random; fallback ≡ CP-SAT on all fixtures; 19 free candidates without ortools → error.
- AC7 Tier boundaries exact to the cent; tier 3 exercised by a planted cancel-everything
  instance; `external_cash_needed` = minimal worst shortfall, `by_date` = first breach.
- AC8 Certificate per D7, hand-verified on a fixture; sentence carries money + date.
- AC9 Determinism: 10 repeats byte-identical minus `wall_ms`; ±$40 sweep flip rate ≤ 15%
  reported.
- AC10 Response: `balances` length = T; `changes_here` partition of plan; `is_payday`;
  plan sorted; `shortfall.total_cents`; `types.ts` ↔ pydantic field parity test.
- AC11 API: fixtures → 200 schema-valid; validation → 422 never 500; `/health`; static
  mount conditional on `frontend/dist`.
- AC12 Performance: fixtures median < 150 ms; n=40/T=60 < 2 s; brute n=18 < 5 s.
- AC13 No response string contains `infeasib` or `guarantee`.
- AC14 Implementation-free invariants on every fixture, planted and random response
  (adopted from the frontend session's critique that a port is not an independent check):
  (a) `with_plan_cents[t] == baseline_cents[t] + Σ deltas of plan items through t`;
  (b) re-simulating the plan reproduces `shortfall` and `tier`; (c) each `per_item` row is
  reproduced by re-simulating the plan minus that item; (d) at tier 3, adding
  `external_cash_needed.amount_cents` on `by_date` and re-simulating clears zero;
  (e) no two plan items share `target_txn_id`; (f) `strictly_needed` ⇔ load-bearing;
  (g) `plan` ids == `changes_here` union == `per_item` ids.
- AC15 FEASIBLE path (stages 1–7 and stage-8 UNKNOWN): with `CpSolver.solve` monkeypatched to report FEASIBLE, response is
  schema-valid, `meta.status == "FEASIBLE"`, `certificate.minimal_proven == False`, and the
  verdict contains neither "fewest" nor "smallest".

## Commands

```bash
cd "/Users/nathanstough/Desktop/VT Hacks" && .venv/bin/pytest backend/ -q
cd "/Users/nathanstough/Desktop/VT Hacks/frontend" && npm run build
```

## Docs committed to

`docs/specs/2026-09-19_solver-core.md` (this), `docs/features/solver.md` (create),
`README.md`, `docs/prize-strategy.md`, `docs/api-contract.md` (Objective + D5),
`frontend/src/solver/mockSolver.ts` (D1 patch, after frontend commit).

## Results — executed Sat 2026-09-19, 01:43–02:10

**Tests: 788 passing** (`.venv/bin/pytest backend/ -q -m "not perf"`, 4.9 s), plus 6 perf
tests reported separately. Frontend build clean.

| Suite | Tests | Covers |
|---|---|---|
| `test_parity.py` | 8 | AC6 — 53 instances vs the Node oracle, both engines, fallback, refusal |
| `test_invariants.py` | 477 | AC14 — 53 cases x 9 properties, rebuilt from the request |
| `test_objective.py` | 43 | AC5 — every objective rule, both engines |
| `test_engines.py` | 12 | AC15 — unproven search, tiebreak timeout, refusal, 40-candidate scale |
| `test_validation.py` | 39 | AC1 |
| `test_dates.py` | 24 | AC2, incl. a Node cross-check of money/date formatting |
| `test_simulate.py` | 11 | AC3 |
| `test_eligibility.py` | 10 | AC4 |
| `test_tiers.py` | 12 | AC7 |
| `test_certificate.py` | 9 | AC8 |
| `test_stability.py` | 6 | AC9 |
| `test_response.py` | 11 | AC10 — `types.ts` and the models agree field for field |
| `test_api.py` | 15 | AC11 |
| `test_wording.py` | 105 | AC13 |
| `test_perf.py` | 6 | AC12 (`-m perf`) |

**Measurements.** Demo accounts solve in 3.5–5.5 ms. Sixty changes over a sixty-day
horizon: 27 ms. A hundred random accounts: 3.1 ms each. Exhaustive search at its
eighteen-change cap: 3.0 s — which is why CP-SAT is the default rather than a nicety.
Plan-flip rate across eighty-one one-dollar steps of the opening balance: **8.8%**
(threshold 15%), and lower with the previous plan remembered than without.

CP-SAT answered 200/200 generated instances with zero disagreements against exhaustive
search, and 53/53 against the TypeScript reference.

**Deviations from the decisions above, all deliberate:**

- *D3's `max_time_in_seconds=2.0` per stage* is superseded by R1: one monotonic six-second
  deadline shared by every solve including the tiebreak. Eight independent two-second
  limits would have allowed sixteen seconds.
- *D11's module list* gained `app/solver/errors.py`. `EngineUnavailable` is named by both
  engines and by the API layer, and neither engine should have to import the other.
- *Stage 8* is skipped when an earlier stage was not proven optimal: without a proven
  cardinality the tiebreak is not well defined, and an arbitrary choice among near-ties is
  worse than reporting the search was cut short.
- *The reference solver was not edited by this session.* The frontend session had already
  implemented D1, the sorted-id tiebreak, one-change-per-transaction, marginal
  irredundancy and first-breach deadlines (`8dca802`, `0c6e0c5`), and made the three
  parity fixes on request (`21c6ecf`). The D1 patch in the plan was therefore a no-op.
- *AC6's instance count* reads 100 in the spec; parity runs 53 against the oracle and 200
  against exhaustive search in a separate sweep.

**One genuine disagreement with the reference solver**, asserted rather than tolerated:
with an empty plan it always says "No changes needed. The schedule already clears." At
tier 3 the schedule does not clear, so this service states the gap instead. A separate
test fails if no instance exercises that branch.

### Audit round 1 (adversarial Claude critique, ~02:20)

Verdict **Fail**, on Test coverage alone; every other dimension Acceptable or better, and
freeze integrity Excellent. The critique ran 2,400 fuzz instances, 26 hand-built cases and
36 mutants. Findings and what was done:

| # | Finding | Resolution |
|---|---|---|
| F1 | **A schema-valid request returned HTTP 500.** Input bounds (±10^11) were applied to *derived* response figures; a large opening balance plus one charge leaves that range, and `build_response` raised past the error handler. | Fixed: `DERIVED_CENTS_ABS` for balances, totals and shortfalls. Repro added in round 2 — see F1-bis. |
| F2 | Two adjacent objective levels had no counterfactual: swapping days-below-zero with worst-shortfall, or pain with hysteresis, left all tests green. | Fixed: `DAYS_BEAT_DEPTH` and `PAIN_BEATS_MEMORY` planted instances. Both swaps now fail 2 tests. |
| F3 | A CP-SAT deferral crediting the recharge day survived the suite. | Fixed: `DEFER_LANDS_IN_HORIZON`. The mutant now fails 4 tests. |
| F4 | The model/ledger cross-check — the only guard against F3's class — had no test at all. | Fixed: a lying engine fixture. Disabling the check now fails 1 test. |
| F5 | The exhaustive-search timing bound was 30 s against the spec's 5 s. | Fixed: tightened to 5 s. Measured 2.8–3.0 s. |
| F6 | `types.ts` parity skipped the three inline object literals, so `meta.excluded_locked_in`, `shortfall.total_cents` and `external_cash_needed.by_date` were unchecked. | Fixed: inline literals parsed and compared. |
| F7 | Two Codex resolutions were only partly implemented. | Planted-vs-oracle parity added. The promised subprocess test for a missing OR-Tools is **deliberately not added**: the `load_cpsat` seam covers the substance and a subprocess test would be slower and flakier. |
| F8 | The certificate's first-wins tie rule was untested. | Fixed: `EQUAL_MARGINALS` unit test. The `>=` mutant now fails. |
| F9 | Determinism tests excluded all of `meta`, not just `wall_ms`. | Fixed: `stable_part()` compares everything but the timing. |
| F10 | `docs/features/solver.md` claimed the `tight` account needs 8 of 11 changes; the fixture was retuned and needs 3. | Fixed, with the sweep result that actually supports D1 in its place. **The same now-stale figure appears in D1's own note above (line ~35), which is frozen: read it as superseded.** The `tight` preset became $180 against a $100 cushion in `0c6e0c5` and solves in 3 changes at tier 2. D1's real support is the sweep: across openings from $30 to $300 the two orders differ on 76 of 271, and D1 never picks more — fewer in 72, the same in 4 where only the tiebreak differs. |
| F11 | The contract documented no 503, and its limits read as if they bound derived figures. | Fixed in `docs/api-contract.md`. |
| F12 | Two unreachable branches in `assemble.py`. | Removed. |

**Tests after the round: 810** (was 788). All five previously-surviving mutants confirmed
killed by re-running each against the full suite.

### Audit round 2 (re-check, ~02:35)

Eleven of twelve fixes verified real and mutation-killed. The critique re-ran all six
adjacent objective swaps, twelve further mutants, 4,000 fresh differential instances, the
tiebreak against full enumeration of every tied optimum, and hand-checked the four new
planted fixtures' arithmetic independently. Two things came back:

| # | Finding | Resolution |
|---|---|---|
| F1-bis | **The F1 fix had no test, and this document claimed it did.** Reverting the fix left all 810 green, while the row above said "Repro added to `test_api.py`" — false. Worse, the bound's headroom is derived from `MAX_T`/`MAX_SCHED`/`MAX_N`/`CENTS_ABS` and nothing tied them together, so raising any cap would silently restore the 500. | Fixed: the two-value repro and the every-cap-at-maximum case in `test_api.py`, plus an invariant in `test_validation.py` that recomputes the worst case from the caps. Reverting the fix now fails 3 tests. |
| F13 | **A broken OR-Tools install returned 500, not a fallback.** The seam caught only `ImportError`, but a wheel whose native library will not load raises `OSError` from the dynamic linker, and a partial build can raise `AttributeError`. Both bypassed the fallback entirely. | Fixed: the seam catches any failure, because all of them mean the same thing and the fallback is exact anyway. Narrowing it back fails 1 test. |

Also confirmed, and left alone: swapping objective terms 2 and 3 is **provably untestable** —
`worst_shortfall > 0` implies `min_balance < 0 <= buffer` implies `buffer_missed = 1`, so the
two orderings induce an identical total order (0/691 divergences on probe). And the
subprocess test for a missing OR-Tools stays omitted: the seam is faithful to the real
failure, and it would not have caught F13 either.

One overstatement corrected: the sweep supporting D1 gives 76/271 differing plans (28%), D1
picking fewer changes in 72 and more in none — in the remaining 4 the counts are equal and
only the tiebreak differs. "Picks fewer wherever they differ" should read "never more".

**Tests after round 2: 814.**

### Audit round 3 (re-check, ~02:40) — **Acceptable**

Both round-2 findings confirmed closed by mutation: reverting the derived bound fails 3
tests, narrowing the fallback fails 1, and growing `MAX_SCHED` or `MAX_T` past the derived
ceiling fails 2. The worst-case formula was independently checked and found correct and
conservative — a chosen change's contribution to any day is in `{0, +freed}` and never
negative, because validation forces a recharge to follow its effective date inside the
horizon. 2,800 fresh differential instances, 22 edge cases, all 17 planted cases and the
tiebreak-against-full-enumeration check all came back clean.

Two residuals were raised as non-blocking and both were closed anyway: the large-value
test passed no candidates, so one of the six widened fields was never constructed by it
(now it is), and this row's wording was still overstated. The fallback also now logs why
it fell back, which it previously did not — on a box with a broken install the only
symptom was that everything got slower.

Scorecard: Plan adherence **Excellent**, Scope discipline **Excellent**, Test coverage
Acceptable, Review compliance Acceptable, Freeze integrity **Excellent**, Regression check
**Excellent**, Documentation Acceptable. **Overall: Acceptable.**

**Tests after round 3: 814.**

### Codex audit (~02:45) — **Fail**, three real findings the critique missed

Independent of the Claude rounds, and it earned its place: all three are defects, not
bookkeeping. Every one is now fixed and mutation-guarded.

| Finding | Why it mattered | Resolution |
|---|---|---|
| **Omitting `recharge_date` bypassed its validator.** A pydantic field validator does not run on a default, so a deferral *missing* the key — as opposed to sending an explicit null — was accepted. | The deferral silently became permanent savings: the money was freed and never came back, and the plan looked better than it was. Confirmed: HTTP 200 on the shipped fixture with the key deleted. | `Field(default=None, validate_default=True)`. Tests for omitted, explicit-null, and the still-legal case of omitting it on a non-deferral. |
| **A failed numeric stage returned an unproven plan instead of falling back.** R1 requires exhaustive search for ≤ 18 free candidates, or a 503. Only the first stage did that; stages 2–7 returned the incumbent as FEASIBLE. | At these sizes the other engine answers *exactly*, so the service was shipping a plan it could not stand behind when a proven one was available. `docs/features/solver.md` described the correct behaviour, so the doc was right and the code was wrong. | Any numeric stage failure now raises and falls back. The tiebreak stage remains the one exception, for a different reason. Tests at stages 2, 4 and 7, plus the no-fallback refusal. |
| **Empty-plan wording was not proof-aware.** An unfinished search that selected nothing still said "There are no changes available to close any of it" and "Nothing here can be changed in time". | Both are claims about every plan that could have been built, and on the `clears` account both are simply false — three changes clear it. | Both branches now check `minimal_proven`; `OPTIMALITY_CLAIMS` gained the three phrases so the unproven-response test covers them. |

Also fixed: the README quoted a test count that had moved twice.

Not actionable: Codex skipped Freeze integrity looking for P1/P2/P3 hashes this spec does not
use (the Claude rounds checked it directly and found it Excellent), and its one test error was
its sandbox refusing a temporary directory, not a failure.

**Tests after the Codex round: 822.**

**Claude critique verdict:** Acceptable (round 3), nothing blocking.
### Codex re-audit (~02:55) — two further findings, both fixed

| Finding | Resolution |
|---|---|
| **AC13 applied to the plan but not to the error body.** A refused request returned `503 {"detail": "stage days_below_zero returned INFEASIBLE"}` — the solver's own status name, containing the one word this product never shows anyone. | Stage and status now go to the log; the response says "the constraint solver could not finish this one". Same for the loader's message on a broken install. New API test asserts the 503 body carries none of the solver's vocabulary. |
| **AC14 says "fixtures, planted and random"; the invariants covered only fixtures and random.** The hand-built cases — where every rule is pinned — were checked by parity and by targeted assertions, but not by the implementation-free properties. | All planted cases added to the parametrisation. 977 tests. |

**Tests after the re-audit: 977** (the invariant properties now run over every planted case).

**Codex audit grade:** Fail on the first two passes, five defects between them; all fixed
and mutation-guarded. Final pass recorded below.

## Refinements from deep exploration (Sat ~01:50, before plan approval)

Three read-only agents (architecture, file impact, risk) verified the design against the
installed toolchain. These amend the decisions above and are binding for execution:

- **R1 (D3/D4)** Time budget: 6 s total, per stage `max(0.25, remaining / stages_left)`,
  not 2 s × 8. Bounds use the *found* value of each stage, never `BestObjectiveBound()`.
  `ObjectiveValue()` is read only on OPTIMAL/FEASIBLE; UNKNOWN/INFEASIBLE → fall back to
  brute force if ≤ 18 free, else HTTP 503 with a structured message. Hints: previous
  stage's solution as warm start; never `fix_variables_to_their_hinted_value`.
- **R2 (D1 term 8, amended 02:15)** Sequential assumption-fixing in ascending-id order
  (architecture agent's verified driver): after stages 1–7 are pinned and `sum(x) == v4`
  is added explicitly, walk ids ascending; skip if already in the incumbent; else
  `add_assumption(x_i)`, solve; feasible → fix in and take the new incumbent; INFEASIBLE →
  fix out; UNKNOWN → return the incumbent as FEASIBLE. Bit-weight objectives are rejected:
  coefficients in 1e14–1e18 hit MODEL_INVALID (frontend session measured) and 2^59
  exceeds that.
- **R3 (model)** Balances are linear expressions; days-below-zero and buffer flag via
  `only_enforce_if(~lit)`; worst shortfall and exposure via epigraph IntVars with domains
  derived from the data. Only `x` is read back; all terms recomputed by `simulate()` and
  asserted equal to the stage optimum. For that assertion to be sound, stage expressions
  carry the constant contributions: cardinality = `len(forced) + Σx`; pain = `Σ_forced
  pain + Σ pain·x`; hysteresis = `K + Σ_{i∉prev} x_i + Σ_{i∈prev∩free} (1−x_i)` with
  `K = |{f ∈ forced : f ∉ prev}| + |prev − ids(forced ∪ free)|`. One-per-txn:
  `add(Σ x_group ≤ 1)` per `target_txn_id` among free candidates. `num_workers=1`,
  `random_seed=0` set explicitly. No `add_max_equality`.
- **R4 (validation, adopted from the superseded parallel spec)** At most one chosen
  candidate per `target_txn_id` (model constraint; brute force filters); `freed_cents ≤
  |target amount|` → 422; `target_txn_id` must exist → 422; `effective_date` within the
  horizon → 422; `id` matches `^[A-Za-z0-9_.:-]{1,64}$`; all cents in ±10^11; ≤ 2000
  scheduled rows. Cross-field checks live on the *later* field via `field_validator` so
  422s carry a field path. Dates stay `str` (regex + `date.fromisoformat`).
- **R5 (ordering, shared with the oracle)** `plan` sorted by (date, id) using code-point
  string order; `per_item` computed and emitted in plan order; `changes_here` sorted;
  `excluded_locked_in` sorted; `worst_date` and the tightest day are the first day of their
  extremum; `external_cash_needed.by_date` and the tier-3 verdict use the FIRST day below
  zero (`Trace.first_below_zero_date`), not the deepest. The oracle already implements D1
  (commits 8dca802, 0c6e0c5); this session does not edit it — three residual changes
  (format import extension, `<` instead of `localeCompare`, `per_item` from plan order)
  were requested from the frontend session.
- **R6 (harness)** One Node invocation per test session over a JSON array of requests;
  `--no-warnings --experimental-strip-types`; `dump.ts` pops `previous_plan` before
  calling `solve(req, previous_plan)`.
- **R7 (tests)** Perf tests carry `@pytest.mark.perf`; the gate is `-m "not perf"`.
  AC10's `types.ts` ↔ pydantic check whitelists the D5 additions until the frontend
  session adds them. `EngineUnavailable` → 503, never 500.
- **R8 (deps)** `httpx2` (not `httpx`) is required by starlette 1.6 `TestClient`; add to
  `backend/requirements.txt`; wheel staged in `wheels/`.
- **R9 (run command)** `uvicorn --app-dir backend app.main:app`; `backend/pytest.ini`
  sets `pythonpath = .`; imports are `from app...`; no `backend/__init__.py`.
- **R10 (wording)** Zero changes at tier 3 must state the gap, not "clears" — including the
  certificate sentence. When `minimal_proven` is False, no string may claim fewest/smallest,
  "no combination closes the gap", or "best partial plan".

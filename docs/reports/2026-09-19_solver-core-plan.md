# Plan — solver core + `/api/solve` (rev 2, after critique)

Run spec: `docs/specs/2026-09-19_solver-core.md` (D1–D11, R1–R10, AC1–AC15 binding; D7,
D5, D6, R2, R3, R5 amended Sat 02:15). Branch `main`. Written Sat ~02:20. Rev 1 was
critiqued (12 findings) and is superseded by this file; the oracle changed under it.

**Oracle = `frontend/src/solver/mockSolver.ts` at `0c6e0c5` (432 lines).** It already
implements D1, the sorted-id tiebreak, one-per-txn in the search, marginal irredundancy,
first-breach `by_date`, forced dedupe, zero-change wording, and emits the D5 fields.
This session does not edit it. The three residual changes requested from the frontend
session (format import `.ts` extension; `<` instead of `localeCompare`; `perItem` built
from `planOrder`) **landed in `21c6ecf`**, verified there under Node. Step 6.3's patched-copy
fallback stays in the plan only as insurance and should be a no-op. Expected plans at HEAD:
clears (20000, 2500) → `c_dd_chipotle, c_gym, c_card_min` tier 1; tight (18000, 10000) →
same three ids, tier 2; gap (6000, 2500) → 9 ids, tier 3.

Environment (verified): Python 3.14.7; ortools 9.15.6755; fastapi 0.141.1; starlette
1.6.0; pydantic 2.13.5; pytest 9.1.1; Node v22.17.1; wheels staged: `httpx2-2.13.0`,
`httpcore2-2.13.0`, `certifi-2026.7.22`. `tsc -p frontend/tsconfig.app.json --noEmit`
passes at HEAD.

**Honest estimate: ~5.5–6 h of agent time** (rev 1 said 3–3.5; the critique re-summed
it). Milestones: `/api/solve` on brute force with the 3 fixtures ≈ +75 min; oracle parity
≈ +2 h; CP-SAT ≈ +3.5 h; full suite + docs ≈ +5.5 h. Commit at each milestone.

---

## Step 0 — Deps and scaffolding (10 min)

0.1 `.venv/bin/pip install --no-index --find-links wheels httpx2` →
    verify `.venv/bin/python -c "from fastapi.testclient import TestClient; print('ok')"`.
0.2 Append `httpx2==2.13.0` to `backend/requirements.txt`.
0.3 `backend/pytest.ini`: `[pytest]` / `testpaths = tests` / `pythonpath = .` /
    `markers = perf: timing tests, reported not gating`.
0.4 Empty `__init__.py` in `backend/app/`, `backend/app/solver/`, `backend/tests/`,
    `backend/tests/fixtures/`. No `backend/__init__.py`.
0.5 `.venv/bin/pytest backend/ -q` → exit 5 (no tests), no import errors.

## Step 1 — `backend/app/schemas.py` (25 min)

`model_config = ConfigDict(extra="forbid", strict=True)` on every model. Constants:
`MAX_T=366`, `MAX_N=60`, `MAX_SCHED=2000`, `MAX_FREE=18`, `CENTS_ABS=10**11`,
`ID_RE=r"^[A-Za-z0-9_.:-]{1,64}$"`. Dates are `str` validated by `iso()` = regex
`\d{4}-\d{2}-\d{2}` fullmatch + `date.fromisoformat`.

Request models: `ScheduledTxn`, `Candidate`, `Locks` (`in_: list[str] = Field(alias="in")`;
no `populate_by_name`), `SolveRequest` (+ `previous_plan: list[str] = []`).
Response models mirror `types.ts` 44–99: `PlanItem` (+ `strictly_needed: bool`, line 52),
`CertificateItem` (+ `marginal_cents`, `marginal_days`, lines 60–61), `Certificate`
(+ `minimal_proven`), `Shortfall`, `ExternalCash`, `BalanceRow`, `Meta`
(`solver: Literal["cp-sat","brute-force"]`, `status: Literal["OPTIMAL","FEASIBLE"]`,
`excluded_locked_in: list[str]`), `SolveResponse`.

Cross-field validators on the LATER field (`field_validator` + `info.data`) so 422 `loc`
carries the field: `Candidate.recharge_date` (defer ⇔ present; `> effective_date`);
`SolveRequest.horizon_end` (`≥ as_of`, span ≤ MAX_T); `SolveRequest.scheduled` (unique
ids); `SolveRequest.candidates` (unique ids; `target_txn_id ∈ scheduled`; `freed_cents ≤
|target.amount_cents|`; `effective_date ∈ [as_of, horizon_end]`); `SolveRequest.locks`
(⊆ candidate ids; `in ∩ out = ∅`). Field bounds per spec R4.

## Step 2 — `dates.py`, `simulate.py`, `eligibility.py`, `objective.py` (30 min)

2.1 `dates.py`: `parse`, `day_range` (inclusive, `timedelta`), `days_between`,
    `short_date` ("Sep 24"), `money` (sign, `f"{dollars:,}"`, 2-digit cents) — must equal
    `frontend/src/lib/format.ts` 5–17. No `datetime` in `solver/` (grep-asserted test).
2.2 `simulate.py`: `Trace(balances, days_below_zero, worst_shortfall, worst_shortfall_date,
    first_below_zero_date, below_buffer_exposure, min_balance, buffer)` — port of oracle
    55–103 exactly (delta map summed before the walk; strict `>` for worst; first day
    below zero recorded once).
2.3 `eligibility.py` — port of oracle 190–205, 385–388: actionable = lead-time ok ∧ not
    locked-out; pinned = actionable ∩ locks.in sorted by id; forced = pinned deduped by
    `target_txn_id` (first wins); free = actionable − locked-in − txns held by forced;
    `excluded_locked_in` = sorted(locks.in − forced ids); `considered = len(actionable)`.
2.4 `objective.py`: `score_tuple(trace, chosen, prev)` = `(dbz, worst, 0 if min ≥ buffer
    else 1, len, exposure, Σpain, |ids Δ prev|, tuple(sorted ids))` — oracle 121–146.
    `load_bearing(item) = marginal_cents > 0 or marginal_days > 0`.

## Step 3 — `engine_brute.py` (15 min)

`EngineUnavailable`; `solve_brute(req, days, forced, free, prev)`: refuse `len(free) >
MAX_FREE`; masks `0..2^n`; skip subsets with a duplicate `target_txn_id` (oracle 216);
strict `<` on `score_tuple`; return `(sorted ids, "OPTIMAL", True, stage_values[:7])`.

## Step 4 — `tiers.py`, `certificate.py`, `wording.py`, `assemble.py`, `solve.py` (45 min)

4.1 `tiers.py`: tier per oracle 229–232; `external_cash` = `{amount: worst_shortfall,
    by_date: first_below_zero_date}` iff tier 3 (oracle 409–417).
4.2 `certificate.py`: iterate `plan_order` (sorted (date, id)); per item simulate
    `best − {i}` → `worst_shortfall_cents`, `worst_date`, `marginal_cents = t.worst −
    best.worst`, `marginal_days = t.dbz − best.dbz` (oracle 240–251); `irredundant =
    bool(per_item) and all(load_bearing)` (empty plan → False, oracle 253); `worst_item` =
    first strict max of `marginal_cents` (254–257), `None` for an empty plan.
4.3 `wording.py`: port sentence branches 259–284, reasons 298–309, verdict/qualifier
    330–365 including the n=0 branches at tiers 2 and 3, with two deliberate departures
    from the oracle (Codex findings 3, 4): (i) empty plan at tier 3 → certificate sentence
    "Nothing here can be changed in time; the gap stands at $X on <date>." never "already
    clears" (R10); (ii) when `minimal_proven` is False, verdicts drop "fewest"/"smallest",
    and the tier-3 branches "No combination … closes the gap" / "This is the best partial
    plan" become "These changes narrow the gap to $X; the search did not finish proving
    that is the best available." `BANNED = ("infeasib", "guarantee")`. Parity prose
    checks skip exactly these two departures.
4.4 `assemble.py`: plan rows (+ `strictly_needed`), balances rows (`changes_here` sorted,
    oracle 368–381), shortfall, meta (`solver`, `status`, `wall_ms`,
    `candidates_considered`, `excluded_locked_in`).
4.5 `solve.py`: `Settings(total_budget_s=6.0, min_stage_s=0.25, force_engine=None)`;
    eligibility → engine (`try: import engine_cpsat` → else brute; CP-SAT
    `EngineUnavailable` → brute if `len(free) ≤ MAX_FREE` else re-raise) → simulate best →
    if all stages proven: `assert score_tuple(...)[:7] == stage_values` (sound because
    Step 7 puts the constants into the stage expressions) → certificate → tier → wording →
    assemble.

## Step 5 — `main.py` + fixtures (30 min) → `/api/solve` demo-able on brute force

5.1 `create_app(dist_dir: Path | None) -> FastAPI`; `app = create_app(Path(__file__).
    resolve().parents[2] / "frontend" / "dist")`. CORS for `http://localhost:5173`.
    `GET /health`; `POST /api/solve` (`response_model=SolveResponse`);
    `exception_handler(EngineUnavailable)` → 503 `{"detail": ...}`; static mount LAST and
    only if `dist_dir` exists.
5.2 `backend/tests/fixtures/scenarios.py`: `SCHEDULED` (15 rows, scenarios.ts 13–27),
    `CANDIDATES` (11 rows, 31–41), `request(opening, buffer=2500, **overrides)`;
    `SCENARIOS = {"clears": (20000, 2500), "tight": (18000, 10000), "gap": (6000, 2500)}`
    (scenarios.ts 78–82). Expected plans: 3 / 3 / 9 changes (oracle at HEAD).
5.3 `backend/tests/fixtures/planted.py` — minimum set now, rest in Step 9: `tier3_cancel_all`,
    `all_locked_out_gap`, `same_txn_two_candidates`, `two_forced_same_txn`, `cushion_only_item`,
    `payday_eve`, `dst_span`, `defer_past_horizon`, `two_equal_dips`, `hysteresis_tie`,
    `greedy_fails`. Each planted instance is ≤ 6 candidates and ≤ 12 days so its expected
    plan is HAND-DERIVED in a comment (day-by-day balances written out), not computed by
    the engine under test; every planted instance also goes through the Node oracle in
    Step 6.5 as a second independent check (Codex 10).
5.4 Smoke: `.venv/bin/uvicorn --app-dir backend app.main:app --port 8000`; `curl /health`;
    POST `clears` → 200, tier 1, 3 changes. **Commit:** `feat(solver): brute-force engine
    and /api/solve`. Message the frontend session: `/health` is up.

## Step 6 — Oracle harness + parity (40 min)

6.1 `backend/tests/oracle/dump.ts`: read a JSON array of requests on stdin; for each,
    `const { previous_plan = [], ...req } = r; solve(req, previous_plan)`; print JSON array.
    Import `'../../../frontend/src/solver/mockSolver.ts'`.
6.2 `backend/tests/oracle/__init__.py` empty; `backend/tests/conftest.py`: `oracle_run(reqs)`
    via `subprocess.run(["node","--no-warnings","--experimental-strip-types", DUMP], input=
    json.dumps(reqs), capture_output=True, text=True, check=True, timeout=120, cwd=DUMP.parent)`;
    `pytest.skip` if no `node`. Session-scoped: one invocation for all parity requests.
6.3 If `mockSolver.ts:10` still lacks the `.ts` extension when the harness first runs,
    `conftest` writes a patched copy to `tmp_path_factory` (only the import line changed)
    and runs that; `test_oracle_identity.py` asserts the repo file equals the copy modulo
    that line, marked `xfail(strict=False)` until the frontend commit lands.
6.4 Generator (`backend/tests/gen.py`, `random.Random(20260919)`): n_free 4–14, T 7–45,
    canonical ASCII ids matching `ID_RE`, defers with `recharge > effective` (some past
    horizon), lead times 0–5, `effective_date` inside the horizon, duplicates of
    `target_txn_id` ALLOWED (so one-per-txn is exercised against the oracle), `locks.in`
    and `locks.out` drawn as mutually disjoint subsets OF the candidate ids (unknown lock
    ids are reserved for validation tests), `previous_plan` with one unknown id,
    `freed ≤ |amount|`.
6.5 `test_parity.py` (b): 3 fixtures + 50 random vs oracle on `tier`, `plan[*].candidate_id`,
    `plan[*].strictly_needed`, `certificate.irredundant`, `per_item` (all five fields),
    `shortfall`, `external_cash_needed`, `balances`, `meta.excluded_locked_in`,
    `meta.candidates_considered`; prose by containment, branch-specific (Codex 7): empty
    plan → sentence equality on the oracle's branch except the tier-3 departure in 4.3;
    tier 3 irredundant → contains `money(worst_item.marginal_cents)`; tier 3 not
    irredundant → contains "does not clear"; tier ≤ 2 irredundant → contains
    `short_date(worst_date)` and `money(worst_shortfall_cents)`; tier ≤ 2 with a
    load-bearing worst item → contains its label; cushion-only → equality on the fixed
    sentence; all tier-3 verdicts contain `short_date(first_below_zero_date)`.
6.6 `test_invariants.py` (AC14 a–g) over fixtures + planted + the 50 random responses.
    **Commit:** `test(solver): oracle parity and invariants`.

## Step 7 — `engine_cpsat.py` (45 min)

Per the architecture agent's verified driver, amended by R1–R3 and the critique:
- `base_t` = opening + scheduled prefix + forced deltas; `delta_i(t)` per D10; `B_t`
  linear expressions; `Bmin_t` for domains.
- `x_i = new_bool_var` for free candidates; one-per-txn: `add(sum(group) <= 1)` per
  `target_txn_id` with ≥ 2 free candidates.
- Terms (7): `w_t` via `add(B_t >= 0).only_enforce_if(~w_t)`; `worst = new_int_var(0,
  max(0, -min(Bmin)))`, `add(worst >= -B_t)`; `f` via `add(B_t >= buffer).only_enforce_if(~f)`;
  cardinality `len(forced) + sum(x)`; exposure `e_t = new_int_var(0, max(0, buffer −
  Bmin_t))`, `add(e_t >= buffer − B_t)`, `sum(e)`; pain `Σ_forced + Σ pain·x`; hysteresis
  `K + Σ_{i∉prev} x_i + Σ_{i∈prev∩free}(1 − x_i)` with `K = |{f∈forced: f∉prev}| +
  |prev − ids(forced∪free)|`.
- Solver: `num_workers=1`, `random_seed=0`. Budget (Codex 5): one monotonic
  `deadline = perf_counter() + total_budget_s` shared by ALL solves including stage 8;
  before each solve `alloc = min(remaining, max(min_stage_s, remaining / solves_left))`;
  if `remaining <= 0` before a stage → return the incumbent as FEASIBLE (stages 1–7) or
  stop fixing and return the incumbent (stage 8); `solves_left` for stage 8 = number of
  ids not yet fixed.
- Loop over 7 terms: `minimize(expr)`; solve; status ∉ {OPTIMAL, FEASIBLE} → raise
  `EngineUnavailable`; `v = solver.value(expr)`; `add(expr <= v)`; record `(v, proven)`;
  `clear_hints`; `add_hint(x_i, value)` for all i.
- After stage 4 pinning also `add(sum(x) == v4 − len(forced))` explicitly (needed when
  stage 4 was only FEASIBLE).
- Stage 8: `clear_objective`; incumbent from the last solution; for ids ascending: if
  slots full → `add(x==0)`; if in incumbent → `add(x==1)`; else `add_assumption(x)`,
  solve, `clear_assumptions`; feasible → `add(x==1)`, new incumbent; INFEASIBLE →
  `add(x==0)`; UNKNOWN → return incumbent as FEASIBLE.
- Return `(sorted ids, "OPTIMAL" if all proven else "FEASIBLE", all_proven, stage_values)`.

## Step 8 — Tests: CP-SAT parity, optimality, FEASIBLE path (45 min)

`test_parity.py` (a) 100 random instances CP-SAT ≡ brute (n_free ≤ 12, T ≤ 30) on all
fields of 6.5; (c) fallback ≡ CP-SAT on fixtures via `Settings(force_engine="brute-force")`
and via the loader seam `solve.load_cpsat()` monkeypatched to raise `ImportError` (Codex
9: `sys.modules` tricks are order-dependent), plus one subprocess test that sets
`sys.modules['ortools']=None` before any import; (d) 19 free without ortools →
`EngineUnavailable` through the same seam; (e) AC15 via a `monkeypatch` that wraps the
REAL `CpSolver.solve` and rewrites an OPTIMAL return to FEASIBLE so a solution exists for
`value()` (Codex 8); (e2) stage-8 UNKNOWN via a wrapper returning UNKNOWN on the first
assumption solve → incumbent preserved, `FEASIBLE`, response valid;
(f) 40 all-tied candidates → stage 8 yields the lexicographically smallest id set, equal
to brute force at n=18.
`test_objective.py`: `greedy_fails`; buffer-flag inversion; pain; hysteresis with and
without `previous_plan`; determinism ×10 byte-identical minus `wall_ms`; empty
candidates; `same_txn_two_candidates`; `two_forced_same_txn` (second listed in
`excluded_locked_in`); per-level counterfactuals k=2..7 from `planted.py` (cuttable).
**Commit:** `feat(solver): CP-SAT lexicographic engine`.

## Step 9 — Remaining test files (60 min)

`test_validation.py` (A), `test_dates.py` (B: 1-day, Sep 29→Oct 2, Feb 27→Mar 2 2027,
Oct 25→Nov 8 2026), `test_simulate.py` (C), `test_eligibility.py` (D; `c_gym` lead 3
is the boundary), `test_tiers.py` (G), `test_certificate.py` (H, marginal semantics
hand-checked on `cushion_only_item` and `gap`), `test_stability.py` (I; ±$40 sweep on
`clears`, flip rate printed, ≤ 0.15), `test_response.py` (J; `types.ts` field-set diff
against the pydantic models — all fields now present on both sides), `test_api.py` (K;
`TestClient(create_app(tmp_dist))` and `create_app(None)`; `loc[1:]` on every 422; OPTIONS
preflight), `test_wording.py` (AC13 over every string of every response), `test_perf.py`
(`@pytest.mark.perf`, median of 5).

## Step 10 — Docs, full run, commit (20 min)

10.1 Run spec Results: counts, timings, flip rate, deviations (R1 supersedes D3's 2 s).
10.2 Doc-sync grep over `docs/` and `README.md` for `DigitalOcean|2 s per stage|
     httpx\b|DP fallback|bit-weight|backend.app.main|against zero`; fix hits.
10.3 `.venv/bin/pytest backend/ -q -m "not perf"` green; `-m perf` reported; `cd frontend
     && npm run build` still clean (no frontend edits expected).
10.4 **Commit:** `test(solver): full suite; docs(solver): results`. Never push.

---

## Verification (AC → test file)

AC1 validation/api · AC2 dates · AC3 simulate · AC4 eligibility · AC5 objective · AC6
parity · AC7 tiers · AC8 certificate · AC9 stability · AC10 response · AC11 api · AC12
perf · AC13 wording · AC14 invariants · AC15 parity(e).

## Risks and mitigations

- Oracle import without `.ts` → landed in `21c6ecf`; Step 6.3 fallback is insurance only.
- `localeCompare` and `worstItem` order → both fixed in `21c6ecf`; generator still uses
  ASCII ids matching `ID_RE`.
- Stage assertion unsound → constants moved into stage expressions (Step 7).
- `solver.value()` garbage after a failed solve → status checked at one chokepoint
  before any read.
- Two forced on one txn → dedupe in eligibility (Step 2.3), never INFEASIBLE.
- FEASIBLE path untestable by time limit → monkeypatch (Step 8e).
- Timing flakiness → `perf` mark, not gating.
- Schedule → milestone commits at Steps 5, 6, 8, 10.

## Cut order if red at the 04:00 check

Cuttable, in order: per-level counterfactuals k=2..7; CP-SAT≡brute 100 → 30; perf tests;
±$40 sweep; `types.ts` diff; static-mount test; feature-doc polish; 19-free error test.
**Not cuttable:** brute engine, `/api/solve` 200 on the 3 fixtures, oracle parity on the
3 fixtures + 50 random, invariants, basic 422s, AC13 grep, the Step 5 and 6 commits. If
CP-SAT parity is still red at the end: ship brute force as the selected engine for
`free ≤ 18` with CP-SAT behind `Settings.force_engine`; D3's "never a heuristic" holds.

---

## Codex plan review (rev 2) — resolutions

Review file: `docs/reports/2026-09-19_solver-core-plan-review.md`.

| # | Finding | Resolution |
|---|---|---|
| 1 | Oracle import "one directory short" | **Rejected.** From `backend/tests/oracle/dump.ts`: `..`=`backend/tests`, `../..`=`backend`, `../../..`=repo root, so `../../../frontend/...` is correct. Verified at that exact depth by the file-impact agent and by the frontend session under Node (`21c6ecf`). |
| 2 | `irredundant` true on empty plan | Fixed, Step 4.2. |
| 3 | Empty-plan sentence "already clears" at tier 3 | Fixed, Step 4.3 (i); parity skips the departure. |
| 4 | FEASIBLE tier-3 wording claims optimality | Fixed, Step 4.3 (ii). |
| 5 | 6 s budget not enforced across stage 8 | Fixed, Step 7: single deadline, all solves. |
| 6 | Generator locks "disjoint from candidate ids" | Fixed, Step 6.4 (wording error; in/out disjoint, drawn from candidates). |
| 7 | Unconditional prose checks | Fixed, Step 6.5: branch-specific. |
| 8 | FEASIBLE monkeypatch must run the real solve | Fixed, Step 8 (e), (e2). |
| 9 | `sys.modules["ortools"]=None` order-dependent | Fixed, Step 8 (c)/(d): loader seam + subprocess. |
| 10 | Planted expectations derived from the engine under test | Fixed, Step 5.3: hand-derived + oracle cross-check. |

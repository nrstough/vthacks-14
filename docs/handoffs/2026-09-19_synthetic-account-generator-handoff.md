# Handoff — synthetic account generator (2026-09-19, Sat 05:15)

**Purpose of this chat:** Build the synthetic account generator — the primary demo data
source. Everything it feeds is already built, merged and green; what is missing is
realistic data to run it on. This is the first of three remaining backend items
(generator → deploy artifacts → Nessie) and the only one of the three that is blocked on
nobody.

## Context

VTHacks 14, solo. Given a transaction history, return the fewest dated spending changes
that keep the balance above zero until payday, and prove it.

**All four lanes are merged and `main` is fully pushed.** `main`, `backend` and
`origin/main` are all `2f59a94`.

- `backend/app/solver/` — the exact solver. CP-SAT primary, exhaustive fallback,
  eight-term lexicographic objective, marginal certificate, tiers, wording. `POST /api/solve`.
- `backend/app/candidates/` — `lexicon.py` (merchant string → category), `policy.py`
  (category → up to two alternatives), `generator.py`. `POST /api/candidates`.
- `backend/app/chat/` — the Gemini explainer. `POST /api/chat`.
- `frontend/` — the UI, 87 of its own tests.

Still outstanding after this: **deploy artifacts** (nothing exists — no `Caddyfile`, no
`deploy.sh`, no CSP anywhere; blocked on Nathan creating the Vultr account) and **Nessie**
(90-min timebox, droppable, blocked on an API key). The Solana Devnet workstream is
**open, not closed** — Nathan said so explicitly at 05:15 Sat, overriding a
recommendation to close it. It is not this lane's work and this lane must not touch it.

## Working branch / worktree

`backend` in `/Users/nathanstough/Desktop/VT Hacks`, **clean**. `CLAUDE.md` is binding —
branch off `main`, in this directory, before writing code:

```bash
git switch -c synthetic main     # git switch, never checkout
```

Four worktrees exist:

```
/Users/nathanstough/Desktop/VT Hacks             [backend]      ← you, == main
/Users/nathanstough/Desktop/vthacks-frontend     [frontend]     16 behind main, 0 ahead
/Users/nathanstough/Desktop/vthacks-gemini       [gemini-chat]  merged
/Users/nathanstough/Documents/Codex/worktrees/…  [codex/spending-forecast]  Nathan's own
```

**The frontend lane has nothing unmerged** — 0 commits ahead of `main`. Older handoffs
describe it as contended; it is not any more. Fast-forward it freely if you need it.

**`git add` names explicit files. Never a directory, never `-A`.** Three sweeps have
already swept another lane's in-flight work into unrelated commits.

## Environment / setup

```bash
cd "/Users/nathanstough/Desktop/VT Hacks"
.venv/bin/pytest backend/ -q -m "not perf"
```

```bash
.venv/bin/uvicorn --app-dir backend app.main:app --reload --port 8000
```

```bash
cd "/Users/nathanstough/Desktop/VT Hacks/frontend"
export npm_config_cache="/Users/nathanstough/Desktop/VT Hacks/.npm-cache"
npm run lint && npm run build && npm test
```

Python 3.14.7; ortools 9.15.6755, fastapi 0.141.1, pydantic 2.13.5, pytest 9.1.1, and
**httpx2**, not httpx — starlette's TestClient needs it. Node 22.17.1 at
`/usr/local/bin/node`. **`rapidfuzz` is importable in the venv but is NOT in
`backend/requirements.txt` or `wheels/`** — using it breaks the offline install, which is
why the lexicon uses stdlib keyword matching. Do not reach for it here either.

Wifi is fine; the older "never install from the hotel" rule is relaxed.

## What to do next

### 1. Decide where the generator lives — do this first, it shapes everything

`backend/tests/fixtures/accounts.py` (161 lines) already does most of this job: a
36-merchant descriptor table built to exercise the lexicon, a business-day payroll
cadence at 7 or 14 days, a clawback dated after a charge, rows just outside the window,
and twin charges identical but for their id. `windows(n, seed)` returns seeded accounts;
`opening_for_mixed_tiers()` picks a balance near the do-nothing trough.

It is a **test fixture**, imported by the parity and perf suites. The choice is:

- **(a)** Product generator in `backend/app/` (e.g. `backend/app/accounts/`), and
  `tests/fixtures/accounts.py` becomes a thin wrapper over it. One source of truth,
  but every existing test that imports the fixture now depends on product code, and the
  perf suite pins 300 generated accounts across both engines — if generation changes,
  those numbers move.
- **(b)** They stay separate. No risk to the gate, at the cost of two tables that drift.

Pick deliberately and write the reason into the run spec. **(a) is the better answer if
and only if you can keep `windows()` byte-identical for the existing seeds** — check that
before committing to it, because the canaries below depend on it.

### 2. Build the generator

Required behaviour, from the product plan:

- Business-day-adjusted weekly/biweekly pay with jitter.
- Heavy-tailed amounts.
- Messy merchant strings that **exercise the lexicon rather than dodge it**.
- A planted dip before the first payday — the demo's whole point.
- **Labelled as modelled on screen.** It must never read as real bank data.

Schema bounds it must respect (`backend/app/schemas.py:18-40`): `CENTS_ABS = 10**11`,
`MAX_SCHED = 2000`, `MAX_T = 366`, `MAX_N = 60`, `MAX_FREE = 18`,
`ID_RE = ^[A-Za-z0-9_.:-]{1,64}$`. Money is integer cents; no float touches it.

### 3. Wire it to the demo

Decide whether it is an endpoint or a script that emits JSON into
`frontend/src/fixtures/`. The frontend already has `scenarios.ts` in that shape.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

**All four numbers below were re-run and verified at Sat 05:12, not copied forward.**

- **Test:** `.venv/bin/pytest backend/ -q -m "not perf"` → **1262 passed**, 8 deselected,
  **20.6 s**. This is the gate.
- **Test:** `.venv/bin/pytest backend/ -m perf -q -s` → **8 passed**, ~137 s. Includes
  **300 generated accounts compared across both engines** — this is the suite that
  option (a) above puts at risk.
- **Test:** `cd frontend && npm run lint && npm run build && npm test` → lint clean,
  build **143 ms**, **87 tests**, main chunk **`dist/assets/index-*.js` = 625,369 bytes**.
  The >500 kB warning is expected and pre-existing.
- **Canaries** (asserted in `test_parity.py` and `test_candidates_policy.py` — if the
  generator moves, these are what tells you): `clears` → tier 1, 3 changes; `gap` →
  tier 3, 9 changes, `"$27.62 more by Sep 24"`. The demo account generates exactly
  **14 candidates**, `rows_considered` 13, `protected` `[t_card, t_verizon]`,
  `not_actionable` `[t_spotify]`. That table in `docs/features/candidates.md` was worked
  by hand and the test pins it.

- **At-risk: `wheels/`** — 65 MB, gitignored, **NOT archived**. Offline install fallback.
- **At-risk: `frontend/dist/`** — 648 KB, gitignored, **NOT archived**, rebuilt Sat 05:12.
  The deploy needs it rsynced; nothing on the box builds it.
- **At-risk: `~/Downloads/Checking.csv`** — Nathan's real bank export, 32,897 bytes.
  **NOT archived, and must never be committed.** `.gitignore` covers it. Anonymise before
  any demo use; the lexicon has never been run against it.
- **At-risk: `experiments/residual_forecast/*.npz`** — 13 MB, gitignored, **NOT
  archived**. Not this lane's. Ask before touching.
- **In flight: nothing.** No background jobs, no cloud runs, no open PRs.
- **Everything is pushed.** `origin/main == main == 2f59a94`, fetched 05:11. Older
  handoffs claiming "11 commits unpushed" and "26 commits unpushed" are **both stale**.
  The repo is still **private** — flip it before submission with
  `gh repo edit nrstough/vthacks-14 --visibility public --accept-visibility-change-consequences`.

## Analytical notes

- **`GUARANTEED AUTO PROTECTION` is a landmine.** It is row 59 of the `MERCHANTS` table
  in `backend/tests/fixtures/accounts.py` — a deliberate lexicon trap, and the obvious
  table to reuse. But `frontend/tests/bundle.test.ts` asserts `doesNotMatch(/guarantee/i)`
  against **every** `.js` in `dist/assets/`. The moment a generated account carrying that
  descriptor is baked into a frontend fixture, the frontend suite fails — and the failure
  will look like a wording regression, not a data one. Either exclude that descriptor from
  anything that ships to the client, or scope the bundle test to the main chunk.
  **Never weaken the pattern** — it enforces a CLAUDE.md product commitment.
- **Candidate ids are a pure function of `(transaction id, action)`** and the client
  round-trips `locks` and `previous_plan` by id. A lock naming an id the generator no
  longer returns is a **422 on the whole solve**; a cached candidate whose `effective_date`
  slipped before a moved `as_of` is a 422 too. Anything that regenerates accounts has to
  respect the three client rules in the contract.
- **`limit` defaults to 18 for a reason with two numbers behind it.** The server's
  exhaustive engine refuses above 18; the browser's stand-in refuses above 20. Eighteen is
  the lower, so it is the largest set every fallback still answers. Raising it silently
  breaks the offline demo, which is the entire point of the fallback.
- **Deferrals are not savings.** Money put off comes back on its recharge date. Only offer
  a deferral when a *positive* income row falls strictly after the charge and inside the
  horizon — a clawback is an income row too, and a recharge past the horizon is a skip
  wearing the wrong label. Two separate bugs have already come from this.
- **Never claim more than was proven.** When a solver stage does not finish,
  `minimal_proven` is false and the optimality sentences are *replaced*, not softened. The
  words `infeasib` and `guarantee` never appear anywhere, including the 503.
- **There is no error boundary anywhere in `frontend/src`** — no `React.lazy`, no
  `Suspense`, no `componentDidCatch`, no router. `App.tsx` is 291 lines. A render throw
  white-screens the submission in front of judges. It is not this lane's work and nobody
  owns it now that the frontend lane is idle, but it is on the demo's critical path and
  costs maybe 40 lines. Worth raising with Nathan.
- **The schedule is Nathan's and the memo's gate was rejected.** The "Sat 18:30 deployed
  demo or freeze" figure came from the VeriLM memo; he disagrees and says freeze can be
  04:00–06:00 Sunday because submission is due **08:00 ET Sunday**. Venue close (23:00) and
  that 08:00 are the externally-imposed deadlines. Do not cite 18:30 or "code freeze 01:30".
- **The review pipeline earned its cost and the useful part was re-checking finished
  work.** Six rounds, every one found something real: a critique caught an edit reported as
  applied that had not been; the Codex audit caught an acceptance criterion reported as met
  that was not; a re-audit caught the same test being vacuous for the third time. Mutation
  testing exposed all of it. Budget for it.
- **A learned pain model is the honest V2, not a V1.** The residual-spending pilot scored
  $103.26 against $103.16 for a weekday-average baseline — ten cents worse, on 2,700
  synthetic accounts and zero real ones. Its own verdict: "do not promote as the default".

## Pointers

- `CLAUDE.md` — working agreement. Binding on every session. Read it first.
- `backend/tests/fixtures/accounts.py` — the 36-merchant table and `windows()`. **The
  starting point**, and the decision in step 1.
- `backend/tests/gen.py` — schema-valid noise for differential testing. A different job;
  don't conflate them.
- `backend/app/schemas.py:18-40` — the bounds the generator must respect.
- `docs/features/candidates.md` — lexicon rules, policy table, wording, the hand-worked
  golden set. Living truth.
- `docs/features/solver.md`, `docs/features/chat.md`, `docs/features/frontend.md`.
- `docs/specs/2026-09-19_candidate-generation.md` — last run spec, six review rounds
  recorded. Frozen; append to Results only.
- `docs/api-contract.md` — all three endpoints. The backend owns it;
  `frontend/src/types.ts` mirrors it.
- `docs/handoffs/2026-09-19_backend-data-and-deploy-handoff.md` — the parent handoff
  covering all three remaining items. Its test counts are stale; the ones above are fresh.
- `docs/handoffs/2026-09-19_solana-devnet-handoff.md` — **open, not closed.** Not this lane.
- Memory: `vthacks-14-event-constraints`, `vthacks-project-plan`, `user-nathan-profile`.

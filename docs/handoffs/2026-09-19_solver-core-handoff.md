# Handoff — solver-core complete (2026-09-19, Sat ~03:10)

**Purpose of this chat:** The exact solver and `POST /api/solve` are finished, audited and
committed. Build what feeds them — candidate generation and a synthetic account generator —
then Nessie and the Vultr deploy. Read the two open questions at the bottom before planning
anything: the Saturday 18:30 gate is currently disputed, and Nathan is working in this same
tree from a Codex session, so this is not a repo you have to yourself.

## Context

VTHacks 14, solo. The product: given a transaction history, return the fewest dated
spending changes that keep the balance above zero until payday, and prove it.

**Done and committed (12 commits, `e83ca59`..`116f6f8`):**

- `backend/app/solver/` — strict schemas, ledger walk, eligibility, the eight-term
  lexicographic objective, CP-SAT engine, exhaustive fallback, marginal certificate, tiers,
  wording, response assembly.
- `backend/app/main.py` — `GET /health`, `POST /api/solve`, serving `frontend/dist` when it
  exists. Stateless: no database, no accounts, the previous plan arrives with the request.
- `backend/tests/` — **977 gate tests + 6 perf.**
- Docs: run spec, plan, Codex review and audit artifacts, feature doc, contract updates.

**The frontend is done and wired to the service**, on its own branch (see below). It calls
`/api/solve` with a 150 ms debounce and a stale-response guard, and falls back to its local
solver with a visible chip if the API is unreachable — deliberate, so a wifi failure during
judging does not kill the demo.

**Verified:** identical to the frontend's TypeScript reference solver on 53 random instances,
all 17 planted cases and the 3 demo accounts; CP-SAT identical to exhaustive search on 200
more. Reviewed three times (two adversarial Claude passes, one Codex audit); 17 issues found
and fixed; final verdicts **Acceptable** from both.

## Working branch / worktree

`main` in `/Users/nathanstough/Desktop/VT Hacks`.

Uncommitted, and **not mine — leave alone unless Nathan says otherwise**: `README.md`
(a dataset-sources line) and the untracked `experiments/residual_forecast/` directory.

**A second worktree exists:** `/Users/nathanstough/Desktop/vthacks-frontend` on branch
`frontend`. Its `frontend/node_modules` is a symlink to this tree's, so an `npm install` in
either affects both. **Merge `frontend` into `main` before building for deploy** — that
branch holds the API-calling UI, and `main`'s copy is older.

**21 commits are unpushed** to `https://github.com/nrstough/vthacks-14` (private). Push when
Nathan asks; flip the repo public before Sunday's submission with
`gh repo edit nrstough/vthacks-14 --visibility public --accept-visibility-change-consequences`.

## Environment / setup

```bash
cd "/Users/nathanstough/Desktop/VT Hacks"
.venv/bin/pytest backend/ -q -m "not perf"          # the gate
.venv/bin/uvicorn --app-dir backend app.main:app --reload --port 8000
```

Python 3.14.7; ortools 9.15.6755, fastapi 0.141.1, starlette 1.6.0, pydantic 2.13.5,
pytest 9.1.1, **httpx2 2.13.0** (starlette's TestClient needs `httpx2`, not `httpx`).
Node 22.17.1 at `/usr/local/bin/node` — the parity tests run the TypeScript solver through
it and skip cleanly if it is missing.

Offline install (hotel wifi): `.venv/bin/pip install --no-index --find-links wheels -r backend/requirements.txt`.

Frontend build needs the project-local npm cache:
`cd frontend && export npm_config_cache="/Users/nathanstough/Desktop/VT Hacks/.npm-cache" && npm run build`

## What to do next

1. **Candidate generation.** This is the real gap: the eleven candidate changes in the demo
   fixtures are hand-written, so the service cannot answer for an account it has not seen.
   Turn transactions into changes — skip, defer, downgrade, cancel — each with a
   `freed_cents`, an `effective_date`, a `lead_time_days` and a `pain` score. Category
   defaults for pain; the user corrects them with the lock toggles, which already work.
   **At most one candidate per `target_txn_id`**, and `freed_cents <= |target amount|`; both
   are validated server-side and will 422 otherwise.
2. **Synthetic account generator.** Business-day-adjusted weekly/biweekly pay with jitter,
   heavy-tailed amounts, messy merchant strings, a planted dip before the first payday. This
   is the primary demo data source; label it as modelled on screen.
3. **Recurring detection**, 1-hour timebox: regex normalise, rapidfuzz WRatio >= 88, 1%
   amount banding, cadence snap to {7,14,15,30,90,365}, >= 3 occurrences, manual override.
   If it is not working at the timebox, hard-code the fixture streams and reframe as
   user-confirmed.
4. **Nessie**, 90-minute timebox, droppable. Nathan must create the key at nessieisreal.com
   first — there is no `.env` yet. Seed a customer with the synthetic account, read it back
   as the app's data source. If the unconfirmed bill field names fight you, fall back to the
   local generator: the track is lost, nothing else is.
5. **Vultr deploy.** Only hosting track at this event; $100 credit, no card, via
   `mlh.link/vultr-signup` plus a gift code from the MLH Coach. VM + Caddy for HTTPS +
   domain + a one-command `deploy.sh`. Build locally and rsync; never install from the hotel.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

- **Test:** `.venv/bin/pytest backend/ -q -m "not perf"` → **977 passed**, 6 deselected, ~5 s.
- **Test:** `.venv/bin/pytest backend/ -m perf -q -s` → **6 passed**. Numbers to reproduce:
  demo accounts 3.2–5.9 ms, 60 changes over 60 days 25–27 ms, exhaustive search at its
  18-change cap 2.6–3.0 s, 100 random accounts 2.6–3.1 ms each.
- **Test:** `cd frontend && npm run build` → clean, ~140 ms.
- **Expected solver answers** (regression canaries, all three asserted in
  `backend/tests/test_parity.py`): `clears` → tier 1, 3 changes
  (`c_dd_chipotle, c_gym, c_card_min`); `tight` ($180 / $100 cushion) → tier 2, same 3;
  `gap` → tier 3, 9 changes, "$27.62 more by Sep 24", certificate "grows by up to $80.00".
- **At-risk: `wheels/`** — 65 MB, 41 wheels, gitignored, **NOT archived**. Regenerate with
  `pip download` on venue wifi. Needed for offline installs from the hotel.
- **At-risk: `frontend/dist/`** — gitignored and **NOT archived**; rebuild before deploy.
  Note the Vultr box will need it rsynced, since nothing builds it there.
- **At-risk: `~/Downloads/Checking.csv`** — Nathan's real bank export, 210 rows. **NOT
  archived, and must never be committed.** `.gitignore` covers it. Anonymise before any
  demo use.
- **At-risk: the VeriLM memo** is now safe — archived at
  `docs/consults/2026-09-18_verilm-memo-solver-design.md` (images stripped).
- **At-risk: `experiments/residual_forecast/`** — untracked, not mine, contains model
  checkpoints and preserved data. Do not delete; ask Nathan.
- **In flight:** nothing. No background jobs, no cloud runs, no open PRs. Port 8000 is free.

## Analytical notes

- **The objective order is load-bearing and non-obvious.** Reaching the cushion is a yes/no
  term ranked *above* the number of changes, and the *size* of the cushion shortfall ranks
  below it. Rank cushion size above cardinality and the solver pads plans to fill the
  cushion, contradicting the headline claim. Across openings from $30 to $300 the two orders
  differ in 76 of 271 cases, and this one never picks more changes.
- **The certificate is marginal, not absolute.** "Does the plan minus this change go below
  zero" is vacuously true at tier 3, where the plan is already below zero. A change earns its
  place by deepening the dip *or* adding a day below zero — `c_amzn` on the `gap` account does
  the second and not the first, and judged on depth alone the whole certificate would collapse.
- **Deferrals are not savings.** Money put off comes back on its recharge date, and that has
  caused two separate bugs — one where the constraint model credited the recharge day, and
  one where a deferral with the date *omitted* (not null) passed validation and became
  permanent savings. Both are now pinned by tests.
- **Never claim more than was proven.** When a solver stage does not finish, the response
  sets `minimal_proven: false` and the sentences asserting optimality are *replaced*, not
  softened. The words `infeasib` and `guarantee` never appear anywhere, including in the 503
  body.
- **A learned pain model is the honest V2, not a V1.** There are no counterfactual labels to
  train a decision model on, and the lock toggles are the mechanism that would collect them.
  A residual-spending pilot already ran (`docs/vthacks-training-pilot.md`): 2,700 synthetic
  accounts, 0 real, and the network scored **$103.26 vs $103.16** for a weekday-average
  baseline — about ten cents worse. Its own verdict is "do not promote as the default".
- Stability: the plan changes on **8.8%** of one-dollar steps of the opening balance, against
  a 15% threshold, and less with the previous plan remembered than without.

## Two things to settle before planning

1. **The Saturday 18:30 gate is disputed.** `docs/ideas.md` now says the gate is "superseded
   by the current product-direction discussion", pointing at
   `docs/vthacks-product-and-training-plan.md` — an expanded direction (neural spending
   forecast, Gemini natural-language scenarios, automatic setup from history). **That
   document is Nathan's own**, written from his Codex session, so it records what he wants
   rather than a proposal from somewhere else. But asked directly he said **"finish the plan
   then we'll talk"**, so the gate is unresolved, not lifted, and the expansion is not yet
   scheduled. The memo's position, recorded in memory, is that the kill criteria *are* the
   plan. **Ask before treating either as settled.** Note the pilot's own numbers are evidence
   against building the product around the network this weekend — see Analytical notes.
2. **Nathan is writing to this tree from a Codex session**, in parallel with the Claude
   sessions. Confirmed, not a mystery. Practical consequences:
   - **Scope `git add` to explicit file paths, never to directories.** Two of this session's
     commits (`92d9bb9`, `116f6f8`) swept his in-flight docs in under solver commit messages.
     Nothing was lost, the attribution is wrong, and history was deliberately not rewritten.
   - **His work in this tree has no git protection.** As of this handoff that is an
     uncommitted `README.md` change and the whole untracked `experiments/residual_forecast/`
     directory, which holds model checkpoints and preserved data. Do not commit it for him
     and do not delete it; if it still looks exposed, say so and let him decide.

## Pointers

- `docs/specs/2026-09-19_solver-core.md` — the run spec: decisions, acceptance criteria, all
  three review rounds and what each found. Frozen; append to Results only.
- `docs/features/solver.md` — living truth for the solver.
- `docs/api-contract.md` — the frozen `/api/solve` shape both sides build against.
- `docs/prize-strategy.md` — tracks and the corrections (no DigitalOcean, no Backboard, no
  "Gen AI" track at this event; Vultr is the only hosting track).
- `docs/reports/2026-09-19_solver-core-plan.md` and `*-plan-review.md`, `*-audit.md`.
- Memory: `vthacks-14-event-constraints`, `vthacks-project-plan`, `user-nathan-profile`.
- `frontend/src/solver/mockSolver.ts` — the reference solver the Python is checked against.
  **Owned by the frontend session; do not edit it from `main`.**

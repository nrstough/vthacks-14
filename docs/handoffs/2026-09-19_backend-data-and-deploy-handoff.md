# Handoff — synthetic data, deploy and Nessie (2026-09-19, Sat ~05:30)

**Purpose of this chat:** Finish what feeds and ships the backend. The exact solver and
candidate generation are both done and audited; what is missing is realistic data to run
them on and a box to run them on. Three items, in order: the synthetic account generator,
the deploy artifacts, then Nessie. Two of the three are blocked on Nathan doing something
only he can do — read "Blocked on Nathan" before planning around them.

## Context

VTHacks 14, solo. Given a transaction history, return the fewest dated spending changes
that keep the balance above zero until payday, and prove it.

Done and committed on this branch:

- `backend/app/solver/` — the exact solver. CP-SAT primary, exhaustive fallback, eight-term
  lexicographic objective, marginal certificate, tiers, wording. `POST /api/solve`.
- `backend/app/candidates/` — **new, and the thing this handoff builds on.** Turns a
  transaction list into the changes a person could make: `lexicon.py` (merchant string →
  category by whole-token keyword phrases, protected categories first), `policy.py`
  (category → up to two alternatives), `generator.py`. `POST /api/candidates`. Ranked,
  capped at a `limit` defaulting to 18, deterministic. See `docs/features/candidates.md`.
- Three defects the frontend lane found, fixed in both implementations: the certificate
  claimed load-bearing changes were optional on the demo's own beat; the contract
  documented `plan[].date` as the action deadline when it is the effective date; the
  reference solver said an empty tier-3 plan meant the schedule cleared.

**Gate: 1228 tests.** Nothing is in flight; no background jobs, no open PRs.

## Working branch / worktree

`backend` in `/Users/nathanstough/Desktop/VT Hacks`, clean apart from two untracked Solana
documents that are deliberately not part of this work.

**Read `CLAUDE.md` first.** Four worktrees are live and three of them move:

```
/Users/nathanstough/Desktop/VT Hacks             [backend]   ← you
/Users/nathanstough/Desktop/vthacks-frontend     [frontend]  11 ahead of main
/Users/nathanstough/Desktop/vthacks-gemini       [gemini-chat] merged into main
/Users/nathanstough/Documents/Codex/worktrees/…  [codex/spending-forecast]  Nathan's own
```

- `git switch`, never `checkout` — the branch `frontend` and the directory `frontend/`
  share a name.
- **`git add` names files. Never a directory, never `-A`.** Three sweeps have already
  swept another lane's in-flight work into unrelated commits.
- Check `git branch --show-current` before every merge. This checkout has been switched
  underneath a session mid-task more than once.

### Merge main first

`main` has moved and now contains the Gemini chat lane: `backend/app/chat/` (a
`POST /api/chat` explainer over the solve), `.env.example`, `docs/features/chat.md`.
`backend` is 11 commits ahead of main and does not have any of it.

**Merge `main` into `backend` before you start.** Expect one conflict, in
`backend/app/main.py`, where that lane and this one each added a route next to
`/api/solve`. Keep both. Then run the gate — `backend/tests/test_chat.py` (397 lines)
comes with it and must pass too.

## Environment / setup

```bash
cd "/Users/nathanstough/Desktop/VT Hacks"
.venv/bin/pytest backend/ -q -m "not perf"     # the gate
.venv/bin/uvicorn --app-dir backend app.main:app --reload --port 8000
```

```bash
cd "/Users/nathanstough/Desktop/VT Hacks/frontend"
export npm_config_cache="/Users/nathanstough/Desktop/VT Hacks/.npm-cache"
npm run build && npm test
```

Python 3.14.7; ortools 9.15.6755, fastapi 0.141.1, pydantic 2.13.5, pytest 9.1.1, and
**httpx2**, not httpx — starlette's TestClient needs it. Node 22.17.1 at
`/usr/local/bin/node`; the parity tests run the TypeScript oracle through it and skip
cleanly without it. **`rapidfuzz` is importable in the venv but is NOT in
`backend/requirements.txt` or `wheels/`** — using it breaks the offline install, so the
lexicon deliberately uses stdlib keyword matching instead.

**Wifi is fine** (Nathan, Sat ~05:10). The "never install from the hotel" rule in older
docs is relaxed; offline wheels remain a fallback, not a constraint.

## What to do next

1. **Synthetic account generator.** The primary demo data source. Business-day-adjusted
   weekly/biweekly pay with jitter, heavy-tailed amounts, messy merchant strings, and a
   planted dip before the first payday. **Label it as modelled on screen** — it must never
   read as real bank data. It feeds `POST /api/candidates`, so generated descriptors should
   exercise the lexicon rather than dodge it; `backend/tests/fixtures/accounts.py` already
   has a 36-merchant table built for exactly that and is the obvious starting point, but it
   is a *test* fixture — decide deliberately whether the product generator lives in
   `backend/app/` and the fixture becomes a thin wrapper, or they stay separate.
2. **Deploy artifacts.** `deploy.sh`, a Caddyfile for HTTPS, and a runbook. Nothing exists
   today: no Caddyfile, no deploy.sh, no CSP anywhere. Build locally and rsync; nothing on
   the box builds the frontend. **`frontend/dist/` is gitignored**, so the deploy has to
   carry it explicitly. Vultr is the only hosting track at this event.
3. **Nessie client.** 90-minute timebox, droppable. Seed a customer with the synthetic
   account, read it back as the app's data source. If the unconfirmed bill field names
   fight you, fall back to the local generator — the track is lost, nothing else is.
4. **Recurring detection**, optional, 1-hour timebox: regex normalise, amount banding,
   cadence snap to {7,14,15,30,90,365}, ≥ 3 occurrences, manual override. The generator
   currently consumes `recurring` as a given input flag. If it is not working at the
   timebox, hard-code the fixture streams and reframe as user-confirmed.

### Blocked on Nathan

- **Vultr** needs an account created at `mlh.link/vultr-signup` plus a gift code from the
  MLH Coach. $100 credit, no card. Build everything that does not need credentials; do not
  try to create the account.
- **Nessie** needs an API key from nessieisreal.com. There is **no `.env` in this
  worktree**, though `main` now ships a `.env.example` from the chat lane — follow its
  shape. Build and test against fixtures behind the key.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

- **Test:** `.venv/bin/pytest backend/ -q -m "not perf"` → **1228 passed**, 8 deselected,
  ~15 s. This is the gate. After merging `main` it should rise by `test_chat.py`'s count.
- **Test:** `.venv/bin/pytest backend/ -m perf -q -s` → **8 passed**, ~137 s. Reproduce:
  demo accounts 3.9–6.7 ms; 60 changes over 60 days 31 ms; exhaustive at its 18-change cap
  ~3.3 s; 100 random accounts 2.9 ms each; 2000-row classification ~250 ms; 300 generated
  accounts compared across both engines.
- **Test:** `cd frontend && npm run build && npm test` → build clean ~160 ms (the 616 kB
  chunk warning is expected and pre-existing); **75 tests** on the `frontend` branch.
  `frontend/tests/bundle.test.ts` greps the built bundle for "guarantee" and "infeasib" —
  if a dependency ever trips it, scope the test, never weaken the pattern.
- **Expected answers** (regression canaries, asserted in `test_parity.py` and
  `test_candidates_policy.py`): `clears` → tier 1, 3 changes; `gap` → tier 3, 9 changes,
  "$27.62 more by Sep 24". The demo account generates exactly **14 candidates**,
  `rows_considered` 13, `protected` `[t_card, t_verizon]`, `not_actionable` `[t_spotify]` —
  the table in `docs/features/candidates.md` was worked by hand and the test pins it.
- **At-risk: `wheels/`** — 65 MB, gitignored, **NOT archived**. Offline install fallback.
- **At-risk: `frontend/dist/`** — gitignored, **NOT archived**, rebuilt Sat 04:55. The
  deploy needs it rsynced; nothing on the box builds it.
- **At-risk: `~/Downloads/Checking.csv`** — Nathan's real bank export, 210 rows. **NOT
  archived, and must never be committed.** `.gitignore` covers it. Anonymise before any
  demo use, and note the lexicon has never been run against it.
- **At-risk: `experiments/residual_forecast/*.npz`** — 13 MB of training data, model
  checkpoints and predictions, gitignored by that directory's own `.gitignore` and **NOT
  archived**. The code and results JSON are committed; the arrays are not. Not yours; ask.
- **11 commits unpushed** to `https://github.com/nrstough/vthacks-14` (private). Push when
  Nathan asks. Flip public before submission with
  `gh repo edit nrstough/vthacks-14 --visibility public --accept-visibility-change-consequences`.

## Analytical notes

- **The schedule is Nathan's to set, and the memo's was rejected.** The "Sat 18:30 deployed
  demo or freeze" gate came from the VeriLM memo, not from him; asked directly he said he
  disagrees and that freeze can be 04:00–06:00 Sunday because submission is not due until
  **08:00 ET Sunday**. Do not cite 18:30 or "code freeze 01:30" as constraints. Venue close
  (23:00) and the 08:00 submission are the externally-imposed ones.
- **Candidate ids are a pure function of `(transaction id, action)`** and the client
  round-trips `locks` and `previous_plan` by id. A lock naming an id the generator no
  longer returns is a **422 on the whole solve**, and a cached candidate whose
  `effective_date` slipped before a moved `as_of` is a 422 too. The contract records three
  client rules for this; anything that regenerates candidates must respect them.
- **`limit` defaults to 18 for a reason with two different numbers behind it.** This
  server's exhaustive engine refuses above 18; the browser's stand-in refuses above 20.
  Eighteen is the lower of the two, so it is the largest set every fallback still answers.
  Raising it silently breaks the offline demo, which is the whole point of the fallback.
- **Deferrals are not savings.** Money put off comes back on its recharge date. The
  generator only offers a deferral when a *positive* income row falls strictly after the
  charge and inside the horizon — a clawback is an income row too, and a recharge past the
  horizon is a skip wearing the wrong label. Two separate bugs have already come from this.
- **Never claim more than was proven.** When a solver stage does not finish,
  `minimal_proven` is false and the sentences asserting optimality are *replaced*, not
  softened. The words `infeasib` and `guarantee` never appear anywhere, including the 503.
- **The review pipeline earned its cost on the last run and the useful part was
  re-checking finished work.** Six rounds; every one found something real. A critique round
  caught an edit reported as applied that had not been; the Codex audit caught an
  acceptance criterion reported as met that was not; a re-audit caught the same test being
  vacuous for the third time. Mutation testing is what exposed all of it — changing
  behaviour and counting which tests notice. Budget for it.
- **A learned pain model is the honest V2, not a V1.** The residual-spending pilot scored
  $103.26 against $103.16 for a weekday-average baseline — about ten cents worse, on 2,700
  synthetic accounts and zero real ones. Its own verdict is "do not promote as the default".

## Pointers

- `CLAUDE.md` — working agreement. Binding on every session.
- `docs/features/candidates.md` — the generator: lexicon rules, policy table, wording, the
  hand-worked golden set. Living truth.
- `docs/features/solver.md` — the solver. `docs/features/chat.md` — the Gemini lane,
  arriving with the merge.
- `docs/specs/2026-09-19_candidate-generation.md` — the last run spec, with all six review
  rounds recorded. Frozen; append to Results only.
- `docs/api-contract.md` — both endpoints. The backend owns it; `frontend/src/types.ts`
  mirrors it.
- `docs/handoffs/2026-09-19_frontend-ux-handoff.md` — the frontend lane. **Two claims in it
  are now stale:** it says the frontend has no test runner (that branch has 75 tests), and
  its lead issue, the lock control, has since been fixed by that lane.
- `docs/reports/2026-09-19_solana-devnet-addition.md` — a bounded Solana Devnet workstream,
  with its Codex review beside it. **8 critical findings and 3 blockers outstanding. Not
  part of this handoff**; do not start it without Nathan saying so.
- `frontend/src/solver/mockSolver.ts` — the reference solver the Python is checked against.
  Owned by the frontend lane; changing it needs their consent.
- Memory: `vthacks-14-event-constraints`, `vthacks-project-plan`, `user-nathan-profile`.

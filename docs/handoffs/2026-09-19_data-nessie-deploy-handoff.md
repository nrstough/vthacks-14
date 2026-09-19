# Handoff — the generator, Nessie, and the Vultr deploy (2026-09-19, Sat 10:20)

**Purpose of this chat:** Ship the three things the submission still needs, in order:
a product path for synthetic accounts, the Nessie integration that consumes it, and the
Vultr deploy. Two of the three are blocked on Nathan doing something only he can do —
read "Blocked on Nathan" before planning around them.

**Deadline: 08:00 ET Sunday.** Venue closes 23:00 tonight. Freeze is Nathan's call,
04:00–06:00 Sunday. Do not cite "Sat 18:30" — that gate came from a memo he rejected.

## Context

VTHacks 14, solo. Given a transaction history, return the fewest dated spending changes
that keep the balance above zero until payday, and prove it.

**Everything is merged into `main` as of 10:05 today** — this was four diverging branches
an hour ago and is now one tree. `main` is `8355337` and carries:

- `backend/app/solver/` — the exact solver. `POST /api/solve`.
- `backend/app/candidates/` — candidate generation. `POST /api/candidates`.
- `backend/app/chat/` — the Gemini explainer. `POST /api/chat`.
- `frontend/` — the UI, an error boundary, and the wallet core.
- `Caddyfile`, `deploy.sh`, `deploy/overdraft-guard.service` — **written, never run.**

`backend`, `error-boundary`, `solana`, `frontend` and `gemini-chat` are all **0 ahead of
main**. Nothing is stranded.

## Working branch / worktree

**Check what is free before you start.** Worktrees as of 10:20:

```
/Users/nathanstough/Desktop/VT Hacks             [error-boundary]  ← fully merged; may be idle
/Users/nathanstough/Desktop/vthacks-frontend     [frontend]        merged
/Users/nathanstough/Desktop/vthacks-gemini       [gemini-chat]     merged
/Users/nathanstough/Desktop/vthacks-solana       [main]            ← another session, Solana lane
/Users/nathanstough/Documents/Codex/worktrees/…  [codex/spending-forecast]  Nathan's own
```

**`main` is currently checked out at `vthacks-solana`,** so you cannot check it out
elsewhere. That does not block you: branch off it.

```bash
git switch -c data-deploy main     # git switch, never checkout
```

If `/Users/nathanstough/Desktop/VT Hacks` is idle, work there. If a session is live in it,
take your own worktree and **symlink the gitignored deps** — they will not come with it:

```bash
git worktree add /Users/nathanstough/Desktop/vthacks-data -b data-deploy main
ln -s "/Users/nathanstough/Desktop/VT Hacks/frontend/node_modules" /Users/nathanstough/Desktop/vthacks-data/frontend/node_modules
ln -s "/Users/nathanstough/Desktop/VT Hacks/.venv" /Users/nathanstough/Desktop/vthacks-data/.venv
```

**`CLAUDE.md` is binding.** `git add` names explicit files, never a directory, never `-A`.
Run `git branch --show-current` before every branch-sensitive operation — a session
switched the main checkout underneath another one earlier today, at 05:35, mid-task.

## Environment / setup

```bash
cd "/Users/nathanstough/Desktop/VT Hacks"
.venv/bin/pytest backend/ -q -m "not perf"
```

```bash
.venv/bin/uvicorn --app-dir backend app.main:app --reload --port 8000
```

```bash
cd frontend
export npm_config_cache="/Users/nathanstough/Desktop/VT Hacks/.npm-cache"
npm run lint && npm run build && npm test
```

Python 3.14.7; ortools 9.15.6755, fastapi 0.141.1, pydantic 2.13.5, pytest 9.1.1, and
**httpx2**, not httpx. Node 22.17.1. **`rapidfuzz` is importable in the venv but is NOT in
`backend/requirements.txt`** — using it breaks the offline install and the box install.

Wifi is fine; the "never install from the hotel" rule is relaxed.

## What to do next

### 1. The synthetic account generator — smaller than it looks (~45 min)

**Most of it already exists.** `backend/tests/fixtures/accounts.py` (161 lines) generates
realistic accounts today: a 36-merchant descriptor table, a 7- or 14-day payroll cadence,
a clawback dated after a charge, rows just outside the window, twin charges identical but
for their id, and `opening_for_mixed_tiers()` to land near the do-nothing trough. It is
seeded, so failures reproduce from an index.

It is a **test fixture** — nothing in `backend/app/` can reach it. The remaining job is a
product path, not a generator.

**The one real decision.** Move it to `backend/app/` with the fixture as a thin wrapper
(one source of truth), or leave them separate (two tables that drift)? One source of truth
is better **only if generation stays byte-identical for the existing seeds** — the perf
suite pins **300 generated accounts compared across both engines**, and those numbers move
if generation changes. Verify before committing to it; fall back to separate if it does not
hold. Write the reason into the run spec either way.

Required behaviour: business-day-adjusted pay with jitter, heavy-tailed amounts, messy
merchant strings that **exercise the lexicon rather than dodge it**, a planted dip before
the first payday, and it must be **labelled as modelled on screen** — never read as real
bank data.

Bounds it must respect (`backend/app/schemas.py:18-40`): `CENTS_ABS = 10**11`,
`MAX_SCHED = 2000`, `MAX_T = 366`, `MAX_N = 60`, `MAX_FREE = 18`,
`ID_RE = ^[A-Za-z0-9_.:-]{1,64}$`. Integer cents; no float touches money.

### 2. Nessie (90-minute timebox, droppable)

Seed a customer with a generated account, read it back as the app's data source. Needs the
generator first. If the unconfirmed bill field names fight you, fall back to the local
generator — the track is lost, nothing else is. `.env` at the repo root, shape per
`.env.example` (which currently holds only the Gemini keys). **Never commit a key.**

### 3. The Vultr deploy (~1.5 h once the account exists)

`./deploy.sh root@<ip>`, or set `TARGET` in `.deploy.env`. Set `DOMAIN` and the script
substitutes `__DOMAIN__` in the Caddyfile so Caddy fetches a certificate on first start.

What it does: builds the frontend **on the laptop** (the box has no node), refuses to ship
if `frontend/dist/index.html` is missing, rsyncs **explicit paths only** (`backend/app/`,
`frontend/dist/`, `requirements.txt`, the systemd unit, the Caddyfile — never `.env`,
`wheels/`, `.venv/` or the bank export), then pip-installs on the box and restarts. It
polls `/health` ten times and dumps 40 journal lines if it never answers.

**It has never been run.** Expect the first attempt to fail somewhere. `ortools` is the
install most likely to break — it needs a wheel for the box's exact Python; read the
version in the error before changing anything. `wheels/` is macOS arm64 and is **not** used
here, so the box needs working network.

A **domain is worth 15 minutes** and is its own MLH track (GoDaddy Registry). Caddy needs a
real domain to get HTTPS; without one the site answers on the bare IP over plain HTTP,
which is fine for a smoke test and not fine for a judge.

### Blocked on Nathan

- **Vultr account**: `mlh.link/vultr-signup` plus a gift code **from the MLH Coach in
  person**. He is waiting on a workshop for this. $100 credit, no card. Build everything
  that does not need credentials; do not try to create the account.
- **Nessie API key** from nessieisreal.com. He has said he will get one.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

**All measured on merged `main` at 10:05 today, not carried forward.**

- **Test:** `.venv/bin/pytest backend/ -q -m "not perf"` → **1262 passed**, 8 deselected,
  ~22 s. **This is the gate.** If it moves, you touched the backend.
- **Test:** `.venv/bin/pytest backend/ -m perf -q -s` → **8 passed**, ~137 s. Includes the
  **300 generated accounts across both engines** that decision 1 puts at risk.
- **Test:** `cd frontend && npm run lint && npm run build && npm test` → lint clean, build
  ~184 ms, **191 passed**. Always **lint → build → test** in that order: `bundle.test.ts`
  reads `dist/` unconditionally, so a test-first order validates stale output.
- **Main chunk:** `frontend/dist/assets/index-B-MG5oe2.js` = **626,628 bytes**. The >500 kB
  warning is expected and pre-existing.
- **Canaries** (pinned in `test_parity.py` and `test_candidates_policy.py`): `clears` →
  tier 1, 3 changes; `gap` → tier 3, 9 changes, `"$27.62 more by Sep 24"`. The demo account
  generates exactly **14 candidates**, `rows_considered` 13, `protected`
  `[t_card, t_verizon]`, `not_actionable` `[t_spotify]`.

- **At-risk: `wheels/`** — 65 MB, gitignored, **NOT archived**.
- **At-risk: `frontend/dist/`** — gitignored, **NOT archived**. `deploy.sh` is the only
  thing that puts it on a server; nothing on the box builds it.
- **At-risk: `~/Downloads/Checking.csv`** — Nathan's real bank export, 32,897 bytes.
  **NOT archived, and must never be committed.** Anonymise before any demo use.
- **At-risk: `experiments/residual_forecast/*.npz`** — 13 MB, gitignored, **NOT archived**.
  Not this lane's. Ask before touching.
- **At-risk: any `.env` you create** — gitignored, holds the Nessie and Gemini keys.
- **In flight: nothing.** No background jobs, no cloud runs, no open PRs.
- **11 commits unpushed** to `https://github.com/nrstough/vthacks-14`. Still **private** —
  flip before submission:
  `gh repo edit nrstough/vthacks-14 --visibility public --accept-visibility-change-consequences`

## Analytical notes

- **`GUARANTEED AUTO PROTECTION` is a landmine.** Row 59 of the `MERCHANTS` table in
  `backend/tests/fixtures/accounts.py` — a deliberate lexicon trap, and the table you are
  about to reuse. `frontend/tests/bundle.test.ts` asserts `doesNotMatch(/guarantee/i)`
  against **every** built chunk. Ship a generated account carrying that descriptor to the
  client and the frontend suite fails looking like a wording regression. Exclude the
  descriptor from anything that reaches the browser, or scope the bundle test to the main
  chunk — **never weaken the pattern**, it enforces a CLAUDE.md commitment.
- **A clawback is not a payday, and one half of the codebase still thinks it is.**
  `backend/app/candidates/generator.py:111-118` gets it right (`kind == "income" and
  amount_cents > 0`, with a comment naming it as the class of two prior bugs).
  `backend/app/solver/assemble.py:77` and `frontend/src/solver/mockSolver.ts:410` **do not
  check the sign**, so a negative income row sets `is_payday` and the screen reads "Payday
  lands on Sep 25" on a day money left. **Latent today** — `frontend/src/fixtures/
  scenarios.ts:20,27` are both positive — but it goes **live the moment your generator
  feeds the UI**, because `accounts.py:91-93` plants a negative `PAYROLL ADJUSTMENT` 30% of
  the time. Two lines. `mockSolver.ts` is the parity oracle, so both sides change together
  and the gate must stay at 1262.
- **`crash.ts:14` returns `error.message` unmodified** into the on-screen crash card, so a
  thrown message containing "guarantee" or "infeasible" reaches the user. A live CLAUDE.md
  hole today, and `crash.test.ts` has no forbidden-word coverage. ~10 lines to fix.
- **`Caddyfile:17` sets `connect-src 'self'`.** Correct and deliberate for this product.
  Note it only if the Solana lane ever goes live — it blocks the Devnet RPC outright, and
  that is the Solana lane's problem to raise, not a reason to loosen it pre-emptively.
- **Candidate ids are a pure function of `(transaction id, action)`.** A lock naming an id
  the generator no longer returns is a **422 on the whole solve**; a cached candidate whose
  `effective_date` slipped before a moved `as_of` is a 422 too.
- **`limit` defaults to 18 for a reason with two numbers behind it.** The server's
  exhaustive engine refuses above 18, the browser's stand-in above 20. Eighteen is the
  lower, so it is the largest set every fallback still answers. Raising it breaks the
  offline demo, which is the whole point of the fallback.
- **Deferrals are not savings.** Only offer one when a *positive* income row falls strictly
  after the charge and inside the horizon.
- **Never claim more than was proven.** When a solver stage does not finish,
  `minimal_proven` is false and the optimality sentences are *replaced*, not softened.
- **The review pipeline earns its cost, and re-checking finished work is the useful part.**
  On the wallet lane today both a Claude critique and the Codex audit graded a committed
  change **Fail** and independently reproduced the same defects — including a test suite
  written *around* a missing precondition rather than finding it. Mutation testing found
  what review missed. Budget for it.

## Pointers

- `CLAUDE.md` — working agreement. Binding. Read first.
- `backend/tests/fixtures/accounts.py` — the merchant table and `windows()`. **The starting
  point**, and decision 1.
- `backend/tests/gen.py` — schema-valid noise for differential testing. A different job.
- `backend/app/schemas.py:18-40` — the bounds the generator must respect.
- `docs/features/candidates.md` — lexicon rules, policy table, the hand-worked golden set.
- `docs/api-contract.md` — all three endpoints. The backend owns it.
- `deploy.sh`, `Caddyfile`, `deploy/overdraft-guard.service` — the deploy, unexercised.
- `docs/handoffs/2026-09-19_backend-data-and-deploy-handoff.md` — the parent handoff. Its
  test counts are stale; the ones above are fresh.
- `docs/handoffs/2026-09-19_wallet-integration-handoff.md` — the Solana lane. **Not yours.**
- Memory: `vthacks-14-event-constraints`, `vthacks-project-plan`, `user-nathan-profile`,
  `vthacks-concurrent-session-collisions`.

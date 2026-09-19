# Handoff — frontend UX (2026-09-19, Sat ~03:40)

**Purpose of this chat:** Make the UI materially better. Nathan's words: "I think we can
make this UI way better." Start with the lock control, which he found confusing on sight and
which is genuinely mis-modelled, then do a broader pass. **Best UI/UX is a target track and
is judged automatically — this work is prize-relevant, not polish.** Do not do backend
candidate generation; another session owns that lane.

## Context

VTHacks 14, solo. The product: given a transaction history, return the fewest dated spending
changes that keep the balance above zero until payday, and prove it.

The frontend is built and wired. React + Vite + TypeScript + Recharts, ~1,240 lines across
15 files. It calls `POST /api/solve` with a 150 ms debounce and a stale-response guard, and
falls back to its local TypeScript solver with a visible chip when the API is unreachable.
Three bands: verdict sentence, before/after balance chart, prescription list with lock
toggles. The `frontend` branch has been merged into `main`; `main`, `frontend` and `backend`
were all at `3d89fcf` when this was written.

Verified running at `http://localhost:5173` on the built-in fallback solver, showing the
`clears` scenario: tier 1, three changes, tightest day Sep 24 at $26.74.

## Working branch / worktree

`main` in `/Users/nathanstough/Desktop/VT Hacks`. **Read `CLAUDE.md` first — it is new and it
is binding.** The short version:

- **Never commit to `main`.** `git switch -c <name> main`, work, verify, then merge.
- **Use `git switch`, not `git checkout`.** The branch `frontend` and the directory
  `frontend/` share a name and `checkout` cannot always tell them apart.
- **Name explicit paths in `git add`.** Never `git add -A`, never a bare directory. Two
  commits already swept a third party's in-flight files in under unrelated messages.
- **Check `git branch --show-current` before you merge, every time.** This checkout has been
  switched underneath a session mid-task at least twice tonight, including during the session
  that wrote this handoff. Assume it will happen to you.
- Branch from `main`, not `origin/main`. The remote runs well behind.

Nathan also works in this repo from a Codex session, in his own worktree at
`/Users/nathanstough/Documents/Codex/worktrees/vthacks-forecast` on `codex/spending-forecast`.

## Environment / setup

```bash
cd "/Users/nathanstough/Desktop/VT Hacks/frontend"
export npm_config_cache="/Users/nathanstough/Desktop/VT Hacks/.npm-cache"
npm run dev        # port 5173
```

Backend, for the non-fallback path:

```bash
.venv/bin/uvicorn --app-dir backend app.main:app --port 8000
```

Node 22.17.1 at `/usr/local/bin/node`. The npm cache export is required — the machine is on
hotel wifi and a cold npm fetch will fail. **Never install from the hotel.**

Note: the Claude preview-server tool could not launch uvicorn (`Operation not permitted`
executing `.venv/bin/uvicorn`); a plain shell works. A Vite dev server may already be running
on 5173 from another session — check before starting a second one.

## What to do next

1. **Fix the lock control.** `frontend/src/components/PrescriptionList.tsx:14`. This is the
   lead issue and the reason this chat exists. Diagnosis in Analytical notes; read it before
   redesigning. Do not just rename "Auto" — the state model is what's wrong.
2. **Fix what the "8 other changes were considered and left out" rows communicate.** Same
   control, same visual state, opposite meaning. See notes.
3. **Broader UI pass.** Nathan wants it materially better, not tweaked. The design system is
   sound (tokens at `index.css:1`, 8px scale, one accent, tabular-nums) — the weakness is in
   what the screen *says*, not its colours. Judging is technical execution, innovation,
   impact, presentation and completeness, on a 4-minute offline demo.
4. **Accessibility.** `BalanceChart.tsx` and `VerdictBand.tsx` have **zero** aria attributes
   between them; `PrescriptionList.tsx` has 3 and `App.tsx` has 1. The chart is a core
   element carrying the whole argument and is currently unreadable to a screen reader. It
   needs a text equivalent — which doubles as demo narration.
5. **Bundle size,** lowest priority. 616 kB / 182 kB gzip, over Vite's 500 kB warning; it is
   almost entirely Recharts. Only worth acting on if the deployed demo feels slow.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

- **Test:** `cd frontend && npm run lint` (oxlint) → **clean, no output**.
- **Test:** `cd frontend && npm run build` (`tsc -b && vite build`) → **clean, ~161 ms**,
  emits `dist/assets/index-*.js` at 616.19 kB / 182.60 kB gzip plus the chunk-size warning.
  The warning is expected; a *new* warning is not.
- **Test:** `.venv/bin/pytest backend/ -q -m "not perf"` → **977 passed**, 6 deselected, ~6 s.
  Run this too. It is a frontend-facing test — see the mockSolver warning below.
- **DO NOT EDIT `frontend/src/solver/mockSolver.ts` for UI reasons.** It is the oracle the
  Python solver is differentially tested against: 53 random instances, 17 planted cases, 3
  demo accounts. Changing its behaviour silently breaks backend parity, and the failure shows
  up in the *backend* suite, not the frontend. If a UI change needs different solver output,
  change the request you send, not the oracle. It is also the offline fallback — two jobs,
  one file.
- **Expected on-screen values** (canaries; also asserted in `backend/tests/test_parity.py`):
  `clears` → tier 1, 3 changes (DoorDash/Chipotle $31.80, gym $34.99, card minimum $80.00),
  tightest day Sep 24 at $26.74. `tight` ($180 opening / $100 cushion) → tier 2, same 3.
  `gap` → tier 3, 9 changes, "$27.62 more by Sep 24", certificate "grows by up to $80.00".
  If the UI stops showing these, the change broke something.
- **At-risk: `frontend/dist/`** — gitignored, **NOT archived**. Rebuilt Sat 03:35; rebuild
  before deploy. The Vultr box needs it rsynced, nothing builds it there.
- **At-risk: `frontend/node_modules/`** and **`.npm-cache/`** — gitignored, **NOT archived**,
  and not reinstallable on hotel wifi. If you take a worktree, symlink them; do not reinstall.
- **At-risk: `wheels/`** — 65 MB, 41 wheels, gitignored, **NOT archived**. Backend only, but
  do not delete it.
- **In flight:** a Vite dev server on port 5173 (PID 44499 at time of writing), started by
  another session. No background jobs, no cloud runs, no open PRs.

## Analytical notes

**The lock control, precisely.** `Locks` is two arrays, `in` and `out` (`types.ts:28`).
`stateOf()` returns `'auto'` for any id in neither. So the three buttons —

```
['in',   'Must do',  'Force this change into the plan'],
['auto', 'Auto',     'Let the solver decide'],
['out',  "Can't do", 'Rule this change out and re-plan without it'],
```

— are not three peers. "Auto" is the **absence of an answer**, rendered as an equal third
option and pre-selected on all 11 rows. The screen therefore looks like the user already
answered "Auto" to eleven questions nobody asked. Nathan's reaction, unprompted: *"it's almost
like some weird default and then I answer with the yes or no."* That is exactly the state
model, read correctly off the screen.

**The worse half:** the same control renders on the "considered and left out" rows, also
showing Auto. So one visual state means "the solver chose this" on a plan row and "the solver
rejected this" on a left-out row. The control shows the user's **input** while being
positioned and styled like the **outcome**. Separating those two things is the actual fix.

Someone already hit a nearby version of this — there is a comment in the file recording that
"Keep" was ambiguous next to a row reading "Skip the DoorDash order". Read it before renaming
anything; the naming trap is real and already cost one iteration.

**Do not "fix" these — they are deliberate** (from `CLAUDE.md`, and they are product
commitments, not preferences):

- The offline-fallback chip in the footer must stay and must keep disclosing itself. Venue
  wifi can die during judging. Never present fallback results as solver results.
- The word "infeasible" never reaches the user. When no plan clears, name the outside amount
  and the date it is needed by.
- "Sufficient under the schedule shown", never "guaranteed".
- Minimality is claimed only when proven; if a solve is not proven optimal the wording
  softens and the tier badge drops the word "proven".
- Money is integer cents everywhere. No floats touch money.

**Schedule.** There is a hard gate at **Sat 18:30**: a working deployed demo, or freeze all
features and fix only. Code freeze Sun 01:30, submission Sun 08:00. Venue closes 11:00 PM.
The gate's status is disputed — `docs/ideas.md:82` calls it superseded, but that line entered
the repo inside commit `92d9bb9` ("fix(solver): three defects the Codex audit found"), one of
the `git add -A` sweeps, so it was never reviewed as a decision about the gate. Nathan's
direct answer when asked was "finish the plan then we'll talk". **Treat the gate as live and
ask before starting anything that cannot be finished by 18:30.**

**Design system already in place** (`frontend/src/index.css:1`): tokens for background/panel/
line/ink at three weights, one accent (`#2c5ae8`), negative and warn with washes, an 8px
spacing scale (`--s1`..`--s5`), 10px radius, system sans. Two `@media (max-width: 720px)`
blocks and a `prefers-reduced-motion` block. **No dark mode.** Keep one accent and one font;
that constraint is doing real work in how the screen reads.

## Pointers

- `CLAUDE.md` — working agreement. Read first. Binding on every session.
- `frontend/src/components/PrescriptionList.tsx` — the lead issue, 141 lines.
- `frontend/src/App.tsx` (215) · `BalanceChart.tsx` (180) · `VerdictBand.tsx` (57) ·
  `index.css` (445) · `lib/api.ts` (75) · `fixtures/scenarios.ts` (82).
- `docs/api-contract.md` — the frozen `/api/solve` shape. **The backend owns it**;
  `frontend/src/types.ts` mirrors it and must be kept in step. Do not change the contract
  from this lane; ask the backend session.
- `docs/demo-script.md` — the four-minute judging script. Any UI change that breaks a beat in
  it needs the script updated in the same commit.
- `docs/prize-strategy.md` — tracks. Best UI/UX at line 25: "One screen, one decision, one
  designer voice."
- `docs/handoffs/2026-09-19_solver-core-handoff.md` — the backend lane, for context only.
- Memory: `vthacks-14-event-constraints`, `vthacks-project-plan`, `user-nathan-profile`.

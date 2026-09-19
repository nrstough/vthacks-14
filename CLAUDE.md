# CLAUDE.md

## Working agreement, read this first

**Never commit directly to `main`.** Work on a branch in your own git worktree,
verify, then merge. This applies to every agent and every session, including
Codex sessions and the human.

This is not a style preference. On the night of 19 September 2026 three actors
were writing to one checkout at once, and it cost real work:

- One session overwrote another's document; it had to be restored from memory.
- One session was a message away from reverting four bug fixes in a file it
  believed it still owned, including a false-proof fix.
- A `git add -A` on a directory swept a third party's in-flight files into
  someone else's commit, twice.

Every one of those happened on **untracked or uncommitted files**, where git
gives no warning and no conflict.

### Starting work

Branch off `main`, in this directory. Not a separate checkout.

```bash
git switch -c <name> main
```

Use `git switch`, not `git checkout`. The branch `frontend` and the directory
`frontend/` share a name, and `checkout` cannot always tell which you mean;
`switch` only ever looks at branches.

Branch from `main`, not `origin/main`. The remote runs well behind.

Only one branch can be checked out here at a time. If two sessions are live at
once, agree who holds the checkout. A separate worktree is the escape hatch for
that case, not the default; if you take one, remember `node_modules` and
`.venv` are gitignored and will not come with it, and reinstalling on hotel
wifi is not an option, so symlink them from here.

### While working

- **Name explicit paths in `git add`.** Never `git add -A`, never a bare
  directory. Someone else's file is probably sitting in it.
- **Commit early and often.** Uncommitted is unprotected.
- **Say what you own.** If two sessions are live, agree on lanes in writing
  before touching anything shared.
- **Do not edit a file in someone else's lane.** Ask them to make the change.
  It is faster than the recovery.

### Merging

Merge `main` into your branch first and resolve there, where it is safe. That
turns the merge into `main` into a fast-forward. Check with the other sessions
before fast-forwarding `main`, because it rewrites files under them.

**Check what branch you are actually on before you merge.** `git branch
--show-current`, every time. Someone else may have switched this checkout
since you last looked. That has already happened once: a merge intended for
`main` landed on `backend` because the directory had moved underneath and
nobody checked.

## Layout

- `backend/` — FastAPI app and the solver. `POST /api/solve`, `GET /health`.
- `frontend/` — Vite, React, TypeScript, Recharts. Also holds
  `src/solver/mockSolver.ts`, an exact reference implementation used both as
  the offline fallback and as the oracle the Python solver is tested against.
- `docs/api-contract.md` — the frozen request and response shape. The backend
  owns it. `frontend/src/types.ts` mirrors it and must be kept in step.
- `docs/specs/` — one run spec per change, frozen after commit.
- `docs/demo-script.md` — the four-minute judging script.

## Running it

```bash
.venv/bin/uvicorn --app-dir backend app.main:app --port 8000
```

```bash
npm run dev --prefix frontend
```

The frontend calls a relative `/api/solve`. Vite proxies it to port 8000 in
development, and FastAPI serves the built bundle from one origin in
production, so the client code is identical in both.

## Checks

```bash
.venv/bin/pytest backend/ -q
```

```bash
cd frontend && npm run lint && npm run build
```

## Things that are deliberate, do not "fix" them

- **The frontend falls back to its local solver when the API is unreachable,**
  and says so in the footer. Venue wifi can die during judging. Never remove
  the chip that discloses it; never claim solver results that did not come
  from the solver.
- **Money is integer cents everywhere.** No floats touch money.
- **The word "infeasible" never reaches the user.** When no plan clears, the
  product names the outside amount needed and the date it is needed by.
- **Say "sufficient under the schedule shown", never "guaranteed".**
- **At most one change per transaction.** Without it the solver frees more
  cash than a charge is worth and understates what the user needs.
- **Minimality is claimed only when proven.** If a solve is not proven
  optimal, the wording softens and the tier badge drops the word "proven".

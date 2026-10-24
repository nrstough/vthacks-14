# Safe to Spend: frontend

The single-page client for the cash-flow planner: Vite, React, TypeScript and
Recharts. It calls a relative `/api/...`. In development Vite proxies that to the
FastAPI backend on `127.0.0.1:8000` (set `VITE_API_TARGET` to point a second
worktree at its own backend); in production FastAPI serves this bundle and the API
from one origin, so the client code is the same in both.

## Commands

```bash
npm ci          # install from the lockfile
npm run dev     # Vite dev server on 5173
npm run lint    # oxlint
npm run build   # tsc -b, then vite build into dist/
npm test        # Node's built-in test runner; reads dist/, so build first
```

The tests run under Node 22's `--experimental-strip-types`, so there is no test
framework to install.

## The local solver

`src/solver/mockSolver.ts` is an exhaustive reference implementation of
`POST /api/solve`, and it has two jobs:

- **Offline fallback.** When the API is unreachable the page solves locally rather
  than going blank, and the nav chip says "Running on the built-in solver". That
  disclosure is deliberate: never remove it, and never present a local result as
  the server's. The local solver refuses above 20 free changes.
- **Oracle.** The backend suite runs it through Node (`backend/tests/oracle/`) as
  the reference the CP-SAT solver is checked against. It has to stay runnable with
  no npm packages, which is why its runtime imports carry explicit `.ts`
  extensions.

`src/types.ts` mirrors `docs/api-contract.md`; change the two together.

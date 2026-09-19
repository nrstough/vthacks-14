# VTHacks 14 — solo entry

Prescriptive cash-flow tool: given a transaction history, find the fewest dated spending
changes that keep the daily balance above zero until the next payday, and prove it.
Exact solver (OR-Tools CP-SAT), stateless server, no accounts, no database.

## Layout

- `backend/app/` — FastAPI app (`/health`, `POST /api/solve`) and the solver package
  (`backend/app/solver/`), Python 3.14
- `backend/tests/` — pytest suite; `tests/oracle/` runs the TypeScript stand-in solver
  through Node for parity checks
- `frontend/` — Vite + React + TypeScript + Recharts; `src/solver/mockSolver.ts` is the
  brute-force stand-in kept as an independent oracle
- `docs/api-contract.md` — the frozen `/api/solve` shape both sides build against
- `docs/specs/` — one frozen run spec per change · `docs/features/` — living feature docs
  · `docs/reports/` — plan files · `docs/consults/` — external research (VeriLM memo)
- `wheels/` — offline Python wheels (not committed; for hotel-wifi installs)

## Local setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install
```

Offline: `.venv/bin/pip install --no-index --find-links wheels -r backend/requirements.txt`

## Run

```bash
.venv/bin/uvicorn --app-dir backend app.main:app --reload --port 8000   # API (+ frontend/dist if built)
cd frontend && npm run dev                                     # Vite dev server on 5173
```

## Test

```bash
.venv/bin/pytest backend/ -q
```

Parity tests need Node ≥ 22 on PATH (they run the TS oracle with `--experimental-strip-types`).

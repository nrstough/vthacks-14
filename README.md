# VTHacks 14 — solo entry

Prescriptive cash-flow tool: given a transaction history, find the smallest dated set of
spending changes that keeps the daily balance above zero until the next payday, and prove it.

## Layout

- `backend/` — FastAPI app and solver (Python 3.14, OR-Tools CP-SAT)
- `frontend/` — Vite + React + TypeScript + Recharts
- `wheels/` — offline Python wheels (not committed)

## Local setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install
```

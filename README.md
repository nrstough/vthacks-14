# VTHacks 14 — solo entry

Prescriptive cash-flow tool: given a transaction history, find the fewest dated spending
changes that keep the daily balance above zero until the next payday, and prove it.
Exact solver (OR-Tools CP-SAT), stateless server, no accounts, no database.

## Layout

- `backend/app/` — FastAPI app (`/health`, `POST /api/solve`, `POST /api/candidates`,
  `POST /api/chat`, `GET /api/chat/status`, `POST /api/accounts/sample`,
  `POST /api/accounts/nessie`), the
  solver package (`backend/app/solver/`) and the candidate generator
  (`backend/app/candidates/`), Python 3.14
- `backend/tests/` — pytest suite; `tests/oracle/` runs the TypeScript stand-in solver
  through Node for parity checks
- `frontend/` — Vite + React + TypeScript + Recharts; `src/solver/mockSolver.ts` is the
  brute-force stand-in kept as an independent oracle
- `docs/api-contract.md` — the frozen request and response shapes both sides build against
- `docs/features/chat.md` — the Gemini explainer, `POST /api/chat`; needs `GEMINI_API_KEY` in `.env` locally (see `.env.example`), or `/etc/overdraft-guard.env` on the box
- `docs/features/nessie.md` — Capital One's sandbox as a data source, `POST /api/accounts/nessie`;
  needs `NESSIE_API_KEY`. Set `NESSIE_ACCOUNT_ID` to read an already-seeded account instead of
  creating one on every call
- `docs/specs/` — one frozen run spec per change · `docs/features/` — living feature docs
  · `docs/reports/` — plan files · `docs/consults/` — external research (VeriLM memo)
- `wheels/` — offline Python wheels (not committed; for hotel-wifi installs)

## Local setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
cd frontend && npm install
```

`requirements.txt` is production only — what `backend/app/` imports, and what
`deploy.sh` installs on the box. `requirements-dev.txt` adds pytest and the
experiment tooling; rebuild the local venv from that one, or the gate will not run.

Offline: `.venv/bin/pip install --no-index --find-links wheels -r backend/requirements-dev.txt`.
`wheels/` is gitignored and macOS arm64 only, so it exists in the original
checkout and in no clone or worktree, and it is never used on the server — the
box installs from PyPI and needs working network.

## Run

```bash
.venv/bin/uvicorn --app-dir backend app.main:app --reload --port 8000   # API (+ frontend/dist if built)
cd frontend && npm run dev                                     # Vite dev server on 5173
```

`/api/docs`, `/api/openapi.json` and `/redoc` are served locally and turned off on the box with
`OVERDRAFT_GUARD_DOCS=0`. It must be a real environment variable — the app reads it when it is
built, before anything loads `.env` — so it is set in `deploy/overdraft-guard.service`, not in
`.env.example`.

## Test

```bash
.venv/bin/pytest backend/ -q -m "not perf"    # the gate
.venv/bin/pytest backend/ -m perf -s          # timings, reported not gating
```

```bash
cd frontend && npm run lint && npm run build && npm test   # frontend: oxlint, tsc+vite, Node test runner
```

The frontend tests run under Node's built-in runner with type stripping, so there is no test
framework to install. `npm test` reads `dist/`, so build before you test.

Parity tests need Node ≥ 22 on PATH (they run the TS oracle with `--experimental-strip-types`).

## Product direction and forecast experiment

- [Expanded product and training plan](docs/vthacks-product-and-training-plan.md) — automatic setup, purchase scenarios, Gemini, model roles, and current prize corrections.
- [Neural pilot report](docs/vthacks-training-pilot.md) — completed synthetic experiment; no advantage over the weekday baseline and no real-data validation.
- [Nessie API brief](docs/nessie-agent-brief.md) and [competitive research](docs/overdraft-guard-research-and-neural-net.md) — dated research snapshots.
- `experiments/residual_forecast/` — isolated NumPy pilot, preserved data, model checkpoints, audit, and reproduction instructions; not wired into the app.

- [Dataset sources and acquisition plan](docs/vthacks-dataset-research.md) — Nedbank/Zindi, MoneyData, IBM, licenses, access paths, and forecast suitability.

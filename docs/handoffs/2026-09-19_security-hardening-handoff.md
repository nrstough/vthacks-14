# Handoff — security hardening before judging (2026-09-19)

> **Closed 2026-09-19.** Both scope items shipped on
> `claude/security-readiness-krrpk9`. The run record is
> `docs/specs/2026-09-19_chat-rate-limit-and-docs-gate.md`.
>
> The table below is the survey of `2653df3`, except for its last two rows:
> those were the open ones, and their status and evidence have been rewritten
> to what closed them. Everything else is as first written — including the
> line just above the table, which counted two of three done because that is
> what was true when the survey was taken. All of it is done now. The
> survey's original text is in git history.

**Purpose of this chat:** Run `/plan review` locally on the two-item security scope below,
then execute it on branch `claude/security-readiness-krrpk9`. The branch exists on
`origin`, is at `2653df3` (the wallet tab, the tip of `origin/main` when the cloud session
looked), and carries only this file. Skills are local, so the plan review has to happen
on the laptop; the cloud session only did the survey.

## Where things stand

The survey of `2653df3` found the security story is mostly already built, and stateless by
design is the load-bearing half of it. **Stateless removes the at-rest category entirely**
(nothing to breach, no accounts to take over, no sessions to hijack). It does not cover what
happens in flight or on the box. Of those, two of three are done:

| Concern | Status | Where |
|---|---|---|
| Data in transit | done | Caddy terminates HTTPS, HSTS set (`Caddyfile`) |
| Page as an exfil vector | done | CSP with `connect-src 'self'`, frame denial, nosniff (`Caddyfile`) |
| Hostile input to the solver | done | every list bounded, money is a strict bounded int (`backend/app/schemas.py`) |
| Key handling | done | env or gitignored `.env`; on the box a root-owned 0600 file outside the rsync list (`deploy/overdraft-guard.service`, `deploy.sh`); history scan found no key or bank export |
| Process exposure | done | uvicorn bound to loopback, `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome` |
| Open endpoint burning the Gemini key | done, 2026-09-19 | was: `POST /api/chat` had no rate limit. Now a per-address token bucket in `backend/app/ratelimit.py` (20/min, burst 10), applied to that route alone as a dependency in `backend/app/main.py`; answers 429 with `Retry-After` |
| OpenAPI docs public | done, 2026-09-19 | was: `docs_url` set unconditionally, and `/redoc` live by default. Now all three gated in `create_app`; `Environment=OVERDRAFT_GUARD_DOCS=0` in `deploy/overdraft-guard.service` closes them on the box |

Anything past this (auth, encryption at rest, per-user keys, audit) arrives with the first
row saved on the server, which is the Plaid line in `docs/prize-strategy.md` §"Security
stance for judges". Not this hackathon.

## Scope to review, in order

### 1. Per-IP rate limit on `/api/chat`

The one real gap. Anyone with the URL can loop the explainer against the server's key.
`ChatRequest` already caps a turn at 4,000 chars and a conversation at 40 turns
(`backend/app/chat/schemas.py`), so payload size is bounded; request *count* is not.

Proposed shape, for the review to accept or push back on:

- In-memory token bucket keyed by client IP, in a small module under `backend/app/chat/`
  or `backend/app/`. No new dependency: `slowapi` would be the obvious pick but installing
  on venue wifi is the recurring hazard every handoff names, so stdlib only.
- Apply only to `POST /api/chat`. `/api/solve`, `/api/candidates`, `/api/chat/status` and
  `/health` stay open; they cost nothing upstream.
- Answer **429** with a `detail` string in the same house voice as the other errors, and a
  `Retry-After` header. The frontend's `src/lib/chat.ts` should treat 429 like 503: show
  the explainer as resting, never as a crash, and never touch the solver result.
- Client IP: behind Caddy the peer is `127.0.0.1`, so read `X-Forwarded-For` first hop
  **only when the peer is loopback**, else the peer address. Caddy sets that header by
  default with `reverse_proxy`.
- Numbers to decide in the review. A starting point: 20 requests per minute per IP, burst
  10. The whole judging room shares one NAT, so too tight breaks the demo; the failure the
  limiter is for is a loop, not a crowd.
- Still stateless for the user: the bucket holds a counter per IP, no request content, and
  it dies with the process. Say exactly that in the module docstring and in the judges'
  stance paragraph.
- Tests in `backend/tests/test_chat.py` (it already stubs Gemini): N+1th request in a
  window gets 429; a different IP is unaffected; the window refills; the solver routes are
  never limited.

### 2. Gate the OpenAPI docs in production

Not a vulnerability. `create_app` should take `docs: bool`, default on, and `deploy/
overdraft-guard.service` sets an env (`OVERDRAFT_GUARD_DOCS=0` or similar) so the box
serves neither `/api/docs` nor `/api/openapi.json`. One test that both 404 when off.

### 3. Not in scope, but say it out loud

The wallet tab (`frontend/src/wallet/**`) keeps a ledger and a payment state machine in
the browser. That is client state, not server state, and it changes nothing about the
server story. A judge who asks should hear "the ledger lives in the tab and dies with it."
Add one sentence to the stance paragraph in `docs/prize-strategy.md`. No code.

## Things the plan review should check

- `CORSMiddleware` allows only the two Vite dev origins. That is correct because production
  is same-origin (one process serves `frontend/dist`). Confirm, then leave it.
- The `.env` loader in `backend/app/chat/gemini.py` reads the repo-root `.env` at first
  call. On the box there is no repo root, so it is a no-op there and `EnvironmentFile` in
  the unit does the job. Confirm nothing else reads `.env`.
- `X-Forwarded-For` trust. The rule above (trust only when the peer is loopback) is the
  whole defence against a spoofed header; the review should agree with it or replace it.

## What could not be verified in the cloud session

- Backend tests. The container had no `.venv`, so the green state of `pytest backend/ -q`
  is from the repo's record, not observed. Run it before touching anything.
- Whether the laptop's `main` is ahead of `origin/main`. If it is, push first, then
  `git switch claude/security-readiness-krrpk9 && git merge main` before executing.

## Working agreement reminders

Per `CLAUDE.md`: `git switch`, never `checkout`; explicit paths in `git add`; check
`git branch --show-current` before any merge; merge `main` into this branch first so the
merge into `main` fast-forwards.

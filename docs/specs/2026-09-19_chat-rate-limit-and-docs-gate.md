# Run spec — a rate limit on the explainer, and a gate on the API docs

**Date:** 2026-09-19
**Branch:** `claude/security-readiness-krrpk9`
**Worktree:** `~/Desktop/vthacks-security`
**Source:** `docs/handoffs/2026-09-19_security-hardening-handoff.md`

## Problem

The service is stateless by design, and that removes the whole at-rest category:
there is nothing stored to breach, no account to take over, no session to hijack.
The survey behind the handoff checked what is left — in flight, and on the box —
and found five of seven concerns already closed: HTTPS and HSTS at Caddy, a CSP
whose `connect-src 'self'` is the load-bearing half, every list bounded and money
a strict bounded int in the schemas, the key in a root-owned `0600` file outside
the rsync list, and uvicorn on loopback under `NoNewPrivileges` and
`ProtectSystem=strict`. Each of those was re-verified against the code at
`ea5632b` before this spec was written.

Two gaps remain.

1. **`POST /api/chat` has no rate limit.** `ChatRequest` caps a turn at 4,000
   characters and a conversation at 40 turns, so payload size is bounded; request
   *count* is not. Anyone with the URL can loop the explainer against the
   server's Gemini key until the free tier is gone. During judging that reads as
   the explainer being broken.

2. **The interactive API documentation is public.** Not a vulnerability — the
   contract is in the repository and the endpoints take no credential — but there
   is no reason for the box to serve a live request console for a demo.

Anything past these two arrives with the first row persisted on a server: auth,
encryption at rest, per-user keys, audit. That is the Plaid line in
`docs/prize-strategy.md`, and it is not this hackathon.

## Design decisions

**D1 — A route dependency, not middleware.** The limiter is attached to
`POST /api/chat` as a FastAPI dependency. Middleware would need a path test, and
a prefix test on `/api/chat` silently also catches `/api/chat/status`. A
dependency makes "only this route" structural rather than a string to get wrong.

Confirmed empirically: a dependency raising `HTTPException` runs *before* body
validation, so a malformed body from a limited address answers 429 rather than
422. That is the right order — the cheaper rejection wins — and it is pinned by
a test rather than left to FastAPI's discretion.

**D2 — The key is a host, never a host and port.** `request.client` is a
`(host, port)` pair and the port changes per connection. Keying on the pair
would produce a fresh budget for every request and a limiter that does nothing
while appearing to work. The key is the host string alone.

**D3 — Trust the forwarded header only from a loopback peer, and take the last
hop.** Behind Caddy the peer is always `127.0.0.1`, and `reverse_proxy` *appends*
the real peer to any `X-Forwarded-For` the client supplied. Taking the first hop
would let a looping client choose its own limiter key by sending the header
itself; taking the last hop takes the value Caddy wrote. When the peer is not
loopback the header is ignored entirely, which is the whole defence against a
spoofed key.

This replaces the handoff's proposed "first hop" rule. The handoff invited the
review to accept or push back, and the review pushed back.

`ipaddress.ip_address()` raises `ValueError` on a non-address host — Starlette's
test client uses the literal host `testclient` — so the loopback test is
guarded and a value that will not parse is treated as not loopback.

**D4 — One limiter per application instance, with an injectable clock.** The
bucket lives on the object built by `create_app`, not in a module global. Two
applications in one process hold independent budgets, which keeps the test suite
honest and means nothing leaks between them. The clock is injected so every
timing test is deterministic; no test sleeps except the one threaded hammer.

**D5 — `time.monotonic`, never the wall clock.** An NTP step or a timezone
change must not hand out free requests or lock an address out.

**D6 — A rejected request is not charged.** Charging on rejection would let a
loop extend its own lockout indefinitely, which turns a rate limit into a ban.
After a rejection, exactly one refill period admits exactly one request.

**D7 — The map of buckets is bounded.** An unbounded dictionary keyed by address
is itself a memory-growth vector. Idle buckets are evicted, and the map has a
hard ceiling.

**D8 — The bucket is lock-guarded.** The endpoint is a sync `def`, so Starlette
runs it in a thread pool and two requests can interleave a read-modify-write on
the same counter. A lock guards the critical section.

**D9 — The gate covers three URLs, and is read from a real environment
variable.** `/api/docs`, `/api/openapi.json`, and `/redoc`. The last is the
FastAPI default the application never sets and which is live today — verified,
it answers 200. The switch is read when the application is built, which is
before `load_dotenv_once()` ever runs, so it **cannot** be set from the
repository's `.env`. It is therefore not added to `.env.example`, and the
systemd unit sets it on the box. A test reads the unit file and asserts the name
it sets is the name the application reads, because that is the only way to catch
the two drifting apart.

**D10 — Wording is checked on both surfaces.** The 429 detail and the client's
message are each asserted against `app.solver.wording.BANNED`. `test_wording.py`
sweeps solver output only, so nothing today would catch a banned word in an HTTP
error detail — and a thrown message reaching the screen verbatim is exactly the
defect fixed in `70bac4d`.

**D11 — Numbers: twenty per minute sustained, burst ten.** The judging room
shares one NAT, so a tight limit breaks the demo; the failure this guards
against is a loop, not a crowd. A person asking a question every few seconds
never approaches it. A loop reaches it in under a second.

**D12 — Still stateless for the user.** A bucket holds a count and a timestamp
per address. No request content, no conversation, no identity. It dies with the
process. This is stated in the module docstring, the feature spec, and the
judges' stance paragraph.

## Scope

Limited: `POST /api/chat` only. Never limited: `POST /api/solve`,
`POST /api/candidates`, `GET /api/chat/status`, `GET /health`. They cost nothing
upstream.

Out of scope, stated out loud: the wallet tab keeps a ledger and a payment state
machine in the browser. That is client state, not server state, and it changes
nothing about the server story. One sentence in the stance paragraph, no code.

## Acceptance criteria

| # | Criterion |
|---|---|
| AC1 | Eleven rapid requests from one address: ten answered, the eleventh 429 with a `Retry-After` header. |
| AC2 | A second address is unaffected while the first is limited. |
| AC3 | Solve, candidates, chat status and health are never limited. |
| AC4 | A client that sends its own `X-Forwarded-For` cannot raise its own limit. |
| AC5 | The three documentation URLs answer 404 when the gate is off, and are served when it is unset. |
| AC6 | No banned word reaches the user from either new surface. |
| AC7 | The budget refills, and a rejected request does not extend the lockout. |
| AC8 | Full suites green: 1,271 backend plus new, 209 frontend plus new. |

## Test plan

Derived from a failure-mode inventory per stage; the inventory is in the plan
file. Roughly 33 backend tests in a new `backend/tests/test_ratelimit.py` plus
additions to `test_chat.py`, and 5 frontend tests.

Eight of them are counterfactual — each fails if its guard is deleted:

1. Trust the header from any peer → the spoof test fails.
2. Take the first hop → the last-hop test fails.
3. Key on `(host, port)` → the same-host-different-port test fails.
4. Drop the lock → the counting-lock test fails.
5. Omit `/redoc` from the gate → the three-URL test fails.
6. Parse the switch with `bool(str)` → the `"0"` row fails.
7. Prefix-match the path instead of a dependency → the status-not-limited test fails.
8. Charge a rejected request → the refill test fails.

Negative gates: malformed body from a limited address, missing key from a
limited address, and an upstream 429 from Gemini which must still surface as a
502 and never be confused with ours.

## Regression definition

Any drop below 1,271 backend or 209 frontend passes; any change to a solver
number or to wording; any existing chat test whose assertions must be weakened.

The module-scoped client fixture in `test_chat.py` posts about twenty times and
will opt out of the limit explicitly. That opt-out cannot hide a wiring mistake,
because the limiter's own tests run against a default-configured application.

## Documents

Committed to in P2:

| File | Change |
|---|---|
| `docs/specs/2026-09-19_chat-rate-limit-and-docs-gate.md` | this spec |
| `docs/features/chat.md` | 429 row, a rate-limit section, the docs-gate variable |
| `docs/prize-strategy.md` | the stance: the limiter, the wallet ledger, and the stale claim that the key lives in `.env` |
| `deploy/overdraft-guard.service` | set the docs variable off on the box |

Conditional, confirmed at execution: `README.md`, `CLAUDE.md`. Not affected:
`docs/api-contract.md`, which covers solve and candidates; the chat contract
lives in the feature spec.

The feature-spec and stance edits land in the implementation commit, when the
behaviour they describe is real. This spec is committed before any code, so
history establishes that the design preceded the implementation.

## Results

Filled in at execution.

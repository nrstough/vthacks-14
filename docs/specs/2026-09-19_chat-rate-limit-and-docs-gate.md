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

## Amendment, 2026-09-19, after the Codex plan review

Decisions above were superseded by the review, before any code was written.
They are left in place because this is the audit record; what shipped is below.

**On the provenance of this section.** The design changes were made in plan
revision 2 and approved before implementation began, but this text and
`…-plan-review.md` were both committed *with* the code, not before it. So the
ordering is self-attested rather than shown by history, and the genuinely
frozen text at `83231f1` describes a design that was never built. The next run
of this pipeline should commit the review artifact and the amendment ahead of
the implementation commit. Recorded here rather than quietly corrected.

**D3 is superseded.** The application does not parse `X-Forwarded-For` at all.
The installed uvicorn (0.53.0) enables `proxy_headers` by default, trusts
`127.0.0.1` by default, and resolves the forwarded list in reverse to the first
untrusted hop — the same rule D3 derived, already implemented and already
deployed. Hand-parsing would have meant two owners for one decision and a
branch that only ever ran under the test client. uvicorn owns it; the app reads
`request.client.host`. The unit states the flags rather than trusting a default
to stay put, and names `::1` as well, because testing showed an IPv6 loopback
peer is not trusted by the default allow-list and the whole room would then
share one bucket.

**D1 is narrowed.** "A malformed body from a limited address answers 429" is
true only for a body that parses as JSON and then fails schema validation.
A body that is not valid JSON at all is rejected by the parser before any
dependency runs, so it answers 422 even from a limited address. Both sides of
that boundary are now pinned by tests rather than left to be discovered later.

**D7 is superseded.** "Evict full or idle buckets" did not bound anything:
4,097 addresses each spending one token leaves every bucket neither full nor
idle. Replaced with a least-recently-used map under a hard ceiling. Full
buckets still go first, since they carry no information.

**D9 refined.** Gating the schema URL is what closes all three consoles —
FastAPI mounts both `/api/docs` and `/redoc` only when `openapi_url` is set.
`redoc_url` is still set explicitly so the intent does not rest on that
nesting. `/redoc` did answer 200 before this change.

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

**Tests.** Full suites, observed in this worktree:

| Suite | Before | After |
|---|---|---|
| `pytest backend/ -q` | 1,271 passed | **1,332 passed** (+61) |
| `npm test` (frontend) | 209 passed | **216 passed** (+7) |

`npm run lint` and `npm run build` clean. The frontend build runs before the
frontend tests: the bundle tests read a built `dist`, and a fresh worktree has
none.

**Acceptance criteria.**

| # | Criterion | Test |
|---|---|---|
| AC1 | Ten answered, the eleventh 429 with `Retry-After` | `test_the_default_app_allows_ten_then_refuses`, `test_the_refusal_carries_a_retry_after_header` |
| AC2 | A second address is unaffected | `test_a_second_address_is_unaffected`, `test_two_clients_behind_the_proxy_hold_separate_budgets` |
| AC3 | The other four routes are never limited | `test_the_status_endpoint_is_never_limited`, `test_health_is_never_limited`, `test_the_solver_routes_are_never_limited` |
| AC4 | A client cannot raise its own limit | `test_a_client_cannot_choose_its_own_key_by_forwarding`, `test_a_direct_peer_is_keyed_by_its_own_address` |
| AC5 | Three URLs 404 when off, served when unset | `test_all_three_documentation_urls_are_gone_when_off`, `test_unset_means_the_docs_are_served` |
| AC6 | No banned word on either surface | `test_the_refusal_uses_no_banned_word`, `no client message uses a banned word`, `the server detail is never echoed on a 429` |
| AC7 | The budget refills; a refusal does not extend the lockout | `test_the_budget_returns_after_the_window`, `test_a_refused_request_is_not_charged` |
| AC8 | Full suites green | above |

**Counterfactuals, run rather than asserted.** Each guard was deleted in turn
and the named test had to fail. All of the following bite:

| Mutation | Test that caught it |
|---|---|
| Key on `(host, port)` | `test_two_ports_on_one_host_share_a_budget` |
| Key ignores the address | `test_two_clients_behind_the_proxy_hold_separate_budgets` |
| Lock removed | `test_the_critical_section_is_locked` |
| Refusals charged | `test_a_refused_request_is_not_charged` |
| Eviction removed | `test_the_map_never_exceeds_its_ceiling` |
| Evict most-recently-used | `test_eviction_forgets_the_least_recently_used` |
| Recency tracking removed | `test_a_busy_address_is_never_the_one_evicted` |
| Limit the status route too | `test_the_status_endpoint_is_never_limited` |
| Schema URL left open | `test_all_three_documentation_urls_are_gone_when_off` |
| `bool(raw)` parsing | `test_the_switch_reads_the_usual_falsey_spellings` |
| Unit drops `::1` | `test_the_unit_enables_proxy_headers_for_both_loopbacks` |
| Unit drops the docs variable | `test_the_unit_file_sets_the_name_the_app_reads` |
| 429 branch never wired into the request path | frontend `chat-errors` (3 fail) |
| Server detail echoed on a 429 | frontend `chat-errors` (3 fail) |
| App stops reading `os.environ` for the gate | `test_the_environment_variable_actually_reaches_the_app` |
| The `ExecStart` continuation backslash is lost | `test_the_unit_parses_the_way_systemd_reads_it` |
| Backwards clock strands the timestamp | `test_a_clock_that_goes_backwards_does_not_lock_an_address_out` |
| The zero guard is removed | `test_a_limiter_cannot_be_configured_into_dividing_by_zero` |

**Two vacuous tests were found this way and fixed**, which is the reason the
exercise is run at all:

1. `test_a_busy_address_is_never_the_one_evicted` passed even when eviction
   took the most-recently-used end, because the victim was then the passer-by
   just inserted rather than the busy address. Split into two tests: one pins
   the direction of eviction, the other pins the recency tracking.
2. `test_the_unit_enables_proxy_headers_for_both_loopbacks` was satisfied by
   the *comment* above `ExecStart`. It now reads directives only. A comment
   that mentions a flag does not set it.

**Doc reconciliation against the P2 list.**

| Promised | Outcome |
|---|---|
| This run spec | Done: committed at `83231f1`, before any code |
| `docs/features/chat.md` | Done: 429 row, a **Rate limit** section, and a note distinguishing it from Gemini's own 429 |
| `docs/prize-strategy.md` | Done: the limiter, the wallet ledger, and the key location corrected — `.env` locally, a root-owned file outside the repository on the box |
| `deploy/overdraft-guard.service` | Done: the docs variable and both uvicorn proxy flags |
| The docs-gate variable *in `chat.md`* | **Moved, not dropped.** It is app-wide, not a chat setting; it went to `README.md` beside the other run-time settings |
| `README.md` (conditional) | Edited, for the reason above |
| `CLAUDE.md` (conditional) | Edited: one line so nobody "tidies away" the test opt-out or the unit's proxy flags |
| `docs/api-contract.md` | Not affected, confirmed: it covers solve and candidates |

Two frozen plan files (`docs/reports/2026-09-19_solver-core-plan.md`,
`…candidate-generation-plan.md`) quote the old `create_app` signature. They are
frozen records, and the new parameters are keyword-only, so what they say still
holds. Left alone.

**Deviations from the plan.** All of them, not only the first:

1. The docs-gate variable went to `README.md` rather than `docs/features/chat.md`;
   it is app-wide, not a chat setting.
2. No tests were added to `test_chat.py`. The plan said "additions"; only the
   fixture changed. The upstream-429 case was already covered there, as the
   review pointed out, and the limiter's own tests live in their own file.
3. `backend/tests/test_docs_gate.py` was not in the plan as a separate file.
   The plan folded stage 5 in with the rest; a separate concern got a separate
   file.
4. Seven frontend tests shipped against five planned.
5. The `docs/prize-strategy.md` edit is wider than the three items P2 named.
   It also states the HSTS, CSP, loopback-binding and sandbox facts that the
   survey had verified but the paragraph never mentioned. Each was
   re-verified against `Caddyfile` and `deploy/overdraft-guard.service` before
   being written down.

**A fourth pass graded the change Fail on documentation. Both causes were
self-inflicted, and five findings were fixed:**

| Defect | Fix |
|---|---|
| The handoff table contradicted itself: rows marked done whose evidence column still described the unfixed state, under a banner claiming the table was kept as written when its status cells had been edited | Status and evidence both rewritten for the two closed rows, and the banner now says exactly which cells changed |
| The demo script's test count was made stale **by the commit that updated it** — it said 1,325 while that same commit's suite was 1,331. The checklist item it sits inside is about precisely this | Corrected, and only after the final run. Timings are now a range with the command to re-measure, because they move between machines |
| `Retry-After` reported 3 seconds during a 600-second stranded window, computing the token deficit while ignoring the catch-up | The reported wait is the sum of both, and a test walks it to the second |
| The unit parser stripped each line before testing for the continuation backslash, so a trailing space after one was silently accepted — a false pass on the exact failure it exists to catch. A continuation left dangling at end of file also vanished silently | The backslash is checked against the raw line and an unterminated continuation is an error. Six cases verified: strict on the three broken units, tolerant of the three valid ones |
| The comment claimed the two clock guarantees "cannot both hold" | They can be had approximately, by clamping the high-water mark to a bounded skew. Not done, and now the comment says that is a choice rather than an impossibility |

**A third pass — a doc-drift sweep and a second adversarial critique — found
four more, all fixed:**

| Defect | Fix |
|---|---|
| The fix for the stranding bug below introduced the opposite hole: resyncing the timestamp to an earlier reading let a clock that steps back and then forward mint a full burst per round trip. Measured at 50 tokens granted with the clock ending exactly where it started | `at` is a high-water mark again. The guarantee is one-way on purpose and the comment now says so: a non-monotonic clock can never *increase* the budget, and the cost is that after a backwards step the bucket waits for the clock to pass its previous reading. `time.monotonic` is non-adjustable, so that cannot happen here, and a guard on spending someone's key should fail closed |
| `max_keys` was left unvalidated one line below the guard that had just been added for the other two parameters. `max_keys=0` silently admitted everything; a negative value raised out of `popitem`, a 500 from inside the dependency | The guard covers all three, and the test's parametrisation with it |
| The unit-file parser claimed systemd fidelity it did not have: it was last-wins on repeated keys, though `Environment=` is cumulative, and it did not skip a comment block inside a continuation, which systemd ignores. Both failed safe, but a correct unit edit could fail the suite depending on where it was placed | The parser collects repeated keys and skips comment blocks inside continuations; assertions test membership rather than equality |
| Two comments in `ratelimit.py` described behaviour the code no longer had | Rewritten alongside the code they sit above |

**A doc-drift sweep found six stale documents**, five of them not in the P2
list and one a contradiction this change introduced:

| Document | Was | Now |
|---|---|---|
| `docs/handoffs/2026-09-19_security-hardening-handoff.md` | Its status table still called both scope items open, and the file read as pending work | A dated closed banner; the two open rows have both their status and their evidence rewritten to what closed them, and the banner says so. Every other row is the survey as first written |
| `CLAUDE.md` | The layout listed three endpoints, omitting the one the rate-limit rule this change added is *about* | All five endpoints, with the limited one marked |
| `README.md` | Same omission; and the key location named only `.env` | Endpoint added; the key's location on the box named |
| `docs/features/chat.md` | The explainer's own configuration section was the last key-location claim that never mentioned the box | The root-owned file outside the repository named |
| `docs/demo-script.md` | "977 backend tests plus 87 frontend", and, spoken to judges, "Eight hundred and ten tests. Solves in under three milliseconds." | 1,332 and 216. **The timing claim was false**: the three demo accounts measure 3-8 ms depending on the machine, so the spoken line says under ten and the checklist gives a range with the command to re-measure. This predates the change and is outside its scope, but a measured-false promise to a judge is exactly what the wording rules exist to prevent |
| This spec | Its reconciliation table did not mention the handoff, the source of most of the above | Listed here |

**A second critique pass found five more defects, all fixed before this
record was finalised:**

| Defect | Fix |
|---|---|
| The environment-to-app wiring for the docs gate had no test at all: every test passed `docs=` explicitly, so deleting the `os.environ` read left the suite green and the box serving the console | `test_the_environment_variable_actually_reaches_the_app` |
| The unit-file tests grepped lines, so a lost `ExecStart` continuation backslash — a unit systemd would refuse to start — still passed | The unit is now parsed the way systemd reads it, continuations joined, and each flag asserted to belong to `ExecStart` |
| D5 was half-built: a backwards clock granted nothing, correctly, but stranded the timestamp in the future and locked the address out until real time caught up | `bucket.at` is resynced unconditionally; the two-sided guarantee is now tested |
| `RateLimiter(per_minute=0)` raised `ZeroDivisionError` from inside the dependency, i.e. a 500 | The constructor refuses it and names `disabled()` as the off switch |
| The full-bucket eviction pass was unreachable, not merely untested: a bucket with a token to spend always spends it, so a stored bucket is never at capacity | Removed. Dead code that looks like a policy is worse than no policy |

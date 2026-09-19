# Implementation plan — chat rate limit and API docs gate

**Run spec:** `docs/specs/2026-09-19_chat-rate-limit-and-docs-gate.md`
**Branch:** `claude/security-readiness-krrpk9` in `~/Desktop/vthacks-security`
**Base:** `83231f1` (run spec), on `ea5632b` (handoff), on `2653df3` (= `main`)
**Revision:** 2, after Codex review. See *Review findings* at the end.

Observed before planning, not taken from the record: backend `1271 passed`
(143 s), frontend `209 passed`, lint and build clean. `main` equals
`origin/main`, so no merge is needed before execution.

## The one design change that came out of review

The handoff, the run spec's D3, and revision 1 of this plan all had the
application parse `X-Forwarded-For` itself. That was wrong, and Codex caught
it.

The installed uvicorn (0.53.0) turns `proxy_headers` **on by default**, trusts
`127.0.0.1` by default, and resolves the address by walking the forwarded list
**in reverse to the first untrusted hop** — the exact rule D3 derived. So in
production `scope["client"]` is already rewritten to the real client before any
application code runs. Hand-parsing the header would have meant two owners for
one decision, and a branch that only ever executed under the test client.
Verified end to end through `ProxyHeadersMiddleware`:

| Peer | `X-Forwarded-For` | `request.client.host` |
|---|---|---|
| `127.0.0.1` | `198.51.100.7` | `198.51.100.7` |
| `127.0.0.1` | `1.2.3.4, 198.51.100.7` | `198.51.100.7` (the spoofed hop is ignored) |
| `127.0.0.1` | `127.0.0.1, 198.51.100.7` | `198.51.100.7` |
| `127.0.0.1` | absent | `127.0.0.1` |
| `203.0.113.9` | `9.9.9.9` | `203.0.113.9` (untrusted peer, header ignored) |
| `::1` | `198.51.100.7` | `::1` — **not** rewritten |

**Revised D3.** uvicorn owns address resolution. The application reads
`request.client.host` and nothing else. The systemd unit states the flags
explicitly rather than depending on a default that a future upgrade could
change, and a test asserts it does. The last row is why the unit must allow
`::1` as well: if Caddy ever dials the service over IPv6 loopback, the default
allow-list would silently key the entire room to one bucket.

## Failure-mode inventory

The tests below are derived from this table, not the other way round.

### Stage 1 — the bucket

| # | Failure mode | Consequence | Test |
|---|---|---|---|
| 1.1 | Module-global bucket | Two apps share a counter; state leaks between tests | `test_two_apps_hold_independent_budgets` |
| 1.2 | Never refills | One burst bans an address until restart | `test_the_budget_returns_after_the_window` |
| 1.3 | Refill overshoots capacity | Burst grows without bound after an idle spell | `test_a_long_idle_does_not_bank_more_than_the_burst` |
| 1.4 | Wall clock | An NTP step frees or locks an address | `test_a_clock_that_goes_backwards_grants_nothing` |
| 1.5 | Off by one | The Nth is rejected, not the N+1th | `test_exactly_the_burst_is_admitted_then_one_is_refused` |
| 1.6 | Rejections are charged | A loop extends its own lockout for ever | `test_a_refused_request_is_not_charged` |
| 1.7 | Map grows without bound | Memory grows with distinct addresses | `test_the_map_never_exceeds_its_ceiling` |
| 1.8 | No lock | Two threads interleave read-modify-write | `test_the_critical_section_is_locked` + `test_a_thread_hammer_never_admits_more_than_the_burst` |
| 1.9 | Integer truncation | Sustained rate drifts below the configured one | `test_the_sustained_rate_matches_what_was_configured` |
| 1.10 | `Retry-After` unrelated to the real wait | The client retries too early, every time | `test_the_wait_it_reports_is_the_wait_it_enforces` |
| 1.11 | Eviction resets an active attacker's budget | Filling the map becomes a bypass | `test_a_busy_address_is_never_the_one_evicted` |

### Stage 2 — the address, as deployed

Tests drive `ProxyHeadersMiddleware(create_app(...), trusted_hosts=...)`, which
is the deployed composition, not the bare application.

| # | Failure mode | Consequence | Test |
|---|---|---|---|
| 2.1 | Key on `(host, port)` | **Limiter does nothing**, looks fine | `test_two_ports_on_one_host_share_a_budget` |
| 2.2 | A client's own forwarded header picks its key | Limiter bypassed by anyone | `test_a_client_cannot_choose_its_own_key_by_forwarding` |
| 2.3 | Two real clients behind the proxy share a budget | One user's loop rate-limits the room | `test_two_clients_behind_the_proxy_hold_separate_budgets` |
| 2.4 | An untrusted peer's header is honoured | Direct-to-port bypass | `test_a_direct_peer_is_keyed_by_its_own_address` |
| 2.5 | `request.client is None` | `AttributeError` → 500 | `test_a_request_with_no_client_does_not_raise` |
| 2.6 | The deployment does not enable proxy headers | Whole room shares one bucket | `test_the_unit_enables_proxy_headers_for_both_loopbacks` |

### Stage 3 — scope

| # | Failure mode | Test |
|---|---|---|
| 3.1 | Prefix match also catches `/api/chat/status` | `test_the_status_endpoint_is_never_limited` |
| 3.2 | Solver routes limited | `test_the_solver_routes_are_never_limited` |
| 3.3 | Health limited | `test_health_is_never_limited` |
| 3.4 | Limiter applied globally | covered by 3.1–3.3 against one exhausted address |
| 3.5 | A second address swept up | `test_a_second_address_is_unaffected` |

### Stage 4 — the 429

| # | Failure mode | Test |
|---|---|---|
| 4.1 | Banned word in the detail (the `70bac4d` class) | `test_the_refusal_uses_no_banned_word` |
| 4.2 | `Retry-After` missing or unparseable | `test_the_refusal_carries_a_retry_after_header` |
| 4.3 | Body shape differs from the other errors | `test_the_refusal_has_the_same_shape_as_every_other_error` |
| 4.4 | Upstream 429 confused with ours | **already covered** by `test_chat.py::test_an_upstream_failure_is_a_502_with_the_reason`, which injects `GeminiError(status=429)` and asserts 502. Mapped, not duplicated. |
| 4.5 | A refused request still reaches Gemini | `test_a_refused_request_never_reaches_the_model` |
| 4.6 | Order of rejection versus body handling | `test_a_limited_address_is_refused_before_its_body_is_validated` **and** `test_unparseable_json_is_still_a_422` |
| 4.7 | Missing key plus limited | `test_the_limit_applies_even_with_no_key_configured` |

On 4.6, measured rather than assumed: a *parseable* body that fails schema
validation yields 429, because the dependency runs first. A body that is not
valid JSON at all yields 422 and the dependency never runs. Both are pinned so
the boundary is recorded rather than discovered later.

### Stage 5 — the docs gate

| # | Failure mode | Test |
|---|---|---|
| 5.1 | `/redoc` left open (live today, verified 200) | `test_all_three_documentation_urls_are_gone_when_off` |
| 5.2 | Schema still served without the UI | same test |
| 5.3 | `bool("0")` is `True` | `test_the_switch_reads_the_usual_falsey_spellings` |
| 5.4 | Defaults off, local development loses docs | `test_unset_means_the_docs_are_served` |
| 5.5 | Unit sets a different name than the app reads | `test_the_unit_file_sets_the_name_the_app_reads` |
| 5.6 | Looks settable from `.env` but is not | `test_the_switch_is_not_advertised_in_the_env_example` |

### Stage 6 — the frontend

Tested through `askViaApi` with a stubbed `fetch`, not only through the pure
helpers: a helper test alone would still pass if the 429 branch were never
wired up, which is the vacuous-guard class this project has been bitten by.

| # | Failure mode | Test |
|---|---|---|
| 6.1 | 429 reads as a crash | `a 429 comes back as resting, not as a failure` |
| 6.2 | The server's detail is echoed to the screen | `the server detail is never echoed on a 429` |
| 6.3 | Seconds ignored | `the seconds from the header are shown` |
| 6.4 | Missing or junk header breaks the sentence | `a 429 with no usable header still reads correctly` |
| 6.5 | 502/503 branches disturbed | `the 502 and 503 branches are unchanged` |
| 6.6 | Banned word in a client message | `no client message uses a banned word` |

## Execution order

### Step 1 — `backend/app/ratelimit.py` (new, ~90 lines)

Pure; no FastAPI import.

```python
"""A per-address rate limit for the one endpoint that costs money upstream.

Stateless for the user: a bucket holds a token count and a timestamp per
address — no request content, no conversation, no identity — and it dies with
the process. It exists to stop a loop from spending the server's Gemini key,
not to identify anyone.
"""

SUSTAINED_PER_MINUTE = 20     # D11
BURST = 10
MAX_KEYS = 4096

class Decision(NamedTuple):
    allowed: bool
    retry_after_s: int

class RateLimiter:
    def __init__(self, *, per_minute=SUSTAINED_PER_MINUTE, burst=BURST,
                 max_keys=MAX_KEYS, clock=time.monotonic, lock=None): ...
    @classmethod
    def disabled(cls) -> "RateLimiter": ...
    def check(self, key: str) -> Decision: ...
```

- Refill `elapsed * rate`, clamp at `burst` (1.3). Spend a token only when one
  is available (1.6), else
  `retry_after = max(1, ceil((1 - tokens) / rate))` (1.10).
- `clock=time.monotonic` (D5); a non-increasing clock gives `elapsed <= 0` and
  adds nothing (1.4).
- The whole body runs under `self._lock`; `lock` is injectable so a counting
  lock can prove the critical section exists (1.8).
- **Bounding (revised, Codex finding 1).** `self._buckets` is an `OrderedDict`
  with `move_to_end` on every access. After each insert: first drop any bucket
  at full capacity, which by definition carries no information, then while the
  map is still over `max_keys`, `popitem(last=False)`. That is a hard ceiling
  under every input, which the "full or idle" rule in revision 1 was not —
  4,097 addresses each spending one token would have evicted nothing.
  Least-recently-used eviction never targets an address that is currently
  hammering, since every attempt moves it to the end (1.11). An actor holding
  thousands of source addresses can force eviction, but that actor defeats any
  per-address limit by rotation alone; the ceiling is a memory bound, not a
  security boundary, and the docstring says so.

```python
def client_key(request) -> str:
    """The address to count against.

    uvicorn's ProxyHeadersMiddleware has already resolved this behind Caddy,
    so there is exactly one owner of that decision and it is not us.
    """
    client = getattr(request, "client", None)
    return client.host if client and client.host else "unknown"
```

Host only, never the port (2.1). Null client falls back to a constant (2.5).

### Step 2 — `backend/app/main.py`

Current state: `create_app` at :35, `FastAPI(...)` at :36, CORS :40–45,
handlers :47–61, routes :63–87, mount :92–93, `app = create_app()` at :98.

- Near the top:

  ```python
  DOCS_ENV = "OVERDRAFT_GUARD_DOCS"
  _FALSEY = {"", "0", "false", "no", "off"}

  def docs_enabled(env: Mapping[str, str]) -> bool:
      raw = env.get(DOCS_ENV)
      return True if raw is None else raw.strip().lower() not in _FALSEY
  ```

  An explicit set, never `bool(raw)` (5.3). Unset is `True` (5.4).
- :35 becomes
  `def create_app(dist_dir=DEFAULT_DIST, *, chat_limiter: RateLimiter | None = None, docs: bool | None = None) -> FastAPI:`
  The three existing positional callers are untouched.
- Inside: `docs = docs_enabled(os.environ) if docs is None else docs`;
  `limiter = chat_limiter or RateLimiter()` — per instance, never a module
  global (1.1, D4).
- :36 becomes

  ```python
  app = FastAPI(
      title="Overdraft Guard",
      docs_url="/api/docs" if docs else None,
      openapi_url="/api/openapi.json" if docs else None,
      redoc_url="/redoc" if docs else None,   # explicit: the default is live (5.1)
  )
  ```

- A dependency defined inside the factory, closing over `limiter`:

  ```python
  def _chat_rate_limit(request: Request) -> None:
      decision = limiter.check(client_key(request))
      if not decision.allowed:
          raise HTTPException(
              status_code=429,
              detail="The explainer is resting: too many questions too quickly. "
                     f"Try again in {decision.retry_after_s} seconds.",
              headers={"Retry-After": str(decision.retry_after_s)},
          )
  ```

  `HTTPException` yields `{"detail": ...}`, the same shape as the three handlers
  above it (4.3). No banned word (4.1, D10).
- :83 gains `dependencies=[Depends(_chat_rate_limit)]`. That route only (D1,
  3.1–3.4).
- Imports: `os`, `Mapping`, `Depends`, `HTTPException`, and
  `from app.ratelimit import RateLimiter, client_key`.

### Step 3 — `backend/tests/test_ratelimit.py` (new, ~27 tests)

Stages 1–4. Stage 2 builds its clients against
`ProxyHeadersMiddleware(create_app(None, chat_limiter=...), trusted_hosts="127.0.0.1")`
and fakes the peer with `TestClient(..., client=("127.0.0.1", 5))` — verified
that Starlette's `TestClient` accepts `client=`. Timing tests drive an injected
list-backed clock; nothing sleeps except the thread hammer.

Counterfactual pins: 2.1, 2.2, 1.8, 1.6, 1.7, 3.1.

`test_the_refusal_uses_no_banned_word` imports `BANNED` from
`app.solver.wording` and checks the live response body, not a copy of the
string. Every expected count is a literal; no test recomputes the limiter's own
arithmetic (the `70bac4d` class).

### Step 4 — `backend/tests/test_docs_gate.py` (new, 6 tests)

Stage 5, plus 2.6. Both cross-file tests read
`Path(__file__).parents[2] / "deploy" / "overdraft-guard.service"` and import
the constant from `app.main` rather than repeating a literal:
the unit must set `Environment={DOCS_ENV}=0` (5.5), and its `ExecStart` must
carry `--proxy-headers` and a `--forwarded-allow-ips` naming both `127.0.0.1`
and `::1` (2.6).
`test_the_switch_is_not_advertised_in_the_env_example` asserts the name is
absent from `.env.example`, because the gate is read before `load_dotenv_once`
and would silently not work from there (5.6, D9).

### Step 5 — `backend/tests/test_chat.py:26-28`

One change to this file, and no new test in it:

```python
@pytest.fixture(scope="module")
def client():
    # This module posts ~20 times. The limit is exercised in test_ratelimit.py
    # against a default-configured app, so opting out here cannot hide a
    # wiring mistake.
    return TestClient(create_app(None, chat_limiter=RateLimiter.disabled()))
```

### Step 6 — `frontend/src/lib/chat.ts`

Current mapping is :62–67. Add above `askViaApi`:

```ts
export const RESTING = 'The explainer is resting after a burst of questions.'

export function restingMessage(retryAfterSeconds: number | null): string {
  if (retryAfterSeconds === null || !Number.isFinite(retryAfterSeconds) || retryAfterSeconds <= 0)
    return `${RESTING} Try again in a moment.`
  const s = Math.ceil(retryAfterSeconds)
  return `${RESTING} Try again in ${s} second${s === 1 ? '' : 's'}.`
}

export function retryAfterOf(r: Response): number | null   // parses the header, null on junk
```

and, in the `!r.ok` block above the 503 line:

```ts
if (r.status === 429) throw new ChatError(restingMessage(retryAfterOf(r)), 429)
```

The client composes its own wording rather than echoing the server's detail;
the defect in `70bac4d` was a server-supplied message reaching the screen
verbatim.

`ChatPanel.tsx` needs no change: `send`'s catch already shows one line, restores
the draft, and never touches the solver result (:74–83).

### Step 7 — `frontend/tests/chat-errors.test.ts` (new, 6 tests)

Stage 6, driving `askViaApi` with `globalThis.fetch` stubbed to return real
`Response` objects, so an unwired branch fails the test (Codex finding 4). The
banned-word test uses the same two stems as the backend list.

### Step 8 — `deploy/overdraft-guard.service`

`ExecStart` at :12 gains the two flags, and a line is added after
`EnvironmentFile` at :17:

```ini
ExecStart=/opt/overdraft-guard/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 \
  --proxy-headers --forwarded-allow-ips 127.0.0.1,::1

# The box serves no interactive API console. Unset locally, so development
# keeps /api/docs.
Environment=OVERDRAFT_GUARD_DOCS=0
```

Both flags match the current defaults; stating them means a future uvicorn
default cannot silently turn the rate limit into a single shared bucket, and
`::1` covers Caddy dialling over IPv6 loopback.

### Step 9 — docs

- `docs/features/chat.md`: a 429 row in the table at :39–44; a **Rate limit**
  section after **Configuration** (:50–56) with the numbers, who owns address
  resolution, and the statelessness sentence; the docs-gate variable with the
  note that it is not a `.env` setting.
- `docs/prize-strategy.md:101-107`: the limiter sentence, the wallet-ledger
  sentence, and a correction to "API key server-side in `.env`", which on the
  box is a root-owned file outside the repository.
- `README.md`, `CLAUDE.md`: confirm at execution, then edit or strike with a
  one-line reason.
- The run spec's D3 and D7 are superseded by this revision; the run spec gets a
  dated amendment noting that, since it is the audit record.

### Step 10 — verify, then commit

```bash
cd ~/Desktop/vthacks-security
.venv/bin/pytest backend/tests/test_ratelimit.py backend/tests/test_docs_gate.py backend/tests/test_chat.py -q
.venv/bin/pytest backend/ -q
cd frontend && npm run lint && npm run build && npm test
```

`npm run build` **before** `npm test`: the bundle tests read a built `dist`, and
a fresh worktree has none. Four failures here came from exactly that, not from
a defect.

Then the doc-sync sweep, then one commit naming every path explicitly — never
`git add -A`, per `CLAUDE.md`.

## Risks

| Risk | Mitigation |
|---|---|
| The thread hammer is flaky | Wide margin; the deterministic counting-lock test is the real pin |
| The chat fixture opt-out hides a wiring mistake | Limiter tests run against a default-configured app; three scope tests cover the other routes |
| 20/min too tight for a shared NAT | ~1 question every 3 s sustained for the whole room, 10 instantly. It is one constant to raise if the venue proves otherwise |
| A future uvicorn changes a proxy default | The unit states both flags, and a test asserts it does |
| Someone reintroduces a path prefix match | The status-not-limited test fails |
| LRU eviction as a bypass | Needs thousands of source addresses, which defeats any per-address limit anyway; documented as a memory bound, and an active address is never the victim |

## Rollback

Every change is additive except two lines at `main.py:36`, the `test_chat.py`
fixture, and the unit's `ExecStart`. Reverting the single implementation commit
restores `ea5632b` behaviour exactly.

## Review findings (Codex, revision 1 → 2)

| # | Finding | Severity | Resolution |
|---|---|---|---|
| 1 | Eviction did not enforce `MAX_KEYS`: with 4,097 active addresses no bucket was full or idle, so nothing was evicted | Critical | **Accepted.** Replaced with an `OrderedDict` LRU and a hard ceiling. New tests 1.7 and 1.11 |
| 2 | "429 beats 422" was false for unparseable JSON, which returns 422 without running the dependency | Critical | **Accepted.** Claim narrowed to schema-invalid bodies; both sides of the boundary pinned in 4.6 |
| 3 | Hand-parsing `X-Forwarded-For` duplicates uvicorn's job, so the production path and the tested path differ | Suggestion, treated as critical | **Accepted, and it changed the design.** uvicorn owns resolution; the app reads `request.client.host`. Stage 2 now tests the deployed composition. The unit pins the flags, and `::1` was added after testing showed an IPv6 loopback peer is not trusted by default |
| 4 | Pure-helper frontend tests would pass even if the 429 branch were never wired | Suggestion | **Accepted.** Stage 6 drives `askViaApi` with a stubbed `fetch` |
| 5 | The proposed upstream-429 test already exists | Suggestion | **Accepted.** Mapped 4.4 to the existing test; nothing added to `test_chat.py` but the fixture |

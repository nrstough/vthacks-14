# Plan — the Nessie round trip on screen, and the Peraton entry (2026-09-19)

Run spec: `docs/specs/2026-09-19_nessie-demo.md`. Branch `nessie-demo`, worktree
`/Users/nathanstough/Desktop/vthacks-nessie`, off `data-deploy` at `fb456ab`. Line numbers
are as of that commit. Every step names the file and the current code it changes.

Order: backend first so the frontend has a real endpoint to build against, chat provenance
second because it touches the same schemas module, frontend third, docs last, then
verification. Commit after each numbered section. Reviewed by a Claude critique agent and
by Codex (`2026-09-19_nessie-demo-plan-review.md`); every finding is folded in below and
marked `[critique N]` or `[codex N]`.

---

## 0. Pre-flight

```bash
cd /Users/nathanstough/Desktop/vthacks-nessie && git branch --show-current && git status --short
```

Expect `nessie-demo` and only the staged spec, plan and review. `.env` is present (copied
from the data worktree, 0600) and holds `NESSIE_API_KEY`; the gate must never read it, so
every backend test that touches config first does
`monkeypatch.setattr(gemini, "_env_loaded", True)` and
`monkeypatch.delenv("NESSIE_API_KEY", raising=False)`, as `backend/tests/test_chat.py:83`
does.

Baselines, recorded before touching anything:

```bash
.venv/bin/pytest backend/ -q -m "not perf" 2>&1 | tail -1
```
```bash
cd frontend && npm run lint && npm run build && npm test 2>&1 | tail -3
```

Expected `2002 passed, 1 skipped, 8 deselected` and 209 frontend tests.

---

## 1. Backend: the round trip

### 1a. `backend/app/nessie/client.py` — config field, transport hardening, dead constant

- `NessieConfig` at `client.py:64-80`: add `account_id: str | None = None`, read in
  `from_env()` as `(os.environ.get("NESSIE_ACCOUNT_ID") or "").strip() or None`. Reading
  it here is what makes `.env` work, because `from_env()` is the only place
  `load_dotenv_once()` runs (`client.py:74`).
- **Redaction at the boundary** `[codex 6]`. `_request` (`client.py:94-121`) forwards the
  upstream `message` and `URLError.reason` verbatim; either can carry the URL with the
  key. Add `_scrub(config, text)` that replaces `config.api_key` (when set) with
  `<redacted>`, applied to every `NessieError` message `_request` builds.
- **Non-JSON bodies** `[codex 4]`. `json.loads` at `client.py:103` raises uncaught, a
  500. Wrap it: `NessieError("Nessie answered with something other than JSON for
  <redacted path>")`.
- `TRANSIENT = {429, 500, 503, 504}` at `client.py:49` is never read and its comment
  promises a retry `_request` does not do. Delete both. Do not add a retry: creates are
  permanent (`DELETE` answers 403) and a blind retry can double-write a row.

### 1b. `backend/app/nessie/roundtrip.py` — new module

```python
BUFFER_CENTS = 2_500            # product.py:173's constant; not a Nessie concept
CUSTOMER = {...}                # the Blacksburg "Modelled Account" body, __init__.py:86-96
NICKNAME_RE = r"^og (\d+) (\d{4}-\d{2}-\d{2}) (\d{4}-\d{2}-\d{2})$"

def round_to_dollars(cents: int) -> int
def dollars(cents: int) -> int                       # abs(round_to_dollars(cents)) // 100
def parse_nickname(text) -> tuple[int, str, str] | None
def seeded_account(seed, as_of, horizon_days) -> dict
def seed_and_read_back(account: dict, config: NessieConfig) -> dict
def read_back(account_id: str, config: NessieConfig, *, as_of: str, horizon_end: str) -> dict
def account_from_nessie(req: SampleAccountRequest, config: NessieConfig | None = None) -> dict
```

- `round_to_dollars`: half away from zero on the absolute value, sign restored, integers
  only: `q, r = divmod(abs(cents), 100); q += r >= 50`. `-1999 → -2000`, `-1950 → -2000`,
  `-1949 → -1900`, `0 → 0`.
- `seeded_account`: `sample_account(seed=, as_of=, horizon_days=)` (`product.py:82-86`),
  then `opening_balance_cents` and every `amount_cents` through `round_to_dollars`; ids,
  dates, descriptions, kinds untouched. Not the sample endpoint's account for the same
  seed; the spec says so.
- `account_from_nessie(req, config)`: `config = config or NessieConfig.from_env()`. **The
  no-key check lives here, before dispatch** `[critique 3]`: no key → `NessieUnavailable("No
  Nessie API key is configured on the server.")`. Then `read_back` when
  `config.account_id`, else `seed_and_read_back(seeded_account(...), config)`. Same
  `as_of` default as the sample route (`product.py:95`).
- `seed_and_read_back(account, config)`:
  1. `post(config, "/customers", CUSTOMER)`. Every body that should be a record passes an
     `isinstance(body, dict)` guard first `[critique 9]`; a bare string or `None` →
     `NessieUpstreamError("Nessie answered with something other than a record")`. Id via
     `body.get("objectCreated", {}).get("_id")` (`__init__.py:103`); missing →
     upstream error. `NessieNotConfigured → NessieUnavailable`, `NessieError →
     NessieUpstreamError` exactly as `__init__.py:98-101`.
  2. `post(config, f"/customers/{cid}/accounts", {"type": "Checking", "nickname": f"og
     {seed} {as_of} {horizon_end}", "rewards": 0, "balance": dollars(opening)})`. The
     nickname encodes the seed window so read-only mode can recover it `[codex 3]`.
  3. For each row of `account["scheduled"]`, by `kind`:
     - `income` → `POST /accounts/{aid}/deposits` `{"medium": "balance",
       "transaction_date": date, "status": "completed", "amount": dollars(cents),
       "description": description}`
     - `discretionary` → `POST /accounts/{aid}/withdrawals`, the same five fields
     - `bill` → `POST /accounts/{aid}/bills` `{"status": "recurring", "payee":
       description, "nickname": description, "payment_date": date, "payment_amount":
       dollars(cents), "recurring_date": int(date[8:10])}`
     Record `written[local_id] = (nessie_id, kind, dollars)`. **Every row write is wrapped
     once, whatever failed** `[critique 1]`: `except NessieError as e: raise
     NessieUpstreamError(f"Nessie failed after {i} of {n} rows were written: {e}")`; a POST
     with no id raises the same sentence with "returned no id". The transport's message
     (`client.py:115-117`) carries no count, so the count is added here.
  4. Read back `GET /accounts/{aid}/deposits`, `/withdrawals`, `/bills`. Each must be a
     list of dicts, else `NessieUpstreamError("Nessie returned a malformed <kind> list")`
     `[codex 4]`. **All three empty → `NessieUnavailable`** with the 200-empty-list wording
     from `__init__.py:115-118`, in both modes `[critique 2]`: a seeded account always has a
     payroll row, and a read-only account with nothing in it looks exactly like a wrong key.
  5. Normalise with `to_scheduled(rows, "income", True)`, `(rows, "discretionary",
     False)`, `(rows, "bill", True)`; `to_scheduled` is unchanged. A row whose `date` is
     `""` (`__init__.py:139`) **or fails the schema's `iso()` validator**
     (`schemas.py:77-80`, imported) is removed and reported `no usable date`.
  6. **The no-empty-account rule runs again after normalisation, both modes** `[codex 5]`:
     empty `scheduled` → `NessieUnavailable("Nessie returned no usable rows for this
     account")`.
  7. Match by Nessie id, known at write time from `objectCreated._id`. **One reason per
     row, in this precedence** `[codex 7]`: returned but undated → `no usable date`;
     returned but dated outside `[as_of, horizon_end]` → `outside the window` `[critique
     13]` (removed from `scheduled`; the generator and both solvers would drop it silently,
     `generator.py:129`, `mockSolver.ts:60`); not returned → `written but not returned`;
     returned with a different amount → `amount changed by the sandbox` (keep the read-back
     value, that is what the sandbox holds). `NotRoundTripped.id` is always the
     `n_<nessie_id>` form `[critique 8]`; no id appears twice. `returned = len(scheduled)`.
     Sort `scheduled` by `(date, id)`; read-back order is unverified.
  8. Return `{seed, as_of, horizon_end, opening_balance_cents (rounded modelled, never read
     back), buffer_cents: BUFFER_CENTS, scheduled, source: "nessie", nessie: {customer_id,
     account_id, mode: "seeded"}, written: N, returned, not_round_tripped}`.
- `read_back(account_id, config, *, as_of, horizon_end)` `[codex 3]`: `GET
  /accounts/{id}`; empty, non-dict or mismatched `_id` → `NessieUnavailable` (D3/D4). If
  `parse_nickname(account["nickname"])` succeeds, **that seed and window win** over the
  request's, because the rows and the frozen creation balance belong to the seeded window;
  otherwise the request's window is used and `seed` is 0, and the docs say the opening
  balance is then only right if the request starts where the seed did.
  `opening_balance_cents = to_cents(account["balance"])` is allowed because the sandbox
  balance never moves, so it is the seeded window's opening value by construction. Then
  steps 4-8 with no write comparison (`not_round_tripped` carries `no usable date` and
  `outside the window` only), `mode: "read_only"`, `customer_id` from the account,
  `written: 0`. Wraps `NessieNotConfigured` and `NessieError` as the seed path does.

The module docstring states the three measured facts (whole-dollar truncation, frozen
balance, withdrawals as the spending path) and cites `docs/nessie-notes.md` on the old
branch. Rewrite `backend/app/nessie/__init__.py:24-31` ("Nessie cannot store a transaction
history … no round trip is implemented") to the new truth and drop "Nothing in
`app/main.py` calls this package yet" at `__init__.py:6-12`.

### 1c. `backend/app/schemas.py` — the response model

After `SampleAccountResponse` (`schemas.py:382-400`):

```python
class NotRoundTripped(Strict):
    id: Id
    reason: Literal["written but not returned", "amount changed by the sandbox",
                    "no usable date", "outside the window"]

class NessieProvenance(Strict):
    customer_id: StrictStr | None
    account_id: StrictStr
    mode: Literal["seeded", "read_only"]

class NessieAccountResponse(Strict):
    seed: StrictInt
    as_of: StrictStr
    horizon_end: StrictStr
    opening_balance_cents: Cents
    buffer_cents: NonNegCents
    scheduled: list[ScheduledTxn] = Field(max_length=MAX_SCHED)
    source: Literal["nessie"]
    nessie: NessieProvenance
    written: Annotated[StrictInt, Field(ge=0)]
    returned: Annotated[StrictInt, Field(ge=0)]
    not_round_tripped: list[NotRoundTripped]
```

`SampleAccountResponse.source` stays `Literal["modelled"]` (`schemas.py:400`); its docstring
at `:390-392`, `test_accounts_product.py:208-211` and `deploy.sh:199` pin it.

### 1d. `backend/app/main.py` — two handlers and one route

- Imports: `from app.nessie import NessieUnavailable, NessieUpstreamError` and `from
  app.nessie.roundtrip import account_from_nessie` after line 25 (`from app.chat.schemas
  import …`); `NessieAccountResponse` into the `app.schemas` list at `:27-34`. Nothing
  else in the header changes; the security branch edits `import os`, `typing`,
  `DEFAULT_DIST` and the `create_app` signature, and one hunk of import conflict with it is
  accepted `[critique 6]`.
- Handlers after `_chat_upstream` (`main.py:103-105`), before `@app.get("/health")`
  (`:107`):

```python
    @app.exception_handler(NessieUnavailable)
    async def _nessie_unavailable(_: Request, exc: NessieUnavailable) -> JSONResponse:
        # No key, or a key the sandbox will not confirm. Never an empty account.
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(NessieUpstreamError)
    async def _nessie_upstream(_: Request, exc: NessieUpstreamError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})
```

- Route after `api_sample_account` (`main.py:133-141`), before `# Mounted last.` (`:143`);
  below the mount it answers 405 (`:143-146`):

```python
    @app.post("/api/accounts/nessie", response_model=NessieAccountResponse)
    def api_nessie_account(req: SampleAccountRequest) -> NessieAccountResponse:
        return NessieAccountResponse.model_validate(account_from_nessie(req))
```

### 1e. `backend/tests/test_nessie_roundtrip.py` — new, about 45 tests

Import `FakeResponse` and `http_error` from `tests.test_nessie` (module-level,
`test_nessie.py:36-54`; sound under `pythonpath = .` with `tests/__init__.py`). Add a
**scripted sandbox**: a class whose `urlopen(req, timeout)` reads `req.get_method()`, the
path of `req.full_url`, and `req.data`; answers POSTs with `{"objectCreated": {"_id":
...}}` and GETs with what was written; records every body. Knobs: `drop_ids`,
`change_amount: {id: dollars}`, `omit_date_ids`, `bad_date_ids`, `fail_at: int`,
`empty_reads`, `string_customer`, `dict_instead_of_list`, `string_row`, `html_body`,
`nickname`, `balance`. Config `NessieConfig(api_key="k"*32,
base_url="https://example.invalid")` from `test_nessie.py:33`.

Rounding, pure: the four half-up cases, zero, sign, `dollars()` is `int` (`type(...) is
int`). `parse_nickname`: `"og 7 2026-09-19 2026-10-18"` → `(7, …)`; `"Demo Checking"` →
`None`; `"og x …"` → `None`.

Seeding, faithful sandbox: exactly `2 + len(scheduled)` POSTs; customer body names
`Modelled`/`Account`; account body `balance == dollars(opening)`, type `Checking`,
nickname `og <seed> <as_of> <horizon_end>`; each row on the path its kind dictates (the
three counters equal the kind counts and are all non-zero, on a seed chosen so all three
kinds appear); every recorded `amount`/`payment_amount`/`balance` is a JSON integer; every
bill body has `payment_date` and an integer `recurring_date`; response `source ==
"nessie"`, `mode == "seeded"`, `written == returned == len(scheduled)`, `not_round_tripped
== []`; every returned amount equals written dollars × 100 with the sign by kind, over a
list asserted non-empty first; ids unique and `n_`-prefixed; `scheduled` sorted by
`(date, id)`; every date inside the window; `opening_balance_cents` equals the rounded
modelled opening while the stub's account `balance` is set to something else (proves it
is not read); same seed twice → identical body sequence.

Failure modes: no key → `NessieUnavailable`, stub never called; no key **with
`account_id` set** → the same `[critique 3]`; customer POST answering `{}` → upstream,
zero further calls; customer POST answering a bare string → upstream, not a 500 `[critique
9]`; account POST fails → upstream, zero row writes; `fail_at` on the 7th write →
upstream, message contains `6 of` and not the key `[critique 1]`; a 503 on read-back →
upstream, key redacted; an upstream `message` containing the key → not in the raised
message `[codex 6]`; a `URLError` whose reason carries the URL with the key → redacted;
`html_body` → upstream `[codex 4]`; `dict_instead_of_list` → upstream; `string_row` →
upstream; all three reads empty → `NessieUnavailable` with the "answers 200 with no data"
wording; `drop_ids` → `written but not returned`, call succeeds, `returned ==
len(scheduled)`; `change_amount` → `amount changed by the sandbox` with the read-back
value in `scheduled`; `omit_date_ids` and `bad_date_ids` (`2026-13-40`) → `no usable
date`, row absent, no `""` date anywhere; a row dated past `horizon_end` → `outside the
window`, absent; all returned rows undated → `NessieUnavailable` `[codex 5]`; a row with
no date and a changed amount appears once, as `no usable date` `[codex 7]`; ids in
`not_round_tripped` unique.

Read-only mode: `NessieConfig(account_id="acc1")` → zero POSTs; `GET /accounts/acc1`
answering `[]`, a string, or a different `_id` → `NessieUnavailable`; three empty lists →
`NessieUnavailable`; all rows undated → `NessieUnavailable`; nickname `og 7 2026-09-19
2026-10-18` → `seed == 7` and that window regardless of the request; nickname `Demo
Checking` → request window, `seed == 0`; faithful → `mode == "read_only"`, `written ==
0`, `returned == len(scheduled)`, `opening_balance_cents == to_cents(balance)`,
`customer_id` from the account.

Contract: the response validates as `NessieAccountResponse`; picking `as_of`,
`horizon_end`, `scheduled` validates as `CandidatesRequest`; adding both balances,
`candidates=[]`, `locks` validates as `SolveRequest`; `generate()` on that returns at
least one candidate (descriptors survive normalisation and classify).

Route, `TestClient(create_app(None))` plus the dist variant from `test_api.py:25-31`: no
key → 503 with JSON `detail`; scripted upstream failure → 502, detail lacks the key;
faithful → 200 and `source == "nessie"`; with a dist dir → not 405 (copy
`test_accounts_product.py:193-200`); `{"seed": 1, "extra": 1}` → 422; `horizon_days: 46`
→ 422; every string literal in `roundtrip.py` and `chat/prompt.py` free of
`guarantee`/`infeasib`/`real bank` (scan both module sources the way `test_wording.py`
scans display fields) `[critique 5]`.

One live test, `@pytest.mark.nessie` (deselected by `conftest.py:66-83` unless `-m
nessie`): seeds seed 20260919, horizon 30, against the real sandbox; asserts
`not_round_tripped == []`; prints customer id, account id and row count for the spec.

`backend/tests/test_nessie.py` gains: `from_env()` reads `NESSIE_ACCOUNT_ID` and treats
blank as `None`; the two redaction tests and the non-JSON test from 1a.

Commit: `feat(nessie): seed a sandbox account, read it back, and say what changed`.

---

## 2. Chat provenance (D12)

- `backend/app/chat/schemas.py:24-27` `ChatRequest`: `account_source: Literal["preset",
  "modelled", "nessie"] = "preset"` after `response`. Every existing test builds
  `ChatRequest` from JSON, so a defaulted field breaks nothing.
- `backend/app/chat/prompt.py:98-105` `render_context(req, res, source)`: keyword
  `account_source: str = "preset"`; after the "Numbers computed by" line at `:105`, one
  `add(...)`: `preset` → `"Account: the built-in sample account."`; `modelled` →
  `"Account: generated demo data, reproducible from its seed. Not a bank's records and
  not anyone's account."`; `nessie` → `"Account: generated demo data seeded into Capital
  One's Nessie sandbox and read back. Not a bank's records and not anyone's account.
  Amounts are whole dollars because the sandbox stores whole dollars."` No string here
  contains "real bank" `[critique 5]`. Thread through `system_instruction` (`:181-182`)
  and `chat()` (`__init__.py:126,148`, `req.account_source`).
- `backend/tests/test_chat.py`: three tests **through `POST /api/chat`** using the existing
  `fake` Gemini fixture (`test_chat.py:66-72`), asserting on the instruction the fake
  received `[critique 4]`: omitted field → the built-in line and no "demo data"; `modelled`
  → "not anyone's account"; `nessie` → the sandbox line. Going through the route is what
  makes a forgotten `account_source=req.account_source` fail.
- `frontend/src/lib/chat.ts:43-52`: `askViaApi` gains `accountSource: AccountSource =
  'preset'` as its **last** parameter with a default `[critique 7]`, so the security
  branch's positional call in `tests/chat-errors.test.ts:38` still compiles; the body
  gains `account_source`. `ChatPanel.tsx:20-28` prop type gains `accountSource`. The
  `source` query parameter is untouched.

Commit: `feat(chat): tell the explainer where the account came from`.

---

## 3. Frontend

### 3a. `frontend/src/types.ts` — mirror the contract

Append after `SolveRequest` (`types.ts:33-42`): `CandidatesRequest`, `CandidatesMeta`
(`schemas.py:336-341`), `CandidatesResponse`, `SampleAccountRequest`,
`SampleAccountResponse` (`source: 'modelled'`), `NotRoundTripped`, `NessieProvenance`,
`NessieAccountResponse` (`source: 'nessie'`), `type LoadedAccount = SampleAccountResponse
| NessieAccountResponse`, `type AccountSource = 'preset' | 'modelled' | 'nessie'`. Unions,
never `enum` (`tsconfig.app.json:22`).

### 3b. `frontend/src/lib/accounts.ts` — new, pure builders plus clients

Export `describeDetail` from `api.ts:23`. Import with `.ts` extensions as `narrate.ts:9`
does.

Pure, tested:
- `CANDIDATE_LIMIT = 18`, with the reason from `docs/api-contract.md:179-183`.
- `toCandidatesRequest(account)` picks exactly `as_of`, `horizon_end`, `scheduled`,
  `limit: CANDIDATE_LIMIT`; never spreads (`seed`/`source` would 422,
  `docs/api-contract.md:229-234`).
- `toBase(account, candidates): SolveRequest` picks `as_of`, `horizon_end`, both
  balances, `scheduled`, `candidates`, `locks: {in: [], out: []}`.
- `parseAccount(json)` refuses any `source` other than `'modelled'`/`'nessie'` with
  `ApiError('The server returned an account with no provenance.')`.
- `provenanceLine(account | null, base)`: null → `Sample checking account, Sep 19 to
  Oct 2.`; modelled → `Modelled account, seed 12345, Sep 19 to Oct 18.`; nessie seeded →
  `Capital One sandbox, 23 of 23 rows read back, Sep 19 to Oct 18.` plus one clause per
  reason present, counted by reason and in a fixed order `[codex 7]`: `, 1 row not
  returned`, `, 2 amounts changed by the sandbox`, `, 1 row without a date`, `, 3 rows
  outside the window`; read-only → `Capital One sandbox account …<last 6 of id>, 19 rows,
  Sep 19 to Oct 18.` Uses `shortDate` (`format.ts:14`).
- `sliderBounds(opening)` `[critique 10]`: the range input snaps to `min + k·500`, so
  `min` must put `opening` on the grid: `min = opening - 500·floor((opening -
  min(2000, opening)) / 500)`, `max = max(30000, opening) + ((min - max) mod 500
  correction)` so that `(max - min) % 500 === 0` and `max >= opening`.

Clients, same shape as `api.ts:44-74` including the `signal.aborted` re-throw:
- `loadModelled(signal)` → `POST /api/accounts/sample` `{}`.
- `loadNessie(signal)` → `POST /api/accounts/nessie` `{}`; 503 → `'The Capital One
  sandbox is not configured on this server.'`; 502 → `'The Capital One sandbox did not
  answer.'`; network, **or any 5xx with no JSON `detail`** `[critique 11]` (the Vite proxy
  answers a dead backend with an empty 500, `vite.config.ts:14`) → `'Could not reach the
  server.'`.
- `candidatesViaApi(request, signal)` → `POST /api/candidates`; 4xx `'Candidates rejected
  the request'`, 5xx `'Candidate generation failed (N)'`.
- `loadAccount(kind, signal)` runs the two in sequence, returns `{account, base, meta}`.

### 3c. `frontend/src/lib/accountState.ts` — new, a pure reducer `[codex 1, 2]`

State `{account: LoadedAccount | null, base: SolveRequest, loading: 'modelled' | 'nessie'
| null, error: string | null, seq: number}`. Actions: `start(kind)` bumps `seq`, sets
`loading`, clears `error`; `succeed(seq, account, base)` ignored when stale, else sets
both and clears `loading`; `fail(seq, message)` ignored when stale, else sets `error` and
clears `loading`; `preset(fixture)` bumps `seq`, **clears `loading` and `error`**, account
`null`, base = fixture. Tests, about 10: stale `succeed` ignored; stale `fail` ignored;
`preset` during a load leaves `loading === null` (Codex 1: otherwise both buttons stay
disabled forever); two `start`s then the first `succeed` ignored, the second applies;
`preset` after `succeed` restores the fixture; `start` clears a previous `error`.

### 3d. `frontend/src/App.tsx`

- `:24` `const BASE = SCENARIOS[0].request` → `const FIXTURE = SCENARIOS[0].request`, and
  `const [acct, dispatch] = useReducer(accountReducer, initial(FIXTURE))`; `base`,
  `account`, `loading`, `error` read off `acct`. A ref holds the in-flight
  `AbortController`.
- `:28-29` initialisers read `FIXTURE`.
- `:34-42` the memo spreads `...base`; deps `[base, opening, buffer, ruledOut]`.
- `:46` unchanged.
- `:92-102` the catch: wrap `solve(debounced, before)` in `try { … } catch (e) {
  setSource('local'); setNotice(e instanceof Error ? e.message : 'Could not solve
  offline.'); return }` so a throw in the fallback is never an unhandled rejection.
- `:157-162` `preset()` gains: abort the in-flight load; `dispatch(preset(FIXTURE))`;
  **`seq.current++`** (`:57`) so a server answer for the old account still in flight is
  discarded by the guard at `:80` `[codex 2]`; `setSolvedRequest(null)`,
  `setSolvedRuledOut(NONE)`, `setNewIds([])`; `setRes(solve({...FIXTURE, the preset
  balances}, []))` so the old account's rows are gone on the next paint.
- New `async function load(kind)`: abort the previous controller, new one in the ref;
  `const seqNo = nextSeq()` and `dispatch(start(kind))`; `try { const {account, base} =
  await loadAccount(kind, ctl.signal); if (seqNo !== current) return;
  dispatch(succeed(seqNo, account, base)); setOpening(base.opening_balance_cents);
  setBuffer(base.buffer_cents); setRuledOut(NONE); previousPlan.current = [];
  seq.current++; setSolvedRequest(null); setSolvedRuledOut(NONE); setNewIds([]); try {
  setRes(solve(base, [])) } catch { /* the effect answers */ } } catch (e) { if
  (ctl.signal.aborted) return; dispatch(fail(seqNo, message)) }`. Because `res`, `base`
  and the sliders change in one event batch `[critique 14]`, the list, chart and verdict
  show the new account on the next paint and the old plan's checkboxes are gone before
  anyone can tick one `[codex 2]`; the debounced request then fetches the server's answer
  for the same account.
- `:174-177` tagline → `{provenanceLine(account, base)}` plus the existing second
  sentence; rendered only when `tab === 'plan'`.
- `:236-252` presets: `aria-pressed` gains `&& account === null`. After the `</span>`, a
  second `<span className="ctl-presets ctl-sources">` with `New modelled account` and
  `Capital One sandbox`, `aria-pressed={account?.source === …}`, `disabled={loading !==
  null}`, label `Loading…` while in flight; below, `<p className="ctl-note"
  role="status">{error}</p>` when set.
- `:230-231` opening slider `min`/`max` from `sliderBounds(opening)`; buffer slider
  unchanged.
- `:276` `<h2>Daily balance, September 19 to October 2</h2>` → `Daily balance,
  {shortDate(base.as_of)} to {shortDate(base.horizon_end)}`.
- `:326` `<ChatPanel key={accountKey} … accountSource={account?.source ?? 'preset'} />`
  with `accountKey = account?.nessie?.account_id ?? (account ? 'm' + account.seed :
  'preset')` `[codex 8]`. A key change remounts the panel, clearing its messages and
  aborting a pending reply through its effect cleanup; verify at execution that
  `ChatPanel.tsx:71`'s controller is aborted on unmount and add the cleanup if not.

### 3e. `frontend/src/index.css`

After `.ctl-presets button[aria-pressed='true']` (`:140-145`): `.ctl-presets
button:disabled { opacity: .55; cursor: progress; }`, `.ctl-presets
button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }`,
`.ctl-sources { margin-top: 6px; }`. The dead `.switcher` block stays.

### 3f. `frontend/tests/accounts.test.ts` and `frontend/tests/account-state.test.ts`

About 32 tests. `toCandidatesRequest` has exactly four keys and `limit === 18`; `toBase`
has exactly the seven `SolveRequest` keys, empty locks; `source: 'other'` refused;
`provenanceLine` for null, modelled, nessie seeded clean, one changed amount (singular),
three (plural), one of each reason (four clauses, fixed order), read-only; none match
`/guarantee|infeasib|real bank/i`; `sliderBounds`: `(19892)` → `{1892, 30392}`, `(20000)`
→ `{2000, 30000}`, `(45000)` → `{2000, 45000}`, `(500)` → `{500, 30000}`, `(0)` → `{0,
30000}`, and for each `(opening - min) % 500 === 0` and `(max - min) % 500 === 0`; a
captured modelled-account fixture (JSON literal, 20 rows, 12 candidates) solves on
`mockSolver.solve` with a tier in 1..3; 21 **actionable** candidates (lead time 0, none
locked, `mockSolver.ts:203,215`) make `solve` throw `[critique 17]`; the reducer cases
from 3c. `bundle.test.ts`: one presence check for `'Capital One sandbox'` mirroring
`:35-38` (the button label is a literal, so the grep passes).

Commit: `feat(frontend): load a modelled or sandbox account, and say which it is`.

---

## 4. Docs

- `docs/features/nessie.md`: status → "built, verified, wired"; the table's unwritten rows
  flip; sections "Whole dollars", "Withdrawals are the spending path", "Read-only mode and
  the nickname", "What `not_round_tripped` means", "Key redaction at the transport".
- `docs/features/accounts.md:66-106`: the Nessie section becomes a pointer to `nessie.md`
  and the route.
- `docs/features/frontend.md`: "Account sources" after "Sources of truth on screen"
  (`:21`); a provenance line under "Wording rules" (`:113`); the reducer under "Tests".
- `docs/features/chat.md`: `account_source`.
- `docs/api-contract.md`: `## POST /api/accounts/nessie` after `:266`, every field, the
  four reasons, the whole-dollar note, the nickname, and the client rules (clear locks on
  load, pin `limit`, treat an empty 5xx as unreachable).
- `README.md`: endpoint list; `NESSIE_ACCOUNT_ID`.
- `.env.example`: `NESSIE_ACCOUNT_ID=` with a two-line comment; fix the stale "No route
  calls the adapter yet" comment on `NESSIE_TIMEOUT_S`.
- `docs/nessie-agent-brief.md`: a dated note at the top listing the measured corrections
  (withdrawals, whole-dollar truncation, frozen balance, the 201 envelope).
- `docs/demo-script.md:147-155`: the optional beat rewritten to what is true: "This
  account was seeded into Capital One's Nessie sandbox and read back over their API.
  Whole dollars, because that is what the sandbox stores. The solver never trusts the
  sandbox's balance." Likely questions gains **"Why is this mission-critical AI?"** with
  the Peraton answer.
- `docs/prize-strategy.md:34,77,99`: Peraton → **Enter**, no build; a "Why Peraton"
  paragraph after the sponsor table; and a fenced **Devpost text** block `[critique 15]`:
  the project blurb, the AI-tools disclosure line naming Claude Code and Codex, and the
  Peraton one-liner, so Sunday morning is copy-paste.
- Run spec results filled at the end.

Known doc conflicts with the security branch, accepted `[critique 6]`: `README.md`,
`docs/demo-script.md`, `docs/prize-strategy.md`, `docs/features/chat.md`.

Commit: `docs: the Nessie route, the account sources, and the Peraton entry`.

---

## 5. Verification

```bash
cd /Users/nathanstough/Desktop/vthacks-nessie && .venv/bin/pytest backend/ -q -m "not perf"
```
```bash
cd /Users/nathanstough/Desktop/vthacks-nessie/frontend && npm run lint && npm run build && npm test
```
```bash
cd /Users/nathanstough/Desktop/vthacks-nessie && .venv/bin/pytest backend/tests/test_nessie_roundtrip.py -q -m nessie -s
```

Browser, via the preview tool on this worktree's servers. First `lsof -nP -iTCP:8000
-sTCP:LISTEN` `[critique 12]`: if another checkout holds 8000, stop it or run this
worktree's backend on 8001 with the proxy target overridden for the session; the backend
must be this worktree's or the sandbox button hits a server without the route. Then:
click "Capital One sandbox", read the provenance line and a solved plan; click "$200.00",
the built-in returns; click a preset mid-load and confirm both buttons re-enable; stop
the backend, click both buttons, read "Could not reach the server", solve a preset.
Screenshots into the run spec.

Golden hash and canaries: `pytest backend/tests/test_accounts_golden.py
backend/tests/test_api.py -q`.

---

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Withdrawals create path is undocumented on the web reference | Confirmed against Capital One's SDKs in the notes; the live test decides. If the sandbox refuses withdrawals, execution **stops and reports**; no silent local-rows alternative, because mixing local and read-back rows contradicts the response contract `[codex 9]`. |
| Whole-dollar rounding removes the planted dip on some seeds | The seed used on stage is chosen from the live test; the sample route keeps cents. |
| Read-back order or truncated payees change candidate classification | Sort locally; the contract test runs `generate()` on the round-tripped account and asserts a non-empty candidate set. |
| Lock naming an evicted id (D-F) | Locks cleared on every load; `limit` pinned; old rows unmounted in the same batch as the new base. |
| Fallback solver throws above 20 | `limit` 18 and a try/catch in the catch. |
| Merge conflict with the security branch | Handlers and route in regions it does not touch; chat provenance via a request field, not the decorator. Accepted one-hunk conflicts: `main.py` import block, `README.md`, `docs/demo-script.md`, `docs/prize-strategy.md`, `docs/features/chat.md`. `data-deploy` already conflicts with security in `main.py`'s header. |
| Seeds are permanent in the sandbox | One customer per load, nonce-named; read-only mode for judging morning. |
| The demo-data line reaching the chat is itself scrubbed | It contains no banned word; the route-level test asserts it reaches the model. |
| A read-only account whose window differs from the request | The nickname carries the seed window and wins; an unparseable nickname is documented as request-window-with-creation-balance. |
| Port 8000 held by another checkout during verification | `lsof` check in section 5. |

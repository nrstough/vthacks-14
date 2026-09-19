# Run spec — the Nessie round trip on screen, and the Peraton entry (2026-09-19)

Branch `nessie-demo`, worktree `/Users/nathanstough/Desktop/vthacks-nessie`, off
`data-deploy` at `fb456ab`. Frozen after commit; later corrections go in a dated note at
the end, never by rewriting a line above.

## Problem

The Capital One track is judged on use of Nessie, and nothing a judge can see touches it.
`app/nessie/` is built, tested and verified against the live sandbox, but no route calls
it; the frontend calls only `/api/solve` and `/api/chat/status`; even `/api/accounts/sample`
has no button. The demo script's bank beat ("pulling an account from Capital One's
sandbox") cannot be said truthfully today.

Separately, the Peraton "Best Mission Critical AI" entry has a one-line rationale in
`docs/prize-strategy.md` and nothing a judge could read.

**What Nessie can hold, corrected while planning.** The adapter's docstring says purchases
cannot be stored and so discretionary charges cannot round-trip. The older Nessie notes
(`docs/nessie-notes.md` on the abandoned review-response branch) settle it differently and
against Capital One's own SDKs: income is a deposit, spending is a **withdrawal**
(`POST /accounts/{id}/withdrawals`, same shape as a deposit), recurring is a bill. So every
kind of row can round-trip. Two further measured facts from the same notes decide the
design: **every amount is truncated to whole dollars on write**, and **writes never move
the account balance**. The local integer-cent ledger stays the system of record; Nessie is
a seeded history source, never the arithmetic.

## What we verified before planning (not inherited from the handoff)

- `data-deploy` is **17 commits ahead of `main` and not merged.** The merge waits on the
  firewall, the public deploy checks, and the security branch, in that order. This branch
  is cut from `data-deploy`, not `main`.
- `app/main.py` registers `/api/accounts/sample` above the static mount; a route added
  below the mount answers 405 (the silent-shadow defect from the deploy).
- `to_scheduled()` derives ids from Nessie `_id` (`n_` prefix), reads `transaction_date`
  or `payment_date`, `description` or `payee`, forces charges negative, and emits `""` for
  a missing date, which the schema would 422.
- `verify()` names its customer "Modelled Account" at a Blacksburg address so nobody
  mistakes it for a person. The seed path reuses that identity.
- `SampleAccountResponse.source` is a required literal `"modelled"`, pinned by its tests
  and by the deploy smoke check. The Nessie response is a sibling model, not a widening.
- The transport forwards upstream messages and network errors verbatim, so a key in an
  upstream message would reach a response; and a non-JSON body is an uncaught 500. Both
  are fixed here.
- The frontend has never called `/api/candidates`; `SCENARIOS` carry their candidates
  inline. A loaded account has to fetch its own.
- The frontend's built-in solver throws above 20 actionable candidates, inside the solve
  effect's catch, where a throw is an unhandled rejection and a silently stale screen.
  The candidates request pins `limit` to 18 explicitly.
- `frontend/src/App.tsx` hard-codes the demo window twice, tagline (line 175) and chart
  heading (line 276). Nothing in `frontend/tests/` imports the App component.
- The chat prompt has no notion of data provenance; `source` there means which solver
  ran. A judge asking the explainer "is this my real account" today gets no guard.
- `frontend/tests/bundle.test.ts` scans every built chunk for `/guarantee/i` and
  `/infeasib/i`. Runtime JSON is not scanned; the chat scrubber masks descriptor fields.
- The security branch (`claude/security-readiness-krrpk9`) forked from `2653df3`, before
  all of `data-deploy`. In `app/main.py` it changes the import block, the `DEFAULT_DIST`
  region, the `create_app` signature and the `/api/chat` decorator. The exception
  handlers, the sample route and the static mount are untouched, so the new handlers and
  route go there, and this branch does not touch the `/api/chat` decorator at all.

## Decisions

**D1 — one route, `POST /api/accounts/nessie`, that seeds and reads back.** Request body
is `SampleAccountRequest` (seed, as_of, horizon_days). The server generates the modelled
account, creates a customer and a checking account, posts each `income` row as a deposit,
each `discretionary` row as a withdrawal and each `bill` row as a bill, reads all three
lists back, normalises through `to_scheduled`, sorts by `(date, id)` because read-back
order is unverified, and returns the account. Sequential writes, twenty-odd, a few seconds.

**D2 — the response is the sample shape plus provenance, in its own model.** A new
`NessieAccountResponse` with `source: "nessie"`, a `nessie: {customer_id, account_id,
mode}` block, `written` and `returned` counts (`returned` is the rows in the response),
and `not_round_tripped: [{id, reason}]` with one reason per row: `no usable date`,
`outside the window`, `written but not returned`, `amount changed by the sandbox`, in that
precedence. A row with no usable date is dropped and reported rather than emitted with an
empty date. Nothing is dropped silently.

**D3 — a read can never confirm the key, on this path too.** Three empty lists, or a
normalised schedule with nothing in it, is raised as unavailable, never returned as an
empty account, in both modes. The no-key check runs before any dispatch, in both modes.

**D4 — `NESSIE_ACCOUNT_ID` makes the route read-only.** When set, no POST is issued; the
route reads that account and returns it. Seeded once before judging, the demo-morning
load is a handful of GETs and creates no customer. The seeded account's nickname encodes
its seed and window (`og <seed> <as_of> <horizon_end>`), so a read-only load recovers the
window the rows and the frozen creation balance belong to; if the nickname does not
parse, the request's window is used and the docs say the opening balance is then only
right if the request starts where the seed did. `nessie.mode` says `"read_only"`.

**D5 — whole dollars at the seed boundary, exact after it.** The sandbox truncates on
write, so every modelled amount is rounded to whole dollars (half away from zero) before
seeding, the opening balance included, and the bodies carry JSON integers. No float is
ever constructed. The account returned uses the read-back amounts, so what is on screen
is what the sandbox holds, and a test asserts written equals read for every row over a
non-empty list. The opening balance is carried from the rounded modelled value in seeded
mode and from the frozen creation balance in read-only mode, never from arithmetic. The
cent-precise path stays on `/api/accounts/sample`.

**D5a — the transport scrubs the key and refuses non-JSON.** Upstream messages and
network errors are scrubbed of the configured key before they become exceptions; a
non-JSON body, a non-list list or a non-dict row is an upstream error, not a 500.

**D6 — status mapping follows the chat precedent.** `NessieUnavailable` → 503 with a
JSON `detail`; `NessieUpstreamError` → 502. Handlers registered beside the chat ones. The
key never appears in either detail.

**D7 — the frontend gets an account-source control, and loading replaces the whole
scenario.** Two buttons beside the presets: "New modelled account" and "Capital One
sandbox". A load sets the base request, both balances, fetches candidates from
`/api/candidates` with `limit` 18, clears ruled-out changes and the previous plan, and
replaces the on-screen answer in the same render so the old account's rows are never
clickable. Any preset returns to the built-in `SCENARIOS`, re-enables the buttons, and
discards any load or solve still in flight. The load lifecycle is a pure reducer.

**D8 — provenance is a sentence, not a badge.** The tagline stops hard-coding the
September dates and states where the account came from, with a clause per
`not_round_tripped` reason counted separately. An unrecognised `source` is refused by the
client. Sandbox data is never called real bank data.

**D9 — the offline demo survives.** With the API unreachable (a network failure, or the
empty 500 the Vite proxy answers with) the two buttons say so and the presets keep
working. An account already loaded still solves on the built-in solver. The footer chip
is unchanged.

**D10 — Peraton is words only.** A paragraph in the prize strategy, a question and answer
in the demo script, and a Devpost text block including the AI-tools disclosure.

**D12 — the explainer is told where the data came from.** `ChatRequest` gains an optional
`account_source: "preset" | "modelled" | "nessie"`, default `"preset"`. The prompt gains
one line naming the source; for modelled and sandbox accounts it says the data is
generated demo data, not a bank's records and not anyone's account. A request field, not a
query parameter, so the `/api/chat` decorator the security branch edits is untouched. The
chat panel remounts on account change so a conversation never spans two accounts.

**D11 — out of scope.** D-G (the dead perf guard) stays open. No change to solver,
candidates or wallet code; the chat code changes only as D12 states. No merge to `main`
from this branch. If the live sandbox refuses withdrawals, execution stops and reports;
there is no local-rows fallback.

## Acceptance criteria

1. `.venv/bin/pytest backend/ -q -m "not perf"` passes: 2002 baseline plus the new tests,
   1 skipped, 8 deselected. Golden hash `8d4ddf30…81048` unmoved. Canaries unmoved.
2. `cd frontend && npm run lint && npm run build && npm test` in that order: lint clean,
   build clean, 209 baseline plus the new tests.
3. `POST /api/accounts/nessie` with a stubbed sandbox returns `source: "nessie"`, one
   write per modelled row plus customer and account, every read-back amount equal to the
   written whole-dollar amount, an empty `not_round_tripped` on a faithful sandbox, and
   the response splits into a valid `CandidatesRequest` and `SolveRequest` with no 422.
3a. With a stub that drops a row, changes an amount, returns a row without a date or with
   a bad date, or a row outside the window, each lands in `not_round_tripped` once with
   its reason and the call still succeeds.
3b. Posting to `/api/chat` with `account_source` `nessie` or `modelled` sends Gemini an
   instruction containing the demo-data line; `preset` and an omitted field do not.
4. Without a key: 503, JSON detail, no network call, in both modes. On an empty
   read-back, or one that normalises to nothing: 503, never an empty account, in both
   modes. On an upstream failure mid-seed, a non-JSON body, or a malformed row: 502, key
   absent from the detail even when the upstream message contained it.
5. With a dist directory present the route answers 200 or 503, never 405.
6. The live opt-in test (`-m nessie`) run once by hand: customer id, account id and row
   count recorded below.
7. In the browser: the sandbox button yields a provenance line naming Nessie and a solved
   plan; the $200.00 preset restores the built-in account; a preset chosen mid-load
   re-enables both buttons; with the backend stopped both buttons say the server could
   not be reached and the presets still solve. Screenshots recorded below.
8. No new user-facing string contains "guarantee", "infeasible" or "real bank".
9. A stale load or a stale server solve for a previous account never lands on screen; the
   chat panel resets on account change.

## Regression

Any of: the golden hash moves; any canary moves; either suite drops below its baseline
count; the bundle scan fails; the `/api/solve`, `/api/candidates`, `/api/chat` or
`/api/accounts/sample` contracts change.

## Docs this change edits

- `docs/features/nessie.md` — status flips; whole dollars, withdrawals, read-only mode and
  the nickname, `not_round_tripped`, redaction.
- `docs/features/accounts.md` — Nessie section rewritten from "not wired" to the route.
- `docs/features/frontend.md` — the account-source control, the provenance line, the
  reducer.
- `docs/features/chat.md` — `account_source` and the provenance line.
- `docs/api-contract.md` — `POST /api/accounts/nessie`, additive.
- `README.md` — endpoint list, `NESSIE_ACCOUNT_ID`.
- `docs/demo-script.md` — the bank beat rewritten to what is true; Peraton Q&A.
- `docs/prize-strategy.md` — Peraton row moves to "enter", the paragraph, the Devpost
  text block.
- `docs/nessie-agent-brief.md` — a dated note pointing at the measured corrections.
- `.env.example` — `NESSIE_ACCOUNT_ID`, optional; the stale timeout comment fixed.

## Defect register (carried forward from the synthetic-accounts spec)

- **D-F** (lock naming an evicted candidate → 422 on the whole solve): not fixed here;
  avoided by D7, which clears locks and unmounts old rows on every load. Still open for
  the slider path.
- **D-G** (dead perf guard): open, out of scope.

## Results (recorded at commit)

Commits: `aa5856a` (backend round trip), `1b8b47a` (chat provenance), `494b4df`
(frontend account sources), `a0764c8` (docs), `594467f` (the load-token fix).

### Gates

- `.venv/bin/pytest backend/ -q -m "not perf"` → **2071 passed, 2 skipped, 8
  deselected**, ~26 s. Baseline was 2002/1/8, so **69 new tests**. The second
  skip is the new live Nessie probe.
- `cd frontend && npm run lint && npm run build && npm test` → lint clean, build
  clean, **241 passed**. Baseline 209, so **32 new**. Bundle 639,989 bytes.
- `.venv/bin/pytest backend/tests/test_accounts_golden.py -q` → 3 passed; golden
  hash `8d4ddf30…81048` **unmoved**.
- Canaries unmoved, checked on screen: `clears` tier 1, three changes, "Tightest
  day is Sep 24 at $26.74"; `tight` tier 2, "$6.74, under the $100.00 cushion";
  `gap` tier 3.

### The live sandbox (acceptance 6)

`.venv/bin/pytest backend/tests/test_nessie_roundtrip.py -q -m nessie -s`:

```
customer=15a2118e-7da4-4699-bfd9-3c4bceadc0fa
account=88720fe7-9487-46cf-a443-d6a6fbb19f62
written=24 returned=24 lost=[]
```

**Withdrawals exist.** That was the one design risk the plan could not retire
without running it: the web reference has no purchase create path, and the plan
said execution would stop and report if the sandbox refused withdrawals. It did
not. All 24 rows round-tripped with nothing lost.

### The browser (acceptance 7 and 9)

Against this worktree's backend on 8000 serving its own `frontend/dist`, which
is the production path (one origin) rather than the Vite proxy.

- Sandbox button → `Capital One sandbox, 23 of 23 rows read back, Sep 19 to Oct
  18.`, the account re-solved to tier 3, "You need $12.00 more by Sep 20".
- Modelled button → `Modelled account, seed 1758986161, Sep 19 to Oct 18.`,
  opening $110.39, cents intact (only the sandbox path rounds).
- `$200.00` preset → built-in account and its canary restored, sandbox button
  no longer pressed.
- Preset clicked mid-load → both buttons re-enabled immediately, and the
  in-flight load did **not** overwrite the preset when it returned.
- Backend stopped → "Could not reach the server." under the buttons, both
  buttons enabled, the loaded account still solving, and `$200.00` still
  restoring and solving the built-in account on the local solver.

### One defect found by the browser, not by the suite

Fixed in `594467f`. After any preset, both account buttons spun forever and
stayed disabled until a page reload. The component and the reducer each kept
their own sequence counter; the reducer bumped its own on preset as well as on
start, so one preset put them permanently out of step and every subsequent
result was discarded as stale — including the one that stops the spinner.

The reducer was correct in isolation and wrong in composition, which is exactly
what its unit tests could not see: each case invented its own self-consistent
numbers. They now drive it through a harness that models the component's real
usage, and the two regression cases fail against the old reducer.

Worth recording as a class, not an incident: a test that supplies both sides of
a protocol will pass whether or not the two sides agree.

### Deviations from the plan

- The plan scoped the new wording scan over `roundtrip.py` **and**
  `chat/prompt.py`. The prompt module names both banned words on purpose — it
  is the instruction telling the model never to use them — so the scan covers
  `roundtrip.py`, and the account-source lines are asserted in `test_chat.py`
  where they are built.
- `docs/features/chat.md` was listed conditional in P2 and was edited: D12
  shipped, so it had to be.
- Read-only mode's `not_round_tripped` gained `outside the window` alongside
  `no usable date`, which the plan had already anticipated in the reason list.

### Still open

- **D-F** and **D-G** remain open, as scoped. D-F is unreachable from the
  account-loading path (locks are cleared on every load) but still live on the
  slider path.
- The sandbox seeds are permanent. `NESSIE_ACCOUNT_ID` is implemented and
  **not yet set anywhere**: seeding once and setting it on the box is a
  judging-morning step, not a code step.
- This branch is **not merged**. It waits on the firewall, the public deploy
  checks, and the security branch, in that order.

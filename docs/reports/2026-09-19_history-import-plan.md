# Plan — history import, recurring detection, assumed everyday spending

2026-09-19. Branch `history-import`, worktree
`/Users/nathanstough/Desktop/vthacks-history-import`, base `main` at `21bd4fe`.
Run spec: `docs/specs/2026-09-19_history-import.md` (D1–D12, A1–A15). Line
numbers below are from that base and were read on this branch.

Three exploration passes (architecture, file impact, risk) fed this plan. The
decisions they changed are marked **(R)**.

## Design refinements adopted from the risk pass

- **(R1) Raw payee text never leaves the import endpoint's process.** Detected
  rows are emitted with a *normalised label* (category or kind plus cadence,
  e.g. `Streaming subscription (monthly)`, `Income (weekly)`), never the bank
  string. Candidate generation runs internally on the raw rows (the lexicon
  needs them), then every `Candidate.detail` is rewritten to the normalised
  label before the response is built. The browser, which already holds the raw
  rows, labels the untick list locally from `source_row_indexes`; that label is
  display only and never enters a `SolveRequest`. A2 becomes "no raw
  description appears anywhere in the response JSON", testable by construction.
- **(R2) D7 is a filter, not a side effect of the lexicon.** The endpoint builds
  the `CandidatesRequest` from detected rows only and passes `limit=18`
  explicitly. A7's counterfactual removes that filter.
- **(R3) Rounding rule for both means:** `int((Decimal(total) / n).quantize(1,
  ROUND_HALF_EVEN))`, integer cents in and out. Trimmed mean of the last eight
  amounts drops the single highest and lowest when at least five remain,
  otherwise plain mean.
- **(R4) Request size is capped server-side too:** an ASGI middleware refuses a
  `Content-Length` above 5 MB on `/api/accounts/import` with 413 before the body
  is read, and the Caddyfile gets `request_body { max_size 5MB }`.
- **(R5) 422 bodies do not echo descriptions.** A `RequestValidationError`
  handler scoped to `/api/accounts/import` keeps `{type, loc, msg}` and replaces
  `input` with its type name.
- **(R6) The qualifier clause is composed in the frontend**, appended to
  `res.qualifier` when the loaded account is an import with assumed rows, so it
  applies to both the server and the built-in solver. `wording.py` is untouched.
- **(R7) Untick is a server round trip**: the browser re-posts the same rows
  with `excluded_stream_ids`; the server recomputes deterministically; the
  client adopts the result through the same `adopt()` path presets use, which
  resets locks and so cannot 422 on a stale lock (the D-F class).
- **(R8) Import fails closed offline** before `solveViaApi` is reached; the
  built-in solver still serves presets and, after a successful import, re-solves
  of slider moves.
- **(R9) Projected dates are never before `as_of`** (the solver would silently
  ignore them, not reject them) and never on a weekend (previous business day).
- **(R10) `.gitignore` gains `*.csv`.** All CSV fixtures are inline strings.

## Ordered steps

### Step 0. Lane checks and dev entries

- `git branch --show-current` → `history-import`; `pwd` → the worktree above.
- Append to `.claude/launch.json` two entries: `frontend-history` on port 5176
  and `backend-history` on port 8002 (5176 and 8002 are free across all
  worktrees; 5173/5174/5175/8000/8001 are taken).
- `.gitignore`: add `*.csv` after the `Checking.csv` line.
- `Caddyfile`: inside the site block, before `reverse_proxy`, add
  `request_body { max_size 5MB }` with a two-line comment naming the import
  route as the reason.

### Step 1. Backend schemas — `backend/app/schemas.py`

Insert after `NessieAccountResponse` (ends line 451). All subclass `Strict`
(lines 60–61); reuse `Id`, `Cents`, `NonNegCents`, `iso()` (47–57),
`check_horizon()` (129–143), `check_unique_txn_ids()` (146–150).

```python
class ImportRow(Strict):
    date: StrictStr            # iso() validated
    description: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    amount_cents: Cents        # signed, never zero (validator)

class ImportRequest(Strict):
    rows: list[ImportRow] = Field(min_length=1, max_length=MAX_IMPORT_ROWS)  # 20_000
    as_of: StrictStr | None = None          # default: today (server clock, UTC date)
    horizon_days: Annotated[StrictInt, Field(ge=14, le=45)] = 30   # same bound and reason as SampleAccountRequest
    opening_balance_cents: Cents            # required: exports carry no balance
    buffer_cents: NonNegCents = 2500
    excluded_stream_ids: list[Id] = Field(default_factory=list, max_length=64)

Cadence = Literal["weekly", "biweekly", "semimonthly", "monthly"]

class Stream(Strict):
    id: Id                                  # s_<n>
    kind: Literal["income", "bill"]
    label: StrictStr                        # normalised, no raw text
    category: StrictStr                     # lexicon category or "unknown"
    cadence: Cadence
    anchor: StrictStr                       # dominant weekday name or day-of-month as text
    amount_cents: Cents                     # trimmed mean, signed
    occurrences: Annotated[StrictInt, Field(ge=3)]
    last_seen: StrictStr
    source_row_indexes: list[Annotated[StrictInt, Field(ge=0)]]   # indexes into request.rows
    projected_ids: list[Id]                 # t_ ids emitted for it
    excluded: bool

class ImportProvenance(Strict):
    history_start: StrictStr
    history_end: StrictStr
    history_days: StrictInt
    imputed_zero_days: StrictInt
    weeks_used_for_assumed: StrictInt | None   # 8, or None when < 56 days
    assumed_method: Literal["same_weekday_8_week_mean"] | None
    assumed_ids: list[Id]
    next_payday: StrictStr | None
    pay_cadence: Cadence | None
    stale_days: StrictInt                   # 0 when not stale
    unscheduled_inflow_count: StrictInt
    unscheduled_inflow_cents: NonNegCents
    truncated_assumed_rows: StrictInt
    rejected_rows: list[RejectedRow]        # {index, reason} closed Literal

class ImportAccountResponse(Strict):
    as_of: StrictStr
    horizon_end: StrictStr
    opening_balance_cents: Cents
    buffer_cents: NonNegCents
    scheduled: list[ScheduledTxn] = Field(max_length=MAX_SCHED)
    candidates: list[Candidate] = Field(max_length=MAX_N)
    meta: CandidatesMeta                    # reuse the /api/candidates meta model
    source: Literal["import"]
    streams: list[Stream]
    provenance: ImportProvenance
```

Validators: `ImportRow.date` through `iso()`; `amount_cents != 0`; rows must
be non-decreasing in date? **No** — exports are often newest-first; the server
sorts. Duplicate rows are legal (two coffees). `ImportRequest.as_of` through
`iso()` when given. `RejectedRow.reason` is
`Literal["before_history_window", "zero_amount"]` (parsing rejections happen
in the browser; the server sees valid rows).

`ChatRequest.account_source` (`backend/app/chat/schemas.py:30`) gains
`"import"`; `ACCOUNT_SOURCE` in `backend/app/chat/prompt.py` (dict ending
~113) gains an `"import"` sentence: "The account was imported from the person's
own bank export. Rows whose description begins 'Everyday spending (assumed'
are assumptions from their last eight weeks, not transactions."

### Step 2. Backend package `backend/app/history/`

Stdlib only (`datetime`, `decimal`, `statistics`, `collections`), so
`test_requirements.py` needs nothing.

- `calendar.py`: `is_weekend(d)`, `previous_business_day(d)`,
  `add_months_clamped(d, n, day_of_month)`, `weekday_name(d)`. Pure, tested.
- `money.py`: `mean_cents(values: list[int]) -> int` and
  `trimmed_mean_cents(values)` per (R3).
- `payee.py`: `payee_key(description) -> str`: reuse
  `app.candidates.lexicon.normalise`, then strip digits, `#`, `*`, and
  trailing tokens that are all digits or one character; keep the first three
  tokens. Documented as a heuristic.
- `detect.py`: `detect_streams(rows, history_end) -> tuple[list[Stream],
  list[int]]` (streams, unscheduled inflow row indexes). Algorithm, pinned:
  1. Sort rows by date; group by `(sign, payee_key)`.
  2. Within a group, split amounts into clusters when they are bimodal: two
     clusters each with ≥3 rows whose members are within 15% of their cluster
     median; otherwise one cluster.
  3. For each cluster with ≥3 rows: collapse same-day rows (sum) and note
     `multi_per_day` if any day had more than one.
  4. Gaps between consecutive dates. Fit cadences: weekly (gap 6–8),
     biweekly (13–16), semimonthly (13–18 alternating so that the day-of-month
     set is two values within ±3 of each other's complements, or 1/15 pattern),
     monthly (27–34). A cadence fits when ≥75% of gaps are inside its band and
     no gap exceeds 2.5 intervals. Choose the tightest fitting cadence.
  5. Amount CV over the last eight: income ≤ 0.5, bill ≤ 0.15. Over the bound,
     or `multi_per_day`, or no cadence fits: income → unscheduled inflow;
     outflow → stays in the residual.
  6. Lapsed when `history_end - last_seen > 2 * interval_days`.
  7. Anchor: weekly/biweekly → most frequent weekday; monthly/semimonthly →
     most frequent day(s) of month.
  8. Stream ids `s_001…` in order of first occurrence. Deterministic.
- `project.py`: `project(stream, as_of, horizon_end) -> list[ScheduledTxn]`.
  Weekly/biweekly: start from `last_seen`, step the interval until ≥ `as_of`,
  snap to anchor weekday, previous business day if weekend (Sat/Sun only occur
  when anchor is such; keep), stop at `horizon_end`. Monthly/semimonthly:
  clamp day-of-month, previous business day if weekend, skip if before
  `as_of`. Ids `t_<stream>_<n>`, description = normalised label, `kind` from
  stream, `recurring: true`, amount = stream amount.
- `residual.py`: `residual_series(rows, stream_row_indexes, history_start,
  history_end) -> dict[date, int]` (every day present, zeros imputed;
  outflows as positive cents), `imputed_zero_days`, and
  `assumed_rows(series, as_of, horizon_end) -> list[ScheduledTxn]` using the
  56 days ending `history_end`: for each horizon day, the same-weekday mean of
  the 8 matching days (R3), emitted only when > 0, id `f_<yyyymmdd>`,
  description `Everyday spending (assumed from your last 8 weeks)`,
  `kind: discretionary`, `recurring: false`, negative amount.
- `labels.py`: `label_for(kind, category, cadence)`; categories from the
  lexicon get their display name (`app.candidates.policy` has the category
  table), unknown → `Recurring bill`/`Income`.
- `__init__.py`: `import_account(req: ImportRequest, today: date) -> dict`:
  sort/validate rows → `history_start/end` → reject rows dated after `as_of`
  (reason `before_history_window` is for rows before an `as_of`-relative cap
  of 3 years; keep both reasons) → detect → apply `excluded_stream_ids` →
  project → residual → assumed → truncate assumed rows first if
  `len(scheduled) > MAX_SCHED` → build `CandidatesRequest(scheduled=detected
  only, limit=18)` with raw descriptions → `generate()` → rewrite every
  `Candidate.detail` to the stream label → provenance → dict.

### Step 3. Route and guards — `backend/app/main.py`

- Import block (29–37): add `ImportAccountResponse, ImportRequest`.
- After the nessie route (ends 214) and before the mount (220):

```python
@app.post("/api/accounts/import", response_model=ImportAccountResponse)
def api_import_account(req: ImportRequest) -> ImportAccountResponse:
    return ImportAccountResponse.model_validate(import_account(req, date.today()))
```
- Body cap middleware (R4) registered in `create_app` after CORS: pure ASGI,
  path-scoped, 413 JSON `{"detail": "…"}`.
- Validation handler (R5): `@app.exception_handler(RequestValidationError)`
  that, when `request.url.path == "/api/accounts/import"`, returns 422 with
  `input` replaced by `type(input).__name__`; other paths keep FastAPI's
  default body so `test_api.py:50-58` is unchanged.

### Step 4. Backend tests

New files under `backend/tests/`, each mapped to acceptance criteria:

- `fixtures/histories.py`: `history(seed, months=24, streams=[...])` writes a
  synthetic export as rows (and as CSV text for the golden), with named stream
  shapes: `rent_monthly`, `pay_weekly_wobble(cv=0.35)`, `pay_biweekly_ended`,
  `pay_semimonthly`, `sub_drift`, `two_subs_same_merchant`, `peer_transfers`,
  `two_occurrences`, `weekend_shifting_bill`. Own RNG; does not touch
  `profiles.window()`.
- `test_history_calendar.py`: weekend, previous business day, month clamp
  (Jan 31 + 1 month → Feb 28/29), year boundary. (A8)
- `test_history_money.py`: half-even on ties, trimmed mean drops one each
  side only at n ≥ 5, integer in/out, `19.99`-class inputs never appear. (R3)
- `test_history_detect.py`: one test per A3 row, each with a counterfactual
  where the spec names a guard (min occurrences, lapsed, CV bound, peer
  transfer). Keyword-free income detected; a keyword-only classifier finds
  nothing on the same fixture. Determinism (A13). `assert len(streams) > 0`
  inside every loop-based test (vacuous-loop class).
- `test_history_project.py`: cadence projection across month/year
  boundaries, never before `as_of`, never on a weekend, `next_payday` when
  `as_of` is a payday. (A8, R9)
- `test_history_residual.py`: A4 exact sum over 300 histories (with a
  non-trivial assertion count), A5 hand-computed weekday mean, < 56 days →
  bills only with `assumed_method None`, 30-day horizon → rows inside the
  window only.
- `test_history_api.py`: A6 (422 shapes, hostile sweep cloned from
  `test_api.py:57-70`, never 500), A7 (every candidate targets a detected id;
  counterfactual by monkeypatching the filter off), A9 (`MAX_SCHED` overflow
  truncates assumed first), 413 on oversized `Content-Length`, `stale_days`,
  `excluded_stream_ids` round trip, round trip through `/api/solve` returns a
  tier, response validates as `SolveRequest` fields.
- `test_history_privacy.py`: A2 — no raw description substring in the
  serialised response; log capture during import and during a 422 shows no
  raw description; 422 `input` is a type name. Chat: `render_context` with an
  import request names assumptions; `ChatRequest` accepts
  `account_source="import"`.
- `test_history_wording.py`: import-specific banned list `("infeasib",
  "guarantee", "predict", "forecast")` over every string in the response and
  the labels table. (A11, risk 4)
- `test_history_golden.py`: pinned SHA-256 of the generator's two-year CSV
  text; import → solve pins tier, change count, stream count, cadence and
  next payday. (A12)
- `tools/import_local.py` (not a test): reads `SAFE_TO_SPEND_CSV` env var
  (no default), parses with the same rules as the browser (a Python twin of
  Step 5's parser, kept minimal), posts to a `TestClient(create_app(None))`,
  prints aggregates only. (A15)

### Step 5. Frontend parsing and adapters

- `frontend/src/lib/importCsv.ts`: `parseBankCsv(text) -> {rows, rejected,
  excluded_non_posted, total}`; RFC-4180 quotes, header any order/case,
  `DATE`/`DESCRIPTION`/`AMOUNT` required, optional `STATUS`; amount grammar by
  string arithmetic (`$`, `,`, parentheses negative, two-digit fraction
  padded/truncated with a rejection when more than 2 decimals), dates
  `MM/DD/YYYY`, `M/D/YY`, `YYYY-MM-DD` via `Date.UTC` as `mockSolver.ts:27`
  does; > 20,000 rows → refuse. Every rejection carries `{line, reason}`.
- `frontend/src/lib/history.ts`: `buildImportRequest(rows, opening, buffer,
  horizonDays, excluded)`, `toBase(response) -> SolveRequest`,
  `streamLabel(stream, rows)` (local label from `source_row_indexes`),
  `qualifierSuffix(account)`, `isImport()`.
- `frontend/src/lib/accounts.ts`: widen `parseAccount` (53–61) to accept
  `'import'`; `provenanceLine` (106–125) new arm: "N detected streams,
  everyday spending assumed from 8 weeks of history, same-weekday average; K
  quiet days counted as zero"; `chatKey` (132–135) arm; `LoadKind` in
  `accountState.ts:11` gains `'import'`; `loadAccount` unchanged, a sibling
  `loadImport(req, signal)` added.
- `frontend/src/types.ts`: `ImportRow`, `Stream`, `ImportProvenance`,
  `ImportAccountResponse`; union at 181 gains it; `account_source` literal
  gains `'import'` where the chat request is built (`lib/chat.ts`).

### Step 6. Frontend UI — one hunk in `App.tsx` plus one component

- `frontend/src/components/ProvenancePanel.tsx`: card in the `.wallet-panel`
  style (`index.css:665-682`), sections: streams with untick checkboxes
  (income first, cadence and next date in words), assumed-spending line with
  method and weeks, imputed zero days, stale badge, unscheduled inflows
  count, truncation note. Emits `onToggleStream(id)`.
- `App.tsx`:
  - imports (1–19): `ProvenancePanel`, `parseBankCsv`, `buildImportRequest`,
    `loadImport`, `qualifierSuffix`, `isImport`.
  - state: `importRows` (parsed rows kept in memory for labels and re-posts),
    `excludedStreams: Set<string>`, `openingPrompt` state for the balance
    field.
  - a third control in the `ctl-sources` group (322–339): a `<label>` wrapping
    a hidden `<input type="file" accept=".csv,text/csv">` styled as the other
    buttons, plus a small numeric "Today's balance" input revealed after a
    file is chosen; disabled while `loading !== null`. Label text "Import a
    bank export". `bundle.test.ts:52` keeps "Capital One sandbox" untouched.
  - `loadFromImport(rows, opening, excluded)`: mirrors `load()` (212–228):
    `loadCtl.current?.abort()`, new controller, `seqRef` bump, `dispatch(start(
    'import'))`, `await loadImport(...)`, stale check, `adopt(base, opening,
    buffer)`, `dispatch(succeed(...))`; on network failure `dispatch(fail(...,
    "Import needs the server. Presets still work offline."))`.
  - mount `<ProvenancePanel …/>` after the chart section closes (395) and
    before the plan section (397), only when `isImport(acct.account)`.
  - qualifier: where `res.qualifier` is rendered, append
    `qualifierSuffix(acct.account)` when non-empty.
- `PrescriptionList.tsx`: unchanged; A10's "assumed rows never carry the
  checkbox" holds because they are never candidates (R2), and a frontend test
  pins that no `f_` id appears in `req.candidates` targets.

### Step 7. Frontend tests (flat files in `frontend/tests/`)

- `import-csv.test.ts`: A1 grid (formats, header order/case, quotes, pending
  excluded, duplicates kept, empty/header-only/one row, 20,001 rows refused,
  200 random decimals string-exact, `19.99 → 1999`).
- `history.test.ts`: request builder, local labels, qualifier suffix only
  when assumed ids exist, `toBase` round trip, no raw description in the
  built `SolveRequest` or chat request (A2), lock reset on adopt.
- `account-state.test.ts`: extend with `'import'` kind and the stale-token
  rejection (A10).
- `provenance-panel.test.ts`: the panel's view-model function (kept in
  `history.ts` so it is testable without a DOM): lines and badges from a
  response.
- `bundle.test.ts`: unchanged; still runs.

### Step 8. Docs and contract

- `docs/api-contract.md`: append `## POST /api/accounts/import` after line
  356: request, response, the privacy rule (no raw description returns), the
  D7 exemption, `excluded_stream_ids`, 413, 422 shape note.
- `docs/features/candidates.md`: under "Rules the solver relies on" (91), a
  paragraph: assumed rows are excluded from generation by the import endpoint.
- `docs/features/frontend.md`: under "Account sources" (34), the import
  control, offline behaviour, the provenance panel; under "The override
  model" (58), stream unticks as a server round trip.
- `README.md`: layout bullet for `backend/app/history/`, routes line (9–11).
- `docs/features/history-import.md`: status flips to "built" with the
  results; limits section kept.
- `docs/specs/2026-09-19_history-import.md`: results section filled.
- `docs/demo-script.md`: conditional; add the import beat only if the local
  run is clean.

### Step 9. Verification order

1. `.venv/bin/pytest backend/tests/test_history_*.py -q` until green.
2. `.venv/bin/pytest backend/ -q -m "not perf"` → expect 2150 + new; canaries
   unmoved; generator golden hash unmoved.
3. `cd frontend && npm run lint && npm run build && npm test` → 253 + new.
4. Start `backend-history` (8002) and `frontend-history` (5176) via the
   preview tool; import the golden CSV in the browser; screenshot the panel;
   check console for errors; untick a stream and confirm one re-solve.
5. `SAFE_TO_SPEND_CSV=~/Downloads/Checking-2.csv .venv/bin/python
   backend/tools/import_local.py` → record aggregates in the run spec; Nathan
   confirms the named next payday by eye.
6. Doc-sync sweep, commit with explicit paths, Claude critique loop, Codex
   audit.

## Risks and mitigations (from the risk pass, with owners in this plan)

| Risk | Sev | Mitigation |
|---|---|---|
| Assumed rows offered as skip candidates | high | R2 filter + A7 counterfactual |
| Raw payee text in solve/chat/422 bodies | high | R1 labels + R5 handler + privacy tests |
| Float cents in CSV parse or means | high | string arithmetic; R3 rule; tests |
| Offline re-solve exceeds mockSolver's 20 | med | `limit=18`; test with 4 weekly discretionary streams degrades, not throws |
| Stale import after preset click | med | same `loadCtl`/`seqRef`/`adopt` triad; A10 test |
| Unbounded request body | med | R4 middleware + Caddy cap |
| "predict"/"forecast" not machine-banned | med | import wording test |
| Pre-`as_of` rows silently ignored | low | R9 + projection test |
| Detection O(n²) | low | group by payee key first |
| CSV committed by accident | low | `*.csv` ignored; inline fixtures |

## Out of scope, restated

Ensemble endpoint and NumPy runtime; evaluation of the 21 research
checkpoints on Nathan's account; any learned model in the schedule; storage;
Plaid; deployment.

## Amendments after the critique pass (supersede the text above where they conflict)

Verified against the tree by the critique agent; each item names the step it changes.

**Wording**
- C1 (Step 6). `res.qualifier` is rendered in `frontend/src/components/VerdictBand.tsx:27`, not in `App.tsx`. Add a `note?: string` prop to `VerdictBand`, rendered as its own `<p>` after the qualifier; `App.tsx` passes `qualifierSuffix(acct.account)`. D11 becomes "one hunk in `App.tsx` plus one prop on `VerdictBand`".
- C2 (Step 5/6, D10). The suffix is a standalone sentence, because tiers 2 and 3 do not end in "Sufficient under the schedule shown." (`wording.py:169-210`, `mockSolver.ts:375-397`): **"Everyday spending here is an assumption from your last eight weeks, not scheduled charges."** `history.test.ts` asserts the composed text against all three tiers of `mockSolver` output. `test_history_wording.py` keeps the backend-side banned-word scan over labels and provenance strings.

**Detection (Step 2 `detect.py`), each with a named test in `test_history_detect.py`**
- C3 Semimonthly is decided by day-of-month dispersion, not gap bands: two DOM modes covering ≥ 80% of occurrences (with month-end days 28–31 folded into one "EOM" mode) ⇒ semimonthly, projected on both anchors. Biweekly requires a single dominant weekday and DOM spread. Test: a 15th/EOM stream is `semimonthly`; a true biweekly Friday stream is `biweekly`.
- C4 Anchor (weekday or DOM) is taken from the **last eight** occurrences, like the amount. Test: 60 Tuesdays then 10 Thursdays ⇒ Thursday, first projected date a Thursday.
- C5 Cadence fit uses the median gap and the in-band fraction (≥ 75%); the hard "no gap > 2.5 intervals" rule is dropped. Lapsed: `> 3 × interval` for income, `> 2 × interval` for bills. Test: weekly income with two skipped weeks mid-history and one at the end is detected, projected, and names the next payday.
- C6 Bimodal split pinned: sort amounts, split at the largest relative gap, accept when both sides have ≥ 3 members within 15% of their median, ties to the lower value. DOM mode ties break to the larger day. CV = population stdev / |mean| over the last eight. Test: a bill on the 1st always pulled to the previous business day projects on the 1st's business day, never the 29th.
- C7 Rows of **every** detected stream, active or lapsed, are removed from the residual. Test: a monthly bill that stopped 40 days before `history_end` does not inflate `assumed_rows`.

**Projection (Step 2 `project.py`)**
- C8 Order is snap-to-anchor first, then step by the interval, then clip to `[as_of, horizon_end]`. Test: a biweekly stream whose `last_seen` weekday differs from the anchor yields the expected number of paydays in a 30-day window.
- C9 Weekend rule by kind: income moves to the **next** business day, bills to the **previous**. Cash never appears early. Test for each.
- C10 Module named `workdays.py`, not `calendar.py` (it needs `calendar.monthrange`).

**Assumed spending (Step 2 `residual.py`, D6, A5)**
- C11 The per-weekday statistic is the **median** of the eight matching days (even count ⇒ mean of the middle two, half-even to cents), so one $900 laptop does not become $112 every Tuesday. Test: one injected outlier moves the assumed amount for that weekday by at most the median's step; hand computation in A5 updated.

**Contract and error paths (Steps 1, 3, 4)**
- C12 A6 amended: out-of-order rows are sorted and duplicates kept (two coffees); a 422 is required for nonfinite or non-integer amounts, booleans, zero amounts, negative counts, unknown fields, and any date failing `iso()`.
- C13 If detected rows alone exceed `MAX_SCHED` after assumed rows are gone, the endpoint answers 422 with a plain message; test alongside A9. No path may reach `model_validate` with an oversized list.
- C14 R5 handler strips **both** `input` and `ctx` on `/api/accounts/import` and builds other paths' bodies with `jsonable_encoder(exc.errors())` so they stay byte-identical to today (a `ctx.error` is a `ValueError` object and a naive `JSONResponse` 500s). Tests: `missing` on a nested row, `too_long` at 20,001 rows, `model_attributes_type` on a raw string row, invalid JSON body; and the unchanged body on `/api/solve`.
- C15 The single source of truth for labels is one dict `{txn_id: label}` built before candidate generation; an assertion that the raw and labelled id sets are equal guards the rewrite. A2's privacy tests use high-entropy descriptions (`ZZQ7K4-<n>`) so a substring check cannot pass vacuously. `parseBankCsv` rejections carry `{line, reason}` and never the cell text.
- C16 Labels: `app/history/labels.py` carries `CATEGORY_DISPLAY: dict[str, str]` for every lexicon category with an import-time completeness check over `lexicon.PRIORITY` (the lexicon's own `display` is a brand and is `None` for every protected bill category). `payee_key` = `" ".join(normalise(desc)[:3])` after dropping all-digit and single-character tokens (`normalise` returns a tuple).

**Frontend (Steps 5–7)**
- C17 New arms in `provenanceLine` and `chatKey` go **before** the early returns at `accounts.ts:109` and `:132-135`, or an import renders "seed undefined". `AccountSource` at `types.ts:6` gains `'import'`.
- C18 Untick is **client-side** (adopting the critique's cut): drop the stream's `projected_ids` from `base.scheduled` and every candidate whose `target_txn_id` is one of them, then re-solve through the normal path. `excluded_stream_ids` is removed from the request schema. The panel states that unticking clears "Can't do this" selections, because the rebuilt request goes through `adopt()`.
- C19 A10's logic is exposed as pure functions in `lib/history.ts` and tested there: `scheduleAfterUntick(base, stream)`, `ticksAfterReimport()`, `checkboxableIds(candidates)` (asserts no `f_` target). Render-level behaviour is verified by the Step 9.4 browser pass and screenshot, and the run spec says so.
- C20 "Re-solves once" is defined as: one untick produces exactly one new `SolveRequest` from the pure function; the debounced solve effect is unchanged.

**Scope cuts adopted**
- C21 R4 is dropped: no ASGI body-cap middleware and no Caddyfile change tonight. `rows` keeps `max_length=20_000`. Recorded as a limitation in the feature spec.
- C22 A12 keeps the aggregate pins (tier, change count, stream count, cadence, next payday) and drops the SHA-256 pin of the CSV text.
- C23 If C3 is not green by a fixed hour, semimonthly is cut from A3 and the doc says so, rather than shipping a classifier that reports biweekly for it.

**Verification**
- C24 Step 9.2 is `.venv/bin/pytest backend/ -q` (the `addopts` already deselect `perf` and the live Nessie probe; a command-line `-m` would override them and put the suite on the network).
- C25 Line corrections: `NessieAccountResponse` starts at `schemas.py:430`; `ChatRequest.account_source` is `chat/schemas.py:35`; the "Capital One sandbox" grep is `bundle.test.ts:53`; the new route is registered inside `create_app` (`main.py:98-224`).

## Amendments after the Codex review (supersede earlier text where they conflict)

Review: `docs/reports/2026-09-19_history-import-plan-review.md`. Each item names
the Codex finding it resolves.

- X1 (finding 1, Step 5/6, C18). Untick goes through the reducer, not `adopt()`
  alone. `accountState.ts` gains an action `streams(selected: Set<string>)`;
  the state keeps `original: ImportAccountResponse` and rebuilds `base` from it
  (drop deselected streams' `projected_ids` and the candidates targeting them),
  preserving the current opening balance and buffer. Re-checking a stream
  restores its rows. Tests: untick, recheck, multiple toggles, through the
  reducer; `App.tsx` dispatches and lets the existing solve effect run.
- X2 (finding 2, C3). Semimonthly requires two day-of-month phases separated
  by 10–20 days, each with ≥ 3 occurrences, and both phases present in ≥ 60% of
  calendar months in the stream's span. A weekend-shifted monthly bill (phases
  within ±3 days) fails the separation test and stays monthly. Tests: a
  weekend-shifted monthly bill is `monthly`; 15th/EOM income is `semimonthly`.
- X3 (finding 3, new D13). The balance cutoff: "Today's balance" includes
  everything posted through today. Rows dated after `as_of` are rejected
  (`after_as_of`). Projection starts at `as_of`, except: an income occurrence
  dated `as_of` is **not** projected (if it posted it is in the balance; if it
  has not, counting it is optimistic), and the provenance lists it under
  `income_not_counted_today` so the panel can say "pay expected today is not
  counted until it posts". Bills dated `as_of` are projected unless the export
  already contains that stream's row on `as_of`. Tests: posted-today income in
  the export is not projected; an expected-but-unposted payday on `as_of` is
  not projected and is named; a bill due today with no posted row is projected.
- X4 (finding 4, Step 1). `ImportRow.amount_cents` is bounded to ±10^8 cents
  ($1,000,000), so every derived quantity (same-day sums, trimmed means,
  medians) stays inside `Cents`; aggregates (`unscheduled_inflow_cents`) use
  `NonNegDerivedCents`. Boundary tests at the row cap and at 20,000 rows of the
  cap prove no 500.
- X5 (finding 5, Step 1). Dates are validated to the range 1970-01-01 to
  2100-12-31 for rows and `as_of`; `horizon_days ≤ 45` keeps arithmetic inside
  it. Tests at both boundaries and at `9999-12-31` (422).
- X6 (finding 6, Step 2). Filter first, then compute history bounds.
  `RejectedRow.reason` is `Literal["after_as_of", "older_than_3_years",
  "zero_amount"]`. If nothing survives, the endpoint answers 422 "no usable
  history in the last three years". Tests: all-future, all-too-old, mixed.
- X7 (finding 7, C15). Candidate **labels** are rewritten too. Import builds
  its own labels from `(action, CATEGORY_DISPLAY[category])`, e.g. "Pause the
  streaming subscription for a cycle", never the lexicon brand. Privacy tests
  include ordinary recognised merchants (`NETFLIX.COM`, `PLANET FIT CLUB FEES`)
  as well as high-entropy strings, and assert neither the raw string nor the
  brand appears anywhere in the response JSON.
- X8 (finding 8, Step 1/5/8). `assumed_method` is
  `Literal["same_weekday_8_week_median"]`; the provenance line says
  "same-weekday median"; frontend types, docs and assertions use the same
  string.
- X9 (finding 9, Step 2). Rows carry their original index through sorting,
  filtering, grouping and residual removal (`(index, date, amount, key)`
  tuples). Test: newest-first input with duplicates and rejected rows yields
  `source_row_indexes` that point at the right request rows.
- X10 (finding 10, Step 0/9). `frontend/vite.config.ts` reads
  `VITE_API_TARGET` (default `http://127.0.0.1:8000`); the `frontend-history`
  launch entry sets it to port 8002. Step 9.4 confirms in the network log that
  requests reach 8002.
- X11 (finding 11, Step 5). Date parsing validates by component round trip
  (year, month, day rebuilt and compared), so `02/30/2026` is rejected, not
  rolled into March. Two-digit years: `YY ≥ 70 → 19YY`, else `20YY`. Tests for
  Feb 30, Apr 31, leap day, and both two-digit branches.
- X12 (finding 12, Step 1/2). `Stream` gains `active: bool`; detection sets it
  from the lapsed rule and `project()` skips inactive streams; all streams'
  rows leave the residual regardless. The C7 fixture becomes a monthly bill
  that stopped **75** days before `history_end` (lapsed under the two-interval
  rule) and asserts it is neither projected nor in `assumed_rows`; a second
  fixture at 40 days asserts it is still projected (not lapsed) and still
  removed from the residual.
- X13 (finding 13, Step 5). `chatKey` for an import is `import:<n>` where `n`
  is a client-side counter incremented on every successful adoption, so a new
  CSV starts a new conversation. Test: two successive imports with identical
  dates and stream counts get different keys.

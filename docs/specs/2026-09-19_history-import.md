# Run spec — history import, recurring detection, assumed everyday spending

Date: 2026-09-19 (Sat evening). Branch `history-import`, worktree
`/Users/nathanstough/Desktop/vthacks-history-import`, base `main` at `21bd4fe`.
Plan: `docs/reports/2026-09-19_history-import-plan.md`. Feature spec:
`docs/features/history-import.md`. Frozen after commit.

## Problem

The app can only plan a schedule someone typed. A real user has a bank export
and nothing else. The product must take that export, work out recurring income
and bills itself, assume everyday spending from the person's own past, hand
the exact solver the result, and say on screen where every number came from.
This is also the prerequisite for evaluating any learned forecaster on a real
consented account, which is the second run
(`docs/reports/2026-09-19_three-model-ensemble-plan.md`, not yet written).

Nathan's own export (`~/Downloads/Checking-2.csv`, 1,060 posted rows,
2024-08-19 to 2026-09-18, five columns `DATE, DESCRIPTION, AMOUNT, CHECK #,
STATUS`, signed amounts, no balance column) is the reference shape. It is read
only by a local script, never copied into the repository, and only aggregate
numbers from it appear in this document.

## Decisions

- **D1. Stateless import endpoint.** `POST /api/accounts/import` takes dated,
  signed rows (already parsed by the browser) plus `as_of`, `horizon_days`,
  `opening_balance_cents`, `buffer_cents`. Nothing is stored, nothing is
  logged; descriptions never appear in server logs. The response is a schedule
  in the frozen `SolveRequest` field shapes plus provenance; `/api/solve` and
  `/api/candidates` are unchanged.
- **D2. Quiet days are zero-spend days**, because a bank export is complete for
  its range. The response counts the imputed zero days and the screen states
  the assumption.
- **D3. Recurring detection is deterministic and cadence-based, not
  keyword-based.** Nathan's export never says "PAYROLL". A stream is a payee
  with at least three occurrences, a stable interval (weekly, biweekly,
  semi-monthly, monthly, with jitter), a dominant weekday or day-of-month, and
  amount variability within a per-kind bound (income tolerates hours-based
  variation, bills do not). A stream is *lapsed*, and not projected, when its
  last occurrence is more than **two** intervals before the last exported day
  for a bill and more than **three** for income. Income gets the longer rope
  deliberately: a student who does not work over an exam week has not lost
  their job, and dropping their pay is the expensive error.
- **D4. Projection.** Each active stream is projected across
  `[as_of, horizon_end]` at its cadence, on its dominant weekday, never on a
  weekend, at the trimmed mean of its last eight amounts. `next_payday` is the
  first projected income date on or after `as_of`.
- **D5. Residual by transaction.** Rows belonging to detected streams are
  removed from the history *as rows*; what remains is the observed everyday
  spending series. No subtraction of totals, no clipping.
- **D6. Assumed everyday spending is the same-weekday eight-week median** of the
  residual series (even count: mean of the middle two, half-even to cents), projected per day across the horizon as `discretionary`,
  `recurring: false` rows whose ids start with `f_` and whose description
  starts with `Everyday spending (assumed`. It needs at least 56 history days;
  with fewer, the response says so and carries bills only.
- **D7. Assumed rows are never candidates.** The endpoint generates candidates
  from detected rows only, so no candidate can target an `f_` row. The solver
  plans around assumed spending; it never proposes cancelling it.
- **D8. Peer transfers are not income.** Irregular inflows (no stable cadence,
  or amount CV above the income bound, or several on one day) are reported as
  `unscheduled_inflows` and excluded from the schedule. Money that may not come
  is not planned around.
- **D9. Dates.** History ends at the last exported day; planning starts at
  `as_of` (today). If the gap exceeds seven days the response sets `stale`
  with the day count. The baseline uses the 56 days ending at the last
  exported day.
- **D10. Wording.** When assumed rows are present a standalone sentence follows
  the qualifier on every tier: "Everyday spending here is an assumption from
  your last eight weeks, not scheduled charges." Never "predict", never
  "forecast", never "guaranteed". The explainer's context names assumed rows
  as assumptions.
- **D11. Frontend.** Browser parses the CSV (header any order or case; amount
  formats `-9.99`, `1,234.56`, `$12.00`, `(12.00)`; dates `MM/DD/YYYY`,
  `YYYY-MM-DD`, two-digit year; `STATUS != Posted` excluded and counted).
  One import control beside the presets, one provenance panel below the chart
  in the plan tab, an untick list for detected streams that re-solves. Assumed
  rows carry no "Can't do this" checkbox. One hunk in `App.tsx` plus one prop
  on `VerdictBand`. Unticking a stream is client-side: its projected rows and
  their candidates are dropped and the plan re-solves; it clears "Can't do
  this" selections and the panel says so.
- **D12. Bounds.** More than 20,000 rows refuses in the browser and is a 422 on
  the server. Row amounts are bounded to ±$1,000,000 and dates to 1970–2100 so
  every derived amount and date stays inside the contract's types. If the horizon schedule would exceed `MAX_SCHED`, assumed rows
  are truncated first and the truncation reported; if detected rows alone
  exceed it the answer is a 422, never a 500. No request-body size cap is
  added tonight (recorded limitation).

- **D13. Balance cutoff.** "Today's balance" includes everything posted
  through today. Rows dated after `as_of` are rejected. An income occurrence
  expected on `as_of` is not projected (if it posted it is already in the
  balance; if not, counting it is optimistic) and is named in the provenance so
  the panel can say pay expected today is not counted until it posts. Bills
  due today are projected unless the export already shows them posted today.
- **D14. Labels carry no brand.** Detected rows and their candidates are
  labelled from the lexicon *category* ("streaming subscription"), never the
  merchant brand, so a recognised merchant reveals no more than an unknown one.

## Out of scope

Any learned model in the schedule. Error bars. Storage. The ensemble endpoint,
NumPy runtime, and the evaluation of the 21 research checkpoints on Nathan's
account (second run). Plaid. Renaming infrastructure.

## Acceptance criteria

Every criterion maps to a named test in the plan; the audit grades against
this list.

- A1 Parsing: each amount format above maps to exact integer cents; `19.99` →
  1999; unparseable amounts and dates are reported per row, never zero, never
  dropped silently; non-Posted rows excluded and counted; duplicates kept;
  empty/header-only/one-row files yield "not enough history"; >20,000 rows
  refused client-side.
- A2 Privacy: no raw description and no lexicon brand appears anywhere in the
  import response JSON, tested with recognised merchants and high-entropy
  strings; solve and chat requests built after an import contain none either;
  server log capture during import and during a 422 shows no description.
- A3 Detection: monthly rent, biweekly and weekly pay (with weekday wobble,
  amount CV ≤ 0.5, and up to two skipped weeks), semi-monthly pay on the 15th
  and month end, a payday that moved weekday (anchor from the last eight),
  amount drift, interval jitter, weekend shift (income later, bills earlier),
  two subscriptions at one merchant, two employers, a lapsed bill inside the
  56-day window: each detected, projected, or excluded as specified. Two occurrences, a stopped stream, and peer-transfer
  patterns are not projected; each guard has a counterfactual test that fails
  when the guard is removed. Keyword-free income is detected; keyword-only
  matching finds nothing on the same fixture.
- A4 Residual: detected rows plus residual series equal the original daily
  totals exactly, in cents, on 300 generated histories.
- A5 Baseline: same-weekday eight-week median matches a hand computation and
  one injected $900 outlier moves that weekday's amount by at most one
  median step; fewer
  than 56 days refuses the baseline with a reason and still returns streams;
  a 30-day horizon projects 30 assumed rows, none outside the window.
- A6 Contract: the response schedule validates against the unchanged
  `SolveRequest`; ids unique; a round trip through the real solver returns a
  tier; out-of-order rows are sorted and duplicates kept; the request is a
  422 in the contract's error shape for a missing opening balance and for
  hostile input (nonfinite or non-integer amounts, booleans, zero amounts,
  negative counts, unknown fields, unparseable dates, more than 20,000 rows,
  detected rows alone above `MAX_SCHED`), never a 500; the 422 body carries
  neither `input` nor `ctx` on this route and is unchanged on every other.
- A7 Exemption: over the import output, every generated candidate targets a
  detected row id; removing the exclusion makes the test fail.
- A8 Dates: `stale` set with the day count when the gap exceeds seven days;
  `next_payday` correct across month and year boundaries and when `as_of` is
  a payday; projected dates never on Saturday or Sunday.
- A9 Bounds: `MAX_SCHED` overflow truncates assumed rows first and reports it.
- A10 Frontend, pure-function tests: `scheduleAfterUntick` drops exactly the
  stream's projected rows and their candidates and yields one new request;
  `ticksAfterReimport` is empty; `checkboxableIds` never contains an `f_`
  target; a stale import response is rejected by the load token; the
  provenance view-model renders the response's numbers and the stale badge;
  the qualifier sentence composes correctly on all three tiers. Render-level
  behaviour (offline message, panel, untick click) is verified in the browser
  pass with a screenshot, not by a test; bundle test still clean.
- A11 Wording: the qualifier appears only when assumed rows exist and the
  banned words do not; explainer context names assumptions.
- A12 Golden: a generator-written two-year synthetic export runs import →
  candidates → solve and pins tier, change count, stream count, cadence and
  next payday (aggregate pins; no hash of the CSV text).
- A13 Determinism: detection and baseline produce byte-identical output on a
  second run; `source_row_indexes` point at the right request rows for
  newest-first input with duplicates and rejected rows.
- A16 Balance cutoff (D13): posted-today income is not projected; an expected
  but unposted payday on `as_of` is not projected and is named; a bill due
  today with no posted row is projected.
- A17 Untick through the reducer: deselecting a stream rebuilds the base from
  the original response without its projected rows or their candidates,
  preserving opening balance and buffer; reselecting restores them; the chat
  key changes on every new import.
- A14 Regression: backend gate (2150 passed on `main`) and frontend gate (253)
  stay green; existing canaries unmoved; generator golden hash unmoved.
- A15 Local run: `backend/tools/import_local.py` reads the CSV path from an
  environment variable (no default), prints aggregates only, and its numbers
  (stream count, weeks used, next payday cadence, tier, change count) are
  recorded below.

## Documentation

Committed to: this run spec; `docs/features/history-import.md` (new);
`docs/api-contract.md` (new section); `docs/features/candidates.md` (the
exemption); `docs/features/frontend.md` (control and panel); `README.md`
(layout and routes); `frontend/src/types.ts` (mirror). Conditional, confirm at
execution: `docs/demo-script.md` (a beat only if the local run is clean).

## Results

**Gates.** Backend `.venv/bin/pytest backend/ -q`: **2282 passed, 10
deselected** (2150 before this change). Frontend `npm run lint && npm run
build && npm test`: lint clean, build clean, **304 passed** (253 before).
Existing canaries unmoved; the generator golden hash unmoved.

**Browser pass** (frontend 5176 proxying to backend 8002, the configurable
target added by this change). A 335-row synthetic export imported, planned
and rendered. No image was retained — the pane's screenshots do not reach
disk — so the evidence is the list of assertions below, each read back out of
the live DOM and each re-runnable:

| Checked | Result |
|---|---|
| file parsed in the browser | "335 transactions read" |
| provenance panel | five streams, income first, brand-free labels |
| next payday | "Next pay expected Sep 22, weekly." |
| assumed line | "about $27.33 a day, the median of the same weekday over your last 8 weeks" |
| assumption sentence under the verdict | present |
| untick rent | three changes became "Nothing to change" |
| re-tick rent | back to three changes, assumed rows intact |
| console | no errors |
| privacy line on screen | names server-side grouping, not "stayed in your browser" |
| import with the endpoint unreachable | "Import needs the server. Presets still work offline." |
| after that failure | both account buttons re-enabled |
| preset after that failure | loaded, "Sample checking account" |

**Local run on a real consented export** (`SAFE_TO_SPEND_CSV`, 1,060 rows,
2024-08-19 to 2026-09-18, 761 days):

| | |
|---|---|
| rows read / skipped | 1060 / 0 |
| quiet days counted as zero spend | 421 |
| streams found | 2, both income |
| active | weekly, Tuesday, 35 occurrences |
| stopped | biweekly, Friday, 18 occurrences, correctly not projected |
| next payday | 2026-09-22, weekly |
| assumed rows | 20, same-weekday 8-week median |
| one-off inflows excluded | 165 |
| bills found | **0** |
| tier | 1, 0 changes |

Both income streams are right, including the one that stopped in October
2025. **Zero bills is also right**: every outflow group on that account has an
amount CV between 0.76 and 1.30, so there is nothing recurring with a stable
amount to find. The consequence is recorded as the first limitation in
`docs/features/history-import.md`: an account like that gets no candidates,
so the product can forecast and name a shortfall but cannot prescribe.

**Deviations from the plan.** Six, each with its reason:

- Stream `kind` gained a third value, `discretionary`. A weekly grocery run is
  recurring and worth projecting but is not a bill, and labelling it one
  misdescribes the account. The kind is derived from the lexicon category.
- The bimodal split threshold moved from 0.6 to 0.75, because two
  subscriptions at one merchant at $15.99 and $22.99 sit at a ratio of 0.70
  and were being averaged into one stream.
- Cadence fitting counts a gap as consistent when it is near ANY small whole
  number of intervals, not just one. Under the original rule a weekly income
  with two skipped weeks failed to fit and was dropped as an unscheduled
  inflow — the exact failure C5 was written to prevent, which the original
  wording did not actually prevent.
- `stale` is reported as `stale_days`, the raw gap, always present; the
  seven-day threshold is applied by the client. D9 described a flag. Any
  other consumer must read the number, not treat non-zero as stale, and the
  contract says so.
- R1's browser-side `streamLabel(stream, rows)` was dropped. The server's
  label is already brand-free, so labelling again from the raw rows would add
  a second place for a payee to reach the screen. `source_row_indexes` is
  still returned and tested as provenance, but no client consumes it.
- A minimum of ten usable rows was added, client and server. A one-row file
  previously parsed, planned an empty schedule, and had the solver answer
  "sufficient" over a single transaction. A1 asked for "not enough history"
  on a one-row file and the original implementation did not deliver it.

**`docs/demo-script.md` was deliberately not touched.** The plan made the
import beat conditional on a clean local run. The run was clean but found no
bills on that account, so the demo would show a plan with nothing to change —
weaker than the existing four minutes. The modelled and Nessie beats stand.

**Post-commit audit.** An adversarial Claude critique of `5513a0a` returned
Fail overall on one blocking defect: a daily residual median above the
contract's cents bound produced a 500 on schema-valid input (rows are capped
but a day is the sum of its rows). Fixed by refusing with a 422 in
`app/history/residual.py` and, for symmetry, on the stream amount in
`detect.py`; the auditor's 9,648-row reproducer is now a named 422 and is
pinned by a test. Also fixed from that pass: the missing minimum-history
refusal, a peer-transfer counterfactual, a real counterfactual for the
assumed-row exemption (the previous one stood in for the filter rather than
removing it), the lapsed-bill-inside-the-window residual test, the 300-history
loop varying only the residual, the untested import arms of `provenanceLine`
and `chatKey`, the one-directional label-map assertion, a float in the panel's
per-day figure, dead code, and the shortened offline message.

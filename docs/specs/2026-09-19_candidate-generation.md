# Run spec — candidate generation + `POST /api/candidates`

Created: Sat 2026-09-19 ~04:10 · Branch: `backend` · Pipeline: `/plan-review` (deep)
Status: **planned** (frozen at commit; do not edit after)

## Problem

`POST /api/solve` is finished and proven, and it cannot answer a single question about an
account it has not seen. The solver takes candidate changes as *input*; the eleven that
exist are hand-written in `backend/tests/fixtures/scenarios.py` and
`frontend/src/fixtures/scenarios.ts`, tuned to one 15-transaction demo account. Every
downstream item — the synthetic account generator, Nessie, a demo on real-looking data —
is blocked on turning a transaction list into the changes a person could plausibly make.

## Scope

**In:** `backend/app/candidates/` (merchant normalisation and keyword classification, a
category → alternatives policy table, generation with the solver's own validity rules
built in, deterministic ranking and capping), additive schemas, `POST /api/candidates`,
four test modules plus a realistic-account fixture generator, docs.

**Out:** recurring detection (separate 1-hour timebox; `recurring` is consumed as an
input flag here), the synthetic account generator proper, Nessie, any frontend change
(`types.ts` and `lib/api.ts` will need the new shapes later — pointer, not a promise),
any edit to `frontend/src/solver/mockSolver.ts`, any change to the `POST /api/solve`
contract, new dependencies.

## Design decisions

- **D1 — Alternatives are allowed, and the solver arbitrates.** One transaction may
  receive up to two competing candidates (e.g. trim the groceries *or* push them past
  payday). Both engines already enforce at-most-one-per-`target_txn_id`
  (`engine_cpsat.py:91`, `engine_brute.py:43`); the claim in the solver-core handoff that
  this is a 422 was wrong. Nothing in validation needs to change.
- **D2 — Additive endpoint.** `POST /api/candidates` takes `{as_of, horizon_end,
  scheduled, limit?}` and returns `{candidates: Candidate[], meta: {rows_considered: int,
  protected: Id[], unrecognised: Id[], not_actionable: Id[], truncated: bool}}`.
  `limit` is a `StrictInt` in `1..MAX_N`, **default `MAX_FREE = 18`**: the TypeScript
  oracle refuses more than 20 free candidates (`mockSolver.ts:209`) and the browser
  fallback throws unhandled above that, and the exhaustive server fallback refuses above
  18 — so 18 is the largest set every safety net still answers. A caller that knows it has
  CP-SAT may ask for up to 60. `meta` identity, pinned by test: every considered row is
  in exactly one of **offered** (targets a returned candidate), `protected` (recognised
  protected category, or unknown and not discretionary) or `not_actionable` (recognised
  as changeable, emitted nothing: lead time, no payday, or 0 cents); `unrecognised` is an
  orthogonal flag — classification, not disposition: every row classified unknown,
  including one the cap removed — so the UI can show that an offered skip rests on the
  caller's `discretionary` label rather than on recognition. When `truncated`, rows whose
  every alternative fell below the limit are in no disposition list (a row that kept one
  alternative is still offered, so truncation does not imply a missing row). Validation of the three request
  fields is *shared* with `SolveRequest` by extracting the three validator bodies into
  module-level helpers both classes call; `SolveRequest`'s class, field order and
  validators' behaviour are unchanged. In `docs/api-contract.md` the `/api/solve`
  contract is the whole current file; the frozen region is **`## Request` through the end
  of `## Notes` (lines 8–160 today), byte-identical**. The title and its preamble (lines
  1–6) may widen to name both endpoints, and the new section is appended after `## Notes`.
- **D3 — No new dependencies.** Stdlib only. `rapidfuzz` is present in the venv but absent
  from `requirements.txt` and `wheels/`; using it would break the offline install.
  Classification is whole-token keyword-phrase matching over a normalised description
  (uppercase; every non-alphanumeric → space; collapse), with categories checked in a
  fixed priority order and first hit winning; **protected categories are checked
  first**, so `GAP INSURANCE` is insurance before it is shopping. Keywords are normalised
  at import with the same function, so `GOLD'S GYM` and `APPLE.COM/BILL` match as
  phrases, and phrases are indexed by first token so a row costs O(tokens), not
  O(tokens × phrases). Short or dictionary-word tokens (`CLUB`, `MARKET`, `WATER`,
  `POWER`, `GAP`, `BP`, `QT`, `FUEL`, `GIANT`, `PILOT`) are never single-token phrases;
  they appear only inside multi-token ones (`SAMS CLUB`, `FRESH MARKET`, `GIANT FOOD`).
  Every table entry is a tuple; nothing is a set, so output cannot vary with
  `PYTHONHASHSEED`.
- **D4 — Protected categories emit nothing:** `card_payment`, `housing`, `utilities`,
  `phone`, `loan`, `insurance`, `medical`, `tuition`, `transfer`, `atm_cash`. Paying only
  the card minimum is deliberately not offered (Nathan, Sat ~04:00: "sets a bad
  precedent"). The hand-written fixture keeps `c_card_min` because the parity tests are
  frozen against the oracle; the generator's output on the demo account therefore
  differs from the eleven, and AC8 pins the difference rather than letting it drift.
- **D5 — Unknown means protected, unless the caller said discretionary.** A description
  no keyword matches yields nothing when `kind` is `bill` or `income`; when `kind` is
  `discretionary` it yields a `skip` at pain 3. This is the product doc's *"do not infer
  that an expense is expendable simply from its merchant"* made mechanical: we offer to
  drop only what we recognise as droppable or what the caller has already labelled so.
- **D6 — Deferral recharge rule.** `recharge_date` = the earliest row with
  `kind == "income"` **and `amount_cents > 0`** dated strictly after the charge and ≤
  `horizon_end` (a negative income row is a clawback, which the schema allows and
  `test_validation.py:178` blesses; "moved past payday" must not point at one). No such row → the defer alternative is
  dropped for that row. Rationale: D10 of the solver spec says a recharge past the
  horizon never returns, which would make the deferral a skip wearing the wrong label —
  the exact class of the two prior deferral bugs (Codex F-1, critique F3).
- **D7 — Emit only what is actionable:** `days_between(as_of, effective_date) >=
  lead_time_days`, boundary inclusive to match `eligibility.split()`. A candidate the
  solver would drop on arrival is not a suggestion, it is noise in the "considered" count.
- **D8 — Ids are a pure function of the row and the action:** `f"{txn.id}.{action}"`;
  if that exceeds 64 characters, `f"{txn.id[:40]}.{action}.{h}"` where `h` is the first
  12 hex characters of `hashlib.sha1(txn.id.encode(), usedforsecurity=False)` — 63
  characters at the longest action, never the builtin `hash()` (seed-randomised). The
  generator asserts global uniqueness and `len <= 64` itself, so a collision is a loud
  failure in tests rather than a 422 on the client's next request. The
  client round-trips `locks` and `previous_plan` by id, so an id that changed between
  calls would silently break every lock and the hysteresis term.
- **D9 — Policy table** (category → ordered alternatives; `pct` of `abs(amount)`, floored
  to cents; a result of 0 cents drops the alternative):

  | category | alt 1 | alt 2 |
  |---|---|---|
  | streaming | cancel 100 %, lead 2, pain 1 | — |
  | gym | cancel 100 %, lead 3, pain 1 | — |
  | software | cancel 100 %, lead 1, pain 2 | — |
  | food_delivery | skip 100 %, lead 0, pain 2 | — |
  | coffee | skip 100 %, lead 0, pain 1 | — |
  | restaurant | skip 100 %, lead 0, pain 2 | — |
  | groceries | downgrade 35 %, lead 0, pain 3 | defer 100 %, lead 0, pain 4, needs payday |
  | fuel | defer 100 %, lead 0, pain 3, needs payday | downgrade 50 %, lead 0, pain 3 |
  | shopping | skip 100 %, lead 1, pain 2 | — |
  | rideshare | skip 100 %, lead 0, pain 3 | — |
  | entertainment | skip 100 %, lead 0, pain 2 | — |
  | personal_care | skip 100 %, lead 1, pain 2 | — |
  | unknown (discretionary) | skip 100 %, lead 0, pain 3 | — |

  Values that coincide with the hand-written fixture (gym lead 3 pain 1, DoorDash pain 2,
  Starbucks pain 1, Amazon lead 1 pain 2, Shell defer pain 3, Kroger trim pain 3) are
  taken from it on purpose: those were tuned by hand against the demo.
- **D10 — Wording.** Labels come from per-category templates with a display name carried
  by the matched keyword ("Pause Netflix for a cycle", "Skip the DoorDash order", "Trim
  the Sep 21 grocery run", "Put off the gas fill to Sep 26"). A post-pass makes labels
  unique by appending the short date, then the amount. `detail` =
  `"{description}, {money(abs(amount))}"` + `" recurring"` if recurring (the schema has
  no cadence; "monthly" would misdescribe a weekly charge) + `" down to
  {money(remaining)}"` for a downgrade or `" moved past payday"` for a defer. **Labels
  never contain the raw description** — a label is interpolated into
  `certificate.sentence` and `GUARANTEED RATE` is a real lender — so an unknown
  discretionary row's label is the fixed "Skip this charge" and its description lives in
  `detail` only. Every label, and every template-generated part of `detail`, is clear of
  `wording.BANNED`, of `("waste", "unnecessary", "frivolous", "afford")`, of `"None"`, and
  of `"$-"`; the verbatim description inside `detail` is the user's own statement line and
  is exempt. Dedupe runs **after** the cap, with a `Counter`, and falls through date →
  amount → an ordinal so it always terminates unique — never the transaction id, which
  is caller text and could carry a banned word into `certificate.sentence`. Generic
  lexicon phrases (`PIZZA`, `SALON`, …) have no display and use a brand-less template.
- **D11 — Rank, cap, order.** Rank by `(alternative index, pain, -freed_cents, id)`, so
  every row's first choice precedes any row's second; truncate at `limit` and set
  `meta.truncated`; dedupe labels; then order the output by `(effective_date, id)`, the
  plan's own rule. `rows_considered` counts rows that pass the pre-filter (`kind !=
  income`, `amount_cents < 0`, date inside the window) before classification.
- **D12 — Multi-occurrence recurring rows** yield one candidate per occurrence, each
  freeing its own amount on its own date, with dated labels. The contract carries one
  `freed_cents` on one `effective_date`; `solver.md` already records this as the data-prep
  layer's job. The count-of-changes term therefore prices a full cancel as N changes over
  an N-billing horizon — a known V1 limitation, documented in the feature spec.
- **D14 — What this run does not fix, recorded as pointers.** (a) The 503 body for
  a >18 set without OR-Tools quotes the cap ("capped at 18") — solver lane, and
  unreachable at the default limit. (b) `App.tsx:58-68` runs the browser fallback inside
  a `.catch` with no try/catch of its own, so a set the mock refuses freezes the UI
  silently — frontend lane. (c) Locks name candidate ids. A lock on an id that merely
  missed its lead time is absorbed (`meta.excluded_locked_in`); a lock on an id **absent
  from the re-fetched set** is a 422 on the whole solve, and a cached candidate whose
  `effective_date` has slipped before a moved `as_of` is a 422 too. The client must prune
  `locks` to the returned id set on every `/api/candidates` response and must send the
  same `as_of` to both endpoints — written into the contract's new section as a client
  rule. (d) `test_response.py` `PAIRS` cannot cover the new models until `types.ts` has
  mirrors — frontend lane.
- **D13 — Module layout.** `backend/app/candidates/{__init__.py, lexicon.py, policy.py,
  generator.py}`; schemas in `backend/app/schemas.py` (additive); route in
  `backend/app/main.py` before the static mount; tests
  `backend/tests/test_candidates_{classify,policy,api,roundtrip}.py`; fixture
  `backend/tests/fixtures/accounts.py`.

## What will change

- Create `backend/app/candidates/` and the four test modules plus the fixture module.
- Edit `backend/app/schemas.py` (additive: three helpers, `CandidatesRequest`,
  `CandidatesMeta`, `CandidatesResponse`) and `backend/app/main.py` (one route).
- Docs per "Docs committed to".

## Acceptance criteria (each maps to a test; the test names are recorded in Results)

- AC1 Every emitted candidate validates as `Candidate`, and the full set validates inside
  a `SolveRequest` with its source rows — demo ×3, 300 seeded random accounts, the
  every-cap-at-maximum case (with an explicit opening balance at the input bound; a
  trough-derived one would be ~`10^14` and 422).
- AC2 No candidate targets an income row, a non-negative amount, a row outside
  `[as_of, horizon_end]`, or a protected category; unknown non-discretionary → nothing.
  Each filter has a counterfactual that fails if the filter is removed.
- AC3 Every defer's `recharge_date` is the next positive income row strictly after
  `effective_date` and ≤ `horizon_end`; no such row → no defer; same-day payday →
  the *next* one or nothing; a negative income row is never a recharge date.
- AC4 `1 <= freed_cents <= abs(amount)` for every candidate; the pct floor checked at
  1, 2, 3, 99, 100, 101 cents; a 0-cent result drops the alternative.
- AC5 Ids match `ID_RE`, are unique, are byte-identical across calls, survive a 64-char
  transaction id, distinguish two ids sharing a 60-char prefix, and are unaffected by
  adding unrelated rows.
- AC6 Labels unique within a set (date, then amount, then an ordinal, as tiebreakers)
  even for two rows with identical description, date and amount, and clean even when the
  transaction id itself carries a banned word; no label, and no
  template-generated part of any detail, contains a banned or judgmental word, `"None"`,
  or `"$-"`; labels never contain the raw description; every detail contains
  `money(abs(amount))`; non-defer candidates carry `recharge_date = None`; every brand
  placeholder resolves — an entry has a display name or its category has a brand-less
  template (asserted at import in `policy.py`).
- AC7 Output is a deterministic total order: shuffled input → identical output; two
  subprocesses with `PYTHONHASHSEED=0` and `=1` → byte-identical output; 2000 eligible
  rows → exactly 18 out by default and exactly 60 with `limit = 60`, `truncated = true`
  both times; 100 rows × 2 alternatives at `limit = 60` → 60 distinct targets, not 30;
  the `meta` identity holds in the two truncation edge cases (one row with two
  alternatives at `limit = 1`; two unknown discretionary rows at `limit = 1`).
- AC8 The demo scheduled list yields the golden set recorded in the feature spec; it
  contains no candidate targeting `t_card`; `eligibility.split()` with empty locks on it
  reports `len(free) <= MAX_FREE` (with empty locks `free` is the whole set, so this is
  the exact quantity `engine_brute.py:30` guards on). A ~40-row table of real merchant
  strings classifies as expected, including every false positive the risk review named
  (`SAM'S CLUB`, `GAP INSURANCE PREMIUM`, `MARKET ST PROPERTIES`, `WATER ST TAVERN`,
  `CORE POWER YOGA`, `TARGET OPTICAL`, `FUEL FITNESS`, `GUARANTEED RATE`).
- AC9 `POST /api/candidates`: 422 with `loc[1]` naming the field for unknown field, float
  cents, malformed date, duplicate txn id, horizon > 366, `horizon_end < as_of`,
  > `MAX_SCHED` rows, `limit` of 0 / 61 / `null` / `"18"`; `limit` omitted → 18; empty
  `scheduled` → 200 `[]`; every-cap input → 200; route answers with the static mount
  present; response items validate as `Candidate`; two clients, same body → same bytes.
- AC10 Generated sets solve identically on CP-SAT and brute force (demo ×3 and 50
  windows at ≤ 14 candidates in the gate; the 300-window sweep at ≤ 18 under `-m perf`,
  because brute force is 2^n × horizon) and agree with the TypeScript oracle per
  `test_parity.assert_agrees` (which carries the tier-3 empty-plan wording exception) on
  demo ×3 + 100 random plus one all-protected tier-3 case — every set handed to the
  oracle is asserted `<= 18` first, because the oracle refuses above 20 and is
  exponential; the existing
  invariant properties hold over generated responses; a locked generated id survives
  regeneration and is honoured by the solve; the same set validated at `as_of + 1` is the
  documented 422 (pins D14c as a contract, not a surprise).
- AC11 Freeze: `docs/api-contract.md` lines 8–160 (today's `## Request` … `## Notes`)
  byte-identical, checked by `git diff` at execution; no existing
  `backend/tests/test_*.py` modified; `frontend/` untouched; `backend/requirements.txt`
  untouched.
- AC12 Gate `977 + N` passed with `N >= 80`; the 2000-row perf case reported under `-m perf`.

## Commands

```bash
cd "/Users/nathanstough/Desktop/VT Hacks" && .venv/bin/pytest backend/tests/test_candidates_classify.py backend/tests/test_candidates_policy.py backend/tests/test_candidates_api.py backend/tests/test_candidates_roundtrip.py -q -m "not perf"
cd "/Users/nathanstough/Desktop/VT Hacks" && .venv/bin/pytest backend/ -q -m "not perf"
cd "/Users/nathanstough/Desktop/VT Hacks" && .venv/bin/pytest backend/ -m perf -q -s
```

## Docs committed to

`docs/specs/2026-09-19_candidate-generation.md` (this), `docs/features/candidates.md`
(create), `docs/features/solver.md` (line 18 pointer to this feature; line 46 "model constraint +
validation" corrected — competing candidates on one transaction are legal input, the
at-most-one rule lives in the search; "Pain scores" link; "Known gaps" per-occurrence
note), `docs/api-contract.md` (title widened; additive `POST /api/candidates` section
after `## Notes`; lines 8–160 unchanged), `README.md` (lines 9–10 endpoint and package
list; line 15 contract description), `CLAUDE.md` (line 65 Layout bullet for `backend/`).
Also the two in-code pointers that name only one endpoint: `backend/app/schemas.py:1`
docstring and `backend/app/main.py:52` comment.

Not touched by design: `frontend/src/types.ts`, `frontend/src/lib/api.ts` (frontend lane;
they need `CandidatesRequest`/`CandidatesResponse` mirrors before the UI can call this),
`docs/demo-script.md` (no demo change in this run). No `BUGS.md` exists; the historical
sweep in P2 came from the solver-core run spec's audit tables and memory.

## Results — executed Sat 2026-09-19, 04:20–05:05

**Gate: 1155 passed**, 8 deselected, 18 s (was 977 + 6). **180 tests added**, against the
P2 floor of 80: classify 68, policy 77, api 22 (+1 perf), roundtrip 13 (+1 perf).
**Perf: 8 passed**, 137 s. Demo accounts 3.9–6.7 ms; 60 changes over 60 days 31 ms;
exhaustive at its 18-change cap 3.27 s; 100 random accounts 2.9 ms each.

Freeze verified at commit time: `git diff HEAD -- backend/tests frontend
backend/requirements.txt` empty; `docs/api-contract.md` lines 8–160 byte-identical against
`HEAD` by `diff`; the only new paths under `backend/tests/` are the five this spec names.

### Acceptance criteria → tests

| AC | Where |
|---|---|
| AC1 | `test_candidates_roundtrip.py::test_every_generated_set_is_a_legal_solve_request` (300 windows), `::test_each_demo_preset_solves_on_generated_candidates`, `::test_the_biggest_account_the_schema_allows_still_solves` |
| AC2 | `test_candidates_policy.py::test_an_income_row_is_never_a_candidate_however_it_reads`, `::test_a_negative_income_row_is_still_income`, `::test_a_refund_is_not_a_charge`, `::test_a_zero_amount_row_is_not_a_charge`, `::test_a_charge_before_the_window_is_not_considered`, `::test_a_charge_after_the_window_is_not_considered`, `::test_both_ends_of_the_window_are_inside_it`, `::test_a_protected_charge_is_reported_and_never_offered` (10 categories), `::test_an_unrecognised_bill_is_protected_and_flagged` |
| AC3 | `::test_a_deferral_needs_a_payday_to_come_back_on`, `::test_a_deferral_lands_on_the_next_payday_after_the_charge`, `::test_a_payday_on_the_day_of_the_charge_is_not_late_enough`, `::test_a_payday_past_the_horizon_cannot_be_a_recharge_date`, `::test_a_clawback_is_not_a_payday`, `::test_every_deferral_anywhere_comes_back_after_it_leaves` |
| AC4 | `::test_a_grocery_trim_frees_thirty_five_percent_floored` (7 amounts), `::test_a_half_tank_frees_half_floored` (4), `::test_a_change_never_frees_more_than_the_charge_is_worth` |
| AC5 | `::test_an_id_says_what_it_is`, `::test_an_id_is_always_legal_however_long_the_transaction_id` (5 lengths), `::test_two_transactions_sharing_a_long_prefix_get_different_ids`, `::test_two_thousand_transactions_sharing_a_prefix_all_get_distinct_ids`, `::test_the_same_account_asked_twice_gets_the_same_ids`, `::test_adding_an_unrelated_row_does_not_renumber_anything` |
| AC6 | `::test_no_two_changes_on_screen_read_the_same`, `::test_the_same_shop_on_two_days_is_told_apart_by_date`, `::test_two_charges_alike_in_every_visible_way_still_read_differently`, `::test_a_label_never_quotes_the_transaction_id`, `::test_a_label_never_quotes_the_merchant_string`, `::test_no_label_says_anything_this_product_never_says`, `::test_a_brandless_merchant_gets_a_label_that_does_not_invent_one`, `::test_only_a_deferral_carries_a_recharge_date` |
| AC7 | `::test_the_cap_spreads_across_transactions_rather_than_stacking_on_a_few`, `::test_the_default_limit_is_what_every_fallback_can_still_answer`, `::test_two_thousand_rows_still_respect_the_limit`, `::test_the_order_rows_arrive_in_does_not_change_the_answer`, `::test_the_output_is_ordered_the_way_the_plan_is`, `::test_two_processes_with_different_hash_seeds_produce_the_same_words` |
| AC8 | `::test_the_demo_account_produces_exactly_the_documented_set`, `::test_the_demo_account_reports_what_it_did_with_every_row`, `::test_the_demo_account_stays_inside_the_exhaustive_engine_s_reach`, `::test_the_card_payment_is_never_offered_even_at_the_minimum`, `test_candidates_classify.py::test_merchant_strings_classify_the_way_a_person_would_read_them` (42 strings) |
| AC9 | `test_candidates_api.py` — the 10-case 422 table, `::test_a_float_amount_is_refused`, `::test_two_transactions_may_not_share_an_id`, `::test_more_rows_than_the_limit_allows_is_refused`, `::test_an_account_with_nothing_in_it_is_an_answer_not_an_error`, `::test_every_field_at_its_maximum_still_answers`, `::test_serving_the_site_does_not_swallow_the_endpoint`, `::test_two_processes_of_the_app_answer_identically` |
| AC10 | `test_candidates_roundtrip.py::test_both_engines_agree_on_generated_accounts`, `::test_the_reference_solver_agrees_on_generated_accounts`, `::test_an_account_where_nothing_may_be_changed_agrees_too`, `::test_the_response_properties_hold_on_generated_accounts` (9 invariants × 50), `::test_an_override_survives_the_account_being_generated_again`, `::test_candidates_go_stale_when_the_day_moves_under_them` |
| AC11 | Verified by command, above. |
| AC12 | 1155 gate, 8 perf. |

### Review rounds

**Exploration (3 parallel agents).** The risk pass changed the design twice. It found that
the TypeScript oracle refuses above 20 free candidates (`mockSolver.ts:209`) and the
browser fallback throws unhandled past that, so a 60-candidate default would have made the
demo's own safety net fail silently — hence D2's `limit`, defaulting to `MAX_FREE`. It also
found the id fallback was exactly 64 characters with no slack, that a negative income row
could be chosen as a deferral's payday, and eight real statement strings that generic
tokens misclassify in both directions.

**Claude critique (pre-Codex).** 15 findings, 3 blockers, all applied before review: the
lexicon violated its own import-time rule (`GYM` and `HBO` are three-character tokens that
were not in the allow-list — the import, and so every new test file, would have failed at
collection); the `meta` identity equation double-counted unknown bills and failed on every
truncated window; and the brute-force agreement test over 300 windows at 18 free would have
run 15–40 minutes inside the gate. Also: the dedupe suffix quoted the transaction id, which
is caller text that reaches `certificate.sentence`; `from tests.test_invariants import …`
would have double-collected; the moving-`as_of` test passed vacuously on the demo.

**Codex plan review (`gpt-6-astra`).** 5 critical and 2 suggestions, all applied: the lexicon
invariant contradicted the brand-less entries step 3 requires; the truncation assertions
were wrong in two constructible cases (both now explicit tests); the every-cap round-trip
would have 422'd on an opening balance of ~10^14; `_normalise` bypasses the one deliberate
oracle divergence, so `assert_agrees` is used instead; `KROGER #382` and `kroger 0382` do
**not** normalise to identical tokens, so the test asserts equal classification instead;
`" monthly"` misdescribes a weekly charge, now `" recurring"`. The second suggestion —
`-m "not perf"` on the first command, so the 300-window sweep does not run twice — was
recorded as applied in the first draft of this section while the command itself was
unchanged; the critique's second round caught that, and it is applied above.

**Codex, asked separately what executing this plan demands.** Estimated 70 % mechanical /
30 % judgment, and named the failure modes worth guarding: an omitted lexicon phrase
leaving a protected merchant unrecognised and therefore skippable; a plausible-looking but
wrong ranking key; and vacuous matcher tests. **One of those was live in this branch** —
`test_the_longest_phrase_wins_within_a_category` compared only categories, and both phrases
were `atm_cash`, so it passed whichever won. It now compares the display, and a second test
asserts every phrase in the table reaches its own category rather than being shadowed.

### Recorded, not resolved

The run spec was written and committed in the same commit as the implementation, so git
carries no evidence that D1–D14 and AC1–AC12 predate the code. Nothing here was rewritten
after the fact — Results is appended — but that cannot be verified from history. Commit the
spec at plan time in the next run.

### Deviations from the plan

- Module named `generator.py` (plan step 4 header said `generate.py` in one place; the
  body and D13 say `generator.py`, which is what shipped — the package attribute and the
  function would otherwise collide).
- `_many(2000)` in the cap test adds its own payday row, so it exceeded `MAX_SCHED` by one.
  Now 1999.
- The invariant function names in plan step 10 were written from memory and were wrong;
  the nine real names are used.
- Two perf cases added rather than one: the 2000-row classification cost and the
  300-window engine-agreement sweep the critique moved out of the gate.

### Audit rounds

**Claude critique, round 1 — Fail** (Test coverage, Documentation). It ran 15 mutations
against the committed code. Six changed load-bearing behaviour and killed **zero** tests:
dropping the alternative index from the rank key, inverting the savings preference,
deleting the final dated sort, and three of the five policy rows that never appear on the
demo account. Two tests were vacuous for reasons reading them would not reveal — the cap
test used 100 identical rows, so pain alone already separated first choices from second;
and the ordering test was masked because `_dedupe` re-sorts as a side effect and the demo
account has two DoorDash rows. It also found a real defect neither review anticipated:
classification depended on the caller's Unicode form, so an accented merchant name
classified differently in NFC and NFD. All fixed in `88b0657`.

**Claude critique, round 2 — Acceptable.** All 22 mutations across both rounds now kill at
least one test; the four that killed tests in round 1 kill exactly as many, so nothing was
weakened. It verified the new ordering test genuinely exits `_dedupe` early (rather than
being masked the way its predecessor was), checked the policy literal against D9 row by
row, and confirmed the Unicode fix changes the tokens of exactly one string in the whole
corpus — the intended one — with no new phrase collisions and no perf cost (2000 rows ×
1880-character descriptions: 251 ms against a 2000 ms budget). Its one surviving finding
was F6 above.

Scorecard: Plan adherence Acceptable, Scope discipline **Excellent**, Test coverage
**Excellent**, Review compliance Acceptable, Freeze integrity Acceptable, Regression check
**Excellent**, Documentation Acceptable. **Overall: Acceptable.**

### Codex audit (~04:47) — **Fail**, one real coverage gap

| Finding | Resolution |
|---|---|
| **AC10's engine comparison was thinner than the criterion.** The test took the first 50 windows and kept whichever qualified — 29 — then asserted only that 20 had been checked. AC10 asks for 50 qualifying accounts *and* the three demo presets, and the demo presets were only ever run through the default engine and the TypeScript oracle, never CP-SAT against exhaustion. | Scans as far through the windows as it needs to collect 50 qualifying accounts and asserts the count; the three presets each get their own engine-agreement case. The 300-window perf sweep stays where it is — it does not substitute for gate coverage. |
| `CandidatesMeta`'s docstring claimed an unconditional partition, omitting the truncation exception the contract documents correctly. | Docstring now carries the exception. |
| `CandidatesRequest`'s docstring conflated the browser's 20-candidate ceiling with this service's 18. | Both ceilings named, and why the lower one is the default. |

Not actionable: Codex looked for P1/P2/P3 freeze hashes this pipeline does not use, and its
two "setup errors" were its sandbox refusing a temporary directory to the static-site
fixtures, not failures. It measured the gate at 1,160 rather than 1,162 for the same reason.

Scorecard as returned: Plan adherence Fail, Scope discipline **Excellent**, Test coverage
Fail, Review compliance **Excellent**, Freeze integrity Acceptable, Regression check
Acceptable, Documentation Acceptable. **Overall: Fail** — on AC10 coverage alone.

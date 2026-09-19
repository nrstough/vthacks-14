# Feature: candidate generation

Living document. Updated with every change to the generator. Run specs:
`docs/specs/2026-09-19_candidate-generation.md` (first).

## What it does

Given the same `as_of`, `horizon_end` and `scheduled` rows a solve request carries, return
the changes a person could plausibly make — skip, defer, downgrade, cancel — each as a
`Candidate` the solver accepts as-is: what it frees, when it takes effect, how much notice
it needs, and a 1–5 pain score from its category. The user corrects the pain scores with
the lock toggles; that mechanism already works end to end.

The output is a set of *suggestions the person corrects*, never a judgment about what
they should live without. That is a product commitment, not a style: the generator only
offers to drop what it recognises as droppable (or what the caller has already labelled
`discretionary`), it never touches a protected category, and the words it uses are
checked against a banned list in tests.

`POST /api/candidates` — `docs/api-contract.md`. Request `{as_of, horizon_end, scheduled,
limit?}`; `limit` defaults to **18**, the largest set every safety net still answers (the
TypeScript fallback refuses above 20 and is exponential; the exhaustive server fallback
refuses above 18), and may be raised to 60 by a caller that knows it has CP-SAT. Response
`{candidates, meta: {rows_considered, protected, unrecognised, not_actionable,
truncated}}`. Stateless; no new dependencies.

**Client rules** (the server cannot enforce these): send the same `as_of` to
`/api/candidates` and `/api/solve`; re-fetch candidates whenever `as_of` changes; on every
`/api/candidates` response prune `locks.in` / `locks.out` to the returned ids, because a
lock naming a vanished id is a 422 on the whole solve.

## Pipeline

```
scheduled rows
  → normalise + classify     description → category (lexicon.py)
  → row eligibility          income / non-negative / out-of-horizon / protected → nothing
  → policy                   category → up to two alternatives (policy.py)
  → emit                     id, label, detail, freed, dates (generator.py)
  → rank + cap               (alt index, pain, -freed, id); limit, default 18
  → dedupe labels            date → amount → ordinal
  → order                    (effective_date, id), the plan's own rule
```

## Classification

The description is uppercased, every non-alphanumeric character becomes a space, runs of
spaces collapse, and the result is split into tokens. Keyword phrases are normalised the
same way at import, and a phrase matches when its tokens appear contiguously in the
description's tokens — so `KROGER #382`, `kroger 0382` and `KROGER*382` all match
`KROGER`, and `GYM` does not match `GYMBOREE`. Phrases are indexed by their first token,
so a row costs O(tokens). Categories are tried in a fixed priority order with **protected
categories first** and the first hit wins: `GAP INSURANCE PREMIUM` is insurance before it
could be shopping, `DOORDASH*CHIPOTLE` is food delivery before it could be a restaurant,
`AMAZON PRIME VIDEO` is streaming before it could be shopping. Among hits at one priority
the longest phrase wins. No hit → `unknown`.

Short or dictionary-word tokens are never phrases on their own — `CLUB`, `MARKET`,
`WATER`, `POWER`, `GAP`, `BP`, `QT`, `FUEL`, `GIANT`, `PILOT` — because `SAM'S CLUB` is
groceries, `WATER ST TAVERN` is a restaurant and `CORE POWER YOGA` is a gym. They appear
only inside multi-token phrases (`SAMS CLUB`, `FRESH MARKET`, `GIANT FOOD`). Every
lexicon table is a tuple, so output cannot vary with `PYTHONHASHSEED`.

Protected categories (emit nothing): `card_payment`, `housing`, `utilities`, `phone`,
`loan`, `insurance`, `medical`, `tuition`, `transfer`, `atm_cash`. Paying only the credit
card minimum is deliberately not offered.

`unknown` emits nothing unless `kind == "discretionary"`, in which case it is a `skip` at
pain 3.

## Policy table

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
| unknown (discretionary only) | skip 100 %, lead 0, pain 3 | — |

`freed_cents = abs(amount) * pct // 100`; a result of 0 drops the alternative.

## Rules the solver relies on

- **Deferral recharge.** `recharge_date` is the earliest row with `kind == "income"` and
  a positive amount, dated strictly after the charge and no later than `horizon_end` (a
  negative income row is a clawback; "moved past payday" must not point at one). If there is none the defer is not offered:
  a recharge past the horizon never returns inside it (solver D10), which would turn the
  deferral into a skip with the wrong label — the class of both prior deferral bugs.
- **Actionability.** A candidate is emitted only if `effective_date − as_of ≥
  lead_time_days`, the same inclusive boundary `eligibility.split()` applies.
- **Ids** are `f"{txn.id}.{action}"`, or `f"{txn.id[:40]}.{action}.{h}"` with `h` the
  first 12 hex characters of a non-security SHA-1 of the transaction id when that would
  exceed 64 characters (63 at the longest action). They are a pure function of the row
  and the action because the client round-trips `locks` and `previous_plan` by id. The
  generator asserts uniqueness and length itself.
- **One occurrence, one candidate.** A recurring bill that lands N times in the horizon
  yields N candidates with dated labels, each freeing its own amount on its own date. The
  contract carries one `freed_cents` on one `effective_date`, so the count-of-changes
  term prices a full cancel as N changes over an N-billing horizon. Known V1 limitation.
- **Alternatives.** Up to two per row. Both engines enforce at-most-one-per-transaction in
  the search (`engine_cpsat.py:91`, `engine_brute.py:43`); competing candidates on one row
  are legal input, not a validation error.
- **Cap.** Ranked by `(alternative index, pain, −freed_cents, id)` so every row's first
  choice precedes any row's second, then truncated at `limit` with `meta.truncated`. With
  empty locks every generated candidate is *free* in `eligibility.split()`, so the default
  limit of 18 is exactly the exhaustive fallback's cap; the demo account yields 14 and a
  test holds it there.
- **`meta` identity.** Every considered row is in exactly one of: **offered** (targets a
  returned candidate), `protected` (recognised protected category, or unknown and not
  discretionary), `not_actionable` (recognised as changeable, emitted nothing: lead time,
  no payday, 0 cents). `unrecognised` is an orthogonal flag — rows classified unknown, a
  classification rather than disposition, so it includes an unknown row the cap removed
  — so the UI can show that an offered skip rests on the caller's `discretionary` label
  rather than on recognition. `rows_considered` counts rows that survive the pre-filter
  (`kind != income`, negative amount, date inside the window). When `truncated`, rows
  whose every alternative fell below the limit are in no disposition list; a row that
  kept one alternative is still offered.

## Wording

| category · action | label template | detail suffix |
|---|---|---|
| streaming · cancel | Pause {Brand} for a cycle | recurring (if flagged) |
| gym · cancel | Cancel the gym membership | recurring |
| software · cancel | Cancel {Brand} | recurring |
| food_delivery · skip | Skip the {Brand} order | — |
| coffee · skip | Skip the coffee run | — |
| restaurant · skip | Skip {Brand} | — |
| groceries · downgrade | Trim the {date} grocery run | down to {money(remaining)} |
| groceries · defer | Do the {date} grocery run after payday | moved past payday |
| fuel · defer | Put off the gas fill to {recharge date} | moved past payday |
| fuel · downgrade | Half-fill the tank on {date} | down to {money(remaining)} |
| shopping · skip | Cancel the {Brand} order | — |
| rideshare · skip | Skip the {Brand} ride | — |
| entertainment · skip | Skip {Brand} | — |
| personal_care · skip | Skip the {Brand} appointment | — |
| unknown · skip | Skip this charge | — |

`detail` always begins `"{description}, {money(abs(amount))}"`. **Labels never carry the
raw description**: a label is interpolated into `certificate.sentence`, and `GUARANTEED
RATE` is a real lender. Duplicate labels are made unique after the cap by appending
`" on {short date}"`, then `" ({money})"`, then `" (#n)"` — never the transaction id,
which is caller text — so two rows identical in everything but id still get distinct,
clean labels. Generic phrases (`PIZZA`, `SALON`, `TST`…) have no brand and use a
brand-less template: "Skip the meal out", "Skip the night out", "Skip the appointment",
"Cancel the order". Money and short dates come from
`app.solver.dates`, which mirrors `frontend/src/lib/format.ts`.

## Golden set — the demo account

Worked by hand from `backend/tests/fixtures/scenarios.py` (`as_of` Sep 19, horizon to
Oct 2, paydays Sep 25 and Oct 2). Pinned by AC8; if the policy table changes, this table
changes with it in the same commit.

| id | action | freed | effective | recharge | lead | pain | why |
|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | `t_spotify` (Sep 20): streaming needs 2 days' lead, only 1 available → not emitted |
| `t_kroger_1.defer` | defer | 6418 | Sep 21 | Sep 25 | 0 | 4 | next payday after Sep 21 |
| `t_kroger_1.downgrade` | downgrade | 2246 | Sep 21 | — | 0 | 3 | 6418 × 35 // 100 |
| `t_dd_chipotle.skip` | skip | 3180 | Sep 22 | — | 0 | 2 | |
| `t_gym.cancel` | cancel | 3499 | Sep 22 | — | 3 | 1 | 3 days available, 3 needed |
| `t_shell.defer` | defer | 4120 | Sep 23 | Sep 25 | 0 | 3 | |
| `t_shell.downgrade` | downgrade | 2060 | Sep 23 | — | 0 | 3 | 4120 × 50 // 100 |
| — | — | — | — | — | — | — | `t_card`: protected (card payment) |
| `t_starbucks.skip` | skip | 745 | Sep 24 | — | 0 | 1 | |
| — | — | — | — | — | — | — | `t_verizon`: protected (phone) |
| `t_amzn.skip` | skip | 5230 | Sep 27 | — | 1 | 2 | |
| `t_kroger_2.defer` | defer | 7105 | Sep 28 | Oct 2 | 0 | 4 | next payday after Sep 28 |
| `t_kroger_2.downgrade` | downgrade | 2486 | Sep 28 | — | 0 | 3 | 7105 × 35 // 100 |
| `t_netflix.cancel` | cancel | 2299 | Sep 29 | — | 2 | 1 | |
| `t_shell_2.defer` | defer | 3860 | Sep 30 | Oct 2 | 0 | 3 | |
| `t_shell_2.downgrade` | downgrade | 1930 | Sep 30 | — | 0 | 3 | |
| `t_dd_panera.skip` | skip | 2840 | Oct 1 | — | 0 | 2 | label deduped: "Skip the DoorDash order on Oct 1" (and "… on Sep 22") |

14 candidates; `rows_considered = 13`; `protected = [t_card, t_verizon]`;
`unrecognised = []`; `not_actionable = [t_spotify]`; `truncated = false`. The hand-written fixture's `c_card_min` has no
counterpart here by decision D4.

## Known gaps

- Recurring detection is not this component's job; `recurring` is consumed as given.
- No tier knowledge for `downgrade` on subscriptions (V1 offers cancel only).
- Pain defaults are category constants (V1); learning them from lock behaviour is the V2
  recorded in `docs/features/solver.md`.

## Tests

`backend/tests/test_candidates_{classify,policy,api,roundtrip}.py`; fixture generator
`backend/tests/fixtures/accounts.py`. Gate: `.venv/bin/pytest backend/ -q -m "not perf"`.

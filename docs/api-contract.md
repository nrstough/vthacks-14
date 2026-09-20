# API contract — `POST /api/solve`, `POST /api/candidates` and `POST /api/accounts/sample`

Frozen shape. The frontend builds against this; the solver targets it. All money is
**integer cents**, all dates are `YYYY-MM-DD` strings in local time (no timezones,
no datetimes). The frontend does no financial arithmetic: it renders what the
solver returns.

## Request

```jsonc
{
  "as_of": "2026-09-19",              // first day of the horizon, inclusive
  "horizon_end": "2026-10-02",        // last day, inclusive (next payday eve)
  "opening_balance_cents": 18432,     // balance at start of as_of
  "buffer_cents": 2500,               // beta; the cushion we aim to keep
  "scheduled": [                      // do-nothing transactions in the horizon
    {
      "id": "t_pay_0925",
      "date": "2026-09-25",
      "description": "HARRIS TEETER PAYROLL",
      "amount_cents": 31240,          // signed: + income, - outflow
      "kind": "income",               // income | bill | discretionary
      "recurring": true
    }
  ],
  "candidates": [                     // the moves the solver may choose from
    {
      "id": "c_skip_dd",
      "label": "Skip DoorDash",
      "detail": "DOORDASH*CHIPOTLE",
      "action": "skip",               // skip | defer | downgrade | cancel
      "target_txn_id": "t_dd_0922",
      "freed_cents": 3180,            // cash kept, from effective_date onward
      "effective_date": "2026-09-22",
      "recharge_date": null,          // defer only: the day it comes back
      "lead_time_days": 0,            // must be actioned this many days ahead
      "pain": 2                       // 1..5, disruption cost
    }
  ],
  "locks": { "in": ["c_cancel_gym"], "out": [] }, // user overrides
  "previous_plan": ["c_skip_dd"]                    // optional, default []: candidate ids of the plan the user was last shown (hysteresis input; the server keeps no state)
}
```

## Response

```jsonc
{
  "tier": 1,                          // see tiers below
  "verdict": "Skip three things and you stay above zero through Oct 2.",
  "qualifier": "Sufficient under the schedule shown.",
  "plan": [
    {
      "candidate_id": "c_skip_dd",
      "label": "Skip DoorDash",
      "detail": "DOORDASH*CHIPOTLE",
      "action": "skip",
      "date": "2026-09-22",           // the day the change takes effect, NOT the deadline:
                                      // act by date - lead_time_days
      "freed_cents": 3180,
      "pain": 2,
      "strictly_needed": true,        // false when it only protects the cushion
      "reason": "Covers the Sep 24 dip."
    }
  ],
  "certificate": {
    "irredundant": true,
    "minimal_proven": true,           // false only if a solver stage hit its time limit (meta.status FEASIBLE)
    "sentence": "Remove any one and you're $41 under on the 24th.",
    "per_item": [
      {
        "candidate_id": "c_skip_dd",
        "worst_shortfall_cents": 4100,  // absolute worst dip with this change removed
        "worst_date": "2026-09-24",
        "marginal_cents": 4100,         // how much DEEPER the dip gets without this change
        "marginal_days": 1              // how many more days below zero without it
      }
    ]
  },
  "shortfall": {                      // what remains AFTER the plan
    "worst_cents": 0,                 // 0 when the plan clears zero
    "worst_date": null,
    "total_cents": 0
  },
  "external_cash_needed": null,       // tier 3 only: { amount_cents, by_date }; by_date = FIRST day below zero, amount covers the deepest dip
  "balances": [                       // one row per day, as_of..horizon_end
    {
      "date": "2026-09-19",
      "baseline_cents": 18432,        // do-nothing end-of-day balance
      "with_plan_cents": 18432,       // end-of-day balance under the plan
      "is_payday": false,
      "changes_here": []              // candidate_ids taking effect this day
    }
  ],
  "meta": {
    "solver": "cp-sat",               // or "brute-force"
    "status": "OPTIMAL",              // OPTIMAL | FEASIBLE
    "wall_ms": 84,
    "candidates_considered": 22,
    "excluded_locked_in": []          // locked-in ids dropped because their lead time has passed
  }
}
```

## Tiers

Computed from the with-plan balance across the horizon. The word *infeasible*
never appears in the response.

| Tier | Condition | Meaning |
|---|---|---|
| 1 | with-plan balance >= `buffer_cents` every day | Proven sufficient |
| 2 | with-plan balance >= 0 every day, but dips below the buffer | Clears zero, no cushion |
| 3 | with-plan balance < 0 on some day | Needs external cash; `external_cash_needed` is set |

## Objective

Lexicographic, minimised in order (settled Sat 2026-09-19, decision D1 in
`docs/specs/2026-09-19_solver-core.md`; the TS stand-in and the Python solver both
implement exactly this):

1. days below zero
2. worst shortfall below zero
3. buffer-missed flag: 0 if every day is >= `buffer_cents`, else 1
4. number of changes (cardinality)
5. total below-buffer exposure, sum of max(0, buffer - balance)
6. total pain
7. hysteresis: symmetric difference against `previous_plan`
8. sorted candidate-id tuple, for a deterministic tiebreak

Consequence: the plan is the *smallest* set at every tier. If any set holds the
cushion, the smallest such set wins (tier 1); otherwise the smallest set that clears
zero (tier 2); otherwise fewest fee-days, then shallowest dip (tier 3).

## Notes

- `balances` is the chart's only input. The red fill is drawn wherever a series
  goes below zero; the with-plan line steps at each `changes_here` date.
- `certificate.sentence` is rendered verbatim. The solver owns the wording.
- Locking a candidate in or out re-posts the whole request. There is no
  incremental endpoint and no session state on the server.
- Schemas are strict: unknown fields are rejected (422); all `*_cents` are integers;
  dates are `YYYY-MM-DD`; `opening_balance_cents` is the available balance at the start
  of `as_of`.
- Unknown ids in `locks`, or the same id in both lists, are a 422. A pinned (locked-in)
  candidate whose lead time has passed is excluded and listed in `meta.excluded_locked_in`.
- At most one chosen candidate per `target_txn_id` (enforced in the search by both the
  stand-in and the server; two pinned candidates on one transaction keep the lower id and
  list the other in `meta.excluded_locked_in`). `freed_cents` must not exceed the target
  transaction's absolute amount (422). `target_txn_id` must exist in `scheduled` (422).
- Certificate is marginal: an item is load-bearing iff removing it deepens the worst dip
  or adds a day below zero relative to the plan itself; `irredundant` means every item is.
- Ordering: `plan` by (date, id) in code-point order; `per_item` in plan order;
  `changes_here` and `excluded_locked_in` sorted; ties on dates resolve to the first day.
- Limits: horizon <= 366 days, <= 60 candidates, <= 2000 scheduled rows, |cents| <= 10^11. Those
  are per-field bounds on the REQUEST. Figures the server derives — daily balances,
  `total_cents` — are sums across the horizon and are legitimately larger.
- Responses: `200` with the body above; `422` with `{"detail": [{type, loc, msg, input}]}`
  where `loc[0]` is `"body"`; `503` with `{"detail": "..."}` when no exact engine can
  answer. A 503 is never an approximate answer — the service refuses rather than guessing,
  because a guess would be indistinguishable from a proof in this shape.

## `POST /api/candidates`

Turns a transaction history into the changes the solver may choose from. Additive: the
`/api/solve` contract above is unchanged, and this endpoint is optional — a client that
builds its own candidates never has to call it.

```jsonc
{
  "as_of": "2026-09-19",              // same three fields /api/solve validates,
  "horizon_end": "2026-10-02",        // checked by the same code
  "scheduled": [ /* ScheduledTxn, as above */ ],
  "limit": 18                         // optional, 1..60, default 18
}
```

`limit` defaults to 18 rather than the 60-candidate maximum because it is the lower of two
different ceilings: this server's exhaustive engine refuses above **18**, and the browser's
stand-in solver refuses above **20**. Eighteen is therefore the largest set every fallback
still answers. Raise it only if you know CP-SAT is available.

```jsonc
{
  "candidates": [ /* Candidate, exactly as /api/solve accepts them */ ],
  "meta": {
    "rows_considered": 13,            // rows that were outflows inside the horizon
    "protected": ["t_card"],          // recognised as not-ours-to-touch, or unrecognised bills
    "unrecognised": [],               // no keyword matched; see below
    "not_actionable": ["t_spotify"],  // changeable, but nothing could be offered
    "truncated": false                // more were generated than `limit` allowed
  }
}
```

Every considered row is in exactly one of **offered** (it is some candidate's
`target_txn_id`), `protected`, or `not_actionable`. `unrecognised` is orthogonal: it
records classification, not disposition, so a row no keyword matched appears there whether
it was offered, protected, or dropped by `limit`. When `truncated` is true, a row whose
every alternative fell below the cut appears in none of the three.

A transaction may receive more than one candidate — trim the grocery run *or* push it past
payday. That is legal input, not an error: both engines choose at most one change per
`target_txn_id` in the search.

**Three rules for the client, which the server cannot enforce:**

- Send the **same `as_of`** to this endpoint and to `/api/solve`. A candidate whose
  `effective_date` falls before a later `as_of` makes the whole solve a 422.
- **Re-fetch candidates whenever `as_of` changes.** A day's passing can retire a change
  whose lead time has run out.
- **Prune `locks` to the ids this endpoint returned.** `locks` naming an id that is no
  longer on offer is a 422 on the entire request; an id that merely missed its lead time
  is absorbed and reported in `meta.excluded_locked_in`.

Responses: `200` with the body above; `422` with the same `{"detail": [{type, loc, msg,
input}]}` shape as `/api/solve`. No `503` — this endpoint runs no solver.

## `POST /api/accounts/sample`

Additive: the `/api/solve` and `/api/candidates` contracts above are unchanged,
and this endpoint is optional — the client can carry its own accounts and never
call it.

Returns one **modelled** account, using the contract's own `ScheduledTxn` shape
so no field needs translating.

The response is not itself a request body for the other two endpoints: it carries
`seed`, `opening_balance_cents`, `buffer_cents` and `source`, and both
`SolveRequest` and `CandidatesRequest` are `extra="forbid"`, so posting it
verbatim is a 422. Pick the fields each endpoint declares — `as_of`,
`horizon_end` and `scheduled` for `/api/candidates`; those plus the two balances
and the candidates for `/api/solve`.

```jsonc
{
  "seed": 12345,          // optional; omit and the server picks one
  "as_of": "2026-09-19",  // optional; defaults to the demo date
  "horizon_days": 30      // optional; 14..45, default 30
}
```

`seed` is echoed on the response. That is the point of it: any account a person
is shown can be regenerated exactly from the response alone, which is the
difference between a demo and a party trick.

`horizon_days` is bounded well inside `MAX_T`. The ceiling is 45 rather than the
schema's because candidate count grows with the window and the exhaustive engine
is 2^n.

```jsonc
{
  "seed": 12345,
  "as_of": "2026-09-19",
  "horizon_end": "2026-10-18",
  "opening_balance_cents": 19892,
  "buffer_cents": 2500,
  "scheduled": [ /* ScheduledTxn, exactly as /api/solve takes them */ ],
  "source": "modelled"
}
```

**`source` is required and is always the literal `"modelled"`.** It is not
decoration. This is generated data and nothing downstream may present it as a
bank's. A client that renders an account from this endpoint must say so on
screen, in the same spirit as the offline-solver chip.

Every account carries a payday inside the horizon and a dip below `buffer_cents`
before the first one, so the solver always has work to do. A dip is not the same
as a solvable dip: roughly 7% of seeds reach tier 3 with an empty plan, which is
a wanted outcome — naming a shortfall that no combination of changes closes is
half of what this product is for. Amounts are integer
cents, heavy-tailed rather than uniform; pay lands on business days.

## `POST /api/accounts/nessie`

Additive, and a sibling of the endpoint above rather than a variant of it. Seeds
a modelled account into Capital One's Nessie sandbox, reads it back, and returns
what the sandbox actually holds.

Request body is the same shape as `/api/accounts/sample`:

```jsonc
{
  "seed": 12345,          // optional
  "as_of": "2026-09-19",  // optional
  "horizon_days": 30      // optional; 14..45, default 30
}
```

```jsonc
{
  "seed": 12345,
  "as_of": "2026-09-19",
  "horizon_end": "2026-10-18",
  "opening_balance_cents": 49800,
  "buffer_cents": 2500,
  "scheduled": [ /* ScheduledTxn, as /api/solve takes them */ ],
  "source": "nessie",
  "nessie": {
    "customer_id": "68cd...",   // null in read-only mode if the sandbox omits it
    "account_id": "68ce...",
    "mode": "seeded"            // or "read_only"
  },
  "written": 23,                // rows sent to the sandbox; 0 in read-only mode
  "returned": 23,               // rows in `scheduled`
  "not_round_tripped": [        // every row the sandbox did not return unchanged
    { "id": "n_68cf...", "reason": "amount changed by the sandbox" }
  ]
}
```

**`source` is required and is always the literal `"nessie"`.** Data generated
here and seeded into someone else's sandbox is still generated data; nothing
downstream may present it as a bank's record of anyone.

**Amounts are whole dollars.** The sandbox truncates on write, so the server
rounds before seeding (half away from zero) and what comes back is what was
written. `/api/accounts/sample` is the cent-precise path.

**`opening_balance_cents` is never an arithmetic result.** Writes never move
Nessie's `balance`. In seeded mode the value is the rounded modelled opening
and the sandbox's balance is not read at all; in read-only mode it *is* the
sandbox's balance, which is the frozen creation value and therefore the same
kind of number — an input, not something the sandbox computed.

`not_round_tripped` reasons, one per row, in this precedence: `returned
without a usable id`, `no usable date`, `outside the window`, `written but not
returned`, `amount rounds to zero dollars` (under fifty cents, so rounding left
nothing to write), `amount changed by the sandbox`.

A row the sandbox returns with no id, or with one the contract's id pattern
refuses, cannot be named by its id — that is the defect. It is dropped from
`scheduled` and counted under a placeholder id of the form
`n_unidentified_<resource>_<n>`, so the loss is stated rather than silent. The first two are dropped from `scheduled`; the last keeps the
sandbox's value, because that is what the sandbox holds.

**Errors.** `503` when no key is configured, when the sandbox returns nothing,
or when what it returns normalises to no usable rows — never an empty account,
because a wrong key answers `200 []` exactly as a real but empty account does.
`502` when the sandbox fails mid-seed or answers something malformed; the
message says how many rows were already written, because creates here are
permanent.

Setting `NESSIE_ACCOUNT_ID` on the server makes this endpoint read that account
instead of seeding: no writes, `mode: "read_only"`, `written: 0`. See
`docs/features/nessie.md`.

**Three rules the server cannot enforce**, for any client rendering these
accounts: clear every lock when the account changes (the ids do not carry
over); pin `limit` to 18 on the candidates call that follows; and treat a 5xx
with no `detail` as unreachable rather than as a refusal, because a dead backend
behind the dev proxy answers with an empty 500.

Responses: `200` with the body above, or `422` when `horizon_days` is out of
range, `as_of` is not an ISO date, or an unknown field is sent.


## `POST /api/accounts/import`

Plans from a person's own bank export. Additive: `/api/solve` and
`/api/candidates` are unchanged, and a client that never imports never calls
this. Stateless like everything else — the rows are planned and forgotten.

The browser parses the CSV; this endpoint takes rows, not a file.

```jsonc
{
  "rows": [                            // 1..20000
    { "date": "2026-08-04",            // YYYY-MM-DD, 1970-01-01..2100-12-31
      "description": "KROGER #382",    // 1..200 chars, used and never returned
      "amount_cents": -2500 }          // signed, non-zero, |amount| <= 10^8
  ],
  "as_of": "2026-09-21",               // optional, default the server's today
  "horizon_days": 30,                  // optional, 14..45
  "opening_balance_cents": 41280,      // required: exports carry no balance.
                                       // The balance INCLUDING anything that
                                       // posted today — see the cutoff below.
  "buffer_cents": 2500                 // optional, default 2500
}
```

```jsonc
{
  "as_of": "2026-09-21",
  "horizon_end": "2026-10-20",
  "opening_balance_cents": 41280,
  "buffer_cents": 2500,
  "scheduled": [ /* ScheduledTxn, exactly as /api/solve accepts them */ ],
  "candidates": [ /* Candidate, likewise */ ],
  "meta": { /* the same CandidatesMeta /api/candidates returns */ },
  "source": "import",
  "streams": [
    { "id": "s_001",
      "kind": "income",                // income | bill | discretionary
      "label": "Income (weekly)",      // from the CATEGORY, never the brand
      "category": "unknown",
      "cadence": "weekly",             // weekly | biweekly | semimonthly | monthly
      "anchor": "Tuesday",
      "amount_cents": 47500,
      "occurrences": 35,
      "last_seen": "2026-09-16",
      "active": true,                  // false = lapsed, nothing projected
      "source_row_indexes": [3, 10],   // indexes into the REQUEST's rows
      "projected_ids": ["t_s_001_01"] }
  ],
  "provenance": {
    "history_start": "2024-08-19", "history_end": "2026-09-18",
    "history_days": 761, "imputed_zero_days": 421, "rows_used": 1060,
    "weeks_used_for_assumed": 8,
    "assumed_method": "same_weekday_8_week_median",  // null if under 56 days
    "assumed_ids": ["f_20260922"],
    "next_payday": "2026-09-22", "pay_cadence": "weekly",
    "income_not_counted_today": ["s_001"],   // due today, not yet posted
    "income_already_posted": ["s_002"],      // its period is already in the balance
    "stale_days": 3,
    "unscheduled_inflow_count": 165, "unscheduled_inflow_cents": 220000,
    "truncated_assumed_rows": 0,
    "rejected_rows": [{ "index": 7, "reason": "after_as_of" }]
  }
}
```

**No merchant name is ever returned.** Descriptions are needed to group and
classify and are used for nothing else; every row and candidate in the
response is labelled from its lexicon category. That is also why this route's
422 body carries neither `input` nor `ctx` — FastAPI's default echoes the
offending value, which for a missing field is the whole row and for an
oversized list is the whole statement. Every other route's 422 body is
unchanged.

**Assumed rows** have ids beginning `f_`, `kind: "discretionary"`,
`recurring: false`, and a description beginning `Everyday spending (assumed`.
They are an estimate — the median of the same weekday over the last eight
weeks — and **no candidate ever targets one**: the solver plans around
assumed spending and never proposes cancelling it. A client must not present
them as transactions that exist.

**The balance cutoff.** `opening_balance_cents` includes everything posted
through `as_of`. An income occurrence due on `as_of` is therefore *not*
projected — if it posted it is already in the balance, and if it has not,
counting it is optimistic — and its stream id appears in
`income_not_counted_today`. More generally, an occurrence is skipped when a
posted row in the export matches it: each row is assigned to the occurrence
it is NEAREST to, so a payment that arrived early or late settles the
occurrence it belongs to rather than its neighbour's. A row further than
half an interval from every occurrence matches none. Matching is per
stream, never per payee: two subscriptions at one merchant share a payee
and only one may have been taken.

`stale_days` is the raw gap between the last exported day and `as_of`, always
present and often zero. It is a NUMBER, not a flag: do not read non-zero as
stale. This app's own threshold is seven days.

**Rejections, never silent drops.** A row after `as_of` or more than three
years old is reported in `rejected_rows` with its index. If nothing survives,
the answer is a 422 rather than an empty plan.

Responses: `200` with the body above; `422` for malformed input, for fewer
than ten usable rows, for a history where every row was rejected, for a
projection that would exceed the 2000-row schedule limit, and for a recurring
charge or a day's spending too large to fit a scheduled amount (rows are
capped individually, but a day is the sum of its rows). Assumed rows are truncated before any detected row is
dropped, and the count appears in `truncated_assumed_rows`.

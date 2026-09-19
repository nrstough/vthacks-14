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

Responses: `200` with the body above, or `422` when `horizon_days` is out of
range, `as_of` is not an ISO date, or an unknown field is sent.

# API contract — `POST /api/solve`

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
  "locks": { "in": ["c_cancel_gym"], "out": [] }  // user overrides
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
      "date": "2026-09-22",           // the day the user must act
      "freed_cents": 3180,
      "pain": 2,
      "reason": "Covers the Sep 24 dip."
    }
  ],
  "certificate": {
    "irredundant": true,
    "sentence": "Remove any one and you're $41 under on the 24th.",
    "per_item": [
      { "candidate_id": "c_skip_dd", "worst_shortfall_cents": 4100, "worst_date": "2026-09-24" }
    ]
  },
  "shortfall": {                      // what remains AFTER the plan
    "worst_cents": 0,                 // 0 when the plan clears zero
    "worst_date": null,
    "total_cents": 0
  },
  "external_cash_needed": null,       // tier 3 only: { amount_cents, by_date }
  "balances": [                       // one row per day, as_of..horizon_end
    {
      "date": "2026-09-19",
      "baseline_cents": 18432,        // do-nothing end-of-day balance
      "with_plan_cents": 18432,       // end-of-day balance under the plan
      "is_payday": false,
      "changes_here": []              // candidate_ids taking effect this day
    }
  ],
  "meta": { "solver": "cp-sat", "status": "OPTIMAL", "wall_ms": 84, "candidates_considered": 22 }
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

Lexicographic, minimised in order:

1. worst shortfall below zero
2. total below-buffer exposure
3. number of changes (cardinality)
4. total pain
5. hysteresis, changes against the previous plan
6. candidate id, for a deterministic tiebreak

## Notes

- `balances` is the chart's only input. The red fill is drawn wherever a series
  goes below zero; the with-plan line steps at each `changes_here` date.
- `certificate.sentence` is rendered verbatim. The solver owns the wording.
- Locking a candidate in or out re-posts the whole request. There is no
  incremental endpoint and no session state on the server.

import type { SolveRequest, SolveResponse } from '../types'

// Every figure the dashboard tiles show, derived from the response and nothing
// else. Two rules govern this file.
//
// First, no invented units. The contract carries no fee schedule, so there is
// no honest "fees avoided" figure in dollars; what the solver actually
// minimises first is days below zero, so that is what is counted here. A $35
// NSF rate multiplied by a day count would be a number this product does not
// have.
//
// Second, the tiles must agree with the sentences beside them. The tie rule for
// the lowest day matches narrate.ts (strictly-less-than, scanning forward, so
// the first day wins a tie), and at tier 3 the low point is read from
// `shortfall` for the same reason narrate.ts reads it there: recomputing it
// from `balances` can land on a different day from the qualifier.

export interface LowPoint {
  cents: number
  date: string | null
}

/** Lowest balance once the plan is applied. */
export function lowestWithPlan(res: SolveResponse): LowPoint {
  // Tier 3 means money is still missing. `shortfall` is the solver's own
  // account of what remains, and the verdict text is built from it.
  if (res.tier === 3 && res.shortfall.worst_date !== null) {
    return { cents: -res.shortfall.worst_cents, date: res.shortfall.worst_date }
  }
  if (res.balances.length === 0) return { cents: 0, date: null }
  let best = res.balances[0]
  for (const row of res.balances) {
    if (row.with_plan_cents < best.with_plan_cents) best = row
  }
  return { cents: best.with_plan_cents, date: best.date }
}

/** Lowest balance if nothing is changed at all. */
export function lowestDoingNothing(res: SolveResponse): LowPoint {
  if (res.balances.length === 0) return { cents: 0, date: null }
  let best = res.balances[0]
  for (const row of res.balances) {
    if (row.baseline_cents < best.baseline_cents) best = row
  }
  return { cents: best.baseline_cents, date: best.date }
}

/** How much room is left above the cushion on the worst day. Signed. */
export function headroom(res: SolveResponse, req: SolveRequest): number {
  return lowestWithPlan(res).cents - req.buffer_cents
}

export interface DaysUnder {
  doingNothing: number
  withPlan: number
  avoided: number
}

/**
 * Days the balance spends below zero, with and without the plan. A count, never
 * a sum of money: the product does not know what any given bank charges.
 */
export function daysUnder(res: SolveResponse): DaysUnder {
  const doingNothing = res.balances.filter((b) => b.baseline_cents < 0).length
  const withPlan = res.balances.filter((b) => b.with_plan_cents < 0).length
  return { doingNothing, withPlan, avoided: doingNothing - withPlan }
}

/**
 * How many of the plan's changes are needed to clear zero, as opposed to the
 * ones that only hold the cushion.
 */
export function loadBearing(res: SolveResponse): number {
  return res.plan.filter((p) => p.strictly_needed).length
}

/**
 * The wording for a count of changes. Minimality is a claim about the search,
 * so it is made only on a solve that proved it — the same gate VerdictBand and
 * narrate.ts apply.
 */
export function planClaim(res: SolveResponse): string {
  if (res.plan.length === 0) return 'Nothing to change'
  if (!res.certificate.minimal_proven) return 'Smallest set not proven: the solver ran out of time'
  if (res.certificate.irredundant) return 'Smallest set, every one load-bearing'
  return 'Smallest set proven'
}

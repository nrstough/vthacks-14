// Words for the things the chart and the footer say in pictures.
//
// The chart carries the whole argument and a screen reader gets nothing from
// several hundred SVG nodes. This builds the text equivalent, which doubles as
// demo narration. Like reasons.ts, it derives everything from the response:
// the only arithmetic is finding a minimum and counting days.

import type { SolveResponse } from '../types'
import { money, shortDate } from './format.ts'

interface Low {
  date: string
  cents: number
}

// Strictly less than, scanning forward, so a tie keeps the FIRST day — the same
// rule the solver uses for its own "tightest day" and worst_date.
function lowest(rows: SolveResponse['balances'], pick: (r: SolveResponse['balances'][number]) => number): Low | null {
  let best: Low | null = null
  for (const row of rows) {
    const cents = pick(row)
    if (best === null || cents < best.cents) best = { date: row.date, cents }
  }
  return best
}

function list(dates: string[]): string {
  const parts = dates.map(shortDate)
  if (parts.length === 1) return parts[0]
  if (parts.length === 2) return `${parts[0]} and ${parts[1]}`
  return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`
}

export function narrateChart(res: SolveResponse): string[] {
  const out: string[] = []

  const base = lowest(res.balances, (r) => r.baseline_cents)
  if (base) {
    out.push(
      base.cents < 0
        ? `Doing nothing, the balance bottoms out at ${money(base.cents)} on ${shortDate(base.date)}.`
        : `Doing nothing, the lowest point is ${money(base.cents)} on ${shortDate(base.date)}.`,
    )
  }

  // At tier 3 the solver has already named the worst remaining point; use its
  // own figures rather than recomputing them from the rows.
  if (res.tier === 3 && res.shortfall.worst_date) {
    out.push(
      `With the plan, the balance is still ${money(-res.shortfall.worst_cents)} on ${shortDate(
        res.shortfall.worst_date,
      )}.`,
    )
  } else {
    const plan = lowest(res.balances, (r) => r.with_plan_cents)
    if (plan) {
      out.push(`With the plan, the lowest point is ${money(plan.cents)} on ${shortDate(plan.date)}.`)
    }
  }

  const paydays = res.balances.filter((r) => r.is_payday).map((r) => r.date)
  out.push(
    paydays.length === 0
      ? 'No payday falls in this window.'
      : `Payday lands on ${list(paydays)}.`,
  )

  // Count the changes, not the days they fall on: two changes on one date is
  // still two changes, and the singular sentence would be false.
  const changeRows = res.balances.filter((r) => r.changes_here.length > 0)
  const changeDays = changeRows.map((r) => r.date)
  const changeCount = changeRows.reduce((n, r) => n + r.changes_here.length, 0)
  if (changeCount === 0) {
    out.push('No changes take effect.')
  } else if (changeCount === 1) {
    out.push(`One change takes effect, on ${shortDate(changeDays[0])}.`)
  } else {
    out.push(`Changes take effect on ${list(changeDays)}.`)
  }

  return out
}

export interface EmptyPlanText {
  heading: string
  body: string
}

// An empty plan means two opposite things. At tiers 1 and 2 it means the
// schedule already clears. At tier 3 it means nothing is left that could help,
// and saying "no changes needed" there would be a flat lie — the verdict band
// is simultaneously naming the money the user has to find.
export function emptyPlanText(res: SolveResponse): EmptyPlanText {
  if (res.tier === 3) {
    // Nothing was on the table at all: every change is ruled out or past its
    // deadline. Only then can we say so.
    if (res.meta.candidates_considered === 0) {
      return {
        heading: 'No changes available',
        body: 'Everything is ruled out or too late to act. The gap stays.',
      }
    }
    // Changes remain, and none of them helps. Rule out all but Netflix on the
    // $200 account and this is what happens: it is actionable, it just lands
    // after the day the balance goes under. Claiming it was unavailable would
    // be false, and the user can see the row sitting there.
    return res.certificate.minimal_proven
      ? {
          heading: 'No change helps here',
          body: 'None of the changes still on the table would leave you fewer days below zero.',
        }
      : {
          heading: 'No change was found to help',
          body: 'Nothing on the table helped in the time the solver had.',
        }
  }
  return {
    heading: 'No changes needed',
    body: 'Nothing to change. The schedule already clears on its own.',
  }
}

export function footerLines(res: SolveResponse): string[] {
  return [
    res.certificate.minimal_proven
      ? 'Exact solver, smallest plan proven'
      : 'Exact solver, smallest plan not proven: it ran out of time',
    `Solved in ${res.meta.wall_ms} ms`,
    `${res.meta.candidates_considered} change${res.meta.candidates_considered === 1 ? '' : 's'} considered`,
  ]
}

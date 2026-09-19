// "Can I send this now without breaking the reserve, and if not, when?"
//
// A walk over dated signed amounts, not a covering optimisation — the solver is
// not involved and /api/solve is never called. Every value is base units.

import type { Entry, Outlook, Verdict } from './types.ts'

/**
 * Net every entry falling on one date into a single delta, then walk the dates.
 *
 * This is not a tidying step, it is the correctness requirement. A walk that
 * visited entries one at a time would report a different running minimum
 * depending on the order they happen to sit in the array: opening 60 with a
 * same-day -20 and +20 gives a minimum of 40 or 60 purely by luck. Dates carry
 * no intraday ordering, so there is no honest tie-break available — the only
 * defensible reading is the day's closing balance.
 *
 * backend/app/solver/simulate.py:39-41 and src/solver/mockSolver.ts:60-62 both
 * net by day for the same reason; this is that invariant, in base units.
 */
function netByDay(entries: readonly Entry[], asOf: string, horizonEnd: string): Map<string, bigint> {
  const delta = new Map<string, bigint>()
  for (const e of entries) {
    // Entries before the window are already reflected in the opening balance,
    // and entries after it are not this horizon's business.
    if (e.date < asOf || e.date > horizonEnd) continue
    delta.set(e.date, (delta.get(e.date) ?? 0n) + e.amount)
  }
  return delta
}

/**
 * The running minimum over the horizon and where it falls.
 *
 * `opening` is the balance as at `asOf`, before any entry in the window. The
 * minimum is taken over the closing balance of every day that has activity, and
 * over `opening` itself — a horizon whose first entry is an inflow still has its
 * worst moment at the start.
 */
export function walk(
  opening: bigint,
  entries: readonly Entry[],
  reserve: bigint,
  asOf: string,
  horizonEnd: string,
): Outlook {
  const delta = netByDay(entries, asOf, horizonEnd)
  const days = [...delta.keys()].sort()

  let running = opening
  let minimum = opening
  let minimumDate = asOf
  let breachDate: string | null = opening < reserve ? asOf : null

  for (const day of days) {
    running += delta.get(day) ?? 0n
    if (running < minimum) {
      minimum = running
      minimumDate = day
    }
    if (breachDate === null && running < reserve) breachDate = day
  }

  return {
    minimum,
    minimumDate,
    breachDate,
    shortfall: minimum < reserve ? reserve - minimum : 0n,
  }
}

/** The outlook if `amount` also leaves the wallet on `date`. */
export function withPayment(
  opening: bigint,
  entries: readonly Entry[],
  reserve: bigint,
  asOf: string,
  horizonEnd: string,
  amount: bigint,
  date: string,
): Outlook {
  const payment: Entry = { id: '__payment', date, amount: -amount, label: 'This payment' }
  return walk(opening, [...entries, payment], reserve, asOf, horizonEnd)
}

/** Every date in the window that has activity, plus asOf, in order. */
function candidateDates(entries: readonly Entry[], asOf: string, horizonEnd: string): string[] {
  const dates = new Set<string>([asOf])
  for (const e of entries) {
    if (e.date >= asOf && e.date <= horizonEnd) dates.add(e.date)
  }
  return [...dates].sort()
}

/**
 * The first date the same payment clears, or null if none does in the horizon.
 *
 * This feature cannot exist without a dated inflow. With outflows only, delaying
 * a payment inside a fixed horizon can never raise the running minimum — the same
 * obligations still fall due, so the answer is always "now" or "never" and the
 * function is a constant dressed as a search. Codex review finding 1.
 *
 * Obligations are carried forward unchanged; only the payment's date moves.
 */
export function earliestAffordableDate(
  opening: bigint,
  entries: readonly Entry[],
  reserve: bigint,
  asOf: string,
  horizonEnd: string,
  amount: bigint,
): string | null {
  for (const date of candidateDates(entries, asOf, horizonEnd)) {
    if (withPayment(opening, entries, reserve, asOf, horizonEnd, amount, date).breachDate === null) {
      return date
    }
  }
  return null
}

/**
 * The sentence that goes on screen, and whether it may enable Sign.
 *
 * Two verdicts are kept apart deliberately. `affordable` is unconditional: the
 * schedule as it stands holds. `conditional` describes a schedule nobody has
 * brought about yet. Only the first may enable an irreversible transfer, so
 * collapsing them into one phrase would erase the distinction that gates it.
 */
export function verdictFor(
  opening: bigint,
  entries: readonly Entry[],
  reserve: bigint,
  asOf: string,
  horizonEnd: string,
  amount: bigint,
  date: string,
  format: (base: bigint) => string,
): Verdict {
  const outlook = withPayment(opening, entries, reserve, asOf, horizonEnd, amount, date)
  if (outlook.breachDate === null) {
    return {
      kind: 'affordable',
      text: `Affordable under the current schedule: the balance stays sufficient under the schedule shown, at its lowest ${format(outlook.minimum)} on ${outlook.minimumDate}.`,
      outlook,
      earliestDate: date,
    }
  }

  const earliest = earliestAffordableDate(opening, entries, reserve, asOf, horizonEnd, amount)
  if (earliest !== null) {
    return {
      kind: 'conditional',
      text: `This breaks the reserve on ${outlook.breachDate} by ${format(outlook.shortfall)}. The same payment clears on ${earliest}.`,
      outlook,
      earliestDate: earliest,
    }
  }

  // No date in the horizon clears, so name the money and the date rather than
  // the word this product never uses.
  return {
    kind: 'never_clears',
    text: `This breaks the reserve on ${outlook.breachDate}. Sending it needs ${format(outlook.shortfall)} more by ${outlook.breachDate}.`,
    outlook,
    earliestDate: null,
  }
}

/** Only an unconditional verdict may enable an irreversible transfer. */
export function canSign(verdict: Verdict): boolean {
  return verdict.kind === 'affordable'
}

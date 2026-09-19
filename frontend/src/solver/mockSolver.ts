// Reference implementation of POST /api/solve, kept as the frontend's local
// solver and as the oracle the Python CP-SAT solver is checked against.
//
// Exhaustive search over candidate subsets with the same lexicographic
// objective the CP-SAT model uses. Candidate counts here are small (< 16), so
// brute force is exact and instant. Keeping it around after the backend exists
// is useful: it is an independent reference the CP-SAT model can be tested
// against, which is how the research memo validated the formulation.

import { money, shortDate } from '../lib/format'
import type {
  BalanceRow,
  Candidate,
  CertificateItem,
  PlanItem,
  SolveRequest,
  SolveResponse,
} from '../types'

/* ---------- dates ---------- */

const DAY_MS = 86_400_000

function toUTC(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y, m - 1, d)
}

function fromUTC(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

export function dayRange(start: string, end: string): string[] {
  const out: string[] = []
  for (let t = toUTC(start); t <= toUTC(end); t += DAY_MS) out.push(fromUTC(t))
  return out
}

export function daysBetween(a: string, b: string): number {
  return Math.round((toUTC(b) - toUTC(a)) / DAY_MS)
}

/* ---------- balance simulation ---------- */

interface Trace {
  balances: number[] // end-of-day, one per day in the horizon
  daysBelowZero: number
  worstShortfall: number // positive cents below zero, 0 if never negative
  worstShortfallDate: string | null
  firstBelowZeroDate: string | null // the day you need money BY, not the deepest day
  belowBufferExposure: number // total cents of buffer eaten, summed over days
  minBalance: number
}

function simulate(req: SolveRequest, chosen: Candidate[], days: string[]): Trace {
  // Daily net delta from the do-nothing schedule.
  const delta = new Map<string, number>()
  for (const t of req.scheduled) {
    delta.set(t.date, (delta.get(t.date) ?? 0) + t.amount_cents)
  }
  // A chosen candidate frees cash on its effective date and, if it is a
  // deferral, gives it back on the recharge date.
  for (const c of chosen) {
    delta.set(c.effective_date, (delta.get(c.effective_date) ?? 0) + c.freed_cents)
    if (c.recharge_date) {
      delta.set(c.recharge_date, (delta.get(c.recharge_date) ?? 0) - c.freed_cents)
    }
  }

  const balances: number[] = []
  let running = req.opening_balance_cents
  let daysBelowZero = 0
  let worstShortfall = 0
  let worstShortfallDate: string | null = null
  let firstBelowZeroDate: string | null = null
  let belowBufferExposure = 0
  let minBalance = Number.POSITIVE_INFINITY

  for (const day of days) {
    running += delta.get(day) ?? 0
    balances.push(running)
    if (running < minBalance) minBalance = running
    if (running < 0) {
      daysBelowZero += 1
      if (firstBelowZeroDate === null) firstBelowZeroDate = day
      if (-running > worstShortfall) {
        worstShortfall = -running
        worstShortfallDate = day
      }
    }
    if (running < req.buffer_cents) belowBufferExposure += req.buffer_cents - running
  }

  return {
    balances,
    daysBelowZero,
    worstShortfall,
    worstShortfallDate,
    firstBelowZeroDate,
    belowBufferExposure,
    minBalance,
  }
}

/* ---------- objective ---------- */

interface Score {
  nums: number[]
  ids: string[] // sorted, compared only when every number ties
}

// Lexicographic, every term minimised. Lower is better at the first term
// where two plans differ.
//
// Cushion-reached is a yes-or-no term ABOVE cardinality, and the size of the
// cushion shortfall sits below it. Ranking the cushion's size above the number
// of changes made the solver add changes purely to pad, which contradicts the
// product's headline claim of the smallest set. Across a sweep of opening
// balances the two orders pick different plans about a quarter of the time,
// and this one picks fewer changes wherever they differ.
function scoreOf(
  trace: Trace,
  chosen: Candidate[],
  previousPlan: string[],
  bufferCents: number,
): Score {
  const pain = chosen.reduce((s, c) => s + c.pain, 0)
  const prev = new Set(previousPlan)
  const now = new Set(chosen.map((c) => c.id))
  let hysteresis = 0
  for (const id of now) if (!prev.has(id)) hysteresis += 1
  for (const id of prev) if (!now.has(id)) hysteresis += 1

  return {
    nums: [
      trace.daysBelowZero, // 1. fee-triggering days
      trace.worstShortfall, // 2. worst dip below zero
      trace.minBalance >= bufferCents ? 0 : 1, // 3. did any plan reach the cushion
      chosen.length, // 4. how many changes
      trace.belowBufferExposure, // 5. how much cushion is eaten
      pain, // 6. disruption
      hysteresis, // 7. churn against the last plan
    ],
    ids: chosen.map((c) => c.id).sort(),
  }
}

// The final tiebreak is the lexicographically smallest sorted id tuple. It is
// a real ordering, unlike the character-code sum this used to use, which was
// a hash: it collided on anagrams and could not be reproduced by any solver.
// Cardinality is an earlier term, so the two tuples are the same length here.
function scoreLess(a: Score, b: Score): boolean {
  for (let i = 0; i < a.nums.length; i++) {
    if (a.nums[i] !== b.nums[i]) return a.nums[i] < b.nums[i]
  }
  for (let i = 0; i < Math.max(a.ids.length, b.ids.length); i++) {
    const x = a.ids[i] ?? ''
    const y = b.ids[i] ?? ''
    if (x !== y) return x < y
  }
  return false
}

// No transaction may be changed two ways at once. Without this, a generated
// candidate list offering both "skip the $31.80 order" and "trim it by $15.90"
// lets the solver take both and free $47.70 from a $31.80 charge, understating
// what the user actually needs while reporting the result as optimal.
function hasDuplicateTarget(chosen: Candidate[]): boolean {
  const seen = new Set<string>()
  for (const c of chosen) {
    if (seen.has(c.target_txn_id)) return true
    seen.add(c.target_txn_id)
  }
  return false
}

/* ---------- solve ---------- */

export function solve(req: SolveRequest, previousPlan: string[] = []): SolveResponse {
  const started = performance.now()
  const days = dayRange(req.as_of, req.horizon_end)
  if (days.length === 0) {
    throw new Error(
      `horizon_end (${req.horizon_end}) is before as_of (${req.as_of}); there are no days to plan over`,
    )
  }

  const lockedIn = new Set(req.locks.in)
  const lockedOut = new Set(req.locks.out)

  // Lead time: a move you can no longer action in time is not on the table.
  const actionable = req.candidates.filter(
    (c) => daysBetween(req.as_of, c.effective_date) >= c.lead_time_days && !lockedOut.has(c.id),
  )
  // If the caller pins two changes on one transaction, keep the first by id so
  // the rule below still holds rather than throwing in the user's face.
  const pinned = actionable.filter((c) => lockedIn.has(c.id)).sort((a, b) => (a.id < b.id ? -1 : 1))
  const forced: Candidate[] = []
  for (const c of pinned) if (!hasDuplicateTarget([...forced, c])) forced.push(c)
  const forcedTargets = new Set(forced.map((c) => c.target_txn_id))
  const free = actionable.filter(
    (c) => !lockedIn.has(c.id) && !forcedTargets.has(c.target_txn_id),
  )

  if (free.length > 20) throw new Error('mock solver is exhaustive; keep candidates under 20')

  let best: Candidate[] = []
  let bestTrace = simulate(req, forced, days)
  let bestScore = scoreOf(bestTrace, forced, previousPlan, req.buffer_cents)

  for (let mask = 1; mask < 1 << free.length; mask++) {
    const chosen = forced.slice()
    for (let i = 0; i < free.length; i++) if (mask & (1 << i)) chosen.push(free[i])
    if (hasDuplicateTarget(chosen)) continue
    const trace = simulate(req, chosen, days)
    const score = scoreOf(trace, chosen, previousPlan, req.buffer_cents)
    if (scoreLess(score, bestScore)) {
      best = chosen
      bestTrace = trace
      bestScore = score
    }
  }
  if (best.length === 0 && forced.length > 0) best = forced


  /* tier */
  let tier: 1 | 2 | 3
  if (bestTrace.worstShortfall > 0) tier = 3
  else if (bestTrace.minBalance < req.buffer_cents) tier = 2
  else tier = 1

  /* irredundancy certificate: drop one item at a time, re-verify against zero */
  // A change earns its place if dropping it makes things MEASURABLY worse than
  // the plan already is. The old test asked only whether the plan-without-it
  // went below zero, which is automatically true at tier 3 where the plan is
  // below zero anyway. That made the proof pass vacuously in exactly the case
  // it mattered most, and print a sentence that was false on its face.
  const perItem: CertificateItem[] = best.map((c) => {
    const without = best.filter((o) => o.id !== c.id)
    const t = simulate(req, without, days)
    return {
      candidate_id: c.id,
      worst_shortfall_cents: t.worstShortfall,
      worst_date: t.worstShortfallDate,
      // How much deeper the dip gets without this one change.
      marginal_cents: t.worstShortfall - bestTrace.worstShortfall,
      marginal_days: t.daysBelowZero - bestTrace.daysBelowZero,
    }
  })
  const loadBearing = (p: CertificateItem) => p.marginal_cents > 0 || p.marginal_days > 0
  const irredundant = perItem.length > 0 && perItem.every(loadBearing)
  const worstItem = perItem.reduce<CertificateItem | null>(
    (acc, p) => (acc === null || p.marginal_cents > acc.marginal_cents ? p : acc),
    null,
  )

  const doNothing = simulate(req, [], days)
  const planClearsZero = bestTrace.worstShortfall === 0
  let sentence: string
  if (best.length === 0) {
    sentence = 'No changes needed. The schedule already clears.'
  } else if (!planClearsZero) {
    // Tier 3. Be explicit that the plan itself does not clear, then say what
    // the changes are still buying.
    sentence = irredundant
      ? `This plan does not clear on its own, so nothing here is optional. Drop any one change and the gap grows by up to ${money(
          worstItem?.marginal_cents ?? 0,
        )}.`
      : `This plan does not clear on its own. Some of these changes are holding the cushion rather than closing the gap.`
  } else if (irredundant && worstItem?.worst_date) {
    sentence = `Every change is load-bearing. Remove any one and you go under on ${shortDate(
      worstItem.worst_date,
    )}, by as much as ${money(worstItem.worst_shortfall_cents)}.`
  } else if (worstItem && worstItem.marginal_cents > 0 && worstItem.worst_date) {
    sentence = `Remove ${
      best.find((c) => c.id === worstItem.candidate_id)?.label ?? 'the largest change'
    } and you go under on ${shortDate(worstItem.worst_date)} by ${money(
      worstItem.worst_shortfall_cents,
    )}. The rest hold the cushion.`
  } else {
    sentence = 'Every change here is keeping you above the cushion, not above zero.'
  }

  /* plan rows, ordered by the day the user has to act */
  const byDate = (a: Candidate, b: Candidate) => a.effective_date.localeCompare(b.effective_date)
  const plan: PlanItem[] = best
    .slice()
    .sort(byDate)
    .map((c) => {
      const cert = perItem.find((p) => p.candidate_id === c.id)
      const needed = cert ? loadBearing(cert) : false
      let reason: string
      if (cert && needed && cert.worst_date && !planClearsZero) {
        reason = `Without it the gap grows to ${money(cert.worst_shortfall_cents)} on ${shortDate(
          cert.worst_date,
        )}.`
      } else if (cert && needed && cert.worst_date) {
        reason = `Without it you are ${money(cert.worst_shortfall_cents)} under on ${shortDate(
          cert.worst_date,
        )}.`
      } else {
        reason = 'Holds the cushion; not strictly needed to clear zero.'
      }
      return {
        candidate_id: c.id,
        label: c.label,
        detail: c.detail,
        action: c.action,
        date: c.effective_date,
        freed_cents: c.freed_cents,
        pain: c.pain,
        strictly_needed: needed,
        reason,
      }
    })

  /* verdict wording; never the word infeasible */
  const tightest = days[bestTrace.balances.indexOf(bestTrace.minBalance)]
  const n = plan.length
  const changeWord = n === 1 ? 'one change' : `${['zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve'][n] ?? n} changes`
  let verdict: string
  let qualifier: string

  if (tier === 1) {
    verdict =
      n === 0
        ? `You stay above zero through ${shortDate(req.horizon_end)} with no changes.`
        : `Make ${changeWord} and you stay above zero through ${shortDate(req.horizon_end)}.`
    qualifier = `Tightest day is ${shortDate(tightest)} at ${money(
      bestTrace.minBalance,
    )}, ${money(bestTrace.minBalance - req.buffer_cents)} over the cushion. Sufficient under the schedule shown.`
  } else if (tier === 2) {
    verdict =
      n === 0
        ? `You clear zero through ${shortDate(req.horizon_end)} with no changes, but nothing is left over.`
        : `Make ${changeWord} and you clear zero through ${shortDate(req.horizon_end)}, with no room left.`
    qualifier = `Tightest day is ${shortDate(tightest)} at ${money(
      bestTrace.minBalance,
    )}, under the ${money(req.buffer_cents)} cushion. One surprise charge puts you over.`
  } else {
    verdict =
      n === 0
        ? `You need ${money(bestTrace.worstShortfall)} more by ${shortDate(
            bestTrace.firstBelowZeroDate!,
          )}. There are no changes available to close any of it.`
        : `You need ${money(bestTrace.worstShortfall)} more by ${shortDate(
            bestTrace.firstBelowZeroDate!,
          )}. No combination of these changes closes the gap on its own.`
    qualifier =
      n === 0
        ? `Nothing on this account can be changed in time. The dip is ${money(
            bestTrace.worstShortfall,
          )} at its deepest, on ${shortDate(bestTrace.worstShortfallDate!)}.`
        : `This is the best partial plan. ${changeWord[0].toUpperCase()}${changeWord.slice(1)} ${
            n === 1 ? 'takes' : 'take'
          } the dip from ${money(doNothing.worstShortfall)} down to ${money(
            bestTrace.worstShortfall,
          )}. Everything else is already on the table.`
  }

  /* per-day rows for the chart */
  const baseline = doNothing
  const changesByDay = new Map<string, string[]>()
  for (const c of best) {
    changesByDay.set(c.effective_date, [...(changesByDay.get(c.effective_date) ?? []), c.id])
  }
  const paydays = new Set(req.scheduled.filter((t) => t.kind === 'income').map((t) => t.date))

  const balances: BalanceRow[] = days.map((date, i) => ({
    date,
    baseline_cents: baseline.balances[i],
    with_plan_cents: bestTrace.balances[i],
    is_payday: paydays.has(date),
    changes_here: changesByDay.get(date) ?? [],
  }))

  return {
    tier,
    verdict,
    qualifier,
    plan,
    certificate: { irredundant, sentence, per_item: perItem },
    shortfall: {
      worst_cents: bestTrace.worstShortfall,
      worst_date: bestTrace.worstShortfallDate,
      total_cents: bestTrace.balances.filter((b) => b < 0).reduce((s, b) => s - b, 0),
    },
    external_cash_needed:
      tier === 3
        ? {
            // Enough to cover the deepest point, and it has to be there by the
            // FIRST day you go under, which can be earlier than the deepest day.
            amount_cents: bestTrace.worstShortfall,
            by_date: bestTrace.firstBelowZeroDate!,
          }
        : null,
    balances,
    meta: {
      solver: 'brute-force (frontend stand-in)',
      status: 'OPTIMAL',
      wall_ms: Math.round((performance.now() - started) * 10) / 10,
      candidates_considered: actionable.length,
    },
  }
}

export function unusedCandidates(req: SolveRequest, res: SolveResponse): Candidate[] {
  const used = new Set(res.plan.map((p) => p.candidate_id))
  return req.candidates.filter((c) => !used.has(c.id))
}

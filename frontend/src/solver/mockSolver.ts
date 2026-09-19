// STAND-IN for POST /api/solve. Delete this file when the FastAPI solver lands.
//
// Exhaustive search over candidate subsets with the same lexicographic
// objective the CP-SAT model uses. Candidate counts here are small (< 16), so
// brute force is exact and instant. Keeping it around after the backend exists
// is useful: it is an independent reference the CP-SAT model can be tested
// against, which is how the research memo validated the formulation.

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

/* ---------- money ---------- */

export function money(cents: number): string {
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(cents)
  const dollars = Math.floor(abs / 100).toLocaleString('en-US')
  return `${sign}$${dollars}.${String(abs % 100).padStart(2, '0')}`
}

export function shortDate(iso: string): string {
  const [, m, d] = iso.split('-').map(Number)
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return `${months[m - 1]} ${d}`
}

/* ---------- balance simulation ---------- */

interface Trace {
  balances: number[] // end-of-day, one per day in the horizon
  daysBelowZero: number
  worstShortfall: number // positive cents below zero, 0 if never negative
  worstShortfallDate: string | null
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
  let belowBufferExposure = 0
  let minBalance = Number.POSITIVE_INFINITY

  for (const day of days) {
    running += delta.get(day) ?? 0
    balances.push(running)
    if (running < minBalance) minBalance = running
    if (running < 0) {
      daysBelowZero += 1
      if (-running > worstShortfall) {
        worstShortfall = -running
        worstShortfallDate = day
      }
    }
    if (running < req.buffer_cents) belowBufferExposure += req.buffer_cents - running
  }

  return { balances, daysBelowZero, worstShortfall, worstShortfallDate, belowBufferExposure, minBalance }
}

/* ---------- objective ---------- */

// Lexicographic, every term minimised. Lower is better at the first term
// where two candidate plans differ.
function scoreOf(trace: Trace, chosen: Candidate[], previousPlan: string[]): number[] {
  const pain = chosen.reduce((s, c) => s + c.pain, 0)
  const prev = new Set(previousPlan)
  const now = new Set(chosen.map((c) => c.id))
  let hysteresis = 0
  for (const id of now) if (!prev.has(id)) hysteresis += 1
  for (const id of prev) if (!now.has(id)) hysteresis += 1
  const idTiebreak = chosen
    .map((c) => c.id)
    .sort()
    .join(',')
    .split('')
    .reduce((s, ch) => s + ch.charCodeAt(0), 0)

  return [
    trace.daysBelowZero, // 1. fee-triggering days
    trace.worstShortfall, // 2. worst dip below zero
    trace.belowBufferExposure, // 3. cushion eaten
    chosen.length, // 4. cardinality
    pain, // 5. disruption
    hysteresis, // 6. churn against the last plan
    idTiebreak, // 7. deterministic
  ]
}

function lexLess(a: number[], b: number[]): boolean {
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return a[i] < b[i]
  }
  return false
}

/* ---------- solve ---------- */

export function solve(req: SolveRequest, previousPlan: string[] = []): SolveResponse {
  const started = performance.now()
  const days = dayRange(req.as_of, req.horizon_end)

  const lockedIn = new Set(req.locks.in)
  const lockedOut = new Set(req.locks.out)

  // Lead time: a move you can no longer action in time is not on the table.
  const actionable = req.candidates.filter(
    (c) => daysBetween(req.as_of, c.effective_date) >= c.lead_time_days && !lockedOut.has(c.id),
  )
  const forced = actionable.filter((c) => lockedIn.has(c.id))
  const free = actionable.filter((c) => !lockedIn.has(c.id))

  if (free.length > 20) throw new Error('mock solver is exhaustive; keep candidates under 20')

  let best: Candidate[] = []
  let bestTrace = simulate(req, forced, days)
  let bestScore = scoreOf(bestTrace, forced, previousPlan)

  for (let mask = 1; mask < 1 << free.length; mask++) {
    const chosen = forced.slice()
    for (let i = 0; i < free.length; i++) if (mask & (1 << i)) chosen.push(free[i])
    const trace = simulate(req, chosen, days)
    const score = scoreOf(trace, chosen, previousPlan)
    if (lexLess(score, bestScore)) {
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
  const perItem: CertificateItem[] = best.map((c) => {
    const without = best.filter((o) => o.id !== c.id)
    const t = simulate(req, without, days)
    return {
      candidate_id: c.id,
      worst_shortfall_cents: t.worstShortfall,
      worst_date: t.worstShortfallDate,
    }
  })
  const irredundant = perItem.length > 0 && perItem.every((p) => p.worst_shortfall_cents > 0)
  const worstItem = perItem.reduce<CertificateItem | null>(
    (acc, p) => (acc === null || p.worst_shortfall_cents > acc.worst_shortfall_cents ? p : acc),
    null,
  )

  let sentence: string
  if (best.length === 0) {
    sentence = 'No changes needed. The schedule already clears.'
  } else if (irredundant && worstItem?.worst_date) {
    sentence = `Every change is load-bearing. Remove any one and you go under on ${shortDate(
      worstItem.worst_date,
    )}, by as much as ${money(worstItem.worst_shortfall_cents)}.`
  } else if (worstItem?.worst_date) {
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
      const reason =
        cert && cert.worst_shortfall_cents > 0 && cert.worst_date
          ? `Without it you are ${money(cert.worst_shortfall_cents)} under on ${shortDate(cert.worst_date)}.`
          : 'Holds the cushion; not strictly needed to clear zero.'
      return {
        candidate_id: c.id,
        label: c.label,
        detail: c.detail,
        action: c.action,
        date: c.effective_date,
        freed_cents: c.freed_cents,
        pain: c.pain,
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
    verdict = `Make ${changeWord} and you clear zero through ${shortDate(req.horizon_end)}, with no room left.`
    qualifier = `Tightest day is ${shortDate(tightest)} at ${money(
      bestTrace.minBalance,
    )}, under the ${money(req.buffer_cents)} cushion. One surprise charge puts you over.`
  } else {
    verdict = `You need ${money(bestTrace.worstShortfall)} more by ${shortDate(
      bestTrace.worstShortfallDate!,
    )}. No combination of these changes closes the gap on its own.`
    qualifier = `This is the best partial plan. ${changeWord[0].toUpperCase()}${changeWord.slice(1)} ${
      n === 1 ? 'takes' : 'take'
    } the dip from ${money(simulate(req, [], days).worstShortfall)} down to ${money(
      bestTrace.worstShortfall,
    )}. Everything else is already on the table.`
  }

  /* per-day rows for the chart */
  const baseline = simulate(req, [], days)
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
        ? { amount_cents: bestTrace.worstShortfall, by_date: bestTrace.worstShortfallDate! }
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

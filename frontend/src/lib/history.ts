// Adapters between an imported account and the rest of the app.
//
// Everything here is a pure function on purpose. The test runner is plain
// node with no DOM, so anything decided inside a component is untested by
// construction — and the decisions that matter here (what a stream label
// says, what unticking does to the schedule, which rows may carry a
// checkbox) are exactly the ones worth pinning.

import type {
  Candidate,
  ImportAccountResponse,
  ImportRow,
  LoadedAccount,
  SolveRequest,
  Stream,
} from '../types.ts'
import { money, shortDate } from './format.ts'

export const ASSUMED_PREFIX = 'f_'

export function isImport(account: LoadedAccount | null): account is ImportAccountResponse {
  return account !== null && account.source === 'import'
}

export interface ImportRequestBody {
  rows: ImportRow[]
  as_of?: string
  horizon_days?: number
  opening_balance_cents: number
  buffer_cents?: number
}

export function buildImportRequest(
  rows: ImportRow[],
  openingBalanceCents: number,
  bufferCents: number,
  horizonDays = 30,
): ImportRequestBody {
  return {
    rows,
    horizon_days: horizonDays,
    opening_balance_cents: openingBalanceCents,
    buffer_cents: bufferCents,
  }
}

export function toBase(account: ImportAccountResponse): SolveRequest {
  return {
    as_of: account.as_of,
    horizon_end: account.horizon_end,
    opening_balance_cents: account.opening_balance_cents,
    buffer_cents: account.buffer_cents,
    scheduled: account.scheduled,
    candidates: account.candidates,
    locks: { in: [], out: [] },
    previous_plan: [],
  }
}

/**
 * The schedule with one stream's rows removed, and any candidate that pointed
 * at them.
 *
 * Rebuilt from the ORIGINAL response every time rather than from the current
 * base, so re-ticking a stream restores it. Locks are dropped with it: a lock
 * naming a candidate that no longer exists is a 422 on the whole solve, which
 * is how a re-fetch took down the entire plan once before.
 */
export function scheduleAfterUntick(
  account: ImportAccountResponse,
  excluded: ReadonlySet<string>,
  openingBalanceCents: number,
  bufferCents: number,
): SolveRequest {
  const dropped = new Set<string>()
  for (const stream of account.streams) {
    if (excluded.has(stream.id)) for (const id of stream.projected_ids) dropped.add(id)
  }
  return {
    as_of: account.as_of,
    horizon_end: account.horizon_end,
    opening_balance_cents: openingBalanceCents,
    buffer_cents: bufferCents,
    scheduled: account.scheduled.filter((t) => !dropped.has(t.id)),
    candidates: account.candidates.filter((c) => !dropped.has(c.target_txn_id)),
    locks: { in: [], out: [] },
    previous_plan: [],
  }
}

/** A fresh import starts with nothing unticked. */
export function ticksAfterReimport(): Set<string> {
  return new Set<string>()
}

/** Candidate ids that may carry a "Can't do this" box: never an assumed row. */
export function checkboxableIds(candidates: Candidate[]): string[] {
  return candidates.filter((c) => !c.target_txn_id.startsWith(ASSUMED_PREFIX)).map((c) => c.id)
}

const CADENCE_WORD: Record<Stream['cadence'], string> = {
  weekly: 'weekly',
  biweekly: 'every two weeks',
  semimonthly: 'twice a month',
  monthly: 'monthly',
}

export function streamLine(stream: Stream): string {
  const amount = money(Math.abs(stream.amount_cents))
  const when = stream.cadence === 'weekly' || stream.cadence === 'biweekly' ? stream.anchor : stream.anchor
  const tail = stream.active ? `${CADENCE_WORD[stream.cadence]} on ${when}` : 'stopped, not counted'
  return `${stream.label} — ${amount}, ${tail}`
}

/**
 * The sentence that follows the verdict when the plan contains assumed rows.
 *
 * A separate sentence, not an appended clause: tiers 2 and 3 do not end in
 * "Sufficient under the schedule shown", so a clause would read as
 * "...puts you over., where everyday spending...".
 */
export function qualifierNote(account: LoadedAccount | null): string | undefined {
  if (!isImport(account) || account.provenance.assumed_ids.length === 0) return undefined
  return 'Everyday spending here is an assumption from your last eight weeks, not scheduled charges.'
}

export interface PanelModel {
  streams: Stream[]
  assumedLine: string | null
  historyLine: string
  paydayLine: string | null
  staleLine: string | null
  inflowLine: string | null
  truncatedLine: string | null
  todayLine: string | null
}

export function panelModel(account: ImportAccountResponse): PanelModel {
  const p = account.provenance
  const assumedDaily = account.scheduled.filter((t) => t.id.startsWith(ASSUMED_PREFIX))
  const total = assumedDaily.reduce((sum, t) => sum + Math.abs(t.amount_cents), 0)
  const perDay = assumedDaily.length > 0 ? Math.round(total / assumedDaily.length) : 0

  return {
    streams: account.streams,
    assumedLine:
      p.assumed_method === null
        ? 'Not enough history to assume everyday spending, so the plan covers the bills only.'
        : `Everyday spending: about ${money(perDay)} a day, the median of the same weekday over your last ${p.weeks_used_for_assumed} weeks. An assumption, not a charge.`,
    historyLine: `${p.rows_used} transactions, ${shortDate(p.history_start)} to ${shortDate(p.history_end)}${
      p.imputed_zero_days > 0 ? `, ${p.imputed_zero_days} days with nothing spent` : ''
    }.`,
    paydayLine: p.next_payday ? `Next pay expected ${shortDate(p.next_payday)}, ${p.pay_cadence ? CADENCE_WORD[p.pay_cadence] : ''}.`.replace(' .', '.') : null,
    staleLine:
      p.stale_days > 7
        ? `This export ends ${p.stale_days} days ago. Download a fresh one for a plan that matches your balance.`
        : null,
    inflowLine:
      p.unscheduled_inflow_count > 0
        ? `${p.unscheduled_inflow_count} one-off payments in were left out: money that may not come again is not planned around.`
        : null,
    truncatedLine:
      p.truncated_assumed_rows > 0
        ? `${p.truncated_assumed_rows} assumed days were dropped to fit the window.`
        : null,
    todayLine:
      p.income_not_counted_today.length > 0
        ? 'Pay expected today is not counted until it posts; type your balance again once it does.'
        : null,
  }
}

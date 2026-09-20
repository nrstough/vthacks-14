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

export function panelModel(
  account: ImportAccountResponse,
  excluded: ReadonlySet<string> = new Set(),
): PanelModel {
  const p = account.provenance
  // The payday belongs to a stream the person can untick. Left unfiltered,
  // the panel keeps promising "Next pay expected Sep 22" after the stream
  // that pays it has been removed from the plan.
  const payingStream = account.streams.find(
    (s) =>
      s.kind === 'income' &&
      p.next_payday !== null &&
      s.projected_ids.some((id) => account.scheduled.find((t) => t.id === id)?.date === p.next_payday),
  )
  const paydayCounted = p.next_payday !== null && (payingStream === undefined || !excluded.has(payingStream.id))
  const assumedDaily = account.scheduled.filter((t) => t.id.startsWith(ASSUMED_PREFIX))
  const total = assumedDaily.reduce((sum, t) => sum + Math.abs(t.amount_cents), 0)
  // Over every day of the horizon, not only the days that carry a row. A
  // quiet weekday emits no row, so dividing by the rows says "$70.00 a day"
  // for a fortnight in which the plan actually assumes $10 a day.
  const horizonDays =
    Math.round(
      (Date.parse(`${account.horizon_end}T00:00:00Z`) - Date.parse(`${account.as_of}T00:00:00Z`)) / 86400000,
    ) + 1
  const perDay =
    horizonDays > 0
      ? Math.floor(total / horizonDays) + (2 * (total % horizonDays) >= horizonDays ? 1 : 0)
      : 0

  return {
    streams: account.streams,
    assumedLine:
      p.assumed_method === null
        ? 'Less than eight weeks of history, so everyday spending was not estimated and the plan covers the recurring charges only.'
        : assumedDaily.length === 0 && p.truncated_assumed_rows > 0
          ? 'Everyday spending was estimated but left out: the window was already full of recurring charges.'
          : assumedDaily.length === 0
            ? 'No everyday spending found outside the recurring charges in your last eight weeks, so the plan covers those only.'
            : `Everyday spending: about ${money(perDay)} a day across the window, the median of the same weekday over your last ${p.weeks_used_for_assumed} weeks. An assumption, not a charge.`,
    // "no transactions in the export", not "nothing spent": the export is
    // assumed complete for its range, and that assumption is the reason a
    // quiet day counts as a zero. Stating it as observed fact would hide it.
    historyLine: `${p.rows_used} transactions, ${shortDate(p.history_start)} to ${shortDate(p.history_end)}${
      p.imputed_zero_days > 0
        ? `, ${p.imputed_zero_days} days with none in the file, counted as no spending`
        : ''
    }.`,
    paydayLine: !paydayCounted
      ? p.next_payday
        ? `Next pay would have been ${shortDate(p.next_payday)}, but that income is unticked and is not in the plan.`
        : null
      : `Next pay expected ${shortDate(p.next_payday as string)}, ${p.pay_cadence ? CADENCE_WORD[p.pay_cadence] : ''}.`.replace(' .', '.'),
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
        : p.income_already_posted.length > 0
          ? 'A payday inside this window already posted, so it is in the balance you typed rather than in the plan.'
          : null,
  }
}

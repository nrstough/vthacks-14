// The pure half of the imported-account UI (A10, A17, A2).
//
// The component is never mounted by these tests, so every decision worth
// pinning lives in lib/history.ts and is tested here: what unticking does to
// the schedule, which candidates may carry a checkbox, what the panel says,
// and what sentence follows the verdict on each tier.

import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  checkboxableIds,
  isImport,
  panelModel,
  qualifierNote,
  scheduleAfterUntick,
  streamLine,
  ticksAfterReimport,
  toBase,
} from '../src/lib/history.ts'
import type { Candidate, ImportAccountResponse, ScheduledTxn, Stream } from '../src/types.ts'
import { SCENARIOS } from '../src/fixtures/scenarios.ts'
import { solve } from '../src/solver/mockSolver.ts'

function txn(id: string, date: string, cents: number, kind: ScheduledTxn['kind'] = 'bill'): ScheduledTxn {
  return { id, date, description: id.startsWith('f_') ? 'Everyday spending (assumed from your last 8 weeks)' : 'Rent or mortgage (monthly)', amount_cents: cents, kind, recurring: !id.startsWith('f_') }
}

function candidate(id: string, target: string): Candidate {
  return {
    id,
    label: 'Cancel the streaming subscription',
    detail: 'Cancelling this streaming subscription keeps $15.99.',
    action: 'cancel',
    target_txn_id: target,
    freed_cents: 1599,
    effective_date: '2026-09-25',
    recharge_date: null,
    lead_time_days: 0,
    pain: 2,
  }
}

function stream(id: string, over: Partial<Stream> = {}): Stream {
  return {
    id,
    kind: 'bill',
    label: 'Rent or mortgage (monthly)',
    category: 'housing',
    cadence: 'monthly',
    anchor: 'the 1st',
    amount_cents: -120000,
    occurrences: 9,
    last_seen: '2026-09-01',
    active: true,
    source_row_indexes: [1, 2, 3],
    projected_ids: [`t_${id}_01`],
    ...over,
  }
}

function account(over: Partial<ImportAccountResponse> = {}): ImportAccountResponse {
  return {
    as_of: '2026-09-21',
    horizon_end: '2026-10-20',
    opening_balance_cents: 41000,
    buffer_cents: 2500,
    scheduled: [txn('t_s_001_01', '2026-10-01', -120000), txn('t_s_002_01', '2026-09-25', -1599), txn('f_20260922', '2026-09-22', -2500, 'discretionary')],
    candidates: [candidate('c_cancel', 't_s_002_01')],
    meta: { rows_considered: 2, protected: [], unrecognised: [], not_actionable: [], truncated: false },
    source: 'import',
    streams: [stream('s_001'), stream('s_002', { label: 'Streaming subscription (monthly)', category: 'streaming', amount_cents: -1599, projected_ids: ['t_s_002_01'] })],
    provenance: {
      history_start: '2026-01-01',
      history_end: '2026-09-18',
      history_days: 261,
      imputed_zero_days: 12,
      rows_used: 300,
      weeks_used_for_assumed: 8,
      assumed_method: 'same_weekday_8_week_median',
      assumed_ids: ['f_20260922'],
      next_payday: '2026-09-22',
      pay_cadence: 'weekly',
      income_not_counted_today: [],
      stale_days: 3,
      unscheduled_inflow_count: 4,
      unscheduled_inflow_cents: 22000,
      truncated_assumed_rows: 0,
      rejected_rows: [],
    },
    ...over,
  }
}

test('an imported account is recognised and others are not', () => {
  assert.equal(isImport(account()), true)
  assert.equal(isImport(null), false)
})

test('unticking a stream drops its rows and the candidates aimed at them', () => {
  const a = account()
  const next = scheduleAfterUntick(a, new Set(['s_002']), 41000, 2500)
  assert.deepEqual(next.scheduled.map((t) => t.id), ['t_s_001_01', 'f_20260922'])
  assert.deepEqual(next.candidates, [])
})

test('re-ticking restores the rows, because the rebuild starts from the original', () => {
  const a = account()
  const off = scheduleAfterUntick(a, new Set(['s_002']), 41000, 2500)
  const on = scheduleAfterUntick(a, new Set(), 41000, 2500)
  assert.equal(off.scheduled.length, 2)
  assert.equal(on.scheduled.length, 3)
  assert.deepEqual(on.candidates.map((c) => c.id), ['c_cancel'])
})

test('unticking preserves the balance and cushion the person set', () => {
  const next = scheduleAfterUntick(account(), new Set(['s_001']), 9900, 5000)
  assert.equal(next.opening_balance_cents, 9900)
  assert.equal(next.buffer_cents, 5000)
})

test('a rebuilt request carries no locks, so a stale lock cannot 422 the solve', () => {
  const next = scheduleAfterUntick(account(), new Set(['s_002']), 41000, 2500)
  assert.deepEqual(next.locks, { in: [], out: [] })
  assert.deepEqual(next.previous_plan, [])
})

test('unticking never removes an assumed row', () => {
  // Assumed rows belong to no stream, so no untick can reach them.
  const next = scheduleAfterUntick(account(), new Set(['s_001', 's_002']), 41000, 2500)
  assert.deepEqual(next.scheduled.map((t) => t.id), ['f_20260922'])
})

test('a fresh import starts with nothing unticked', () => {
  assert.equal(ticksAfterReimport().size, 0)
})

test('an assumed row can never carry a "Can\'t do this" box', () => {
  const withAssumed = [candidate('c_cancel', 't_s_002_01'), candidate('c_bad', 'f_20260922')]
  assert.deepEqual(checkboxableIds(withAssumed), ['c_cancel'])
})

test('the base request mirrors the response', () => {
  const base = toBase(account())
  assert.equal(base.as_of, '2026-09-21')
  assert.equal(base.scheduled.length, 3)
  assert.deepEqual(base.locks, { in: [], out: [] })
})

test('the note is a standalone sentence, so it reads on every tier', () => {
  // Tiers 2 and 3 do not end in "Sufficient under the schedule shown", so an
  // appended clause would read as "...puts you over., where everyday...".
  // Annotated rather than inferred: `assert.ok` is an assertion signature,
  // and TypeScript refuses to infer through one.
  const note: string | undefined = qualifierNote(account())
  assert.ok(note !== undefined)
  assert.match(note, /^Everyday spending here is an assumption/)
  assert.match(note, /\.$/)
  // Real qualifiers from the built-in solver, not invented strings: the
  // whole point is that tiers 2 and 3 do NOT end in "Sufficient under the
  // schedule shown", so an appended clause would read as "...over., where".
  const tiers = new Set<number>()
  for (const scenario of SCENARIOS) {
    const result = solve(scenario.request, [])
    tiers.add(result.tier)
    const composed: string = `${result.qualifier} ${note}`
    assert.equal(composed.includes('., '), false, `reads badly: ${composed}`)
    assert.equal(/[.!?]$/.test(result.qualifier.trim()), true, result.qualifier)
  }
  assert.ok(tiers.size >= 2, `the scenarios must span tiers, saw ${[...tiers].join()}`)
})

test('no note when the plan assumed nothing', () => {
  const bare = account({ provenance: { ...account().provenance, assumed_ids: [], assumed_method: null } })
  assert.equal(qualifierNote(bare), undefined)
  assert.equal(qualifierNote(null), undefined)
})

test('the per-day figure spreads across the window, not across the rows', () => {
  // Two $70 rows in a fortnight is $10 a day, not $70 a day. Dividing by the
  // rows that exist ignores every quiet day the plan also covers.
  const sparse = account({
    as_of: '2026-09-21',
    horizon_end: '2026-10-04',
    scheduled: [
      txn('f_20260922', '2026-09-22', -7000, 'discretionary'),
      txn('f_20260929', '2026-09-29', -7000, 'discretionary'),
    ],
    provenance: { ...account().provenance, assumed_ids: ['f_20260922', 'f_20260929'] },
  })
  assert.match(panelModel(sparse).assumedLine ?? '', /\$10\.00 a day/)
})

test('truncated estimates are not reported as no spending', () => {
  const cut = account({
    scheduled: [txn('t_s_001_01', '2026-10-01', -120000)],
    provenance: { ...account().provenance, assumed_ids: [], truncated_assumed_rows: 14 },
  })
  const line = panelModel(cut).assumedLine ?? ''
  assert.match(line, /estimated but left out/)
  assert.equal(/No everyday spending found/.test(line), false)
})

test('quiet days are described as absent from the file, not as observed', () => {
  // The export is ASSUMED complete for its range; stating a quiet day as
  // "nothing spent" presents that assumption as a fact.
  const line = panelModel(account()).historyLine
  assert.match(line, /days with none in the file/)
  assert.equal(/days with nothing spent/.test(line), false)
})

test('the panel says the method, the window and the payday', () => {
  const model = panelModel(account())
  assert.match(model.assumedLine ?? '', /median of the same weekday/)
  assert.match(model.assumedLine ?? '', /An assumption, not a charge/)
  assert.match(model.historyLine, /300 transactions/)
  assert.match(model.historyLine, /12 days with none in the file/)
  assert.match(model.paydayLine ?? '', /Next pay expected/)
  assert.match(model.inflowLine ?? '', /may not come again/)
})

test('the panel tells short history apart from no spending found', () => {
  // Two different facts. Collapsing them tells someone with seven months of
  // bills and no card spending that they have "not enough history".
  const short = account({
    scheduled: [txn('t_s_001_01', '2026-10-01', -120000)],
    provenance: { ...account().provenance, assumed_ids: [], assumed_method: null, weeks_used_for_assumed: null },
  })
  assert.match(panelModel(short).assumedLine ?? '', /Less than eight weeks of history/)

  const nothingFound = account({
    scheduled: [txn('t_s_001_01', '2026-10-01', -120000)],
    provenance: { ...account().provenance, assumed_ids: [] },
  })
  const line = panelModel(nothingFound).assumedLine ?? ''
  assert.match(line, /No everyday spending found/)
  assert.equal(/not enough history/i.test(line), false)
})

test('a stale export is flagged only past a week', () => {
  assert.equal(panelModel(account()).staleLine, null)
  const old = account({ provenance: { ...account().provenance, stale_days: 20 } })
  assert.match(panelModel(old).staleLine ?? '', /20 days ago/)
})

test('pay expected today is explained rather than silently missing', () => {
  const today = account({ provenance: { ...account().provenance, income_not_counted_today: ['s_003'] } })
  assert.match(panelModel(today).todayLine ?? '', /not counted until it posts/)
})

test('truncated assumed days are disclosed', () => {
  const cut = account({ provenance: { ...account().provenance, truncated_assumed_rows: 6 } })
  assert.match(panelModel(cut).truncatedLine ?? '', /6 assumed days were dropped/)
})

test('a stopped stream says it is not counted', () => {
  assert.match(streamLine(stream('s_009', { active: false })), /stopped, not counted/)
  assert.match(streamLine(stream('s_010')), /monthly on the 1st/)
})

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { PENDING, actByNotice, daysBetween, reasonFor } from '../src/lib/reasons.ts'
import type { ReasonKind } from '../src/lib/reasons.ts'
import { SCENARIOS } from '../src/fixtures/scenarios.ts'
import {
  CUSHION_ONLY_REASON,
  CUSHION_ONLY_REASON_GAP,
  solve,
} from '../src/solver/mockSolver.ts'
import type { Candidate, SolveRequest, SolveResponse } from '../src/types.ts'

const FORBIDDEN = [/guarantee/i, /infeasib/i]

function candidate(over: Partial<Candidate> = {}): Candidate {
  return {
    id: 'c_x',
    label: 'Change x',
    detail: 'MERCHANT',
    action: 'skip',
    target_txn_id: 't_x',
    freed_cents: 1000,
    effective_date: '2026-09-25',
    recharge_date: null,
    lead_time_days: 0,
    pain: 2,
    ...over,
  }
}

function req(over: Partial<SolveRequest> = {}): SolveRequest {
  return {
    as_of: '2026-09-19',
    horizon_end: '2026-10-02',
    opening_balance_cents: 20000,
    buffer_cents: 2500,
    scheduled: [],
    candidates: [candidate()],
    locks: { in: [], out: [] },
    ...over,
  }
}

function res(tier: 1 | 2 | 3, proven = true, plan: SolveResponse['plan'] = []): SolveResponse {
  return {
    tier,
    verdict: '',
    qualifier: '',
    plan,
    certificate: { irredundant: true, minimal_proven: proven, sentence: '', per_item: [] },
    shortfall: { worst_cents: 0, worst_date: null, total_cents: 0 },
    external_cash_needed: null,
    balances: [],
    meta: {
      solver: 'brute-force',
      status: proven ? 'OPTIMAL' : 'FEASIBLE',
      wall_ms: 1,
      candidates_considered: 1,
      excluded_locked_in: [],
    },
  }
}

function planItem(id: string): SolveResponse['plan'][number] {
  return {
    candidate_id: id,
    label: id,
    detail: '',
    action: 'skip',
    date: '2026-09-22',
    freed_cents: 100,
    pain: 1,
    strictly_needed: true,
    reason: '',
  }
}

test('daysBetween counts calendar days, and crosses a month end', () => {
  assert.equal(daysBetween('2026-09-19', '2026-09-19'), 0)
  assert.equal(daysBetween('2026-09-19', '2026-09-24'), 5)
  assert.equal(daysBetween('2026-09-28', '2026-10-02'), 4)
  assert.equal(daysBetween('2026-09-24', '2026-09-19'), -5)
})

test('a ruled-out change says the solver never saw it', () => {
  const r = reasonFor(candidate(), req(), res(1), true)
  assert.equal(r.kind, 'ruled_out')
  assert.match(r.text, /You ruled this out/)
})

test('ruled out beats every other reason', () => {
  // Too late, clashing, and tier 3 all at once: still "you ruled this out".
  const c = candidate({ effective_date: '2026-09-19', lead_time_days: 5 })
  const r = reasonFor(c, req({ candidates: [c] }), res(3, true, [planItem('c_x')]), true)
  assert.equal(r.kind, 'ruled_out')
})

test('a change whose lead time has passed is too late, not unneeded', () => {
  const c = candidate({ effective_date: '2026-09-20', lead_time_days: 3 })
  const r = reasonFor(c, req({ candidates: [c] }), res(1), false)
  assert.equal(r.kind, 'too_late')
  assert.match(r.text, /3 days of notice before Sep 20/)
})

test('lead time exactly met is actionable', () => {
  const c = candidate({ effective_date: '2026-09-22', lead_time_days: 3 })
  const r = reasonFor(c, req({ candidates: [c] }), res(1), false)
  assert.notEqual(r.kind, 'too_late')
})

test('one day short of the lead time is too late', () => {
  const c = candidate({ effective_date: '2026-09-21', lead_time_days: 3 })
  assert.equal(reasonFor(c, req({ candidates: [c] }), res(1), false).kind, 'too_late')
})

test('zero lead time is never too late, even on the first day', () => {
  const c = candidate({ effective_date: '2026-09-19', lead_time_days: 0 })
  assert.notEqual(reasonFor(c, req({ candidates: [c] }), res(1), false).kind, 'too_late')
})

test('one day of notice is singular', () => {
  const c = candidate({ effective_date: '2026-09-19', lead_time_days: 1 })
  assert.match(reasonFor(c, req({ candidates: [c] }), res(1), false).text, /1 day of notice/)
})

test('a change to a transaction already being changed says so', () => {
  const chosen = candidate({ id: 'c_a', target_txn_id: 't_shared' })
  const other = candidate({ id: 'c_b', target_txn_id: 't_shared' })
  const r = reasonFor(
    other,
    req({ candidates: [chosen, other] }),
    res(1, true, [planItem('c_a')]),
    false,
  )
  assert.equal(r.kind, 'same_txn')
  assert.match(r.text, /Only one is allowed/)
})

test('too late beats the same-transaction reason', () => {
  const chosen = candidate({ id: 'c_a', target_txn_id: 't_shared' })
  const other = candidate({
    id: 'c_b',
    target_txn_id: 't_shared',
    effective_date: '2026-09-19',
    lead_time_days: 4,
  })
  const r = reasonFor(other, req({ candidates: [chosen, other] }), res(1, true, [planItem('c_a')]), false)
  assert.equal(r.kind, 'too_late')
})

test('a different transaction does not trigger the clash reason', () => {
  const chosen = candidate({ id: 'c_a', target_txn_id: 't_one' })
  const other = candidate({ id: 'c_b', target_txn_id: 't_two' })
  const r = reasonFor(other, req({ candidates: [chosen, other] }), res(1, true, [planItem('c_a')]), false)
  assert.equal(r.kind, 'not_needed')
})

test('tier 1 proven says the plan clears without it', () => {
  const r = reasonFor(candidate(), req(), res(1), false)
  assert.equal(r.kind, 'not_needed')
  assert.match(r.text, /already clears zero without it/)
  // The cushion belongs to the in-plan line. If this one drifted onto it too,
  // the two lists would read alike again, which is the bug being fixed.
  assert.doesNotMatch(r.text, /cushion/i)
})

test('tier 2 proven says the same', () => {
  const r = reasonFor(candidate(), req(), res(2), false)
  assert.equal(r.kind, 'not_needed')
  assert.doesNotMatch(r.text, /cushion/i)
})

test('tier 3 proven claims only what the first objective term establishes', () => {
  const r = reasonFor(candidate(), req(), res(3), false)
  assert.equal(r.kind, 'no_fewer_days')
  assert.match(r.text, /fewer days below zero/)
  // A deferral CAN shrink the deepest dip while adding a day below zero, so
  // the wording must not claim anything about the size of the gap.
  assert.doesNotMatch(r.text, /gap|shrink|deeper/i)
})

test('an unproven solve never claims the plan clears without a change', () => {
  for (const tier of [1, 2, 3] as const) {
    const r = reasonFor(candidate(), req(), res(tier, false), false)
    assert.match(r.text, /was not proven; the solver ran out of time/)
    assert.doesNotMatch(r.text, /already clears/)
    assert.doesNotMatch(r.text, /would not leave/)
  }
})

test('tier 3 never tells the user the schedule clears', () => {
  for (const proven of [true, false]) {
    assert.doesNotMatch(reasonFor(candidate(), req(), res(3, proven), false).text, /clears/i)
  }
})

test('no reason ever contains a forbidden word', () => {
  const kinds = new Set<ReasonKind>()
  const texts: string[] = [PENDING.text]
  for (const tier of [1, 2, 3] as const) {
    for (const proven of [true, false]) {
      for (const ruled of [true, false]) {
        const r = reasonFor(candidate(), req(), res(tier, proven), ruled)
        kinds.add(r.kind)
        texts.push(r.text)
      }
    }
  }
  const late = candidate({ effective_date: '2026-09-19', lead_time_days: 2 })
  texts.push(reasonFor(late, req({ candidates: [late] }), res(1), false).text)
  kinds.add('too_late')
  const a = candidate({ id: 'c_a', target_txn_id: 't_s' })
  const b = candidate({ id: 'c_b', target_txn_id: 't_s' })
  texts.push(reasonFor(b, req({ candidates: [a, b] }), res(1, true, [planItem('c_a')]), false).text)
  kinds.add('same_txn')

  for (const text of texts) {
    assert.ok(text.length > 0)
    for (const bad of FORBIDDEN) assert.doesNotMatch(text, bad)
  }
  // Every kind the module can produce was exercised above.
  assert.equal(kinds.size, 8 - 1) // all but 'pending', which is the constant
})

test('every left-out change on every fixture gets a non-empty reason', () => {
  for (const scenario of SCENARIOS) {
    const response = solve(scenario.request, [])
    const used = new Set(response.plan.map((p) => p.candidate_id))
    const rest = scenario.request.candidates.filter((c) => !used.has(c.id))
    assert.ok(rest.length > 0, `${scenario.key} should leave some change out`)
    for (const c of rest) {
      const r = reasonFor(c, scenario.request, response, false)
      assert.ok(r.text.length > 0, `${scenario.key}/${c.id} has no reason`)
      for (const bad of FORBIDDEN) assert.doesNotMatch(r.text, bad)
    }
  }
})

test('the same inputs always give the same reason', () => {
  const scenario = SCENARIOS[2]
  const response = solve(scenario.request, [])
  for (const c of scenario.request.candidates) {
    const first = reasonFor(c, scenario.request, response, false)
    const second = reasonFor(c, scenario.request, response, false)
    assert.deepEqual(first, second)
  }
})

test('a change needing notice states the real deadline, not its effect date', () => {
  // Codex audit finding: labelling the effect date "act by" is false whenever a
  // change needs notice. The gym bills on the 22nd and needs three days, so the
  // user has to act by the 19th; saying the 22nd would cost them the plan.
  const gym = candidate({ effective_date: '2026-09-22', lead_time_days: 3 })
  const text = actByNotice(gym)
  assert.equal(text, 'Act by Sep 19: it needs 3 days of notice.')
})

test('a change with no lead time has no deadline to state', () => {
  assert.equal(actByNotice(candidate({ lead_time_days: 0 })), null)
})

test('one day of notice is singular, and the deadline crosses a month end', () => {
  assert.equal(
    actByNotice(candidate({ effective_date: '2026-10-01', lead_time_days: 1 })),
    'Act by Sep 30: it needs 1 day of notice.',
  )
})

test('every fixture candidate with lead time gets a deadline before its effect date', () => {
  for (const c of SCENARIOS[0].request.candidates) {
    const text = actByNotice(c)
    if (c.lead_time_days === 0) {
      assert.equal(text, null)
      continue
    }
    assert.ok(text, `${c.id} needs a deadline`)
    assert.match(text, /^Act by /)
    // The stated day must be strictly earlier than the day it takes effect.
    const stated = /Act by (\w+ \d+)/.exec(text)![1]
    assert.notEqual(stated, shortDateOf(c.effective_date))
  }
})

function shortDateOf(iso: string): string {
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  const [, m, d] = iso.split('-').map(Number)
  return `${months[m - 1]} ${d}`
}

test('the in-plan cushion-only lines never read like the left-out line', () => {
  // Both lists used to open on "not needed", one about a change the solver
  // chose and one about a change it did not. The in-plan sentences say what
  // zero marginals actually prove, and say it differently.
  const leftOut = reasonFor(candidate(), req(), res(1), false).text
  for (const text of [CUSHION_ONLY_REASON, CUSHION_ONLY_REASON_GAP]) {
    assert.ok(text.length > 0)
    assert.doesNotMatch(text, /not needed/i)
    assert.notEqual(text, leftOut)
    assert.ok(!text.includes(leftOut))
    assert.ok(!leftOut.includes(text))
    for (const bad of FORBIDDEN) assert.doesNotMatch(text, bad)
    assert.doesNotMatch(text, /smallest|fewest/i)
  }
  assert.notEqual(CUSHION_ONLY_REASON, CUSHION_ONLY_REASON_GAP)
})

test('a pending row says it is re-solving and claims nothing', () => {
  assert.equal(PENDING.kind, 'pending')
  assert.match(PENDING.text, /Re-solving/)
})

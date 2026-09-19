import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  daysUnder,
  headroom,
  lowestDoingNothing,
  lowestWithPlan,
  planClaim,
} from '../src/lib/kpis.ts'
import { SCENARIOS } from '../src/fixtures/scenarios.ts'
import { solve } from '../src/solver/mockSolver.ts'
import type { BalanceRow, SolveRequest, SolveResponse } from '../src/types.ts'

function row(over: Partial<BalanceRow> = {}): BalanceRow {
  return {
    date: '2026-09-19',
    baseline_cents: 1000,
    with_plan_cents: 1000,
    is_payday: false,
    changes_here: [],
    ...over,
  }
}

function res(over: Partial<SolveResponse> = {}): SolveResponse {
  return {
    tier: 1,
    verdict: '',
    qualifier: '',
    plan: [],
    certificate: { irredundant: true, minimal_proven: true, sentence: '', per_item: [] },
    shortfall: { worst_cents: 0, worst_date: null, total_cents: 0 },
    external_cash_needed: null,
    balances: [row()],
    meta: {
      solver: 'brute-force',
      status: 'OPTIMAL',
      wall_ms: 4,
      candidates_considered: 11,
      excluded_locked_in: [],
    },
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
    candidates: [],
    locks: { in: [], out: [] },
    ...over,
  }
}

function planItem(over: Partial<SolveResponse['plan'][number]> = {}): SolveResponse['plan'][number] {
  return {
    candidate_id: 'c_a',
    label: 'Change a',
    detail: '',
    action: 'skip',
    date: '2026-09-22',
    freed_cents: 100,
    pain: 1,
    strictly_needed: true,
    reason: '',
    ...over,
  }
}

test('the lowest point with the plan is the minimum, and a tie goes to the first day', () => {
  const r = res({
    balances: [
      row({ date: '2026-09-19', with_plan_cents: 5000 }),
      row({ date: '2026-09-20', with_plan_cents: -300 }),
      row({ date: '2026-09-21', with_plan_cents: -300 }),
      row({ date: '2026-09-22', with_plan_cents: 900 }),
    ],
  })
  // Strictly-less-than, scanning forward, the same tie rule narrate.ts uses: a
  // deadline you have already missed is not a deadline.
  assert.deepEqual(lowestWithPlan(r), { cents: -300, date: '2026-09-20' })
})

test('an empty window has no low point with the plan rather than a fabricated one', () => {
  assert.deepEqual(lowestWithPlan(res({ balances: [] })), { cents: 0, date: null })
})

test('an empty window has no low point doing nothing either', () => {
  assert.deepEqual(lowestDoingNothing(res({ balances: [] })), { cents: 0, date: null })
})

test('at tier 3 the low point is the solver’s own shortfall, not the balance scan', () => {
  // Recomputing it from `balances` can land on a different day from the
  // qualifier, and a tile that disagrees with the sentence beside it is worse
  // than no tile.
  const r = res({
    tier: 3,
    shortfall: { worst_cents: 2762, worst_date: '2026-09-24', total_cents: 5000 },
    balances: [
      row({ date: '2026-09-19', with_plan_cents: 100 }),
      row({ date: '2026-09-26', with_plan_cents: -9999 }),
    ],
  })
  assert.deepEqual(lowestWithPlan(r), { cents: -2762, date: '2026-09-24' })
})

test('a tier 3 response with no worst date falls through to the scan', () => {
  const r = res({
    tier: 3,
    shortfall: { worst_cents: 0, worst_date: null, total_cents: 0 },
    balances: [
      row({ date: '2026-09-19', with_plan_cents: 400 }),
      row({ date: '2026-09-20', with_plan_cents: 150 }),
    ],
  })
  assert.deepEqual(lowestWithPlan(r), { cents: 150, date: '2026-09-20' })
})

test('doing nothing reads the baseline series, and tier 3 does not redirect it', () => {
  const r = res({
    tier: 3,
    shortfall: { worst_cents: 2762, worst_date: '2026-09-24', total_cents: 5000 },
    balances: [
      row({ date: '2026-09-19', baseline_cents: 800, with_plan_cents: 800 }),
      row({ date: '2026-09-20', baseline_cents: -4200, with_plan_cents: -100 }),
      row({ date: '2026-09-21', baseline_cents: -4200, with_plan_cents: 50 }),
    ],
  })
  assert.deepEqual(lowestDoingNothing(r), { cents: -4200, date: '2026-09-20' })
})

test('days under counts each series separately and the difference is what the plan avoids', () => {
  const r = res({
    balances: [
      row({ baseline_cents: -100, with_plan_cents: -100 }),
      row({ baseline_cents: -100, with_plan_cents: 0 }),
      row({ baseline_cents: -1, with_plan_cents: 500 }),
      row({ baseline_cents: 0, with_plan_cents: 500 }),
    ],
  })
  // Zero is not under: the product's claim is "above zero", and a day that
  // lands exactly on it has not overdrafted.
  assert.deepEqual(daysUnder(r), { doingNothing: 3, withPlan: 1, avoided: 2 })
})

test('headroom is signed against the cushion the user asked for', () => {
  const over = res({ balances: [row({ with_plan_cents: 4000 })] })
  assert.equal(headroom(over, req({ buffer_cents: 2500 })), 1500)
  const under = res({ balances: [row({ with_plan_cents: 1000 })] })
  assert.equal(headroom(under, req({ buffer_cents: 2500 })), -1500)
})

test('the plan claim says "smallest" only on a solve that proved it', () => {
  assert.equal(planClaim(res({ plan: [] })), 'Nothing to change')

  const unproven = planClaim(
    res({
      plan: [planItem()],
      certificate: { irredundant: true, minimal_proven: false, sentence: '', per_item: [] },
    }),
  )
  assert.match(unproven, /not proven/)
  assert.doesNotMatch(unproven, /^Smallest set(,| proven)/)

  const provenIrredundant = planClaim(
    res({
      plan: [planItem()],
      certificate: { irredundant: true, minimal_proven: true, sentence: '', per_item: [] },
    }),
  )
  assert.match(provenIrredundant, /every one load-bearing/)

  const provenRedundant = planClaim(
    res({
      plan: [planItem()],
      certificate: { irredundant: false, minimal_proven: true, sentence: '', per_item: [] },
    }),
  )
  assert.equal(provenRedundant, 'Smallest set proven')
})

test('no plan claim ever names a dollar figure or a fee', () => {
  // The contract carries no fee schedule, so a dollar figure here would be a
  // number this product does not have.
  const claims = [planClaim(res({ plan: [] }))]
  for (const minimal_proven of [true, false]) {
    for (const irredundant of [true, false]) {
      claims.push(
        planClaim(
          res({
            plan: [planItem()],
            certificate: { irredundant, minimal_proven, sentence: '', per_item: [] },
          }),
        ),
      )
    }
  }
  for (const claim of claims) {
    assert.ok(claim.length > 0)
    assert.ok(!claim.includes('$'), claim)
    assert.doesNotMatch(claim, /fee/i)
  }
})

test('the demo account reads the hand-checked canary figures', () => {
  const clears = solve(SCENARIOS[0].request, [])
  assert.deepEqual(lowestWithPlan(clears), { cents: 2674, date: '2026-09-24' })
  assert.equal(lowestDoingNothing(clears).cents, -12005)

  const gap = solve(SCENARIOS[2].request, [])
  assert.equal(gap.tier, 3)
  assert.deepEqual(lowestWithPlan(gap), { cents: -2762, date: '2026-09-24' })
})

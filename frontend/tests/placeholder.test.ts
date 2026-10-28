import assert from 'node:assert/strict'
import { test } from 'node:test'

import { SCENARIOS } from '../src/fixtures/scenarios.ts'
import { PLACEHOLDER_MAX_CANDIDATES, placeholderSolve } from '../src/lib/placeholder.ts'
import { solve } from '../src/solver/mockSolver.ts'
import type { Candidate, ScheduledTxn, SolveRequest } from '../src/types'

const DEMO = SCENARIOS[0].request

// The demo account plus enough one-off charges, each with its own skip, to
// put `n` changes on the table.
function withCandidates(n: number): SolveRequest {
  const extra = Array.from({ length: n - DEMO.candidates.length }, (_, i) => i)
  const scheduled: ScheduledTxn[] = extra.map((i) => ({
    id: `t_extra_${i}`,
    date: '2026-09-26',
    description: `EXTRA ${i}`,
    amount_cents: -1000,
    kind: 'discretionary',
    recurring: false,
  }))
  const candidates: Candidate[] = extra.map((i) => ({
    id: `c_extra_${i}`,
    label: `Skip extra ${i}`,
    detail: `EXTRA ${i}, $10.00`,
    action: 'skip',
    target_txn_id: `t_extra_${i}`,
    freed_cents: 1000,
    effective_date: '2026-09-26',
    recharge_date: null,
    lead_time_days: 0,
    pain: 1,
  }))
  return {
    ...DEMO,
    scheduled: [...DEMO.scheduled, ...scheduled],
    candidates: [...DEMO.candidates, ...candidates],
  }
}

test('the demo account still gets the local answer at once, the same one the solver gives', () => {
  // The first paint of every preset depends on this: the demo has eleven
  // changes, well inside the cap.
  const got = placeholderSolve(DEMO)
  assert.ok(got, 'the demo account got no placeholder')
  const want = solve(DEMO, [])
  assert.deepEqual(got.plan, want.plan)
  assert.equal(got.tier, want.tier)
})

test('an account at the cap still gets a placeholder', () => {
  const req = withCandidates(PLACEHOLDER_MAX_CANDIDATES)
  assert.equal(req.candidates.length, 14)
  assert.ok(placeholderSolve(req), 'fourteen changes should still be solved locally')
})

test('one change over the cap gets none, so the exhaustive search never runs for it', () => {
  // Fifteen is 2^15 subsets, already a few hundred milliseconds of frozen
  // page on a laptop; eighteen, the candidates call's default, is over a
  // second. The server or the effect's fallback answers instead.
  assert.equal(placeholderSolve(withCandidates(PLACEHOLDER_MAX_CANDIDATES + 1)), null)
  assert.equal(placeholderSolve(withCandidates(18)), null)
})

test('a request the stand-in refuses gives no placeholder rather than a throw', () => {
  // adopt() has no try/catch of its own any more: null is how it hears that
  // there is nothing to show yet.
  const backwards = { ...DEMO, horizon_end: '2026-09-01' }
  assert.throws(() => solve(backwards, []))
  assert.equal(placeholderSolve(backwards), null)
})

// The three demo accounts, checked through the same reference solver the page
// falls back to. These numbers are what a judge sees; if one of them moves, a
// change broke something. They are also asserted in backend/tests/test_parity.py,
// so a disagreement here means the two implementations have diverged.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { SCENARIOS } from '../src/fixtures/scenarios.ts'
import { solve } from '../src/solver/mockSolver.ts'
import { emptyPlanText } from '../src/lib/narrate.ts'

const [clears, tight, gap] = SCENARIOS

test('the $200 account clears in three changes', () => {
  const res = solve(clears.request, [])
  assert.equal(res.tier, 1)
  assert.equal(res.plan.length, 3)
  assert.deepEqual(res.plan.map((p) => p.candidate_id).sort(), ['c_card_min', 'c_dd_chipotle', 'c_gym'])
  assert.match(res.qualifier, /Tightest day is Sep 24 at \$26\.74/)
  assert.equal(res.certificate.minimal_proven, true)
})

test('the $180 account against a $100 cushion clears zero with no room', () => {
  const res = solve(tight.request, [])
  assert.equal(res.tier, 2)
  assert.equal(res.plan.length, 3)
  assert.match(res.qualifier, /Tightest day is Sep 24 at \$6\.74/)
})

test('the $60 account needs outside cash and says how much, by when', () => {
  const res = solve(gap.request, [])
  assert.equal(res.tier, 3)
  assert.equal(res.plan.length, 9)
  assert.deepEqual(res.external_cash_needed, { amount_cents: 2762, by_date: '2026-09-24' })
  assert.match(res.verdict, /You need \$27\.62 more by Sep 24/)
  assert.match(res.certificate.sentence, /grows by up to \$80\.00/)
})

test('the demo beat: ruling out the card minimum takes three changes to seven', () => {
  const res = solve({ ...clears.request, locks: { in: [], out: ['c_card_min'] } }, [])
  assert.equal(res.tier, 1)
  assert.equal(res.plan.length, 7)
  // The moment in the script: the proof stops saying every change is
  // load-bearing, because some of these only hold the cushion. Three of the
  // seven are still load-bearing, and the row-level styling marks which.
  assert.equal(res.certificate.irredundant, false)
  const needed = res.plan.filter((p) => p.strictly_needed).map((p) => p.candidate_id)
  assert.deepEqual(needed, ['c_dd_chipotle', 'c_gym', 'c_shell_defer'])
  // NOTE: the certificate sentence for this case names only the worst item and
  // then says "The rest hold the cushion", which is false while three items are
  // load-bearing. The wording is the solver's (api-contract.md: the sentence is
  // rendered verbatim) and is identical in backend/app/solver/wording.py:97-102,
  // so it is recorded for the backend lane rather than patched here. Asserted
  // loosely on purpose: this test should not pin a defect in place.
  assert.ok(res.certificate.sentence.length > 0)
})

test('ruling out the gym is the weaker moment the script warns against', () => {
  const res = solve({ ...clears.request, locks: { in: [], out: ['c_gym'] } }, [])
  assert.equal(res.plan.length, 4)
})

test('ruling everything out leaves tier 3 with an empty plan', () => {
  const all = clears.request.candidates.map((c) => c.id)
  const res = solve({ ...clears.request, locks: { in: [], out: all } }, [])
  assert.equal(res.tier, 3)
  assert.equal(res.plan.length, 0)
  assert.equal(res.meta.candidates_considered, 0)
  assert.deepEqual(res.external_cash_needed, { amount_cents: 12005, by_date: '2026-09-24' })
})

test('the empty plan at tier 3 is never described as "no changes needed"', () => {
  const all = clears.request.candidates.map((c) => c.id)
  const res = solve({ ...clears.request, locks: { in: [], out: all } }, [])
  const text = emptyPlanText(res)
  assert.equal(text.heading, 'No changes available')
  assert.doesNotMatch(text.body, /already clears/)
})

test('leaving only a change that lands too late gives an empty plan with one on the table', () => {
  // The case behind the wording fix: Netflix is actionable but takes effect on
  // Sep 29, after the Sep 24 dip, so it cannot reduce the days below zero.
  const others = clears.request.candidates.map((c) => c.id).filter((id) => id !== 'c_netflix')
  const res = solve({ ...clears.request, locks: { in: [], out: others } }, [])
  assert.equal(res.tier, 3)
  assert.equal(res.plan.length, 0)
  assert.equal(res.meta.candidates_considered, 1)
  const text = emptyPlanText(res)
  assert.equal(text.heading, 'No change helps here')
  assert.doesNotMatch(text.body, /ruled out|too late/)
})

test('every fixture offers eleven changes, so the request shape is unchanged', () => {
  for (const scenario of SCENARIOS) {
    assert.equal(scenario.request.candidates.length, 11)
    assert.deepEqual(scenario.request.locks, { in: [], out: [] })
  }
})

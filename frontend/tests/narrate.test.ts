import { test } from 'node:test'
import assert from 'node:assert/strict'
import { emptyPlanText, footerLines, narrateChart } from '../src/lib/narrate.ts'
import { SCENARIOS } from '../src/fixtures/scenarios.ts'
import { solve } from '../src/solver/mockSolver.ts'
import type { BalanceRow, SolveResponse } from '../src/types.ts'

const FORBIDDEN = [/guarantee/i, /infeasib/i]

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

function narrate(r: SolveResponse): string {
  return narrateChart(r).join(' ')
}

test('the clears fixture is narrated with the canary figures', () => {
  const text = narrate(solve(SCENARIOS[0].request, []))
  assert.match(text, /Doing nothing, the balance bottoms out at -\$120\.05 on Sep 24\./)
  assert.match(text, /With the plan, the lowest point is \$26\.74 on Sep 24\./)
  assert.match(text, /Payday lands on Sep 25 and Oct 2\./)
  assert.match(text, /Changes take effect on Sep 22 and Sep 24\./)
})

test('the tight fixture narrates its own tighter low point', () => {
  const text = narrate(solve(SCENARIOS[1].request, []))
  assert.match(text, /bottoms out at -\$140\.05 on Sep 24/)
  assert.match(text, /With the plan, the lowest point is \$6\.74 on Sep 24\./)
})

test('the gap fixture says the balance is still under, using the solver figures', () => {
  const response = solve(SCENARIOS[2].request, [])
  const text = narrate(response)
  assert.match(text, /bottoms out at -\$260\.05 on Sep 24/)
  assert.match(text, /With the plan, the balance is still -\$27\.62 on Sep 24\./)
  assert.doesNotMatch(text, /lowest point is \$/)
  assert.equal(response.shortfall.worst_cents, 2762)
})

test('the narrated low point agrees with the verdict qualifier', () => {
  for (const scenario of [SCENARIOS[0], SCENARIOS[1]]) {
    const response = solve(scenario.request, [])
    // [\d,]+\.\d\d, not [\d.,]+: the latter swallows the comma that follows
    // the amount in the qualifier sentence.
    const match = /Tightest day is (\w+ \d+) at \$([\d,]+\.\d\d)/.exec(response.qualifier)
    assert.ok(match, `${scenario.key} qualifier should name a tightest day`)
    assert.match(narrate(response), new RegExp(`lowest point is \\$${match[2]} on ${match[1]}`))
  }
})

test('a tie on the lowest point names the first day, as the solver does', () => {
  const r = res({
    balances: [
      row({ date: '2026-09-19', baseline_cents: 500, with_plan_cents: 500 }),
      row({ date: '2026-09-20', baseline_cents: -100, with_plan_cents: -100 }),
      row({ date: '2026-09-21', baseline_cents: -100, with_plan_cents: -100 }),
    ],
  })
  assert.match(narrate(r), /bottoms out at -\$1\.00 on Sep 20/)
})

test('a baseline that never goes negative is not called a bottoming out', () => {
  const r = res({ balances: [row({ baseline_cents: 5000, with_plan_cents: 5000 })] })
  assert.match(narrate(r), /Doing nothing, the lowest point is \$50\.00 on Sep 19\./)
  assert.doesNotMatch(narrate(r), /bottoms out/)
})

test('a single payday is singular and a single change day says one change', () => {
  const r = res({
    balances: [
      row({ date: '2026-09-19', changes_here: ['c_a'] }),
      row({ date: '2026-09-25', is_payday: true }),
    ],
  })
  const text = narrate(r)
  assert.match(text, /Payday lands on Sep 25\./)
  assert.match(text, /One change takes effect, on Sep 19\./)
})

test('three change days are listed with commas and a final and', () => {
  const r = res({
    balances: [
      row({ date: '2026-09-20', changes_here: ['a'] }),
      row({ date: '2026-09-22', changes_here: ['b'] }),
      row({ date: '2026-09-24', changes_here: ['c'] }),
    ],
  })
  assert.match(narrate(r), /Changes take effect on Sep 20, Sep 22 and Sep 24\./)
})

test('two changes on one day are not described as one change', () => {
  // Codex audit finding: the singular was keyed on the number of DATES, so two
  // changes landing together read "One change takes effect".
  const r = res({
    balances: [
      row({ date: '2026-09-22', changes_here: ['c_dd_chipotle', 'c_gym'] }),
      row({ date: '2026-09-25', is_payday: true }),
    ],
  })
  const text = narrate(r)
  assert.doesNotMatch(text, /One change takes effect/)
  assert.match(text, /Changes take effect on Sep 22\./)
})

test('exactly one change anywhere in the window is singular', () => {
  const r = res({ balances: [row({ date: '2026-09-22', changes_here: ['c_gym'] })] })
  assert.match(narrate(r), /One change takes effect, on Sep 22\./)
})

test('the clears fixture has two changes on Sep 22 and never says "one change"', () => {
  const response = solve(SCENARIOS[0].request, [])
  const sameDay = response.balances.find((b) => b.changes_here.length > 1)
  assert.ok(sameDay, 'the fixture should land two changes on one day')
  assert.deepEqual(sameDay.changes_here, ['c_dd_chipotle', 'c_gym'])
  assert.doesNotMatch(narrate(response), /One change takes effect/)
})

test('an empty window says there is no payday and nothing takes effect', () => {
  const text = narrate(res())
  assert.match(text, /No payday falls in this window\./)
  assert.match(text, /No changes take effect\./)
})

test('the gap fixture narrates all seven of its change days', () => {
  const response = solve(SCENARIOS[2].request, [])
  const days = response.balances.filter((b) => b.changes_here.length > 0)
  assert.equal(days.length, 7)
  assert.match(narrate(response), /Changes take effect on Sep 20, Sep 21, Sep 22, Sep 23, Sep 24, Sep 27 and Oct 1\./)
})

test('an empty plan at tier 1 or 2 says no changes are needed', () => {
  for (const tier of [1, 2] as const) {
    const t = emptyPlanText(res({ tier }))
    assert.equal(t.heading, 'No changes needed')
    assert.match(t.body, /already clears on its own/)
  }
})

test('an empty plan at tier 3 never says no changes are needed', () => {
  const t = emptyPlanText(res({ tier: 3 }))
  assert.equal(t.heading, 'No changes available')
  assert.match(t.body, /The gap stays\./)
  assert.doesNotMatch(t.heading, /needed/)
  assert.doesNotMatch(t.body, /clears/)
})

test('the footer claims a proof only when the solver obtained one', () => {
  assert.match(footerLines(res())[0], /^Exact solver, smallest plan proven$/)
  const unproven = res({
    certificate: { irredundant: true, minimal_proven: false, sentence: '', per_item: [] },
  })
  assert.match(footerLines(unproven)[0], /not proven: it ran out of time/)
  assert.doesNotMatch(footerLines(unproven)[0], /smallest plan proven/)
})

test('the footer reports the solve time and the number of changes considered', () => {
  const lines = footerLines(res())
  assert.equal(lines[1], 'Solved in 4 ms')
  assert.equal(lines[2], '11 changes considered')
})

test('one change considered is singular', () => {
  const r = res()
  const lines = footerLines({ ...r, meta: { ...r.meta, candidates_considered: 1 } })
  assert.equal(lines[2], '1 change considered')
})

test('nothing narrated or in the footer contains a forbidden word', () => {
  for (const scenario of SCENARIOS) {
    const response = solve(scenario.request, [])
    const all = [...narrateChart(response), ...footerLines(response), emptyPlanText(response).heading, emptyPlanText(response).body]
    for (const text of all) {
      for (const bad of FORBIDDEN) assert.doesNotMatch(text, bad)
    }
  }
})

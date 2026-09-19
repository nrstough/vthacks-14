// The account-loading lifecycle. Every case here is an ordering bug that a
// screenshot cannot show and that nothing else in the suite would catch: the
// component is never mounted by these tests, by design.
//
// They drive the reducer the way the component does — one monotonic token,
// pre-incremented, handed in with every start. An earlier version of these
// tests let each case invent its own consistent numbers, which is why they all
// passed while the real page had two counters drifting apart. See the last
// test in this file.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  accountReducer,
  fail,
  initial,
  preset,
  start,
  succeed,
} from '../src/lib/accountState.ts'
import type { AccountState } from '../src/lib/accountState.ts'
import { SCENARIOS } from '../src/fixtures/scenarios.ts'
import type { LoadedAccount } from '../src/types.ts'

const FIXTURE = SCENARIOS[0].request
const OTHER = SCENARIOS[2].request

const modelled = (seed = 1): LoadedAccount => ({
  seed,
  as_of: '2026-09-19',
  horizon_end: '2026-10-18',
  opening_balance_cents: 49800,
  buffer_cents: 2500,
  scheduled: [],
  source: 'modelled',
})

/** The component's half: a monotonic token, and state threaded through. */
function page() {
  let token = 0
  let state: AccountState = initial(FIXTURE)
  return {
    get state() {
      return state
    },
    startLoad(kind: 'modelled' | 'nessie') {
      const mine = ++token
      state = accountReducer(state, start(kind, mine))
      return mine
    },
    settle(mine: number, account: LoadedAccount) {
      state = accountReducer(state, succeed(mine, account, OTHER))
    },
    break_(mine: number, message: string) {
      state = accountReducer(state, fail(mine, message))
    },
    choosePreset() {
      state = accountReducer(state, preset(FIXTURE))
    },
  }
}

test('a load marks itself pending and clears the last error', () => {
  const p = page()
  const first = p.startLoad('nessie')
  p.break_(first, 'it broke')
  assert.equal(p.state.error, 'it broke')
  p.startLoad('modelled')
  assert.equal(p.state.loading, 'modelled')
  assert.equal(p.state.error, null)
})

test('a result that arrives for the current load is adopted', () => {
  const p = page()
  const mine = p.startLoad('modelled')
  p.settle(mine, modelled())
  assert.equal(p.state.account?.source, 'modelled')
  assert.equal(p.state.base, OTHER)
  assert.equal(p.state.loading, null)
})

test('a result for a load the user has replaced is ignored', () => {
  const p = page()
  const first = p.startLoad('modelled')
  p.startLoad('nessie')
  const before = p.state
  p.settle(first, modelled())
  assert.equal(p.state, before, 'the stale result must not touch state at all')
  assert.equal(p.state.loading, 'nessie')
})

test('the second of two loads is the one that lands', () => {
  const p = page()
  const first = p.startLoad('modelled')
  const second = p.startLoad('nessie')
  p.settle(first, modelled(1))
  p.settle(second, modelled(2))
  assert.equal(p.state.account?.seed, 2)
  assert.equal(p.state.loading, null)
})

test('a failure for a stale load is ignored', () => {
  const p = page()
  const first = p.startLoad('modelled')
  p.startLoad('nessie')
  p.break_(first, 'the first one died')
  assert.equal(p.state.error, null)
  assert.equal(p.state.loading, 'nessie')
})

test('a failure for the current load is shown and stops the spinner', () => {
  const p = page()
  const mine = p.startLoad('nessie')
  p.break_(mine, 'sandbox is not set up')
  assert.equal(p.state.error, 'sandbox is not set up')
  assert.equal(p.state.loading, null)
})

test('choosing a preset mid-load re-enables the buttons', () => {
  const p = page()
  const mine = p.startLoad('nessie')
  assert.equal(p.state.loading, 'nessie')
  p.choosePreset()
  assert.equal(p.state.loading, null)
  p.settle(mine, modelled())
  assert.equal(p.state.loading, null, 'the stale result must not re-disable them')
  assert.equal(p.state.account, null)
})

test('a preset drops the loaded account and restores the fixture', () => {
  const p = page()
  const mine = p.startLoad('modelled')
  p.settle(mine, modelled())
  p.choosePreset()
  assert.equal(p.state.account, null)
  assert.equal(p.state.base, FIXTURE)
})

test('a preset clears a visible error', () => {
  const p = page()
  const mine = p.startLoad('nessie')
  p.break_(mine, 'sandbox is not set up')
  p.choosePreset()
  assert.equal(p.state.error, null)
})

test('a load still lands after the user has used a preset', () => {
  // The regression. The reducer used to bump a counter of its own on both
  // start and preset, while the component bumped one only on start, so a
  // single preset put them permanently out of step: from then on every result
  // was ignored, the spinner never stopped, and both buttons stayed disabled
  // until a reload. The unit tests missed it because each one invented its own
  // self-consistent numbers. The browser found it in four seconds.
  const p = page()
  p.choosePreset()
  const mine = p.startLoad('nessie')
  p.settle(mine, modelled(7))
  assert.equal(p.state.loading, null, 'the spinner must stop')
  assert.equal(p.state.account?.seed, 7, 'the account must land')
})

test('loads keep landing after several presets', () => {
  const p = page()
  for (let i = 0; i < 3; i++) {
    p.choosePreset()
    const mine = p.startLoad('modelled')
    p.settle(mine, modelled(i))
    assert.equal(p.state.account?.seed, i)
    assert.equal(p.state.loading, null)
  }
})

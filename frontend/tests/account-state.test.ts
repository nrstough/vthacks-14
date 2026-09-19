// The account-loading lifecycle. Every case here is an ordering bug that a
// screenshot cannot show and that nothing else in the suite would catch: the
// component is never mounted by these tests, by design.

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

test('a load marks itself pending and clears the last error', () => {
  const errored = { ...initial(FIXTURE), error: 'it broke' }
  const s = accountReducer(errored, start('nessie'))
  assert.equal(s.loading, 'nessie')
  assert.equal(s.error, null)
  assert.equal(s.seq, errored.seq + 1)
})

test('a result that arrives for the current load is adopted', () => {
  const s1 = accountReducer(initial(FIXTURE), start('modelled'))
  const s2 = accountReducer(s1, succeed(s1.seq, modelled(), OTHER))
  assert.equal(s2.account?.source, 'modelled')
  assert.equal(s2.base, OTHER)
  assert.equal(s2.loading, null)
})

test('a result for a load the user has replaced is ignored', () => {
  const s1 = accountReducer(initial(FIXTURE), start('modelled'))
  const s2 = accountReducer(s1, start('nessie'))
  const s3 = accountReducer(s2, succeed(s1.seq, modelled(), OTHER))
  assert.equal(s3, s2, 'the stale result must not touch state at all')
  assert.equal(s3.loading, 'nessie')
})

test('the second of two loads is the one that lands', () => {
  const s1 = accountReducer(initial(FIXTURE), start('modelled'))
  const s2 = accountReducer(s1, start('nessie'))
  const s3 = accountReducer(s2, succeed(s1.seq, modelled(1), OTHER))
  const s4 = accountReducer(s3, succeed(s2.seq, modelled(2), OTHER))
  assert.equal(s4.account?.seed, 2)
  assert.equal(s4.loading, null)
})

test('a failure for a stale load is ignored', () => {
  const s1 = accountReducer(initial(FIXTURE), start('modelled'))
  const s2 = accountReducer(s1, start('nessie'))
  const s3 = accountReducer(s2, fail(s1.seq, 'the first one died'))
  assert.equal(s3.error, null)
  assert.equal(s3.loading, 'nessie')
})

test('a failure for the current load is shown and stops the spinner', () => {
  const s1 = accountReducer(initial(FIXTURE), start('nessie'))
  const s2 = accountReducer(s1, fail(s1.seq, 'sandbox is not set up'))
  assert.equal(s2.error, 'sandbox is not set up')
  assert.equal(s2.loading, null)
})

test('choosing a preset mid-load re-enables the buttons', () => {
  // Without this the in-flight load is stale when it returns, skips its own
  // cleanup, and both account buttons stay disabled until a page reload.
  const s1 = accountReducer(initial(FIXTURE), start('nessie'))
  assert.equal(s1.loading, 'nessie')
  const s2 = accountReducer(s1, preset(FIXTURE))
  assert.equal(s2.loading, null)
  const s3 = accountReducer(s2, succeed(s1.seq, modelled(), OTHER))
  assert.equal(s3.loading, null, 'the stale result must not re-disable them either')
  assert.equal(s3.account, null)
})

test('a preset drops the loaded account and restores the fixture', () => {
  const s1 = accountReducer(initial(FIXTURE), start('modelled'))
  const s2 = accountReducer(s1, succeed(s1.seq, modelled(), OTHER))
  const s3 = accountReducer(s2, preset(FIXTURE))
  assert.equal(s3.account, null)
  assert.equal(s3.base, FIXTURE)
})

test('a preset clears a visible error', () => {
  const s1 = accountReducer(initial(FIXTURE), start('nessie'))
  const s2 = accountReducer(s1, fail(s1.seq, 'sandbox is not set up'))
  assert.equal(accountReducer(s2, preset(FIXTURE)).error, null)
})

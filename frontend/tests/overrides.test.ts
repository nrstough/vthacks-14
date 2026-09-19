import { test } from 'node:test'
import assert from 'node:assert/strict'
import { NONE, count, fromIds, isRuledOut, pendingIds, toLocks, toggle } from '../src/lib/overrides.ts'

test('toggle adds an id that is absent', () => {
  assert.deepEqual([...toggle(NONE, 'c_gym')], ['c_gym'])
})

test('toggle removes an id that is present', () => {
  assert.deepEqual([...toggle(fromIds(['c_gym']), 'c_gym')], [])
})

test('toggle twice restores the original set', () => {
  const start = fromIds(['a', 'b'])
  const round = toggle(toggle(start, 'c'), 'c')
  assert.deepEqual([...round].sort(), ['a', 'b'])
})

test('toggle never mutates its input', () => {
  const start = fromIds(['a'])
  toggle(start, 'b')
  assert.deepEqual([...start], ['a'])
})

test('toggling an id twice does not duplicate it', () => {
  const once = toggle(NONE, 'a')
  const twice = toggle(toggle(once, 'b'), 'b')
  assert.equal(count(twice), 1)
})

test('locks.in is always empty: the screen offers no pin', () => {
  assert.deepEqual(toLocks(fromIds(['a', 'b', 'c'])).in, [])
  assert.deepEqual(toLocks(NONE).in, [])
})

test('locks.out is sorted, so equal sets give byte-identical requests', () => {
  const a = toLocks(fromIds(['c_gym', 'c_amzn', 'c_card_min']))
  const b = toLocks(fromIds(['c_card_min', 'c_gym', 'c_amzn']))
  assert.deepEqual(a.out, ['c_amzn', 'c_card_min', 'c_gym'])
  assert.deepEqual(a, b)
  assert.equal(JSON.stringify(a), JSON.stringify(b))
})

test('count reports the number of ruled-out changes', () => {
  assert.equal(count(NONE), 0)
  assert.equal(count(fromIds(['a', 'b'])), 2)
})

test('isRuledOut reports membership', () => {
  assert.equal(isRuledOut(fromIds(['a']), 'a'), true)
  assert.equal(isRuledOut(fromIds(['a']), 'b'), false)
})

test('pendingIds is the symmetric difference of current and solved', () => {
  assert.deepEqual([...pendingIds(fromIds(['a', 'b']), fromIds(['b', 'c']))].sort(), ['a', 'c'])
  assert.deepEqual([...pendingIds(fromIds(['a']), fromIds(['a']))], [])
  assert.deepEqual([...pendingIds(fromIds(['a']), NONE)], ['a'])
  assert.deepEqual([...pendingIds(NONE, fromIds(['a']))], ['a'])
})

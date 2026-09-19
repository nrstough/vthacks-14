import { test } from 'node:test'
import assert from 'node:assert/strict'
import { money, shortDate } from '../src/lib/format.ts'

test('money renders integer cents with two decimals', () => {
  assert.equal(money(2674), '$26.74')
  assert.equal(money(0), '$0.00')
  assert.equal(money(-12005), '-$120.05')
  assert.equal(money(100000), '$1,000.00')
})

test('shortDate renders a month and day from an ISO date', () => {
  assert.equal(shortDate('2026-09-24'), 'Sep 24')
  assert.equal(shortDate('2026-10-02'), 'Oct 2')
})

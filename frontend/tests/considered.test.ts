import assert from 'node:assert/strict'
import { test } from 'node:test'

import { decideConsidered } from '../src/lib/considered.ts'

test('ruling out the first change opens the list', () => {
  assert.equal(decideConsidered(0, 1), 'open')
})

test('ruling out another change opens it again, even from a collapsed state', () => {
  // The demo's 1:45 beat, and the reason this is not `prev === 0`. Rule out A,
  // collapse the list by hand, rule out B: that is 1 -> 2. If this returned
  // 'leave', B would land in a shut list and the script's line "the card row
  // then moves down to the left-out list" would be a claim about something
  // the judge cannot see.
  assert.equal(decideConsidered(1, 2), 'open')
  assert.equal(decideConsidered(2, 3), 'open')
})

test('a re-solve that changes nothing leaves a hand-collapsed list alone', () => {
  // The counterweight: if any response reopened it, collapsing it by hand
  // would be impossible while an override was active.
  assert.equal(decideConsidered(1, 1), 'leave')
  assert.equal(decideConsidered(0, 0), 'leave')
  assert.equal(decideConsidered(3, 3), 'leave')
})

test('clearing the last override closes it', () => {
  assert.equal(decideConsidered(1, 0), 'close')
  assert.equal(decideConsidered(4, 0), 'close')
})

test('un-ticking one of several overrides does not close it', () => {
  // Still ruled out, still rows in the list.
  assert.equal(decideConsidered(3, 2), 'leave')
})

test('the full Safari sequence: tick, collapse by hand, tick again', () => {
  // armOnToggle returns null when a checkbox is activated without being
  // focused, which is the documented Safari mouse-click case, so the
  // imperative open in App's focus-restore effect never fires there. This
  // rule is the only thing keeping the second row visible.
  const open1 = decideConsidered(0, 1)
  assert.equal(open1, 'open')
  // The reader collapses it. No override count changes, so nothing here runs.
  // Then they rule out a second change:
  const open2 = decideConsidered(1, 2)
  assert.equal(open2, 'open', 'the second row would land in a shut list')
})

test('reset from a hand-opened list is NOT expressible here', () => {
  // Deliberate, and the reason App also closes it explicitly in adopt() and
  // the clear-overrides handler: a reader who opens the list by hand with no
  // overrides and then presses a preset produces 0 -> 0.
  assert.equal(decideConsidered(0, 0), 'leave')
})

import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  DEFAULT_TAB,
  TABS,
  isPlanVisible,
  label,
  showsAlarmDot,
} from '../src/lib/tabs.ts'

test('there are two tabs, plan and ask', () => {
  assert.deepEqual([...TABS], ['plan', 'ask'])
})

test('the app opens on the plan tab', () => {
  // The four-minute demo runs entirely here. Opening anywhere else costs a
  // click before the first word.
  assert.equal(DEFAULT_TAB, 'plan')
})

test('the pills are called Plan and Ask', () => {
  assert.equal(label('plan'), 'Plan')
  assert.equal(label('ask'), 'Ask')
})

test('the plan list is on screen only on the plan tab', () => {
  assert.equal(isPlanVisible('plan'), true)
  assert.equal(isPlanVisible('ask'), false)
})

test('the alarm dot is spent only on tier 3', () => {
  assert.equal(showsAlarmDot('plan', 3), true)
  assert.equal(showsAlarmDot('plan', 1), false)
  assert.equal(showsAlarmDot('plan', 2), false)
})

test('the alarm dot belongs to the plan pill, never the ask pill', () => {
  // It is a pointer at the tab whose verdict is off screen. On the ask pill it
  // would be pointing at itself.
  assert.equal(showsAlarmDot('ask', 3), false)
})

test('every tab has a label, so no pill can render empty', () => {
  for (const t of TABS) assert.ok(label(t).length > 0, `${t} has no label`)
})

test('the default tab is one of the tabs', () => {
  assert.ok(TABS.includes(DEFAULT_TAB))
})

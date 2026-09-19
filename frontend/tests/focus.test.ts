import { test } from 'node:test'
import assert from 'node:assert/strict'
import { armOnToggle, decideRestore, domId } from '../src/lib/focus.ts'

test('toggling the row you are standing on remembers it', () => {
  assert.equal(armOnToggle(null, { activeElementId: 'cant-c_gym', toggledId: 'c_gym' }), 'c_gym')
})

test('activating a row without focusing it forgets any older row', () => {
  // Safari does not focus a checkbox when you click it. Holding an older id
  // here is how focus ends up jumping to a row the user left minutes ago.
  assert.equal(armOnToggle('c_gym', { activeElementId: null, toggledId: 'c_card_min' }), null)
  assert.equal(
    armOnToggle('c_gym', { activeElementId: 'some-other-control', toggledId: 'c_card_min' }),
    null,
  )
})

test('toggling one row while standing on another keeps the one you are on', () => {
  assert.equal(
    armOnToggle('c_gym', { activeElementId: 'cant-c_amzn', toggledId: 'c_card_min' }),
    'c_gym',
  )
})

test('nothing is restored when no row is remembered', () => {
  assert.deepEqual(decideRestore({ refId: null, focusWasLost: true, settled: true }), {
    focus: null,
    clear: false,
  })
})

test('focus the user moved deliberately is left alone, and tracking stops', () => {
  assert.deepEqual(decideRestore({ refId: 'c_card_min', focusWasLost: false, settled: true }), {
    focus: null,
    clear: true,
  })
})

test('focus lost to an unmounted row is restored and then forgotten', () => {
  assert.deepEqual(decideRestore({ refId: 'c_card_min', focusWasLost: true, settled: true }), {
    focus: 'c_card_min',
    clear: true,
  })
})

test('a tick and a quick undo keep the row across both responses', () => {
  // The audit case: the first response restores focus, and consuming the id
  // there leaves the second response with nothing to put focus back on.
  const first = decideRestore({ refId: 'c_card_min', focusWasLost: true, settled: false })
  assert.deepEqual(first, { focus: 'c_card_min', clear: false })
  const second = decideRestore({ refId: 'c_card_min', focusWasLost: true, settled: true })
  assert.deepEqual(second, { focus: 'c_card_min', clear: true })
})

test('an unrelated re-solve after settling restores nothing', () => {
  const after = decideRestore({ refId: null, focusWasLost: true, settled: true })
  assert.equal(after.focus, null)
})

test('the checkbox id is derived from the candidate id', () => {
  assert.equal(domId('c_gym'), 'cant-c_gym')
})

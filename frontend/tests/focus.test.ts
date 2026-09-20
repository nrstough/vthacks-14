import { test } from 'node:test'
import assert from 'node:assert/strict'
import { armOnToggle, decideRestore, domId, sameInputs } from '../src/lib/focus.ts'
import type { FocusRequest } from '../src/lib/focus.ts'

function req(over: Partial<FocusRequest> = {}): FocusRequest {
  return {
    as_of: '2026-09-19',
    horizon_end: '2026-10-02',
    opening_balance_cents: 20000,
    buffer_cents: 2500,
    locks: { in: [], out: [] },
    ...over,
  }
}

test('toggling the row you are standing on remembers it', () => {
  assert.equal(armOnToggle({ activeElementId: 'cant-c_gym', toggledId: 'c_gym' }), 'c_gym')
})

test('activating a row without focusing it forgets any older row', () => {
  // Safari does not focus a checkbox when you click it. Holding an older id
  // here is how focus ends up jumping to a row the user left minutes ago.
  assert.equal(armOnToggle({ activeElementId: null, toggledId: 'c_card_min' }), null)
  assert.equal(
    armOnToggle({ activeElementId: 'some-other-control', toggledId: 'c_card_min' }),
    null,
  )
})

test('toggling one row while standing on another keeps the one you are on', () => {
  // Read from the DOM rather than trusting the remembered row: focus events do
  // not fire in every environment, so `onFocusRow` cannot be the only source.
  assert.equal(armOnToggle({ activeElementId: 'cant-c_amzn', toggledId: 'c_card_min' }), 'c_amzn')
})

test('nothing is restored when no row is remembered', () => {
  assert.deepEqual(decideRestore({ refId: null, focusWasLost: true, settled: true, planVisible: true }), {
    focus: null,
    clear: false,
  })
})

test('focus the user moved deliberately is left alone, and tracking stops', () => {
  assert.deepEqual(decideRestore({ refId: 'c_card_min', focusWasLost: false, settled: true, planVisible: true }), {
    focus: null,
    clear: true,
  })
})

test('focus lost to an unmounted row is restored and then forgotten', () => {
  assert.deepEqual(decideRestore({ refId: 'c_card_min', focusWasLost: true, settled: true, planVisible: true }), {
    focus: 'c_card_min',
    clear: true,
  })
})

test('a response landing while the plan list is hidden restores nothing', () => {
  const d = decideRestore({
    refId: 'c_card_min',
    focusWasLost: true,
    settled: true,
    planVisible: false,
  })
  assert.equal(d.focus, null)
})

test('and it does not forget the row, which is the whole point of the guard', () => {
  // The caller applies `clear` BEFORE it goes looking for the element, so
  // returning clear:true here would discard the row on the way past and lose
  // it for good — the answer landed on the Ask tab, where the checkbox is not
  // mounted, so there was never anything to restore it to.
  //
  // Delete the planVisible branch in decideRestore and this fails: `clear`
  // falls back to `settled`, which is true. A test asserting only on `focus`
  // would pass against that, because `focus` is null either way.
  const hidden = decideRestore({
    refId: 'c_card_min',
    focusWasLost: true,
    settled: true,
    planVisible: false,
  })
  assert.equal(hidden.clear, false)

  // Same inputs with the list on screen: restored and then forgotten.
  const shown = decideRestore({
    refId: 'c_card_min',
    focusWasLost: true,
    settled: true,
    planVisible: true,
  })
  assert.deepEqual(shown, { focus: 'c_card_min', clear: true })
})

test('a tick and a quick undo keep the row across both responses', () => {
  // The audit case: the first response restores focus, and consuming the id
  // there leaves the second response with nothing to put focus back on.
  const first = decideRestore({ refId: 'c_card_min', focusWasLost: true, settled: false, planVisible: true })
  assert.deepEqual(first, { focus: 'c_card_min', clear: false })
  const second = decideRestore({ refId: 'c_card_min', focusWasLost: true, settled: true, planVisible: true })
  assert.deepEqual(second, { focus: 'c_card_min', clear: true })
})

test('a row still focused is remembered while newer input is pending', () => {
  // Codex audit: an older response can land inside a newer toggle's debounce.
  // The row is still mounted, so nothing is restored — but forgetting it here
  // means the newer response moves that row with nothing left to focus.
  const older = decideRestore({ refId: 'c_card_min', focusWasLost: false, settled: false, planVisible: true })
  assert.deepEqual(older, { focus: null, clear: false })
  const newer = decideRestore({ refId: 'c_card_min', focusWasLost: true, settled: true, planVisible: true })
  assert.deepEqual(newer, { focus: 'c_card_min', clear: true })
})

test('overlapping responses never drop the row before the last one lands', () => {
  // Three responses for two toggles: only the final, settled one forgets it.
  const steps = [
    { focusWasLost: false, settled: false, planVisible: true },
    { focusWasLost: true, settled: false, planVisible: true },
    { focusWasLost: true, settled: true, planVisible: true },
  ]
  let ref: string | null = 'c_card_min'
  const restored: (string | null)[] = []
  for (const step of steps) {
    const d = decideRestore({ refId: ref, ...step })
    restored.push(d.focus)
    if (d.clear) ref = null
  }
  assert.deepEqual(restored, [null, 'c_card_min', 'c_card_min'])
  assert.equal(ref, null)
})

test('an unrelated re-solve after settling restores nothing', () => {
  const after = decideRestore({ refId: null, focusWasLost: true, settled: true, planVisible: true })
  assert.equal(after.focus, null)
})

test('the checkbox id is derived from the candidate id', () => {
  assert.equal(domId('c_gym'), 'cant-c_gym')
})

test('two requests asking the same question compare equal', () => {
  assert.equal(sameInputs(req(), req()), true)
  assert.equal(
    sameInputs(req({ locks: { in: [], out: ['c_gym'] } }), req({ locks: { in: [], out: ['c_gym'] } })),
    true,
  )
})

test('a pending balance change means the answer on screen is not the current one', () => {
  // Codex audit: settled was derived from the overrides alone, so dragging the
  // balance while a solve was in flight looked settled, the remembered row was
  // dropped, and the next response moved it with nothing left to focus.
  assert.equal(sameInputs(req(), req({ opening_balance_cents: 30000 })), false)
})

test('a pending cushion change counts too', () => {
  assert.equal(sameInputs(req(), req({ buffer_cents: 10000 })), false)
})

test('different overrides are not the same question', () => {
  assert.equal(sameInputs(req(), req({ locks: { in: [], out: ['c_gym'] } })), false)
  assert.equal(
    sameInputs(
      req({ locks: { in: [], out: ['c_gym'] } }),
      req({ locks: { in: [], out: ['c_amzn'] } }),
    ),
    false,
  )
})

test('a different horizon is not the same question', () => {
  assert.equal(sameInputs(req(), req({ as_of: '2026-09-20' })), false)
  assert.equal(sameInputs(req(), req({ horizon_end: '2026-10-09' })), false)
})

test('the row survives a balance drag landing between two responses', () => {
  // The exact sequence: an older response arrives while a newer request is
  // still pending, with the row mounted. Nothing is restored, and the row must
  // NOT be forgotten, or the newer response has nothing to put focus on.
  const older = decideRestore({ refId: 'c_gym', focusWasLost: false, settled: false, planVisible: true })
  assert.deepEqual(older, { focus: null, clear: false })
  const newer = decideRestore({ refId: 'c_gym', focusWasLost: true, settled: true, planVisible: true })
  assert.deepEqual(newer, { focus: 'c_gym', clear: true })
})

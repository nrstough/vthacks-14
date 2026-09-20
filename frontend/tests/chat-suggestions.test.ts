// Offers from the explainer: what they resolve to, and what they never do.
//
// The runner is `node --experimental-strip-types --test` — no DOM, no React.
// So the claim that carries this feature's safety is asserted here, on the
// pure layer, rather than against the component: `resolve` returns a value and
// changes nothing, and the only thing that can change state is App calling a
// setter with that value. The component honouring that is checked by the type
// system, by a grep on the built bundle, and by hand in the browser — said
// plainly in the run spec rather than implied to be automated.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readSuggestions } from '../src/lib/chat.ts'
import type { Suggestion } from '../src/lib/chat.ts'
import {
  CUSHION_MAX,
  SLIDER_STEP,
  clampCushion,
  clampOpening,
  keyOf,
  labelFor,
  resolve,
} from '../src/lib/suggestions.ts'
import { allow, isRuledOut, ruleOut, toggle } from '../src/lib/overrides.ts'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { sliderBounds } from '../src/lib/accounts.ts'
import { money } from '../src/lib/format.ts'

const OPENING = 24_000
const KNOWN = new Set(['c_gym', 'c_rent'])

function offer(kind: Suggestion['kind'], id: string | null, cents: number | null): Suggestion {
  return { kind, candidate_id: id, amount_cents: cents }
}

const nameOf = (id: string) => (id === 'c_gym' ? 'Gym membership' : id)

// --------------------------------------------------------------------------
// the safety claim
// --------------------------------------------------------------------------

test('an offer resolves to a value and moves nothing by itself', () => {
  // The whole feature in one assertion: resolving is a pure read. Anything
  // that changes has to be handed to a setter by App, on a tap.
  const before = new Set(['c_rent'])
  const r = resolve(offer('rule_out', 'c_gym', null), OPENING, KNOWN)
  assert.deepEqual(r, { kind: 'rule_out', id: 'c_gym' })
  assert.deepEqual([...before], ['c_rent'])
  assert.equal(isRuledOut(before, 'c_gym'), false)
})

test('an offer with no usable payload resolves to nothing', () => {
  assert.equal(resolve(offer('rule_out', null, null), OPENING, KNOWN), null)
  assert.equal(resolve(offer('opening', null, null), OPENING, KNOWN), null)
})

// --------------------------------------------------------------------------
// directional, where the row control is a flip
// --------------------------------------------------------------------------

test('ruling out a change already ruled out by hand leaves it ruled out', () => {
  // Through `toggle` this would put the change back, which is the opposite of
  // what the person approved.
  const already = new Set(['c_gym'])
  assert.equal(isRuledOut(ruleOut(already, 'c_gym'), 'c_gym'), true)
  assert.equal(isRuledOut(toggle(already, 'c_gym'), 'c_gym'), false)
})

test('approving the same offer twice changes nothing the second time', () => {
  const once = ruleOut(new Set<string>(), 'c_gym')
  assert.equal(ruleOut(once, 'c_gym'), once, 'the same set is returned, so no re-solve')
})

test('putting a change back is the other direction, not another flip', () => {
  const out = new Set(['c_gym'])
  assert.equal(isRuledOut(allow(out, 'c_gym'), 'c_gym'), false)
  assert.equal(allow(new Set<string>(), 'c_gym').size, 0)
})

// --------------------------------------------------------------------------
// money: the button says what lands
// --------------------------------------------------------------------------

test('a cushion above the slider is clamped to the slider', () => {
  assert.equal(clampCushion(25_000), CUSHION_MAX)
})

test('a negative cushion is clamped to zero', () => {
  assert.equal(clampCushion(-5_000), 0)
})

test('a cushion off the step is snapped onto it', () => {
  assert.equal(clampCushion(5_240) % SLIDER_STEP, 0)
  assert.equal(clampCushion(5_240), 5_000)
  assert.equal(clampCushion(5_260), 5_500)
})

test('snapping never lands above the maximum', () => {
  // Rounding up at the top of the range is how a value ends one step past the
  // end of the control that is supposed to represent it.
  assert.ok(clampCushion(CUSHION_MAX - 1) <= CUSHION_MAX)
  assert.ok(clampCushion(CUSHION_MAX + 999) <= CUSHION_MAX)
})

test('an opening balance is clamped but never snapped', () => {
  // The opening slider recomputes its floor from the current value, so every
  // integer balance is representable and snapping would discard cents.
  const odd = 24_137
  assert.equal(clampOpening(odd, OPENING), odd)
  assert.notEqual(odd % SLIDER_STEP, 0)
})

test('an opening balance outside the slider is pulled inside it', () => {
  const { min, max } = sliderBounds(OPENING)
  assert.equal(clampOpening(max + 10_000, OPENING), max)
  assert.equal(clampOpening(min - 10_000, OPENING), min)
})

test('the label carries the value that will actually apply', () => {
  // Acceptance criterion 9. The panel labels from `resolve` and App applies
  // from `resolve`, so a clamped offer cannot promise $250 and deliver $100.
  const r = resolve(offer('cushion', null, 25_000), OPENING, KNOWN)
  assert.deepEqual(r, { kind: 'cushion', cents: CUSHION_MAX })
  assert.equal(labelFor(r!, nameOf), `Set cushion to ${money(CUSHION_MAX)}`)
  assert.ok(!labelFor(r!, nameOf).includes('250'))
})

test('a label names the change rather than repeating the model', () => {
  const r = resolve(offer('rule_out', 'c_gym', null), OPENING, KNOWN)
  assert.equal(labelFor(r!, nameOf), 'Rule out Gym membership')
})

test('no label uses a banned word', () => {
  const all = [
    resolve(offer('rule_out', 'c_gym', null), OPENING, KNOWN),
    resolve(offer('allow', 'c_gym', null), OPENING, KNOWN),
    resolve(offer('opening', null, 20_000), OPENING, KNOWN),
    resolve(offer('cushion', null, 5_000), OPENING, KNOWN),
  ].map((r) => labelFor(r!, nameOf).toLowerCase())
  for (const text of all) {
    assert.doesNotMatch(text, /guarantee/)
    assert.doesNotMatch(text, /infeasib/)
  }
})

// --------------------------------------------------------------------------
// keys, and what comes off the wire
// --------------------------------------------------------------------------

test('the same change offered again later is a new offer', () => {
  // A content-derived key would render a legitimate second offer already
  // approved; a bare index would collide between two offers on one message.
  assert.notEqual(keyOf(1, 0), keyOf(6, 0))
  assert.notEqual(keyOf(1, 0), keyOf(1, 1))
})

test('a malformed suggestion off the wire is dropped, not coerced', () => {
  const raw = [
    { kind: 'rule_out', candidate_id: 'c_gym', amount_cents: null },
    { kind: 'nonsense', candidate_id: 'c_x', amount_cents: null },
    { kind: 'rule_out', candidate_id: 42, amount_cents: null },
    { kind: 'opening', candidate_id: null, amount_cents: '20000' },
    { kind: 'opening', candidate_id: null, amount_cents: 1.5 },
    null,
    'nope',
  ]
  assert.deepEqual(readSuggestions(raw), [
    { kind: 'rule_out', candidate_id: 'c_gym', amount_cents: null },
  ])
})

test('a response with no suggestions field reads as none', () => {
  assert.deepEqual(readSuggestions(undefined), [])
  assert.deepEqual(readSuggestions({}), [])
})

// --------------------------------------------------------------------------
// the id is re-checked against the account as it is NOW
// --------------------------------------------------------------------------

test('an offer naming a change that is not in the account resolves to nothing', () => {
  // The server validated the id when the offer was made. The account can move
  // underneath an offer still on screen, and an unknown id reaching locks.out
  // 422s the solve, which drops the app to the local solver — turning a stale
  // offer into a disclosure the footer then has to make.
  assert.equal(resolve(offer('rule_out', 'c_vanished', null), OPENING, KNOWN), null)
  assert.equal(resolve(offer('allow', 'c_vanished', null), OPENING, KNOWN), null)
})

test('an amount offer does not depend on the candidate set', () => {
  assert.deepEqual(resolve(offer('cushion', null, 5_000), OPENING, new Set()), {
    kind: 'cushion',
    cents: 5_000,
  })
})

test('a suggestion carrying both payloads is refused off the wire', () => {
  // The server's own validator forbids this shape. Billing the client check as
  // a second look while it was weaker than the first defeated the point.
  assert.deepEqual(
    readSuggestions([{ kind: 'rule_out', candidate_id: 'c_gym', amount_cents: 5 }]),
    [],
  )
})

test('more offers than the cap are not trusted off the wire', () => {
  const many = Array.from({ length: 50 }, () => ({
    kind: 'rule_out',
    candidate_id: 'c_gym',
    amount_cents: null,
  }))
  assert.equal(readSuggestions(many).length, 3)
})

// --------------------------------------------------------------------------
// the wiring, asserted on the source
// --------------------------------------------------------------------------
//
// There is no DOM here, but the component is still a file. These read it and
// pin the two invariants that no unit test of the pure layer can reach. They
// are coarse by nature; a refactor will need them updated, which is the price
// of covering the thing at all rather than declaring it uncoverable.

const SRC = (f: string) =>
  readFileSync(join(import.meta.dirname, '..', 'src', f), 'utf8')

test('the panel only ever applies an offer from a click handler', () => {
  // Acceptance criterion 4, as close as this runner gets to it: the single
  // call to onApply lives inside `approve`, and `approve` is reached only from
  // an onClick. Nothing on the receive path can call it.
  const src = SRC('components/ChatPanel.tsx')
  const calls = src.split('onApply?.(').length - 1
  assert.equal(calls, 1, 'onApply should be called in exactly one place')

  const body = src.slice(src.indexOf('function approve('))
  const end = body.indexOf('\n  }')
  assert.ok(body.slice(0, end).includes('onApply?.('), 'the call must be inside approve()')

  assert.match(src, /onClick=\{\(\) => approve\(/)

  // The deferred-response guard: a reply sent before an account change must
  // not land after it. Delete either half and every behavioural test stays
  // green, which is exactly the condition that let the accountGen defect ship.
  assert.match(src, /const sentAt = generation/)
  assert.match(src, /sentAt !== genNow\.current/)
  assert.match(src, /genNow\.current = generation[\s\S]{0,120}inFlight\.current\.abort\(\)/)

  // And the abort must release the input. `send`'s finally deliberately leaves
  // `pending` alone on an abort, because there it always came from a newer send
  // that had just set it. This abort has no newer send behind it, so without
  // this the box and the Ask button stay disabled for the rest of the session
  // after any account change mid-reply.
  assert.match(src, /inFlight\.current\.abort\(\)[\s\S]{0,600}setPending\(false\)/)
  // Two and only two: the declaration, and the click handler that reaches it.
  // A third would be a second route into applying an offer, which is the thing
  // this test exists to prevent.
  const mentions = src.split('approve(').length - 1
  assert.equal(mentions, 2, 'approve() should be declared once and called only from onClick')
})

test('the panel is told about accounts, not about solves', () => {
  // The regression test for the one defect that shipped broken. `seq`
  // increments on every solve, so wiring it to `generation` cleared the offer
  // being approved at the moment of approving it. Every unit test passed
  // either way, because the bug was in which counter a prop was given.
  const app = SRC('App.tsx')
  assert.match(app, /generation=\{accountGen\}/)
  assert.doesNotMatch(app, /generation=\{seq\.current\}/)

  // Criterion 9 holds only because the panel gets the UNDEBOUNCED request: the
  // label clamps against req.opening_balance_cents and App re-clamps against
  // the committed opening, and those are the same value only while this is
  // `request`. Switching to `debounced` to cut chat re-renders would look like
  // a tidy-up and would silently make the button lie by up to 150 ms.
  assert.doesNotMatch(app, /req=\{debounced\}/)
  const adopt = app.slice(app.indexOf('function adopt('))
  assert.ok(
    adopt.slice(0, adopt.indexOf('\n  }')).includes('setAccountGen'),
    'adopt() must bump the account generation',
  )
})

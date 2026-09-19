import { test } from 'node:test'
import assert from 'node:assert/strict'
import { crashDetail } from '../src/lib/crash.ts'

test('an Error shows its message', () => {
  assert.equal(crashDetail(new Error('cannot read length of undefined')), 'cannot read length of undefined')
})

test('an Error with no message falls back to its name', () => {
  assert.equal(crashDetail(new TypeError('')), 'TypeError')
})

// `throw` takes any value, and the non-Error cases are the ones that would
// otherwise render as "[object Object]" or an empty box.
test('a thrown string is shown as itself', () => {
  assert.equal(crashDetail('solver returned nothing'), 'solver returned nothing')
})

test('thrown null and undefined still name themselves', () => {
  assert.equal(crashDetail(null), 'null was thrown')
  assert.equal(crashDetail(undefined), 'undefined was thrown')
})

test('a thrown object is serialised rather than stringified to [object Object]', () => {
  assert.equal(crashDetail({ status: 422 }), '{"status":422}')
})

test('a circular object does not throw a second error out of the handler', () => {
  const circular: Record<string, unknown> = { a: 1 }
  circular.self = circular
  assert.doesNotThrow(() => crashDetail(circular))
  assert.ok(crashDetail(circular).length > 0)
})

// Fails if the collapse is removed: a stack-shaped message would keep its
// newlines and push the reload button off a laptop screen.
test('whitespace is collapsed to one line', () => {
  assert.equal(crashDetail(new Error('at foo\n  at bar\n\n  at baz')), 'at foo at bar at baz')
})

// Fails if the cap is removed.
test('a very long message is truncated with an ellipsis', () => {
  const detail = crashDetail(new Error('x'.repeat(5000)))
  assert.equal(detail.length, 300)
  assert.ok(detail.endsWith('…'))
})

test('a message that collapses to nothing still says something', () => {
  assert.equal(crashDetail('   '), 'No detail was attached to the error.')
})

// CLAUDE.md bans both words from reaching the user. Everywhere else that holds
// because the copy was written to avoid them; here the string comes from code
// nobody in this project wrote, so it has to be checked at runtime.
// Fails if the FORBIDDEN guard is removed.
const FORBIDDEN = [/guarantee/i, /infeasib/i]

test('a thrown message using banned wording never reaches the screen', () => {
  const thrown = [
    new Error('CP-SAT returned INFEASIBLE for this model'),
    new Error('the provider cannot guarantee delivery'),
    'Guaranteed minimum not met',
    { detail: 'solver reported infeasible' },
  ]
  for (const e of thrown) {
    const out = crashDetail(e)
    for (const bad of FORBIDDEN) assert.doesNotMatch(out, bad)
    assert.ok(out.length > 0)
  }
})

// The guard must not swallow ordinary errors — a crash card that says nothing
// useful about every failure is its own defect.
test('an ordinary message is still shown in full', () => {
  assert.equal(crashDetail(new Error('Cannot read properties of undefined')), 'Cannot read properties of undefined')
})

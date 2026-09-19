import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  compareAmounts,
  formatAmount,
  formatUnits,
  parseUnits,
  toBase,
  toSigned,
} from '../src/wallet/units.ts'

function ok(input: string, decimals = 2): bigint {
  const r = parseUnits(input, decimals)
  assert.equal(r.ok, true, `${input} should parse`)
  if (!r.ok) throw new Error('unreachable')
  return r.value
}

function reason(input: string, decimals = 2): string {
  const r = parseUnits(input, decimals)
  assert.equal(r.ok, false, `${input} should be rejected`)
  if (r.ok) throw new Error('unreachable')
  return r.reason
}

test('a two-decimal amount is exact base units', () => {
  assert.equal(ok('12.34'), 1234n)
})

// The whole point of the padEnd: "0.5" is five tenths, which is 50 hundredths.
// A naive /^\d+\.\d{2}$/ parser hides this by rejecting the input instead.
// Fails if padEnd becomes padStart, or if the fraction is parsed on its own.
test('a one-decimal amount pads on the right, not the left', () => {
  assert.equal(ok('0.5'), 50n)
  assert.equal(ok('1.5'), 150n)
})

test('a whole number with no point is scaled', () => {
  assert.equal(ok('12'), 1200n)
})

test('leading zeros do not change the value', () => {
  assert.equal(ok('00012.34'), 1234n)
})

test('surrounding whitespace is trimmed', () => {
  assert.equal(ok(' 12.34 '), 1234n)
})

test('zero decimals means the input is already base units', () => {
  assert.equal(ok('1234', 0), 1234n)
})

// Each rejection names a DIFFERENT reason. A parser that refuses everything on one
// shared branch would pass a test that only checked ok === false, which is how five
// assertions come to exercise one line.
test('every rejection has its own distinct reason', () => {
  assert.equal(reason(''), 'empty')
  assert.equal(reason('   '), 'empty')
  assert.equal(reason('-1'), 'negative')
  assert.equal(reason('1e3'), 'exponent')
  assert.equal(reason('12,34'), 'malformed')
  assert.equal(reason('12.'), 'malformed')
  assert.equal(reason('.34'), 'malformed')
  assert.equal(reason('abc'), 'malformed')
  assert.equal(reason('12.345'), 'too_many_decimals')
  assert.equal(reason('0'), 'zero')
  assert.equal(reason('0.00'), 'zero')
})

test('the reasons are genuinely distinct, not one value repeated', () => {
  const reasons = new Set(['', '-1', '1e3', '12,34', '12.345', '0'].map((s) => reason(s)))
  assert.equal(reasons.size, 6)
})

test('formatUnits pads the fraction and never loses a leading zero', () => {
  assert.equal(formatUnits(1234n, 2), '12.34')
  assert.equal(formatUnits(5n, 2), '0.05')
  assert.equal(formatUnits(0n, 2), '0.00')
  assert.equal(formatUnits(50n, 2), '0.50')
})

test('formatUnits carries the sign outside the digits', () => {
  assert.equal(formatUnits(-1234n, 2), '-12.34')
  assert.equal(formatUnits(-5n, 2), '-0.05')
})

test('formatUnits at zero decimals emits no point', () => {
  assert.equal(formatUnits(1234n, 0), '1234')
})

// The reason this module exists at all. Number(base)/100 is correct for every
// amount in the demo and wrong here, silently.
// Fails if formatUnits is reimplemented with Number arithmetic.
test('formatUnits is exact past the safe-integer range', () => {
  assert.equal(formatUnits(12345678901234567890n, 2), '123456789012345678.90')
})

test('parse and format round-trip', () => {
  for (const s of ['12.34', '0.05', '1.00', '999999999999.99']) {
    assert.equal(formatUnits(ok(s), 2), s)
  }
})

test('formatAmount labels the token and never uses a dollar sign', () => {
  const text = formatAmount(1234n, 2, 'DEMO')
  assert.equal(text, '12.34 DEMO')
  assert.doesNotMatch(text, /\$/)
})

// Fails if toBase is relaxed to accept a number, which is exactly what reading
// the RPC's uiAmount field would hand it.
test('toBase accepts only exact digit strings', () => {
  assert.equal(toBase('1234'), 1234n)
  assert.equal(toBase('0'), 0n)
  for (const bad of [12.34, 1234, '12.34', '-1', '', ' 1', null, undefined, {}, 1234n]) {
    assert.throws(() => toBase(bad), TypeError)
  }
})

test('toSigned accepts negatives and still refuses floats', () => {
  assert.equal(toSigned('-1234'), -1234n)
  assert.equal(toSigned('1234'), 1234n)
  for (const bad of [-12.34, '-12.34', '', '--1', null]) {
    assert.throws(() => toSigned(bad), TypeError)
  }
})

// This asserts the contract, not a counterfactual: a mutation to
// (a, b) => Number(a - b) killed no test, because that form sorts identically.
// The value here is the -1/0/1 range, which the second assertion pins.
test('compareAmounts orders correctly past the safe-integer range', () => {
  const a = 9007199254740993n
  const b = 9007199254740992n
  assert.equal(compareAmounts(a, b), 1)
  assert.equal(compareAmounts(b, a), -1)
  assert.equal(compareAmounts(a, a), 0)

  const sorted = [30n, 10n, 20n].sort(compareAmounts)
  assert.deepEqual(sorted, [10n, 20n, 30n])
})

// Fails if compareAmounts ever returns a raw difference: the magnitude below is
// past 2^53, so a Number(a - b) implementation returns 1.8014398509481984e16
// rather than 1, and anything reading the value rather than the sign is wrong.
test('compareAmounts returns only -1, 0 or 1', () => {
  const far = compareAmounts(18014398509481984n, 0n)
  assert.equal(far, 1)
  assert.ok(Math.abs(far) <= 1, 'the comparator must not leak a magnitude')
})

// formatUnits is presented as part of the float gate, so it has to behave like
// one. Without the guard, formatUnits(12.34, 2) returns the string "12..34" —
// silent garbage on screen, no throw, in a project whose rule is that no float
// touches money. The parsers were gated and this was not.
// Fails if the bigint check is removed.
test('formatUnits refuses anything that is not a bigint', () => {
  for (const bad of [12.34, 1234, '1234', null, undefined, {}]) {
    assert.throws(() => formatUnits(bad as unknown as bigint, 2), TypeError)
  }
})

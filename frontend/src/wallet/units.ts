// Decimal strings in, base units out, and back. Nothing here uses Number.
//
// src/lib/format.ts does the same job for cents and is the shape to follow — sign
// first, then integer division and remainder, then padStart. It is NOT the code to
// copy: it takes a `number` and hardcodes `$` and /100, both of which are wrong for
// a token. CLAUDE.md: money is integer everywhere and no floats touch money.

const DIGITS = /^\d+$/
const SIGNED_DIGITS = /^-?\d+$/
// Deliberately no exponent, no sign, no separators, and a dot only between digits:
// "12.", ".34", "1e3", "-1" and "12,34" are all rejected with distinct reasons so a
// test cannot pass five cases on one shared branch.
const DECIMAL = /^\d+(\.\d+)?$/

export type ParseFailure =
  | 'empty'
  | 'negative'
  | 'exponent'
  | 'malformed'
  | 'too_many_decimals'
  | 'zero'

export type ParseResult =
  | { readonly ok: true; readonly value: bigint }
  | { readonly ok: false; readonly reason: ParseFailure }

/**
 * A decimal amount a person typed, as exact base units.
 *
 * "0.5" at 2 decimals is 50n, not 5n — the fractional part is padded on the RIGHT,
 * which is the mistake a naive /^\d+\.\d{2}$/ implementation hides by rejecting the
 * input instead of mis-scaling it.
 */
export function parseUnits(input: string, decimals: number): ParseResult {
  const text = input.trim()
  if (text === '') return { ok: false, reason: 'empty' }
  if (text.startsWith('-')) return { ok: false, reason: 'negative' }
  if (/[eE]/.test(text)) return { ok: false, reason: 'exponent' }
  if (!DECIMAL.test(text)) return { ok: false, reason: 'malformed' }

  const dot = text.indexOf('.')
  const whole = dot === -1 ? text : text.slice(0, dot)
  const frac = dot === -1 ? '' : text.slice(dot + 1)
  if (frac.length > decimals) return { ok: false, reason: 'too_many_decimals' }

  const value = BigInt(whole + frac.padEnd(decimals, '0'))
  if (value === 0n) return { ok: false, reason: 'zero' }
  return { ok: true, value }
}

/**
 * Base units as a decimal string, by slicing — never Number(base) / 10 ** decimals,
 * which is correct for every amount in this demo and wrong above 2^53. The point of
 * using bigint at all is that the wrongness never becomes possible.
 */
export function formatUnits(base: bigint, decimals: number): string {
  const negative = base < 0n
  const digits = (negative ? -base : base).toString().padStart(decimals + 1, '0')
  const cut = digits.length - decimals
  const whole = digits.slice(0, cut)
  const frac = digits.slice(cut)
  const body = decimals === 0 ? whole : `${whole}.${frac}`
  return negative ? `-${body}` : body
}

/** Base units plus the token's own label. Never a `$`. */
export function formatAmount(base: bigint, decimals: number, symbol: string): string {
  return `${formatUnits(base, decimals)} ${symbol}`
}

/**
 * The single gate every chain-reported amount passes through.
 *
 * getTokenAccountBalance and getTransaction both return an exact `amount` string
 * AND a float `uiAmount`. Reading uiAmount puts a Number into the money path and
 * nothing fails until the value is large enough to lose a digit. Accepting only a
 * digits-string makes that impossible rather than merely discouraged.
 */
export function toBase(value: unknown): bigint {
  if (typeof value !== 'string' || !DIGITS.test(value)) {
    throw new TypeError('token amounts must arrive as exact digit strings')
  }
  return BigInt(value)
}

/** As toBase, for values that may legitimately be negative (schedule entries). */
export function toSigned(value: unknown): bigint {
  if (typeof value !== 'string' || !SIGNED_DIGITS.test(value)) {
    throw new TypeError('signed amounts must arrive as exact digit strings')
  }
  return BigInt(value)
}

/**
 * Ordering for bigint.
 *
 * Note what this is NOT: `(a, b) => Number(a - b)` is often called a bug here, and
 * for sorting it is not one — the difference of two integers never rounds to zero,
 * so the sign survives and sort behaves the same. A mutation swapping this for it
 * killed no test, which is the honest reason this comment no longer claims it would.
 *
 * It is still the form to use, because it returns only -1/0/1 and so cannot be
 * mistaken for, or refactored into, an actual difference — where the rounding above
 * 2^53 is real and silent.
 */
export function compareAmounts(a: bigint, b: bigint): number {
  return a < b ? -1 : a > b ? 1 : 0
}

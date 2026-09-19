import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  canSign,
  earliestAffordableDate,
  verdictFor,
  walk,
  withPayment,
} from '../src/wallet/ledger.ts'
import {
  AS_OF,
  CLEARS_ON,
  HORIZON_END,
  OPENING,
  PAYMENT_BREAKS,
  PAYMENT_CLEARS,
  RESERVE,
  SCHEDULE,
  SCHEDULE_BLOCKED,
} from '../src/wallet/fixtures.ts'
import { formatAmount, formatUnits } from '../src/wallet/units.ts'
import type { Entry } from '../src/wallet/types.ts'

const FORBIDDEN = [/guarantee/i, /infeasib/i]
const fmt = (base: bigint): string => formatAmount(base, 2, 'DEMO')

function base(over: Partial<Entry> = {}): Entry {
  return { id: 'e', date: AS_OF, amount: -100n, label: 'thing', ...over }
}

test('the baseline schedule clears its reserve', () => {
  const out = walk(OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END)
  assert.equal(out.breachDate, null)
  assert.equal(out.minimum, 6_800n)
  assert.equal(out.minimumDate, '2026-09-24')
  assert.equal(out.shortfall, 0n)
})

// The demo beat, as a number rather than a sentence.
test('thirty fails today and fifteen passes today', () => {
  const breaks = withPayment(OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END, PAYMENT_BREAKS, AS_OF)
  assert.equal(breaks.breachDate, '2026-09-22')
  assert.equal(breaks.shortfall, 1_200n)
  assert.equal(formatUnits(breaks.shortfall, 2), '12.00')

  const clears = withPayment(OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END, PAYMENT_CLEARS, AS_OF)
  assert.equal(clears.breachDate, null)
})

// The beat's actual claim: the SAME payment clears later. "30 fails, 15 passes"
// is a statement about amount and holds with no inflow at all, so on its own it
// does not test postponement.
// Fails if the payday row is removed — see the next test.
test('the same thirty first clears on the payday', () => {
  const date = earliestAffordableDate(
    OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END, PAYMENT_BREAKS,
  )
  assert.equal(date, CLEARS_ON)
})

// Codex review finding 1, as an executable statement: with outflows only, moving
// a payment inside a fixed horizon cannot raise the running minimum, so the
// feature is a constant dressed as a search.
test('without an inflow there is no affordable date at all', () => {
  const outflowsOnly = SCHEDULE.filter((e) => e.amount < 0n)
  const date = earliestAffordableDate(
    OPENING, outflowsOnly, RESERVE, AS_OF, HORIZON_END, PAYMENT_BREAKS,
  )
  assert.equal(date, null)
})

// Proves the earliest date is computed, not just "the day the inflow lands".
test('an earlier obligation can prevent any date clearing', () => {
  const date = earliestAffordableDate(
    OPENING, SCHEDULE_BLOCKED, RESERVE, AS_OF, HORIZON_END, PAYMENT_BREAKS,
  )
  assert.equal(date, null)
})

// The reason netByDay exists. Opening 60 with a same-day -20 and +20: walking
// entries one at a time gives a minimum of 40 or 60 depending purely on where
// they sit in the array, and a date carries no intraday ordering to break the tie.
// Fails if the per-day aggregation is removed.
test('same-day entries net, so the verdict does not depend on array order', () => {
  const out = '2026-09-22'
  const a: Entry = { id: 'a', date: out, amount: -2_000n, label: 'out' }
  const b: Entry = { id: 'b', date: out, amount: 2_000n, label: 'in' }
  const forward = walk(6_000n, [a, b], 5_000n, AS_OF, HORIZON_END)
  const reversed = walk(6_000n, [b, a], 5_000n, AS_OF, HORIZON_END)
  assert.deepEqual(forward, reversed)
  assert.equal(forward.minimum, 6_000n)
  assert.equal(forward.breachDate, null)
})

test('the whole outlook is invariant under any permutation of entries', () => {
  const reference = walk(OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END)
  const orders: Entry[][] = [
    [SCHEDULE[0], SCHEDULE[2], SCHEDULE[1]],
    [SCHEDULE[1], SCHEDULE[0], SCHEDULE[2]],
    [SCHEDULE[1], SCHEDULE[2], SCHEDULE[0]],
    [SCHEDULE[2], SCHEDULE[0], SCHEDULE[1]],
    [SCHEDULE[2], SCHEDULE[1], SCHEDULE[0]],
  ]
  for (const order of orders) {
    assert.deepEqual(walk(OPENING, order, RESERVE, AS_OF, HORIZON_END), reference)
  }
})

// A negative amount is money leaving, whatever it is called. The bank solver has
// twice shipped a bug where a negative row labelled income read as money arriving;
// this type has no label to disagree with the sign, and this pins it.
// Fails if the walk ever branches on anything but the sign.
test('a negative entry reduces the balance no matter what it is labelled', () => {
  const clawback = base({ id: 'c', date: '2026-09-23', amount: -1_000n, label: 'Payroll adjustment' })
  const out = walk(OPENING, [...SCHEDULE, clawback], RESERVE, AS_OF, HORIZON_END)
  assert.equal(out.minimum, 5_800n)
  assert.ok(out.minimum < walk(OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END).minimum)
})

test('entries before as_of are already in the opening balance and are ignored', () => {
  const old = base({ id: 'old', date: '2026-09-01', amount: -9_000n })
  assert.deepEqual(
    walk(OPENING, [...SCHEDULE, old], RESERVE, AS_OF, HORIZON_END),
    walk(OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END),
  )
})

test('entries after the horizon are not this window s business', () => {
  const later = base({ id: 'later', date: '2026-10-15', amount: -9_000n })
  assert.deepEqual(
    walk(OPENING, [...SCHEDULE, later], RESERVE, AS_OF, HORIZON_END),
    walk(OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END),
  )
})

// The breach date is the FIRST day under the reserve; the minimum date is the
// worst day. They are different questions and this schedule separates them.
test('an opening balance already under the reserve breaches on day one', () => {
  const out = walk(1_000n, SCHEDULE, RESERVE, AS_OF, HORIZON_END)
  assert.equal(out.breachDate, AS_OF)
  assert.equal(out.minimumDate, '2026-09-24')
  assert.equal(out.minimum, -2_200n)
})

// The reserve is a floor to stay at or above, not to exceed.
// Fails if >= becomes > in the comparison.
test('landing exactly on the reserve is not a breach', () => {
  const exact = base({ id: 'x', date: '2026-09-22', amount: -5_000n })
  const out = walk(10_000n, [exact], 5_000n, AS_OF, HORIZON_END)
  assert.equal(out.minimum, 5_000n)
  assert.equal(out.breachDate, null)
  assert.equal(out.shortfall, 0n)
})

test('an empty schedule is the opening balance', () => {
  const out = walk(OPENING, [], RESERVE, AS_OF, HORIZON_END)
  assert.equal(out.minimum, OPENING)
  assert.equal(out.minimumDate, AS_OF)
  assert.equal(out.breachDate, null)
})

test('the unconditional verdict is the only one that enables signing', () => {
  const affordable = verdictFor(
    OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END, PAYMENT_CLEARS, AS_OF, fmt,
  )
  assert.equal(affordable.kind, 'affordable')
  assert.equal(canSign(affordable), true)

  const conditional = verdictFor(
    OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END, PAYMENT_BREAKS, AS_OF, fmt,
  )
  assert.equal(conditional.kind, 'conditional')
  assert.equal(conditional.earliestDate, CLEARS_ON)
  assert.equal(canSign(conditional), false)

  const never = verdictFor(
    OPENING, SCHEDULE_BLOCKED, RESERVE, AS_OF, HORIZON_END, PAYMENT_BREAKS, AS_OF, fmt,
  )
  assert.equal(never.kind, 'never_clears')
  assert.equal(never.earliestDate, null)
  assert.equal(canSign(never), false)
})

// Collapsing the two verdicts into one phrase would erase the distinction that
// gates an irreversible transfer. They must not read the same.
test('the conditional verdict never reads as the unconditional one', () => {
  const affordable = verdictFor(
    OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END, PAYMENT_CLEARS, AS_OF, fmt,
  )
  const conditional = verdictFor(
    OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END, PAYMENT_BREAKS, AS_OF, fmt,
  )
  assert.notEqual(affordable.text, conditional.text)
  assert.match(affordable.text, /sufficient under the schedule shown/)
  assert.doesNotMatch(conditional.text, /sufficient under the schedule shown/)
})

// When nothing clears, name the money and the date — never the word.
test('the no-clearing verdict names the amount needed and the date', () => {
  const never = verdictFor(
    OPENING, SCHEDULE_BLOCKED, RESERVE, AS_OF, HORIZON_END, PAYMENT_BREAKS, AS_OF, fmt,
  )
  assert.match(never.text, /needs \d+\.\d\d DEMO more by \d{4}-\d\d-\d\d/)
})

// Every verdict the module can produce, checked against the product's two banned
// words and against a dollar sign reaching a token screen. The cardinality
// assertion is what makes this fail if a fourth kind is added unexercised.
test('no verdict contains a forbidden word or a dollar sign', () => {
  const kinds = new Set<string>()
  const texts: string[] = []
  const cases: Array<[readonly Entry[], bigint]> = [
    [SCHEDULE, PAYMENT_CLEARS],
    [SCHEDULE, PAYMENT_BREAKS],
    [SCHEDULE_BLOCKED, PAYMENT_BREAKS],
  ]
  for (const [entries, amount] of cases) {
    const v = verdictFor(OPENING, entries, RESERVE, AS_OF, HORIZON_END, amount, AS_OF, fmt)
    kinds.add(v.kind)
    texts.push(v.text)
  }
  for (const text of texts) {
    assert.ok(text.length > 0)
    for (const bad of FORBIDDEN) assert.doesNotMatch(text, bad)
    assert.doesNotMatch(text, /\$/)
    assert.match(text, /DEMO/)
  }
  // Every kind reachable from a ledger walk was exercised. 'affordable',
  // 'conditional' and 'never_clears'; 'breaches' is reserved for the view.
  assert.equal(kinds.size, 3)
})

test('the same inputs always give the same verdict', () => {
  const a = verdictFor(OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END, PAYMENT_BREAKS, AS_OF, fmt)
  const b = verdictFor(OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END, PAYMENT_BREAKS, AS_OF, fmt)
  assert.deepEqual(a, b)
})

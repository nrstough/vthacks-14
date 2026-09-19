import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  amountHint,
  balanceLine,
  headerChip,
  obligationRows,
  reserveLine,
  signState,
} from '../src/wallet/view.ts'
import type { Connection } from '../src/wallet/view.ts'
import { verdictFor } from '../src/wallet/ledger.ts'
import {
  AS_OF,
  DEMO,
  HORIZON_END,
  OPENING,
  PAYMENT_BREAKS,
  PAYMENT_CLEARS,
  RESERVE,
  SCHEDULE,
  SCHEDULE_BLOCKED,
} from '../src/wallet/fixtures.ts'
import { formatAmount } from '../src/wallet/units.ts'
import type { ParseFailure } from '../src/wallet/units.ts'

const FORBIDDEN = [/guarantee/i, /infeasib/i]
const fmt = (b: bigint): string => formatAmount(b, 2, 'DEMO')
const READY: Connection = { kind: 'ready', address: 'Abc123', balance: OPENING }
const GOOD = { ok: true }

function verdict(amount: bigint, entries = SCHEDULE) {
  return verdictFor(OPENING, entries, RESERVE, AS_OF, HORIZON_END, amount, AS_OF, fmt)
}

test('Sign is enabled only when everything holds', () => {
  const s = signState(READY, GOOD, verdict(PAYMENT_CLEARS))
  assert.equal(s.enabled, true)
  assert.equal(s.reason, null)
})

// The load-bearing rule: a conditional verdict describes a schedule nobody has
// brought about yet, so it can never enable an irreversible transfer.
// Fails if signState stops consulting canSign.
test('a conditional verdict never enables Sign', () => {
  const s = signState(READY, GOOD, verdict(PAYMENT_BREAKS))
  assert.equal(s.enabled, false)
  assert.match(s.reason as string, /does not clear the reserve/)
})

test('a verdict that never clears does not enable Sign either', () => {
  const s = signState(READY, GOOD, verdict(PAYMENT_BREAKS, SCHEDULE_BLOCKED))
  assert.equal(s.enabled, false)
})

// A dead RPC must say so and must never imply a transfer happened.
// Fails if the unavailable branch is removed.
test('an unreachable network disables Sign and says payment unavailable', () => {
  const s = signState({ kind: 'unavailable', detail: 'fetch failed' }, GOOD, verdict(PAYMENT_CLEARS))
  assert.equal(s.enabled, false)
  assert.match(s.reason as string, /Payment unavailable/)
})

test('the wrong network disables Sign and names the network observed', () => {
  const s = signState({ kind: 'wrong_network', observed: 'mainnet-beta' }, GOOD, verdict(PAYMENT_CLEARS))
  assert.equal(s.enabled, false)
  assert.match(s.reason as string, /mainnet-beta/)
  assert.match(s.reason as string, /Devnet/)
})

test('disconnected asks for a wallet', () => {
  const s = signState({ kind: 'disconnected' }, GOOD, verdict(PAYMENT_CLEARS))
  assert.equal(s.enabled, false)
  assert.match(s.reason as string, /Connect a wallet/)
})

// The reason shown is the FIRST thing wrong, not the last checked: a
// disconnected wallet with a bad amount still says to connect.
test('the reason names the first problem, not the last', () => {
  const s = signState({ kind: 'disconnected' }, { ok: false, reason: 'zero' }, null)
  assert.match(s.reason as string, /Connect a wallet/)
})

test('a bad amount disables Sign with a reason specific to it', () => {
  const s = signState(READY, { ok: false, reason: 'too_many_decimals' }, null)
  assert.equal(s.enabled, false)
  assert.match(s.reason as string, /two decimal places/)
})

test('no verdict yet asks for an amount rather than claiming anything', () => {
  const s = signState(READY, GOOD, null)
  assert.equal(s.enabled, false)
  assert.match(s.reason as string, /Enter an amount/)
})

// Every rejection the parser can produce must have its own sentence, or the
// hint is a shrug with extra steps.
test('every parse failure has a distinct hint', () => {
  const failures: ParseFailure[] = [
    'empty', 'negative', 'zero', 'exponent', 'too_many_decimals', 'malformed',
  ]
  const hints = failures.map((f) => amountHint(f))
  assert.equal(new Set(hints).size, failures.length)
  for (const h of hints) assert.ok(h.length > 0)
  // An unknown reason still produces a line rather than undefined on screen.
  assert.ok(amountHint(undefined).length > 0)
})

// A custom demo token is not USDC and must never read as real money.
test('the header always names the network', () => {
  assert.equal(headerChip(DEMO), 'Demo wallet — Solana Devnet')
})

test('a disconnected balance is a placeholder, never a number', () => {
  assert.equal(balanceLine({ kind: 'disconnected' }, DEMO), '— DEMO')
  assert.equal(balanceLine({ kind: 'unavailable', detail: 'x' }, DEMO), '— DEMO')
  assert.equal(balanceLine(READY, DEMO), '100.00 DEMO')
})

// `incoming` comes from the sign and nothing else — there is no kind field to
// disagree with it. A negative row labelled like income is still outgoing.
// Fails if incoming is ever derived from the label.
test('an obligation is incoming by its sign, not its label', () => {
  const rows = obligationRows(
    [
      { id: 'a', date: '2026-09-25', amount: 6_000n, label: 'Payroll' },
      { id: 'b', date: '2026-09-26', amount: -3_000n, label: 'Payroll adjustment' },
    ],
    DEMO,
  )
  assert.equal(rows[0].incoming, true)
  assert.equal(rows[1].incoming, false)
  assert.equal(rows[1].amount, '-30.00 DEMO')
})

test('obligations come out in date order whatever order they went in', () => {
  const forward = obligationRows(SCHEDULE, DEMO).map((r) => r.date)
  const reversed = obligationRows([...SCHEDULE].reverse(), DEMO).map((r) => r.date)
  assert.deepEqual(forward, reversed)
  assert.deepEqual(forward, [...forward].sort())
})

test('the reserve line names the amount in tokens, never dollars', () => {
  const line = reserveLine(RESERVE, DEMO)
  assert.match(line, /50\.00 DEMO/)
  assert.doesNotMatch(line, /\$/)
})

// Every string this module can put on screen, against the two banned words and
// against a dollar sign reaching a token screen.
test('no wallet view string is forbidden or denominated in dollars', () => {
  const connections: Connection[] = [
    { kind: 'disconnected' },
    { kind: 'unavailable', detail: 'fetch failed' },
    { kind: 'wrong_network', observed: 'mainnet-beta' },
    READY,
  ]
  const texts: string[] = [headerChip(DEMO), reserveLine(RESERVE, DEMO), amountHint(undefined)]
  for (const c of connections) {
    texts.push(balanceLine(c, DEMO))
    for (const v of [null, verdict(PAYMENT_CLEARS), verdict(PAYMENT_BREAKS)]) {
      const r = signState(c, GOOD, v).reason
      if (r !== null) texts.push(r)
    }
  }
  for (const f of ['empty', 'negative', 'zero', 'exponent', 'too_many_decimals', 'malformed'] as ParseFailure[]) {
    texts.push(amountHint(f))
  }
  for (const text of texts) {
    assert.ok(text.length > 0)
    for (const bad of FORBIDDEN) assert.doesNotMatch(text, bad)
    assert.doesNotMatch(text, /\$/)
  }
  // Every connection kind was exercised above.
  assert.equal(new Set(connections.map((c) => c.kind)).size, 4)
})

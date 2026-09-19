import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  createMachine,
  deserializeAttempt,
  isTerminal,
  serializeAttempt,
} from '../src/wallet/state.ts'
import type { AttemptToken, Snapshot, Store } from '../src/wallet/state.ts'
import { canSign, verdictFor } from '../src/wallet/ledger.ts'
import {
  AS_OF,
  DEMO,
  HORIZON_END,
  PAYMENT_CLEARS,
  RECIPIENT,
  RESERVE,
  SCHEDULE,
  SENDER,
  SIGNATURE,
} from '../src/wallet/fixtures.ts'
import { formatAmount } from '../src/wallet/units.ts'
import type { Attempt, AttemptStatus, PaymentIdentity, ReceiptResult } from '../src/wallet/types.ts'
import { TERMINAL } from '../src/wallet/types.ts'

const IDENTITY: PaymentIdentity = {
  attemptId: 'a_1',
  sender: SENDER,
  recipient: RECIPIENT,
  asset: DEMO,
  amount: PAYMENT_CLEARS,
  reserve: RESERVE,
  schedule: SCHEDULE,
  asOf: AS_OF,
  horizonEnd: HORIZON_END,
}

const OK: ReceiptResult = { ok: true, slot: 1_000 }

/**
 * The REAL ledger evaluator, not a constant.
 *
 * An audit replaced `reading.amount` with a huge number and all 26 state tests
 * still passed, because every approve test injected `() => true`. A constant
 * evaluator tests that approve calls a function, which is not the property.
 */
function reallyAffordable(opening: bigint, identity: PaymentIdentity): boolean {
  return canSign(
    verdictFor(
      opening,
      identity.schedule,
      identity.reserve,
      identity.asOf,
      identity.horizonEnd,
      identity.amount,
      identity.asOf,
      (b) => formatAmount(b, identity.asset.decimals, identity.asset.symbol),
    ),
  )
}

function memoryStore(): Store & { value: string | null } {
  const s = {
    value: null as string | null,
    read: () => s.value,
    write: (v: string) => {
      s.value = v
    },
    clear: () => {
      s.value = null
    },
  }
  return s
}

function snapshot(over: Partial<Snapshot> = {}): Snapshot {
  return {
    account: SENDER,
    mint: DEMO.mint,
    network: DEMO.network,
    commitment: 'confirmed',
    amount: 10_000n,
    slot: 1_000,
    ...over,
  }
}

/** begin → approve → persistBeforeBroadcast, the only route to a broadcast. */
function submitted(store: Store): { token: AttemptToken; m: ReturnType<typeof createMachine> } {
  const m = createMachine(store)
  const begun = m.begin(IDENTITY)
  if (!begun.ok) throw new Error('begin failed')
  const approved = m.approve(begun.token, snapshot(), 0, reallyAffordable)
  assert.equal(approved.ok, true)
  assert.equal(m.persistBeforeBroadcast(begun.token, SIGNATURE, 100).ok, true)
  return { token: begun.token, m }
}

function tokenOf(m: ReturnType<typeof createMachine>, identity = IDENTITY): AttemptToken {
  const r = m.begin(identity)
  if (!r.ok) throw new Error('begin failed')
  return r.token
}

// --------------------------------------------------------------- persistence

test('serializing an attempt does not throw on any bigint field', () => {
  const attempt: Attempt = {
    identity: IDENTITY,
    signature: SIGNATURE,
    lastValidBlockHeight: 42,
    status: 'submitted',
  }
  assert.doesNotThrow(() => serializeAttempt(attempt))
})

test('an attempt round-trips to deep equality', () => {
  const attempt: Attempt = {
    identity: IDENTITY,
    signature: SIGNATURE,
    lastValidBlockHeight: 42,
    status: 'submitted',
  }
  const back = deserializeAttempt(serializeAttempt(attempt))
  assert.deepEqual(back, attempt)
  assert.equal(back.identity.reserve, RESERVE)
  for (const e of back.identity.schedule) assert.equal(typeof e.amount, 'bigint')
})

// Fails if deserialize uses toBase for schedule entries: it rejects a leading '-'.
test('negative schedule entries survive the round trip', () => {
  const attempt: Attempt = {
    identity: IDENTITY,
    signature: null,
    lastValidBlockHeight: null,
    status: 'reviewing',
  }
  const back = deserializeAttempt(serializeAttempt(attempt))
  const outflows = back.identity.schedule.filter((e) => e.amount < 0n)
  assert.equal(outflows.length, 2)
  assert.equal(outflows[0].amount, -2_400n)
})

// `readonly` is a compile-time claim about one reference and does nothing about
// the object the caller still holds.
// Fails if begin() stores the caller's object instead of copying it.
test('the frozen identity cannot be changed through the caller s own object', () => {
  const mutable = {
    ...IDENTITY,
    schedule: SCHEDULE.map((e) => ({ ...e })),
    asset: { ...DEMO },
  }
  const m = createMachine(memoryStore())
  const begun = m.begin(mutable as PaymentIdentity)
  assert.equal(begun.ok, true)
  // The caller mutates what it still has a reference to.
  ;(mutable as { amount: bigint }).amount = 999_999n
  ;(mutable.asset as { mint: string }).mint = 'EvilMint'
  ;(mutable.schedule[0] as { amount: bigint }).amount = -1n
  const held = m.current() as Attempt
  assert.equal(held.identity.amount, PAYMENT_CLEARS)
  assert.equal(held.identity.asset.mint, DEMO.mint)
  assert.equal(held.identity.schedule[0].amount, -2_400n)
})

// -------------------------------------------------------------------- guard

test('a second attempt while one is in flight is refused', () => {
  const m = createMachine(memoryStore())
  tokenOf(m)
  const second = m.begin(IDENTITY)
  assert.equal(second.ok, false)
  if (second.ok) throw new Error('unreachable')
  assert.equal(second.reason, 'already_in_flight')
})

// Two clicks arriving back to back, nothing awaited between them.
test('three immediate clicks produce one attempt', () => {
  const m = createMachine(memoryStore())
  const results = [m.begin(IDENTITY), m.begin(IDENTITY), m.begin(IDENTITY)]
  assert.equal(results.filter((r) => r.ok).length, 1)
})

test('a new attempt is allowed once the previous one is terminal', () => {
  const { token, m } = submitted(memoryStore())
  m.resolve(token, 'failed', 101)
  assert.equal(m.begin(IDENTITY).ok, true)
})

// Every call carries the token it is acting on, so a callback belonging to an
// abandoned attempt cannot resolve the current one. An audit reproduced exactly
// this: verify A, start B, reconcile A's result, and B became confirmed.
// Fails if any entry point stops checking the generation.
test('a callback from a superseded attempt cannot resolve the current one', () => {
  const store = memoryStore()
  const { token: first, m } = submitted(store)
  m.resolve(first, 'rejected', 50)

  const second = tokenOf(m, { ...IDENTITY, attemptId: 'a_2', recipient: 'SomeoneElse' })
  // The first attempt's callback arrives late.
  assert.equal(m.reconcile(first, OK, snapshot()).ok, false)
  assert.equal(
    (m.reconcile(first, OK, snapshot()) as { reason: string }).reason,
    'stale_attempt',
  )
  assert.equal((m.resolve(first, 'confirmed', 60) as { status: unknown }).status, null)
  assert.notEqual(m.current()?.status, 'confirmed')
  assert.equal(m.current()?.identity.recipient, 'SomeoneElse')
  assert.equal(
    (m.persistBeforeBroadcast(first, 'OTHER_SIG', 1) as { reason: string }).reason,
    'stale_attempt',
  )
  assert.equal(second !== first, true)
})

// ---------------------------------------------------------- fresh-balance gate

// The gate must be a transition that has to be passed, not a function that may
// be called. An audit added this precondition and 14 tests failed, because the
// suite had been written around the hole.
// Fails if persistBeforeBroadcast stops requiring awaiting_approval.
test('a broadcast is unreachable without an approval', () => {
  const m = createMachine(memoryStore())
  const token = tokenOf(m)
  const out = m.persistBeforeBroadcast(token, SIGNATURE, 100)
  assert.equal(out.ok, false)
  if (out.ok) throw new Error('unreachable')
  assert.equal(out.reason, 'not_approved')
  assert.equal(m.current()?.signature, null)
})

// Uses the real ledger, so the assertion is about affordability and not about
// whether a callback was invoked.
test('approval is refused when the real balance no longer affords it', () => {
  const m = createMachine(memoryStore())
  const token = tokenOf(m)
  const out = m.approve(token, snapshot({ amount: 1_000n }), 0, reallyAffordable)
  assert.equal(out.ok, false)
  if (out.ok) throw new Error('unreachable')
  assert.equal(out.reason, 'no_longer_affordable')
  assert.equal(m.current()?.status, 'reviewing')
})

test('approval proceeds when the real balance still affords it', () => {
  const m = createMachine(memoryStore())
  const token = tokenOf(m)
  assert.equal(m.approve(token, snapshot(), 0, reallyAffordable).ok, true)
  assert.equal(m.current()?.status, 'awaiting_approval')
})

// The boundary: the balance that makes the outlook land exactly on the reserve.
test('approval tracks the real affordability boundary', () => {
  const m1 = createMachine(memoryStore())
  assert.equal(m1.approve(tokenOf(m1), snapshot({ amount: 9_700n }), 0, reallyAffordable).ok, true)
  const m2 = createMachine(memoryStore())
  assert.equal(m2.approve(tokenOf(m2), snapshot({ amount: 9_600n }), 0, reallyAffordable).ok, false)
})

test('a stale balance reading is refused', () => {
  const m = createMachine(memoryStore())
  const out = m.approve(tokenOf(m), snapshot({ slot: 5 }), 900, reallyAffordable)
  assert.equal((out as { reason: string }).reason, 'stale_reading')
})

test('a reading for a different account is refused', () => {
  const m = createMachine(memoryStore())
  const out = m.approve(tokenOf(m), snapshot({ account: 'SomeoneElse' }), 0, reallyAffordable)
  assert.equal((out as { reason: string }).reason, 'stale_reading')
})

// Core review finding 3: account, mint and slot cannot establish which chain a
// reading came from, nor how settled it is.
test('a reading from the wrong network is refused', () => {
  const m = createMachine(memoryStore())
  const out = m.approve(tokenOf(m), snapshot({ network: 'mainnet-beta' }), 0, reallyAffordable)
  assert.equal((out as { reason: string }).reason, 'wrong_network')
})

test('a reading that is only processed is too weak to gate a signature', () => {
  const m = createMachine(memoryStore())
  const out = m.approve(tokenOf(m), snapshot({ commitment: 'processed' }), 0, reallyAffordable)
  assert.equal((out as { reason: string }).reason, 'too_weak_commitment')
})

test('approving twice does not re-open an approved attempt', () => {
  const m = createMachine(memoryStore())
  const token = tokenOf(m)
  assert.equal(m.approve(token, snapshot(), 0, reallyAffordable).ok, true)
  const again = m.approve(token, snapshot(), 0, reallyAffordable)
  assert.equal((again as { reason: string }).reason, 'not_reviewing')
})

// ------------------------------------------------------------ reload recovery

test('the signature is persisted before broadcast', () => {
  const store = memoryStore()
  submitted(store)
  assert.notEqual(store.value, null)
  assert.equal(deserializeAttempt(store.value as string).signature, SIGNATURE)
})

// Overwriting a signature loses the first one from memory AND disk — the exact
// loss the persisted attempt exists to prevent, one level up.
// Fails if the already_signed precondition is removed.
test('a second broadcast never replaces the first signature', () => {
  const store = memoryStore()
  const { token, m } = submitted(store)
  const out = m.persistBeforeBroadcast(token, 'SIG_TWO', 101)
  assert.equal(out.ok, false)
  if (out.ok) throw new Error('unreachable')
  assert.equal(out.reason, 'already_signed')
  assert.equal(m.current()?.signature, SIGNATURE)
  assert.equal(deserializeAttempt(store.value as string).signature, SIGNATURE)
})

test('a lost submission response then a reload restores the attempt', () => {
  const store = memoryStore()
  submitted(store)
  const second = createMachine(store)
  const restored = second.restore()
  assert.equal(restored.attempt?.signature, SIGNATURE)
  assert.equal(restored.attempt?.status, 'submitted')
  assert.notEqual(restored.token, null)
})

test('a restored unresolved attempt still blocks a new one', () => {
  const store = memoryStore()
  submitted(store)
  const second = createMachine(store)
  second.restore()
  assert.equal(second.begin(IDENTITY).ok, false)
})

// A reload racing a click would otherwise swap the machine's view to a different
// payment while the guard still reported "in flight".
// Fails if restore() stops checking for a live attempt.
test('restore never clobbers an attempt that is already live', () => {
  const store = memoryStore()
  submitted(store)
  const m2 = createMachine(store)
  const live = m2.begin({ ...IDENTITY, attemptId: 'a_live' })
  assert.equal(live.ok, true)
  const restored = m2.restore()
  assert.equal(restored.attempt?.identity.attemptId, 'a_live')
  assert.equal(m2.current()?.identity.attemptId, 'a_live')
  assert.equal(m2.current()?.signature, null)
})

test('nothing to restore is not an error', () => {
  assert.deepEqual(createMachine(memoryStore()).restore(), { attempt: null, token: null })
})

// ------------------------------------------------------------------- statuses

// Fails if resolve() returns 'expired' or 'failed' for a null reading.
test('an unavailable status stays unconfirmed, never expired', () => {
  const { token, m } = submitted(memoryStore())
  assert.equal(m.resolve(token, null, 50).status, 'unconfirmed')
})

test('a passed block height reports separately and does not become a status', () => {
  const { token, m } = submitted(memoryStore())
  const out = m.resolve(token, null, 101)
  assert.equal(out.status, 'unconfirmed')
  assert.equal(out.cannotNewlyLand, true)
  assert.equal(isTerminal(out.status as AttemptStatus), false)
})

test('unconfirmed is not terminal and the four resolved states are', () => {
  assert.equal(isTerminal('unconfirmed'), false)
  assert.equal(isTerminal('reviewing'), false)
  for (const s of ['confirmed', 'failed', 'rejected', 'expired'] as AttemptStatus[]) {
    assert.equal(isTerminal(s), true, `${s} should be terminal`)
  }
  assert.equal(TERMINAL.length, 4)
})

test('an unresolved attempt stays on disk and a terminal one is cleared', () => {
  const store = memoryStore()
  const { token, m } = submitted(store)
  m.resolve(token, null, 50)
  assert.notEqual(store.value, null)
  m.resolve(token, 'rejected', 50)
  assert.equal(store.value, null)
})

// --------------------------------------------------------------- reconcile

// An earlier revision confirmed an attempt that had never been signed, and then
// stored null as the reconciled marker, which disarmed idempotence entirely.
// Fails if the signature precondition is removed.
test('an unsigned attempt can never be reconciled', () => {
  const m = createMachine(memoryStore())
  const token = tokenOf(m)
  const out = m.reconcile(token, OK, snapshot())
  assert.equal(out.ok, false)
  if (out.ok) throw new Error('unreachable')
  assert.equal(out.reason, 'not_submitted')
  assert.notEqual(m.current()?.status, 'confirmed')

  // And twice, because the disarmed-idempotence variant returned ok both times.
  assert.equal(m.reconcile(token, OK, snapshot()).ok, false)
})

test('an approved but unsent attempt can never be reconciled', () => {
  const m = createMachine(memoryStore())
  const token = tokenOf(m)
  m.approve(token, snapshot(), 0, reallyAffordable)
  assert.equal((m.reconcile(token, OK, snapshot()) as { reason: string }).reason, 'not_submitted')
})

test('a verified receipt with a fresh snapshot installs the balance', () => {
  const { token, m } = submitted(memoryStore())
  const out = m.reconcile(token, OK, snapshot({ amount: 8_500n }))
  assert.deepEqual(out, { ok: true, balance: 8_500n })
  assert.equal(m.current()?.status, 'confirmed')
})

test('reconciling twice is a no-op the second time', () => {
  const { token, m } = submitted(memoryStore())
  assert.equal(m.reconcile(token, OK, snapshot()).ok, true)
  assert.equal((m.reconcile(token, OK, snapshot()) as { reason: string }).reason, 'already')
})

// Core review finding 6. If the signature were marked before the snapshot
// installed, this retry would return 'already' and the outlook would stay stale.
// Fails if `reconciled = signature` moves above the snapshot checks.
test('a failed reconcile leaves the attempt retryable', () => {
  const { token, m } = submitted(memoryStore())
  const stale = m.reconcile(token, OK, snapshot({ slot: 999 }))
  assert.equal((stale as { reason: string }).reason, 'stale_snapshot')
  assert.equal(m.reconcile(token, OK, snapshot({ slot: 1_000 })).ok, true)
})

test('a snapshot older than the receipt slot is refused', () => {
  const { token, m } = submitted(memoryStore())
  const out = m.reconcile(token, { ok: true, slot: 2_000 }, snapshot({ slot: 1_999 }))
  assert.equal((out as { reason: string }).reason, 'stale_snapshot')
})

test('a snapshot for the wrong account, mint, network or commitment is refused', () => {
  const { token, m } = submitted(memoryStore())
  assert.equal(
    (m.reconcile(token, OK, snapshot({ account: 'Other' })) as { reason: string }).reason,
    'snapshot_mismatch',
  )
  assert.equal(
    (m.reconcile(token, OK, snapshot({ mint: 'OtherMint' })) as { reason: string }).reason,
    'snapshot_mismatch',
  )
  assert.equal(
    (m.reconcile(token, OK, snapshot({ network: 'mainnet-beta' })) as { reason: string }).reason,
    'wrong_network',
  )
  assert.equal(
    (m.reconcile(token, OK, snapshot({ commitment: 'processed' })) as { reason: string }).reason,
    'too_weak_commitment',
  )
})

// Never report success because a signature was requested.
test('an unverified receipt never installs a balance', () => {
  const { token, m } = submitted(memoryStore())
  const out = m.reconcile(token, { ok: false, reason: 'transaction_failed' }, snapshot())
  assert.equal((out as { reason: string }).reason, 'not_confirmed')
  assert.notEqual(m.current()?.status, 'confirmed')
})

test('every reconcile rejection reason is distinct', () => {
  const { token, m } = submitted(memoryStore())
  const reasons = [
    (m.reconcile(token, { ok: false, reason: 'transaction_failed' }, snapshot()) as { reason: string }).reason,
    (m.reconcile(token, OK, snapshot({ account: 'Other' })) as { reason: string }).reason,
    (m.reconcile(token, OK, snapshot({ network: 'mainnet-beta' })) as { reason: string }).reason,
    (m.reconcile(token, OK, snapshot({ commitment: 'processed' })) as { reason: string }).reason,
    (m.reconcile(token, OK, snapshot({ slot: 1 })) as { reason: string }).reason,
  ]
  assert.equal(new Set(reasons).size, 5)
  assert.equal(m.reconcile(token, OK, snapshot()).ok, true)
  assert.equal((m.reconcile(token, OK, snapshot()) as { reason: string }).reason, 'already')
})

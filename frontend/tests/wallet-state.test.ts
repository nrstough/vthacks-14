import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  createMachine,
  deserializeAttempt,
  isTerminal,
  serializeAttempt,
} from '../src/wallet/state.ts'
import type { Snapshot, Store } from '../src/wallet/state.ts'
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
const yes = (): boolean => true
const no = (): boolean => false

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
  return { account: SENDER, mint: DEMO.mint, amount: 8_500n, slot: 1_000, ...over }
}

// --------------------------------------------------------------- persistence

// Three monetary fields, not one. A serializer that converts only `amount`
// still throws on `reserve` and on every schedule entry.
// Fails if any of the three conversions is dropped.
test('serializing an attempt does not throw on any bigint field', () => {
  const attempt: Attempt = {
    identity: IDENTITY,
    signature: SIGNATURE,
    lastValidBlockHeight: 42,
    status: 'submitted',
  }
  assert.doesNotThrow(() => serializeAttempt(attempt))
})

test('an attempt round-trips to deep equality, signs and all', () => {
  const attempt: Attempt = {
    identity: IDENTITY,
    signature: SIGNATURE,
    lastValidBlockHeight: 42,
    status: 'submitted',
  }
  const back = deserializeAttempt(serializeAttempt(attempt))
  assert.deepEqual(back, attempt)
  assert.equal(back.identity.reserve, RESERVE)
  assert.equal(typeof back.identity.amount, 'bigint')
  for (const e of back.identity.schedule) assert.equal(typeof e.amount, 'bigint')
})

// The schedule holds negative amounts, so restoring it needs the signed parser.
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

// -------------------------------------------------------------------- guard

test('a second attempt while one is in flight is refused', () => {
  const m = createMachine(memoryStore())
  assert.equal(m.begin(IDENTITY).ok, true)
  const second = m.begin(IDENTITY)
  assert.equal(second.ok, false)
  if (second.ok) throw new Error('unreachable')
  assert.equal(second.reason, 'already_in_flight')
})

// Two clicks arriving back to back, with nothing awaited between them. The guard
// has to be taken in the same synchronous turn as the check or this passes twice.
// Fails if begin() awaits anything before setting inFlight.
test('two immediate clicks produce one attempt', () => {
  const m = createMachine(memoryStore())
  const results = [m.begin(IDENTITY), m.begin(IDENTITY), m.begin(IDENTITY)]
  assert.equal(results.filter((r) => r.ok).length, 1)
})

test('a new attempt is allowed once the previous one is terminal', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  m.persistBeforeBroadcast(SIGNATURE, 100)
  m.resolve('failed', 101)
  assert.equal(m.begin(IDENTITY).ok, true)
})

// ---------------------------------------------------------- fresh-balance gate

// Freezing the identity does not keep it true. Spending from elsewhere between
// review and approval invalidates the verdict with every frozen field unchanged.
// Fails if approve() stops consulting the fresh reading.
test('approval is refused when the fresh balance no longer affords it', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  const out = m.approve(snapshot({ amount: 10n }), 0, no)
  assert.equal(out.ok, false)
  if (out.ok) throw new Error('unreachable')
  assert.equal(out.reason, 'no_longer_affordable')
  assert.equal(m.current()?.status, 'reviewing')
})

test('approval proceeds when the fresh balance still affords it', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  assert.equal(m.approve(snapshot(), 0, yes).ok, true)
  assert.equal(m.current()?.status, 'awaiting_approval')
})

// A reading from before what we already knew is not evidence of anything.
test('a stale balance reading is refused', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  const out = m.approve(snapshot({ slot: 5 }), 900, yes)
  assert.equal(out.ok, false)
  if (out.ok) throw new Error('unreachable')
  assert.equal(out.reason, 'stale_reading')
})

test('a reading for a different account is refused', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  const out = m.approve(snapshot({ account: 'SomeoneElse' }), 0, yes)
  assert.equal(out.ok, false)
  if (out.ok) throw new Error('unreachable')
  assert.equal(out.reason, 'stale_reading')
})

test('approving without a review in progress is refused', () => {
  const m = createMachine(memoryStore())
  const out = m.approve(snapshot(), 0, yes)
  assert.equal(out.ok, false)
  if (out.ok) throw new Error('unreachable')
  assert.equal(out.reason, 'not_reviewing')
})

// ------------------------------------------------------------ reload recovery

// The signature must be on disk before it goes to the network, or a lost
// response plus a reload loses the transfer and licenses a duplicate.
// Fails if persistBeforeBroadcast stops writing, or writes after broadcast.
test('the signature is persisted before broadcast', () => {
  const store = memoryStore()
  const m = createMachine(store)
  m.begin(IDENTITY)
  m.persistBeforeBroadcast(SIGNATURE, 100)
  assert.notEqual(store.value, null)
  assert.equal(deserializeAttempt(store.value as string).signature, SIGNATURE)
})

test('a lost submission response then a reload restores the attempt', () => {
  const store = memoryStore()
  const first = createMachine(store)
  first.begin(IDENTITY)
  first.persistBeforeBroadcast(SIGNATURE, 100)
  // The response never arrives and the page reloads: a brand new machine over
  // the same store.
  const second = createMachine(store)
  const restored = second.restore()
  assert.notEqual(restored, null)
  assert.equal(restored?.signature, SIGNATURE)
  assert.equal(restored?.status, 'submitted')
})

// The recovered attempt has to keep blocking, or the reload IS the duplicate.
test('a restored unresolved attempt still blocks a new one', () => {
  const store = memoryStore()
  const first = createMachine(store)
  first.begin(IDENTITY)
  first.persistBeforeBroadcast(SIGNATURE, 100)
  const second = createMachine(store)
  second.restore()
  assert.equal(second.begin(IDENTITY).ok, false)
})

test('nothing to restore is not an error', () => {
  assert.equal(createMachine(memoryStore()).restore(), null)
})

// ------------------------------------------------------------------- statuses

// Codex review finding 4: a null getSignatureStatuses can be a cache miss, so it
// is never proof a transfer did not land.
// Fails if resolve() returns 'expired' or 'failed' for a null reading.
test('an unavailable status stays unconfirmed, never expired', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  m.persistBeforeBroadcast(SIGNATURE, 100)
  assert.equal(m.resolve(null, 50).status, 'unconfirmed')
})

// Even past the last valid block height. That proves it cannot NEWLY land; it
// does not prove it never landed.
test('a passed block height reports separately and does not become a status', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  m.persistBeforeBroadcast(SIGNATURE, 100)
  const out = m.resolve(null, 101)
  assert.equal(out.status, 'unconfirmed')
  assert.equal(out.cannotNewlyLand, true)
  assert.ok(!isTerminal(out.status))
})

test('unconfirmed is not terminal and the four resolved states are', () => {
  assert.equal(isTerminal('unconfirmed'), false)
  assert.equal(isTerminal('reviewing'), false)
  for (const s of ['confirmed', 'failed', 'rejected', 'expired'] as AttemptStatus[]) {
    assert.equal(isTerminal(s), true, `${s} should be terminal`)
  }
  // Fails if a state is added to TERMINAL without being considered here.
  assert.equal(TERMINAL.length, 4)
})

test('an unresolved attempt stays on disk and a terminal one is cleared', () => {
  const store = memoryStore()
  const m = createMachine(store)
  m.begin(IDENTITY)
  m.persistBeforeBroadcast(SIGNATURE, 100)
  m.resolve(null, 50)
  assert.notEqual(store.value, null)
  m.resolve('rejected', 50)
  assert.equal(store.value, null)
})

// --------------------------------------------------------------- reconcile

test('a verified receipt with a fresh snapshot installs the balance', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  m.persistBeforeBroadcast(SIGNATURE, 100)
  const out = m.reconcile(OK, snapshot())
  assert.deepEqual(out, { ok: true, balance: 8_500n })
  assert.equal(m.current()?.status, 'confirmed')
})

test('reconciling twice is a no-op the second time', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  m.persistBeforeBroadcast(SIGNATURE, 100)
  assert.equal(m.reconcile(OK, snapshot()).ok, true)
  const again = m.reconcile(OK, snapshot())
  assert.equal(again.ok, false)
  if (again.ok) throw new Error('unreachable')
  assert.equal(again.reason, 'already')
})

// Codex review finding 6, and the reason the ordering inside reconcile matters.
// If the signature were marked before the snapshot installed, this retry would
// return 'already' and the outlook would stay stale for good.
// Fails if `reconciled = signature` moves above the snapshot checks.
test('a failed reconcile leaves the attempt retryable', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  m.persistBeforeBroadcast(SIGNATURE, 100)

  const stale = m.reconcile(OK, snapshot({ slot: 999 }))
  assert.equal(stale.ok, false)
  if (stale.ok) throw new Error('unreachable')
  assert.equal(stale.reason, 'stale_snapshot')

  // The retry must still work, and must not report 'already'.
  const retry = m.reconcile(OK, snapshot({ slot: 1_000 }))
  assert.equal(retry.ok, true)
})

// A successful refresh is not necessarily a refresh that includes the transfer.
test('a snapshot older than the receipt slot is refused', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  m.persistBeforeBroadcast(SIGNATURE, 100)
  const out = m.reconcile({ ok: true, slot: 2_000 }, snapshot({ slot: 1_999 }))
  assert.equal(out.ok, false)
  if (out.ok) throw new Error('unreachable')
  assert.equal(out.reason, 'stale_snapshot')
})

test('a snapshot for the wrong account or mint is refused', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  m.persistBeforeBroadcast(SIGNATURE, 100)
  assert.equal(
    (m.reconcile(OK, snapshot({ account: 'Other' })) as { reason: string }).reason,
    'snapshot_mismatch',
  )
  assert.equal(
    (m.reconcile(OK, snapshot({ mint: 'OtherMint' })) as { reason: string }).reason,
    'snapshot_mismatch',
  )
})

// Never report success because a signature was requested.
test('an unverified receipt never installs a balance', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  m.persistBeforeBroadcast(SIGNATURE, 100)
  const out = m.reconcile({ ok: false, reason: 'transaction_failed' }, snapshot())
  assert.equal(out.ok, false)
  if (out.ok) throw new Error('unreachable')
  assert.equal(out.reason, 'not_confirmed')
  assert.notEqual(m.current()?.status, 'confirmed')
})

test('every reconcile rejection reason is distinct', () => {
  const m = createMachine(memoryStore())
  m.begin(IDENTITY)
  m.persistBeforeBroadcast(SIGNATURE, 100)
  const reasons = [
    (m.reconcile({ ok: false, reason: 'transaction_failed' }, snapshot()) as { reason: string }).reason,
    (m.reconcile(OK, snapshot({ account: 'Other' })) as { reason: string }).reason,
    (m.reconcile(OK, snapshot({ slot: 1 })) as { reason: string }).reason,
  ]
  assert.equal(new Set(reasons).size, 3)
  assert.equal(m.reconcile(OK, snapshot()).ok, true)
  assert.equal((m.reconcile(OK, snapshot()) as { reason: string }).reason, 'already')
})

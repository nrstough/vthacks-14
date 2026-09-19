import { test } from 'node:test'
import assert from 'node:assert/strict'
import { verifyReceipt } from '../src/wallet/receipt.ts'
import {
  AS_OF,
  DEMO,
  HORIZON_END,
  OPENING,
  PAYMENT_CLEARS,
  RECIPIENT,
  RESERVE,
  SCHEDULE,
  SENDER,
  SIGNATURE,
  receipt,
  receiptNewRecipient,
} from '../src/wallet/fixtures.ts'
import type { PaymentIdentity, Receipt, ReceiptResult } from '../src/wallet/types.ts'

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

function check(r: Receipt | null, genesis = DEMO.genesisHash): ReceiptResult {
  return verifyReceipt(r, IDENTITY, SIGNATURE, genesis)
}

function rejected(r: Receipt | null, genesis = DEMO.genesisHash): string {
  const out = check(r, genesis)
  assert.equal(out.ok, false)
  if (out.ok) throw new Error('unreachable')
  return out.reason
}

test('a matching transfer verifies and reports its slot', () => {
  const out = check(receipt())
  assert.deepEqual(out, { ok: true, slot: 1_000 })
})

// Codex review finding 2: a recipient with no associated token account has no
// pre-balance entry at all. Absent means zero here, and must be ACCEPTED.
// Fails if balanceOf's null is treated as a rejection, or if the code does
// arithmetic on the missing entry — which strictNullChecks being off will not
// warn about.
test('a recipient who had no token account before still verifies', () => {
  const out = check(receiptNewRecipient())
  assert.equal(out.ok, true)
})

// The float the RPC sends beside the exact string. Every uiAmount in the fixtures
// is already wrong on purpose; this makes it wronger and asserts nothing moves.
// Fails the moment any code path reads uiAmount instead of amount.
test('the float uiAmount field is never read', () => {
  const poisoned: Receipt = {
    ...receipt(),
    preTokenBalances: receipt().preTokenBalances.map((r) => ({ ...r, uiAmount: -1 })),
    postTokenBalances: receipt().postTokenBalances.map((r) => ({ ...r, uiAmount: 1e30 })),
  }
  assert.deepEqual(check(poisoned), check(receipt()))
  assert.equal(check(poisoned).ok, true)
})

test('no receipt at all is unresolved, not failed', () => {
  assert.equal(rejected(null), 'metadata_unavailable')
})

test('a receipt from the wrong chain is refused', () => {
  assert.equal(rejected(receipt(), 'MainnetGenesisHashXXXXXXXXXXXXXXXXXXXXXXXXX'), 'network_mismatch')
})

test('a receipt for a different signature is refused', () => {
  assert.equal(rejected(receipt({ signature: 'other' })), 'signature_mismatch')
})

test('a transaction that errored is refused', () => {
  assert.equal(rejected(receipt({ err: { InstructionError: [0, 'Custom'] } })), 'transaction_failed')
})

test('a receipt that never touches the mint is refused', () => {
  const other = receipt()
  assert.equal(
    rejected({
      ...other,
      preTokenBalances: other.preTokenBalances.map((r) => ({ ...r, mint: 'OtherMint' })),
      postTokenBalances: other.postTokenBalances.map((r) => ({ ...r, mint: 'OtherMint' })),
    }),
    'mint_absent',
  )
})

test('a sender missing from the post balances is refused', () => {
  const r = receipt()
  assert.equal(
    rejected({ ...r, postTokenBalances: r.postTokenBalances.filter((b) => b.account !== SENDER) }),
    'sender_absent',
  )
})

test('a recipient missing from the post balances is refused', () => {
  const r = receipt()
  assert.equal(
    rejected({ ...r, postTokenBalances: r.postTokenBalances.filter((b) => b.account !== RECIPIENT) }),
    'recipient_absent',
  )
})

// Each delta is checked independently against an otherwise-valid receipt, so a
// verifier that short-circuits early cannot pass both on one branch.
test('a sender debited the wrong amount is refused', () => {
  const r = receipt()
  assert.equal(
    rejected({
      ...r,
      postTokenBalances: r.postTokenBalances.map((b) =>
        b.account === SENDER ? { ...b, amount: '9000' } : b,
      ),
    }),
    'sender_delta_wrong',
  )
})

test('a recipient credited the wrong amount is refused', () => {
  const r = receipt()
  assert.equal(
    rejected({
      ...r,
      postTokenBalances: r.postTokenBalances.map((b) =>
        b.account === RECIPIENT ? { ...b, amount: '1400' } : b,
      ),
    }),
    'recipient_delta_wrong',
  )
})

test('an unrelated third token balance in the same transaction is ignored', () => {
  const r = receipt()
  const noise = { account: 'SomeoneElse', mint: DEMO.mint, amount: '4242' }
  assert.equal(
    check({
      ...r,
      preTokenBalances: [...r.preTokenBalances, noise],
      postTokenBalances: [...r.postTokenBalances, noise],
    }).ok,
    true,
  )
})

// If two rejections shared a code the tests above could pass while checking
// nothing distinct. This pins that every branch is reachable and separate.
test('every rejection reason is distinct', () => {
  const r = receipt()
  const reasons = [
    rejected(null),
    rejected(r, 'WrongChain'),
    rejected(receipt({ signature: 'other' })),
    rejected(receipt({ err: 'boom' })),
    rejected({ ...r, postTokenBalances: r.postTokenBalances.filter((b) => b.account !== SENDER) }),
    rejected({ ...r, postTokenBalances: r.postTokenBalances.filter((b) => b.account !== RECIPIENT) }),
  ]
  assert.equal(new Set(reasons).size, reasons.length)
})

test('a malformed amount string is refused loudly rather than coerced', () => {
  const r = receipt()
  assert.throws(
    () =>
      check({
        ...r,
        postTokenBalances: r.postTokenBalances.map((b) =>
          b.account === SENDER ? { ...b, amount: '85.00' } : b,
        ),
      }),
    TypeError,
  )
})

test('verification is deterministic', () => {
  assert.deepEqual(check(receipt()), check(receipt()))
})

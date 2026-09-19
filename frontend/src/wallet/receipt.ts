// Did this transfer actually happen, exactly as reviewed?
//
// Nothing here trusts that a signature was requested, or that a submission
// returned. Only a receipt whose token-balance movement matches the frozen
// identity counts, and every way it can fail to match has its own reason so a
// test cannot pass five cases on one shared branch.

import type { PaymentIdentity, Receipt, ReceiptResult, TokenBalance } from './types.ts'
import { toBase } from './units.ts'

/**
 * Find one account's balance for one mint.
 *
 * Absent is a real answer, not an error: a recipient who had no associated token
 * account before the transfer has no pre-balance entry at all. Returning null
 * rather than reaching into `undefined` matters more than usual here, because
 * strictNullChecks is off in this project and the compiler types `.find()` as
 * always-present. Nothing but this check and its test will catch it.
 */
function balanceOf(rows: readonly TokenBalance[], account: string, mint: string): bigint | null {
  for (const row of rows) {
    if (row.account === account && row.mint === mint) return toBase(row.amount)
  }
  return null
}

/**
 * Verify a receipt against what was reviewed.
 *
 * `network` is passed in, not read from the receipt: getTransaction returns no
 * genesis hash, so a receipt cannot establish which chain it came from. The
 * network is captured at review time from getGenesisHash() and compared here,
 * and this function never claims to have derived it.
 */
export function verifyReceipt(
  receipt: Receipt | null,
  identity: PaymentIdentity,
  expectedSignature: string,
  observedGenesisHash: string,
): ReceiptResult {
  // No receipt yet is not a rejection. A transfer that has not been looked up,
  // or whose lookup came back empty, is unresolved — saying "failed" here is the
  // claim the evidence does not support.
  if (receipt === null) return { ok: false, reason: 'metadata_unavailable' }

  if (observedGenesisHash !== identity.asset.genesisHash) {
    return { ok: false, reason: 'network_mismatch' }
  }
  if (receipt.signature !== expectedSignature) {
    return { ok: false, reason: 'signature_mismatch' }
  }
  if (receipt.err !== null) return { ok: false, reason: 'transaction_failed' }

  const mint = identity.asset.mint
  const touchesMint =
    receipt.preTokenBalances.some((r) => r.mint === mint) ||
    receipt.postTokenBalances.some((r) => r.mint === mint)
  if (!touchesMint) return { ok: false, reason: 'mint_absent' }

  // The sender must have held the token before and after: an absent post-balance
  // for the sender is not a transfer we can read.
  const senderPre = balanceOf(receipt.preTokenBalances, identity.sender, mint)
  const senderPost = balanceOf(receipt.postTokenBalances, identity.sender, mint)
  if (senderPre === null || senderPost === null) return { ok: false, reason: 'sender_absent' }

  // The recipient may legitimately have had no account beforehand, in which case
  // absent means zero. Absent AFTER the transfer means it did not arrive.
  const recipientPreRaw = balanceOf(receipt.preTokenBalances, identity.recipient, mint)
  const recipientPre = recipientPreRaw === null ? 0n : recipientPreRaw
  const recipientPost = balanceOf(receipt.postTokenBalances, identity.recipient, mint)
  if (recipientPost === null) return { ok: false, reason: 'recipient_absent' }

  if (senderPost - senderPre !== -identity.amount) {
    return { ok: false, reason: 'sender_delta_wrong' }
  }
  if (recipientPost - recipientPre !== identity.amount) {
    return { ok: false, reason: 'recipient_delta_wrong' }
  }

  return { ok: true, slot: receipt.slot }
}

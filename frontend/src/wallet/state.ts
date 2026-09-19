// The payment attempt: what was reviewed, what was signed, and what is known.
//
// Everything irreversible is governed here, so the rules are stricter than
// elsewhere and each one exists because of a specific way this goes wrong:
//
//   - the identity is frozen at review, so signing cannot approve something the
//     review never showed;
//   - the duplicate guard is taken synchronously, before any await including
//     wallet approval, because two clicks are two clicks;
//   - the attempt is persisted before broadcast, because a submission can reach
//     the network while its response is lost;
//   - affordability is re-established against fresh balance evidence at signing,
//     because freezing what was reviewed does not keep it true;
//   - reconciliation installs the balance and marks the signature together or
//     does neither, because a half-done reconcile makes the retry a no-op while
//     the outlook stays stale.
//
// The clock, the store and the RPC are injected. That is not ceremony: the
// deterministic failure tests this lane cannot write yet (ambiguous submission,
// delayed receipts, account changes) need those seams to exist now, or adding
// them later means redesigning this file.

import type {
  Attempt,
  AttemptStatus,
  Entry,
  PaymentIdentity,
  ReceiptResult,
} from './types.ts'
import { TERMINAL } from './types.ts'
import { toBase, toSigned } from './units.ts'

export type Store = {
  read(): string | null
  write(value: string): void
  clear(): void
}

/** A balance reading, with the slot it was taken at. */
export type Snapshot = {
  readonly account: string
  readonly mint: string
  readonly amount: bigint
  readonly slot: number
}

export type AcquireResult =
  | { readonly ok: true; readonly attempt: Attempt }
  | { readonly ok: false; readonly reason: 'already_in_flight' }

export type ApproveResult =
  | { readonly ok: true }
  | { readonly ok: false; readonly reason: 'no_longer_affordable' | 'stale_reading' | 'not_reviewing' }

export type ReconcileResult =
  | { readonly ok: true; readonly balance: bigint }
  | {
      readonly ok: false
      readonly reason: 'not_confirmed' | 'stale_snapshot' | 'snapshot_mismatch' | 'already'
    }

export function isTerminal(status: AttemptStatus): boolean {
  return TERMINAL.includes(status)
}

// ---------------------------------------------------------------- persistence

/**
 * JSON.stringify throws a TypeError on a bigint, and it would throw inside a
 * click handler, where no React error boundary catches it — the user sees a Sign
 * button that does nothing. So every monetary field converts explicitly, and
 * there are three of them: the amount, the reserve, and every schedule entry.
 * Converting only the first still throws.
 */
export function serializeAttempt(attempt: Attempt): string {
  const i = attempt.identity
  return JSON.stringify({
    identity: {
      ...i,
      amount: i.amount.toString(),
      reserve: i.reserve.toString(),
      schedule: i.schedule.map((e) => ({ ...e, amount: e.amount.toString() })),
    },
    signature: attempt.signature,
    lastValidBlockHeight: attempt.lastValidBlockHeight,
    status: attempt.status,
  })
}

export function deserializeAttempt(text: string): Attempt {
  const raw = JSON.parse(text)
  const i = raw.identity
  const identity: PaymentIdentity = {
    ...i,
    // toBase, not toSigned: a payment amount and a reserve are magnitudes.
    amount: toBase(i.amount),
    reserve: toBase(i.reserve),
    // Schedule entries ARE signed — a negative one is money leaving — so they
    // need the signed parser. toBase would reject every obligation in the list.
    schedule: i.schedule.map((e: { amount: unknown }) => ({
      ...e,
      amount: toSigned(e.amount),
    })) as Entry[],
  }
  return {
    identity,
    signature: raw.signature,
    lastValidBlockHeight: raw.lastValidBlockHeight,
    status: raw.status,
  }
}

// ------------------------------------------------------------------- machine

export function createMachine(store: Store) {
  // The guard. Held in a closure and taken synchronously, so there is no await
  // between the check and the set for a second click to slip through.
  let inFlight: Attempt | null = null

  function current(): Attempt | null {
    return inFlight
  }

  /**
   * Freeze the review and take the guard, in that order, with nothing async
   * between them. A caller that awaits anything before this has already lost.
   */
  function begin(identity: PaymentIdentity): AcquireResult {
    if (inFlight !== null && !isTerminal(inFlight.status)) {
      return { ok: false, reason: 'already_in_flight' }
    }
    inFlight = { identity, signature: null, lastValidBlockHeight: null, status: 'reviewing' }
    return { ok: true, attempt: inFlight }
  }

  /**
   * Re-establish affordability against a fresh reading before approval.
   *
   * Freezing the identity stops the app changing what was reviewed; it does not
   * stop the world changing. Spending from another wallet app between review and
   * approval invalidates the verdict while every frozen field is untouched — and
   * this app explicitly cannot prevent that spending, only refuse to add to it.
   *
   * `evaluate` is the ledger walk, injected so this stays synchronous and pure.
   */
  function approve(
    reading: Snapshot,
    minimumSlot: number,
    evaluate: (opening: bigint, identity: PaymentIdentity) => boolean,
  ): ApproveResult {
    if (inFlight === null || inFlight.status !== 'reviewing') {
      return { ok: false, reason: 'not_reviewing' }
    }
    // A reading from before the last thing we knew about is not evidence.
    if (reading.slot < minimumSlot) return { ok: false, reason: 'stale_reading' }
    if (reading.account !== inFlight.identity.sender || reading.mint !== inFlight.identity.asset.mint) {
      return { ok: false, reason: 'stale_reading' }
    }
    if (!evaluate(reading.amount, inFlight.identity)) {
      return { ok: false, reason: 'no_longer_affordable' }
    }
    inFlight = { ...inFlight, status: 'awaiting_approval' }
    return { ok: true }
  }

  /**
   * Write the signature down BEFORE it is broadcast.
   *
   * If the signature only ever exists in memory, a lost submission response plus
   * a reload loses the transfer entirely: the app shows nothing pending, the user
   * sends again, and the first one may already have landed.
   */
  function persistBeforeBroadcast(signature: string, lastValidBlockHeight: number): void {
    if (inFlight === null) throw new Error('no attempt to persist')
    inFlight = { ...inFlight, signature, lastValidBlockHeight, status: 'submitted' }
    store.write(serializeAttempt(inFlight))
  }

  /** Reload recovery. A restored unresolved attempt keeps blocking new ones. */
  function restore(): Attempt | null {
    const text = store.read()
    if (text === null) return null
    const attempt = deserializeAttempt(text)
    if (!isTerminal(attempt.status)) inFlight = attempt
    return attempt
  }

  /**
   * Fold a status reading into the attempt.
   *
   * `null` means the RPC had nothing to say, which is a cache miss as often as it
   * is an absence — historical search is off by default. It is never evidence
   * that a transfer did not land, so it produces `unconfirmed`, never `expired`.
   *
   * Passing lastValidBlockHeight proves a transaction cannot NEWLY land. It does
   * not prove it never landed, so expiry only resolves an attempt we have already
   * failed to find, and even then the honest state stays unconfirmed until a
   * lookup says otherwise.
   */
  function resolve(
    observed: 'confirmed' | 'failed' | 'rejected' | null,
    blockHeight: number,
  ): { readonly status: AttemptStatus; readonly cannotNewlyLand: boolean } {
    if (inFlight === null) throw new Error('no attempt to resolve')
    const status: AttemptStatus = observed === null ? 'unconfirmed' : observed

    // Reported separately from the status on purpose. Passing the last valid
    // block height is a real fact and worth showing, but it is a fact about
    // what can happen NEXT, not about what already happened — so it informs the
    // wording and never becomes `expired` on its own. The status stays
    // unconfirmed until a lookup actually resolves it.
    const cannotNewlyLand =
      inFlight.lastValidBlockHeight !== null && blockHeight > inFlight.lastValidBlockHeight

    inFlight = { ...inFlight, status }
    if (isTerminal(status)) store.clear()
    else store.write(serializeAttempt(inFlight))
    return { status, cannotNewlyLand }
  }

  let reconciled: string | null = null

  /**
   * Install the post-transfer balance and mark the signature, together.
   *
   * The ordering is the whole point. Marking first and installing second means a
   * failed refresh leaves the signature marked, so the retry returns `already`
   * and the outlook stays stale for good. Nothing is marked unless the snapshot
   * is actually installed.
   *
   * A successful refresh is also not necessarily a refresh that INCLUDES the
   * transfer, so the snapshot must be at least as recent as the receipt's slot.
   */
  function reconcile(result: ReceiptResult, snapshot: Snapshot): ReconcileResult {
    if (inFlight === null) throw new Error('no attempt to reconcile')
    const signature = inFlight.signature
    if (signature !== null && reconciled === signature) {
      return { ok: false, reason: 'already' }
    }
    if (!result.ok) return { ok: false, reason: 'not_confirmed' }
    if (
      snapshot.account !== inFlight.identity.sender ||
      snapshot.mint !== inFlight.identity.asset.mint
    ) {
      return { ok: false, reason: 'snapshot_mismatch' }
    }
    if (snapshot.slot < result.slot) return { ok: false, reason: 'stale_snapshot' }

    reconciled = signature
    inFlight = { ...inFlight, status: 'confirmed' }
    store.clear()
    return { ok: true, balance: snapshot.amount }
  }

  function reset(): void {
    inFlight = null
    reconciled = null
    store.clear()
  }

  return {
    current,
    begin,
    approve,
    persistBeforeBroadcast,
    restore,
    resolve,

    reconcile,
    reset,
  }
}

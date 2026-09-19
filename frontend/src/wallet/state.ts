// The payment attempt: what was reviewed, what was signed, and what is known.
//
// Everything irreversible is governed here, so the rules are stricter than
// elsewhere and each one exists because of a specific way this goes wrong:
//
//   - the identity is COPIED and frozen at review, so neither the caller nor a
//     later render can change what was approved;
//   - the duplicate guard is taken synchronously, before any await including
//     wallet approval, because two clicks are two clicks;
//   - every call carries the token it is acting on, so a callback belonging to
//     an abandoned attempt cannot resolve the current one;
//   - the transitions are enforced, not merely available: a broadcast is only
//     reachable through an approval that saw fresh balance evidence;
//   - a signature is written down before broadcast, and never overwritten;
//   - reconciliation installs the balance and marks the signature together or
//     does neither.
//
// An earlier revision of this file had `approve` as a function a caller could
// simply skip, and `reconcile` would confirm an attempt that had never been
// signed. Two independent audits reproduced both. The preconditions below are
// the fix, and the tests now go through the real transitions rather than around
// them.
//
// The store and the evaluator are injected. That is not ceremony: the
// deterministic failure tests this lane cannot write yet (ambiguous submission,
// delayed receipts, account changes) need those seams to exist now.

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

/**
 * A balance reading, with everything needed to know it is the right one.
 *
 * `network` and `commitment` are not decoration: matching account, mint and slot
 * cannot establish which chain a reading came from or how settled it is, and a
 * reading at `processed` can be rolled back. Core review finding 3.
 */
export type Snapshot = {
  readonly account: string
  readonly mint: string
  readonly network: string
  readonly commitment: 'processed' | 'confirmed' | 'finalized'
  readonly amount: bigint
  readonly slot: number
}

/** Returned by begin(); every later call must present it. */
export type AttemptToken = number

export type BeginResult =
  | { readonly ok: true; readonly attempt: Attempt; readonly token: AttemptToken }
  | { readonly ok: false; readonly reason: 'already_in_flight' }

export type ApproveResult =
  | { readonly ok: true }
  | {
      readonly ok: false
      readonly reason:
        | 'no_longer_affordable'
        | 'stale_reading'
        | 'wrong_network'
        | 'too_weak_commitment'
        | 'not_reviewing'
        | 'stale_attempt'
    }

export type BroadcastResult =
  | { readonly ok: true }
  | { readonly ok: false; readonly reason: 'not_approved' | 'already_signed' | 'stale_attempt' }

export type ReconcileResult =
  | { readonly ok: true; readonly balance: bigint }
  | {
      readonly ok: false
      readonly reason:
        | 'not_confirmed'
        | 'stale_snapshot'
        | 'snapshot_mismatch'
        | 'wrong_network'
        | 'too_weak_commitment'
        | 'not_submitted'
        | 'already'
        | 'stale_attempt'
    }

export function isTerminal(status: AttemptStatus): boolean {
  return TERMINAL.includes(status)
}

/** A reading must be at least this settled before it can gate a signature. */
function settledEnough(commitment: Snapshot['commitment']): boolean {
  return commitment === 'confirmed' || commitment === 'finalized'
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

/**
 * Copy the identity away from the caller, then freeze it.
 *
 * `readonly` is a compile-time claim about one reference; it does nothing about
 * the object the caller still holds. Without this copy, mutating the argument
 * after review silently changes what gets signed.
 */
function freezeIdentity(identity: PaymentIdentity): PaymentIdentity {
  const schedule = identity.schedule.map((e) => Object.freeze({ ...e }))
  return Object.freeze({
    ...identity,
    asset: Object.freeze({ ...identity.asset }),
    schedule: Object.freeze(schedule),
  }) as PaymentIdentity
}

// ------------------------------------------------------------------- machine

export function createMachine(store: Store) {
  // The guard. Held in a closure and taken synchronously, so there is no await
  // between the check and the set for a second click to slip through.
  let inFlight: Attempt | null = null
  // Monotonic, and required by every call. This is the App.tsx:62-97 pattern:
  // capture the generation, compare it inside the callback, refuse if it moved.
  let generation = 0
  let reconciled: string | null = null

  function current(): Attempt | null {
    return inFlight
  }

  function live(token: AttemptToken): boolean {
    return token === generation && inFlight !== null
  }

  function begin(identity: PaymentIdentity): BeginResult {
    if (inFlight !== null && !isTerminal(inFlight.status)) {
      return { ok: false, reason: 'already_in_flight' }
    }
    generation += 1
    reconciled = null
    inFlight = {
      identity: freezeIdentity(identity),
      signature: null,
      lastValidBlockHeight: null,
      status: 'reviewing',
    }
    return { ok: true, attempt: inFlight, token: generation }
  }

  /**
   * Re-establish affordability against a fresh reading, and only then unlock the
   * broadcast.
   *
   * Freezing the identity stops the app changing what was reviewed; it does not
   * stop the world changing. Spending from another wallet app between review and
   * approval invalidates the verdict while every frozen field is untouched — and
   * this app cannot prevent that spending, only refuse to add to it.
   */
  function approve(
    token: AttemptToken,
    reading: Snapshot,
    minimumSlot: number,
    evaluate: (opening: bigint, identity: PaymentIdentity) => boolean,
  ): ApproveResult {
    if (!live(token)) return { ok: false, reason: 'stale_attempt' }
    const attempt = inFlight as Attempt
    if (attempt.status !== 'reviewing') return { ok: false, reason: 'not_reviewing' }
    if (reading.network !== attempt.identity.asset.network) {
      return { ok: false, reason: 'wrong_network' }
    }
    if (!settledEnough(reading.commitment)) return { ok: false, reason: 'too_weak_commitment' }
    if (reading.slot < minimumSlot) return { ok: false, reason: 'stale_reading' }
    if (reading.account !== attempt.identity.sender || reading.mint !== attempt.identity.asset.mint) {
      return { ok: false, reason: 'stale_reading' }
    }
    if (!evaluate(reading.amount, attempt.identity)) {
      return { ok: false, reason: 'no_longer_affordable' }
    }
    inFlight = { ...attempt, status: 'awaiting_approval' }
    return { ok: true }
  }

  /**
   * Write the signature down BEFORE it is broadcast.
   *
   * Reachable only from `awaiting_approval`, so a broadcast cannot happen without
   * an approval that saw fresh balance evidence. And only once: overwriting a
   * signature loses the first one from memory AND disk, which is the exact loss
   * the persisted attempt exists to prevent.
   */
  function persistBeforeBroadcast(
    token: AttemptToken,
    signature: string,
    lastValidBlockHeight: number,
  ): BroadcastResult {
    if (!live(token)) return { ok: false, reason: 'stale_attempt' }
    const attempt = inFlight as Attempt
    if (attempt.signature !== null) return { ok: false, reason: 'already_signed' }
    if (attempt.status !== 'awaiting_approval') return { ok: false, reason: 'not_approved' }
    inFlight = { ...attempt, signature, lastValidBlockHeight, status: 'submitted' }
    store.write(serializeAttempt(inFlight))
    return { ok: true }
  }

  /**
   * Reload recovery. A restored unresolved attempt keeps blocking new ones.
   *
   * Refuses to overwrite an attempt that is already live: a reload racing a click
   * would otherwise swap the machine's view to a different payment while the
   * guard still reported "in flight".
   */
  function restore(): { readonly attempt: Attempt | null; readonly token: AttemptToken | null } {
    if (inFlight !== null && !isTerminal(inFlight.status)) {
      return { attempt: inFlight, token: generation }
    }
    const text = store.read()
    if (text === null) return { attempt: null, token: null }
    const attempt = deserializeAttempt(text)
    if (isTerminal(attempt.status)) return { attempt, token: null }
    generation += 1
    reconciled = null
    inFlight = { ...attempt, identity: freezeIdentity(attempt.identity) }
    return { attempt: inFlight, token: generation }
  }

  /**
   * Fold a status reading into the attempt.
   *
   * `null` means the RPC had nothing to say, which is a cache miss as often as it
   * is an absence — historical search is off by default. It is never evidence
   * that a transfer did not land, so it produces `unconfirmed`, never `expired`.
   */
  function resolve(
    token: AttemptToken,
    observed: 'confirmed' | 'failed' | 'rejected' | null,
    blockHeight: number,
  ): { readonly status: AttemptStatus | null; readonly cannotNewlyLand: boolean } {
    if (!live(token)) return { status: null, cannotNewlyLand: false }
    const attempt = inFlight as Attempt
    const status: AttemptStatus = observed === null ? 'unconfirmed' : observed

    // Reported separately from the status on purpose. Passing the last valid
    // block height is a real fact and worth showing, but it is a fact about what
    // can happen NEXT, not about what already happened — so it informs the
    // wording and never becomes `expired` on its own.
    const cannotNewlyLand =
      attempt.lastValidBlockHeight !== null && blockHeight > attempt.lastValidBlockHeight

    inFlight = { ...attempt, status }
    if (isTerminal(status)) store.clear()
    else store.write(serializeAttempt(inFlight))
    return { status, cannotNewlyLand }
  }

  /**
   * Install the post-transfer balance and mark the signature, together.
   *
   * Requires a submitted attempt with a signature. An earlier revision would
   * confirm an attempt that had never been signed and then store `null` as the
   * reconciled marker, which disarmed the idempotence check entirely — both
   * audits reproduced it.
   *
   * The ordering is the rest of the point. Marking first and installing second
   * means a failed refresh leaves the signature marked, so the retry returns
   * `already` and the outlook stays stale for good.
   */
  function reconcile(
    token: AttemptToken,
    result: ReceiptResult,
    snapshot: Snapshot,
  ): ReconcileResult {
    if (!live(token)) return { ok: false, reason: 'stale_attempt' }
    const attempt = inFlight as Attempt
    const signature = attempt.signature
    if (signature === null || attempt.status === 'reviewing' || attempt.status === 'awaiting_approval') {
      return { ok: false, reason: 'not_submitted' }
    }
    if (reconciled === signature) return { ok: false, reason: 'already' }
    if (!result.ok) return { ok: false, reason: 'not_confirmed' }
    if (snapshot.network !== attempt.identity.asset.network) {
      return { ok: false, reason: 'wrong_network' }
    }
    if (!settledEnough(snapshot.commitment)) return { ok: false, reason: 'too_weak_commitment' }
    if (
      snapshot.account !== attempt.identity.sender ||
      snapshot.mint !== attempt.identity.asset.mint
    ) {
      return { ok: false, reason: 'snapshot_mismatch' }
    }
    // A successful refresh is not necessarily a refresh that INCLUDES the
    // transfer.
    if (snapshot.slot < result.slot) return { ok: false, reason: 'stale_snapshot' }

    reconciled = signature
    inFlight = { ...attempt, status: 'confirmed' }
    store.clear()
    return { ok: true, balance: snapshot.amount }
  }

  return { current, begin, approve, persistBeforeBroadcast, restore, resolve, reconcile }
}

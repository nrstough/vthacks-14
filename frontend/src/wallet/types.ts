// Shapes for the demo wallet. Deliberately NOT in src/types.ts, which mirrors
// the API contract: nothing here crosses /api, and a token amount must never be
// mistaken for a cents amount by anything reading that file.
//
// Every monetary value is a signed bigint in the mint's base units. There is no
// second field naming a direction — see Entry.

/** A dated obligation or inflow. */
export type Entry = {
  readonly id: string
  readonly date: string
  /**
   * Signed base units: negative leaves the wallet, positive arrives.
   *
   * The sign is the ONLY thing that carries direction. The bank solver has twice
   * shipped a bug where a negative row labelled "income" — a clawback — was read
   * as money arriving, so there is deliberately no `kind` field to disagree with
   * this one. backend/app/candidates/generator.py:111-118 carries the fix and the
   * comment naming it as the class of both prior bugs.
   */
  readonly amount: bigint
  readonly label: string
}

/** Which chain, which token. Travels with every amount that is displayed. */
export type Asset = {
  readonly network: 'devnet'
  readonly genesisHash: string
  readonly mint: string
  readonly symbol: string
  readonly decimals: number
}

/** The running minimum over the horizon, and where it falls. */
export type Outlook = {
  readonly minimum: bigint
  readonly minimumDate: string
  /** Null when the minimum never drops below the reserve. */
  readonly breachDate: string | null
  /** How far under the reserve, at the worst point. Zero when there is no breach. */
  readonly shortfall: bigint
}

/**
 * Two verdicts, kept apart on purpose.
 *
 * `affordable` is a statement about the schedule as it stands. `conditional` is a
 * statement about a schedule that would exist if changes nobody has made yet were
 * made. Only `affordable` may enable signing — see canSign(). Collapsing these
 * into one sentence erases the distinction that gates an irreversible transfer.
 */
export type VerdictKind = 'affordable' | 'conditional' | 'breaches' | 'never_clears'

export type Verdict = {
  readonly kind: VerdictKind
  readonly text: string
  readonly outlook: Outlook
  /** The first date the same payment clears, or null when none does in the horizon. */
  readonly earliestDate: string | null
}

/**
 * What was reviewed, frozen.
 *
 * Re-reading form state at signing time can change what the user actually approves,
 * so every field the review asserted over is captured here and nothing is read back
 * out of the UI afterwards. Codex review finding 5.
 */
export type PaymentIdentity = {
  readonly attemptId: string
  readonly sender: string
  readonly recipient: string
  readonly asset: Asset
  readonly amount: bigint
  readonly reserve: bigint
  readonly schedule: readonly Entry[]
  readonly asOf: string
  readonly horizonEnd: string
}

/**
 * An attempt, persisted BEFORE broadcast.
 *
 * A submission can reach the network while its response is lost. If the signature
 * only exists in memory, a reload loses it, the transfer disappears from the app's
 * view, and a duplicate becomes possible. Codex review finding 3.
 */
export type Attempt = {
  readonly identity: PaymentIdentity
  readonly signature: string | null
  readonly lastValidBlockHeight: number | null
  readonly status: AttemptStatus
}

/**
 * `unconfirmed` is NOT terminal and is the honest answer whenever the evidence is
 * inconclusive — a null getSignatureStatuses is a cache miss, not proof that a
 * transfer never landed. Codex review finding 4.
 */
export type AttemptStatus =
  | 'reviewing'
  | 'awaiting_approval'
  | 'submitted'
  | 'unconfirmed'
  | 'confirmed'
  | 'failed'
  | 'rejected'
  | 'expired'

export const TERMINAL: readonly AttemptStatus[] = ['confirmed', 'failed', 'rejected', 'expired']

/** One side of a token-balance change, as the chain reports it. */
export type TokenBalance = {
  readonly account: string
  readonly mint: string
  /** Exact base units as a decimal string. Never the float the RPC also sends. */
  readonly amount: string
}

/**
 * A normalised receipt. This module defines the shape it verifies rather than
 * accepting a raw RPC envelope, so the contract is executable.
 *
 * Note what is absent: a genesis hash. getTransaction does not return one, so
 * network provenance cannot be derived from a receipt and is supplied separately,
 * captured at review time.
 */
export type Receipt = {
  readonly signature: string
  readonly slot: number
  readonly err: unknown
  readonly preTokenBalances: readonly TokenBalance[]
  readonly postTokenBalances: readonly TokenBalance[]
}

export type ReceiptRejection =
  | 'signature_mismatch'
  | 'transaction_failed'
  | 'sender_delta_wrong'
  | 'recipient_delta_wrong'
  | 'mint_absent'
  | 'sender_absent'
  | 'recipient_absent'
  | 'metadata_unavailable'
  | 'network_mismatch'

export type ReceiptResult =
  | { readonly ok: true; readonly slot: number }
  | { readonly ok: false; readonly reason: ReceiptRejection }

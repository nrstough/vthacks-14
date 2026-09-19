// What the wallet screen shows, as data.
//
// Split from the component for the same reason src/lib/crash.ts is: the test
// runner is plain node with no DOM, so a .tsx file cannot be rendered here.
// Every decision that could be wrong — whether Sign is enabled, what the
// disabled reason says, which chip the header carries — lives here and is
// tested. The component only arranges the results.

import type { Asset, Entry, Verdict } from './types.ts'
import { canSign } from './ledger.ts'
import { formatAmount } from './units.ts'
import type { ParseFailure } from './units.ts'

/** What the app knows about the chain right now. */
export type Connection =
  | { readonly kind: 'disconnected' }
  | { readonly kind: 'unavailable'; readonly detail: string }
  | { readonly kind: 'wrong_network'; readonly observed: string }
  | { readonly kind: 'ready'; readonly address: string; readonly balance: bigint }

export type SignState = {
  readonly enabled: boolean
  /** Why not, in the product's voice. Null when enabled. */
  readonly reason: string | null
}

/**
 * Sign is enabled only when everything below holds, and the order matters: the
 * reason shown is the first thing actually wrong, not the last one checked.
 *
 * `canSign(verdict)` is the load-bearing one. A conditional verdict describes a
 * schedule nobody has brought about yet, so it can never enable an irreversible
 * transfer — see the comment on VerdictKind.
 */
export function signState(
  connection: Connection,
  amount: { readonly ok: boolean; readonly reason?: ParseFailure },
  verdict: Verdict | null,
): SignState {
  switch (connection.kind) {
    case 'disconnected':
      return { enabled: false, reason: 'Connect a wallet to sign.' }
    case 'unavailable':
      // Never fabricate a transfer, and never take the planning screen down.
      return { enabled: false, reason: 'Payment unavailable. The network could not be reached.' }
    case 'wrong_network':
      return {
        enabled: false,
        reason: `This wallet is on ${connection.observed}. Switch it to Devnet.`,
      }
    case 'ready':
      break
  }

  if (!amount.ok) return { enabled: false, reason: amountHint(amount.reason) }
  if (verdict === null) return { enabled: false, reason: 'Enter an amount to see the outlook.' }
  if (!canSign(verdict)) {
    return { enabled: false, reason: 'This payment does not clear the reserve on the date shown.' }
  }
  return { enabled: true, reason: null }
}

/** A rejected amount, said in words rather than as a code. */
export function amountHint(reason: ParseFailure | undefined): string {
  switch (reason) {
    case 'empty':
      return 'Enter an amount.'
    case 'negative':
      return 'An amount cannot be negative.'
    case 'zero':
      return 'An amount has to be more than zero.'
    case 'exponent':
      return 'Write the amount in full, not in scientific notation.'
    case 'too_many_decimals':
      return 'This token has two decimal places.'
    case 'malformed':
      return 'Use digits and at most one decimal point.'
    default:
      return 'Enter an amount.'
  }
}

/** The header chip. Always names the network, so a demo token is never mistaken. */
export function headerChip(asset: Asset): string {
  return `Demo wallet — Solana ${asset.network === 'devnet' ? 'Devnet' : asset.network}`
}

/** The balance line, or an honest placeholder. */
export function balanceLine(connection: Connection, asset: Asset): string {
  if (connection.kind !== 'ready') return `— ${asset.symbol}`
  return formatAmount(connection.balance, asset.decimals, asset.symbol)
}

export type ObligationRow = {
  readonly id: string
  readonly date: string
  readonly label: string
  readonly amount: string
  readonly incoming: boolean
}

/**
 * The obligations list, in date order.
 *
 * `incoming` is derived from the sign and nothing else. There is no kind field
 * to disagree with it, which is the whole reason Entry has no kind field.
 */
export function obligationRows(entries: readonly Entry[], asset: Asset): ObligationRow[] {
  return [...entries]
    .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0))
    .map((e) => ({
      id: e.id,
      date: e.date,
      label: e.label,
      amount: formatAmount(e.amount, asset.decimals, asset.symbol),
      incoming: e.amount > 0n,
    }))
}

/**
 * The sentence under the verdict, naming the reserve being protected.
 *
 * Never says "guaranteed"; when nothing clears it names the amount and the date
 * rather than using the word this product does not use.
 */
export function reserveLine(reserve: bigint, asset: Asset): string {
  return `Protecting a reserve of ${formatAmount(reserve, asset.decimals, asset.symbol)}.`
}

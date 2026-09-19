// Worked scenarios for the wallet core. Hand-checked, like src/fixtures/scenarios.ts.
//
// The numbers here are the demo beat, not decoration: the thirty-token payment has
// to fail today, the fifteen-token one has to pass today, and the same thirty has
// to first clear on the inflow date. If any of those stops holding, the beat is
// wrong and the tests say so.

import type { Asset, Entry, Receipt } from './types.ts'

export const DEMO: Asset = {
  network: 'devnet',
  genesisHash: 'EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG',
  mint: 'DEMomintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
  symbol: 'DEMO',
  decimals: 2,
}

export const AS_OF = '2026-09-21'
export const HORIZON_END = '2026-09-30'
export const OPENING = 10_000n // 100.00 DEMO
export const RESERVE = 5_000n //  50.00 DEMO

/**
 * Two obligations this week and a payday on Friday.
 *
 * Baseline, with no payment: 100.00 → 76.00 (Tue) → 68.00 (Thu) → 128.00 (Fri).
 * The low point is 68.00, comfortably over the 50.00 reserve.
 */
export const SCHEDULE: readonly Entry[] = [
  { id: 'e_rent', date: '2026-09-22', amount: -2_400n, label: 'Rent share' },
  { id: 'e_phone', date: '2026-09-24', amount: -800n, label: 'Phone' },
  { id: 'e_pay', date: '2026-09-25', amount: 6_000n, label: 'Payroll' },
]

/** The same week with an extra obligation that sinks it before the inflow lands. */
export const SCHEDULE_BLOCKED: readonly Entry[] = [
  ...SCHEDULE,
  { id: 'e_card', date: '2026-09-23', amount: -2_200n, label: 'Card payment' },
]

export const PAYMENT_BREAKS = 3_000n // 30.00 — fails today
export const PAYMENT_CLEARS = 1_500n // 15.00 — passes today
/** The date PAYMENT_BREAKS first clears: the payday, and only because of it. */
export const CLEARS_ON = '2026-09-25'

const SENDER_ATA = 'SenderAtaXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
const RECIPIENT_ATA = 'RecipAtaXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
export const SENDER = SENDER_ATA
export const RECIPIENT = RECIPIENT_ATA
export const SIGNATURE = '5xSigXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

/**
 * A confirmed 15.00 DEMO transfer.
 *
 * The `uiAmount` fields carry deliberately WRONG values. The real RPC sends them
 * alongside the exact strings, and the verifier must read only the strings — a
 * fixture that omitted the field entirely would prove nothing about that.
 */
export function receipt(over: Partial<Receipt> = {}): Receipt {
  return {
    signature: SIGNATURE,
    slot: 1_000,
    err: null,
    preTokenBalances: [
      { account: SENDER_ATA, mint: DEMO.mint, amount: '10000', uiAmount: 999.99 },
      { account: RECIPIENT_ATA, mint: DEMO.mint, amount: '0', uiAmount: 999.99 },
    ],
    postTokenBalances: [
      { account: SENDER_ATA, mint: DEMO.mint, amount: '8500', uiAmount: 999.99 },
      { account: RECIPIENT_ATA, mint: DEMO.mint, amount: '1500', uiAmount: 999.99 },
    ],
    ...over,
  }
}

/**
 * The same transfer to a recipient who had no token account beforehand.
 *
 * There is no pre-balance entry for them at all — not a zero, an absence. A
 * verifier that looks the entry up and does arithmetic on `undefined` fails here,
 * and with strictNullChecks off the compiler will not have warned it. Codex
 * review finding 2.
 */
export function receiptNewRecipient(): Receipt {
  return {
    ...receipt(),
    preTokenBalances: [
      { account: SENDER_ATA, mint: DEMO.mint, amount: '10000', uiAmount: 999.99 },
    ],
  }
}

// The demo wallet screen: same idea, second ledger.
//
// Deliberately thin. Every decision that could be wrong lives in view.ts and
// ledger.ts, which are tested; this file arranges the results and owns no rules
// of its own. The test runner has no DOM, so anything decided here is untested
// by construction — which is the argument for deciding as little as possible.
//
// There is no wallet connection yet and no RPC call. That is not a stub
// pretending to work: the connection state is `disconnected`, the screen says
// so, and Sign is disabled with the reason. Nothing here ever implies a
// transfer happened.

import { useMemo, useState } from 'react'
import { verdictFor } from './ledger.ts'
import { formatAmount, parseUnits } from './units.ts'
import {
  balanceLine,
  headerChip,
  obligationRows,
  reserveLine,
  signState,
} from './view.ts'
import type { Connection } from './view.ts'
import {
  AS_OF,
  DEMO,
  HORIZON_END,
  OPENING,
  RESERVE,
  SCHEDULE,
} from './fixtures.ts'

// Until a wallet extension is wired in, this is the honest state.
const CONNECTION: Connection = { kind: 'disconnected' }

export default function WalletView() {
  const [raw, setRaw] = useState('30.00')
  const asset = DEMO
  const fmt = useMemo(
    () => (base: bigint) => formatAmount(base, asset.decimals, asset.symbol),
    [asset.decimals, asset.symbol],
  )

  const parsed = useMemo(() => parseUnits(raw, asset.decimals), [raw, asset.decimals])

  const verdict = useMemo(() => {
    if (!parsed.ok) return null
    return verdictFor(OPENING, SCHEDULE, RESERVE, AS_OF, HORIZON_END, parsed.value, AS_OF, fmt)
  }, [parsed, fmt])

  const sign = signState(
    CONNECTION,
    parsed.ok ? { ok: true } : { ok: false, reason: parsed.reason },
    verdict,
  )
  const rows = useMemo(() => obligationRows(SCHEDULE, asset), [asset])

  return (
    <section className="wallet">
      <header className="wallet-head">
        <p className="wallet-chip">{headerChip(asset)}</p>
        <p className="wallet-balance num">{balanceLine(CONNECTION, asset)}</p>
      </header>

      <p className="wallet-note">
        A test token on a test network. Not USDC, not money, and not connected to the checking
        account on the other tab — there is no bridge between them by design.
      </p>

      <div className="wallet-grid">
        <div className="wallet-panel">
          <h2>Upcoming</h2>
          <ul className="wallet-rows">
            {rows.map((r) => (
              <li key={r.id} className={r.incoming ? 'in' : 'out'}>
                <span className="wallet-date num">{r.date}</span>
                <span className="wallet-label">{r.label}</span>
                <span className="wallet-amt num">{r.amount}</span>
              </li>
            ))}
          </ul>
          <p className="wallet-reserve">{reserveLine(RESERVE, asset)}</p>
        </div>

        <div className="wallet-panel">
          <h2>Send</h2>
          <label className="ctl">
            <span className="ctl-head">
              Amount <span className="num">{asset.symbol}</span>
            </span>
            <input
              className="wallet-input num"
              value={raw}
              inputMode="decimal"
              onChange={(e) => setRaw(e.target.value)}
              aria-label={`Amount in ${asset.symbol}`}
            />
          </label>

          {verdict !== null && (
            <p className={`wallet-verdict ${verdict.kind}`}>{verdict.text}</p>
          )}

          <button className="wallet-sign" type="button" disabled={!sign.enabled}>
            Review and sign
          </button>
          {sign.reason !== null && <p className="wallet-why">{sign.reason}</p>}
        </div>
      </div>
    </section>
  )
}

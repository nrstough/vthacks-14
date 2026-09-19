import type { SolveRequest, SolveResponse } from '../types'
import { money, shortDate } from '../lib/format'

const TIER_LABEL: Record<1 | 2 | 3, string> = {
  1: 'Proven sufficient',
  2: 'Clears zero, no cushion',
  3: 'Needs outside cash',
}

// The server softens its own wording when a solve stage times out, but these
// three strings are the client's and would keep asserting a proof that was
// never obtained. Tier 1's label is the worst of them: "Proven sufficient" is
// a claim about the search, not about the balances.
const TIER_LABEL_UNPROVEN: Record<1 | 2 | 3, string> = {
  1: 'Sufficient',
  2: 'Clears zero, no cushion',
  3: 'Needs outside cash',
}

export default function VerdictBand({ res, req }: { res: SolveResponse; req: SolveRequest }) {
  return (
    <section className="verdict">
      <span className={`pill t${res.tier}`}>
        {(res.certificate.minimal_proven ? TIER_LABEL : TIER_LABEL_UNPROVEN)[res.tier]}
      </span>
      <h1>{res.verdict}</h1>
      <p className="qualifier num">{res.qualifier}</p>

      {res.external_cash_needed && (
        <div className="cash-callout">
          <div className="amount num">
            {money(res.external_cash_needed.amount_cents)} by {shortDate(res.external_cash_needed.by_date)}
          </div>
          <p>
            Cutting spending is not enough here. That is enough to cover the deepest point, and it
            has to be there by the first day you would otherwise go under.
          </p>
        </div>
      )}

      {res.plan.length > 0 && (
        <div className="certificate num">
          {!res.certificate.minimal_proven && (
            <span className="unproven">Not fully proven, the solver ran out of time</span>
          )}
          <strong>
            {res.certificate.minimal_proven ? 'Why this is the smallest plan. ' : 'Why these changes. '}
          </strong>
          {res.certificate.sentence}{' '}
          {res.tier === 3
            ? 'Measured against a zero balance.'
            : `Checked against a zero balance, not the ${money(req.buffer_cents)} cushion.`}
        </div>
      )}
    </section>
  )
}

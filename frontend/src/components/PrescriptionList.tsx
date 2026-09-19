import type { Candidate, SolveRequest, SolveResponse } from '../types'
import type { Overrides } from '../lib/overrides'
import { isRuledOut, pendingIds } from '../lib/overrides'
import { PENDING, reasonFor } from '../lib/reasons'
import { emptyPlanText } from '../lib/narrate'
import { money, shortDate } from '../lib/format'

// One control, the same on every row in both sections: the user tells us
// whether they can do a change, and nothing else. Which section a row is in is
// the solver's answer; this checkbox is the user's input. They used to be the
// same three-way control, which meant one visual state read as "chosen" on a
// plan row and "rejected" on a left-out row.
function CantDo({
  id,
  label,
  checked,
  onToggle,
}: {
  id: string
  label: string
  checked: boolean
  onToggle: (id: string) => void
}) {
  return (
    <label className="cant" htmlFor={`cant-${id}`}>
      <input
        id={`cant-${id}`}
        type="checkbox"
        checked={checked}
        onChange={() => onToggle(id)}
        // Eleven identical labels are indistinguishable to a screen reader, so
        // the accessible name carries the change it belongs to.
        aria-label={`Can't do this: ${label}`}
      />
      Can&rsquo;t do this
    </label>
  )
}

function Pain({ n }: { n: number }) {
  return (
    <div className="rx-pain">
      <span aria-hidden="true">{`${'●'.repeat(n)}${'○'.repeat(5 - n)}`}</span>{' '}
      <span className="rx-pain-text">Disruption {n} of 5</span>
    </div>
  )
}

export default function PrescriptionList({
  req,
  res,
  ruledOut,
  solvedRuledOut,
  newIds,
  onToggle,
}: {
  req: SolveRequest
  res: SolveResponse
  ruledOut: Overrides
  solvedRuledOut: Overrides
  newIds: string[]
  onToggle: (id: string) => void
}) {
  const used = new Set(res.plan.map((p) => p.candidate_id))
  const rest: Candidate[] = req.candidates.filter((c) => !used.has(c.id))
  // Rows whose override has moved since the answer on screen was solved. Every
  // sentence we could write about them describes a solve that never saw the
  // user's current answer, so they say nothing until the next response lands.
  const pending = pendingIds(ruledOut, solvedRuledOut)

  return (
    <>
      <div className="rx">
        {res.plan.length === 0 && <p className="rx-empty">{emptyPlanText(res).body}</p>}
        {res.plan.map((p) => {
          const stale = pending.has(p.candidate_id)
          const cls = [
            'rx-row',
            newIds.includes(p.candidate_id) ? 'is-new' : '',
            stale ? 'is-pending' : '',
          ]
            .filter(Boolean)
            .join(' ')
          return (
            <div key={p.candidate_id} className={cls}>
              <div className="rx-date num">
                {shortDate(p.date)}
                <small>act by</small>
              </div>
              <div>
                <p className="rx-label">{p.label}</p>
                <p className="rx-detail num">{p.detail}</p>
                {stale ? (
                  <p className="rx-reason soft">{PENDING.text}</p>
                ) : (
                  <p className={`rx-reason num${p.strictly_needed ? '' : ' soft'}`}>{p.reason}</p>
                )}
              </div>
              <div>
                <div className="rx-amount num">+{money(p.freed_cents)}</div>
                <Pain n={p.pain} />
              </div>
              <CantDo
                id={p.candidate_id}
                label={p.label}
                checked={isRuledOut(ruledOut, p.candidate_id)}
                onToggle={onToggle}
              />
            </div>
          )
        })}
      </div>

      {rest.length > 0 && (
        <details className="considered" open>
          <summary>
            {rest.length} other {rest.length === 1 ? 'change was' : 'changes were'} considered and
            left out
          </summary>
          <div className="rx">
            {rest.map((c) => {
              const out = isRuledOut(ruledOut, c.id)
              // The response on screen was solved with `solvedRuledOut`. If the
              // user has since changed this row, no reason we could give would
              // be about the answer they are looking at.
              const reason = pending.has(c.id)
                ? PENDING
                : reasonFor(c, req, res, isRuledOut(solvedRuledOut, c.id))
              return (
                <div key={c.id} className={`rx-row${out ? ' is-out' : ''}`}>
                  <div className="rx-date num">{shortDate(c.effective_date)}</div>
                  <div>
                    <p className="rx-label">{c.label}</p>
                    <p className="rx-detail num">{c.detail}</p>
                    <p className="rx-why">{reason.text}</p>
                  </div>
                  <div>
                    <div className="rx-amount num">+{money(c.freed_cents)}</div>
                    <Pain n={c.pain} />
                  </div>
                  <CantDo id={c.id} label={c.label} checked={out} onToggle={onToggle} />
                </div>
              )
            })}
          </div>
        </details>
      )}
    </>
  )
}

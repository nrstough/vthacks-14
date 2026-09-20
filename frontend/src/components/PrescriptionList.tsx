import type { Candidate, SolveRequest, SolveResponse } from '../types'
import type { Overrides } from '../lib/overrides'
import { isRuledOut, pendingIds } from '../lib/overrides'
import type { Control } from '../lib/cant.ts'
import { controlFor } from '../lib/cant.ts'
import { PENDING, actByNotice, reasonFor } from '../lib/reasons'
import { emptyPlanText } from '../lib/narrate'
import { money, shortDate } from '../lib/format'

// One set underneath, two readings on top. In the plan list the question is
// "can't you do this?"; in the left-out list it is "can you?", and the box is
// ticked when the answer is yes. The words carry the meaning, never the tick
// alone: a tick meaning two things silently is the bug the one control replaced.
// What to render is decided by `controlFor` in `lib/cant.ts`; this component
// renders whatever it returns.
function CantDo({
  control,
  candidateId,
  onToggle,
  onFocus,
}: {
  control: Control
  candidateId: string
  onToggle: (id: string) => void
  onFocus: (id: string) => void
}) {
  return (
    <label className="cant" htmlFor={control.id}>
      <input
        id={control.id}
        type="checkbox"
        checked={control.checked}
        onChange={() => onToggle(candidateId)}
        onFocus={() => onFocus(candidateId)}
        // Eleven identical labels are indistinguishable to a screen reader, so
        // the accessible name carries the change it belongs to.
        aria-label={control.ariaLabel}
      />
      {control.text}
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
  onFocusRow,
}: {
  req: SolveRequest
  res: SolveResponse
  ruledOut: Overrides
  solvedRuledOut: Overrides
  newIds: string[]
  onToggle: (id: string) => void
  onFocusRow: (id: string) => void
}) {
  const byId = new Map(req.candidates.map((c) => [c.id, c]))
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
          const candidate = byId.get(p.candidate_id)
          const notice = candidate ? actByNotice(candidate) : null
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
                <small>takes effect</small>
              </div>
              <div>
                <p className="rx-label">{p.label}</p>
                <p className="rx-detail num">{p.detail}</p>
                {stale ? (
                  <p className="rx-reason soft">{PENDING.text}</p>
                ) : (
                  <p className={`rx-reason num${p.strictly_needed ? '' : ' soft'}`}>{p.reason}</p>
                )}
                {notice && <p className="rx-notice num">{notice}</p>}
              </div>
              <div>
                <div className="rx-amount num">+{money(p.freed_cents)}</div>
                <Pain n={p.pain} />
              </div>
              <CantDo
                control={controlFor('plan', ruledOut, p.candidate_id, p.label)}
                candidateId={p.candidate_id}
                onToggle={onToggle}
                onFocus={onFocusRow}
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
                <div
                  key={c.id}
                  className={`rx-row${out ? ' is-out' : ''}${pending.has(c.id) ? ' is-pending' : ''}`}
                >
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
                  <CantDo
                    control={controlFor('out', ruledOut, c.id, c.label)}
                    candidateId={c.id}
                    onToggle={onToggle}
                    onFocus={onFocusRow}
                  />
                </div>
              )
            })}
          </div>
        </details>
      )}
    </>
  )
}

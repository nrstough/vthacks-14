import type { Candidate, Locks, SolveRequest, SolveResponse } from '../types'
import { money, shortDate } from '../lib/format'

export type LockState = 'in' | 'auto' | 'out'

function stateOf(id: string, locks: Locks): LockState {
  if (locks.in.includes(id)) return 'in'
  if (locks.out.includes(id)) return 'out'
  return 'auto'
}

// "Keep" was ambiguous next to a row reading "Skip the DoorDash order": it
// could mean keep the order or keep the change. These say what the user means.
const OPTIONS: [LockState, string, string][] = [
  ['in', 'Must do', 'Force this change into the plan'],
  ['auto', 'Auto', 'Let the solver decide'],
  ['out', "Can't do", 'Rule this change out and re-plan without it'],
]

function LockControl({
  id,
  locks,
  onChange,
}: {
  id: string
  locks: Locks
  onChange: (id: string, next: LockState) => void
}) {
  const current = stateOf(id, locks)
  return (
    <div className="locks" role="group" aria-label="Pin or rule out this change">
      {OPTIONS.map(([value, label, title]) => (
        <button
          key={value}
          type="button"
          title={title}
          aria-label={title}
          aria-pressed={current === value}
          onClick={() => onChange(id, value)}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

function pain(n: number): string {
  return `${'●'.repeat(n)}${'○'.repeat(5 - n)}`
}

export default function PrescriptionList({
  req,
  res,
  locks,
  newIds,
  onLockChange,
}: {
  req: SolveRequest
  res: SolveResponse
  locks: Locks
  newIds: string[]
  onLockChange: (id: string, next: LockState) => void
}) {
  const used = new Set(res.plan.map((p) => p.candidate_id))
  const rest: Candidate[] = req.candidates.filter((c) => !used.has(c.id))

  return (
    <>
      <div className="rx">
        {res.plan.length === 0 && (
          <p className="rx-empty">Nothing to change. The schedule already clears on its own.</p>
        )}
        {res.plan.map((p) => {
          const pinned = stateOf(p.candidate_id, locks) === 'in'
          const strictlyNeeded = p.strictly_needed
          const cls = [
            'rx-row',
            pinned ? 'is-pinned' : '',
            newIds.includes(p.candidate_id) ? 'is-new' : '',
          ]
            .filter(Boolean)
            .join(' ')
          return (
            <div key={p.candidate_id} className={cls}>
              <div className="rx-date num">{shortDate(p.date)}</div>
              <div>
                <p className="rx-label">
                  {p.label}
                  {pinned && <span className="tag">you pinned this</span>}
                </p>
                <p className="rx-detail num">{p.detail}</p>
                <p className={`rx-reason num${strictlyNeeded ? '' : ' soft'}`}>{p.reason}</p>
              </div>
              <div>
                <div className="rx-amount num">+{money(p.freed_cents)}</div>
                <div className="rx-pain" title={`Disruption ${p.pain} of 5`}>
                  {pain(p.pain)}
                </div>
              </div>
              <LockControl id={p.candidate_id} locks={locks} onChange={onLockChange} />
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
              const out = stateOf(c.id, locks) === 'out'
              return (
                <div key={c.id} className={`rx-row${out ? ' is-out' : ''}`}>
                  <div className="rx-date num">{shortDate(c.effective_date)}</div>
                  <div>
                    <p className="rx-label">
                      {c.label}
                      {out && <span className="tag tag-out">you ruled this out</span>}
                    </p>
                    <p className="rx-detail num">{c.detail}</p>
                  </div>
                  <div>
                    <div className="rx-amount num">+{money(c.freed_cents)}</div>
                    <div className="rx-pain" title={`Disruption ${c.pain} of 5`}>
                      {pain(c.pain)}
                    </div>
                  </div>
                  <LockControl id={c.id} locks={locks} onChange={onLockChange} />
                </div>
              )
            })}
          </div>
        </details>
      )}
    </>
  )
}

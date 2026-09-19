import { money, shortDate } from '../lib/format'
import { daysUnder, lowestDoingNothing, lowestWithPlan } from '../lib/kpis'
import type { SolveResponse } from '../types'

interface Props {
  res: SolveResponse
}

/**
 * The three figures beside the verdict. All of them are read off the solve.
 *
 * There is deliberately no "fees avoided" figure in dollars: the contract
 * carries no fee schedule, so the honest unit is days below zero, which is
 * also the term the objective minimises first.
 *
 * Each value is keyed on its own text, so React remounts it when it changes
 * and the tick animation replays only when the number actually moved.
 */
export default function Stats({ res }: Props) {
  const low = lowestWithPlan(res)
  const base = lowestDoingNothing(res)
  const days = daysUnder(res)
  const gap = res.external_cash_needed
  // Signed, and it can be zero when the schedule already cleared on its own.
  const improvement = low.cents - base.cents

  return (
    <div className="stats" aria-label="This solve at a glance">
      <div className="stat">
        <span className="stat-label">Lowest point</span>
        <span
          className={`stat-value ${low.cents < 0 ? 'neg' : 'pos'}`}
          key={`low-${low.cents}`}
        >
          {money(low.cents)}
        </span>
        <span className="stat-sub">{low.date ? `with the plan, ${shortDate(low.date)}` : 'no days in window'}</span>
      </div>

      <div className="stat">
        <span className="stat-label">Days below zero</span>
        <span className="stat-value" key={`days-${days.withPlan}-${days.doingNothing}`}>
          {days.withPlan} / {days.doingNothing}
        </span>
        <span className={`stat-sub${days.avoided > 0 ? ' pos' : ''}`}>
          {days.avoided > 0 ? `${days.avoided} avoided` : 'none either way'}
        </span>
      </div>

      {gap ? (
        <div className="stat">
          <span className="stat-label">Outside cash</span>
          <span className="stat-value neg" key={`gap-${gap.amount_cents}`}>
            {money(gap.amount_cents)}
          </span>
          <span className="stat-sub neg">needed by {shortDate(gap.by_date)}</span>
        </div>
      ) : (
        <div className="stat">
          <span className="stat-label">Doing nothing</span>
          <span className="stat-value neg" key={`base-${base.cents}`}>
            {money(base.cents)}
          </span>
          <span className={`stat-sub${improvement > 0 ? ' pos' : ''}`}>
            {improvement > 0 ? `${money(improvement)} better with the plan` : 'same with the plan'}
          </span>
        </div>
      )}
    </div>
  )
}

import { money, shortDate } from '../lib/format'
import { daysUnder, headroom, lowestDoingNothing, lowestWithPlan, planClaim } from '../lib/kpis'
import type { SolveRequest, SolveResponse } from '../types'

interface Props {
  res: SolveResponse
  req: SolveRequest
}

/**
 * Four figures, all of them read off the solve. There is deliberately no
 * "fees avoided" tile in dollars: the contract carries no fee schedule, so the
 * honest unit is days below zero, which is also the term the objective
 * minimises first.
 *
 * Each value is keyed on its own text so React remounts it when it changes and
 * the tick animation replays — a figure that moved should look like it moved.
 */
export default function KpiRow({ res, req }: Props) {
  const low = lowestWithPlan(res)
  const base = lowestDoingNothing(res)
  const days = daysUnder(res)
  const gap = res.external_cash_needed
  const room = headroom(res, req)
  const improvement = low.cents - base.cents

  return (
    <section className="kpi-row" aria-label="This solve at a glance">
      <div className="kpi-card accent">
        <div className="kpi-label">
          Lowest point with the plan
          <span className="kpi-icon" aria-hidden="true">
            ↓
          </span>
        </div>
        <div className="kpi-value num" key={`low-${low.cents}`}>
          {money(low.cents)}
        </div>
        <div className="kpi-sub">
          {improvement > 0 && <span className="delta up num">+{money(improvement)}</span>}
          {low.date ? `on ${shortDate(low.date)}` : 'no days in the window'}
        </div>
      </div>

      <div className="kpi-card">
        <div className="kpi-label">
          Doing nothing, you bottom out at
          <span className="kpi-icon" aria-hidden="true">
            ≈
          </span>
        </div>
        <div className="kpi-value num" key={`base-${base.cents}`}>
          {money(base.cents)}
        </div>
        <div className="kpi-sub">
          {base.date ? `on ${shortDate(base.date)}` : 'no days in the window'}
        </div>
      </div>

      <div className="kpi-card">
        <div className="kpi-label">
          Days below zero
          <span className="kpi-icon" aria-hidden="true">
            #
          </span>
        </div>
        <div className="kpi-value num" key={`days-${days.withPlan}-${days.doingNothing}`}>
          {days.withPlan}
          <span className="kpi-of"> of {days.doingNothing}</span>
        </div>
        <div className="kpi-sub">
          {days.avoided > 0 && <span className="delta up num">{days.avoided} avoided</span>}
          {days.doingNothing === 0 ? 'none either way' : 'left after the plan'}
        </div>
      </div>

      {gap ? (
        <div className="kpi-card">
          <div className="kpi-label">
            Outside cash needed
            <span className="kpi-icon" aria-hidden="true">
              +
            </span>
          </div>
          <div className="kpi-value num" key={`gap-${gap.amount_cents}`}>
            {money(gap.amount_cents)}
          </div>
          <div className="kpi-sub">
            <span className="delta down num">by {shortDate(gap.by_date)}</span>
            the first day you would go under
          </div>
        </div>
      ) : (
        <div className="kpi-card">
          <div className="kpi-label">
            {res.plan.length === 1 ? 'Change' : 'Changes'} in the plan
            <span className="kpi-icon" aria-hidden="true">
              ✓
            </span>
          </div>
          <div className="kpi-value num" key={`plan-${res.plan.length}`}>
            {res.plan.length}
          </div>
          <div className="kpi-sub">
            {room >= 0 && <span className="delta up num">{money(room)} over the cushion</span>}
            {planClaim(res)}
          </div>
        </div>
      )}
    </section>
  )
}

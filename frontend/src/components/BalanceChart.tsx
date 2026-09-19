import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { SolveRequest, SolveResponse } from '../types'
import { money, shortDate } from '../solver/mockSolver'

interface Row {
  date: string
  day: string
  baseline: number
  withPlan: number
  isPayday: boolean
  changes: string[]
}

function compactMoney(cents: number): string {
  const sign = cents < 0 ? '-' : ''
  return `${sign}$${Math.round(Math.abs(cents) / 100)}`
}

function Tip({ active, payload, plan }: any) {
  if (!active || !payload?.length) return null
  const row: Row = payload[0].payload
  const names = row.changes
    .map((id) => plan.find((p: any) => p.candidate_id === id)?.label)
    .filter(Boolean)
  return (
    <div className="tip num">
      <div className="tip-date">{shortDate(row.date)}</div>
      <div className={`tip-row${row.baseline < 0 ? ' tip-neg' : ''}`}>
        <span>Do nothing</span>
        <b>{money(row.baseline)}</b>
      </div>
      <div className={`tip-row${row.withPlan < 0 ? ' tip-neg' : ''}`}>
        <span>With the plan</span>
        <b>{money(row.withPlan)}</b>
      </div>
      {names.length > 0 && <div className="tip-change">{names.join(' + ')} takes effect</div>}
    </div>
  )
}

export default function BalanceChart({ res, req }: { res: SolveResponse; req: SolveRequest }) {
  const data: Row[] = res.balances.map((b) => ({
    date: b.date,
    day: String(Number(b.date.slice(8, 10))),
    baseline: b.baseline_cents,
    withPlan: b.with_plan_cents,
    isPayday: b.is_payday,
    changes: b.changes_here,
  }))

  // Split the baseline fill exactly at zero, so red marks the overdraft and
  // nothing else. The gradient maps to the area shape's bounding box, which
  // spans the baseline series min to max because the area is based at zero.
  const vals = data.map((d) => d.baseline)
  const hi = Math.max(...vals)
  const lo = Math.min(...vals)
  const zeroOffset = hi <= 0 ? 0 : lo >= 0 ? 1 : hi / (hi - lo)

  // Tier 3 leaves a dip the plan cannot close. Mark it, or the blue line just
  // looks like it grazes zero.
  const residual = res.shortfall.worst_date
    ? data.find((d) => d.date === res.shortfall.worst_date)
    : undefined

  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
          <defs>
            <linearGradient id="splitFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset={0} stopColor="var(--accent)" stopOpacity={0.1} />
              <stop offset={zeroOffset} stopColor="var(--accent)" stopOpacity={0.02} />
              <stop offset={zeroOffset} stopColor="var(--neg)" stopOpacity={0.16} />
              <stop offset={1} stopColor="var(--neg)" stopOpacity={0.3} />
            </linearGradient>
          </defs>

          <CartesianGrid stroke="var(--line)" vertical={false} />

          <XAxis
            dataKey="day"
            tickLine={false}
            axisLine={{ stroke: 'var(--line)' }}
            tick={{ fill: 'var(--ink-3)', fontSize: 12 }}
            interval={0}
          />
          <YAxis
            tickFormatter={compactMoney}
            tickLine={false}
            axisLine={false}
            width={56}
            tick={{ fill: 'var(--ink-3)', fontSize: 12 }}
          />

          <Tooltip content={<Tip plan={res.plan} />} cursor={{ stroke: 'var(--line-strong)' }} />

          {data
            .filter((d) => d.isPayday)
            .map((d) => (
              <ReferenceLine
                key={d.date}
                x={d.day}
                stroke="var(--line-strong)"
                strokeDasharray="3 3"
                label={{ value: 'payday', position: 'insideTopRight', fill: 'var(--ink-3)', fontSize: 11 }}
              />
            ))}

          <ReferenceLine y={req.buffer_cents} stroke="var(--ink-3)" strokeDasharray="2 5" />
          <ReferenceLine y={0} stroke="var(--neg)" strokeWidth={1} />

          {residual && (
            <ReferenceDot
              x={residual.day}
              y={residual.withPlan}
              r={5}
              fill="var(--neg)"
              stroke="var(--bg)"
              strokeWidth={2}
              label={{
                value: `${money(residual.withPlan)} still short`,
                position: 'bottom',
                fill: 'var(--neg)',
                fontSize: 11,
              }}
            />
          )}

          <Area
            type="linear"
            dataKey="baseline"
            baseValue={0}
            fill="url(#splitFill)"
            stroke="var(--ink-3)"
            strokeWidth={1.5}
            strokeDasharray="4 3"
            isAnimationActive
            animationDuration={350}
            activeDot={false}
          />
          <Line
            type="linear"
            dataKey="withPlan"
            stroke="var(--accent)"
            strokeWidth={2.5}
            isAnimationActive
            animationDuration={350}
            activeDot={{ r: 4, fill: 'var(--accent)', stroke: 'var(--bg)', strokeWidth: 2 }}
            dot={(props: any) => {
              const row: Row = props.payload
              const marked = row.changes.length > 0
              return (
                <circle
                  key={row.date}
                  cx={props.cx}
                  cy={props.cy}
                  r={marked ? 4.5 : 0}
                  fill="var(--bg)"
                  stroke="var(--accent)"
                  strokeWidth={2.5}
                />
              )
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

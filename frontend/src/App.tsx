import { useEffect, useMemo, useRef, useState } from 'react'
import BalanceChart from './components/BalanceChart'
import PrescriptionList from './components/PrescriptionList'
import type { LockState } from './components/PrescriptionList'
import VerdictBand from './components/VerdictBand'
import { SCENARIOS } from './fixtures/scenarios'
import { money } from './lib/format'
import { solve } from './solver/mockSolver'
import type { Locks } from './types'

const NO_LOCKS: Locks = { in: [], out: [] }
const BASE = SCENARIOS[0].request

export default function App() {
  const [opening, setOpening] = useState(BASE.opening_balance_cents)
  const [buffer, setBuffer] = useState(BASE.buffer_cents)
  const [locks, setLocks] = useState<Locks>(NO_LOCKS)
  const [newIds, setNewIds] = useState<string[]>([])
  const previousPlan = useRef<string[]>([])

  const request = useMemo(
    () => ({ ...BASE, opening_balance_cents: opening, buffer_cents: buffer, locks }),
    [opening, buffer, locks],
  )

  // Solving happens in an effect, not in render, because the real build swaps
  // the solve() call for `await fetch('/api/solve', ...)`. Nothing else in the
  // UI changes: the response shape is already the contract's. Hysteresis wants
  // the plan the user was last looking at, which is what the ref holds.
  const [res, setRes] = useState(() => solve(request, []))

  useEffect(() => {
    const before = previousPlan.current
    const next = solve(request, before)
    previousPlan.current = next.plan.map((p) => p.candidate_id)
    setRes(next)
    setNewIds(next.plan.map((p) => p.candidate_id).filter((id) => !before.includes(id)))
  }, [request])

  function onLockChange(id: string, next: LockState) {
    setLocks((prev) => ({
      in: next === 'in' ? [...prev.in.filter((x) => x !== id), id] : prev.in.filter((x) => x !== id),
      out: next === 'out' ? [...prev.out.filter((x) => x !== id), id] : prev.out.filter((x) => x !== id),
    }))
  }

  function preset(cents: number) {
    setOpening(cents)
    setLocks(NO_LOCKS)
    previousPlan.current = []
  }

  const locked = locks.in.length + locks.out.length

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="wordmark">
            Overdraft Guard <span>&nbsp;/&nbsp; the smallest plan that clears</span>
          </p>
          <p className="tagline">
            Sample checking account, September 19 to October 2, 2026. Move a slider or rule a change
            out, and the plan is re-solved from scratch.
          </p>
        </div>
      </header>

      <section className="controls">
        <label className="ctl">
          <span className="ctl-head">
            Starting balance
            <b className="num">{money(opening)}</b>
          </span>
          <input
            type="range"
            min={2000}
            max={30000}
            step={500}
            value={opening}
            onChange={(e) => setOpening(Number(e.target.value))}
          />
          <span className="ctl-presets">
            {SCENARIOS.map((s) => (
              <button
                key={s.key}
                type="button"
                aria-pressed={s.request.opening_balance_cents === opening}
                onClick={() => preset(s.request.opening_balance_cents)}
              >
                {money(s.request.opening_balance_cents)}
              </button>
            ))}
          </span>
        </label>

        <label className="ctl">
          <span className="ctl-head">
            Cushion to keep
            <b className="num">{money(buffer)}</b>
          </span>
          <input
            type="range"
            min={0}
            max={10000}
            step={500}
            value={buffer}
            onChange={(e) => setBuffer(Number(e.target.value))}
          />
          <span className="ctl-note">How much you want left over on the worst day.</span>
        </label>
      </section>

      <VerdictBand res={res} req={request} />

      <section className="band">
        <div className="band-head">
          <h2>Daily balance, September 19 to October 2</h2>
          <div className="legend">
            <span>
              <i className="l-base" />
              Do nothing
            </span>
            <span>
              <i className="l-plan" />
              With the plan
            </span>
            <span>
              <i className="l-zero" />
              Zero
            </span>
            <span>
              <i className="l-buffer" />
              {money(buffer)} cushion
            </span>
          </div>
        </div>
        <BalanceChart res={res} req={request} />
      </section>

      <section className="band">
        <div className="band-head">
          <h2>
            {res.plan.length === 0
              ? 'No changes needed'
              : `${res.plan.length} change${res.plan.length === 1 ? '' : 's'}, in the order you have to make them`}
          </h2>
          {locked > 0 && (
            <button type="button" className="reset" onClick={() => setLocks(NO_LOCKS)}>
              Clear {locked} override{locked === 1 ? '' : 's'}
            </button>
          )}
        </div>
        <PrescriptionList
          req={request}
          res={res}
          locks={locks}
          newIds={newIds}
          onLockChange={onLockChange}
        />
      </section>

      <footer className="meta num">
        <span>Solver: {res.meta.solver}</span>
        <span>Status: {res.meta.status}</span>
        <span>Solved in {res.meta.wall_ms} ms</span>
        <span>{res.meta.candidates_considered} candidates on the table</span>
      </footer>
    </main>
  )
}

import { useEffect, useMemo, useRef, useState } from 'react'
import BalanceChart from './components/BalanceChart'
import PrescriptionList from './components/PrescriptionList'
import VerdictBand from './components/VerdictBand'
import { SCENARIOS } from './fixtures/scenarios'
import { solveViaApi } from './lib/api'
import { money } from './lib/format'
import { emptyPlanText, footerLines, narrateChart } from './lib/narrate'
import type { Overrides } from './lib/overrides'
import { NONE, count, fromIds, pendingIds, toLocks, toggle } from './lib/overrides'
import { armOnToggle, decideRestore, domId } from './lib/focus'
import { useDebounced } from './lib/useDebounced'
import { solve } from './solver/mockSolver'
import type { SolveResponse } from './types'

const BASE = SCENARIOS[0].request

export default function App() {
  const [opening, setOpening] = useState(BASE.opening_balance_cents)
  const [buffer, setBuffer] = useState(BASE.buffer_cents)
  const [ruledOut, setRuledOut] = useState<Overrides>(NONE)
  const [newIds, setNewIds] = useState<string[]>([])
  const previousPlan = useRef<string[]>([])

  const request = useMemo(
    () => ({
      ...BASE,
      opening_balance_cents: opening,
      buffer_cents: buffer,
      locks: toLocks(ruledOut),
    }),
    [opening, buffer, ruledOut],
  )

  // Seeded from the local solver so the first paint is instant and the page is
  // never blank, then replaced by the server's answer when it arrives.
  const [res, setRes] = useState(() => solve(request, []))
  // Which overrides the answer on screen was actually solved with. The reasons
  // under the left-out changes are statements about THAT solve, so they cannot
  // be computed from a set the solver has not seen yet.
  const [solvedRuledOut, setSolvedRuledOut] = useState<Overrides>(NONE)
  const [source, setSource] = useState<'local' | 'server'>('local')
  const [notice, setNotice] = useState<string | null>(null)
  const seq = useRef(0)
  // A re-solve moves rows between the plan and the left-out list, unmounting
  // their checkboxes. Track the row the user is actually on rather than the one
  // they toggled: the response can move a different row out from under them.
  const focused = useRef<string | null>(null)
  // Restoring focus dispatches the checkbox's own focus event, which would
  // write the id straight back into the ref we just consumed.
  const restoring = useRef(false)

  // A drag of the balance slider steps through dozens of values. Debounce the
  // request, not the slider, so the number under the thumb still tracks it.
  const debounced = useDebounced(request, 150)

  useEffect(() => {
    const mine = ++seq.current
    const ctl = new AbortController()
    const before = previousPlan.current
    const sentOverrides = fromIds(debounced.locks.out)

    function apply(next: SolveResponse, from: 'local' | 'server', msg: string | null) {
      // A newer request has already landed, so this one is stale. Returning
      // here also protects previousPlan: it feeds the churn term, so letting a
      // late response write it would make the plan depend on arrival order.
      if (mine !== seq.current) return
      previousPlan.current = next.plan.map((p) => p.candidate_id)
      setRes(next)
      setSolvedRuledOut(sentOverrides)
      setNewIds(next.plan.map((p) => p.candidate_id).filter((id) => !before.includes(id)))
      setSource(from)
      setNotice(msg)
    }

    solveViaApi(debounced, before, ctl.signal)
      .then((next) => apply(next, 'server', null))
      .catch((err: unknown) => {
        if (ctl.signal.aborted) return
        // Fall back rather than blank the page. The local solver is exact at
        // this size, so a dead backend or dead venue wifi during judging
        // costs the CP-SAT provenance, not the demo.
        apply(
          solve(debounced, before),
          'local',
          err instanceof Error ? err.message : 'Solver unreachable.',
        )
      })

    return () => ctl.abort()
  }, [debounced])

  useEffect(() => {
    const active = document.activeElement
    const decision = decideRestore({
      refId: focused.current,
      // Focus parked on the body (or the root) means it was lost when a row
      // unmounted, not moved there by the user.
      focusWasLost: !active || active === document.body || active === document.documentElement,
      // Nothing else is in flight: what is on screen answers what the user asked.
      settled: pendingIds(ruledOut, solvedRuledOut).size === 0,
    })
    if (decision.clear) focused.current = null
    if (!decision.focus) return

    const el = document.getElementById(domId(decision.focus))
    if (!el) return
    // The row may have landed inside the collapsed "other changes" section, and
    // nothing inside a closed <details> can take focus.
    const section = el.closest('details')
    if (section && !section.open) section.open = true
    // Focusing dispatches the checkbox's own focus event, which would write the
    // id straight back into the ref this just consumed.
    restoring.current = true
    el.focus()
    restoring.current = false
    // Deliberately keyed on the response alone. Running this when `ruledOut`
    // changes would fire it at the moment of the toggle, while the row is still
    // mounted and focus has not been lost, and it would throw the remembered
    // row away before the answer that unmounts it ever arrives. The values it
    // reads are this render's, which is the render the response produced.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [res])

  function onToggle(id: string) {
    // Two signals feed the same ref, because neither covers everything. The
    // toggle tells us where focus is at the moment of the change, which works
    // even where focus events do not fire; the onFocus handler below keeps it
    // current if the user tabs on while the answer is still being solved.
    focused.current = armOnToggle({
      activeElementId: document.activeElement?.id ?? null,
      toggledId: id,
    })
    setRuledOut((prev) => toggle(prev, id))
  }

  function onFocusRow(id: string) {
    if (restoring.current) return
    focused.current = id
  }

  function preset(cents: number, cushion: number) {
    setOpening(cents)
    setBuffer(cushion)
    setRuledOut(NONE)
    previousPlan.current = []
  }

  const locked = count(ruledOut)
  const narration = narrateChart(res).join(' ')

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
                title={`${money(s.request.opening_balance_cents)} to start, ${money(
                  s.request.buffer_cents,
                )} cushion`}
                aria-pressed={
                  s.request.opening_balance_cents === opening && s.request.buffer_cents === buffer
                }
                onClick={() => preset(s.request.opening_balance_cents, s.request.buffer_cents)}
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
        <p className="narration" id="chart-text">
          {narration}
        </p>
        <BalanceChart res={res} req={request} describedBy="chart-text" />
      </section>

      <section className="band">
        <div className="band-head">
          <h2>
            {res.plan.length === 0
              ? emptyPlanText(res).heading
              : `${res.plan.length} change${res.plan.length === 1 ? '' : 's'}, in the order they take effect`}
          </h2>
          {locked > 0 && (
            <button type="button" className="reset" onClick={() => setRuledOut(NONE)}>
              Clear {locked} override{locked === 1 ? '' : 's'}
            </button>
          )}
        </div>
        <PrescriptionList
          req={request}
          res={res}
          ruledOut={ruledOut}
          solvedRuledOut={solvedRuledOut}
          newIds={newIds}
          onToggle={onToggle}
          onFocusRow={onFocusRow}
        />
      </section>

      <footer className="meta num">
        {footerLines(res).map((line) => (
          <span key={line}>{line}</span>
        ))}
        {source === 'local' && (
          <span className="meta-local" title={notice ?? undefined}>
            Running on the built-in solver
          </span>
        )}
      </footer>
    </main>
  )
}

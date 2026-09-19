import { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react'
import BalanceChart from './components/BalanceChart'
import ErrorBoundary from './components/ErrorBoundary.tsx'
import ChatPanel from './components/ChatPanel'
import PrescriptionList from './components/PrescriptionList'
import Stats from './components/Stats'
import TopNav from './components/TopNav'
import VerdictBand from './components/VerdictBand'
import { SCENARIOS } from './fixtures/scenarios'
import { solveViaApi } from './lib/api'
import { money, shortDate } from './lib/format'
import { emptyPlanText, footerLines, narrateChart } from './lib/narrate'
import type { Overrides } from './lib/overrides'
import { NONE, count, fromIds, toLocks, toggle } from './lib/overrides'
import { armOnToggle, decideRestore, domId, sameInputs } from './lib/focus'
import { useDebounced } from './lib/useDebounced'
import { solve } from './solver/mockSolver'
import type { SolveRequest, SolveResponse } from './types'

// Lazily loaded, so the wallet and its fixtures never enter the main chunk.
// The planning demo is what is being judged; it must not carry the weight of a
// side screen, and `npm run build` reports the two chunks separately so the
// main one can be watched.
const WalletView = lazy(() => import('./wallet/WalletView.tsx'))

const BASE = SCENARIOS[0].request

export default function App() {
  const [tab, setTab] = useState<'plan' | 'wallet'>('plan')
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
  // The whole request the displayed answer came from, not just its overrides: a
  // slider still moving means the answer on screen is not the one being waited
  // for, even though the checkboxes match.
  const [solvedRequest, setSolvedRequest] = useState<SolveRequest | null>(null)
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
      setSolvedRequest(debounced)
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
      // Nothing else is in flight: what is on screen answers exactly what the
      // user is asking now, sliders included.
      settled: solvedRequest !== null && sameInputs(solvedRequest, request),
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
  // True when what is on screen answers exactly what is being asked right now.
  // While it is false a slider is still moving or a solve is in flight, and the
  // panels dim to say so.
  const settled = solvedRequest !== null && sameInputs(solvedRequest, request)

  return (
    <div className="app">
      <TopNav tab={tab} onTab={setTab} res={res} source={source} notice={notice} />

      <main className={`main${settled ? '' : ' is-solving'}`}>
        {tab === 'wallet' ? (
          // Its OWN boundary, not the root one. A lazy chunk that fails to load
          // throws into the nearest boundary, and if that were the root the whole
          // planning demo would be replaced by a crash card over a side screen
          // the judge was not even looking at.
          <ErrorBoundary
            inline={(detail) => (
              <section className="wallet-down" role="alert">
                <h2>The demo wallet did not load</h2>
                <p>The checking account view is unaffected — switch back to it.</p>
                <details>
                  <summary>What went wrong</summary>
                  <p className="crash-detail">{detail}</p>
                </details>
              </section>
            )}
          >
            <Suspense fallback={<p className="wallet-loading">Loading the demo wallet…</p>}>
              <WalletView />
            </Suspense>
          </ErrorBoundary>
        ) : (
          <>
            {/* The one card that lifts off the gradient: the verdict on the
                left, the figures it is made of on the right. Keyed on the tier
                so a verdict that reverses meaning fades in rather than
                swapping under the eye. */}
            <section className="hero" key={`tier-${res.tier}`}>
              <div className="hero-copy">
                <VerdictBand res={res} req={request} />
              </div>
              <Stats res={res} />
            </section>

            <div className="duo">
              <section className="panel chart-panel">
                <div className="panel-head">
                  <div>
                    <p className="panel-kicker">
                      Daily balance · {shortDate(request.as_of)} to {shortDate(request.horizon_end)}
                    </p>
                    <h2>Where the money actually goes</h2>
                  </div>
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

              <section className="panel controls-panel" aria-label="What if">
                <div className="panel-head">
                  <div>
                    <p className="panel-kicker">What if</p>
                    <h2>Move the inputs</h2>
                  </div>
                </div>

                {/* One scenario control, not two. The presets that used to sit
                    under the balance slider said the same thing as this. */}
                <div className="switcher" role="group" aria-label="Starting position">
                  {SCENARIOS.map((s) => (
                    <button
                      key={s.key}
                      type="button"
                      title={s.blurb}
                      aria-pressed={
                        s.request.opening_balance_cents === opening &&
                        s.request.buffer_cents === buffer
                      }
                      onClick={() =>
                        preset(s.request.opening_balance_cents, s.request.buffer_cents)
                      }
                    >
                      {money(s.request.opening_balance_cents)}
                    </button>
                  ))}
                </div>

                <div className="controls">
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
                    <span className="ctl-note">What is in the account this morning.</span>
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
                </div>
              </section>
            </div>

            <div className="duo duo-start">
              <section className="panel rx-panel">
                <div className="panel-head">
                  <div>
                    <p className="panel-kicker">The plan</p>
                    <h2>
                      {res.plan.length === 0
                        ? emptyPlanText(res).heading
                        : `${res.plan.length} change${res.plan.length === 1 ? '' : 's'}, in the order they take effect`}
                    </h2>
                  </div>
                  {locked > 0 && (
                    <div className="panel-actions">
                      <button type="button" className="reset" onClick={() => setRuledOut(NONE)}>
                        Clear {locked} override{locked === 1 ? '' : 's'}
                      </button>
                    </div>
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

              <ChatPanel req={request} res={res} source={source} />
            </div>
          </>
        )}

        <footer className="meta">
          {footerLines(res).map((line) => (
            <span key={line}>{line}</span>
          ))}
        </footer>
      </main>
    </div>
  )
}

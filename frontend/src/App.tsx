import { useEffect, useMemo, useReducer, useRef, useState } from 'react'
import BalanceChart from './components/BalanceChart'
import ChatPanel from './components/ChatPanel'
import PrescriptionList from './components/PrescriptionList'
import Stats from './components/Stats'
import TopNav from './components/TopNav'
import VerdictBand from './components/VerdictBand'
import { SCENARIOS } from './fixtures/scenarios'
import { solveViaApi } from './lib/api'
import { chatKey, loadAccount, provenanceLine, sliderBounds } from './lib/accounts.ts'
import type { LoadKind } from './lib/accountState.ts'
import { accountReducer, fail, initial, preset as presetAction, start, succeed } from './lib/accountState.ts'
import { money, shortDate } from './lib/format'
import { emptyPlanText, footerLines, narrateChart } from './lib/narrate'
import type { Overrides } from './lib/overrides'
import { NONE, count, fromIds, toLocks, toggle } from './lib/overrides'
import { armOnToggle, decideRestore, domId, sameInputs } from './lib/focus'
import type { Tab } from './lib/tabs.ts'
import { DEFAULT_TAB, isPlanVisible } from './lib/tabs.ts'
import { decideConsidered } from './lib/considered.ts'
import { useDebounced } from './lib/useDebounced'
import { solve } from './solver/mockSolver'
import type { SolveRequest, SolveResponse } from './types'

const FIXTURE = SCENARIOS[0].request

export default function App() {
  const [tab, setTab] = useState<Tab>(DEFAULT_TAB)
  const planVisible = isPlanVisible(tab)
  // Whether the left-out list is expanded. It lives here, not in
  // PrescriptionList, for two reasons: the planning view unmounts on the Ask
  // tab, so component state would reset to collapsed and the row the reader
  // just ruled out would vanish again; and the reset paths that collapse it
  // are here.
  const [consideredOpen, setConsideredOpen] = useState(false)
  // The account the request is built from. A preset restores the fixture; the
  // two source buttons replace it wholesale. The lifecycle lives in a reducer
  // because the ways it goes wrong are about ordering, not rendering.
  const [acct, dispatch] = useReducer(accountReducer, FIXTURE, initial)
  const { account, base, loading, error: loadError } = acct
  const seqRef = useRef(0)
  const loadCtl = useRef<AbortController | null>(null)
  const [opening, setOpening] = useState(FIXTURE.opening_balance_cents)
  const [buffer, setBuffer] = useState(FIXTURE.buffer_cents)
  const [ruledOut, setRuledOut] = useState<Overrides>(NONE)
  const [newIds, setNewIds] = useState<string[]>([])
  const previousPlan = useRef<string[]>([])

  const request = useMemo(
    () => ({
      ...base,
      opening_balance_cents: opening,
      buffer_cents: buffer,
      locks: toLocks(ruledOut),
    }),
    [base, opening, buffer, ruledOut],
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

  // The solve effect is keyed on the request alone and must stay that way, so
  // its closure cannot see a tab switch that happened after it ran. This ref
  // is how `apply` above learns which tab is showing when a response actually
  // lands.
  const planVisibleRef = useRef(planVisible)
  useEffect(() => {
    planVisibleRef.current = planVisible
  }, [planVisible])

  // Leaving the plan tab retires the "new row" highlight.
  //
  // Suppressing it inside `apply` covers only responses that LAND while the
  // plan is hidden. The ordinary path is the other one: the reader ticks a
  // row, the answer arrives while they are watching, the highlight plays out,
  // and `newIds` then just sits there. Switching to Ask unmounts the list;
  // coming back mounts it again with those ids still set, and a 900ms
  // animation re-announces rows as new that the reader watched arrive minutes
  // ago. The highlight has done its job by then, so drop it on the way out.
  useEffect(() => {
    if (!planVisible) setNewIds([])
  }, [planVisible])

  // Open the left-out list when a change moves into it, close it when the
  // reader is back to no overrides. The rule is a transition rather than
  // `count > 0` so that collapsing the list by hand is not undone by the next
  // unrelated re-solve.
  const prevOverrides = useRef(0)
  useEffect(() => {
    const next = count(ruledOut)
    const action = decideConsidered(prevOverrides.current, next)
    prevOverrides.current = next
    if (action === 'open') setConsideredOpen(true)
    else if (action === 'close') setConsideredOpen(false)
  }, [ruledOut])

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
      // The "new row" highlight is a 900ms animation, so it only means
      // anything to someone who is looking at the list. The solve effect keeps
      // running on the Ask tab, so a response landing there would arm the
      // highlight for rows the reader never saw leave, and they would all
      // flash as new on the way back. Read through a ref: this closure was
      // made when the effect last ran and would otherwise hold a stale tab.
      setNewIds(
        planVisibleRef.current
          ? next.plan.map((p) => p.candidate_id).filter((id) => !before.includes(id))
          : [],
      )
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
        // The local solver is exhaustive and refuses above 20 free changes.
        // Throwing here would be a rejection inside a .catch: no state update,
        // no notice, and the previous account's plan left on screen looking
        // like this one's. Say something instead.
        try {
          apply(
            solve(debounced, before),
            'local',
            err instanceof Error ? err.message : 'Solver unreachable.',
          )
        } catch (offline: unknown) {
          if (mine !== seq.current) return
          setSource('local')
          setNotice(
            offline instanceof Error ? offline.message : 'Could not work that out offline.',
          )
        }
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
      // On the Ask tab the plan list is unmounted, so there is no checkbox to
      // focus. The guard also stops the remembered row being discarded on the
      // way past, which is what used to happen.
      planVisible,
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

  // Everything a change of account has to reset. Shared by the presets and the
  // two source buttons so neither can drift from the other.
  function adopt(next: SolveRequest, cents: number, cushion: number) {
    setOpening(cents)
    setBuffer(cushion)
    setRuledOut(NONE)
    // Explicit, because the transition rule cannot express this one: a reader
    // who opened the list by hand with no overrides produces 0 -> 0 here,
    // which is "leave", and the list would stay open into a fresh account.
    setConsideredOpen(false)
    previousPlan.current = []
    // Invalidate any solve still in flight for the previous account: its answer
    // would otherwise land on these rows and look like an answer about them.
    seq.current++
    setSolvedRequest(null)
    setSolvedRuledOut(NONE)
    setNewIds([])
    // Forget the remembered row too. It belongs to a plan the reader is no
    // longer looking at, and on a change of account its id may not even exist.
    // Leaving it set is not harmless: when the next answer lands, the restore
    // effect finds that row in the left-out list, opens the section
    // imperatively to focus it, and the resulting toggle writes `open` back to
    // true — quietly undoing the collapse three lines above.
    focused.current = null
    try {
      setRes(solve({ ...next, opening_balance_cents: cents, buffer_cents: cushion }, []))
    } catch {
      // Too many changes for the exhaustive stand-in; the effect will answer.
    }
  }

  function preset(cents: number, cushion: number) {
    loadCtl.current?.abort()
    // Bump the token too, not just the reducer's. The abort above is what
    // stops an in-flight load today, and an abort is not guaranteed to win a
    // race with a response already in flight: without this, the reducer would
    // reject the stale result while `adopt` below still wrote its balances,
    // putting a sandbox account's numbers under a line saying "Sample
    // checking account".
    seqRef.current++
    dispatch(presetAction(FIXTURE))
    adopt(FIXTURE, cents, cushion)
  }

  async function load(kind: LoadKind) {
    loadCtl.current?.abort()
    const ctl = new AbortController()
    loadCtl.current = ctl
    // One counter, handed to the reducer, so the two can never drift.
    const mine = ++seqRef.current
    dispatch(start(kind, mine))
    try {
      const loaded = await loadAccount(kind, ctl.signal)
      if (mine !== seqRef.current) return
      dispatch(succeed(mine, loaded.account, loaded.base))
      adopt(loaded.base, loaded.base.opening_balance_cents, loaded.base.buffer_cents)
    } catch (e: unknown) {
      if (ctl.signal.aborted || mine !== seqRef.current) return
      dispatch(fail(mine, e instanceof Error ? e.message : 'Could not load that account.'))
    }
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
        {/* The planning view is a conditional render, not a hidden one. Two
            reasons, both deliberate: the chart's ResponsiveContainer sizes
            itself from its parent, and a parent inside `display: none` is
            0x0, so hiding it would leave the chart depending on a resize
            observer firing correctly on reveal; and a hidden checkbox cannot
            take focus, which would make the restore effect look like it
            worked when it had not. Everything it owns that must outlive a tab
            switch — the overrides, the remembered row, whether the left-out
            list is open — is state up here, not in the subtree. */}
        {planVisible && (
          <>
            {/* The one card that lifts off the gradient: the verdict on the
                left, the figures it is made of on the right. Keyed on the tier
                so a verdict that reverses meaning fades in rather than
                swapping under the eye. */}
            <section className="hero" key={`tier-${res.tier}`}>
              <div className="hero-copy">
                {/* Where the numbers come from. Deliberately a sibling ABOVE
                    the verdict rather than inside it: the verdict is an
                    aria-live region, and provenance does not change on a
                    re-solve, so announcing it again on every slider move
                    would be noise. */}
                <p className="eyebrow-note">{provenanceLine(account, base)}</p>
                <VerdictBand res={res} req={request} />
              </div>
              <Stats res={res} />
            </section>

            <div className="duo">
              <section className="panel chart-panel">
                <div className="panel-head">
                  <div>
                    <p className="panel-kicker">
                      Daily balance · {shortDate(base.as_of)} to {shortDate(base.horizon_end)}
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
                    {/* The clause the old tagline carried. It belongs next to
                        the controls it describes, not over the verdict. */}
                    <p className="panel-lede">
                      Move a slider or rule a change out, and the plan is re-solved from scratch.
                    </p>
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
                        account === null &&
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

                <span className="ctl-presets ctl-sources">
                  <button
                    type="button"
                    title="Generate a fresh account on the server"
                    aria-pressed={account?.source === 'modelled'}
                    disabled={loading !== null}
                    onClick={() => void load('modelled')}
                  >
                    {loading === 'modelled' ? 'Loading…' : 'New modelled account'}
                  </button>
                  <button
                    type="button"
                    title="Seed an account into Capital One's Nessie sandbox and read it back"
                    aria-pressed={account?.source === 'nessie'}
                    disabled={loading !== null}
                    onClick={() => void load('nessie')}
                  >
                    {loading === 'nessie' ? 'Loading…' : 'Capital One sandbox'}
                  </button>
                </span>
                {loadError && (
                  <p className="ctl-note" role="status">
                    {loadError}
                  </p>
                )}

                <div className="controls">
                  <label className="ctl">
                    <span className="ctl-head">
                      Starting balance
                      <b className="num">{money(opening)}</b>
                    </span>
                    <input
                      type="range"
                      min={sliderBounds(opening).min}
                      max={sliderBounds(opening).max}
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
                      <button
                        type="button"
                        className="reset"
                        onClick={() => {
                          setRuledOut(NONE)
                          setConsideredOpen(false)
                        }}
                      >
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
                consideredOpen={consideredOpen}
                onConsideredToggle={setConsideredOpen}
              />
            </section>
          </>
        )}

        {/* The explainer is the one panel that must never unmount: it holds
            the conversation, an unsent draft and an in-flight request, and
            losing a judge's thread because they looked at the plan would be
            worse than the tab is worth. The wrapper is what carries `hidden`
            — the panel's own root is a `.panel`, and this stylesheet gives
            that `display: flex`, which would beat the browser's rule for the
            attribute and leave the whole thing on screen. */}
        <div hidden={tab !== 'ask'}>
          <ChatPanel
            key={chatKey(account)}
            req={request}
            res={res}
            source={source}
            accountSource={account?.source ?? 'preset'}
            visible={tab === 'ask'}
          />
        </div>

        <footer className="meta">
          {footerLines(res).map((line) => (
            <span key={line}>{line}</span>
          ))}
        </footer>
      </main>
    </div>
  )
}

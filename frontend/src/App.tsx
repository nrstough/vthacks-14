import { Suspense, lazy, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import BalanceChart from './components/BalanceChart'
import ErrorBoundary from './components/ErrorBoundary.tsx'
import ChatPanel from './components/ChatPanel'
import PrescriptionList from './components/PrescriptionList'
import Stats from './components/Stats'
import TopNav from './components/TopNav'
import VerdictBand from './components/VerdictBand'
import { SCENARIOS } from './fixtures/scenarios'
import { solveViaApi } from './lib/api'
import { chatKey, loadAccount, loadImport, provenanceLine, sliderBounds } from './lib/accounts.ts'
import type { LoadKind } from './lib/accountState.ts'
import {
  accountReducer,
  fail,
  initial,
  preset as presetAction,
  start,
  streams as streamsAction,
  succeed,
} from './lib/accountState.ts'
import ProvenancePanel from './components/ProvenancePanel.tsx'
import { parseAmountCents, parseBankCsv } from './lib/importCsv.ts'
import {
  buildImportRequest,
  isImport,
  qualifierNote,
  scheduleAfterUntick,
  toBase as importToBase,
} from './lib/history.ts'
import { money, shortDate } from './lib/format'
import { emptyPlanText, footerLines, narrateChart } from './lib/narrate'
import type { Overrides } from './lib/overrides'
import { NONE, allow, count, fromIds, ruleOut, toLocks, toggle } from './lib/overrides'
import type { Resolved } from './lib/suggestions'
import { clampCushion, clampOpening } from './lib/suggestions'
import { armOnToggle, decideRestore, domId, sameInputs } from './lib/focus'
import { useDebounced } from './lib/useDebounced'
import { solve } from './solver/mockSolver'
import type { SolveRequest, SolveResponse } from './types'

// Lazily loaded, so the wallet and its fixtures never enter the main chunk.
// The planning demo is what is being judged; it must not carry the weight of a
// side screen, and `npm run build` reports the two chunks separately so the
// main one can be watched.
const WalletView = lazy(() => import('./wallet/WalletView.tsx'))

const FIXTURE = SCENARIOS[0].request

// What each parser rejection means, in words. The codes never carry the
// cell, so neither does this.
const REJECT_TEXT: Record<string, string> = {
  no_date: 'no date',
  bad_date: 'the date could not be read',
  no_amount: 'no amount',
  bad_amount: 'the amount could not be read',
  too_many_decimals: 'more than two decimal places',
  zero_amount: 'an amount of zero',
  no_description: 'no description',
  not_posted: 'not yet posted',
}

// The balance the person types. Same string arithmetic as the CSV parser,
// for the same reason: no float ever touches money here.
function parseBalance(raw: string): number | null {
  const cents = parseAmountCents(raw)
  return typeof cents === 'number' ? cents : null
}

export default function App() {
  const [tab, setTab] = useState<'plan' | 'wallet'>('plan')
  // The account the request is built from. A preset restores the fixture; the
  // two source buttons replace it wholesale. The lifecycle lives in a reducer
  // because the ways it goes wrong are about ordering, not rendering.
  const [acct, dispatch] = useReducer(accountReducer, FIXTURE, initial)
  const { account, base, loading, error: loadError, original, excluded } = acct
  // The parsed rows stay in the browser so a re-import needs no second file
  // read. They are NOT used for labelling: the server's labels are already
  // brand-free, and labelling again here would add a second place a payee
  // could reach the screen.
  const importedRows = useRef<ReturnType<typeof parseBankCsv>['rows']>([])
  const importSeq = useRef(0)
  const [importBalance, setImportBalance] = useState('')
  const [pendingFile, setPendingFile] = useState<string | null>(null)
  const [importNote, setImportNote] = useState<string | null>(null)
  const [rejected, setRejected] = useState<string[]>([])
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

  // An approved offer. Directional, never `toggle`: the offer names the state
  // it wants, so approving "rule this out" for a row already ruled out by hand
  // has to leave it ruled out rather than flip it back.
  //
  // The focus machinery is deliberately not touched. It exists to put focus
  // back on a row that a re-solve unmounted, and a tap in the chat panel is not
  // on a row at all -- arming it here would hand the restore a bogus id.
  function applySuggestion(r: Resolved) {
    switch (r.kind) {
      case 'rule_out':
        setRuledOut((prev) => ruleOut(prev, r.id))
        break
      case 'allow':
        setRuledOut((prev) => allow(prev, r.id))
        break
      case 'opening':
        // Functional, and re-clamped against the value at apply time: the
        // opening slider's bounds are computed from the current opening, so a
        // value clamped at render is only right if nothing moved since.
        setOpening((prev) => clampOpening(r.cents, prev))
        break
      case 'cushion':
        setBuffer(clampCushion(r.cents))
        break
    }
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
    previousPlan.current = []
    // Invalidate any solve still in flight for the previous account: its answer
    // would otherwise land on these rows and look like an answer about them.
    seq.current++
    setSolvedRequest(null)
    setSolvedRuledOut(NONE)
    setNewIds([])
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
      const loaded = await loadAccount(kind === 'nessie' ? 'nessie' : 'modelled', ctl.signal)
      if (mine !== seqRef.current) return
      dispatch(succeed(mine, loaded.account, loaded.base))
      adopt(loaded.base, loaded.base.opening_balance_cents, loaded.base.buffer_cents)
    } catch (e: unknown) {
      if (ctl.signal.aborted || mine !== seqRef.current) return
      dispatch(fail(mine, e instanceof Error ? e.message : 'Could not load that account.'))
    }
  }

  async function runImport(cents: number) {
    loadCtl.current?.abort()
    const ctl = new AbortController()
    loadCtl.current = ctl
    // The same single counter the other two sources use, so a preset click
    // during a slow import still wins the race.
    const mine = ++seqRef.current
    dispatch(start('import', mine))
    try {
      const body = buildImportRequest(importedRows.current, cents, buffer)
      const account = await loadImport(body, ctl.signal)
      if (mine !== seqRef.current) return
      importSeq.current++
      const next = importToBase(account)
      dispatch(succeed(mine, account, next))
      adopt(next, next.opening_balance_cents, next.buffer_cents)
    } catch (e: unknown) {
      if (ctl.signal.aborted || mine !== seqRef.current) return
      dispatch(fail(mine, e instanceof Error ? e.message : 'Could not import that export.'))
    }
  }

  async function chooseFile(file: File | null) {
    if (!file) return
    setImportNote(null)
    const parsed = parseBankCsv(await file.text())
    const detail = parsed.rejected.map((r) => `line ${r.line}: ${REJECT_TEXT[r.reason]}`)
    if (parsed.error !== null) {
      importedRows.current = []
      setPendingFile(null)
      // The refusal does not erase the per-row reasons; they are how the
      // person finds the line their bank wrote oddly.
      setRejected(detail)
      setImportNote(parsed.error)
      return
    }
    importedRows.current = parsed.rows
    const skipped = [
      parsed.notPosted > 0 ? `${parsed.notPosted} not yet posted` : null,
      parsed.rejected.length > 0 ? `${parsed.rejected.length} unreadable` : null,
    ].filter(Boolean)
    setPendingFile(
      `${parsed.rows.length} transactions read` + (skipped.length ? `, ${skipped.join(', ')} skipped` : ''),
    )
    setRejected(detail)
    setImportNote(null)
  }

  function toggleStream(streamId: string) {
    if (original === null) return
    const next = new Set(excluded)
    if (next.has(streamId)) next.delete(streamId)
    else next.add(streamId)
    const rebuilt = scheduleAfterUntick(original, next, opening, buffer)
    dispatch(streamsAction(next, rebuilt))
    adopt(rebuilt, opening, buffer)
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
                {/* Where the numbers come from. Deliberately a sibling ABOVE
                    the verdict rather than inside it: the verdict is an
                    aria-live region, and provenance does not change on a
                    re-solve, so announcing it again on every slider move
                    would be noise. */}
                <p className="eyebrow-note">{provenanceLine(account, base)}</p>
                <VerdictBand res={res} req={request} note={qualifierNote(account)} />
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

              {isImport(account) && (
                <ProvenancePanel account={account} excluded={excluded} onToggle={toggleStream} />
              )}

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
                  <label
                    className="ctl-file"
                    title="Plan from your own bank export. Nothing is stored; merchant names are used to group the rows and are never returned."
                  >
                    <input
                      type="file"
                      accept=".csv,text/csv"
                      disabled={loading !== null}
                      onChange={(e) => {
                        void chooseFile(e.target.files?.[0] ?? null)
                        e.target.value = ''
                      }}
                    />
                    <span>Import a bank export</span>
                  </label>
                </span>
                {pendingFile && (
                  <span className="ctl-import">
                    <span className="ctl-note">{pendingFile}. Today's balance:</span>
                    <input
                      className="num"
                      type="text"
                      inputMode="decimal"
                      placeholder="412.80"
                      value={importBalance}
                      aria-label="Your balance today, including anything that posted today"
                      onChange={(e) => setImportBalance(e.target.value)}
                    />
                    <button
                      type="button"
                      disabled={loading !== null || parseBalance(importBalance) === null}
                      onClick={() => {
                        const cents = parseBalance(importBalance)
                        if (cents !== null) void runImport(cents)
                      }}
                    >
                      {loading === 'import' ? 'Planning…' : 'Plan from this'}
                    </button>
                  </span>
                )}
                {importNote && (
                  <p className="ctl-note" role="status">
                    {importNote}
                  </p>
                )}
                {rejected.length > 0 && (
                  <details className="ctl-note import-rejects">
                    <summary>
                      {rejected.length} {rejected.length === 1 ? 'row was' : 'rows were'} skipped
                    </summary>
                    <ul>
                      {rejected.slice(0, 20).map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                      {rejected.length > 20 && <li>and {rejected.length - 20} more</li>}
                    </ul>
                  </details>
                )}
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

              <ChatPanel
                key={chatKey(account, importSeq.current)}
                req={request}
                res={res}
                source={source}
                accountSource={account?.source ?? 'preset'}
                generation={seq.current}
                onApply={applySuggestion}
              />
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

import { useEffect, useMemo, useRef, useState } from 'react'
import { askViaApi, chatStatus } from '../lib/chat'
import type { ChatTurn, Suggestion } from '../lib/chat'
import type { Resolved } from '../lib/suggestions'
import { keyOf, labelFor, resolve } from '../lib/suggestions'
import type { AccountSource, SolveRequest, SolveResponse } from '../types'

// Questions a first-time viewer, or a judge, actually asks. Each one is
// answerable from the context the server renders, so none tempts the model
// into arithmetic.
const STARTERS = [
  'Why these changes and not others?',
  'Explain the proof in plain words.',
  'What if my paycheck comes late?',
  'How is the plan computed?',
]

// The panel explains the solve on screen. Numbers come from the solver in
// `res`; the model only puts words to them, and the note under the input says
// so. When no key is configured the server answers 503 and the panel says the
// explainer is off rather than hiding, so the layout does not jump.
export default function ChatPanel({
  req,
  res,
  source,
  accountSource = 'preset',
  generation = 0,
  onApply,
}: {
  req: SolveRequest
  res: SolveResponse
  source: 'local' | 'server'
  accountSource?: AccountSource
  // Bumped whenever the account underneath changes. Offers earned against the
  // old one are cleared, and a reply already in flight when it changed is
  // dropped rather than allowed to repopulate them.
  generation?: number
  onApply?: (r: Resolved) => void
}) {
  const [messages, setMessages] = useState<ChatTurn[]>([])
  // Beside `messages`, not inside it: ChatTurn is also the wire payload and the
  // server forbids unknown fields, so a field added here would 422 the next
  // request. Keyed by message index, which is safe because the array is
  // append-only within a mount.
  const [offers, setOffers] = useState<Record<number, Suggestion[]>>({})
  const [applied, setApplied] = useState<ReadonlySet<string>>(new Set())
  // Clearing on a generation change happens here, during render, rather than
  // in an effect: React's own pattern for resetting state when a prop changes,
  // and it avoids the cascading extra render an effect would cause.
  const [seenGeneration, setSeenGeneration] = useState(generation)
  if (seenGeneration !== generation) {
    setSeenGeneration(generation)
    setOffers({})
    setApplied(new Set())
  }
  // The live generation, readable from inside an in-flight closure. Comparing
  // the prop against itself would compare two values from the same render and
  // never differ, which is the quiet way this guard fails to guard.
  const genNow = useRef(generation)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [state, setState] = useState<'checking' | 'ready' | 'off' | 'unreachable'>('checking')
  const [model, setModel] = useState<string | null>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const inFlight = useRef<AbortController | null>(null)

  useEffect(() => {
    const ctl = new AbortController()
    chatStatus(ctl.signal)
      .then((s) => {
        setState(s.configured ? 'ready' : 'off')
        setModel(s.model)
      })
      .catch(() => {
        if (!ctl.signal.aborted) setState('unreachable')
      })
    return () => ctl.abort()
  }, [])

  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, pending])

  async function send(text: string) {
    const q = text.trim()
    if (!q || pending || state !== 'ready') return
    inFlight.current?.abort()
    const ctl = new AbortController()
    inFlight.current = ctl

    const next: ChatTurn[] = [...messages, { role: 'user', text: q }]
    setMessages(next)
    setDraft('')
    setError(null)
    setPending(true)
    try {
      // The solve on screen at the moment of asking is what the answer is
      // about, which is why req and res go with every question.
      const sentAt = generation
      const { reply, suggestions } = await askViaApi(
        next,
        req,
        res,
        source,
        ctl.signal,
        accountSource,
      )
      if (ctl.signal.aborted) return
      // The account can change while a reply is in the air. Clearing offers on
      // a generation change only removes the ones already here; a reply that
      // left before the change would land after it and put them back.
      if (sentAt !== genNow.current) return
      setMessages([...next, { role: 'assistant', text: reply }])
      if (suggestions.length) {
        setOffers((prev) => ({ ...prev, [next.length]: suggestions }))
      }
    } catch (e) {
      if (ctl.signal.aborted) return
      setError(e instanceof Error ? e.message : 'The explainer failed.')
      // Put the question back in the box, not the log: one click on Ask
      // resends it, and the log never shows a question with no answer.
      setMessages(messages)
      setDraft(q)
    } finally {
      if (!ctl.signal.aborted) setPending(false)
    }
  }

  // Offers describe a plan that no longer exists once the account changes
  // underneath them, and the ids may not even be in the new candidate set. The
  // clearing is done above, during render; what is left here is the half that
  // genuinely belongs in an effect — abandoning a reply that is still in the
  // air, which would otherwise land after the change and put offers back.
  useEffect(() => {
    genNow.current = generation
    if (inFlight.current) {
      inFlight.current.abort()
      inFlight.current = null
      // And release the input. `send`'s own finally deliberately leaves
      // `pending` alone when the request was aborted, because an abort there
      // always came from a newer send that had just set it. This abort has no
      // newer send behind it, so nothing would ever clear it: the box and the
      // Ask button would stay disabled for the rest of the session. A stale
      // completion cannot undo this, since its finally still sees an aborted
      // signal and returns.
      setPending(false)
    }
  }, [generation])

  // The LIVE candidate ids, rebuilt whenever the request changes. An offer is
  // re-checked against these at render and at tap, not against the set it was
  // earned against.
  const known = useMemo(() => new Set(req.candidates.map((c) => c.id)), [req.candidates])

  const nameOf = (id: string) =>
    req.candidates.find((c) => c.id === id)?.label ?? 'that change'

  // Resolved again at tap rather than trusting the value computed for the
  // label. In practice the two agree: the handler is a fresh closure from the
  // latest committed render, over the same `req` and `known` that produced the
  // label, and `resolve` is pure. An account change would have cleared these
  // offers during that same render, so there is no window in which this
  // disagrees — it is defence, not a live guard, and saying otherwise would be
  // the same overstatement the finishReason note already was.
  function approve(key: string, s: Suggestion) {
    if (applied.has(key)) return
    const r = resolve(s, req.opening_balance_cents, known)
    if (!r) return
    setApplied((prev) => new Set(prev).add(key))
    onApply?.(r)
  }

  const disabled = state !== 'ready' || pending

  return (
    <section className="panel chat-panel" aria-label="Ask about this plan">
      <div className="panel-head">
        <div>
          <p className="panel-kicker">Explainer</p>
          <h2>Ask about this plan</h2>
        </div>
        {state === 'off' && <span className="panel-tag warn">Explainer off: no Gemini key</span>}
        {state === 'unreachable' && <span className="panel-tag warn">Explainer unreachable</span>}
        {state === 'ready' && model && <span className="panel-tag">Gemini · {model}</span>}
      </div>

      <div className="chat-log" ref={logRef} role="log" aria-live="polite">
        {messages.length === 0 && (
          <p className="chat-empty">
            Ask why a change is in the plan, what the proof means, or how it is built. Answers are
            about the plan on screen when you ask.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role === 'user' ? 'msg-user' : 'msg-bot'}`}>
            {m.text}
            {(offers[i] ?? []).map((s, j) => {
              const r = resolve(s, req.opening_balance_cents, known)
              if (!r) return null
              const key = keyOf(i, j)
              const done = applied.has(key)
              const text = labelFor(r, nameOf)
              return (
                <button
                  key={key}
                  type="button"
                  className="chat-apply"
                  disabled={done}
                  aria-label={done ? `Applied: ${text}` : `Apply: ${text}`}
                  onClick={() => approve(key, s)}
                >
                  {done ? `Applied — ${text}` : text}
                </button>
              )
            })}
          </div>
        ))}
        {pending && (
          <div className="msg msg-bot msg-pending" aria-label="Thinking">
            <span />
            <span />
            <span />
          </div>
        )}
        {error && <p className="chat-error">{error}</p>}
      </div>

      {messages.length === 0 && (
        <div className="chips">
          {STARTERS.map((s) => (
            <button key={s} type="button" disabled={disabled} onClick={() => send(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault()
          send(draft)
        }}
      >
        <input
          type="text"
          value={draft}
          placeholder={state === 'ready' ? 'Ask a question about this plan' : 'The explainer is not available'}
          disabled={disabled}
          maxLength={4000}
          aria-label="Your question"
          onChange={(e) => setDraft(e.target.value)}
          // Implicit form submission on Enter is the browser's job, but it is
          // the one interaction a judge will try first, so it is also ours.
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send(draft)
            }
          }}
        />
        <button type="submit" disabled={disabled || !draft.trim()}>
          Ask
        </button>
      </form>
      <p className="chat-note">
        Every number comes from the solver. Gemini only puts words to them. It can offer to change
        what the solver is asked, and nothing moves until you tap it.
      </p>
    </section>
  )
}

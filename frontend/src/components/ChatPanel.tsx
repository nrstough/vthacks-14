import { useEffect, useRef, useState } from 'react'
import { askViaApi, chatStatus } from '../lib/chat'
import type { ChatTurn } from '../lib/chat'
import type { SolveRequest, SolveResponse } from '../types'

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
}: {
  req: SolveRequest
  res: SolveResponse
  source: 'local' | 'server'
}) {
  const [messages, setMessages] = useState<ChatTurn[]>([])
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
      const { reply } = await askViaApi(next, req, res, source, ctl.signal)
      if (ctl.signal.aborted) return
      setMessages([...next, { role: 'assistant', text: reply }])
    } catch (e) {
      if (ctl.signal.aborted) return
      setError(e instanceof Error ? e.message : 'The explainer failed.')
      // Leave the question in the log so it can be retried by resending.
    } finally {
      if (!ctl.signal.aborted) setPending(false)
    }
  }

  const disabled = state !== 'ready' || pending

  return (
    <section className="band chat" aria-label="Ask about this plan">
      <div className="band-head">
        <h2>Ask about this plan</h2>
        {state === 'off' && <span className="chat-off">Explainer off: no Gemini key on the server</span>}
        {state === 'unreachable' && <span className="chat-off">Explainer unreachable</span>}
        {state === 'ready' && model && <span className="chat-model num">Gemini · {model}</span>}
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
        />
        <button type="submit" disabled={disabled || !draft.trim()}>
          Ask
        </button>
      </form>
      <p className="chat-note">
        Every number comes from the solver. Gemini only puts words to it, and it can’t change the
        plan or act on your account.
      </p>
    </section>
  )
}

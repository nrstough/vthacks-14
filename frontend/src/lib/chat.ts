// Client for the plan explainer, POST /api/chat and GET /api/chat/status.
//
// Stateless on both sides: every call carries the whole conversation and the
// solve it is about. The server keeps nothing, so a reload starts fresh.

import type { AccountSource, SolveRequest, SolveResponse } from '../types'

export interface ChatTurn {
  role: 'user' | 'assistant'
  text: string
}

export interface ChatStatus {
  configured: boolean
  model: string | null
}

// An offer the model made about what the solver is asked. Never applied on
// arrival: it becomes a control, and a person taps it.
//
// A union of string literals rather than a TS enum, because tsconfig sets
// erasableSyntaxOnly and an enum emits runtime code.
export type SuggestionKind = 'rule_out' | 'allow' | 'opening' | 'cushion'

export interface Suggestion {
  kind: SuggestionKind
  candidate_id: string | null
  amount_cents: number | null
}

const KINDS: readonly string[] = ['rule_out', 'allow', 'opening', 'cushion']

// Mirrors MAX_SUGGESTIONS on the server. A response is not trusted to honour
// its own cap.
const MAX_SUGGESTIONS = 3

// The server validated these already. This is the second check, because the
// value crossing here ends up driving solver input, and `as` is a promise the
// compiler cannot keep: a field that arrives malformed is a runtime shape, not
// a type error. Anything that does not fit is dropped, never coerced.
export function readSuggestions(raw: unknown): Suggestion[] {
  if (!Array.isArray(raw)) return []
  const out: Suggestion[] = []
  for (const item of raw) {
    if (typeof item !== 'object' || item === null) continue
    const s = item as Record<string, unknown>
    if (typeof s.kind !== 'string' || !KINDS.includes(s.kind)) continue
    const id = s.candidate_id
    const cents = s.amount_cents
    const wantsId = s.kind === 'rule_out' || s.kind === 'allow'
    // Exactly one payload, matching the kind — the same invariant the server's
    // own validator enforces. Billing this as "the second check" while it was
    // weaker than the first was the point of having it at all.
    if (wantsId) {
      if (typeof id !== 'string' || !id) continue
      if (cents !== null && cents !== undefined) continue
      out.push({ kind: s.kind as SuggestionKind, candidate_id: id, amount_cents: null })
    } else {
      if (typeof cents !== 'number' || !Number.isSafeInteger(cents)) continue
      if (id !== null && id !== undefined) continue
      out.push({ kind: s.kind as SuggestionKind, candidate_id: null, amount_cents: cents })
    }
    if (out.length === MAX_SUGGESTIONS) break
  }
  return out
}

export class ChatError extends Error {
  status: number | undefined

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ChatError'
    this.status = status
  }
}

async function detailOf(r: Response): Promise<string> {
  try {
    const body = (await r.json()) as { detail?: unknown }
    return typeof body.detail === 'string' ? body.detail : ''
  } catch {
    return ''
  }
}

// The server limits this endpoint per address, because every call spends its
// Gemini key. A limit is not a crash: the panel says the explainer is resting
// and the plan on screen is untouched.
export const RESTING = 'The explainer is resting after a burst of questions.'

export function restingMessage(retryAfterSeconds: number | null): string {
  if (retryAfterSeconds === null || !Number.isFinite(retryAfterSeconds) || retryAfterSeconds <= 0) {
    return `${RESTING} Try again in a moment.`
  }
  const s = Math.ceil(retryAfterSeconds)
  return `${RESTING} Try again in ${s} second${s === 1 ? '' : 's'}.`
}

export function retryAfterOf(r: Response): number | null {
  const raw = r.headers.get('Retry-After')
  if (raw === null) return null
  const n = Number(raw.trim())
  return Number.isFinite(n) && n > 0 ? n : null
}

export async function chatStatus(signal: AbortSignal): Promise<ChatStatus> {
  const r = await fetch('/api/chat/status', { signal })
  if (!r.ok) throw new ChatError('Could not reach the explainer.', r.status)
  return (await r.json()) as ChatStatus
}

export async function askViaApi(
  messages: ChatTurn[],
  request: SolveRequest,
  response: SolveResponse,
  source: 'local' | 'server',
  signal: AbortSignal,
  // Appended last, with a default: a positional caller that predates account
  // loading keeps compiling and keeps meaning what it meant.
  accountSource: AccountSource = 'preset',
): Promise<{ reply: string; model: string; suggestions: Suggestion[] }> {
  let r: Response
  try {
    r = await fetch(`/api/chat?source=${source}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, request, response, account_source: accountSource }),
      signal,
    })
  } catch (e) {
    if (signal.aborted) throw e
    throw new ChatError('Could not reach the explainer.')
  }
  if (!r.ok) {
    // The wording here is ours, not the server's. A thrown message shown
    // verbatim is how banned wording reached the screen once already.
    if (r.status === 429) throw new ChatError(restingMessage(retryAfterOf(r)), 429)
    const detail = await detailOf(r)
    if (r.status === 503) throw new ChatError(detail || 'The explainer is off.', 503)
    if (r.status === 502) throw new ChatError(detail || 'Gemini did not answer.', 502)
    throw new ChatError(detail || `The explainer failed (${r.status}).`, r.status)
  }
  const payload = (await r.json()) as { reply: string; model: string; suggestions?: unknown }
  return {
    reply: payload.reply,
    model: payload.model,
    suggestions: readSuggestions(payload.suggestions),
  }
}

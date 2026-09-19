// Client for the plan explainer, POST /api/chat and GET /api/chat/status.
//
// Stateless on both sides: every call carries the whole conversation and the
// solve it is about. The server keeps nothing, so a reload starts fresh.

import type { SolveRequest, SolveResponse } from '../types'

export interface ChatTurn {
  role: 'user' | 'assistant'
  text: string
}

export interface ChatStatus {
  configured: boolean
  model: string | null
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
): Promise<{ reply: string; model: string }> {
  let r: Response
  try {
    r = await fetch(`/api/chat?source=${source}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, request, response }),
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
  return (await r.json()) as { reply: string; model: string }
}

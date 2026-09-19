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
    const detail = await detailOf(r)
    if (r.status === 503) throw new ChatError(detail || 'The explainer is off.', 503)
    if (r.status === 502) throw new ChatError(detail || 'Gemini did not answer.', 502)
    throw new ChatError(detail || `The explainer failed (${r.status}).`, r.status)
  }
  return (await r.json()) as { reply: string; model: string }
}

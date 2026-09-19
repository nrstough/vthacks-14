// Client for POST /api/solve.
//
// The URL is relative on purpose. In development Vite proxies /api to the
// backend port; in production FastAPI serves this bundle and the API from one
// origin. Same code either way, so there is no build-time switch to forget.

import type { SolveRequest, SolveResponse } from '../types'

// Plain field assignment, not a constructor parameter property: the project
// compiles with erasableSyntaxOnly, and Node's type stripping needs the same.
export class ApiError extends Error {
  status: number | undefined

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// A validation failure arrives as FastAPI's list of {loc, msg, ...}. Turn it
// into a sentence naming the field, rather than pasting raw JSON at the user.
export function describeDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (!Array.isArray(detail)) return ''
  return detail
    .map((d) => {
      const item = d as { loc?: unknown; msg?: unknown }
      const loc = Array.isArray(item.loc)
        ? item.loc.filter((x) => x !== 'body').join('.')
        : ''
      const msg = typeof item.msg === 'string' ? item.msg : 'is not valid'
      return loc ? `${loc} ${msg.charAt(0).toLowerCase()}${msg.slice(1)}` : msg
    })
    .join('; ')
}

export async function solveViaApi(
  request: SolveRequest,
  previousPlan: string[],
  signal: AbortSignal,
): Promise<SolveResponse> {
  let r: Response
  try {
    r = await fetch('/api/solve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...request, previous_plan: previousPlan }),
      signal,
    })
  } catch (e) {
    if (signal.aborted) throw e
    throw new ApiError('Could not reach the solver.')
  }

  if (!r.ok) {
    let detail = ''
    try {
      detail = describeDetail((await r.json())?.detail)
    } catch {
      /* body was not JSON; the status alone will have to do */
    }
    // A 4xx means the request was wrong. A 503 means the server declined to
    // answer at all, which it does rather than return an approximate plan.
    // Saying "rejected the request" for the second would blame the wrong side.
    let prefix: string
    if (r.status === 503) prefix = 'The solver declined to answer'
    else if (r.status >= 500) prefix = `The solver failed (${r.status})`
    else prefix = 'Solver rejected the request'

    throw new ApiError(detail ? `${prefix}: ${detail}` : `${prefix}.`, r.status)
  }

  return (await r.json()) as SolveResponse
}

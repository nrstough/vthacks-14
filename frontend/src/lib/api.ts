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
    // The backend answers a bad request with a field path. Surface it rather
    // than a bare status code, since it is the only clue to what went wrong.
    let detail = ''
    try {
      const body = await r.json()
      detail = typeof body?.detail === 'string' ? body.detail : JSON.stringify(body?.detail ?? '')
    } catch {
      /* body was not JSON; the status alone will have to do */
    }
    throw new ApiError(detail ? `Solver rejected the request: ${detail}` : `Solver returned ${r.status}.`, r.status)
  }

  return (await r.json()) as SolveResponse
}

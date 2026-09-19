// Loading an account from the server: a modelled one, or one seeded into
// Capital One's Nessie sandbox and read back.
//
// The pure parts are separated from the fetching parts on purpose. Everything
// that decides what the user reads — which fields go in a request, what the
// provenance sentence says — is a function of its arguments and is tested as
// one. Nothing in here renders.

import { ApiError, describeDetail } from './api.ts'
import { shortDate } from './format.ts'
import type {
  Candidate,
  CandidatesRequest,
  CandidatesResponse,
  LoadedAccount,
  NessieAccountResponse,
  SolveRequest,
} from '../types'

// The server's exhaustive engine refuses above 18 and the browser's stand-in
// above 20, so 18 is the largest set every fallback can still answer. Pinned
// explicitly rather than left to the server's default: if the local solver is
// handed more than 20 it throws, and it throws inside the solve effect's catch,
// where the page would silently keep the previous plan.
export const CANDIDATE_LIMIT = 18

export function toCandidatesRequest(account: LoadedAccount): CandidatesRequest {
  // Picked field by field. Spreading the account would carry `seed` and
  // `source`, and the endpoint forbids extras, so the whole call would 422.
  return {
    as_of: account.as_of,
    horizon_end: account.horizon_end,
    scheduled: account.scheduled,
    limit: CANDIDATE_LIMIT,
  }
}

export function toBase(account: LoadedAccount, candidates: Candidate[]): SolveRequest {
  return {
    as_of: account.as_of,
    horizon_end: account.horizon_end,
    opening_balance_cents: account.opening_balance_cents,
    buffer_cents: account.buffer_cents,
    scheduled: account.scheduled,
    candidates,
    // A fresh account has no overrides. Carrying them across would name
    // candidate ids this account has never heard of, which is a 422 on the
    // whole solve rather than a missing row.
    locks: { in: [], out: [] },
  }
}

export function parseAccount(body: unknown): LoadedAccount {
  const source = (body as { source?: unknown } | null)?.source
  if (source !== 'modelled' && source !== 'nessie') {
    // Provenance is required, not decoration. An account whose origin the page
    // cannot name is one it must not show.
    throw new ApiError('The server returned an account with no provenance.')
  }
  return body as LoadedAccount
}

function isNessie(account: LoadedAccount): account is NessieAccountResponse {
  return account.source === 'nessie'
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

// Reported in a fixed order so the sentence reads the same way every time, and
// counted by reason because "3 rows changed" would be false when one was
// dropped, one was undated and one was moved.
const REASON_TEXT: [NotRoundTrippedReason, string, string][] = [
  ['written but not returned', 'row not returned', 'rows not returned'],
  ['amount changed by the sandbox', 'amount changed by the sandbox', 'amounts changed by the sandbox'],
  ['no usable date', 'row without a date', 'rows without a date'],
  ['outside the window', 'row outside the window', 'rows outside the window'],
]

type NotRoundTrippedReason = NessieAccountResponse['not_round_tripped'][number]['reason']

export function provenanceLine(account: LoadedAccount | null, base: SolveRequest): string {
  const window = `${shortDate(base.as_of)} to ${shortDate(base.horizon_end)}`
  if (account === null) return `Sample checking account, ${window}.`
  if (!isNessie(account)) return `Modelled account, seed ${account.seed}, ${window}.`

  const where = 'Capital One sandbox'
  const head =
    account.nessie.mode === 'read_only'
      ? `${where} account ${account.nessie.account_id.slice(-6)}, ${plural(account.scheduled.length, 'row', 'rows')}`
      : `${where}, ${account.returned} of ${account.written} rows read back`

  const clauses = REASON_TEXT.map(([reason, one, many]) => {
    const n = account.not_round_tripped.filter((p) => p.reason === reason).length
    return n === 0 ? null : `${n} ${n === 1 ? one : many}`
  }).filter((c): c is string => c !== null)

  return [head, ...clauses].join(', ') + `, ${window}.`
}

// A range input snaps its value to min + k*step, so a balance that is not on
// the grid renders with the thumb somewhere else and jumps on the first drag.
// Move the floor instead of the balance: the number is the truth here.
export function sliderBounds(opening: number, step = 500): { min: number; max: number } {
  const floor = Math.min(2000, opening)
  const min = opening - step * Math.floor((opening - floor) / step)
  const wanted = Math.max(30000, opening)
  const max = min + step * Math.ceil((wanted - min) / step)
  return { min, max }
}

async function post(url: string, body: unknown, signal: AbortSignal, unreachable: string) {
  let r: Response
  try {
    r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e) {
    if (signal.aborted) throw e
    throw new ApiError(unreachable)
  }
  if (r.ok) return r.json()

  let detail = ''
  try {
    detail = describeDetail((await r.json())?.detail)
  } catch {
    /* body was not JSON; the status alone will have to do */
  }
  // A 5xx with no detail is not the server declining, it is nothing answering:
  // in development the Vite proxy turns a dead backend into an empty 500
  // rather than a network error, and in production the server is simply down.
  if (r.status >= 500 && !detail) throw new ApiError(unreachable, r.status)
  return { __error: true, status: r.status, detail }
}

function fail(result: { status: number; detail: string }, prefixes: Record<string, string>): never {
  const prefix =
    prefixes[String(result.status)] ??
    (result.status >= 500 ? prefixes.server : prefixes.client)
  throw new ApiError(result.detail ? `${prefix}: ${result.detail}` : `${prefix}.`, result.status)
}

export async function loadModelled(signal: AbortSignal): Promise<LoadedAccount> {
  const out = await post('/api/accounts/sample', {}, signal, 'Could not reach the server.')
  if (out?.__error) {
    fail(out, { server: 'Could not build an account', client: 'The account request was rejected' })
  }
  return parseAccount(out)
}

export async function loadNessie(signal: AbortSignal): Promise<LoadedAccount> {
  const out = await post('/api/accounts/nessie', {}, signal, 'Could not reach the server.')
  if (out?.__error) {
    fail(out, {
      '503': 'The Capital One sandbox is not set up on this server',
      '502': 'The Capital One sandbox did not answer',
      server: 'The sandbox request failed',
      client: 'The sandbox request was rejected',
    })
  }
  return parseAccount(out)
}

export async function candidatesViaApi(
  request: CandidatesRequest,
  signal: AbortSignal,
): Promise<CandidatesResponse> {
  const out = await post('/api/candidates', request, signal, 'Could not reach the server.')
  if (out?.__error) {
    fail(out, { server: 'Finding changes failed', client: 'Finding changes was rejected' })
  }
  return out as CandidatesResponse
}

export async function loadAccount(
  kind: 'modelled' | 'nessie',
  signal: AbortSignal,
): Promise<{ account: LoadedAccount; base: SolveRequest; meta: CandidatesResponse['meta'] }> {
  const account = kind === 'nessie' ? await loadNessie(signal) : await loadModelled(signal)
  const found = await candidatesViaApi(toCandidatesRequest(account), signal)
  return { account, base: toBase(account, found.candidates), meta: found.meta }
}

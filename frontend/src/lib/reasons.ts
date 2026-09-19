// Why a change the solver did not use is not in the plan.
//
// Every reason here is derived from the response, the request's dates, and the
// user's own overrides. None of it is financial arithmetic: the frontend
// renders what the solver returns (docs/api-contract.md). Where the solver has
// not proven something, the wording says so rather than softening it.
//
// The precedence order matters. A change the user ruled out is not "not
// needed" — the solver never saw it. A change that is too late to act on is
// not "not needed" either — it was not on the table.

import type { Candidate, SolveRequest, SolveResponse } from '../types'
import { shortDate } from './format.ts'

export type ReasonKind =
  | 'ruled_out'
  | 'too_late'
  | 'same_txn'
  | 'not_needed'
  | 'not_used_unproven'
  | 'no_fewer_days'
  | 'no_help_unproven'
  | 'pending'

export interface Reason {
  kind: ReasonKind
  text: string
}

const DAY_MS = 86_400_000

function toUTC(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y, m - 1, d)
}

export function daysBetween(a: string, b: string): number {
  return Math.round((toUTC(b) - toUTC(a)) / DAY_MS)
}

export const PENDING: Reason = { kind: 'pending', text: 'Re-solving…' }

export function reasonFor(
  candidate: Candidate,
  req: SolveRequest,
  res: SolveResponse,
  ruledOut: boolean,
): Reason {
  if (ruledOut) {
    return { kind: 'ruled_out', text: 'You ruled this out, so the solver never saw it.' }
  }

  // The same rule the solver applies: a change is actionable only if there are
  // at least `lead_time_days` between the horizon's first day and its effect.
  const notice = daysBetween(req.as_of, candidate.effective_date)
  if (notice < candidate.lead_time_days) {
    const n = candidate.lead_time_days
    return {
      kind: 'too_late',
      text: `Too late to act. It needed ${n} day${n === 1 ? '' : 's'} of notice before ${shortDate(
        candidate.effective_date,
      )}.`,
    }
  }

  // At most one change per transaction, so a change whose transaction is
  // already being changed was never a free choice.
  const byId = new Map(req.candidates.map((c) => [c.id, c]))
  const clash = res.plan.some(
    (p) => byId.get(p.candidate_id)?.target_txn_id === candidate.target_txn_id,
  )
  if (clash) {
    return {
      kind: 'same_txn',
      text: 'Another change to the same transaction is already in the plan. Only one is allowed.',
    }
  }

  const proven = res.certificate.minimal_proven

  if (res.tier === 3) {
    // Only the first objective term — days below zero — is established by
    // optimality here. Saying "would not shrink the gap" would be false: a
    // deferral can shrink the deepest dip while adding a day below zero.
    return proven
      ? { kind: 'no_fewer_days', text: 'Adding it would not leave you fewer days below zero.' }
      : {
          kind: 'no_help_unproven',
          text: 'Not used in the plan shown. Whether it would help was not proven; the solver ran out of time.',
        }
  }

  return proven
    ? { kind: 'not_needed', text: 'Not needed. The plan already clears zero without it.' }
    : {
        kind: 'not_used_unproven',
        text: 'Not used in the plan shown. Whether it is needed was not proven; the solver ran out of time.',
      }
}

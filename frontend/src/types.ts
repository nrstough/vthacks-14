// Mirrors docs/api-contract.md. Keep the two in step.

// Where the account on screen came from, which is a different question from
// which solver produced the numbers. A union, not an enum: the project compiles
// with erasableSyntaxOnly and Node's type stripping needs the same.
export type AccountSource = 'preset' | 'modelled' | 'nessie'

export type TxnKind = 'income' | 'bill' | 'discretionary'
export type Action = 'skip' | 'defer' | 'downgrade' | 'cancel'

export interface ScheduledTxn {
  id: string
  date: string
  description: string
  amount_cents: number // signed: + income, - outflow
  kind: TxnKind
  recurring: boolean
}

export interface Candidate {
  id: string
  label: string
  detail: string
  action: Action
  target_txn_id: string
  freed_cents: number
  effective_date: string
  recharge_date: string | null
  lead_time_days: number
  pain: number // 1..5
}

export interface Locks {
  in: string[]
  out: string[]
}

export interface SolveRequest {
  as_of: string
  horizon_end: string
  opening_balance_cents: number
  buffer_cents: number
  scheduled: ScheduledTxn[]
  candidates: Candidate[]
  locks: Locks
  previous_plan?: string[] // plan the user was last shown; the server keeps no state
}

export interface PlanItem {
  candidate_id: string
  label: string
  detail: string
  action: Action
  date: string
  freed_cents: number
  pain: number
  strictly_needed: boolean // false when it only protects the cushion
  reason: string
}

export interface CertificateItem {
  candidate_id: string
  worst_shortfall_cents: number // absolute worst dip with this change removed
  worst_date: string | null
  marginal_cents: number // how much DEEPER the dip gets without this change
  marginal_days: number // how many more days below zero without it
}

export interface Certificate {
  irredundant: boolean
  minimal_proven: boolean // false when a solver stage hit its time limit
  sentence: string
  per_item: CertificateItem[]
}

export interface BalanceRow {
  date: string
  baseline_cents: number
  with_plan_cents: number
  is_payday: boolean
  changes_here: string[]
}

export interface SolveResponse {
  tier: 1 | 2 | 3
  verdict: string
  qualifier: string
  plan: PlanItem[]
  certificate: Certificate
  shortfall: {
    worst_cents: number
    worst_date: string | null
    total_cents: number
  }
  external_cash_needed: { amount_cents: number; by_date: string } | null
  balances: BalanceRow[]
  meta: {
    solver: string
    status: 'OPTIMAL' | 'FEASIBLE'
    wall_ms: number
    candidates_considered: number
    excluded_locked_in: string[] // pinned ids dropped because they are no longer actionable
  }
}

// --------------------------------------------------------------------------
// account sources
// --------------------------------------------------------------------------

export interface CandidatesRequest {
  as_of: string
  horizon_end: string
  scheduled: ScheduledTxn[]
  limit?: number
}

export interface CandidatesMeta {
  rows_considered: number
  protected: string[]
  unrecognised: string[]
  not_actionable: string[]
  truncated: boolean
}

export interface CandidatesResponse {
  candidates: Candidate[]
  meta: CandidatesMeta
}

export interface SampleAccountRequest {
  seed?: number
  as_of?: string
  horizon_days?: number
}

// Not a request body for the other endpoints: it carries `seed` and `source`,
// and both request models forbid extras, so posting it verbatim is a 422. Pick
// the fields each endpoint declares — see toCandidatesRequest and toBase.
export interface SampleAccountResponse {
  seed: number
  as_of: string
  horizon_end: string
  opening_balance_cents: number
  buffer_cents: number
  scheduled: ScheduledTxn[]
  source: 'modelled'
}

// One row the sandbox did not give back unchanged. Reported, never hidden.
export interface NotRoundTripped {
  id: string
  reason:
    | 'written but not returned'
    | 'amount changed by the sandbox'
    | 'no usable date'
    | 'outside the window'
    | 'amount rounds to zero dollars'
}

export interface NessieProvenance {
  customer_id: string | null
  account_id: string
  mode: 'seeded' | 'read_only'
}

export interface NessieAccountResponse {
  seed: number
  as_of: string
  horizon_end: string
  opening_balance_cents: number
  buffer_cents: number
  scheduled: ScheduledTxn[]
  source: 'nessie'
  nessie: NessieProvenance
  written: number
  returned: number
  not_round_tripped: NotRoundTripped[]
}

export type LoadedAccount = SampleAccountResponse | NessieAccountResponse

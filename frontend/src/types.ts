// Mirrors docs/api-contract.md. Keep the two in step.

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

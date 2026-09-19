// The account-loading lifecycle, as a reducer.
//
// It is here rather than in the component because the sequencing is the part
// that goes wrong. Two of the three ways it can go wrong are invisible in a
// screenshot: a slow load landing after the user has moved on, and a cancelled
// load leaving the buttons disabled forever. Both are one-line tests here and
// neither is testable through the component, which nothing in tests/ mounts.

import type { LoadedAccount, SolveRequest } from '../types'

export type LoadKind = 'modelled' | 'nessie'

export interface AccountState {
  account: LoadedAccount | null
  base: SolveRequest
  loading: LoadKind | null
  error: string | null
  // The token of the load currently in flight, handed in by the caller. A
  // result carrying any other token belongs to a request the user has already
  // replaced. The reducer never invents one: two counters, one here and one in
  // the component, drift apart the first time a preset bumps only this one —
  // after which every result is silently ignored and the buttons never
  // re-enable. That happened; the browser found it and the unit tests did not.
  seq: number
}

// No load ever carries this token: the component's counter is pre-incremented,
// so the first load is 1. It means "nothing in flight that may land".
export const NO_LOAD = 0

export type AccountAction =
  | { type: 'start'; kind: LoadKind; seq: number }
  | { type: 'succeed'; seq: number; account: LoadedAccount; base: SolveRequest }
  | { type: 'fail'; seq: number; message: string }
  | { type: 'preset'; base: SolveRequest }

export function initial(base: SolveRequest): AccountState {
  return { account: null, base, loading: null, error: null, seq: NO_LOAD }
}

export function accountReducer(state: AccountState, action: AccountAction): AccountState {
  switch (action.type) {
    case 'start':
      return { ...state, loading: action.kind, error: null, seq: action.seq }

    case 'succeed':
      if (action.seq !== state.seq) return state
      return {
        ...state,
        account: action.account,
        base: action.base,
        loading: null,
        error: null,
      }

    case 'fail':
      if (action.seq !== state.seq) return state
      return { ...state, loading: null, error: action.message }

    case 'preset':
      // Clearing `loading` is the whole reason a preset goes through the
      // reducer. Without it, choosing a preset mid-load leaves the in-flight
      // load stale, so it skips its own cleanup and both account buttons stay
      // disabled until the page is reloaded.
      return {
        account: null,
        base: action.base,
        loading: null,
        error: null,
        seq: NO_LOAD,
      }
  }
}

export const start = (kind: LoadKind, seq: number): AccountAction => ({
  type: 'start',
  kind,
  seq,
})
export const succeed = (
  seq: number,
  account: LoadedAccount,
  base: SolveRequest,
): AccountAction => ({ type: 'succeed', seq, account, base })
export const fail = (seq: number, message: string): AccountAction => ({
  type: 'fail',
  seq,
  message,
})
export const preset = (base: SolveRequest): AccountAction => ({ type: 'preset', base })

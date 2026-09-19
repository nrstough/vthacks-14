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
  // Bumped by every start and every preset. A result carrying an older number
  // belongs to a request the user has already replaced.
  seq: number
}

export type AccountAction =
  | { type: 'start'; kind: LoadKind }
  | { type: 'succeed'; seq: number; account: LoadedAccount; base: SolveRequest }
  | { type: 'fail'; seq: number; message: string }
  | { type: 'preset'; base: SolveRequest }

export function initial(base: SolveRequest): AccountState {
  return { account: null, base, loading: null, error: null, seq: 0 }
}

export function accountReducer(state: AccountState, action: AccountAction): AccountState {
  switch (action.type) {
    case 'start':
      return { ...state, loading: action.kind, error: null, seq: state.seq + 1 }

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
      // reducer. Without it, choosing a preset mid-load bumps the sequence,
      // the in-flight load's result is then stale and skips its own cleanup,
      // and both account buttons stay disabled until the page is reloaded.
      return {
        account: null,
        base: action.base,
        loading: null,
        error: null,
        seq: state.seq + 1,
      }
  }
}

export const start = (kind: LoadKind): AccountAction => ({ type: 'start', kind })
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

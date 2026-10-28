// The answer put on screen the moment the account changes, before the
// server's.
//
// It comes from the built-in solver, which is exhaustive: its cost doubles
// with every change on the table, and it runs on the main thread with the page
// frozen. Measured under Node: 10-100 ms for the demo's eleven, about 0.3 s at
// sixteen, 0.7-1.8 s at eighteen (the candidates call's default limit) and
// several seconds at twenty. Sampled modelled accounts carry 7 to 15.
//
// Above the cap there is no placeholder. App withholds the previous account's
// answer (hidden, with the plan list and the explainer inert) until this
// account's first answer lands: the server's, or the solve effect's local
// fallback when the server cannot be reached. Neither that fallback nor the
// chip that discloses it goes through here.
//
// The cap counts every candidate, not only the free ones the search actually
// enumerates, so it is an upper bound: it never lets an expensive solve
// through, and at worst a cheap one waits for the server.

import { solve } from '../solver/mockSolver.ts'
import type { SolveRequest, SolveResponse } from '../types'

export const PLACEHOLDER_MAX_CANDIDATES = 14

export function placeholderSolve(req: SolveRequest): SolveResponse | null {
  if (req.candidates.length > PLACEHOLDER_MAX_CANDIDATES) return null
  try {
    return solve(req, [])
  } catch {
    // A request the stand-in refuses; the effect will answer, or say why not.
    return null
  }
}

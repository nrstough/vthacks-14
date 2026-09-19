// The user's overrides, and how they become the request's locks.
//
// The user tells the app exactly one thing about a change: whether they can do
// it. So this is a set of ids they have ruled out, and nothing else. There is
// no "pin" state — `locks.in` is always empty — because the screen no longer
// offers one, and an empty list is the honest encoding of "the user has not
// said".

import type { Locks } from '../types'

export type Overrides = ReadonlySet<string>

export const NONE: Overrides = new Set<string>()

export function toggle(current: Overrides, id: string): Overrides {
  const next = new Set(current)
  if (!next.delete(id)) next.add(id)
  return next
}

export function isRuledOut(current: Overrides, id: string): boolean {
  return current.has(id)
}

export function count(current: Overrides): number {
  return current.size
}

// Sorted, so that two equal sets produce byte-identical requests. The debounce
// upstream compares request objects, and an unstable order would make an
// unchanged set look like a new request.
export function toLocks(current: Overrides): Locks {
  return { in: [], out: [...current].sort() }
}

export function fromIds(ids: readonly string[]): Overrides {
  return new Set(ids)
}

// Ids whose override state differs between what the user has now and what the
// displayed response was actually solved with. Those rows cannot be described
// yet: the answer on screen never saw the current override.
export function pendingIds(current: Overrides, solved: Overrides): ReadonlySet<string> {
  const out = new Set<string>()
  for (const id of current) if (!solved.has(id)) out.add(id)
  for (const id of solved) if (!current.has(id)) out.add(id)
  return out
}

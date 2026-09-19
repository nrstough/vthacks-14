// Deciding where keyboard focus goes when the plan is re-solved.
//
// Ticking a row's checkbox moves that row between the plan and the left-out
// list, which unmounts its checkbox and drops focus on the floor. Restoring it
// sounds trivial and is not: three separate audit rounds found a different way
// to get it wrong. The rules live here, apart from React, so they can be tested
// without a DOM.

export interface ArmInput {
  /** The DOM id that had focus when the user changed something, if any. */
  activeElementId: string | null
  /** The candidate whose checkbox was just toggled. */
  toggledId: string
}

/**
 * The id to remember when a row is toggled, or null to stop tracking.
 *
 * It is derived entirely from where focus is at that moment, so it does not
 * depend on focus events having fired.
 */
export function armOnToggle(input: ArmInput): string | null {
  const { activeElementId, toggledId } = input
  // The usual case: the user is standing on the checkbox they just activated.
  if (activeElementId === domId(toggledId)) return toggledId
  // Activated without focusing it — a mouse click in Safari, which does not
  // focus checkboxes. There is no focus to preserve, and holding on to an older
  // id would later yank focus to a row the user left long ago.
  if (!activeElementId || !activeElementId.startsWith('cant-')) return null
  // Focus is on some other row. That is the one to restore if it moves, and
  // reading it from the DOM here means the rule holds even where focus events
  // never fire and `onFocusRow` has not run.
  return activeElementId.slice('cant-'.length)
}

/**
 * Whether two requests ask the same question.
 *
 * Used to decide whether the answer on screen is still the one the user is
 * waiting for. Overrides alone are not enough: dragging the balance slider or
 * the cushion also starts a new solve, and treating the old answer as current
 * because the checkboxes match is how focus gets dropped between two responses.
 */
export function sameInputs(a: FocusRequest, b: FocusRequest): boolean {
  return (
    a.opening_balance_cents === b.opening_balance_cents &&
    a.buffer_cents === b.buffer_cents &&
    a.as_of === b.as_of &&
    a.horizon_end === b.horizon_end &&
    sameIds(a.locks.out, b.locks.out) &&
    sameIds(a.locks.in, b.locks.in)
  )
}

export interface FocusRequest {
  as_of: string
  horizon_end: string
  opening_balance_cents: number
  buffer_cents: number
  locks: { in: readonly string[]; out: readonly string[] }
}

function sameIds(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((id, i) => id === b[i])
}

export interface RestoreInput {
  refId: string | null
  /** True when focus was lost rather than deliberately moved. */
  focusWasLost: boolean
  /** True when the answer on screen reflects the user's current input. */
  settled: boolean
}

export interface RestoreDecision {
  /** The candidate to focus, or null to leave focus alone. */
  focus: string | null
  /** Whether to forget the remembered row. */
  clear: boolean
}

export function decideRestore(input: RestoreInput): RestoreDecision {
  const { refId, focusWasLost, settled } = input
  if (!refId) return { focus: null, clear: false }
  return {
    // Restore only focus that was lost. Focus that survived is where the user
    // put it, and pulling it back would throw away their navigation.
    focus: focusWasLost ? refId : null,
    // Forget the row only once the answer on screen matches what the user last
    // asked for. Letting go earlier loses focus for good when responses
    // overlap: an older one arrives while the row is still mounted, so nothing
    // is restored, and the newer one then moves that row with nothing left to
    // put focus on.
    clear: settled,
  }
}

export function domId(candidateId: string): string {
  return `cant-${candidateId}`
}

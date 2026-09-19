// Deciding where keyboard focus goes when the plan is re-solved.
//
// Ticking "Can't do this" moves that row between the plan and the left-out
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
  // The user moved focus somewhere that survived the re-solve. Leave it, and
  // stop tracking: pulling it back would throw away their navigation.
  if (!focusWasLost) return { focus: null, clear: true }
  // Keep the id while more input is still being solved. A fast tick-untick
  // produces two responses, and consuming the id on the first leaves the second
  // with nothing to restore.
  return { focus: refId, clear: settled }
}

export function domId(candidateId: string): string {
  return `cant-${candidateId}`
}

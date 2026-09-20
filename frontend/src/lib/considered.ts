// Whether the "considered and left out" list should open itself.
//
// The list renders collapsed, which takes roughly 845px off the page. That is
// only safe because of this rule: when the user rules a change out, the row
// moves into that list, and a row moving into a shut list looks like a row
// that vanished. The demo says out loud "the card row then moves down to the
// left-out list", so the list has to be open when it lands.
//
// Why a transition and not `count > 0`: a reader who collapses the list by
// hand should not have it reopened by an unrelated re-solve.

export type ConsideredAction = 'open' | 'close' | 'leave'

/**
 * What to do with the list, given how many changes were ruled out before and
 * after.
 *
 * Opens on ANY increase, not only on the first override. Rule out A, collapse
 * the list by hand, rule out B: that is 1 -> 2, and if it returned 'leave' then
 * B would land in a shut list. This is not hypothetical — `armOnToggle`
 * returns null when a checkbox is activated without being focused, which is
 * the documented Safari mouse-click case, so the imperative open in App's
 * focus-restore effect never fires there and this rule is the only thing
 * keeping the row visible.
 *
 * Closes on any drop to zero, which is the reset buttons and also a reader
 * un-ticking their last override by hand. At zero the list is back to its
 * default state, so that is right, but it is a decision rather than an
 * accident: the list can collapse under you.
 *
 * Reset is NOT fully expressible here. A reader who opens the list by hand
 * with no overrides and then presses a preset produces 0 -> 0, which is
 * 'leave'. App closes it explicitly on that path as well.
 */
export function decideConsidered(prev: number, next: number): ConsideredAction {
  if (next > prev) return 'open'
  if (next === 0 && prev > 0) return 'close'
  return 'leave'
}

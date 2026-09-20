// Which of the two views is showing, and what follows from that.
//
// The union used to be written twice — once in App's useState and once in
// TopNav — and only stayed in step because props tied them together. It lives
// here now, with the rules that read it, so they can be tested without a DOM.

export type Tab = 'plan' | 'ask'

export const TABS: readonly Tab[] = ['plan', 'ask']

// The whole four-minute demo runs on the plan tab without a click. Ask exists
// for judges who probe, so it is never where the app opens.
export const DEFAULT_TAB: Tab = 'plan'

export function label(tab: Tab): string {
  return tab === 'plan' ? 'Plan' : 'Ask'
}

/**
 * Whether the plan list is on screen.
 *
 * The planning view is a conditional render, so when this is false its
 * checkboxes are not merely hidden, they are unmounted. `decideRestore` needs
 * to know: focus cannot be restored to a row that does not exist, and the
 * remembered row must survive rather than being thrown away.
 */
export function isPlanVisible(tab: Tab): boolean {
  return tab === 'plan'
}

/**
 * Whether a pill carries the alarm dot.
 *
 * One dot, spent on the one state that is an alarm: a gap no combination of
 * changes closes. It belongs to the plan pill, because the verdict is off
 * screen while Ask is showing and the dot is then the only thing saying the
 * other tab needs attention.
 */
export function showsAlarmDot(tab: Tab, tier: number): boolean {
  return tab === 'plan' && tier === 3
}

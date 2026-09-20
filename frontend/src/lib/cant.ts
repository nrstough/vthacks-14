import { domId } from './focus.ts'
import type { Overrides } from './overrides.ts'
import { isRuledOut } from './overrides.ts'

export type Section = 'plan' | 'out'
export interface Control { id: string; checked: boolean; text: string; ariaLabel: string }

// One set underneath, two readings on top. In the plan list the question is
// "can't you do this?"; in the left-out list it is "can you?", and the box is
// ticked when the answer is yes. The words carry the meaning, never the tick
// alone: a tick meaning two things silently is the bug the one control replaced.
export function controlFor(section: Section, ruledOut: Overrides, id: string, label: string): Control {
  const out = isRuledOut(ruledOut, id)
  const text = section === 'plan' ? 'Can’t do this' : 'Can do this'
  return { id: domId(id), checked: section === 'plan' ? out : !out, text, ariaLabel: `${text}: ${label}` }
}

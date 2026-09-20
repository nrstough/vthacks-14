import { domId } from './focus.ts'
import type { Overrides } from './overrides.ts'
import { isRuledOut } from './overrides.ts'

export interface Control { id: string; checked: boolean; text: string; ariaLabel: string }

export const CANT_DO_THIS = 'Can’t do this'

/**
 * The one checkbox, read the same way everywhere on the page.
 *
 * One ruled-out set underneath, and exactly one reading on top: the box asks
 * "can't you do this?", it is empty until you say otherwise, and a tick means
 * you have ruled the change out. Plan row or left-out row, the label and the
 * resting state are identical.
 *
 * This replaced a two-reading version where the left-out list asked "can you
 * do this?" and started ticked. The logic was sound — a change the solver did
 * not need is still one you could do — but on screen it put eight blue
 * checkmarks directly under a heading that said those changes had been LEFT
 * OUT, and a tick reads as "chosen" before anybody gets to the label. The
 * words were carrying a distinction the ticks were busy contradicting.
 *
 * So the distinction is gone rather than better explained. A tick now means
 * one thing anywhere: the user ruled this out. Which section a row sits in is
 * the solver's answer and is said in the heading and the reason line; the
 * checkbox only ever carries the user's own constraint.
 */
export function controlFor(ruledOut: Overrides, id: string, label: string): Control {
  const out = isRuledOut(ruledOut, id)
  return { id: domId(id), checked: out, text: CANT_DO_THIS, ariaLabel: `${CANT_DO_THIS}: ${label}` }
}

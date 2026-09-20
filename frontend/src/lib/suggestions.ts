// What an offer from the explainer would do, worked out before anyone taps it.
//
// Every decision about a suggestion lives here as a plain function over plain
// data, and for a reason beyond tidiness: the test runner is
// `node --experimental-strip-types --test`, which has no DOM and no React
// renderer. A component-level assertion that a suggestion does not apply
// itself cannot be executed in this project tonight. So the rule that carries
// the safety claim — an offer only ever becomes a value, never an action — is
// asserted here, where it can be, and the component's job is reduced to
// calling `resolve` and rendering what it returns.
//
// `resolve` is also what keeps the button honest. The panel labels a control
// with the value `resolve` gives it and `App` applies the value `resolve`
// gives it, so the number on the button is the number that lands. Clamping in
// one place and labelling in another is how a button comes to promise $250 and
// deliver $100.

import type { Suggestion, SuggestionKind } from './chat.ts'
import { sliderBounds } from './accounts.ts'
import { money } from './format.ts'

// The cushion slider's own range. Lifted out of App.tsx, where they were three
// literals on a JSX attribute, because a clamp that disagrees with the control
// it clamps to is a silent bug and duplication is how they come to disagree.
export const CUSHION_MIN = 0
export const CUSHION_MAX = 10000
export const SLIDER_STEP = 500

export type Resolved =
  | { kind: 'rule_out'; id: string }
  | { kind: 'allow'; id: string }
  | { kind: 'opening'; cents: number }
  | { kind: 'cushion'; cents: number }

// Clamped, never snapped. The opening slider's floor is recomputed from the
// current value (see sliderBounds), so the grid is relative and every integer
// balance is representable on its own: snapping to the step here would throw
// away cents to no purpose.
export function clampOpening(cents: number, currentOpening: number): number {
  const { min, max } = sliderBounds(currentOpening)
  return Math.min(max, Math.max(min, cents))
}

// Clamped AND snapped, the cushion's range being absolute. Integer arithmetic
// rather than Math.round(c / STEP) * STEP: rounding is float, and the money
// rule in CLAUDE.md is not a style preference. Re-clamped after snapping
// because rounding up at the top of the range would otherwise leave the value
// one step above the maximum.
export function clampCushion(cents: number): number {
  const held = Math.min(CUSHION_MAX, Math.max(CUSHION_MIN, cents))
  const snapped = Math.floor((held + SLIDER_STEP / 2) / SLIDER_STEP) * SLIDER_STEP
  return Math.min(CUSHION_MAX, Math.max(CUSHION_MIN, snapped))
}

// What this offer would actually do, or null if it would do nothing coherent.
// The server validated the shape; this decides the value, because the bounds
// belong to the screen and move with it.
export function resolve(s: Suggestion, currentOpening: number): Resolved | null {
  switch (s.kind) {
    case 'rule_out':
      return s.candidate_id ? { kind: 'rule_out', id: s.candidate_id } : null
    case 'allow':
      return s.candidate_id ? { kind: 'allow', id: s.candidate_id } : null
    case 'opening':
      return s.amount_cents === null
        ? null
        : { kind: 'opening', cents: clampOpening(s.amount_cents, currentOpening) }
    case 'cushion':
      return s.amount_cents === null
        ? null
        : { kind: 'cushion', cents: clampCushion(s.amount_cents) }
    default:
      return null
  }
}

// The words on the button, composed here from the resolved value and never
// from the model's prose. The prose above a control is influenced by whoever
// is typing into the chat; the button is not, which makes it the last thing on
// screen that can be relied on to say what will happen.
export function labelFor(r: Resolved, nameOf: (id: string) => string): string {
  switch (r.kind) {
    case 'rule_out':
      return `Rule out ${nameOf(r.id)}`
    case 'allow':
      return `Put ${nameOf(r.id)} back`
    case 'opening':
      return `Set starting balance to ${money(r.cents)}`
    case 'cushion':
      return `Set cushion to ${money(r.cents)}`
  }
}

// Stable per message and per position within it. Not content-derived: a
// legitimate second offer of the same change, six turns later, is a new offer
// and must not render already-approved.
export function keyOf(messageIndex: number, suggestionIndex: number): string {
  return `${messageIndex}:${suggestionIndex}`
}

export type { Suggestion, SuggestionKind }

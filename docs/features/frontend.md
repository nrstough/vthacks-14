# Feature: frontend

Living document for the UI. Run specs: `docs/specs/2026-09-19_frontend-ux.md` (first). The
solver and its contract are documented in `docs/features/solver.md` and `docs/api-contract.md`;
this doc covers what the screen says and how the user talks back to it.

## What it is

One screen, three bands, over a frozen `POST /api/solve` contract. React + Vite + TypeScript +
Recharts. The page does no financial arithmetic: every balance, tier, verdict, certificate and
reason on screen is either returned by the solver or derived from dates and ids alone.

1. **Verdict band**: tier pill, verdict sentence, qualifier, proof box (the certificate
   sentence), and at tier 3 the outside-cash callout. Announced to assistive tech as a polite
   live region, so a re-solve is read out once.
2. **Balance band**: a written equivalent of the chart above the chart itself, then the chart.
   The chart container is an image described by the text; the SVG is hidden from assistive tech.
3. **Plan band**: the chosen changes in the order they take effect, then the left-out changes
   with a reason each.

## Sources of truth on screen

- The solver: `POST /api/solve`, with a 150 ms debounce and a stale-response guard.
- The built-in fallback: `src/solver/mockSolver.ts`, used when the API is unreachable, disclosed
  by the footer chip "Running on the built-in solver". The chip is a product commitment, not
  styling. The same file is the oracle the Python solver is tested against; UI work never edits
  it. If the UI needs different solver output, change the request, not the oracle.
- The fixtures: `src/fixtures/scenarios.ts`, three presets whose on-screen values are canaries
  (see below).

## The override model

The user tells the app one thing about a change: whether they can do it. So every row, chosen
or not, carries one identical control: a checkbox, "Can't do this", unchecked by default.
Unchecked means the user has said nothing. Checked means the id goes into `locks.out` and the
solver may not use it. `locks.in` is always empty; pinning is not on the screen.

Which section a row sits in is the outcome. The checkbox is the input. They share no control.
Presets clear all overrides; so does the "Clear n overrides" button.

`src/lib/overrides.ts` owns the set and its translation to `locks`.

## Reasons on left-out rows

`src/lib/reasons.ts`. Derived only from the response, the request's dates and the override
set. Precedence, first match wins:

1. Ruled out by the user: "You ruled this out, so the solver never saw it."
2. Too late to act: `effective_date − as_of < lead_time_days`, the same rule the solver applies.
3. Another change to the same `target_txn_id` is already in the plan: "Another change to the
   same transaction is already in the plan. Only one is allowed." At most one change per
   transaction, so this one was never a free choice and calling it unneeded would be wrong.
4. Tier 1 or 2, minimality proven: "Not needed. The plan already clears zero without it."
5. Tier 3, proven: "Adding it would not leave you fewer days below zero." This is exactly what
   optimality of the first objective term establishes and no more. It must not say the change
   would not shrink the gap: a deferral can shrink the deepest dip while adding a day below
   zero, so that claim would be false.
6. Unproven, any tier: "Not used in the plan shown. Whether it is needed / would help was not
   proven; the solver ran out of time." An unproven solve never claims the plan clears without
   a change.

No reason ever claims a change "lands after the dip" or similar: that would be the frontend
doing the solver's job.

A row whose "Can't do this" state differs from the set the displayed answer was solved with
shows "Re-solving…" instead of any reason, in the plan list and the left-out list alike. The
alternative is describing a change against a solve that never saw the user's current answer.

## Narration

`src/lib/narrate.ts`. The chart's text equivalent: the do-nothing series' lowest point and its
first day; the with-plan series' lowest point and first day (at tier 3, taken from the response's
`shortfall`); paydays; the days changes take effect. Also the footer sentences: the proof claim
appears only when `certificate.minimal_proven` is true.

## Dates on a plan row

`plan[].date` is the day a change **takes effect**, and the chip says so. It is not the day the
user has to act: `lead_time_days` is how far ahead the change must be actioned, so a gym that
bills on Sep 22 and needs three days' notice must be cancelled by **Sep 19**. Rows with a lead
time carry that deadline explicitly ("Act by Sep 19: it needs 3 days of notice."), derived in
`src/lib/reasons.ts` from the candidate. Dates only; no money arithmetic happens here.

`docs/api-contract.md` describes `plan[].date` as "the day the user must act", but both solvers
return the effective date. If the backend ever returns a real deadline, delete this derivation
and use it.

## The empty plan

An empty plan means three different things, so `src/lib/narrate.ts`'s `emptyPlanText` splits on
the tier and on how many changes were on the table:

| Case | Heading | Body |
|---|---|---|
| Tier 1 or 2 | No changes needed | Nothing to change. The schedule already clears on its own. |
| Tier 3, nothing considered | No changes available | Everything is ruled out or too late to act. The gap stays. |
| Tier 3, changes still on the table | No change helps here | None of the changes still on the table would leave you fewer days below zero. |

Saying "no changes needed" at tier 3 would flatly contradict the verdict band above it, which is
naming money the user has to find by a date. Rule out all eleven changes on the $200 account:
tier 3, empty plan, $120.05 needed by Sep 24.

Saying "everything is ruled out or too late" when changes remain is equally false, and the user
can see the rows. Rule out all but Netflix on the same account: it is actionable, it just takes
effect on Sep 29, after the Sep 24 dip, so it cannot reduce the days below zero. That is what
the third case says, and no more.

## Wording rules (from CLAUDE.md, binding)

- "Sufficient under the schedule shown", never "guaranteed".
- An empty plan at tier 3 never says "no changes needed".
- The word "infeasible" never appears. Tier 3 names the amount and the date.
- Minimality is claimed only when proven; the tier pill drops "proven" otherwise.
- The fallback chip is never removed and never reworded to hide the fallback.
- A test greps the built bundle for the forbidden words.

## Accessibility

The chart is `role="img"` labelled and described by the narration paragraph above it; its whole
subtree is `aria-hidden`, and Recharts' `accessibilityLayer` is switched off with it, because
that layer puts a `tabIndex=0` surface inside the hidden subtree. Verified: 11 checkboxes in the
tab order, zero tabbable elements inside `.chart-wrap`.

Each row's checkbox carries an accessible name including the change it belongs to, since eleven
rows otherwise read identically. Ticking one moves its row between sections, which unmounts the
input; focus is restored to the same checkbox afterwards, but only when it was lost to the
document body, so a user who has tabbed on is not yanked back.

The verdict section is an `aria-live="polite"` region so a re-solve is announced.

## Focus

Ticking a checkbox moves its row between the plan and the left-out list, which unmounts the
input. `src/lib/focus.ts` holds the rules, apart from React so they can be tested without a DOM:

- Remember the row the user is standing on, from the toggle itself and from `onFocus`. A row
  activated without being focused (Safari does not focus checkboxes on click) clears the memory
  rather than leaving a stale one to grab focus later.
- Restore only focus that was **lost** — parked on the body. Focus the user moved deliberately
  is left alone.
- Keep the memory until the answer on screen matches the user's current input, so a quick tick
  and undo does not consume it on the first of two responses.
- Open the "other changes" section before focusing into it; nothing inside a closed `details`
  can take focus.
- Suppress tracking during the restore itself, or the focus event writes the id straight back.

Verified by hand in the browser, six sequences: toggled row moves; user moves to a surviving
row; activation with no prior focus; a later unrelated re-solve; the left-out section collapsed;
tick then undo inside the debounce.

## Design system

`src/index.css`: tokens for background, panel, line, ink at three weights; one accent
(`#2c5ae8`); negative and warn with washes; an 8px spacing scale; 10px radius; system sans;
tabular numerals on money. No dark mode. Two `max-width: 720px` blocks and a reduced-motion
block. Keep one accent and one font.

## Canaries

| Preset | Tier | Plan | Tightest day |
|---|---|---|---|
| $200.00 / $25 cushion | 1 | 3 (DoorDash, gym, card minimum) | Sep 24 at $26.74 |
| $180.00 / $100 cushion | 2 | same 3 | Sep 24 at $6.74 |
| $60.00 / $25 cushion | 3 | 9, "$27.62 more by Sep 24" | gap grows by up to $80.00 |

Demo beat: on the $200 preset, ruling out the card minimum gives 7 changes. **Three** of them
are load-bearing — the DoorDash order, the gym and the gas deferral — and the rows say which.
The certificate sentence for this case reads "Remove Put off the gas fill to the 26th … The
rest hold the cushion", which is false while three are load-bearing. That sentence is the
solver's, is rendered verbatim per the contract, and is identical in
`backend/app/solver/wording.py` and `frontend/src/solver/mockSolver.ts`. Logged for the backend
lane; `docs/demo-script.md` carries a fallback answer if a judge reads the box closely.

## Tests

`frontend/tests/*.test.ts`, run by `npm test` (Node's built-in runner under
`--experimental-strip-types`, no DOM). Rendering is checked in the browser pane against the
canaries. Full check, **in this order**:

```bash
cd frontend && npm run lint && npm run build && npm test
```

Build before test, always. `tests/bundle.test.ts` greps the built bundle for the forbidden
words and the fallback chip, and it fails rather than skips when `dist/` is missing, so running
it first either errors or, worse, passes against stale output that no longer ships.

Then the backend gate, because the parity tests run this frontend's oracle:

```bash
.venv/bin/pytest backend/ -q -m "not perf"
```

## Known gaps

- No DOM test runner (none installable from the hotel); component rendering is verified by hand.
- Bundle is 621 kB / 184 kB gzip, almost all Recharts. Only worth acting on if the deployed demo
  feels slow.
- No dark mode.

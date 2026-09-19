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
3. **Plan band**: the chosen changes in act-by order, then the left-out changes with a reason
   each.

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
set. Precedence:

1. Ruled out by the user: "You ruled this out, so the solver never saw it."
2. Too late to act: `effective_date − as_of < lead_time_days`, the same rule the solver applies.
3. Tier 1 or 2, minimality proven: "Not needed. The plan already clears without it."
4. Tier 1 or 2, unproven: "Not used in the plan shown. Whether it is needed was not proven; the
   solver ran out of time."
5. Tier 3, proven: "Adding it would not shrink the gap or lift another day above zero."
6. Tier 3, unproven: softened as in 4.

No reason ever claims a change "lands after the dip" or similar: that would be the frontend
doing the solver's job.

## Narration

`src/lib/narrate.ts`. The chart's text equivalent: the do-nothing series' lowest point and its
first day; the with-plan series' lowest point and first day (at tier 3, taken from the response's
`shortfall`); paydays; the days changes take effect. Also the footer sentences: the proof claim
appears only when `certificate.minimal_proven` is true.

## Wording rules (from CLAUDE.md, binding)

- "Sufficient under the schedule shown", never "guaranteed".
- The word "infeasible" never appears. Tier 3 names the amount and the date.
- Minimality is claimed only when proven; the tier pill drops "proven" otherwise.
- The fallback chip is never removed and never reworded to hide the fallback.
- A test greps the built bundle for the forbidden words.

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

Demo beat: on the $200 preset, ruling out the card minimum gives 7 changes; only the gas
deferral is strictly needed, the rest hold the cushion.

## Tests

`frontend/tests/*.test.ts`, run by `npm test` (Node's built-in runner under
`--experimental-strip-types`, no DOM). Rendering is checked in the browser pane against the
canaries. Full check: `npm run lint && npm test && npm run build`, plus the backend gate
`.venv/bin/pytest backend/ -q -m "not perf"`, because the parity tests run this frontend's oracle.

## Known gaps

- No DOM test runner (none installable from the hotel); component rendering is verified by hand.
- Bundle is 616 kB / 182 kB gzip, almost all Recharts. Only worth acting on if the deployed demo
  feels slow.
- No dark mode.

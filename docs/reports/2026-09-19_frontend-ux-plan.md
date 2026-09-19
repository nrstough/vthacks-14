# Plan — frontend UX: one override control, reasons, narration, labels

Run spec: `docs/specs/2026-09-19_frontend-ux.md`. Branch `frontend` in worktree
`/Users/nathanstough/Desktop/vthacks-frontend` (node_modules, .npm-cache, .venv are symlinks to
the main checkout; never `npm install`). Line numbers below are against `frontend` at `3d89fcf`.

Pre-flight every step: `git branch --show-current` must print `frontend`; `pwd` must be the
worktree. `git add` names explicit paths only.

Time budget: ~3.5 h coding + verification, well inside the 18:30 gate.

## Step 0 — Test runner works (10 min)

1. `frontend/package.json:6`: add `"test": "node --experimental-strip-types --test tests/*.test.ts"`.
   (npm runs scripts through `sh`, which expands the glob; Node's default `--test` patterns do
   not match `.ts`.)
2. `frontend/tsconfig.app.json`: `"types": ["vite/client"]` → `["vite/client", "node"]`;
   `"include": ["src"]` → `["src", "tests"]`, so `tsc -b` type-checks the tests. If this fights
   the build (e.g. DOM lib vs node types), revert and record it in the run spec; the tests still
   run under Node.
3. `frontend/tests/smoke.test.ts`: one `node:test` case importing
   `../src/lib/format.ts` and asserting `money(2674) === '$26.74'`. Run `npm test`. Delete the
   file in Step 6 once real tests exist, or keep it as the format test.
4. `npm run lint` must stay clean with the new dir (oxlint lints cwd).

## Step 1 — `src/lib/overrides.ts` (15 min)

Pure module, no React.

```ts
import type { Locks } from '../types'
export type Overrides = ReadonlySet<string>
export const NONE: Overrides = new Set()
export function toggle(o: Overrides, id: string): Overrides   // add if absent, remove if present; returns a new Set
export function isRuledOut(o: Overrides, id: string): boolean
export function toLocks(o: Overrides): Locks                   // { in: [], out: [...sorted] }
export function count(o: Overrides): number
```

`toLocks` sorts so the request is deterministic and the debounce compares equal for equal sets.
`in` is always `[]` (D1).

## Step 2 — `src/lib/reasons.ts` (25 min)

```ts
import type { Candidate, SolveResponse } from '../types'
// mockSolver.ts exports daysBetween, but UI code must not import the oracle. Reimplement
// locally: UTC date arithmetic as in mockSolver.ts:22-31. Dates only, no money.
export type ReasonKind = 'ruled_out' | 'too_late' | 'same_txn' | 'not_needed' | 'not_used_unproven' | 'no_fewer_days' | 'no_help_unproven'
export interface Reason { kind: ReasonKind; text: string }
export function reasonFor(c: Candidate, req: SolveRequest, res: SolveResponse, ruledOut: boolean): Reason
export function daysBetween(a: string, b: string): number
```

`ruledOut` here is whether `c` was ruled out **in the request that produced `res`**, not the
current checkbox state (see Step 5, review finding 5).

Rules (D2), in order:
- `ruledOut` → `ruled_out`, "You ruled this out, so the solver never saw it."
- `daysBetween(asOf, c.effective_date) < c.lead_time_days` → `too_late`,
  `Too late to act. It needed ${n} day${n===1?'':'s'}' notice before ${shortDate(c.effective_date)}.`
- A chosen plan item targets the same `target_txn_id` (look up each `plan[].candidate_id` in
  `req.candidates`) → `same_txn`, "Another change to the same transaction is already in the
  plan. Only one is allowed." (The one-per-transaction rule, `api-contract.md:146`.)
- `res.tier === 3`: proven → `no_fewer_days`, "Adding it would not leave you fewer days below
  zero." This is exactly what optimality of the first objective term establishes and nothing
  more; the earlier "would not shrink the gap" was wrong because a deferral can shrink the dip
  while adding a day below zero (review finding 2). Unproven → `no_help_unproven`, "Not used
  in the plan shown. Whether it would help was not proven; the solver ran out of time."
- else proven → `not_needed`, "Not needed. The plan already clears zero without it."; unproven
  → `not_used_unproven`, "Not used in the plan shown. Whether it is needed was not proven; the
  solver ran out of time." 

`shortDate` from `../lib/format.ts` (explicit `.ts` extension in every import inside `src/lib`
that Node will load: see `mockSolver.ts:10-12` for the precedent; `allowImportingTsExtensions`
is on in `tsconfig.app.json`).

## Step 3 — `src/lib/narrate.ts` (30 min)

```ts
import type { SolveResponse } from '../types'
import { money, shortDate } from './format.ts'
export function narrateChart(res: SolveResponse): string[]   // sentences, joined by the component
export function footerLines(res: SolveResponse): string[]
```

`narrateChart`:
1. First-day minimum of `baseline_cents` (strict `<` while scanning, so ties keep the first):
   `Doing nothing, the balance bottoms out at ${money(v)} on ${shortDate(d)}.`
   If min ≥ 0: `Doing nothing, the lowest point is ${money(v)} on ${shortDate(d)}.`
2. With-plan: at tier 3 use `res.shortfall.worst_cents`/`worst_date`:
   `With the plan, the balance is still ${money(-worst)} on ${shortDate(worst_date)}.`
   Otherwise first-day minimum of `with_plan_cents`:
   `With the plan, the lowest point is ${money(v)} on ${shortDate(d)}.`
3. Paydays: `Payday lands on Sep 25 and Oct 2.` / singular / none → `No payday in this window.`
4. Change days: `Changes take effect on Sep 22 and Sep 24.` / `One change takes effect on …` /
   plan empty → `No changes take effect.`

Test expectations for the three fixtures come from the oracle run recorded in the run spec's
Results (clears: baseline −$120.05 Sep 24, plan $26.74 Sep 24, paydays Sep 25 and Oct 2, changes
Sep 22 and Sep 24; tight: −$140.05 / $6.74; gap: −$260.05 / still −$27.62 Sep 24, seven change
days).

`emptyPlanText(res)` (review finding 1): tier 3 with an empty plan →
`{ heading: 'No changes available', body: 'Everything is ruled out or too late to act. The gap stays.' }`;
otherwise `{ heading: 'No changes needed', body: 'Nothing to change. The schedule already clears on its own.' }`
(the current strings, `App.tsx:184` and `PrescriptionList.tsx:72`). The verdict band already
names the amount and date at tier 3.

`footerLines`:
- `res.certificate.minimal_proven ? 'Exact solver, smallest plan proven' : 'Exact solver, smallest plan not proven: it ran out of time'`
- `Solved in ${res.meta.wall_ms} ms`
- `${res.meta.candidates_considered} changes considered`
The chip text stays in `App.tsx` verbatim (D4).

## Step 4 — `PrescriptionList.tsx` (40 min)

Current file: 141 lines. Rewrite:
- Delete `LockState`, `stateOf`, `OPTIONS`, `LockControl` (lines 4-46).
- Props: `{ req, res, ruledOut: Overrides, solvedRuledOut: Overrides, newIds, onToggle }`.
  `ruledOut` drives the checkboxes; `solvedRuledOut` is the set the displayed response was
  solved with and drives the reasons (review finding 5).
- `CantDo({ id, label, checked, onToggle })`: `<label className="cant"><input type="checkbox"
  id={`cant-${id}`} checked={checked} onChange={() => onToggle(id)}
  aria-label={`Can't do this: ${label}`} /> Can't do this</label>`. The accessible name
  includes the change label so eleven identical checkboxes are distinguishable (AC1). The DOM id
  is what focus restoration targets (Step 5).
- Empty state (line 72): use `emptyPlanText(res).body`.
- `pain(n)` (48-50) → `Disruption ${n} of 5` text, keep the dots as a visual prefix
  `aria-hidden`.
- Plan rows (74-104): date chip gains `<small>act by</small>`; keep `rx-reason` line (the
  solver's own reason); drop the `pinned` branch and tag; `CantDo` in the fourth column.
- Left-out rows (107-138): reason line via `reasonFor(c, req, res, isRuledOut(solvedRuledOut,
  c.id))` rendered as `<p className="rx-why">`. If `isRuledOut(ruledOut, c.id) !==
  isRuledOut(solvedRuledOut, c.id)` the row is pending: reason text "Re-solving…" instead, so a
  just-unticked change never reads "not needed" on the strength of a solve that never saw it.
  `is-out` class from the **current** set (keeps the strike-through and muted chip,
  `index.css:353-365`); `CantDo` checked from the current set.
- Heading text for the left-out section unchanged.

## Step 5 — `App.tsx`, `VerdictBand.tsx`, `BalanceChart.tsx` (30 min)

`App.tsx`:
- Lines 3-4: drop the `LockState` import; import `overrides.ts` helpers and `narrate.ts`.
- Line 19: `const [ruledOut, setRuledOut] = useState<Overrides>(NONE)`.
- Lines 23-26: `locks: toLocks(ruledOut)` in the memo (deps `[opening, buffer, ruledOut]`).
- Lines 73-78: `onLockChange` → `onToggle(id) { setRuledOut(o => toggle(o, id)) }`.
- Lines 80-85 preset: `setRuledOut(NONE)`.
- Line 87: `const locked = count(ruledOut)`.
- Lines 155-178 chart band: insert `<p className="narration" id="chart-text">{narrateChart(res).join(' ')}</p>`
  between `band-head` and the chart; pass `describedBy="chart-text"` to `BalanceChart`.
- Lines 187-191 reset button: `setRuledOut(NONE)`.
- Lines 193-199: new props.
- Lines 202-212 footer: replace the three `meta` spans with `footerLines(res).map(...)`;
  keep `candidates_considered` inside `footerLines`; keep lines 207-211 (the chip) verbatim.
- Solved-overrides tracking (finding 5): `const [solvedRuledOut, setSolvedRuledOut] =
  useState<Overrides>(NONE)`; in `apply()` (44-54) set it to the overrides the request carried
  (capture `debounced.locks.out` as a Set at the top of the effect). Pass both sets to
  `PrescriptionList`.
- Focus restoration (finding 4): `const refocus = useRef<string | null>(null)`; `onToggle`
  records `refocus.current = id` when `document.activeElement?.id === `cant-${id}``. In a
  `useEffect` on `[res]`, if `refocus.current` is set, `document.getElementById(`cant-${id}`)
  ?.focus()` and clear it. The row moves between sections, so the input remounts; the id is
  stable and the effect runs after commit.
- Lines 183-185 heading: `res.plan.length === 0 ? emptyPlanText(res).heading : …`.

`VerdictBand.tsx:22`: `<section className="verdict" aria-live="polite" aria-atomic="true">`.

`BalanceChart.tsx`:
- Prop `describedBy: string`.
- Line 77: `<div className="chart-wrap" role="img" aria-label="Daily balance, do nothing versus with the plan" aria-describedby={describedBy}>`.
- Wrap `ResponsiveContainer` (78-177) in `<div aria-hidden="true">` so the SVG's hundreds of
  nodes are not read.
- Line 79: `<ComposedChart accessibilityLayer={false} …>`. Recharts 3.10 defaults the layer on
  and gives the surface `tabIndex=0` (`CartesianChart.d.ts:7`); a focusable element inside
  `aria-hidden` is an accessibility violation (finding 3). Browser check: Tab never lands in
  the chart.

## Step 6 — `index.css` (20 min)

- Lines 375-392 (`.locks`): replace with
  `.cant { display:flex; align-items:center; gap:8px; font-size:13px; color:var(--ink-2); white-space:nowrap; cursor:pointer; }`
  `.cant input { width:16px; height:16px; margin:0; accent-color:var(--accent); }`
  `.rx-row.is-out .cant { color: var(--warn); font-weight: 600; }`
- Add `.rx-why { font-size:13px; color:var(--ink-2); margin:6px 0 0; }`
- Add `.rx-date small { display:block; font-size:10px; font-weight:400; letter-spacing:.04em; text-transform:uppercase; }`
- Add `.narration { font-size:14px; color:var(--ink-2); margin:0 0 var(--s2); max-width:68ch; }`
- Lines 440-445 mobile: `.locks` → `.cant`.
- Lines 88-90, 151-172 (`.switcher`, an unused leftover) — leave alone; out of scope.

## Step 7 — Tests (50 min)

`frontend/tests/`:
- `overrides.test.ts` (~8): toggle add/remove/idempotent, new Set each time, `in` always `[]`,
  sorted `out`, count.
- `reasons.test.ts` (~20): each kind including `same_txn` (a candidate whose target is used by
  a plan item); precedence ruled_out > too_late > same_txn > tier; lead-time boundary
  (equal → not too_late, one less → too_late, lead 0 always ok); unproven never contains
  "already clears" or "would not"; tier 3 never says "clears"; forbidden words absent from every
  reason across all kinds; every unused candidate of each fixture gets non-empty text; 200
  random `Candidate`/tier/proven combos deterministic (same input → same output).
- `narrate.test.ts` (~17): three fixtures' exact sentences; `emptyPlanText` at tier 3 vs tier
  1/2 (never "No changes needed" at tier 3); tie on min picks first day; baseline
  never negative wording; tier 3 uses `shortfall`; empty plan; single payday; footer proven /
  unproven; forbidden words absent.
- `fixtures.test.ts` (~8): via `mockSolver.solve` (read-only import): tiers 1/2/3, plan sizes
  3/3/9, qualifier contains "Sep 24 at $26.74", beat (out `c_card_min`) → 7 changes and only
  `c_shell_defer` strictly needed; all eleven out → tier 3, empty plan, `emptyPlanText` heading
  "No changes available".
- `overrides.test.ts` also covers `pendingIds(current, solved)` = symmetric difference.
- `bundle.test.ts` (~3): reads `dist/assets/*.js`; asserts no `/guarantee/i`, no `/infeasib/i`,
  and contains "Running on the built-in solver". **Fails** if `dist/` is absent (finding 6):
  the check order is lint → build → test, everywhere.

Target ≈ 55 tests.

## Step 8 — Browser verification (30 min)

Dev server on 5173 is the other session's Vite from the MAIN checkout, not this worktree.
Start this worktree's own: `.claude/launch.json` in the worktree points at `frontend`; run
`preview_start {name: "frontend"}` from the worktree (port clash → set `--port 5174` in the
launch config for this worktree only; do not commit that).

Checks (record each in the run spec Results with what `read_page` showed):
1. $200 preset: 3 rows, all checkboxes unchecked, names "Can't do this: Skip the DoorDash order" etc.
2. Tick the card minimum: 7 changes; card row in left-out with "You ruled this out"; heading
   "7 changes"; "Clear 1 override" visible. Untick: back to 3.
3. Tick two, click a preset: both cleared.
4. $60 preset: tier 3 callout; narration says "still -$27.62 on Sep 24"; left-out rows say
   "would not shrink the gap".
5. Tick all eleven: tier 3, heading "No changes available", body "Everything is ruled out or
   too late to act. The gap stays."; never "No changes needed"; no forbidden words in page text.
6. `read_page`: chart region is `img` with description = narration; verdict region live.
7. Keyboard: Tab to a checkbox, Space toggles; after the re-solve the same candidate's checkbox
   still has focus (row moved sections); Space again undoes it. Tab from the narration never
   enters the chart.
8. Backend down: chip present. Backend up (`uvicorn` from the worktree on 8000, or the main
   checkout's if running): chip absent, footer says "Exact solver, smallest plan proven".
9. `resize_window mobile`: no horizontal overflow, checkbox visible. Screenshot.

## Step 9 — Docs, full run, commit (20 min)

- `docs/demo-script.md:75`: "**[Click "Can't do" on the "Pay the card minimum" row.]**" →
  "**[Tick "Can't do this" on the "Pay the card minimum" row.]**"; line 84 note unchanged in
  meaning; line 19-21 checklist: add the frontend test count to the numbers to refresh.
- `README.md` Test section: add `cd frontend && npm test`. (Conditional in P2; do it, it is one line.)
- Run spec Results: commands, counts, browser checks, canaries, deviations.
- Full run, in this order: lint, build, test, pytest. `git diff main -- frontend/src/solver/mockSolver.ts` empty.
- Commit with explicit paths: `git add frontend/src/App.tsx frontend/src/components/… frontend/src/lib/overrides.ts … frontend/tests/… frontend/src/index.css frontend/package.json frontend/tsconfig.app.json docs/specs/… docs/features/frontend.md docs/reports/… docs/demo-script.md README.md`.
  Message: `feat(ui): one override control per row, reasons for left-out changes, chart narration`.

## Verification (AC → where)

AC1 overrides.test + browser 1,2 · AC2 fixtures.test + browser 2 · AC3 reasons.test · AC4
narrate.test + browser 6 · AC5 browser 1 · AC6 narrate.test footer + bundle.test + browser 8 ·
AC7 bundle.test · AC8 git diff + pytest · AC9 fixtures.test + browser 1,4 · AC10 browser 9.

## Risks and mitigations

- **Node `--test` glob**: if `sh` glob expansion misbehaves, list files explicitly in the script.
- **tsc including tests**: DOM lib + node types can conflict on `fetch`/`URL` typings; fall back
  to leaving tests out of `tsc -b` (they still run) and record it.
- **oxlint on tests**: `node:test` imports are fine; if it flags `any`, don't use `any`.
- **aria-live on the verdict** could chatter while the slider drags; the request is already
  debounced 150 ms and the response applied once, so one announcement per settled value. If it
  still chatters, move `aria-live` to the `h1` only.
- **Recharts and `aria-hidden`**: hiding the container hides the tooltip from AT too; the
  narration is the accessible path. Acceptable and documented.
- **Port 5173 belongs to another session**: never kill it; use 5174 for this worktree.
- **The other chat may merge `backend` into `main`** while this runs: merge `main` into
  `frontend` before fast-forwarding, per CLAUDE.md, and re-run the full check after.

## Cut order if red at the 06:00 check

1. Drop tsc-includes-tests (Step 0.2). 2. Drop bundle.test (keep the grep as a manual step
recorded in Results). 3. Drop the "act by" sublabel. Never drop: D1, D2, D3, the chip.

## Codex plan review — resolutions

Review: `docs/reports/2026-09-19_frontend-ux-plan-review.md` (6 findings, 3 critical).

1. **All-ruled-out wording (critical).** Verified with the oracle: all eleven out on the $200
   preset gives tier 3, empty plan, "$120.05 by Sep 24", yet the page would say "No changes
   needed". Fixed: `emptyPlanText(res)` is tier-aware (Step 3), used in `App.tsx` and
   `PrescriptionList.tsx` (Steps 4, 5), tested in `narrate.test.ts` and `fixtures.test.ts`,
   browser check 5. Observation for the backend lane, not fixed here: the oracle's certificate
   sentence in that case reads "No changes needed. The schedule already clears." It is never
   rendered (the proof box needs a non-empty plan), but it is a wrong string in the oracle.
2. **Tier-3 reason overclaims (critical).** Agreed. Wording reduced to what the first objective
   term establishes: "would not leave you fewer days below zero". Added the same-transaction
   reason so a candidate blocked by the one-per-transaction rule is not called useless (Step 2).
3. **Focusable chart inside aria-hidden (critical).** Verified in `node_modules/recharts`:
   `accessibilityLayer` defaults true and sets `tabIndex=0`. Fixed: `accessibilityLayer={false}`
   (Step 5) plus a Tab-order browser check.
4. **Focus lost when a row changes section.** Fixed: stable DOM id per checkbox and a
   post-response refocus effect (Steps 4, 5); browser check 7.
5. **Reasons from current overrides against a stale response.** Fixed: reasons use the override
   set the displayed response was solved with; rows whose override changed since show
   "Re-solving…" until the new response lands (Steps 4, 5); `pendingIds` unit-tested.
6. **Test order / silent skip.** Fixed: lint → build → test everywhere; `bundle.test.ts` fails
   without `dist/` (Steps 7, 9; run spec Commands).

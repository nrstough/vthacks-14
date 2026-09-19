# Run spec — frontend UX: one override control, reasons, narration, labels

Written Sat 2026-09-19 ~03:20. Branch `frontend`, worktree
`/Users/nathanstough/Desktop/vthacks-frontend`. Frozen after commit; append to Results only.
Pipeline: `/plan-review` (P1 frozen ~03:10 after two mockups, P2 frozen ~03:15, standard mode).

## Problem

The verdict, chart and proof box make the argument. The list of changes under them undercuts
it. Every one of the eleven rows carries a three-way control (Must do / Auto / Can't do) with
Auto pre-selected, so the page reads as if the user already answered "Auto" to eleven questions
nobody asked. The same control in the same state sits on both the rows the solver chose and the
rows it rejected, so one picture means "chosen" in one section and "rejected" in the other. The
control shows the user's input while positioned as the outcome.

The chart and the verdict have no text equivalent. The chart carries the whole argument and is
invisible to a screen reader. Best UI/UX is a judged track.

Unlabelled things: the disruption dots, the act-by dates, the left-out rows (no reason given
although the solver knows why), the footer in engineer's words.

## Scope

In: `frontend/src/App.tsx`, `components/PrescriptionList.tsx`, `components/VerdictBand.tsx`,
`components/BalanceChart.tsx`, `index.css`, three new pure modules under `src/lib/`, a Node
test suite under `frontend/tests/`, `frontend/package.json` (test script), `tsconfig.app.json`
(include tests), `docs/demo-script.md` (one beat), the new feature doc.

Out: `frontend/src/solver/mockSolver.ts` (the oracle; must stay byte-identical to `main`),
`frontend/src/types.ts` and `docs/api-contract.md` (backend lane), anything under `backend/`,
the fixture accounts, dark mode, bundle size, the header layout.

## Design decisions

- **D1 One control per row.** A checkbox labelled "Can't do this", unchecked by default, on
  every row in both sections, same position, same words. Checked adds the id to `locks.out`.
  `locks.in` is always `[]`; pinning is removed from the screen. The request shape is unchanged.
- **D2 Outcome is written, not implied.** Which section a row sits in is the outcome. Every
  left-out row carries one reason line. Reasons derive only from the response, the request's
  dates and the override set; never from money arithmetic (contract rule: the frontend renders
  what the solver returns). Precedence: ruled out > too late to act (lead time) > tier/proof
  > same transaction already used by a plan item > tier/proof wording. Tier 1/2 with
  `minimal_proven`: "Not needed. The plan already clears zero without it." Tier 1/2 unproven:
  "Not used in the plan shown. Whether it is needed was not proven; the solver ran out of
  time." Tier 3 proven: "Adding it would not leave you fewer days below zero" (exactly what the
  first objective term establishes; nothing about the size of the gap, since a deferral can
  shrink the dip while adding a day below zero). Tier 3 unproven: softened likewise. Reasons
  are computed against the override set the displayed response was solved with; a row whose
  override changed since reads "Re-solving…" until the new response lands. The mockup's "lands
  after the dip" reason is dropped: it is a claim the frontend cannot justify.
- **D2a Empty plan is tier-aware.** At tier 3 with no plan the heading is "No changes
  available" and the body "Everything is ruled out or too late to act. The gap stays." Never
  "No changes needed" at tier 3.
- **D3 Chart text equivalent.** A visible sentence group above the chart, derived from
  `balances` (first-day minimums of each series, paydays, change days) and, at tier 3, the
  response's own `shortfall` fields. The chart container is `role="img"` described by it; the
  SVG is hidden from assistive tech and Recharts' focusable accessibility layer is turned off,
  so nothing focusable sits inside `aria-hidden`. The verdict section is an
  `aria-live="polite"` region. Ticking a checkbox moves its row between sections; focus is
  restored to the same candidate's checkbox after the response arrives.
- **D4 Labels in words.** Date chips read "act by" on plan rows. Disruption reads "Disruption n
  of 5". Footer: "Exact solver, smallest plan proven" or "smallest plan not proven, the solver
  ran out of time"; "Solved in n ms"; "n changes considered". The fallback chip keeps its exact
  current text, "Running on the built-in solver", and its condition.
- **D5 Design system unchanged.** Same tokens, one accent, one font, 8px scale. No new
  dependencies. Two weights.
- **D6 Tests without a DOM.** Logic lives in pure modules (`overrides.ts`, `reasons.ts`,
  `narrate.ts`) tested by Node's built-in runner under `--experimental-strip-types`, the way the
  backend oracle harness already runs the TypeScript. Rendering is verified in the browser pane
  against the fixture canaries and recorded below.

## What will change

- `PrescriptionList.tsx`: `LockControl` and `LockState` go; a `CantDo` checkbox per row; reason
  line on left-out rows; "act by" on plan-row date chips; "Disruption n of 5".
- `App.tsx`: override state is a `Set<string>` of ruled-out ids via `overrides.ts`; request
  locks built from it; narration passed to the chart band; footer wording from `narrate.ts`.
- `BalanceChart.tsx`: `role="img"`, `aria-label`, `aria-describedby`; inner chart `aria-hidden`.
- `VerdictBand.tsx`: `aria-live="polite"`, `aria-atomic`.
- `index.css`: `.locks` styles replaced by `.cant`; `.rx-why`, `.rx-date small`, `.narration`,
  `.sr-only`; mobile block updated.
- New `src/lib/overrides.ts`, `reasons.ts`, `narrate.ts`; `tests/*.test.ts`; `npm test`.

## Acceptance criteria (each maps to a test)

| AC | Criterion | Test |
|---|---|---|
| AC1 | One identical control per row, unchecked by default; `locks.in` never sent | `overrides.test.ts`; browser check |
| AC2 | Demo beat: tick the card minimum on $200 preset gives 7 changes, card row in left-out with "You ruled this out" | `fixtures.test.ts` (7 changes via oracle); browser check |
| AC3 | Every left-out row shows a reason derived only from response, dates, overrides; precedence and boundaries right; no minimality claim when unproven or tier 3 | `reasons.test.ts` |
| AC4 | Chart has a text equivalent matching the verdict's tightest day; tier 3 says still under; ties pick the first day; screen reader reaches it | `narrate.test.ts`; browser `read_page` |
| AC5 | Act-by and disruption labelled in words | browser `read_page` |
| AC6 | Footer plain words; proof claim only when proven; chip text and condition unchanged | `narrate.test.ts` (footer fn); `bundle.test.ts` (chip string present); browser with backend down/up |
| AC7 | Built bundle contains neither "guarantee" nor "infeasib" | `bundle.test.ts` |
| AC8 | Oracle byte-identical to `main`; backend gate 977 | `git diff main -- frontend/src/solver/mockSolver.ts` empty; pytest |
| AC9 | Three fixture canaries unchanged on screen (tiers 1/2/3, plan sizes 3/3/9, Sep 24 $26.74) | `fixtures.test.ts`; browser |
| AC10 | Phone width holds: no overflow, control reachable | browser at 375px |
| AC11 | Empty plan at tier 3 never says "No changes needed"; says "No changes available" | `narrate.test.ts`, `fixtures.test.ts`; browser (all eleven ruled out) |
| AC12 | Focus stays on the toggled checkbox across the re-solve; Tab never enters the chart | browser keyboard check |
| AC13 | A left-out reason never describes a change against a response that did not see the current override; pending rows say "Re-solving…" | `overrides.test.ts` (`pendingIds`); code review |

Regression: backend count below 977, a canary value changing, the chip disappearing, a new
build warning, a forbidden word in the bundle, `mockSolver.ts` differing from `main`.

## Commands

```bash
cd /Users/nathanstough/Desktop/vthacks-frontend/frontend && export npm_config_cache="/Users/nathanstough/Desktop/VT Hacks/.npm-cache" && npm run lint && npm run build && npm test
```

```bash
cd /Users/nathanstough/Desktop/vthacks-frontend && .venv/bin/pytest backend/ -q -m "not perf"
```

## Docs committed to

- This run spec.
- `docs/features/frontend.md` (new, living).
- `docs/demo-script.md`: the 1:45 beat ("Click Can't do on the Pay the card minimum row" becomes
  ticking the checkbox) and its verification note; the "Refresh the two numbers" checklist item
  gains the new test count.
- `README.md`: conditional, only if the Test section should list `npm test`. Confirm at execution.

Not touched: `docs/api-contract.md`, `frontend/src/types.ts`, `mockSolver.ts`, `backend/`,
`CLAUDE.md`, the frontend UX handoff (a dated record).

## Codex plan review

`docs/reports/2026-09-19_frontend-ux-plan-review.md`, six findings, three critical, all
resolved in the plan (`docs/reports/2026-09-19_frontend-ux-plan.md`, "Codex plan review —
resolutions"): tier-aware empty state (D2a); tier-3 reason wording limited to the first
objective term plus a same-transaction reason (D2); Recharts accessibility layer off (D3);
focus restoration (D3); reasons against the solved override set with a pending state (D2);
check order lint → build → test with the bundle test failing, not skipping, without `dist/`.

## Results — executed Sat 2026-09-19, 03:26–03:45

Branch `frontend` in `/Users/nathanstough/Desktop/vthacks-frontend`. All ten plan steps ran in
order, no steps skipped, no cuts taken.

### Commands

| Command | Result |
|---|---|
| `npm run lint` (oxlint) | clean, no output |
| `npm run build` (`tsc -b && vite build`) | clean, 142 ms, 619.16 kB / 183.60 kB gzip |
| `npm test` (Node runner, no DOM) | **59 passed, 0 failed** |
| `.venv/bin/pytest backend/ -q -m "not perf"` | **977 passed**, 6 deselected, 5.27 s |
| `git diff main -- frontend/src/solver/mockSolver.ts` | empty: the oracle is byte-identical |
| `git diff main -- frontend/src/types.ts docs/api-contract.md backend/` | empty: contract and backend untouched |

Bundle grew 616.19 → 619.16 kB (+2.97 kB) for the three new modules and the reason strings. The
chunk-size warning is the pre-existing Recharts one; no new warning.

Test counts: overrides 10, reasons 20, narrate 16, fixtures 8, bundle 3, format 2.

### Acceptance criteria

| AC | Verdict | Evidence |
|---|---|---|
| AC1 | Met | 11 checkboxes, 0 checked on load; `toLocks` tests pin `in: []`; DOM shows `checkboxCount 11, checkedCount 0` |
| AC2 | Met | Ticking the card minimum: 3 → 7 changes, heading "7 changes…", card row in left-out reading "You ruled this out, so the solver never saw it.", "Clear 1 override" appears. Verified on the built-in solver AND against the live API |
| AC3 | Met | 20 reason tests; on screen every left-out row carries a reason at tiers 1, 2 and 3 |
| AC4 | Met | `.chart-wrap` is `role="img"`, `aria-describedby="chart-text"`; narration matches the qualifier on all three fixtures; tier 3 reads "still -$27.62 on Sep 24" |
| AC5 | Met | Rows render "ACT BY" and "Disruption 2 of 5" |
| AC6 | Met | Footer: "Exact solver, smallest plan proven / Solved in 3.6 ms / 11 changes considered". Chip present with the API down, absent with it up |
| AC7 | Met | `bundle.test.ts` greps the built JS: no "guarantee", no "infeasib", chip string present |
| AC8 | Met | See commands table |
| AC9 | Met | $200 → tier 1, 3 changes, Sep 24 $26.74; $180/$100 → tier 2; $60 → tier 3, 9 changes, $27.62 by Sep 24 |
| AC10 | Met | 375 px: `scrollWidth` 375, no horizontal overflow, checkbox fully in view, narration 327 px |
| AC11 | Met | All eleven ruled out → tier 3, heading "No changes available", body "Everything is ruled out or too late to act. The gap stays.", page text contains no "No changes needed" |
| AC12 | Met (one part structurally) | Focus stayed on `cant-c_card_min` across the re-solve that moved its row between sections. 11 checkboxes in the tab order, **0 tabbable elements inside `.chart-wrap`** |
| AC13 | Met | `pendingIds` unit-tested; the list renders "Re-solving…" whenever a row's override differs from the set the shown response was solved with |

### Deviations and limitations

1. **Keyboard activation could not be driven through the automation harness.** Synthetic key
   events produce no default action there — an arrow key on a native `<input type="range">` also
   failed to move it — so Space-to-toggle was verified structurally instead: the control is a
   native, enabled `input[type=checkbox]` with `tabIndex 0`, outside any `aria-hidden` subtree,
   with a correctly associated `<label for>`, and activation through `.click()` (the same path
   Space triggers) re-solves correctly. Tab order was computed from the DOM rather than walked.
2. **`frontend/tests/` is included in `tsconfig.app.json`** and the DOM/node type mix caused no
   conflict, so the Step 0.2 fallback was not needed.
3. **The `.claude/launch.json` route to a preview server was not usable.** The preview tool reads
   the MAIN checkout's config, which belongs to another session, so this worktree's Vite ran
   directly on port 5174 (`--strictPort`) and the browser was pointed at the URL. Port 5173 was
   left untouched throughout. The backend was started on 8000 only for the connected-path check
   and stopped immediately afterwards.
4. **Reason text repeats** when many left-out changes share a situation: eight rows read "Not
   needed. The plan already clears zero without it." on the $200 account. Accurate, and varying
   the wording for variety would make identical situations look different. Left as is.

### Found, not fixed here: a false claim in the certificate sentence

Ruling out the card minimum on the $200 account — **the demo script's 1:45 beat** — produces:

> "Remove Put off the gas fill to the 26th and you go under on Sep 24 by $8.82. The rest hold
> the cushion."

Three of the seven changes are load-bearing, not one: `c_dd_chipotle` (marginal $3.57, +1 day
below zero), `c_gym` ($6.76, +2 days) and `c_shell_defer` ($8.82, +1 day). "The rest hold the
cushion" is false for two of them. The per-row reasons are correct and do say which, so the
contradiction is between the headline sentence and the rows beneath it.

The string is the solver's, not the UI's — `docs/api-contract.md` states the certificate
sentence is rendered verbatim — and it is **identical in both implementations**:
`backend/app/solver/wording.py:97-102` and `frontend/src/solver/mockSolver.ts:293-298`. Both are
outside this lane, and `mockSolver.ts` is the parity oracle, so nothing was changed. Recorded
here for the backend lane. `tests/fixtures.test.ts` deliberately asserts only that the sentence
is non-empty, so this run does not pin the defect in place. The demo script now carries a
one-line fallback answer if a judge reads the box closely on Sunday.

## Audit round 1 (adversarial Claude critique, ~03:50) — **Fail**, twelve findings

Test coverage and Documentation both graded Fail. All findings addressed; the substantive ones
are below with what was verified before and after.

1. **`tests/bundle.test.ts` could not read the bundle in the real checkout (Fail driver).**
   `new URL(...).pathname` percent-encodes a space, and the canonical checkout is
   `/Users/nathanstough/Desktop/VT Hacks`. The suite passed here only because this worktree's
   path has no space; merged to `main` it would have errored 3/3 and the AC7 forbidden-word
   gate would never have run. Fixed with `fileURLToPath`, and **reproduced both ways**: copied
   under `/tmp/space test dir/` it failed with `ENOENT … VT%20Hacks …` before the fix and
   passes 3/3 after.
2. **`docs/features/frontend.md` documented the tier-3 wording Codex finding 2 removed** ("would
   not shrink the gap or lift another day above zero"). The doc was written before the review
   resolutions and never updated. It now states the shipped wording and why the stronger claim
   is false.
3. **The same doc gave the check order finding 6 exists to forbid** (`lint && test && build`).
   Corrected to lint → build → test, with the reason spelled out.
4. **The same doc repeated "only the gas deferral is strictly needed"**, which this change's own
   `fixtures.test.ts:47` disproves: three of the seven are load-bearing. Corrected, and the doc
   now carries the certificate-sentence defect and its fallback.
5. **The documented reason precedence omitted `same_txn` entirely** — the reason added to
   resolve finding 2. A developer extending the module against the doc could have shadowed it,
   making blocked candidates read "Not needed". Precedence corrected to the six shipped steps.
6. **`pendingIds` was exported, unit-tested, and never called** (AC13 cited it as evidence).
   `PrescriptionList.tsx` now uses it, so the cited test covers the shipped path.
7. **Focus restoration stole focus.** The effect fired on every response, so a user who tabbed
   on during the debounce was yanked back. Now it restores only when focus was lost to the
   document body. Verified in the browser: focus stays put → restored to `cant-c_card_min`;
   focus moved to `cant-c_gym` first → stays on `cant-c_gym`.
8. **Plan rows had no pending state** — the mirror of finding 5. Ticking a chosen row left it in
   the plan section still showing the solver's reason for picking a change the user had just
   said they cannot do. Plan rows now show "Re-solving…" too. Verified: 60 ms after ticking, the
   row has `is-pending` and reads "Re-solving…"; after the response, no pending rows remain.
9. **D2's precedence sentence in this spec is garbled** — it prints "tier/proof" twice, putting
   the tier branch ahead of `same_txn`. The plan and the code both order it ruled_out >
   too_late > same_txn > tier, and the code is correct. Recorded here rather than editing D2,
   because the spec is frozen after commit.
10. Stale strings in the feature doc (an old reason quote, the pre-change bundle figure):
    corrected.
11. **The aria-live chatter risk the plan flagged was never measured.** Now measured: a
    13-step slider drag produced **one** live-region change, because the request is debounced
    and applied once. No fallback needed.
12. **`.sr-only` appears in this spec's "What will change" but was never added.** Struck: the
    narration is visible text, so the class had no use. No other listed file was left unwritten.

Not accepted as defects: the browser-only evidence for AC5, AC10 and the on-screen halves of
AC2/AC9 is reported honestly in Deviations and is inherent to having no DOM test runner
installable on this connection; the critique records the same limitation rather than disputing
it.

### Re-run after the fixes

| Command | Result |
|---|---|
| `npm run lint` | clean |
| `npm run build` | clean, 619.45 kB / 183.67 kB gzip, pre-existing Recharts warning only |
| `npm test` | **59 passed, 0 failed** |
| `.venv/bin/pytest backend/ -q -m "not perf"` | **977 passed** |
| `tests/bundle.test.ts` under a path containing a space | **3 passed** (failed 3/3 before the fix) |
| oracle / types / contract / backend diff vs `main` | empty |

## Audit round 2 (same critique agent, re-checking its own findings, ~04:05) — **Acceptable**

All twelve round-1 findings verified resolved against the files, not the claims; the agent
re-reproduced the space-path test both ways (0/3 before, 3/3 after) and re-ran the full suite.
Both Fail dimensions cleared: Test coverage and Documentation → Acceptable, Freeze integrity and
Regression check → Excellent. Three new findings, all judged non-material by the agent; all three
were fixed anyway, and one of them turned out to hide two further real defects.

1. **`is-pending` was applied to plan rows only**, not left-out rows, so the two sections were
   styled asymmetrically although both showed "Re-solving…". Class now applied in both.
2. **Pinning styles orphaned by D1** — `.rx-row.is-pinned`, `@keyframes land-pinned`, `.tag`,
   `.tag-out` — nothing could match them once the three-way control went. Removed; the CSS
   bundle drops 9.16 → 8.59 kB. They would have told a later reader that pinning still exists.
3. **The tier-aware empty state was undocumented** in the feature doc although it is the fix for
   Codex critical finding 1 and a hard wording rule. Added, with the case that produces it.

### Two defects found while fixing the focus edge

The agent also reported a residual focus edge: tabbing onto a row that the *same* re-solve moves
leaves focus restored to the toggled row instead of following the user. Fixing it properly
exposed two more problems, both caught by verifying rather than assuming:

- **Tracking focus only through React's `onFocus` broke restoration entirely** in the automation
  pane, because the document there is not focused and focus events never fire. Case A regressed
  from "restored" to "focus lost" and the browser check caught it. The ref is now fed by **both**
  signals: the toggle records where focus is at the moment of the change (works without focus
  events), and `onFocus` keeps it current if the user tabs on.
- **The ref persisted across interactions.** Safari does not focus a checkbox when you click it,
  so a later re-solve could have pulled focus to whichever row was focused last, minutes earlier.
  The ref is now consumed once per response.

Focus behaviour, all four cases verified in the browser after the fix:

| Sequence | Result |
|---|---|
| Focus a row, toggle it, its row moves sections | restored to that row |
| Focus a row, toggle it, tab to a row that survives | stays where the user went |
| Activate without focusing, after an earlier focus elsewhere | nothing grabbed (focus stays on body) |
| Focus a row, then drag the slider | stays where the user went |

### Final run

| Command | Result |
|---|---|
| `npm run lint` | clean |
| `npm run build` | clean, 619.53 kB JS / 8.59 kB CSS |
| `npm test` | **59 passed, 0 failed** |
| `.venv/bin/pytest backend/ -q -m "not perf"` | **977 passed** |
| oracle / types / contract / backend diff vs `main` | empty |

### Still open, by choice

`AC12`'s keyboard half and the focus cases are verified by browser observation, not by an
automated test, because no DOM test runner can be installed on this connection. The four cases
above are written down so they can be re-checked by hand, or turned into tests the moment a
runner is available. The test count stays at 59.

## Codex audit (~04:15) — **Fail**, three real findings the Claude critique missed

Full output: `docs/specs/2026-09-19_frontend-ux-audit.md`. Scope discipline, Freeze integrity and
Documentation graded Excellent; Plan adherence and Test coverage Fail. All three findings are
genuine, were reproduced before fixing, and each now has a regression test. Test count 59 → 66.

1. **The narration called two changes one change.** `narrate.ts` picked the singular by counting
   the number of *dates* changes fell on, not the number of changes. Two changes landing on one
   day read "One change takes effect, on Sep 22." Reachable on the shipped $200 account's
   candidate set, where `c_dd_chipotle` and `c_gym` both take effect on Sep 22, but **not** in
   its default state and **not** on the demo script's one-override beat: a later sweep of all
   2,048 override states across the three presets found the false singular in 31 of 6,144,
   every one of them needing eight or nine of the eleven changes ruled out. The correction below
   replaces an earlier sentence in this section that said it "fires on the shipped $200 demo
   account", which overstated the reach — someone replaying the demo would see correct plural
   narration and conclude the finding was invented. The bug and the fix are both real; only that
   sentence was wrong. Now counts `changes_here` entries.
   Three tests, including one asserting the fixture genuinely lands two changes on one day.
2. **Restoring focus re-armed the reference it had just consumed.** The programmatic `.focus()`
   dispatches the checkbox's own focus event, which wrote the id straight back through
   `onFocusRow`, defeating the consume-once fix from round 2. Codex derived this from the event
   path without being able to replay it; it is correct, and it is invisible in this automation
   pane because the document there is never focused. A `restoring` flag now suppresses tracking
   for the duration of the restore.
3. **"Act by" was false for every change that needs notice.** This round's own new label put
   "act by" under the date the change *takes effect*, but `lead_time_days` means the change must
   be actioned that many days ahead. The gym bills on Sep 22 and needs three days, so the
   deadline is **Sep 19**; the screen said Sep 22. Someone following it would miss the
   cancellation and lose the plan — the exact class of false claim this project refuses
   elsewhere. The date chip now says "takes effect", which is what `plan[].date` actually is, and
   a row that needs notice carries its real deadline: "Act by Sep 19: it needs 3 days of
   notice." Verified on screen. The section heading became "in the order they take effect",
   because the plan is ordered by effect date and "the order you have to make them" is a
   different order once lead times differ.

Contract note for the backend lane, not changed here: `docs/api-contract.md:58` describes
`plan[].date` as "the day the user must act", but both solvers return `effective_date`. The
frontend now derives the deadline itself from `lead_time_days`, which is dates-only arithmetic
and touches no money. If the backend later returns a true deadline field, this derivation should
be replaced by it.

Deviation from D4, recorded rather than hidden: D4 said the date chip reads "act by". It reads
"takes effect", because "act by" there was false. The deadline is still shown, on the rows that
have one.

### Focus behaviour re-verified after the fix

| Sequence | Result |
|---|---|
| Focus a row, toggle it, its row moves sections | restored to that row |
| Focus a row, toggle it, tab to a row that survives | stays where the user went |
| Activate with no prior focus, after an earlier restore | nothing grabbed |
| A restore, then a second unrelated re-solve | nothing grabbed the second time |

### Final run

| Command | Result |
|---|---|
| `npm run lint` | clean |
| `npm run build` | clean, 620.07 kB / 183.85 kB gzip |
| `npm test` | **66 passed, 0 failed** |
| `.venv/bin/pytest backend/ -q -m "not perf"` | **977 passed**, 6 deselected |
| oracle / types / contract / backend diff vs `main` | empty |

On the audit's own regression note: it measured 976 passed and 1 setup error, because its
sandbox is read-only and one test needs a writable temporary directory. Run normally in this
worktree the suite is 977 passed, reproduced after every commit in this run.

## Codex re-audit (~04:25) — **Fail**, two further focus defects, both real

Full output: `docs/specs/2026-09-19_frontend-ux-audit.md` (overwritten per round). The three
findings from the first Codex round were accepted as fixed. Two new ones, both source-traced
rather than reproduced by the auditor, and both correct:

1. **A restored checkbox inside the collapsed "other changes" section cannot take focus.** If the
   user collapses that section and then toggles a plan row, the row lands inside a closed
   `details`, and nothing inside one is focusable. Reproduced in the browser: focus went to the
   body. The restore now opens the section first. Re-checked: focus lands on the row and the
   section is open.
2. **A quick tick-and-undo lost focus on the second response.** The first response restored focus
   and consumed the remembered row; the second moved the row back with nothing left to restore.
   The memory is now kept until the answer on screen matches the user's current input.
   Reproduced and re-checked: focus ends on the toggled row, plan back to 3 changes.
3. **The focus rules had no tests** — correct, and the reason was that they were tangled up in a
   React effect. They now live in `src/lib/focus.ts`, apart from React, with **9 unit tests**
   covering every rule including both defects above. Test count 66 → 75.

A regression was caught while fixing 2, by re-running the earlier cases rather than assuming:
adding `ruledOut` and `solvedRuledOut` to the effect's dependencies made it run at the moment of
the toggle, while the row was still mounted, and throw the remembered row away before the
response that unmounts it arrived. Case A went from "restored" to "focus lost". The effect is
keyed on the response alone, with a comment saying why.

Stale figures the audit flagged, both corrected: the demo checklist's test count and the feature
doc's bundle size.

### Focus behaviour, all six sequences re-verified after the fixes

| Sequence | Result |
|---|---|
| Focus a row, toggle it, its row moves sections | restored to that row |
| Focus a row, toggle it, tab to a row that survives | stays where the user went |
| Activate with no prior focus, after an earlier restore | nothing grabbed |
| A restore, then a later unrelated re-solve | nothing grabbed |
| "Other changes" collapsed, then toggle a plan row | section opened, focus restored |
| Tick, then undo inside the debounce | restored, plan back to 3 changes |

### Final run

| Command | Result |
|---|---|
| `npm run lint` | clean |
| `npm run build` | clean, 620.51 kB / 184.04 kB gzip |
| `npm test` | **75 passed, 0 failed** |
| `.venv/bin/pytest backend/ -q -m "not perf"` | **977 passed**, 6 deselected |
| oracle / types / contract / backend diff vs `main` | empty |

## Claude critique, final pass (~04:05) — **Acceptable**

Run as the standing gate after Codex hit its usage limit part-way through a third pass. Scope
discipline, Review compliance, Freeze integrity and Regression check graded Excellent; Plan
adherence, Test coverage and Documentation Acceptable; nothing material outstanding. The agent
re-derived the act-by arithmetic independently across month, year and leap boundaries, swept all
2,048 override states per preset to establish the narration bug's true reach, confirmed the
heading matches the oracle's sort order, and drove five focus sequences live including three not
recorded here. Three findings, all handled:

1. **`focus.ts` said one thing and did another.** The comment and the test name said the rule
   keeps the row the user is standing on; the code returned the remembered row instead. Safe
   only because a second mechanism kept the two in step. Fixed so all three agree: the row is
   read from the DOM at toggle time, which also means the rule holds where focus events never
   fire. `armOnToggle` no longer takes the previous value at all.
2. **This spec overstated the narration bug's reach** — corrected in place above, with the sweep
   numbers.
3. **The CSS figure drifted** by 0.08 kB after `.rx-notice` — corrected.

### Recorded honestly, not fixed: one path cannot be exercised here

`onFocusRow` in `App.tsx` never runs in the verification pane. The agent established why:
`document.hasFocus()` is false there and `visibilityState` is hidden, so calling `.focus()`
updates `activeElement` without dispatching a single focus event. None of the recorded browser
sequences can have exercised it, and `focus.test.ts` covers the pure rules rather than the
wiring. The visible consequence, measured: toggle a row, then move to a row that the *same*
re-solve promotes, and focus returns to the row that was toggled rather than following the user.
In a real browser `onFocusRow` would have updated the remembered row first. That cannot be
confirmed from here, so it is written down as unverified rather than claimed. The failure mode
is focus landing in the wrong place, never a wrong number or a wrong date.

Fixing finding 1 narrows this: the remembered row is now read from the DOM on every toggle, so
`onFocusRow` only matters when focus moves **without** a toggle following it.

### For the backend lane, alongside the contract note

`frontend/src/solver/mockSolver.ts` comments its plan sort as "Sort by the day you must act",
which is the same effective-date-versus-deadline conflation this round fixed in the UI, in a
protected file. Untouched.

### Final run

| Command | Result |
|---|---|
| `npm run lint` | clean |
| `npm run build` | clean, 620.50 kB JS / 8.67 kB CSS |
| `npm test` | **75 passed, 0 failed** |
| `.venv/bin/pytest backend/ -q -m "not perf"` | **977 passed**, 6 deselected |
| oracle / types / contract / backend diff vs `main` | empty |
| Focus sequences re-checked after the fix | all six as recorded above |

## Codex audit, third pass (~04:10) — **Fail**, two findings, both real

Ran after the usage limit reset. Scope discipline, Freeze integrity and Documentation graded
Excellent; Plan adherence, Test coverage and Review compliance Fail on one focus defect and its
missing test. Both findings accepted and fixed.

1. **Overlapping responses could lose focus for good.** `decideRestore` forgot the remembered row
   whenever focus survived a response, regardless of whether newer input was still pending. An
   older response landing inside a newer toggle's 150 ms debounce leaves the row mounted, so
   nothing is restored — and the row was forgotten, so when the newer response moved it there was
   nothing left to focus. The rule is now: restore only focus that was lost, and forget the row
   only once the answer on screen matches what the user last asked for. Two tests added,
   including a three-response walk of the exact sequence. Verified in the browser with three
   toggles inside the debounce: focus lands on the toggled row, plan at 7 changes.
2. **The empty-plan wording overclaimed.** "Everything is ruled out or too late to act" is false
   when changes remain on the table and simply do not help. Rule out all but Netflix on the $200
   account: it is actionable, it just takes effect on Sep 29, after the Sep 24 dip, so the plan
   is empty at tier 3 with one candidate considered — and the user can see the row sitting there.
   The wording now splits on `meta.candidates_considered`: nothing considered keeps the original
   sentence; changes still on the table get "No change helps here" / "None of the changes still
   on the table would leave you fewer days below zero", which is what the first objective term
   establishes, matching the tier-3 reason wording. An unproven solve gets a softer form. Four
   tests added, one driving the real oracle. Both verified on screen.

**Correction to D2a**, recorded here rather than editing frozen text: D2a gave a single tier-3
empty-plan wording. There are two cases, and the one it specified is only correct when nothing
was on the table at all.

Test count 75 → 81.

### Focus behaviour, seven sequences after this fix

| Sequence | Result |
|---|---|
| Focus a row, toggle it, its row moves sections | restored to that row |
| Focus a row, toggle it, tab to a row that survives | stays where the user went |
| Activate with no prior focus, after an earlier restore | nothing grabbed |
| A restore, then a later unrelated re-solve | nothing grabbed |
| "Other changes" collapsed, then toggle a plan row | section opened, focus restored |
| Tick, then undo inside the debounce | restored, plan back to 3 |
| Three toggles inside the debounce, overlapping responses | restored, plan at 7 |

### Final run

| Command | Result |
|---|---|
| `npm run lint` | clean |
| `npm run build` | clean, 620.76 kB / 184.10 kB gzip |
| `npm test` | **81 passed, 0 failed** |
| `.venv/bin/pytest backend/ -q -m "not perf"` | **977 passed**, 6 deselected |
| oracle / types / contract / backend diff vs `main` | empty |

On the audit's backend count: it measures 976 passed and 1 setup error every round, because its
sandbox is read-only and one API test needs a writable temporary directory. Run normally here the
suite is 977 passed.

### Still open, and why

AC12's keyboard activation is still verified by structure and by driving the controls
programmatically, not by real key events: this pane reports `document.hasFocus()` false, so
synthetic keys produce no default action and React focus events never fire. An arrow key on a
native range input does nothing here either, which is how that was established. The focus rules
themselves are now pure functions with 11 tests; what remains unexercised is the wiring between
them and React's events.

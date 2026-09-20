# Run spec — UI: drop the wallet, one surface, the explainer behind its own pill

Written Sat 2026-09-19 ~22:00. Branch `ui-design-system`, worktree
`/Users/nathanstough/Desktop/vthacks-ui`, clean at `bac3f73`. Frozen after commit; append to
Results only. Pipeline: `/plan-review`, started at P1 (P1 frozen ~21:20, P2 frozen ~21:55,
deep mode).

P1 was re-derived from scratch rather than inherited. The previous session's handoff
(`docs/handoffs/2026-09-19_ui-tabs-and-no-wallet-handoff.md`) recorded a P1 as "already frozen
by Nathan"; Nathan had not read it. That P1 proposed three tabs and moving the sliders into the
hero. Both were reopened and one was reversed — see D7.

## Problem

Three things, one screen.

**The wallet is dead weight.** Solana was dropped from the project. The app still carries a
"Demo wallet" pill leading to a view we do not want to talk about, that can fail in front of a
judge, and that costs a lazy chunk, its own error boundary, 110 tests and 34 stylesheet rules
(41 selectors) to keep alive.

**The page does not read as one page.** Measured at `bac3f73` in headless Chrome: 2,563px tall
at 1440 wide, 5,674px at 390. It is a hero plus four cards in two columns, which makes the eye
read a Z. About 845px of that height — a third of the page — is the left-out change list,
rendered open by default.

**The explainer is in the way of the thing being judged.** It holds half the bottom row, it is
the only panel that cannot work without a network key, and it appears nowhere in the
four-minute demo script. It is something judges may probe, not something presented.

## Scope

In: deleting the wallet; the nav pills; moving `ChatPanel` behind a pill; the plan list going
full width; the left-out list's default collapse and its auto-open rule; the docs those touch.

Out, deliberately: the hero, the verdict, the proof box, the stat tiles, the sliders, the
scenario switcher, the account-source buttons, the chart, the gradient, `.controls`, the
solver, the backend, and anything under `docs/` that records Solana history.

Not attempted: merging to `main`. `main` is checked out in `Desktop/vthacks-integrate` and has
not moved ahead of this branch; per CLAUDE.md that session is asked before any fast-forward,
and memory records merges and pushes as on hold.

## Design decisions

**D1 — Delete the wallet, do not hide it.** Solana is gone from the project; a hidden view is
still code that can break and still ships strings a judge can find.

**D2 — Two pills, Plan and Ask. Plan is the default.** The entire four-minute script runs on
Plan without a single click. Ask exists for judges who probe.

**D3 — Ask replaces the main area, the way the wallet did.** Not a panel beside the plan, and
not a third tab under a permanent hero. This reuses the branch already in `App.tsx` rather than
inventing a layout.

**D4 — `ChatPanel` is always mounted and hidden with the `hidden` attribute; the planning view
stays a conditional render.** The asymmetry is the point and is the single most important
decision here. `ChatPanel` owns `messages`, `draft`, `pending`, `error`, `state`, `model`, an
in-flight `AbortController` and a mount-time call to the rate-limited `/api/chat/status`.
Unmounting it loses a judge's conversation and re-spends a limited endpoint. Nothing else on
the page owns state that a remount would destroy.

**D5 — The chart is never hidden-but-mounted.** It unmounts with the planning view. `BalanceChart`
renders a Recharts `ResponsiveContainer width="100%"`, which sizes from its parent; inside a
`display: none` subtree that parent is 0×0 and correct rendering then depends on a
`ResizeObserver` firing on reveal. Unmounting removes the failure mode instead of managing it.
This repo has already been bitten nearby — `.chart-panel .chart-wrap { min-height: 0 }` exists
because of a chart resize growth loop.

**D6 — Hiding uses the `hidden` attribute, never a CSS class — and `hidden` alone is not
enough here.** `ChatPanel`'s log is `role="log" aria-live="polite"`. A live region hidden only
by CSS is ambiguous across screen readers; `hidden` takes it out of the accessibility tree.
But the architecture sweep found that `hidden` on `ChatPanel`'s own root would not hide it:
`index.css:468` declares `.panel { display: flex }`, an author declaration that beats the
user-agent's `[hidden] { display: none }`. `ChatPanel` returns its own
`<section className="panel chat-panel">`, so the panel must be wrapped in an element that
carries `hidden` (no author `display` targets it), rather than passing `hidden` down to that
section. Writing the attribute and assuming it works is the bug this decision exists to
prevent.

**D7 — The sliders do NOT move into the hero.** This reverses the inherited plan. The sliders
already sit beside the chart in the same row; lifting them into the hero would put them next to
the verdict but push the chart below them, making "drag a slider and watch it all move" worse,
not better. Leaving them also avoids three consequences that plan carried: the hero's
`key={`tier-${res.tier}`}` would remount a range input mid-drag when a drag crosses a tier
boundary, killing the demo's best interaction; the gradient's hand-tuned `460px` / `620px`
heights would need re-measuring; and `.controls-panel`'s rules would need rehoming without
tripping the "`.controls` declared exactly once" pin.

**D8 — The tier-3 alarm dot stays, on the Plan pill.** Under D3 the verdict is off screen while
Ask is showing, so the dot recovers the job it does today: telling you the other tab is an
alarm.

**D9 — The left-out list starts collapsed, opens when the user rules something out, and closes
on reset. Its open state is React state owned by `App`, controlled, with `onToggle` syncing the
user's own clicks back.** Collapsed it removes ~845px, and the summary line still says eleven
changes were considered and three chosen, which is a claim worth making. The auto-open is what
protects the demo's 1:45 beat: the row the judge just ruled out must be seen landing in the
list, not vanishing.

This reverses the "uncontrolled, opened imperatively" position taken before the deep pass. Both
sweeps showed that plain-uncontrolled and plain-controlled each fail:

- **Plain controlled desyncs.** React never observes a native `<details>` toggle. Rule out row
  A (state true, DOM opens) → user collapses by hand (DOM false, React still true) → rule out
  row B (state true → true) → React diffs true against true, writes nothing, and the section
  stays shut with the row moving somewhere invisible.
- **Plain uncontrolled cannot survive a tab switch.** The planning view unmounts on Ask (D3),
  so open state living in `PrescriptionList` resets to collapsed on every return, and the row
  the judge just ruled out vanishes again.

Controlled state in `App` plus `onToggle` fixes both: `App` survives the tab switch, and the
toggle event fires for programmatic changes as well as clicks, so the existing imperative
`section.open = true` in the focus-restore effect (`App.tsx:149-150`) syncs itself back into
React instead of fighting it.

The Safari path makes this load-bearing rather than tidy. `armOnToggle` returns `null` when a
checkbox is activated without being focused, which is the documented Safari mouse-click case,
so the imperative open never runs there and **the D9 rule is the only thing keeping the moved
row visible**. The demo script's payoff line — "The card row then moves down to the left-out
list and says you ruled it out" — is a claim made to a judge's face about a list that would
otherwise not be on screen. Tick → manual collapse → tick a second row is a required test.

**D10 — Tabs are buttons with `aria-current`, not an ARIA `tablist`.** A real tablist owes
roving tabindex, arrow-key navigation, `aria-selected` and `aria-controls`; a half-built one is
worse for screen-reader users than honest buttons in the existing `<nav aria-label="Views">`.

**D11 — Three rules move into pure modules so they can be tested without a DOM.** The project
forbids DOM in the suite. `src/lib/tabs.ts` (tab type, default, plan visibility, which pill owns
the dot), `src/lib/considered.ts` (the open/close/leave decision), and a `planVisible` guard
added to `src/lib/focus.ts`.

**D12 — The wallet-specific style pin is retired with a note and replaced by its inverse.** The
sixth responsive pin asserts the wallet keeps its own card on the gradient. It becomes a pin
that no `.wallet` selector survives anywhere in the stylesheet, carrying a comment that records
what it replaced and why.

**D13 — The `planVisible` guard keeps the remembered row; it does not forget it.** P1 and P2
both said "do nothing and forget". The architecture sweep showed that is the existing defect,
not the fix: `App.tsx:142` runs `if (decision.clear) focused.current = null` *before* the early
return on `:143`, and `clear` is simply `settled`, so a response landing while the user is on
another tab already discards the row. The guard therefore returns `{ focus: null, clear: false }`
and is placed after the `!refId` check, so the row survives an out-of-view response. This is
safe against a surprise focus jump because the restore effect is keyed on `[res]` alone — it
does not re-run on a tab switch, only when a new answer arrives.

Cost, recorded because it will show up in the diff: `planVisible` is a required field on
`RestoreInput`, so all eleven existing `decideRestore` call sites in `focus.test.ts` must be
updated. That is intended — it forces every existing case to state which side of the guard it
is on.

**D14 — A `[hidden] { display: none !important }` shim, pinned.** `hidden` does not hide
anything wrapped in a `.panel`, because `index.css:468` declares `display: flex` and an author
declaration beats the user-agent's `[hidden]` rule at any specificity. Verified on the running
app: with `hidden` set, the chat panel still computed `display: flex`, `clientHeight: 363`, a
non-null `offsetParent` and **six focusable descendants left in the tab order** — which would
have silently taken the documented eleven tab stops on the Plan tab to seventeen. The fix is
the shim plus a wrapper element carrying the attribute, and both a style pin and a browser
assertion that the panel computes `display: none` on the Plan tab. Nothing in the original P2
could have caught this: pure modules cannot see the cascade, and the bundle greps cannot
either.

**D15 — The chart is conditionally rendered inside the planning view, not merely hidden with
it.** D5's reason stands, and this states the mechanism: `{tab === 'plan' && <BalanceChart …/>}`
so the `ResponsiveContainer` is never mounted at 0×0.

**D16 — Accepted limitations, decided rather than overlooked.** The planning view stays a
conditional render (D3), which costs two things we are choosing to accept:

- The mount-only entrance animations (`.main > * { animation: rise }`, the stat sweep, the
  verdict rise) replay on every return to Plan, and so does the chart, which sets
  `isAnimationActive` with `animationDuration={350}`. Cosmetic, roughly 180–350ms of
  re-assembly, and the script never leaves Plan. The one part that is *not* acceptable is
  `.rx-row.is-new`, which would re-flash rows as new that are not. Clearing `newIds` on the
  way out of Plan does not achieve that — the solve effect keeps running while Ask is showing
  and `apply()` repopulates it — so the suppression lives inside `apply()` itself.
- `VerdictBand` is `aria-live="polite" aria-atomic="true"`, so remounting it *may* cause some
  screen readers to read the entire verdict on each return to Plan. The critique pass judged
  this a conservative worry rather than a demo problem — a freshly inserted live region's
  initial content is generally not announced by NVDA or JAWS. Recorded so it is not mistaken
  later for a regression in the live-region chatter this project measured and cleared.

- **Scroll position across a tab switch is not preserved.** Switching to Ask collapses `.main`
  to two children, the document shrinks, the browser clamps the scroll offset, and returning
  to Plan lands wherever that clamp left it. Measured as part of browser check 10 rather than
  assumed harmless.

The alternative — mounting the planning view always and hiding it too — removes both, but
requires wrapping it in an element that then has to reproduce `.main`'s flex column, its gap
and its `nth-child` stagger, and would put the load-bearing `.main > * { flex: none }` pin
(itself the fix for a past bug where the hero was crushed to 66px) onto a wrapper instead of
the hero. That is more surgery than the two costs justify at this hour.

**D18 — One checkbox label everywhere, never ticked by default.** Added during execution,
after Nathan saw the finished left-out list at full width. Every row on the page now reads
"Can't do this", starts empty, and means one thing when ticked: the user ruled it out.

This reverses `e61d087`, landed earlier the same evening, which gave the left-out list the
opposite question — "Can do this", starting ticked — on the sound logic that a change the
solver did not need is still one you could do. On screen that put **eight blue checkmarks
directly under a heading saying those changes had been LEFT OUT**. A tick reads as "chosen"
before anyone reaches the label, so the two readings did not disambiguate each other; the
heading and the ticks simply contradicted one another eight times.

Worse, the one row that *was* ruled out appeared as the single **empty** box in a column of
ticks — exactly backwards from how a checkmark reads.

The distinction was removed rather than explained better. `controlFor` loses its `section`
parameter entirely (`noUnusedParameters` is on, so there is no half-measure), and which
section a row sits in is now carried only by the heading and the reason line, which is where
the solver's answer belongs. The checkbox carries the user's constraint and nothing else.

The older bug both versions descend from is still avoided: a single visual state meaning
"chosen" in one list and "rejected" in the other. One label over one meaning prevents it.
Two labels over two resting states was an over-correction.

**D17 — The footer gets an explicit animation delay.** `.main`'s children go from four to five
once the hidden chat wrapper is added, and a `display: none` child still counts for
`:nth-child`, so the footer would inherit no delay and animate in before the hero.

## What will change

Deleted: `frontend/src/wallet/` (8 files); `frontend/tests/wallet-{ledger,receipt,state,units,view}.test.ts`
(5 files, 110 tests); the `.wallet*` rules in `frontend/src/index.css` — two contiguous blocks
at 1110–1250 and 1436–1500, plus one selector inside the shared transition rule at 1340–1354
whose removal leaves a trailing comma to clean up on the preceding line, and two stale comments
at 185–186; the lazy `WalletView` import, the wallet branch, its
`ErrorBoundary inline={…}` and its `Suspense` in `frontend/src/App.tsx`; the "Demo wallet" pill
in `frontend/src/components/TopNav.tsx`.

Added: `frontend/src/lib/tabs.ts`, `frontend/src/lib/considered.ts`, and their test files.

Changed: `frontend/src/App.tsx` (tab model, chat always mounted and hidden, planning view
conditional, the `.duo-start` row becomes the full-width plan panel, the auto-open effect);
`frontend/src/components/TopNav.tsx` (two pills, the dot on Plan); `frontend/src/components/PrescriptionList.tsx`
(the `<details>` becomes controlled); `frontend/src/components/ChatPanel.tsx` (a `visible`
prop, so the log re-scrolls when the panel is revealed — added after the critique found the
run spec had an acceptance criterion and a named risk for this with no file authorised to
change); `frontend/src/lib/focus.ts` (`planVisible`);
`frontend/src/index.css` (`.duo-start` and the sticky chat rule go, the plan panel goes full
width, the chart row's `.duo` is untouched); `frontend/tests/styles.test.ts` (D12);
`frontend/tests/bundle.test.ts` (new string pins); `frontend/tests/focus.test.ts` (the new
counterfactual); `frontend/scripts/shoot.mjs` (it currently clicks "Demo wallet").

Conditional, confirmed at execution: whether `ErrorBoundary`'s `inline` prop has any caller
left once the wallet is gone, and therefore whether it is removed.

## Acceptance criteria (each maps to a test)

1. No route from the UI reaches Solana, and no wallet string survives in the built bundle —
   new `bundle.test.ts` pins for `/solana/i` and the wallet view strings.
2. No `.wallet` selector survives in the stylesheet — the D12 replacement pin in `styles.test.ts`.
3. Pills read Plan and Ask; Plan is the default; the tier-3 dot belongs to the Plan pill —
   `tabs.test.ts`.
4. The conversation survives tab switches, and `/api/chat/status` is called once across several
   switches — browser-verified; the suite has no DOM.
5. The left-out list starts collapsed, opens when the user rules something out, and closes on
   reset — `considered.test.ts`, counterfactual on each of the three transitions.
6. Focus is restored only when the plan list is showing, **and the remembered row survives** a
   response that lands while it is not — `focus.test.ts`, two counterfactuals: `planVisible:
   false` restores nothing, and the same case must report `clear: false` (per D13). A test that
   only checked `focus === null` would pass against the existing defect.
10. The `minmax(0, 1fr)` pin still finds at least six tracks after `.duo-start` collapses —
   `styles.test.ts:159`. Both sweeps flagged this as the pin most likely to trip; it must be
   recounted against the edited stylesheet, not assumed.
7. The Plan tab is materially shorter than 2,563px at 1440 wide — measured screenshot.
8. Every CLAUDE.md wording commitment still holds: the offline disclosure chip is present on
   both tabs, and no banned word enters the bundle — existing `bundle.test.ts` pins plus a
   browser check on both tabs.
9. The frontend suite is green at its new floor plus the new tests; the backend suite does not
   move from 2,165 and `test_parity` does not skip. The floor arithmetic, corrected by the
   file-impact sweep: 292 today − 110 wallet tests = 182, − 1 for the retired wallet style pin
   = 181, + 1 for its D12 replacement = **182**, plus the new `tabs`, `considered` and
   `focus` tests.

## Commands

```bash
cd /Users/nathanstough/Desktop/vthacks-ui/frontend && npm run lint && npm run build && npm test
```

```bash
cd /Users/nathanstough/Desktop/vthacks-ui && .venv/bin/pytest backend/ -q -rs
```

```bash
cd /Users/nathanstough/Desktop/vthacks-ui && .venv/bin/pytest backend/tests/test_requirements.py -q
```

`npm test` reads `dist/`, so the build must run first. Exit codes are read from the command
itself, never after a pipe. Expected: frontend 182 + new, 0 failing; backend 2,165 passed, 10
deselected, and zero lines matching `SKIPPED.*test_parity`; requirements 2 passed.

## Browser checks (the suite has no DOM)

1. **On the Plan tab, the chat is genuinely not rendered.** The D14 check, and the most
   important one here. Assert on **the wrapper**, not on `.chat-panel`: an element inside a
   `display: none` ancestor still reports its own computed `display`, so asserting
   `display: none` on the inner panel would fail even when hiding works correctly (Codex plan
   review finding 5). Three assertions: the wrapper computes `display: none`; the panel
   returns no client rectangles; and the panel contributes zero focusable descendants to the
   tab order. Measured before the fix, it contributed six.
2. Ask a question, switch to Plan, switch back — the conversation is intact and the log is
   scrolled to the latest message, not to the top.
3. `/api/chat/status` shows a **delta of zero** across three tab switches. Not an absolute
   count: `main.tsx:8` wraps the app in `StrictMode`, so React double-invokes effects and the
   baseline in dev is already two calls on a cold load, before any change. An absolute-count
   check fails against unchanged code and invites deleting `StrictMode`, which would hide real
   double-mount bugs. Absolute counts only against `npm run build && npm run preview`. The
   deliberate remount on an account change via `key={chatKey(account)}` fires another status
   call and is not a regression.
4. Ticking "Can't do this" on the card row opens the left-out list with the row visible in it.
5. **Tick → collapse the list by hand → tick a second row.** The list must open again. This is
   the D9 desync case and the Safari path.
6. Clearing overrides, and each preset button, collapses it again.
7. The disclosure chip is present and correct on **both** tabs, including with the backend
   down — Ask is where a judge stands when the wifi dies, and the chip must not contradict
   ChatPanel's own "Explainer unreachable".
8. The page scroll jump when the card row is ticked, measured before and after. It is 1048 →
   1630 today, and the script's next line points at the proof box that the jump has just
   pushed 582px off screen. If the change worsens it, the beat's scroll position goes into the
   demo-script pre-flight. Note `preventScroll: true` is not a free fix — it reintroduces
   invisible focus, which was Codex round-2 finding 1 on the frontend-ux spec.
9. The rendered pills read Plan and Ask, Plan is selected on load, and the tier-3 dot is on
   Plan. Pure helper tests cannot prove any of the three — they prove the helpers, not what
   `TopNav` does with them.
10. Scroll position on returning to Plan from Ask, measured. The document shrinks while Ask is
    showing, so the offset is clamped and the return position is not the departure position.
11. Screenshots at 1440 and 390: Plan default, Plan at tier 3, Ask.

## Docs committed to

- `docs/specs/2026-09-19_ui-one-surface-and-ask-tab.md` — this file.
- `docs/features/frontend.md` — the wallet card line, "six" pinned rules becoming five, the tab
  model, the collapse rule, the test counts.
- `docs/demo-script.md` — the 1:45 beat now shows the row landing in an opening list; the build
  numbers, currently 1,333 backend and 216 frontend, become the measured figures.
- `frontend/scripts/shoot.mjs` — retargeted from the wallet pill to the two tabs, and made to
  fail loudly: its text matcher currently returns `'missing'` and still writes a screenshot of
  the wrong view.
- `docs/prize-strategy.md` — **added after the file-impact sweep.** Lines 175–176 make a live
  privacy claim about a tab that will not exist ("The wallet tab keeps its ledger in the
  browser… it dies with the tab"). The Solana prize-track rows at 51 and 94 are decisions about
  sponsors, not about the wallet, and stay.

Confirmed needing nothing: `CLAUDE.md` and `README.md` — the sweep found zero
wallet/solana/devnet occurrences in either, and neither carries a frontend test count.

Explicitly not edited: the frozen `2026-09-19_ui-mise-tuning.md`, which gets a dated note only
if this change contradicts it; the Solana handoffs, specs, reports and screenshots, which stay
as history.

Outside the commit: the `solana-wallet-lane` auto-memory entry goes stale and will be flagged
rather than silently rewritten as part of a code change.

## Open questions escalated to Nathan, not resolved here

**CLAUDE.md and the footer disagree, and this change is the moment someone "fixes" the wrong
one.** CLAUDE.md's binding list says the frontend "falls back to its local solver when the API
is unreachable, **and says so in the footer**". It does not. `footerLines`
(`frontend/src/lib/narrate.ts:123-131`) never reads `source`; it renders "Exact solver,
smallest plan proven / Solved in N ms / N changes considered" identically whether the answer
came from the server or the offline fallback. The disclosure that actually exists is the nav
chip in `TopNav`.

This is pre-existing and not caused by this change. It is escalated rather than fixed because
the two honest repairs point in opposite directions — correct the sentence in CLAUDE.md to say
"nav chip", or make the footer disclose as CLAUDE.md claims — and one of them changes what the
product tells a judge. Nathan's call.

Second, smaller: the footer renders on the Ask tab, where "smallest plan proven" refers to a
plan that is not on screen. Same as the wallet tab does today, so not a regression, but Ask is
a tab judges will actually visit.

Third: **the Ask tab has no beat in the demo script.** It is about to become one of two
top-level destinations. Either it gets a beat or the script records in writing that it is
Q&A-only, so it is an unbudgeted feature on purpose rather than by omission.

## Scope re-freeze, recorded for the auditor

This spec contradicts the P1 frozen in `docs/handoffs/2026-09-19_ui-tabs-and-no-wallet-handoff.md`
(three pills Balance/Plan/Ask, sliders moved into the hero). That handoff's P1 was written by a
previous session and marked frozen without Nathan having read it. He re-froze this scope on
2026-09-19 at ~21:20 after seeing rendered comparisons of both. The Codex audit is pointed at
this run spec, not at that handoff; grading against the handoff would grade against a plan that
was deliberately replaced. See D7 for the substantive reversal and why.

## Review of the plan

Two independent passes over `docs/reports/2026-09-19_ui-one-surface-and-ask-tab-plan.md`.
Full Codex output in `…-plan-review.md`.

**Codex (`review-plan.sh`)** — 4 critical, 3 suggestions, all accepted and fixed:
1. `decideConsidered(1→2)` returned `leave`, so the Safari desync path left the ruled-out row
   in a shut list. Rule changed to open on any increase.
2. Reset cannot be derived from count transitions (0→0 when the list was opened by hand).
   `consideredOpen` is now reset explicitly in `adopt()` and the clear handler.
3. Clearing `newIds` on tab exit is insufficient; `apply()` repopulates it from responses that
   land while Plan is hidden. Suppression moved into `apply()`.
4. The chat-log re-scroll had an acceptance criterion and a risk entry but no implementing
   step. Now step 6b, and `ChatPanel.tsx` is authorised in "What will change".
5. The D14 browser assertion targeted the wrong element — an element inside a `display: none`
   ancestor still reports its own computed `display`. Now asserts on the wrapper, plus no
   client rects, plus zero focusable descendants.
6. Step 6 never said the first pill is renamed from "Checking account" to "Plan", nor that the
   helpers are wired into rendering rather than merely exported.
7. Step 0's expected `git status` would have hard-stopped on this pipeline's own paperwork.

**Adversarial Claude critique** — independently reproduced Codex findings 1, 3 and 4, verified
every cited line number bar three, and added nine:
- Steps 1–10 do not compile in between (`tsconfig.app.json` includes `tests`, `noUnusedLocals`
  is on), so they are now declared one atomic commit. The claim that an unused import fails
  `oxlint` was wrong — it fails `tsc -b` first.
- Step 0 ends inside `frontend/`; step 1's paths did not resolve from there.
- The `!important` shim was argued from a premise D6 already removes. Narrowed to
  `.main > [hidden] { display: none }`, keeping the stylesheet's `!important` count at zero.
- `verbatimModuleSyntax: true` requires the `Tab` type imported separately.
- `.rx-panel { flex: 1 }` goes from inert to live-and-overridden and should be deleted.
- The footer's delay must be `:nth-child(5)`, not a `.meta` rule, because the Ask tab has a
  different child count. D17's "animates before the hero" was wrong — it animates *with* it.
- The collapsed default invalidates the "11 checkboxes in the tab order" claim documented at
  `docs/features/frontend.md:190-193`, plus the Focus section at 205-218. Added to step 11.
- Editing `frontend.md:270-272` would harden one side of the open CLAUDE.md escalation, so it
  is held back pending Nathan's ruling.
- Three line numbers drifted: `.panel`'s `display: flex` is at 473 not 468; the nav chip span
  is 52-54 not 51-54; the `chatKey` tests span 198-216 not 201-215.

Verified and left alone: React 19.3.0 does attach a `toggle` listener to `details` on both
mount and hydrate paths, and the HTML spec queues the toggle task for programmatic
`.open = true`, so D9's mechanism holds — with two traps recorded in the plan (the synthetic
event carries no `newState`; a remount with `open={true}` fires a redundant toggle, so the
handler must assign rather than flip). Test arithmetic re-verified by running the suite:
292 = 182 + 110, exactly one existing test retired, one replacement. The `minmax(0, 1fr)` pin
survives with exactly six matches, none inside a deleted block.

## Codex plan review

See above; raw output in `docs/reports/2026-09-19_ui-one-surface-and-ask-tab-plan-review.md`.

## Results — executed Sat 2026-09-19, ~22:10–23:00

Committed at `a2299fc`, with the audit fixes in the commit that follows it.

**Correction to `a2299fc`'s own message.** It says "Nine browser checks and screenshots at
1440 and 390 recorded in the run spec." That was wrong twice over when it was written: there
are **eleven** checks, not nine, and this section still said "to be appended". The checks had
been run — the evidence below is real — but the record did not exist at the time the message
claimed it. Recorded here rather than by amending history.

### Commands

```
cd frontend && npm run lint          exit 0
cd frontend && npm run build         exit 0   637.38 kB / 189.06 kB gzip, ONE chunk (was two)
cd frontend && npm test              209 pass, 0 fail, 0 skipped
.venv/bin/pytest backend/ -q -rs     2165 passed, 10 deselected, 22.18s
grep -c "SKIPPED.*test_parity"       0
```

Frontend arithmetic: 292 − 110 wallet = 182; +3 bundle, +1 cant, +7 considered, +2 focus,
+2 styles, +8 tabs = 205 at `a2299fc`; then −1 vacuous bundle pin and +5 source pins from the
audit = **209**.

### Acceptance criteria

| # | Criterion | Result |
|---|---|---|
| 1 | No Solana/wallet string in the bundle | **Pass**, automated. Also zero `.wallet` in `src/`. |
| 2 | No `.wallet` selector in the stylesheet | **Pass**, automated, the D12 inverse pin. |
| 3 | Pills read Plan/Ask, Plan default, dot on Plan | **Pass.** Helpers in `tabs.test.ts`; the wiring pinned at source after the audit found the helpers could have been exported and ignored. Browser: pills `Plan`/`Ask`, `aria-current` on Plan, dot present on the Plan pill at tier 3 and absent from Ask. |
| 4 | Conversation survives tab switches; status-call delta zero | **Pass**, browser only. Asked a question, switched to Plan before the reply, switched back: both turns intact, log scrolled to the latest. `/api/chat/status` delta **0** across three round trips (absolute 2 on load — StrictMode double-invokes). |
| 5 | List starts collapsed, opens on override, closes on reset | **Pass.** All three transitions automated. Browser: collapsed on load; ticking the card row by mouse with no keyboard focus (the Safari path) opened it with the row visible; hand-collapse then a second override reopened it; both `Clear n overrides` and a preset re-collapsed it, including from a hand-opened list at zero overrides. |
| 6 | Focus restored only when plan visible, row survives | **Pass**, automated, both counterfactuals including `clear === false`. |
| 7 | Plan tab materially shorter | **Pass.** 2,563 → **1,770px** at 1440 (−31%). Tier 3 2,840 → 2,634. Ask 1,044. |
| 8 | Chip on both tabs, no banned word | **Pass.** Strings automated; the chip is in `<header>` outside the tab switch, now pinned at source. Browser: identical text on both tabs. Backend-down case **not re-run** — the chip's offline text is unchanged code and was verified before this change. |
| 9 | Frontend green at the new floor; backend unmoved | **Pass**, see Commands. |
| 10 | `minmax(0, 1fr)` still ≥ 6 | **Pass.** Exactly six, zero headroom, none inside a deleted block. |

### Browser checks

1. **Chat not rendered on Plan** — wrapper computes `display: none`, panel returns **0** client rectangles, **0** focusable descendants in the tab order. Before the `.main > [hidden]` rule: `display: flex`, 363px tall, **6** focusable descendants.
2. **Conversation survives** — see criterion 4.
3. **Status-call delta 0** — see criterion 4.
4. **Tick opens the list** — 3 changes → 7, list opened, "Pay the card minimum" in it, struck through, ticked.
5. **Hand-collapse then second override reopens** — passed; row visible.
6. **Both reset paths collapse** — passed, including the 0 → 0 case.
7. **Chip on both tabs** — identical. Backend-down half not re-run; see criterion 8.
8. **Scroll jump at the tick beat** — 1048 → 1630 before; after the change the page no longer scrolls at all at the default preset (0 → 0), because the collapsed list shortens the document enough that the focused row is already in view. Improved, not worsened.
9. **Rendered pills** — see criterion 3.
10. **Scroll position across a tab switch** — not preserved. Recorded as a known gap.
11. **Screenshots** — `docs/shots/2026-09-19_ui-one-surface-and-ask-tab/`, six files. Desktop downscaled to 1200 tall; mobile kept at native 390 wide, because downscaling a 390×3149 page by its longest edge crushes it to 148px and proves nothing.

### Tab order, measured

Plan tab: **3** checkboxes plus the left-out `<summary>`, zero inside `.chart-wrap`, zero
inside the hidden explainer. It was 11 checkboxes before the list began collapsed; the other
eight join when it opens. Rows inside a closed `<details>` still report client rectangles in
Chrome but are not focusable, so tabbability has to be tested by attempting focus.

### Deviations

1. **D18 was added mid-execution**, after Nathan saw the finished left-out list. It changed
   `cant.ts` and `cant.test.ts`, neither of which was in "What will change", and it has no
   acceptance criterion and never went through the Codex plan review. The change is sound and
   tested; the process record is not, and that is the deviation.
2. **D16 shipped incomplete and was fixed after the audit.** The `is-new` suppression inside
   `apply()` covers only responses landing while Plan is hidden. The ordinary path — tick, watch
   the highlight, then visit Ask and come back — left `newIds` set, so the animation replayed on
   remount, which is the one outcome D16 named unacceptable. Now also cleared on leaving Plan.
   Browser-confirmed: 5 rows highlighted while watching, 0 after the round trip.
3. **The left-out list does not open for rows that leave the plan without an override change.**
   Deliberate; reasoning in `docs/features/frontend.md`.
4. **One bundle pin was vacuous.** "Ask" is also the explainer's submit-button text, so the pin
   passed with the Ask pill deleted. Replaced by source pins.
5. **Backend-down chip check not re-run.** Unchanged code, verified before this change.

## Claude critique (adversarial, Opus)

Round 1 graded **Fail**, on Test coverage and Documentation. Thirteen findings; the ones that
mattered:

- `.rx-row.is-new` re-flashing on the Plan → Ask → Plan round trip (deviation 2) — verified in
  code, the one thing D16 called unacceptable, and documented as fixed when it was not.
- `docs/demo-script.md` told the presenter the left-out row reads "Can do this" — the string
  D18 had deleted, in the file that gets read aloud under pressure.
- `docs/features/frontend.md` still documented `controlFor(section, …)` two paragraphs below the
  table saying there is one reading.
- The commit message claimed a Results section that did not exist, and said nine checks when
  the spec lists eleven.
- The "Ask" bundle pin could not fail.
- `shoot.mjs` had the same ambiguity, in the script the same commit had hardened.
- The frontend count in the demo script was off by one.
- Acceptance criteria 3 and 5 had no automated coverage of their rendering halves.
- Mobile screenshots downscaled to 96px wide.

All fixed. The audit also confirmed D1–D15, D17 and D18 implemented as stated, all 7 Codex plan
items and all 9 critique items in code, exact test arithmetic, no CLAUDE.md violation, and that
escalating the footer contradiction rather than resolving it was the right call.

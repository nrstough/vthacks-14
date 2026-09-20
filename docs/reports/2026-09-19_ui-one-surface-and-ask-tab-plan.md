# Implementation plan — drop the wallet, one surface, the explainer behind its own pill

Run spec: `docs/specs/2026-09-19_ui-one-surface-and-ask-tab.md` (D1–D17).
Branch `ui-design-system`, worktree `/Users/nathanstough/Desktop/vthacks-ui`, clean at `bac3f73`
apart from the untracked run spec. Written 2026-09-19 ~22:05 after a deep pass: three parallel
exploration agents (architecture, file impact, adversarial risk), all read-only.

Line numbers below are as of `bac3f73` and were verified by the sweeps, not remembered. They
shift as steps land — re-read before each edit rather than trusting an offset.

---

## Step 0 — Pre-flight

```bash
cd /Users/nathanstough/Desktop/vthacks-ui
git branch --show-current     # must print ui-design-system
git status --short            # see the allowlist below
```

Hard stop if the branch is wrong. Another session may have switched this checkout; CLAUDE.md
records that happening once already.

Expected untracked files, all artifacts of this pipeline — Codex review finding 7, since the
original "expect only the run spec" would have hard-stopped on the plan's own paperwork:

```
docs/specs/2026-09-19_ui-one-surface-and-ask-tab.md
docs/reports/2026-09-19_ui-one-surface-and-ask-tab-plan.md
docs/reports/2026-09-19_ui-one-surface-and-ask-tab-plan-review.md
```

Anything else untracked belongs to another session — stop and ask, do not sweep it into a
commit. That has already cost this project twice.

Baseline, so every later number is a delta and not a guess:

```bash
cd /Users/nathanstough/Desktop/vthacks-ui/frontend && npm run lint && npm run build && npm test
```
→ 292 passing. Keep the number.

### Steps 1–10 are ONE atomic commit. Do not commit partway.

Critique finding 4. `tsconfig.app.json` sets `"include": ["src", "tests"]` with
`noUnusedLocals: true`, so the intermediate states genuinely do not compile:

- after step 1, `App.tsx:27` imports a deleted module → TS2307, and a dead dev server;
- after step 2c, `Tab` and `DEFAULT_TAB` do not exist until step 3;
- after step 8, `planVisible` is required and the eleven `focus.test.ts` call sites are red
  until step 10.

The sequence works as written, but CLAUDE.md says "commit early and often" and a commit taken
at 1, 2c or 8 would be a broken one. This is the exception, and it is deliberate: one commit
at step 12.

Related correction: step 2b said an unused `Suspense`/`lazy` "fails `oxlint`". It fails
`tsc -b` first — `.oxlintrc.json` enables only `rules-of-hooks` and `only-export-components`.

---

## Step 1 — Delete the wallet source and tests

```bash
cd /Users/nathanstough/Desktop/vthacks-ui
git rm -r frontend/src/wallet
git rm frontend/tests/wallet-ledger.test.ts frontend/tests/wallet-receipt.test.ts \
       frontend/tests/wallet-state.test.ts frontend/tests/wallet-units.test.ts \
       frontend/tests/wallet-view.test.ts
```

The `cd` is not decoration — step 0 ends inside `frontend/`, where these paths do not resolve
(critique finding 5).

Explicit paths, never `git add -A` — CLAUDE.md, and two real incidents behind it.

Nothing outside `src/wallet/` imports any of those eight modules except `App.tsx:27`, and no
wallet module imports anything outside its own directory except React. It is a clean cut.

---

## Step 2 — `frontend/src/App.tsx`

Five edits, in this order.

**2a.** Delete the lazy import and its comment, lines **23–27**:
```
23: // Lazily loaded, so the wallet and its fixtures never enter the main chunk.
…
27: const WalletView = lazy(() => import('./wallet/WalletView.tsx'))
```
The comment at 25 claims `npm run build` "reports the two chunks separately". That becomes
false; it goes with the import rather than being left as stale prose.

**2b.** Line **1** — drop `Suspense` and `lazy` from the React import. Both are used only in
the block removed at 2a; leaving either fails `oxlint`.

**2c.** Line **32** — the tab state moves to the new module:
```tsx
const [tab, setTab] = useState<Tab>(DEFAULT_TAB)
```
imported from `./lib/tabs.ts`.

**2d.** Lines **244–265** and the matching `)}` at **454** — replace the wallet ternary with a
plain conditional around the planning fragment, and hoist `ChatPanel` out of the `.duo-start`
row (**445–451**) to sit as a sibling inside `<main>`, wrapped so the attribute lands on an
element no author `display` rule targets:

```tsx
{tab === 'plan' && (
  <>
    {/* hero, .duo chart row, the now-full-width plan panel */}
  </>
)}

<div hidden={tab !== 'ask'}>
  <ChatPanel key={chatKey(account)} … />
</div>

<footer className="meta">…</footer>
```

`key={chatKey(account)}` is preserved exactly. It is deliberate and pinned by
`tests/accounts.test.ts:201-215`: remounting on an account change clears the log so an answer
about the previous account cannot appear under the current one.

The wrapper is required, not stylistic — see D14 and step 5a.

**2e.** The `.duo duo-start` wrapper at **415** goes; the plan panel (`416–443`) becomes a
direct child of `<main>`. The `.duo` chart row at **284–413** is untouched.

**2f.** Add the two new effects and the guard:
- pass `planVisible: tab === 'plan'` into `decideRestore` at **133–141**. Do not add `tab` to
  the `[res]` dep array — the effect must not re-run on a tab switch, and the comment at
  **156–160** explains why it reads this render's values.
- suppress the `is-new` highlight for any response the user did not see (D16). Clearing
  `newIds` on the way out of Plan is **not sufficient** — Codex review finding 3: the solve
  effect keeps running on the Ask tab, and `apply()` at **88–100** repopulates `newIds` from a
  response that lands while Plan is hidden, so the rows flash as new on return anyway. The
  suppression belongs inside `apply()`: when the plan is not visible, write an empty
  `newIds`. Test by switching away before a slow solve completes.
- own the `<details>` open state (D9) and pass it plus an `onToggle` handler to
  `PrescriptionList`; reset it explicitly in `adopt()` and in the clear-overrides handler
  (step 4).

---

## Step 3 — `frontend/src/lib/tabs.ts` (new)

```ts
export type Tab = 'plan' | 'ask'
export const DEFAULT_TAB: Tab = 'plan'
export function isPlanVisible(tab: Tab): boolean { return tab === 'plan' }
export function showsAlarmDot(tab: Tab, tier: number): boolean { … }
```

No enums — `erasableSyntaxOnly: true` in `tsconfig.app.json`. Value imports inside this module
carry the `.ts` extension, because a test will import it and type stripping resolves
specifiers literally.

**`verbatimModuleSyntax: true` is also on** (critique finding 11), so consumers need the type
and the values imported separately — `import type { Tab } from './lib/tabs.ts'` alongside
`import { DEFAULT_TAB, isPlanVisible } from './lib/tabs.ts'`. A single combined import does
not compile.

The union currently exists twice — `App.tsx:32` and `TopNav.tsx:3` — and only survives because
props tie them together. One exported type ends that.

---

## Step 4 — `frontend/src/lib/considered.ts` (new)

```ts
export type ConsideredAction = 'open' | 'close' | 'leave'
export function decideConsidered(prev: number, next: number): ConsideredAction {
  if (next > prev) return 'open'
  if (next === 0 && prev > 0) return 'close'
  return 'leave'
}
```

**Open on any increase, not only on 0 → 1.** Codex review finding 1: with the 0 → 1 form,
rule out A → collapse the list by hand → rule out B is a 1 → 2 transition, which returned
`leave` and left the section shut with B invisible. That is precisely the Safari path D9 exists
to protect, so the guard has to fire whenever a row moves in, not only on the first one.

A steady-state re-solve is still `leave`, so a manual collapse is not fought by an unrelated
response.

**Reset is explicit, not derived.** Codex review finding 2: count transitions cannot express
it. A user who opens the list by hand with zero overrides and then hits a preset produces
0 → 0, which is `leave`, and the list stays open. So `consideredOpen` is set to `false`
directly in `adopt()` (`App.tsx:183-199`) and in the clear-overrides handler
(`App.tsx:428`), in addition to the `close` transition. Test: manually open with zero
overrides, press a preset, assert collapsed.

**One behaviour to state out loud rather than discover:** the `close` transition fires on any
drop to zero, so hand-unticking your *last* override also collapses the list under you — not
only the reset buttons. The plan previously sold count-based detection as closing on reset
"for free"; this is the other half of that bargain (critique finding 1, secondary). It is
acceptable — at zero overrides the list is back to its default state — but it is a decision,
not an accident.

---

## Step 5 — `frontend/src/index.css`

**5a.** Add a scoped hiding rule:
```css
.main > [hidden] { display: none; }
```

**Narrowed from `[hidden] { display: none !important }` after critique finding 6.** The
original justification was that `hidden` loses to `.panel { display: flex }` — true, and
verified live (the panel kept `display: flex`, 363px of height and six focusable descendants).
But that only applies to putting `hidden` *on* the panel, which D6 already rejects in favour of
a wrapper. The wrapper is a bare `<div>`; the only rule that touches it is `.main > *`
(**1394–1400**), which sets `flex` and `animation` and never `display`, so the user-agent
`[hidden]` rule already wins.

`.main > [hidden]` is (0,2,0), beats `.panel` outright, is scoped to the one place it is
needed, and keeps this stylesheet's count of `!important` declarations at **zero** — verified,
the sheet currently has none. Belt-and-braces against a future `display` on the wrapper,
without a global override nobody can see the effect of.

Note the declaration D6 and D14 argue from is at **473**, not 468 — 468 is the `.panel {`
selector line (critique finding 13).

**5b.** Delete the wallet CSS: block A at **1110–1250**, block B at **1436–1500**, the
`.wallet-sign` selector at **1347** inside the shared transition rule at 1340–1354 — and drop
the now-trailing comma after `.crash button,` at **1346**. Fix the stale comment at
**185–186**, which names `.wallet-balance` and `.wallet-amt`.

There is **no** `.wallet` entry in either `prefers-reduced-motion` block (857–859, 1565–1585).
Do not go looking for one.

**5c.** Delete `.duo-start { align-items: start; }` at **1263** with its comment at 1258–1262,
and the whole `@media (min-width: 1281px)` block at **1268–1273**, whose only rule is the
sticky `.duo-start > .chat-panel`. Keep `.duo` at **459–464** and its 1280px rule at
**1504–1506** — the chart row still uses both.

**5d.** Give the plan panel its full-width treatment, and delete `.rx-panel { flex: 1 }` at
**580** — it is inert today as a grid item, but once `.rx-panel` becomes a direct `.main` flex
child it becomes live and is then silently overridden by `.main > * { flex: none }` on source
order. That is the exact shape of the bug `styles.test.ts:152-154` exists to catch, so it goes
rather than sitting there looking load-bearing (critique finding 10).

**5e.** The footer's stagger (D17). `.main > *:nth-child(1..4)` are at **1402–1405**. On Plan
the children are hero(1), `.duo`(2), `.rx-panel`(3), the hidden wrapper(4), footer(5) — so the
footer needs `:nth-child(5)`, **not** a `.meta` class rule: on the Ask tab the children are
wrapper(1), footer(2), and a class rule would misfire there (critique finding 9).

Correction to D17's wording: with no delay the footer animates **with** the hero, both at 0ms
— not before it.

**5f.** Revisit `.chat-panel .chat-log { max-height: 220px }` at **607–609**. That was tuned
for a 489px side column; on a full-width tab it leaves a short card with a small scroll box.
Raise it, or let it grow, without introducing a literal white (`styles.test.ts:221-230`).

**Recount after 5c**: `styles.test.ts:159-162` asserts at least six `minmax(0, 1fr)` and there
are exactly **six** (lines 358, 398, 461, 1505, 1513, 1547). Zero headroom. None sits in the
deleted `.duo-start` block, so the planned change is safe — but verify, do not assume.

---

## Step 6 — `frontend/src/components/TopNav.tsx`

**Rename the first pill as well.** Codex review finding 6: the plan described replacing the
second pill and never said the first one changes. Line **36** currently reads `Checking
account` and becomes `Plan`; the pill at **41–48** becomes `Ask`. Both pills take their label,
their `aria-current` and the tier-3 dot placement from `lib/tabs.ts` rather than from inline
comparisons, so the helpers are actually wired into rendering and not merely exported.

Pure helper tests cannot prove the rendered labels, the default selection or where the dot
landed — those three go on the browser-check list.

Rewrite the `Tab` type at **3** to import from
`lib/tabs.ts`; update the JSDoc at **13–18**, which is the written record of why the disclosure
chip lives in the nav rather than the footer — rewrite it for Ask, do not delete it. The chip
itself at **52–54** (51 is the enclosing `.nav-right` div) must not move: it is the only
rendered home of "Running on the built-in
solver", and `bundle.test.ts:35-38` only proves the string ships, not that it renders on both
tabs.

---

## Step 6b — `frontend/src/components/ChatPanel.tsx`: re-scroll on reveal

Codex review finding 4: the mitigation was in the risk table with no step to implement it.

`ChatPanel.tsx:53-56` scrolls the log on `[messages, pending]`. While the panel is hidden,
`scrollHeight` is 0, so the write lands as `scrollTop = 0` and nothing re-runs it when the
panel reappears. An answer arriving while the user is on Plan therefore shows up scrolled to
the top of a 220px box with the reply below the fold — which defeats the entire reason for
keeping the panel mounted.

Add a `visible: boolean` prop and include it in that effect's dependencies so the scroll
re-runs on reveal. Test: ask, switch to Plan before the reply lands, switch back, assert the
log is at the bottom.

---

## Step 7 — `frontend/src/components/PrescriptionList.tsx`

Line **125**: `<details className="considered" open>` becomes controlled —
`open={consideredOpen} onToggle={onConsideredToggle}`, both from `App`.

**The mechanism is verified, not assumed** (critique finding 12). React is **19.3.0**;
`toggle` is in `nonDelegatedEvents` and `listenToNonDelegatedEvent("toggle", domElement)` runs
for `details` on both the mount and hydrate paths, so React attaches the listener on the
element itself. The HTML spec queues the toggle task for any `open` add/remove **including a
programmatic `.open = true`**, so the imperative open in the focus-restore effect syncs itself
back into React instead of desyncing from it.

Two implementation traps that follow from that:

- React's synthetic `toggle` event does **not** carry `newState`. The handler must read
  `e.currentTarget.open`.
- Remounting the `<details>` with `open={true}` — returning to Plan with the list open — fires
  a redundant toggle. The handler must **assign** the DOM's value, never flip the previous
  state, or the list closes itself on every return.

---

## Step 8 — `frontend/src/lib/focus.ts`

Add `planVisible: boolean` to `RestoreInput` (**67–73**) and, in `decideRestore` (**82–96**),
after the `!refId` check at **84**:

```ts
if (!planVisible) return { focus: null, clear: false }
```

`clear: false` is the point (D13). Today `App.tsx:142` applies `clear` *before* the early
return at 143, and `clear` is just `settled`, so a response landing while the user is on
another tab already discards the remembered row. Returning `clear: true` here would preserve
that defect.

All eleven existing call sites in `focus.test.ts` (38, 45, 52, 61, 63, 71, 73, 87, 96, 143,
145) must gain the field. That is intended.

---

## Step 9 — `frontend/src/components/ErrorBoundary.tsx`

`inline` has exactly one caller, the wallet branch removed in 2d — confirmed across all of
`src/`, `tests/` and `scripts/`. Remove the prop at **28**, its branch at **50** and its
doc comment at **16–27**. The component stays: `main.tsx:9` uses it, and its full-page
fallback carries "This page stopped working", pinned by `bundle.test.ts:43-46`.

---

## Step 10 — Tests

New: `frontend/tests/tabs.test.ts`, `frontend/tests/considered.test.ts`.

`considered.test.ts` must include the desync case end to end: rule out A → manual collapse →
rule out B, list open. That is the Safari path where the imperative open never fires, and the
demo's payoff line depends on it.

`focus.test.ts`: update eleven call sites; add two counterfactuals — `planVisible: false`
returns no focus, **and** reports `clear: false`. A test checking only `focus === null` passes
against the existing defect.

`styles.test.ts`: retire the wallet pin at **192–213** with a note recording what it replaced,
and put its inverse in place — no `.wallet` selector survives anywhere in the sheet. Add a pin
for the D14 shim.

`bundle.test.ts`: add pins for `/solana/i` and the wallet view strings.

---

## Step 11 — Docs, before commit

`docs/features/frontend.md`: the "One screen, three bands" description at **9–19**; the
both-tabs chip claim at **26**; the six-pins paragraph at **274–281**, where "six" becomes
five and the wallet clause goes; the bundle size at **324**.

**Added after the critique (finding 7):** the Accessibility section at **190–193** states
"Verified: 11 checkboxes in the tab order". With the left-out list collapsed on first paint
that becomes three checkboxes plus a focusable `<summary>`, so 190–193, the "eleven rows
otherwise read identically" line, and the Focus section at **205–218** — the imperative open
at 212–213 and the six hand-verified sequences at 216–218 — all need updating, and D13's
`planVisible` rule belongs in that list.

The same finding exposes an inconsistency inside the spec: D14 says the shim protects "the
documented eleven tab stops", but D9 means it is no longer eleven. D14's arithmetic is about
the six focusable descendants the chat panel would have added, not about a total of eleven.

**Held back pending Nathan's ruling:** lines **270–272**, which already assert "It is a nav
chip, not a footer one" — directly against CLAUDE.md's "says so in the footer". That is the
open escalation in the run spec. Editing that paragraph now would harden one side of a
question that is his to settle, so this change limits itself to the tab wording and leaves the
chip-versus-footer sentence alone.

`docs/demo-script.md`: the stale counts at **21** — it says 216 frontend tests and the suite is
292 today; the 1:45 beat at **96–97**, whose payoff now depends on the auto-open; add the tab
to each beat; and either give Ask a beat or record that it is Q&A-only.

`docs/prize-strategy.md`: **175–176**, a live privacy claim about the wallet tab. Lines 51 and
94 are sponsor-track decisions and stay.

`frontend/scripts/shoot.mjs`: line **24** clicks "Demo wallet"; line **2** is a stale header.
Retarget to plan/ask/tier3 and **make a `missing` click throw** — today it logs `missing` and
screenshots anyway, which is how a wrong view gets committed under `docs/shots/` as evidence.

`CLAUDE.md` and `README.md`: confirmed to need nothing.

---

## Step 12 — Verify, then commit

```bash
cd /Users/nathanstough/Desktop/vthacks-ui/frontend && npm run lint && npm run build && npm test
cd /Users/nathanstough/Desktop/vthacks-ui && .venv/bin/pytest backend/ -q -rs
cd /Users/nathanstough/Desktop/vthacks-ui && .venv/bin/pytest backend/tests/test_requirements.py -q
```

Frontend: 292 − 110 = 182, − 1 retired pin, + 1 replacement, + the new tests. Backend must not
move from 2,165 passed / 10 deselected, with zero `SKIPPED.*test_parity`. Exit codes from the
command, never after a pipe.

Then the nine browser checks in the run spec, screenshots at 1440 and 390, and a commit with
explicit paths.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| `hidden` silently does nothing; chat renders on the Plan tab with six extra tab stops | the 5a shim, a style pin, and a computed-style browser assertion. Verified live as a real failure, not a hypothesis |
| The `<details>` desyncs after a manual collapse; the ruled-out row vanishes mid-demo | controlled state in `App` + `onToggle`; the three-step desync test |
| Focus guard written to forget rather than keep, preserving the existing defect | D13; the counterfactual asserts `clear: false`, not just `focus === null` |
| `minmax(0, 1fr)` pin has exactly zero headroom | recount after 5c before running the suite |
| Status-call check fails against unchanged code | `StrictMode` doubles effects in dev; measure a delta, or use `vite preview` |
| Chat log scrolled to the top on return | `scrollHeight` is 0 while hidden; re-run the scroll on unhide |
| The Codex audit grades against the superseded three-tab handoff | the re-freeze is recorded in the run spec |
| Another session switches the checkout mid-work | step 0, and re-check before the commit |

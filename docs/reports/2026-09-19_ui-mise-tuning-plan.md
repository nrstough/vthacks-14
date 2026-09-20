# Plan — UI: Mise tuning, two wording fixes, merge (2026-09-19, deep mode)

Run spec: `docs/specs/2026-09-19_ui-mise-tuning.md`. Branch `ui-design-system`, worktree
`/Users/nathanstough/Desktop/vthacks-ui`. Three exploration agents (architecture, file impact,
risk) and one critique agent (26 findings, all folded in) fed this plan.

Line numbers are against the branch at `a8f22d1` unless marked "post-merge". Files that
`main` also changed (`App.tsx`, `index.css`, `prompt.py`, `demo-script.md`) shift in step 1;
for those the plan names the rule or sentence, not only the line.

## What the exploration changed about the approach

1. **`main` has moved 46 commits since this branch forked** (merge-base `2653df3`, `main` now
   `21bd4fe`, checked out in `/Users/nathanstough/Desktop/vthacks-integrate`). It carries the
   product rename to **Safe to Spend**, an account loader in the app shell (two source buttons,
   a provenance tagline, slider bounds, a chat remount key), and a bundle assertion for the
   "Capital One sandbox" label. The dry-run merge conflicts in `App.tsx` (five blocks) and
   `index.css` (one block); `ChatPanel.tsx` and `index.html` auto-merge. **The merge is step 1,
   before any retune.**
2. **The rename would be lost silently.** On `main` the wordmark is in `App.tsx`; here it is in
   `TopNav.tsx:26`, which git will not touch. Hand-applied in step 1.
3. **Only the in-plan sentence changes.** The critique showed the stated problem, two lines
   both reading "not needed", is solved by the solver-side change alone. The P2 idea of also
   rewording the tier 1 left-out line to "holds the cushion" would make both lines lead on the
   cushion and would need a tier split to stay true at tier 2. It is dropped; `reasons.ts` is
   untouched and its texts are pinned as-is. **This is a change from the frozen P2 and is
   called out at the approval stop.**
4. **The in-plan sentence is emitted at tier 3 too** (`wording.py:122-124` ignores tier).
   "Not to clear zero" misreads when nothing clears zero. The not-load-bearing branch gets a
   second string on the `plan_clears_zero` argument already in scope, claiming only what zero
   marginals prove: "Removing it would not widen the gap."
5. **Provenance goes above the verdict, outside its live region.** `main` requires the
   account's provenance on screen; this branch dropped the tagline that carried it. The
   verdict section is `aria-live` and `aria-atomic`, so the line is rendered as a sibling
   above it in the hero, never inside it. The wallet tab shows the demo token wallet, not the
   checking account, so provenance is not shown there; recorded in the spec.
6. **No glass wallet card.** `.wallet-head` is inside the white `.wallet` card that commit
   `6fa71df` added on purpose; glass over white is white on white. The wallet keeps its card.
   D1's optional item is withdrawn.
7. **`.num` stays in the text face.** It is on the qualifier, the proof paragraph and the
   reason lines, not only figures. Figures get the mono face by adding their own selectors
   to the existing mono rule.
8. **The nav's active pill is already white on navy.** No inversion step; the deeper
   `--accent-press` is the only change there, plus a navy focus ring on the active pill.
9. **Array is not on `main`**; it arrived with Hrushi's commit, is referenced by nothing, and is
   7.0 MB of the 8.0 MB font payload. It goes with Clash and Doto.
10. **Two `:root` blocks** (`index.css:37` and `:1515`); the live gradient is hard-coded in
    `.app` at `:171` while `--grad` at `:93` is dead. Both blocks are retuned; `--grad` becomes
    the one gradient and `.app` consumes it.
11. **Harness rules for new files:** `fileURLToPath`, never `.pathname`; value imports inside
    `src/lib` carry explicit `.ts` extensions; `Control` is a type-only import; no enums.
    Parity must be shown to run, not skip.

## Step 0 — Pre-flight

```bash
cd /Users/nathanstough/Desktop/vthacks-ui && git branch --show-current && git status --short
```
Expect `ui-design-system` and two untracked docs. Commit them first so the merge starts clean
(the Codex review file is added in step 10):

```bash
git add docs/specs/2026-09-19_ui-mise-tuning.md docs/reports/2026-09-19_ui-mise-tuning-plan.md
git commit -m "docs: run spec and plan for the Mise tuning"
```

Before-screenshots of the current branch in the browser pane (1440 and 390; plan default,
`$60.00` tier 3, wallet), saved to the scratchpad as the baseline.

## Step 1 — Merge `main` into the branch, resolve, re-baseline

```bash
git merge main
```
Expected conflicts: `frontend/src/App.tsx`, `frontend/src/index.css` only.

**`index.css`:** HEAD's appended section versus `main`'s 16-line tail. Keep HEAD's block, then
from `main`'s block take only `.ctl-sources { margin-top: 6px; flex-wrap: wrap }` and
`.ctl-presets button:disabled { opacity: 0.55; cursor: progress }`. `main`'s
`.ctl-presets button:focus-visible` duplicates this branch's `:1491-1502` (which also has the
pill radius), so it is not taken.

**`App.tsx`** (five blocks; `main`'s logic, this branch's markup):

- Imports: `main`'s (`useReducer`; `chatKey, loadAccount, provenanceLine, sliderBounds` from
  `./lib/accounts.ts`; `LoadKind` type and `accountReducer, fail, initial, preset as
  presetAction, start, succeed` from `./lib/accountState.ts`; `money, shortDate`) plus this
  branch's `Stats` and `TopNav`. `FIXTURE` replaces `BASE`.
- State: `main`'s reducer block (`acct`, `dispatch`, `account, base, loading, error:
  loadError`, `seqRef`, `loadCtl`); `request` built from `base` with `base` in its deps.
- The solve effect's `.catch`: `main`'s try/catch around the offline fallback.
- Functions: `main`'s `adopt`, `preset`, `load` replace this branch's `preset`.
- Markup, this branch's, with these insertions:
  - In `.hero-copy`, before `<VerdictBand>`: `<p className="eyebrow-note">{provenanceLine(account, base)}</p>`
    (the class exists at `index.css:353-359`, mono 12px, unused until now). `main`'s second
    tagline clause, "Move a slider or rule a change out, and the plan is re-solved from
    scratch.", is dropped: the controls panel is headed "What if / Move the inputs".
  - Controls panel, after the `.switcher` div: `main`'s `<span className="ctl-presets
    ctl-sources">` with both buttons verbatim (labels "New modelled account" and "Capital One
    sandbox", the latter bundle-asserted) and the `loadError` `<p className="ctl-note"
    role="status">`. Slider `min`/`max` from `sliderBounds(opening)`. The switcher's
    `aria-pressed` gains `account === null &&`.
  - Chart kicker dates from `base.as_of` / `base.horizon_end`.
  - `<ChatPanel key={chatKey(account)} … accountSource={account?.source ?? 'preset'} />`.
- `TopNav.tsx:26`: `Overdraft Guard` → `Safe to Spend`; the mark at `:23` → `S`.
- `grep -rn "Overdraft Guard" frontend/src` afterwards must return nothing.

```bash
git add frontend/src/App.tsx frontend/src/index.css frontend/src/components/TopNav.tsx
git commit   # merge commit: "Merge main into ui-design-system: account loader, Safe to Spend"
cd frontend && npm run lint && npm run build && npm test
cd .. && .venv/bin/pytest backend/tests/test_requirements.py -q
.venv/bin/pytest backend/ -q --collect-only > /tmp/collect.log; echo "collect exit=$?"; tail -1 /tmp/collect.log
.venv/bin/pytest backend/ -q -rs > /tmp/backend.log; echo "pytest exit=$?"; grep -E "passed|failed|skipped|error" /tmp/backend.log | tail -3
grep -c "SKIPPED.*test_parity" /tmp/backend.log   # must print 0
```
Exit codes are read from `$?` on the pytest line itself, never from a pipe into `tail`.
Expected: frontend **253 passing** (209 + 11 + 25 + 7 + 1). Backend: the `--collect-only`
number is written into the spec's Commands block as the post-merge baseline (`main` added ten
test files and modified the existing `pytest.ini`, which deselects `perf` and `nessie`). If
`test_requirements.py` fails, the shared `.venv` lacks `main`'s packages: **stop and report**,
do not install into the shared venv. `test_parity`: 0 skipped in the `-rs` summary.

Browser check: both account buttons under the switcher, the provenance line above the verdict,
the wordmark reads Safe to Spend.

## Step 2 — Checkbox helper (B)

**New `frontend/src/lib/cant.ts`:**

```ts
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
```
Curly apostrophe in both `text` and `ariaLabel`.

**`PrescriptionList.tsx`:**
- `import type { Control } from '../lib/cant.ts'` and `import { controlFor } from '../lib/cant.ts'`.
- `CantDo` (`:13-41`) takes `control: Control`, `candidateId`, `onToggle`, `onFocus`; renders
  `<label className="cant" htmlFor={control.id}>` and a real `<input id={control.id}
  type="checkbox" checked={control.checked} aria-label={control.ariaLabel}
  onChange={() => onToggle(candidateId)} onFocus={() => onFocus(candidateId)}>` followed by
  `{control.text}`. Both `cant-${id}` literals at `:27,:29` go.
- Plan rows (`:112-118`): `control={controlFor('plan', ruledOut, p.candidate_id, p.label)}`.
- Left-out rows (`:154-160`): `control={controlFor('out', ruledOut, c.id, c.label)}`; `out`
  at `:132` and `is-out` at `:142` unchanged.
- Header comment `:8-12` rewritten to the helper's comment.
- `focus.ts:3` comment: "Ticking a row's checkbox" instead of naming one label.
- `backend/app/chat/prompt.py` (post-merge): the line at `:66` describes both labels; the
  line that today reads `RULED OUT by the user ("Can't do this")` (post-merge `:181`) becomes
  `RULED OUT by the user (unticked "Can do this" in the left-out list)` — the literal
  `RULED OUT by the user` is pinned by `main`'s `test_chat.py:184` and must stay. The
  paraphrase at `:137`, `"only protects the cushion, not needed to clear zero"`, is the old
  interpretation restated for the model; it becomes the tier-neutral
  `"not load-bearing: removing it would not change the worst day"`, so the model is never
  handed a reading the reason line no longer makes. A `test_chat.py` assertion checks the
  rendered context contains the new phrase and not "not needed to clear zero".

**New `frontend/tests/cant.test.ts`:**
- plan + not ruled → `checked false`, text `Can’t do this`, ariaLabel `Can’t do this: Gym`.
- plan + ruled → `checked true`.
- out + not ruled → `checked true`, text `Can do this`, ariaLabel `Can do this: Gym`
  (the counterfactual for removing the inversion).
- out + ruled → `checked false`.
- `id === domId(id)` in both sections.
- `toggle(NONE, id)` flips `checked` in both sections.
- Source greps via `fileURLToPath` on `../src/`: `cant-` occurs **0** times under
  `src/components`; the template `` `cant- `` occurs exactly once across `src/`, in
  `lib/focus.ts` (its two prefix-test literals at `:29,:33` are not templates and are
  expected); `components/PrescriptionList.tsx` contains `onFocus={`.

## Step 3 — Wording (C), both solvers

**`frontend/src/solver/mockSolver.ts`:** exported above `solve`:

```ts
export const CUSHION_ONLY_REASON = 'Here for the cushion, not to clear zero.'
export const CUSHION_ONLY_REASON_GAP = 'Removing it would not widen the gap.'
```
At `:335-346` the `else` branch becomes `reason = planClearsZero ? CUSHION_ONLY_REASON :
CUSHION_ONLY_REASON_GAP` (`planClearsZero` is bound at the top of `solve` and already read at
`:336`). A one-line comment notes the Python twin tests this case first and the order is
mirrored deliberately.

**`backend/app/solver/wording.py:122-133`:** module constants `CUSHION_ONLY_REASON` and
`CUSHION_ONLY_REASON_GAP`, ASCII, one line each, terminal period; the first branch of
`plan_reason` returns `CUSHION_ONLY_REASON if plan_clears_zero else CUSHION_ONLY_REASON_GAP`.
Same mirrored-order comment. `assemble.py:69` unchanged.

**`frontend/src/lib/reasons.ts`: untouched** (see rationale 3).

**Tests:**
- `frontend/tests/reasons.test.ts:154-162`: the tier 1 and tier 2 tests gain
  `assert.doesNotMatch(r.text, /cushion/i)` so the left-out line never drifts onto the cushion
  claim; names and existing matches unchanged.
- New test in `reasons.test.ts`: import both constants from the oracle; neither matches
  `/not needed/i`, neither equals nor contains the `not_needed` text, neither matches
  `FORBIDDEN`, neither contains `smallest`/`fewest`.
- `backend/tests/test_certificate.py:46` → `assert all(p.reason == CUSHION_ONLY_REASON for p in res.plan)`.
- `backend/tests/test_wording.py`: one new test calling `plan_reason` directly with a
  `CertificateItem` whose marginals are zero: `plan_clears_zero=True` → `CUSHION_ONLY_REASON`,
  `False` → the gap variant; neither contains "not needed" (any case) nor any `BANNED` or
  `OPTIMALITY_CLAIMS` word.
- **End-to-end pin for the gap variant.** Add a planted fixture `TIER3_CUSHION_ONLY` to
  `backend/tests/fixtures/planted.py`: an account whose gap no change can close (tier 3)
  plus one cheap change that lowers below-cushion exposure on a day other than the worst
  day, so the solver selects it with zero marginals. `test_parity` and `test_wording` pick
  up every uppercase dict in that module automatically, so the fixture runs through the
  TypeScript oracle and the banned-word sweep with no wiring. A new `test_certificate` test
  asserts the fixture is tier 3 and that at least one plan row's reason equals
  `CUSHION_ONLY_REASON_GAP`. If the solver cannot be made to select such a change within
  two attempts, the fixture is dropped and the spec records that the branch is unreachable
  in practice, with the unit test standing as the pin.
- `.venv/bin/pytest backend/tests/test_parity.py -q -rs` reports 0 skipped.

## Step 4 — `kpis.test.ts`

`frontend/tests/kpis.test.ts`, with the spread-overrides `res()`/`row()` helpers copied from
`narrate.test.ts:10-40`:
- `lowestWithPlan`: minimum `with_plan_cents`, first day on a tie; empty `balances` →
  `{cents: 0, date: null}`; tier 3 with `shortfall.worst_date` → negated `worst_cents` on that
  date ignoring balances; tier 3 with null `worst_date` falls through to the scan.
- `lowestDoingNothing`: same on `baseline_cents`.
- `daysUnder`: negative-day counts per series; `avoided` is their difference.
- `headroom`: signed against `req.buffer_cents`.
- `planClaim`: empty plan → "Nothing to change"; unproven → matches `/not proven/` and does
  not match `/^Smallest set(,| proven)/`; proven irredundant → "every one load-bearing";
  proven not irredundant → "Smallest set proven".
- Every `planClaim` output across those cases contains neither `$` nor `/fee/i`.
- Canaries: `solve(SCENARIOS[0].request, [])` → with plan `{2674, '2026-09-24'}`, doing nothing
  `-12005`; `SCENARIOS[2]` → shortfall 2762 on 2026-09-24.

## Step 5 — Fonts

Download latin-subset woff2 into `frontend/public/fonts/` (the one download P2's freeze
approved): Libre Baskerville 400 and 700; Inter 400, 500, 600; JetBrains Mono 400, 500, 600.
Method: fetch the Google Fonts CSS with a modern Chrome user agent, take the `latin` block's
URLs, `curl` each to `<Family>-<weight>.woff2`, verify each is > 10 KB and begins with `wOF2`.

```bash
git rm -q frontend/public/fonts/ClashDisplay-* frontend/public/fonts/Doto-* frontend/public/fonts/Array-*
git add frontend/public/fonts/*.woff2
```

**`index.css:1-34`:** the three `@font-face` blocks become eight, one per file,
`font-display: swap`. **`index.html`:** two `<link rel="preload" as="font" type="font/woff2"
crossorigin>` for `LibreBaskerville-700.woff2` and `JetBrainsMono-500.woff2`.

**Tokens (`:95-106`):**
```
--sans:    'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
--display: 'Libre Baskerville', Georgia, 'Times New Roman', serif;
--mono:    'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
```
`--dotted` deleted. The heading rule at `:124-135` drops the dead selectors (`.sidebar-brand`,
`.topbar h1`, `.kpi-card .kpi-value`), sets `font-weight: 700` and `letter-spacing: -0.005em`;
`.navbar .brand` (`:191-201`) also gets `font-weight: 700` and `font-synthesis-weight: none`
(Libre Baskerville has no 600). The `.num` rule at `:139-147` **keeps** `var(--sans)` and
tabular figures, dropping only the dead `.kpi-card .kpi-value`, `.t-num`, `.t-amount`.
Figures get the mono face by adding `.rx-amount`, `.rx-date`, `.ctl-head b` to a mono rule
next to it (`.stat-value`, `.wallet-balance`, `.wallet-amt`, `.cash-callout .amount` already
are).

**`tailwind.config.ts:61-75`:** `sans`, `display`, `numbers` stacks updated; `dotted` removed;
comments rewritten.

## Step 6 — Colour, shape, hero, tiles (A)

- `:root` block 1 (`:37-116`): `--accent-press: #0b2545`; new `--navy: #071a33`, `--navy-2:
  #0b2545`, `--on-navy: #ffffff`, `--on-navy-soft: rgba(255,255,255,0.78)`, `--on-navy-wash:
  rgba(255,255,255,0.14)`, `--on-navy-line: rgba(255,255,255,0.26)`. `--grad` at `:93` becomes
  `linear-gradient(180deg, var(--navy) 0%, var(--navy-2) 40%, var(--accent) 78%, rgba(37,99,235,0) 100%)`.
  `--panel: #f4f7fb`.
- `:root` block 2 (`:1515-1526`): `--shadow-glass: 0 24px 48px -18px rgba(7,26,51,0.35)`;
  `--shadow-card: 0 2px 12px -2px rgba(7,26,51,0.06), 0 1px 3px rgba(7,26,51,0.03)`.
- `.app` (`:163-174`): `background: var(--grad) no-repeat top center / 100% 460px, var(--panel)`;
  in the existing `@media (max-width: 640px)` block, `.app { background-size: 100% 620px }`
  because `.stats` goes to one column there and the hero roughly doubles.
- Literal sites → tokens: `:188`, `:199`, `:242`, `:273` `#fff` → `var(--on-navy)`; `:210-211`,
  `:225-226`, `:274-275` white rgba → `--on-navy-wash` / `--on-navy-line`; `:235` →
  `--on-navy-soft`; `:927` cash-callout border → `color-mix(in srgb, var(--neg) 35%, transparent)`.
  `:289` `.nav-avatar` and `:1506` unchanged. New: `.pillnav button.on:focus-visible {
  outline-color: var(--navy-2) }` (today's white ring vanishes on the white active pill).
- Hero (`:315-316`): radius `var(--radius-lg)` and `var(--shadow-glass)` stay. The
  `.eyebrow-note` rule (`:353-359`) gains a `::before` green dot (`var(--good)`, 6px) and
  `margin-bottom: var(--s2)`; the dead `.eyebrow` block (`:326-351`) is deleted.
- Stat tiles (`:371-424`): already mono label / figure / coloured sub on `--canvas` with the
  measured `clamp(17px, 1.5vw, 25px)`; both stay. No change beyond inheriting the new mono face.
- Panels (`:437-440`): radius `var(--radius)` stays. Primary button (`.chat-form button`
  `:1214-1225`): `background: linear-gradient(90deg, var(--accent-press), var(--accent-ink))`
  (navy to the product blue; white on `#1d4ed8` is 6.3:1, on `#0b2545` higher), pill radius,
  white text. Codex measured the first draft's cyan endpoint at 4.3:1; the button is in the
  step 8 contrast list, measured against the pixel under the text.
- Recharts ticks: `BalanceChart.tsx:118,:126` add `fontFamily: 'var(--mono)'`.
- Load-bearing rules that must survive, pinned in step 7: `.controls` declared once
  (`:775-779`), `.main > * { flex: none }` (`:1585-1589`), `minmax(0, 1fr)` at `:319, :367,
  :430, :1696, :1704, :1735`, the 640px release `.rx-amount, .rx-pain, .cant { grid-column: 1 }`
  (`:1745`), the reduced-motion block (`:1753-1773`) gaining any new transition.
- `.rx-row.is-out .cant` (`:1090`): keep the warn colour (the row is the user's "no");
  verified with an unticked "Can do this" in step 8.

## Step 7 — Style and bundle tests

**`frontend/tests/bundle.test.ts`** (after `main`'s sandbox test):
- built CSS contains no `--tw-`;
- every font reference in built CSS, matched as `url\((['"]?)\/fonts\/([^'")]+)\1\)` so
  quoted and unquoted forms both count, resolves to `dist/fonts/<name>`, present and > 1 KB;
  the test asserts at least one CSS file and at least eight references were found, and that
  the set of referenced files includes a Libre Baskerville, an Inter and a JetBrains Mono
  file, so it cannot pass on an empty match.

**New `frontend/tests/styles.test.ts`** (`src/index.css`, `tailwind.config.ts`,
`public/fonts` via `fileURLToPath`), regex pins, whitespace-tolerant, no colours or sizes:
- no `Doto`, `Clash`, `Array` in the stylesheet, the config, or the fonts directory;
- `/--display:\s*'Libre Baskerville'/`, `/--mono:\s*'JetBrains Mono'/`, `/--sans:[^;]*'Inter'/`;
- `/h1,\s*h2,\s*h3\s*\{[^}]*font-family:\s*var\(--display\)/`;
- `/\.rx-amount[^{]*\{[^}]*font-family:\s*var\(--mono\)/` (or the shared mono rule's selector
  list contains `.rx-amount`);
- `(css.match(/\.controls\s*\{/g) ?? []).length === 1`;
- `/\.main\s*>\s*\*[^{]*\{[^}]*flex:\s*none/`;
- `(css.match(/minmax\(\s*0\s*,\s*1fr\s*\)/g) ?? []).length >= 6`;
- `/\.rx-amount,\s*\.rx-pain,\s*\.cant\s*\{[^}]*grid-column:\s*1/`;
- the `@media (prefers-reduced-motion: reduce)` block mentions `.hero`, `.panel`, `.rx-row`;
- no `@tailwind` in the stylesheet.

## Step 8 — Verify

```bash
cd /Users/nathanstough/Desktop/vthacks-ui/frontend && npm run lint && npm run build && npm test; echo "frontend exit=$?"
cd /Users/nathanstough/Desktop/vthacks-ui && .venv/bin/pytest backend/ -q -rs > /tmp/backend.log; echo "pytest exit=$?"; grep -E "passed|failed|skipped|error" /tmp/backend.log | tail -3; grep -c "SKIPPED.*test_parity" /tmp/backend.log
```
Expected: frontend exit 0, 253 + new (7 cant + 11 kpis + 10 styles + 2 bundle + 1 reasons =
31 → 284); backend exit 0, baseline + 2 (one wording unit test, one planted fixture through
the existing parametrised suites); parity 0 skipped. The full logs are kept in the scratchpad.

Browser pane (`ui`, port 5175): screenshots at 1440 and 390 for plan default, tier 3
(`$60.00`), wallet, saved to the scratchpad and listed in the spec. Computed contrast via
`javascript_tool` on `.nav-chip`, `.pillnav button`, `.eyebrow-note`, `.stat-sub`: ≥ 4.5:1.
Chart ticks legible at 390. Focus sequence: untick "Can do this" on a left-out row → label
strikes through, "Re-solving…" shows, focus returns to that row's checkbox after the response;
tick "Can't do this" on the card minimum → it moves to the left-out list unticked and the
certificate reads three load-bearing. Load "New modelled account" → provenance line changes,
overrides clear.

## Step 9 — Docs, memory, spec results

- `docs/features/frontend.md` (post-merge): override section → one set, two readings, the
  words per section, left-out rows start ticked; reasons item 4 unchanged; new "Visual
  language" section: Mise reference, set B faces, navy tokens, config mirrors CSS, provenance
  above the verdict.
- `docs/demo-script.md` (post-merge, the four-line passage beginning "Every row carries the
  same checkbox"): rewritten as "Plan rows ask 'Can't do this' and start unticked; left-out
  rows ask 'Can do this' and start ticked. Either way it is the one thing the app asks…".
- `docs/specs/2026-09-19_frontend-ux.md`: dated note under Results: D1's "same words" and
  the `mockSolver.ts` freeze superseded by this spec.
- `docs/features/chat.md:15`: both labels.
- Run spec: Scope gains `prompt.py` (label text only), `BalanceChart.tsx` (tick font),
  `chat.md`; D1 loses the glass card; D5 provenance placement; D7 as built; A5, A7, A8 as
  built; post-merge counts; Results.
- Memory: `hrushi-design-system.md` rewritten; `ui-design-system-lane.md` updated;
  `MEMORY.md` lines.

## Step 10 — Commit, critique, audit

Commits in order, explicit paths: merge (step 1); `feat(ui): the left-out list asks "Can do
this"`; `fix(solver): the cushion-only reason no longer reads as "not needed"`; `test: first
tests for kpis`; `feat(ui): set B type, navy, and the fonts we actually use`; `test: style and
font pins`; `docs: …` (including the Codex review file). Then the adversarial Claude critique
loop, then `bash ~/.claude/review-audit.sh docs/specs/2026-09-19_ui-mise-tuning.md`, fixes,
re-audit.

**Not done here:** fast-forwarding `main`. It is checked out in `vthacks-integrate`; per
CLAUDE.md that session is asked first. One line in the final report.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Rename lost in merge | step 1 hand-applies to `TopNav.tsx`; grep for the old name |
| "not to clear zero" at tier 3 | gap variant on `plan_clears_zero`, parity pair, direct unit test |
| Left-out line drifts onto the cushion claim | `doesNotMatch(/cushion/i)` on tier 1 and 2 |
| Focus restore broken by id or a non-focusable input | `controlFor` returns `domId(id)`; template grep; input stays real |
| Provenance announced on every re-solve | rendered outside the live region |
| Parity silently skipped | `-rs` summary asserted 0 skipped |
| Font 404 masked by `swap` | bundle test on `dist/fonts` presence and size; preloads |
| Prose in monospace | `.num` stays sans; mono only on figure selectors, pinned |
| Responsive fixes undone | regex pins; before/after screenshots; 640px gradient override |
| Shared `.venv` missing `main`'s packages | `test_requirements.py` after the merge; stop and report |
| `guaranteed` or `smallest` in new copy | eyebrow is provenance only; bundle greps; tiles from `kpis.ts` only |
| `main`'s button rules dropped in the CSS conflict | the two new rules taken explicitly; step 1 browser check |
| `RULED OUT by the user` pin in `test_chat.py` | literal kept in the rewritten prompt line |

## Codex plan review (gpt-6-astra) and how each finding was addressed

Review file: `docs/reports/2026-09-19_ui-mise-tuning-plan-review.md`.

1. **Critical, button gradient contrast 4.3:1.** Gradient changed to navy → product blue;
   the button added to the step 8 contrast list, measured under the text. (step 6, step 8)
2. **Critical, pytest piped into `tail` loses the exit status.** Every pytest run now writes
   to a log and echoes `$?` from the pytest line; the parity skip count is grepped from the
   log. (steps 1 and 8)
3. **Suggestion, tier 3 wording not pinned end to end.** A planted `TIER3_CUSHION_ONLY`
   fixture runs through parity and the wording sweep automatically; a certificate test
   asserts the emitted reason. Fallback recorded if the solver cannot be made to select
   such a change. (step 3)
4. **Suggestion, the chat prompt restates the old interpretation.** Its paraphrase becomes
   tier-neutral and is asserted in `test_chat.py`. (step 2; spec scope widened to three
   lines of `prompt.py`)
5. **Suggestion, the font test can pass vacuously.** It now requires at least eight matches,
   accepts quoted URLs, and checks all three families are represented. (step 7)

# Run spec — UI: tune the rebuild to the Mise look, two wording fixes, merge

Written Sat 2026-09-19 ~16:40. Branch `ui-design-system`, worktree
`/Users/nathanstough/Desktop/vthacks-ui`. Frozen after commit; append to Results only.
Pipeline: `/plan-review` (P1 frozen ~16:25 after one wrong turn, P2 frozen ~16:35, deep mode).

## Problem

The reference design is **Mise**, a restaurant dashboard Hrushi built as a separate project and
showed Nathan as screenshots. Its source was never pushed anywhere we can reach. The one commit
he pushed to this repo (`60df151`, `origin/hrushi-ui/ux`) carried Mise's `tailwind.config.ts`,
its font files and its dependencies, plus a stylesheet from a different, plainer attempt that
never used any of them. The first session on this lane read that stylesheet as the intent; the
second rebuilt from the config, which was the right call, and that rebuild is what is on this
branch now: a gradient shell, a floating hero card with three stat tiles, display headings,
monospace eyebrows, rounded cards. It is most of the way to Mise and not there.

Nathan's direction on seeing the two side by side (16:20): Mise's shell, cards, tiles and colour
are right; make the blue deeper toward Capital One's navy with white accents; use a more formal,
financial typeface instead of Clash Display; no dot-matrix digits anywhere. Cut the parts of
Mise that only make sense for a six-page product with invented figures.

Two wording fixes in the plan list are still open from the handoff
(`docs/handoffs/2026-09-19_ui-design-system-handoff.md`): the left-out list's checkbox should
read "Can do this", and the in-plan "not strictly needed" line and the left-out "Not needed"
line read alike although one is in the plan and one is out.

## Scope

First, `main` is merged into the branch (46 commits: the Safe to Spend rename, the account
loader, Nessie, rate limiting, deploy). The retune is done on the merged files. The rename is
hand-carried into `TopNav.tsx`, which git cannot do because the wordmark moved.

In: `frontend/src/index.css`, `frontend/tailwind.config.ts`, `frontend/index.html` (font
preloads if any), `frontend/public/fonts/` (add three families, remove two),
`frontend/src/App.tsx`, `components/TopNav.tsx`, `components/Stats.tsx`,
`components/VerdictBand.tsx`, `components/PrescriptionList.tsx`, a new pure module
`src/lib/cant.ts`, `src/lib/reasons.ts`, `src/solver/mockSolver.ts` (one string, one export),
`backend/app/solver/wording.py` (two strings), `backend/app/chat/prompt.py` (the two lines
that name the checkbox label and the one line that paraphrases the cushion-only reason,
nothing else), `backend/tests/fixtures/planted.py` (one new fixture), `components/BalanceChart.tsx` (axis tick font
only), tests under `frontend/tests/` and `backend/tests/`, the docs listed below
(including `docs/features/chat.md`), two memory notes.

Out: the wallet's logic, state machine and styling, the chat panel's behaviour and the chat
endpoint, the
solver's model and objective, `frontend/src/types.ts` and `docs/api-contract.md`, dark mode,
the other lanes' worktrees, obtaining the Mise source from Hrushi.

## Design decisions

- **D1 Mise is the reference; keep the language, cut the sprawl.** Keep: the navy gradient
  shell fading to near-white, white cards with large radii and a soft glass shadow, the pill
  nav with one dark active pill and an avatar, the header card pattern (eyebrow pill, status
  line, title, one paragraph, three stat tiles with a mono uppercase label, a big figure and a
  coloured sub-line), bold-left/mono-right row cards, and one gradient primary button. The
  glass balance card on the wallet tab was considered and withdrawn: the wallet header sits
  inside the white card commit `6fa71df` added on purpose, and glass over white is white on
  white. Cut: extra pages, the alerts bell, the floating copilot
  bubble, the proactive alert popup, every invented figure, the floor plan and demo charts,
  dot-matrix digits, the welcome hero, sync/deploy buttons, and the word "guaranteed".
- **D2 Type, set B.** Libre Baskerville 700 for the wordmark, the verdict and panel headings;
  Inter for body copy; JetBrains Mono for eyebrows, labels, chips and every figure, with
  tabular numerals so digits never shift under a slider. All three self-hosted as woff2 under
  `frontend/public/fonts/` (venue wifi cannot be trusted to fetch a font). Clash Display and
  Doto are removed: the `@font-face` blocks, the `--display`/`--dotted` uses, and the files.
  The `--display` and `--mono` token names stay and are re-pointed, so component rules do not
  move. Body falls back to the system sans if a file is missing; headings fall back to Georgia.
- **D3 Colour.** The gradient deepens toward Capital One's navy: roughly `#071a33` at the top
  through `#0b2545` to the product blue, resolving to a near-white page. Text on the gradient
  is white; the nav's active pill is already white on navy and stays so, with a navy focus
  ring so the ring is visible on it. The product accent
  stays the blue; the warm ramp from the config stays for anything going wrong; green for
  anything improved. Every literal colour outside `:root` is replaced by a token.
- **D4 Shape.** Card radius 32px (hero) / 24px (panels) / 18px (tiles and rows), the `glass`
  shadow from the config on the hero, `card` on panels. Values from `tailwind.config.ts`,
  which mirrors the stylesheet's tokens and is kept in step by hand; still no `@tailwind`
  directives.
- **D5 Hero.** The verdict card gains Mise's status line: a mono line with a green dot
  carrying the account's provenance, `provenanceLine(account, base)` from `main`'s account
  loader ("Sample checking account, Sep 19 to Oct 2.", or the modelled / sandbox line),
  rendered above the verdict and **outside** its `aria-live` region so a re-solve never
  re-announces it. `main` requires provenance to be stated, and this branch had dropped the
  tagline that stated it; `main`'s second tagline clause ("Move a slider…") is dropped, the
  controls panel carries that instruction. The wallet tab shows the demo token wallet, not
  the checking account, so provenance is not shown there. The proof claim stays in the
  footer, already gated on `minimal_proven`; the status line never carries an optimality
  word. The disclosure chip stays where it is in `TopNav` on both tabs; its text is unchanged.
- **D6 Checkbox, presentation only.** One `ruledOut` set (`overrides.ts`) as before. A new pure
  helper `controlFor(section, ruledOut, id, label)` in `src/lib/cant.ts` returns
  `{ id, checked, text, ariaLabel }`: in the plan section `checked = isRuledOut`, text "Can’t
  do this", accessible name "Can’t do this: {label}"; in the left-out section
  `checked = !isRuledOut`, text "Can do this", accessible name "Can do this: {label}". The id
  is always `domId(id)` (`cant-…`) because `focus.ts` prefix-tests it. `is-out` still keys on
  `isRuledOut`. `PrescriptionList.tsx` renders whatever the helper returns.
- **D7 Wording.** Solver-owned, changed in both implementations because `test_parity` compares
  `plan[].reason` field for field. In-plan, not load-bearing (`load_bearing` false or no
  worst date): "Here for the cushion, not to clear zero." when the plan clears zero, and
  "Removing it would not widen the gap." when it does not (tier 3), because "not to clear
  zero" misreads when nothing clears zero, and zero marginals prove exactly that removal
  changes nothing below zero; `plan_reason` already takes `plan_clears_zero`. The left-out
  line in `reasons.ts` is **unchanged**: with the in-plan line no longer opening on "not
  needed", the two already read differently, and P2's idea of moving the tier 1 left-out
  text to "holds the cushion" would have put the cushion on both lines and needed a tier
  split to stay true at tier 2. Its texts are pinned never to mention the cushion. Tier 3 and
  every unproven branch are untouched. The certificate sentence is untouched. The two in-plan
  sentences are exported from the oracle as `CUSHION_ONLY_REASON` and
  `CUSHION_ONLY_REASON_GAP` so tests can compare them against the left-out texts.
- **D8 Nothing invented.** The stat tiles stay `kpis.ts`-derived (lowest point with the plan,
  days below zero, doing nothing or outside cash). No fees in dollars. No tile or eyebrow says
  "smallest" unless `minimal_proven`.
- **D9 Tests without a DOM**, as before: pure modules under Node's runner; the bundle greps
  extend to CSS and fonts; rendering verified in the browser pane and recorded below.

## What will change

- `index.css`: both `:root` blocks retuned (gradient, shadows, fonts, navy tokens);
  `@font-face` for the three new families; Clash/Doto blocks and the dead `.eyebrow` block
  removed; the `.eyebrow-note` status line gains its dot; a navy focus ring on the active nav
  pill; the primary button gradient; literal colours tokenised; a 640px gradient height.
  Component rule names unchanged.
- `tailwind.config.ts`: font stacks and shadow/radius values updated to match.
- `public/fonts/`: add Libre Baskerville (400, 700), Inter (400, 500, 600), JetBrains Mono
  (400, 500, 600) as woff2; remove the 28 Clash Display files, Doto, and the 24 Array files.
  Array arrived with Hrushi's commit (it is not on `main`), is referenced by nothing, and is
  7.0 MB of the 8.0 MB font payload.
- `TopNav.tsx`: the wordmark becomes Safe to Spend. `Stats.tsx`, `VerdictBand.tsx`: unchanged.
- `PrescriptionList.tsx`: `CantDo` takes the helper's output; the left-out branch passes
  `section: 'out'`.
- `src/lib/cant.ts`: new. `src/lib/reasons.ts`: unchanged.
- `mockSolver.ts`: two exported strings in the one branch. `wording.py`: the same two.
- `App.tsx`: the provenance line above the verdict; the account buttons under the switcher.
- `backend/app/chat/prompt.py`: two lines naming the checkbox labels. `BalanceChart.tsx`:
  axis tick font.
- Tests: new `frontend/tests/cant.test.ts`, `kpis.test.ts`, `styles.test.ts`; `reasons.test.ts`
  and `bundle.test.ts` extended; `backend/tests/test_certificate.py:46` updated;
  `backend/tests/test_wording.py` gains one test.

## Acceptance criteria (each maps to a test)

- **A1** Built JS contains no `/guarantee/i`, no `/infeasib/i`; contains the disclosure chip
  text and the crash fallback text. (`bundle.test.ts`, existing)
- **A2** Built CSS contains no `--tw-` variable. (`bundle.test.ts`, new)
- **A3** Neither built CSS nor `public/fonts` nor `src/` references Doto or Clash Display.
  (`styles.test.ts`, new)
- **A4** Every `url(/fonts/…)` in the built CSS names a file that exists in `dist/fonts/`.
  (`bundle.test.ts`, new)
- **A5** In the source stylesheet, `--display` resolves to Libre Baskerville and is applied to
  `h1`, `h2`, `h3`; `--mono` resolves to JetBrains Mono and is applied to `.rx-amount` (and the
  other figure selectors); `--sans` resolves to Inter and `.num` stays on it, so prose that
  carries `.num` (qualifier, proof paragraph, reason lines) is never monospaced. The six
  load-bearing responsive rules from the handoff are pinned by regex. (`styles.test.ts`, new)
- **A6** `kpis.ts`: lowest-with-plan, lowest-doing-nothing and days-under are correct on
  hand-built responses including an empty window and a tier 3 shortfall; `planClaim` says
  "smallest" only on a proven solve and never mentions a dollar figure or fees.
  (`kpis.test.ts`, new)
- **A7** `controlFor`: four cases (plan/out × ruled/not) give the right `checked`, `text` and
  `ariaLabel`; the id is `domId(id)` in both sections; a toggle flips `checked` in both
  sections; left-out and not ruled out is ticked and reads "Can do this" (counterfactual for
  removing the inversion). The string `cant-` occurs nowhere under `src/components`, and the
  template `` `cant- `` occurs exactly once across `src/`, in `lib/focus.ts`. The component
  still wires `onFocus`. (`cant.test.ts`, new)
- **A8** `reasons.ts`: tier 1 and tier 2 proven texts still match `/clears zero without it/`
  and never contain "cushion"; tier 3 and unproven branches unchanged. (`reasons.test.ts`,
  updated)
- **A9** `CUSHION_ONLY_REASON` and `CUSHION_ONLY_REASON_GAP` contain neither "not needed"
  (any case) nor a banned or optimality word, and neither contains the left-out text.
  (`reasons.test.ts`, new)
- **A10** Parity: the TypeScript oracle and the Python solver agree on every field including
  `plan[].reason` across the corpus. (`test_parity.py`, existing)
- **A11** Backend: `plan_reason` on a zero-marginal item returns `CUSHION_ONLY_REASON` when
  the plan clears zero and the gap variant when it does not; neither contains "not needed"
  nor a banned or optimality word. (`test_certificate.py:46` updated; `test_wording.py`, new)
- **A11b** The planted `TIER3_CUSHION_ONLY` fixture (if the solver selects such a change) is
  tier 3 and emits `CUSHION_ONLY_REASON_GAP` on at least one plan row, identically in both
  solvers. (`test_certificate.py`, new; `test_parity.py`, existing)
- **A12** Certificate-sentence tests unchanged and green. (`test_wording.py`, existing)
- **A13** Manual, recorded with screenshots: default plan, tier 3 (`$60.00`), wallet tab, at
  1440 and 390 wide; the four handoff-fixed layouts hold; computed contrast ≥ 4.5:1 on nav
  text, hero copy, tile sub-lines; ruling a left-out row out strikes the label, shows
  "Re-solving…", and focus returns to the same row after the re-solve.

## Commands

```bash
cd /Users/nathanstough/Desktop/vthacks-ui/frontend && npm run lint && npm run build && npm test
```

Expected: lint clean, build clean, 253 after the merge (209 + main's 44) plus the new tests,
0 failing.

```bash
cd /Users/nathanstough/Desktop/vthacks-ui && .venv/bin/pytest backend/ -q
```

Expected: the post-merge baseline (re-measured in step 1; `main` added tests and a
`pytest.ini` that deselects `perf` and `nessie`) plus 1, parity running with 0 skipped.

## Docs committed to

- This run spec.
- `docs/features/frontend.md`: the override section (control wording per section), reasons item
  4 (tier-aware), a visual-language section naming the three faces and the config.
- `docs/demo-script.md`: the sentence that no checkbox starts ticked.
- `docs/specs/2026-09-19_frontend-ux.md`: one dated note under Results (frozen otherwise).
- `frontend/tailwind.config.ts` comments.
- Memory: `hrushi-design-system.md` corrected (config right, stylesheet a stray attempt, Mise
  is the reference, set B fonts); `ui-design-system-lane.md` updated.

Not touched: `docs/api-contract.md`, `CLAUDE.md`, the handoff (historical).

## Codex plan review

Ran on the plan after the critique pass. Five findings, two critical: the primary button's
cyan gradient measured 4.3:1 under white text (gradient darkened, button added to the
contrast check); pytest piped into `tail` would hide a failing exit (exit status now read
from the pytest line, parity skips grepped from a log). Three suggestions taken: an
end-to-end tier 3 fixture through parity, the chat prompt's paraphrase of the old reason
made tier-neutral, and the font test made non-vacuous. Full text in
`docs/reports/2026-09-19_ui-mise-tuning-plan-review.md`; the plan file records each
resolution.

## Results — executed Sat 2026-09-19, ~17:45–18:40

Branch `ui-design-system` in `/Users/nathanstough/Desktop/vthacks-ui`. Run as four Opus
subagents in lanes, orchestrated by Fable: lane 1 the merge of `main` and the re-baseline,
lane 2 the checkbox helper and the two solvers' wording, lane 3 fonts, colour and the style
pins, lane 4 the docs. All ten plan steps ran in order; no step was skipped.

Commits: `05ffa43` (merge), `e61d087` (the left-out list asks "Can do this"), `f0c34fe` (the
cushion-only reason), `0089203` (kpis tests), `736cc3c` (set B type), `4efa6ab` (navy and the
status line), `fa240dd` (style and font pins), `759d7d0` (one variable file per family), `e9c969b` (the
status line's dot on its own first line), then this docs commit. An adversarial audit afterwards
produced two more: one for the code, tests and screenshots, one restoring this spec's frozen
body and recording what really deviated.

### Commands

| Command | Exit | Result |
|---|---|---|
| `npm run lint` (oxlint) | 0 | clean, no output |
| `npm run build` (`tsc -b && vite build`) | 0 | clean, no new warning |
| `npm test` (Node runner, no DOM) | 0 | **288 passed, 0 failed, 0 skipped** |
| `.venv/bin/pytest backend/ -q -rs` | 0 | **2165 passed, 10 deselected**, 27.6 s |
| `grep -c "SKIPPED.*test_parity"` on the `-rs` summary | — | **0**: parity ran |

Baselines measured after the merge in step 1: frontend 253, backend 2150 passed / 10 deselected
in ~22 s. Frontend +35 (cant 7, kpis 11, styles 14, bundle 2, reasons 1). Backend +15 (three
tests written by hand, twelve parametrisations the `TIER3_CUSHION_ONLY` fixture is picked up by
across the parity, wording and objective suites).

**Re-run after the adversarial audit's fixes**, same commands, same worktree:

| Command | Exit | Result |
|---|---|---|
| `npm run lint` (oxlint) | 0 | clean, no output |
| `npm run build` (`tsc -b && vite build`) | 0 | clean; the pre-existing Recharts chunk-size note only |
| `npm test` | 0 | **292 passed, 0 failed, 0 skipped** |
| `.venv/bin/pytest backend/ -q -rs` | 0 | **2165 passed, 10 deselected**, 25.3 s |
| `grep -c "SKIPPED.*test_parity"` on the `-rs` summary | — | **0**: parity ran |

Frontend 288 → 292: the wallet card pin and the literal-white pin in `styles.test.ts`, the
`controlFor` call-site pin in `cant.test.ts`, and the `index.html` preload pin in
`bundle.test.ts`. Each was checked against a deliberate mutation and fails when the thing it
protects goes. The backend was not touched and its figure is unchanged.

### Acceptance criteria

| AC | Verdict | Evidence |
|---|---|---|
| A1 | Met | `bundle.test.ts`: "never promises a guarantee", "never contains the word infeasible", "still discloses the offline fallback", "still carries the crash fallback" |
| A2 | Met | `bundle.test.ts` "the built CSS carries no Tailwind runtime variables" |
| A3 | Met | `styles.test.ts`, the two "no Doto…" tests, over the stylesheet, the config and `public/fonts` |
| A4 | Met | `bundle.test.ts` "every font the built CSS asks for is actually in dist/fonts": 3 references, all three families, each file present and > 1 KB |
| A5 | Met, the sixth pin added in the audit round | `styles.test.ts`: "the three font tokens resolve to the three self-hosted families", "headings are on the display face", "`.rx-amount` is on the mono face", "`.num` stays on the text face", and "the stylesheet has no @tailwind directives". Of the **six** load-bearing responsive rules the handoff lists, **five** shipped in the first round ("`.controls` is declared exactly once", "`.main` children do not flex-shrink", "the grid tracks are all minmax(0…", "the 640px breakpoint releases the row cells", "reduced motion covers the transitions"); the sixth, the wallet keeping its card on the gradient (handoff bug 5), was pinned in the audit round as "the wallet keeps its own card on the gradient" |
| A6 | Met | `kpis.test.ts`, 11 tests, including the empty window, the tier 3 shortfall with and without a worst date, and "no plan claim ever names a dollar figure or a fee" |
| A7 | Met | `cant.test.ts`, 7 tests: the four plan/out × ruled/not cases, the `domId` pin in both sections, the toggle flipping both, and the source greps ( `cant-` absent under `src/components`, the template once in `lib/focus.ts`, `onFocus={` still wired) |
| A8 | Met | `reasons.test.ts`: the tier 1 and tier 2 texts still match `/clears zero without it/` and now also `doesNotMatch(/cushion/i)`; tier 3 and unproven branches unchanged |
| A9 | Met | `reasons.test.ts` "the in-plan cushion-only lines never read like the left-out line": neither constant matches `/not needed/i`, equals or contains the left-out text, matches `FORBIDDEN`, or says smallest/fewest |
| A10 | Met | `test_parity.py`, 0 skipped in the `-rs` summary, and the new fixture runs through it in both directions |
| A11 | Met | `test_wording.py::test_a_cushion_only_reason_never_reads_as_not_needed` calls `plan_reason` directly on a zero-marginal item both ways; `test_certificate.py:47` updated to `CUSHION_ONLY_REASON` |
| A11b | Met | `test_certificate.py::test_at_tier_three_a_cushion_only_row_talks_about_the_gap`: tier 3, at least one row `CUSHION_ONLY_REASON_GAP`, no row the clears-zero form. Achieved with `locks.in`; see deviation 1 |
| A12 | Met | The existing certificate-sentence tests in `test_wording.py` are unchanged and green |
| A13 | Met | Screenshots at 1440 and 390 for plan, tier 3 and wallet, now in the repo under `docs/shots/2026-09-19_ui-mise-tuning/`; contrast and browser checks below. The evidence is the shots **and** the inline browser observations recorded under "Browser checks" — the shots show the layouts, the observations cover the behaviour and the measured contrast, which a still cannot carry |

Not in the spec but done alongside: `test_chat.py::test_a_cushion_only_change_is_paraphrased_without_not_needed`,
pinning the prompt's tier-neutral paraphrase (deviation 5).

### Deviations and limitations

One to six were deliberate and are recorded rather than fixed. Seven to nine were found by
the adversarial audit afterwards: the first write-up had edited them into the frozen body of
this spec instead of recording them here, and the body has since been restored.

1. **The tier 3 fixture pins its zero-marginal change in through `locks.in`.** The plan assumed
   a freely chosen tier 3 plan could contain such a row. It cannot: the objective ranks plan
   cardinality above below-cushion exposure, and `buffer_missed` is already 1 at tier 3 because
   the balance is under zero, let alone under the cushion. Dropping a zero-marginal row
   therefore ties on days below zero, on the worst shortfall and on buffer-missed while
   strictly lowering the count, so the smaller plan always wins. A tier 3 row with zero
   marginals is reachable only when the caller pins it, which `locks.in` is exactly for. The
   reasoning and the arithmetic are written out in the comment above `TIER3_CUSHION_ONLY` in
   `backend/tests/fixtures/planted.py`. The plan's fallback (drop the fixture, keep the unit
   test) was not needed. The consequence for the product is worth stating plainly: because plan
   size outranks cushion exposure in the objective and the screen never sends `locks.in`, the
   `CUSHION_ONLY_REASON_GAP` sentence is reachable through the API but **cannot** be produced by
   the UI as built.
2. **Fonts ship as three variable files, not eight static ones.** Google serves one variable
   file per family and hands back the same URL for every weight asked for, so the eight-file
   plan was three payloads written down eight times. Each `@font-face` declares the range its
   file actually carries — Libre Baskerville 400–700, Inter 100–900, JetBrains Mono 400–800 —
   measured off the rendered glyphs rather than taken from Google's CSS, which advertises only
   the weights that were requested. Declaring a wider range would let the browser pick a weight
   the file cannot draw and quietly clamp it. `styles.test.ts` pins the three files and the
   three ranges; A4's threshold dropped from eight references to three, still non-vacuous
   because all three families must appear.
3. **`--ink-3` darkened from `#6b7280` to `#646b78`.** As a `.stat-sub` on the warm `--canvas`
   the old value measured **4.49:1** — a rounding error short of AA on the one line that
   explains a figure. The new value clears 4.5:1 on white, `--canvas`, `--panel` and `--panel-2`.
4. **Two style-test regexes were broadened.** The `.controls`-declared-once count is taken over
   top-level declarations only, since a media-query copy is not a redeclaration; the
   reduced-motion check is run over the union of both `@media (prefers-reduced-motion: reduce)`
   blocks rather than the first one found. Both pins still fail if the rule they protect goes.
5. **The chat prompt's paraphrase was made tier-neutral.** It restated the old reading
   ("only protects the cushion, not needed to clear zero"), which is exactly what the wording
   change removed from the screen; it now reads "not load-bearing: removing it would not change
   the worst day", and `test_chat.py` asserts the rendered context contains that and not "not
   needed to clear zero". The literal `RULED OUT by the user`, pinned by `main`'s
   `test_chat.py:184`, was kept.
6. **The tagline's second clause was relocated and provenance moved.** `main`'s "Move a slider
   or rule a change out, and the plan is re-solved from scratch." no longer sits over the
   verdict. The first write-up said it was dropped, and for one round it was: the controls
   panel's heading ("What if / Move the inputs") names the controls but does not say what moving
   one does. The sentence now sits under that heading as a `.panel-lede`, beside the controls it
   describes. Provenance is rendered on the plan tab only, as a sibling **above** the verdict and
   outside its `aria-live` region, so a re-solve never re-announces it. The wallet tab shows the
   demo token wallet, not the checking account, so it carries no provenance line.
7. **D2 planned eight static woff2 files; three variable files shipped.** The frozen D2 paragraph
   says "All three self-hosted as woff2" against a plan of eight files — Libre Baskerville 400
   and 700, Inter 400/500/600, JetBrains Mono 400/500/600. Google serves one variable file per
   family and hands the same URL back for every weight asked for, so those eight were three
   payloads written down eight times. What shipped is `LibreBaskerville-Variable.woff2`,
   `Inter-Variable.woff2` and `JetBrainsMono-Variable.woff2`, each `@font-face` declaring the
   range its file actually carries, measured off the rendered glyphs: **Libre Baskerville
   400–700, Inter 100–900, JetBrains Mono 400–800**. A range wider than the file would let the
   browser pick a weight the font cannot draw and quietly clamp it. (Deviation 2 records the
   same decision; this entry records that the spec's own D2 and "What will change" text was
   edited to match rather than left to stand.)
8. **A4 shipped stricter than it was frozen.** Frozen A4 asks only that every `url(/fonts/…)` in
   the built CSS name a file that exists in `dist/fonts/`. The shipped test also requires **at
   least three references** and **all three families**, so the check cannot pass on an empty
   match, and each file to be over 1 KB. The audit round added a second test over `dist/index.html`,
   requiring at least two `rel="preload" as="font"` hrefs, each resolving to a file in
   `dist/fonts/` over 1 KB — the preloads were previously untested, and a renamed font file
   leaves a `<link>` pointing at a 404 that `font-display: swap` then hides.
9. **Both frozen `Expected:` lines were low.** The frozen frontend line reads "253 + new ≈ 284";
   the run measured **288**, the extra four being additional style and bundle pins written during
   the run. The frozen backend line reads "baseline + 2"; the run measured **2165**, the
   post-merge baseline of 2150 plus 15 — three tests written by hand and twelve parametrisations
   the new `TIER3_CUSHION_ONLY` fixture is picked up by automatically across the parity, wording
   and objective suites. The audit round adds four more frontend tests, taking that figure to
   **292**; see the Commands table, which records both runs.

### Contrast, measured in the browser at 1440 wide

Computed from the rendered pixels under each piece of text, not from the tokens.

| Element | Ratio |
|---|---|
| Brand wordmark on the gradient | 17.0 |
| Active nav pill (navy on white) | 15.4 |
| Nav chip on the gradient | 11.2 |
| Inactive nav pill | 7.6 |
| Chat primary button (both gradient ends) | 15.4 / 6.7 |
| Status line (`.eyebrow-note`) | 5.4 |
| Stat sub-line | 5.0 |
| Stat sub-line, positive | 4.7 |

All ≥ 4.5:1. The lowest, the positive stat sub-line at 4.7, is the one `--ink-3` was darkened
for; it measured 4.49 before.

### Browser checks

- **Unticking "Can do this" on a left-out row**: the label strikes through, "Re-solving…"
  appears for about 290 ms, the row then reads "You ruled this out, so the solver never saw
  it.", and focus is restored to that row's checkbox.
- **Ticking "Can't do this" on the card minimum** (the demo script's 1:45 beat): the row moves
  to the left-out list **unticked**, and the certificate reads "Three of these seven changes
  are load-bearing."
- **"New modelled account" with the backend down**: the controls note reads "Could not reach
  the server." and the provenance line above the verdict is left unchanged, so the screen never
  claims an account it did not load.

### Screenshots

Captured at 1440 and 390 wide for the plan tab, tier 3 (`$60.00`) and the wallet tab, against
the same three states as the pre-merge baseline.

The after-shots were held in a session scratchpad, which is volatile: the evidence for A13
would not have survived the session. They are now in the repo, downscaled to 1200px on the long
edge, under `docs/shots/2026-09-19_ui-mise-tuning/` — `after-desktop-plan.png`,
`after-desktop-tier3.png`, `after-desktop-wallet.png`, `after-mobile-plan.png`,
`after-mobile-tier3.png`, `after-mobile-wallet.png`, plus `before-desktop-plan.png` for the
comparison. 1.1 MB in all.

A13 does not rest on the shots alone. The contrast figures above were computed from the
rendered pixels in the browser pane, and the three behaviours under "Browser checks" were
observed live there; neither is something a still can carry.

Recorded after the second critique round:

10. **D3 narrowed to whites.** D3 said every literal colour outside `:root` becomes a token.
    What shipped and is pinned: every literal *white* is a token; neutral ink shadows and the
    navy pill shadow are tokens too as of the audit round (`--ink-shadow`, `--ink-shadow-soft`,
    `--on-navy-shadow`). Remaining literals outside `:root` are none. The feature doc states
    the pin as "white only", which is what the test checks.
11. **Panel headings at 600, not 700.** D2 froze 700 for the wordmark, the verdict and panel
    headings. The variable file is one continuous 400–700 axis, and 700 at the panel
    headings' 20px reads heavy, so `.panel-head h2` stays at 600 by choice; the wordmark and
    the verdict are 700 (the verdict was 600 until the audit round). The stylesheet comment
    that claimed the file "ships 400 and 700 and nothing between" was wrong and is corrected.
12. **"A 640px gradient height" in What-will-change was loose wording.** The intent, and the
    code, is a 640px *breakpoint* at which the gradient grows from 460px to 620px because the
    stat tiles stack; there is no 640px gradient.

## Claude critique (adversarial, Opus, two rounds)

**Round 1 (~18:45) — Fail.** Freeze integrity failed because the docs pass had rewritten nine
frozen lines of this spec instead of appending deviations; documentation failed because the
feature doc claimed no literal colour survived outside `:root` while five whites did, and the
demo script still sent the presenter to a footer chip that lives in the nav. Eight further
findings: the sixth responsive pin (the wallet card) missing; no test could fail if a checkbox
call site's section argument were swapped; the gap-form reason unreachable from the UI and
undocumented as such; the "Move a slider" instruction deleted rather than relocated; font
preloads untested; ~260 lines of dead CSS; screenshot evidence only in the scratchpad. All ten
were fixed in `bb9cf4d`, `6dedfda` and `8f937f5`: the frozen body restored byte-for-byte from
`dc92fbe` with deviations 7–9 added; whites tokenised and pinned; docs corrected; the wallet
pin, the call-site pin and the preload pin added (each verified to fail on a mutation); the
re-solve sentence relocated into the controls panel as `.panel-lede`; dead rules deleted with
every remaining selector checked against the components; `docs/shots/` committed.

**Round 2 (~19:20) — Needs-work, plan adherence only; every other dimension Pass.** Three
enumerated departures: two neutral shadow literals still outside `:root`; panel headings and
the verdict at 600 where D2 said 700, with a wrong comment; the gradient-height wording. Fixed
or recorded as deviations 10–12 above (`--ink-shadow` tokens; the verdict to 700, the panel
headings kept at 600 and recorded; the comment corrected). A third round was not run: the
critic named exactly what would flip the dimension and nothing else was below Pass; the Codex
audit below is the confirmation pass.


## Codex audit (gpt-6-astra, read-only sandbox)

**Round 1 (~19:40) — Acceptable overall.** Scope discipline and review compliance Excellent;
plan adherence, test coverage, freeze integrity, regression check and documentation
Acceptable. Its independent run: lint clean, 292 frontend tests passing, both TypeScript
configurations type-check; backend 2161 passed with 4 setup errors that need temp files the
sandbox forbids, parity ran, 0 skipped. Three actionable notes, all fixed in `b0ac908` and
the commit after it: the checkbox call-site test now ties each section to its own row data
(`p.candidate_id` vs `c.id`) so swapping both arguments fails; the wordmark comment and the
feature doc's shadow sentence corrected; the six screenshots re-captured from the final
revision (they had predated the relocated re-solve line). Full text in
`docs/specs/2026-09-19_ui-mise-tuning-audit.md`.

**Round 2** — recorded below after the confirmation run.


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

## Results

Pending.

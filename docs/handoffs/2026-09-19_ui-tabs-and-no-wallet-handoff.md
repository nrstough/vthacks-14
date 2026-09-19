# Handoff — the UI lane: drop the wallet, one tab per card (2026-09-19, ~20:20)

**Purpose of this chat:** run `/plan-review` for the next UI change on branch
`ui-design-system`: delete the Solana demo wallet tab and everything only it uses, then turn
the top-nav pills into three section tabs, Balance / Plan / Ask, with the hero (verdict, three
tiles and the what-if sliders) visible on every tab. P1 is already frozen by Nathan; start at
P2. An Opus session is expected to run this; it does not need the previous session's context
beyond this file and the docs it points at.

## Context

The Mise tuning landed tonight at `4e1bfde` and is audited: two adversarial Claude critique
rounds and two Codex audit rounds, final grade Acceptable with freeze integrity Excellent.
What the page is now: a navy-to-white gradient shell, a nav with the wordmark "Safe to Spend",
two pills (Checking account / Demo wallet), the solver disclosure chip and an avatar; a white
hero card carrying a provenance line, the tier pill, the verdict in Libre Baskerville, the
proof box, and three stat tiles; then four cards in two rows: the balance chart, the what-if
panel (scenario switcher, two account-source buttons, two sliders), the plan list, and the
explainer chat. Read `docs/specs/2026-09-19_ui-mise-tuning.md` for everything that was
decided and why, and `docs/features/frontend.md` for the living description of the screen.

**`main` was merged into this branch at `05ffa43`** (it had moved 46 commits: the Safe to
Spend rename, the account loader, Nessie, rate limiting, deploy). `main` itself is checked out
in `/Users/nathanstough/Desktop/vthacks-integrate`; it cannot be fast-forwarded from here, and
per CLAUDE.md that session is asked first. Memory says merges and pushes are on hold tonight.

Nathan's decisions for this change (19 Sep ~19:45 and ~20:15):
- **The wallet goes.** Solana was dropped from the project. Delete the tab, not just hide it.
- **Three tabs, not four.** The what-if sliders stay in the hero on every tab, because the
  demo's best beat is moving a slider and watching the verdict, tiles and chart move together.
  Tabs are Balance, Plan, Ask. Default tab is Plan.
- The hero stays the headline on every tab.

## Working branch / worktree

`ui-design-system` in `/Users/nathanstough/Desktop/vthacks-ui`, **clean** at `4e1bfde`.
Start in this worktree; do not use the shared checkout at `Desktop/VT Hacks` (it has the
superseded `ui-system` branch checked out and owns the real `node_modules` and `.venv` that
this worktree symlinks to).

```bash
cd /Users/nathanstough/Desktop/vthacks-ui
git branch --show-current   # expect ui-design-system, every time, per CLAUDE.md
git status --short          # expect empty
```

## Environment / setup

`frontend/node_modules` and `.venv` are symlinks into the shared checkout; if either is
missing, symlink it again rather than reinstalling (venue wifi). Dev server: the `ui` entry in
this worktree's `.claude/launch.json`, port 5175, via `preview_start` with name `ui`. The
backend cannot be started from the preview tool in a sandboxed session; the frontend then
falls back to its local solver and the nav chip discloses it, which is correct. The two
account-source buttons show "Could not reach the server." when the backend is down; also
correct.

Screenshots for evidence: the preview pane cannot save images, so use headless Chrome over
CDP. The script is now in the repo:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --remote-debugging-port=9222 --user-data-dir=/tmp/shoot-profile --no-first-run about:blank &
sleep 3 && node frontend/scripts/shoot.mjs http://localhost:5175 after && pkill -f remote-debugging-port=9222
```
It clicks the `$60.00` scenario for tier 3 and the "Demo wallet" pill; **the wallet click
will report `missing` once the tab is gone, which is expected — edit the script to capture
the three new tabs instead.** Downscale with `sips -Z 1200` before committing under
`docs/shots/<spec-name>/`.

## What to do next

Run `/plan-review` from P2 (P1 below is frozen). The change is one run spec.

### P1, frozen

Problem: the demo wallet is dead weight now that Solana is dropped, and the plan tab stacks a
hero and four cards that Nathan finds hard to read as one page. Approach: (1) delete the
wallet and everything only it uses; (2) the pill nav becomes the section tabs Balance / Plan /
Ask; the hero, with the sliders moved into it, stays on every tab; Plan is the default.

### The wallet's footprint (measured at `4e1bfde`)

- `frontend/src/wallet/` — seven files: `WalletView.tsx`, `fixtures.ts`, `ledger.ts`,
  `receipt.ts`, `state.ts`, `types.ts`, `units.ts`, `view.ts`.
- `frontend/tests/wallet-{ledger,receipt,state,units,view}.test.ts` — 110 tests. The suite
  drops from 292 to about 182; that is expected and must be recorded, not "fixed".
- `frontend/src/App.tsx`: the lazy `WalletView` import and its comment, the `tab` state's
  `'wallet'` value, the wallet branch with its own `ErrorBoundary inline={…}` and `Suspense`.
- `frontend/src/components/TopNav.tsx`: the "Demo wallet" pill; the `Tab` type.
- `frontend/src/components/ErrorBoundary.tsx`: a comment about the wallet chunk, and check
  whether the `inline` prop has any other caller once the wallet is gone (if not, it may go).
- `frontend/src/index.css`: 41 `.wallet*` rules, plus `.wallet` in the reduced-motion block
  and in `styles.test.ts`'s sixth responsive pin ("the wallet keeps its own card on the
  gradient"), which must be retired with a note, not left failing.
- `frontend/tests/bundle.test.ts`: nothing wallet-specific, but `npm run build` currently
  reports two chunks; after deletion there is one. Check no assertion depends on the chunk.
- Docs mentioning the wallet tab: `docs/features/frontend.md` (the tab, the boundary story,
  the sixth pin), `docs/demo-script.md` (check; wallet may not be in the script), the
  ui-mise-tuning spec (frozen; a dated note only), `docs/prize-strategy.md` (Solana track;
  Nathan's call whether to edit), memory `solana-wallet-lane.md`. The Solana handoffs, specs
  and reports stay as history.

### The tabs

- The `TopNav` pills become Balance / Plan / Ask, `aria-current="page"` on the active one,
  the disclosure chip and avatar unchanged. The tier-3 alarm dot on the "Checking account"
  pill needs a new home: on the Plan pill, or drop it since the hero is always visible.
- `App.tsx` renders the hero always, then exactly one of: the chart panel, the plan panel
  (with its "Clear n overrides" action), the chat panel. Keep every panel's markup and
  class names; the CSS `.duo` grids go, and the single card can go full width under the hero.
- The sliders move into the hero under the tiles (the scenario switcher and the two
  account-source buttons with them, or leave those in a slim row — a P2 decision). The
  `.controls` rule must still be declared exactly once (a style pin), and the what-if panel's
  `aria-label` and the `.panel-lede` re-solve sentence must survive somewhere visible.
- **Focus restore** (`lib/focus.ts`, the effect in `App.tsx`) assumes the plan list is
  mounted when a response lands; if a re-solve arrives while the Balance tab is showing, the
  checkbox it wants to focus is unmounted. Decide the rule (do nothing when the plan tab is
  not showing) and pin it in `focus.test.ts` with a counterfactual.
- The `aria-live` verdict region and the provenance line above it stay as they are.
- Product commitments that tests enforce and that a tab layout can break: the bundle must
  still contain "Running on the built-in solver", "This page stopped working" and "Capital One
  sandbox"; no "guarantee" or "infeasib"; every white on the gradient a token; the six
  responsive pins minus the wallet one.
- The demo script (`docs/demo-script.md`) walks slider → verdict → chart → plan → chat; with
  tabs, each beat needs to say which tab is showing. Update it as part of the change.

### Then

Merge `main` into the branch again before finishing if it has moved (`git log --oneline
ui-design-system..main`), run both suites, screenshots at 1440 and 390 for the three tabs and
tier 3, commit with explicit paths, the Claude critique loop, the Codex audit
(`bash ~/.claude/review-audit.sh <run-spec>`), and present. Do not fast-forward `main`.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

- Test: `cd /Users/nathanstough/Desktop/vthacks-ui/frontend && npm run lint && npm run build && npm test`
  → expected **292 passing, 0 failing** before the change; about **182** after the wallet
  tests are deleted. `npm test` reads `dist/`, so `npm run build` must run first.
- Test: `cd /Users/nathanstough/Desktop/vthacks-ui && .venv/bin/pytest backend/ -q -rs`
  → expected **2165 passed, 10 deselected**, ~25 s, and **0** lines matching
  `SKIPPED.*test_parity` (parity needs `node` on the path; a skipped parity suite is how a
  wording divergence ships). Nothing in this change should move the backend count.
- Test: `.venv/bin/pytest backend/tests/test_requirements.py -q` → 2 passed (the shared
  `.venv` has `main`'s packages; do not install into it).
- Read exit codes from the command itself, never after a pipe into `tail`.
- At-risk: nothing uncommitted. The screenshots from tonight are committed under
  `docs/shots/2026-09-19_ui-mise-tuning/` (1.1 MB); the scratchpad copies will be swept.
- In flight: nothing. No background jobs, no cloud runs, no open PRs. The `ui` dev server on
  5175 dies with the session; start it again with `preview_start`.

## Analytical notes

- **Merge `main` first, always.** The last change did this as step 1 and it was the step
  that found the "Safe to Spend" rename would otherwise have been lost (the wordmark had
  moved into `TopNav.tsx`, so git resolved the rename "cleanly" by dropping it). Check
  `git diff --name-only $(git merge-base main HEAD) main` against the files you touch.
- **Freeze integrity.** The run spec is frozen once committed; append to Results only. The
  first docs pass tonight rewrote frozen lines and failed the critique for it. Record what
  differs as numbered deviations instead.
- **No DOM in the test suite.** Logic lives in pure modules under `src/lib/` tested by Node's
  runner (`--experimental-strip-types`: explicit `.ts` extensions on value imports, type-only
  imports for types, no enums, `fileURLToPath` for file paths). Rendering is verified in the
  browser pane and by the CDP screenshots. A tab switch is React state, so put the "which
  panel is showing, what happens to focus" rule in a pure function and test that.
- The oracle `frontend/src/solver/mockSolver.ts` is executed directly by the backend's parity
  suite (`backend/tests/oracle/dump.ts`); it does not change in this work.
- Contrast on the gradient was measured tonight: nav chip 11.2, inactive pill 7.6, status line
  5.4, stat sub-lines 5.0 and 4.7; `--ink-3` is `#646b78` for that reason. Anything new on the
  gradient uses the `--on-navy*` tokens and gets measured.
- The Codex audit runs in a read-only sandbox: it cannot `vite build` and four backend tests
  that need temp files error there. Record the unrestricted runs in the spec so the auditor
  can lean on them.

## Pointers

Read first, in this order:
- `CLAUDE.md` — the working agreement and the "deliberate, do not fix" list.
- `docs/specs/2026-09-19_ui-mise-tuning.md` — every decision behind the current screen, the
  twelve recorded deviations, both critique rounds, both audit rounds.
- `docs/features/frontend.md` — the living description: override model, reasons, visual
  language, the six pinned rules.
- `docs/demo-script.md` — the four-minute script the tabs must serve.
- `frontend/src/App.tsx`, `components/TopNav.tsx`, `lib/focus.ts`, `tests/styles.test.ts`.
- Memory: `ui-design-system-lane`, `hrushi-design-system`, `main-integration-2026-09-19`,
  `vthacks-concurrent-session-collisions`.

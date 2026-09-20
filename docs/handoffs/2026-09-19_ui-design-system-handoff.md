# Handoff — the UI/UX lane on the imported design system (2026-09-19)

**Purpose of this chat:** Land two agreed wording fixes in the prescription list, then
merge the UI rebuild. The visual work is done, committed and verified; what is left is
two small changes that both touch wording the solver owns, so neither is as local as it
looks.

## Context

Hrushi pushed a design to `origin/hrushi-ui/ux` in one commit that changed two things at
once: it rewrote `frontend/src/index.css` into an indigo Stripe-style dashboard, **and**
it added `frontend/tailwind.config.ts` describing something else entirely.

The first attempt read the stylesheet as the intent and replaced the config. That was
backwards, and it cost a full rebuild. **`tailwind.config.ts` is the design system.** It
carries the cool `#f0f4f9` page, the warm brand ramp for anything going wrong, the
18/24/32px radius scale, the `glass` shadow, Clash Display, and `numbers`/`dotted`
pointing at a monospace.

Nathan's font rule only parses against that config — keep the bold face, change the body
face — because the body face there is Plus Jakarta Sans, not a system stack.

What is on screen now: a gradient header with the wordmark, view pills and the solver
disclosure chip; one white card lifting off that gradient carrying the verdict on the left
and its three figures on the right; the rest of the product as rounded cards on the cool
background.

Type: Clash Display for the wordmark, the verdict and every panel heading. **Arial GT** for
body copy, falling back to Arial — no machine here has Arial GT, and Arial is metrically
compatible, so the layout does not move between them. Monospace for eyebrows, labels and
figures. Doto stays wired as `--dotted` for decoration only; it is a dot-matrix face and is
deliberately kept off anything read as a balance.

Every `:root` token was retuned in place rather than renamed, so the ~1700 lines of
component rules below them moved to the new system without being rewritten. That property
is worth preserving.

## Working branch / worktree

`ui-design-system` in `/Users/nathanstough/Desktop/vthacks-ui`. **Clean**, nothing
uncommitted.

```
6fa71df fix(ui): the wallet tab had no card, so it sat on the gradient
a8d2c33 chore(ui): a dev server entry for this worktree, on its own port
9f4bf17 feat(ui): rebuild on the design system the config actually describes
c8d19c7 feat(ui): the imported design system, applied to the whole demo   <- first attempt
60df151 feat(ui): update frontend styling, tailwind config, typography     <- Hrushi's import
```

`ui-system` is the superseded first attempt. It is fully contained in this branch and is
still checked out in the shared checkout at `/Users/nathanstough/Desktop/VT Hacks`. Delete
it once this merges.

## Environment / setup

**Start the new chat directly in this worktree.** The previous session moved here
mid-flight and its preview tooling stayed bound to the old folder, which cost a detour.

```bash
cd /Users/nathanstough/Desktop/vthacks-ui
git branch --show-current   # expect ui-design-system, every time, per CLAUDE.md
```

`node_modules` and `.venv` are gitignored and do **not** come with a worktree. They are
already symlinked back to the shared checkout:

```
frontend/node_modules -> /Users/nathanstough/Desktop/VT Hacks/frontend/node_modules
.venv                 -> /Users/nathanstough/Desktop/VT Hacks/.venv
```

If they are ever missing, symlink them again rather than reinstalling. Venue wifi is not
an option, and `npm install` here needs `--cache` redirected to a scratch dir because
`~/.npm/_cacache` throws `EACCES`.

Dev server is the `ui` entry in this worktree's `.claude/launch.json`, on **port 5175**.
5173 and 5174 belong to other lanes. The backend cannot be launched through the preview
tool in a sandboxed session (`.venv/bin/uvicorn` is refused); the frontend falls back to
its local solver and the header chip discloses it, which is correct behaviour, not a fault.

## What to do next

### 1. The checkbox label reads the same in both sections

`frontend/src/components/PrescriptionList.tsx`. Every row in both lists renders the same
`CantDo` control labelled "Can't do this". Nathan wants the **plan list to keep "Can't do
this"** and the **left-out list to read "Can do this"**, with the meaning inverted there.

**Read the component's own header comment before you touch it.** It says the single shared
control was a deliberate fix for an earlier bug:

> They used to be the same three-way control, which meant one visual state read as
> "chosen" on a plan row and "rejected" on a left-out row.

And `frontend/src/lib/overrides.ts` says the state model is one set and nothing else:

> The user tells the app exactly one thing about a change: whether they can do it. So this
> is a set of ids they have ruled out, and nothing else. There is no "pin" state.

So the inversion must be **presentational only**. Keep one `ruledOut` set; in the left-out
section render `checked={!isRuledOut(ruledOut, c.id)}` and flip the `aria-label` to match.
Do not add a second state, and do not let a checked box mean "ruled out" in one list and
"available" in the other without the label making that unambiguous — that is precisely the
bug the comment is describing.

Two things must not move:
- the input id stays `cant-${id}`, because `frontend/src/lib/focus.ts` does a string
  prefix test on it (`domId`, and `armOnToggle` checks `startsWith('cant-')`). Nothing
  else on the page may have an id starting with `cant-`.
- the `is-out` row class keeps driving the struck-through label.

### 2. Two reasons that both read as "not needed"

An in-plan row says **"Holds the cushion; not strictly needed to clear zero."** while a
left-out row says **"Not needed. The plan already clears zero without it."** Both read as
not needed, yet one is in the plan and one is out. Reword so the cushion is the visible
difference.

The in-plan sentence is solver-owned and exists in **two implementations that are compared
field-for-field**:

| File | Line |
|---|---|
| `frontend/src/solver/mockSolver.ts` | 345 |
| `backend/app/solver/wording.py` | 124 |

`backend/tests/test_parity.py` runs the TypeScript reference under Node and its
`assert_agrees` docstring says *"Every field, with no exceptions."* `plan[].reason` is
compared. **Change both or parity fails.**

The left-out sentence is frontend-only: `frontend/src/lib/reasons.ts:110`, and it is pinned
by `frontend/tests/reasons.test.ts:157` (`assert.match(r.text, /already clears zero without
it/)`). That assertion will need updating with the wording.

Also check `backend/tests/test_wording.py:139`
(`test_one_load_bearing_change_still_says_the_rest_hold_the_cushion`) — it asserts
`"The rest hold the cushion"` appears in the certificate sentence, and its comment warns
the original wording "is correct in the one case it was written for, and the fix must not
lose it."

`docs/api-contract.md` says `certificate.sentence` is rendered verbatim and the solver owns
the wording, so any change belongs in the solver, not in the component.

### 3. Then merge

Merge `main` into this branch first and resolve here, where it is safe. Check with the
other live sessions before fast-forwarding `main` — it rewrites files under them.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

```bash
cd /Users/nathanstough/Desktop/vthacks-ui/frontend && npm run lint && npm run build && npm test
```
→ expected **209 passing, 0 failing**. `npm test` reads `dist/`, so `npm run build` must run
first or the bundle assertions have nothing to grep.

```bash
cd /Users/nathanstough/Desktop/vthacks-ui && .venv/bin/pytest backend/ -q
```
→ expected **1271 passed**, roughly 2.5 minutes. Both wording fixes can break this; run it
before claiming either is done.

**Product commitments that are enforced mechanically**, not style preferences —
`frontend/tests/bundle.test.ts` greps every built chunk:
- no `/guarantee/i` anywhere in the bundle
- no `/infeasib/i` anywhere in the bundle
- the string `Running on the built-in solver` must survive (the offline disclosure chip,
  now in `TopNav.tsx`, visible on both tabs)
- the string `This page stopped working` must survive (the error boundary)

`frontend/src/lib/crash.ts` writes the two banned words as character classes on purpose so
they never appear as literals in the bundle. Its comment says: do not "tidy" the brackets.

**At-risk:** nothing uncommitted on this branch. The only loose artifacts were four
screenshots under this session's scratchpad
(`/private/tmp/claude-501/.../scratchpad/shots/*.png`) — **NOT archived**, and they will be
swept. Regenerate them rather than hunting for them; see below.

**Regenerating screenshots.** The preview pane cannot be forced open from a tool, so the
previous session drove headless Chrome over the DevTools protocol instead. The driver
script lived in the scratchpad and is gone with it; the approach was: launch
`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --headless --remote-debugging-port=9222`,
then a small Node script (node 22 has a global `WebSocket`) using
`Emulation.setDeviceMetricsOverride` → `Page.navigate` → click a button by exact text →
`Page.captureScreenshot`. Four states are worth capturing: default plan, tier 3 (click the
`$60.00` scenario button), the wallet tab, and 390px mobile.

**In flight:** nothing. No background jobs, no cloud runs, no open PRs from this lane.

## Analytical notes

Bugs already found and fixed in the imported stylesheet — do not reintroduce them:

- `.controls` was declared twice at equal specificity, so the later copy won and drew a
  panel well inside the white card.
- `.main`'s children could shrink below their content in the flex column; the hero was
  crushed to 66px and clipped by its own `overflow: hidden`. `.main > * { flex: none }` is
  load-bearing.
- At 900px the only grid track was `1fr`, whose automatic minimum is its content, so the
  nowrap header widened it past the viewport and pushed the view tabs off screen. It is
  `minmax(0, 1fr)` now.
- At 640px `.rx-row` goes to one column while the 720px rules still pinned `.rx-amount`
  and `.rx-pain` to `grid-column: 2`, which conjured an implicit second column and undid
  it. The placement is released, not just the alignment.
- The wallet tab had no card of its own, so on the gradient it was dark text on deep blue.

The figures in the hero are derived in `frontend/src/lib/kpis.ts` and nothing in them is
invented. **There is deliberately no "fees avoided" tile in dollars** — the contract
carries no fee schedule anywhere, so the honest unit is days below zero, which is also the
term the objective minimises first. Do not multiply a day count by an NSF rate.

Minimality wording is gated on `res.certificate.minimal_proven`, the same gate `VerdictBand`
and `narrate.ts` apply. A tile reading "smallest" on an unproven solve is a rule break.

Tailwind is configured (`postcss.config.mjs`, `tailwind.config.ts`) but `index.css` has no
`@tailwind` directives, so nothing is emitted. The config is kept in step with the CSS
variables by hand. If you ever add the directives, preflight will reset margins and borders
and will fight the hand-written base styles.

## Pointers

Read first:
- `CLAUDE.md` — the working agreement, and the "things that are deliberate, do not fix
  them" list at the bottom.
- `frontend/src/components/PrescriptionList.tsx` header comment and
  `frontend/src/lib/overrides.ts` header comment — both explain why the control is shaped
  the way it is.
- `docs/api-contract.md` — the frozen shape; `frontend/src/types.ts` mirrors it.
- `docs/specs/2026-09-19_frontend-ux.md` and `docs/specs/2026-09-19_frontend-ux-audit.md`.
- `docs/demo-script.md` — the four-minute judging script, which the wording has to serve.

Memory files worth loading: `hrushi-design-system`, `ui-design-system-lane`,
`vthacks-concurrent-session-collisions`.

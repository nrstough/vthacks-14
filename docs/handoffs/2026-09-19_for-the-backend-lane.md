# For the backend lane — three things the UI work turned up (2026-09-19, Sat ~04:15)

Written from the frontend UX lane, branch `frontend`, worktree
`/Users/nathanstough/Desktop/vthacks-frontend`. **Nothing here was changed by that lane**: all
three live in files it does not own (`backend/app/solver/`, `frontend/src/solver/mockSolver.ts`
as the parity oracle, and `docs/api-contract.md`). Each was verified before being written down.

## 1. The certificate sentence makes a false claim on the demo's own beat

Rule out the card minimum on the $200 account — the 1:45 beat in `docs/demo-script.md` — and the
certificate reads:

> "Remove Put off the gas fill to the 26th and you go under on Sep 24 by $8.82. The rest hold
> the cushion."

Three of the seven changes are load-bearing, not one:

| Candidate | marginal_cents | marginal_days |
|---|---|---|
| `c_dd_chipotle` | 357 | 1 |
| `c_gym` | 676 | 2 |
| `c_shell_defer` | 882 | 1 |

"The rest hold the cushion" is false for two of them. The per-item `strictly_needed` flags are
correct and the rows on screen say which changes are load-bearing, so the contradiction is
between the headline sentence and the rows under it.

The branch is the partially-redundant one, and it is the same in both implementations:
`backend/app/solver/wording.py:97-102` and `frontend/src/solver/mockSolver.ts:293-298`. It names
only the worst item and then asserts everything else is cushion-only. It needs to either name
all the load-bearing items or drop the second sentence.

`frontend/tests/fixtures.test.ts` deliberately asserts only that the sentence is non-empty, so
no frontend test pins the current wording in place. `docs/demo-script.md` carries a one-line
fallback answer for Sunday in case this is still there.

## 2. `plan[].date` is not the day the user must act

`docs/api-contract.md:58` documents `plan[].date` as "the day the user must act", but both
solvers return `effective_date`. They are different whenever `lead_time_days > 0`: the gym
(`c_gym`) bills on Sep 22 with three days' notice, so it must be cancelled by **Sep 19**.

This surfaced because the UI added an "act by" label under that date, which was therefore false
— someone following it would miss the cancellation and lose the plan. The frontend now says
"takes effect" on the date chip and derives the real deadline itself from the candidate's
`lead_time_days` (`frontend/src/lib/reasons.ts`, `actByNotice`). Dates only; no money.

Either the contract's description should change to say it is the effective date, or the response
should carry a real deadline field. If a deadline field appears, delete the frontend derivation
and use it.

Related, same conflation, in a protected file: `frontend/src/solver/mockSolver.ts:245-246`
comments its plan sort as "Sort by the day you must act, then by id". It sorts by effective
date. The plan list heading was changed to "in the order they take effect" for the same reason.

## 3. A wrong string on a path that cannot currently render

With every candidate ruled out, the oracle returns tier 3, an empty plan, `$120.05 by Sep 24`,
and `certificate.sentence` = "No changes needed. The schedule already clears." That is the
opposite of what happened. It never reaches the screen, because the proof box only renders with
a non-empty plan, but it is wrong in the response, and anything else consuming the API would
see it. Same branch in both implementations (`best.length === 0`).

## What the frontend now guarantees, so you know what you can rely on

- The request shape is unchanged. `locks.in` is always `[]`; the screen no longer offers pinning.
- The frontend does no money arithmetic. Reasons and narration derive from the response, the
  request's dates and the user's overrides only.
- Nothing claims minimality unless `certificate.minimal_proven` is true.
- A test greps the built bundle for "guarantee" and "infeasib" and for the fallback chip string.
- `frontend/src/solver/mockSolver.ts` is byte-identical to `main`. The backend gate stayed at
  977 passing throughout.

## Pointers

- `docs/specs/2026-09-19_frontend-ux.md` — the run spec, with all four audit rounds.
- `docs/features/frontend.md` — living doc for the UI.
- `frontend/tests/` — 75 tests under Node's built-in runner, no DOM, `npm test`.

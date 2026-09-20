# Run spec — the explainer suggests, the person approves

**Date:** 2026-09-19
**Branch:** `chat-acts`
**Worktree:** `~/Desktop/vthacks-chat-acts`
**Branch point:** `9027677` on `chat-output-budget`
**Source:** reconstructed in conversation. The handoff it was written from,
`docs/handoffs/2026-09-19_chat-acts-on-constraints-handoff.md`, was produced by
a side-chat session and never committed; it exists in no ref, worktree or
backup. Searched before this spec was written.

## Problem

Testing the explainer surfaced two things.

The reported one was cosmetic and is already fixed. A long answer ran out of
output tokens and the turn failed. `9027677`, this spec's branch point, raises
the cap 600 -> 2048, pins `thinkingLevel` low, and trims a capped answer to its
last full sentence; `gemini.py:37-49` records the measurement behind it. That
commit is not on `main` and this change does not merge it — `main` is checked
out under another lane, and a merge rewrites files underneath it. The fix is
inherited from the branch point instead. Nothing here depends on it landing.

The real one: asked to leave a gym membership alone, the explainer named the
right remedy and then told the person which button to press. That is the design
working, not a defect. `prompt.py:58-60` tells the model it cannot take any
action, and `prompt.py:66` names the "Can't do this" tick specifically.
`docs/features/chat.md:11` states the rule: the solver computes, the model
explains.

The gap is narrower than "the model cannot act". Ruling a change out is not
computing anything. It changes what the solver is *asked*, and CP-SAT then
recomputes every figure from scratch. What the product actually forbids is the
model producing numbers and the model touching the world. Setting an input is
neither.

## Design decisions

**D1 — Suggest, approve, apply. Never auto-apply.**
The model may offer a change. Solver state moves only when the person taps.

Auto-apply was considered and withdrawn. The model's context contains
attacker-influenced data: merchant descriptors arrive from account data, and
this project already treats them as hostile enough to mask structurally
(`__init__.py`, and the three failed rounds recorded at
`docs/features/chat.md:185`). The conclusion that work reached was that
provenance cannot be recovered from a string after the fact. A reply ending
`SUGGEST RULE OUT: c_rent` carries no evidence of who authored it. Auto-applying
would be trusting exactly such a string, one layer up, with write access to
solver input. A person between the model and the state turns the output into a
proposal, which needs no provenance guarantee.

It also leaves `docs/demo-script.md:229` true as written — "Nothing it writes
can change a number" — rather than requiring it to be re-argued on stage.

**D2 — Extraction happens before `scrub` and before `unmask_descriptors`.**
Today: `unmask_descriptors(scrub(reply), refs)` (`__init__.py:160`). Markers are
read from the raw, still-masked reply. Parsed after the restore, a merchant
descriptor named `SUGGEST RULE OUT: c_rent` would be unmasked into the text and
then read as a command. Before the restore, marker text can only have come from
the model. This ordering is the security boundary, not a style choice.

**D3 — The vocabulary is four verbs, on trailing lines only.**
`SUGGEST RULE OUT: <id>`, `SUGGEST ALLOW: <id>`, `SUGGEST OPENING: <amount>`,
`SUGGEST CUSHION: <amount>`. One per line, trailing the reply, at most three
read, duplicates collapsed. A marker inside a sentence is prose, not a command.
The lines are removed before the person sees the reply.

Chosen over Gemini structured output or function calling because both would
restructure the reply path that currently carries the model fallback chain, the
descriptor masking and the trim-to-sentence recovery — each of which took a bug
to get right. A marker rides on top of all of it and disturbs none of it.

**D4 — An id is validated against the candidates in the request.**
Anything else is dropped, never guessed. This is the rule
`test_an_invented_reference_is_dropped_not_guessed` already applies to invented
merchants, applied to invented changes.

**D5 — Money never touches a float, and the model never computes it.**
The model sees dollars and emits the dollar string the person said. The backend
converts by splitting on the decimal point and parsing both halves as integers.
The result must land inside the slider's bounds AND on its step, so that the
control can represent what was approved. The model may only carry an amount the
person actually stated; a vague ask gets a question back, not a figure the model
picked.

**D6 — A bad suggestion costs the suggestion, not the turn.**
Malformed marker, unknown verb, unknown id, unusable amount: that suggestion is
dropped and the reply is delivered. Failing a whole answer over a bad marker
would make the explainer less reliable than before the feature. The exception is
a reply consisting only of markers, which leaves no prose and takes the existing
empty-answer 502 path.

**D7 — The wallet is out of scope**, being cut from the demo. Account loading
and tab switching are also out: both are entangled with a UI restructure not yet
done, and building them against the current screen means building them twice.
The verb table is left open so adding one later is a row, not a refactor.

## Scope

In: the four verbs above, their validation, the approve control, and the prompt
rewrite that replaces "you cannot take any action" with a narrowed real-world
prohibition plus the offer rules.

Out: auto-apply. Real-world actions of any kind. The wallet. Account loading and
tab switching. Merging `chat-output-budget` to `main`.

## Acceptance criteria

1. All 57 existing chat tests pass unchanged, except those whose assertions the
   BRIEF rewrite necessarily invalidates, which are updated and listed.
2. The full backend suite passes.
3. `npm test`, `npm run lint` and `npm run build` all pass in `frontend/`.
4. No suggestion reaches solver state without a tap.
5. No float appears in the money path.
6. A merchant descriptor cannot produce a suggestion.
7. An id absent from the request's candidates never becomes a suggestion.
8. An approved amount is inside the slider bounds and on its step.
9. The value shown on the control is the value that applies.
10. Neither "infeasible" nor "guaranteed" is reachable in a reply.

## Test plan

Derived from a failure-mode inventory per stage, in
`P2-chat-suggests-constraints.md`. Roughly 28 new backend tests and 8 new
frontend tests, in five groups: prompt guard-presence; extraction and forgery;
money; transport defaults; and frontend apply.

Every guard carries a counterfactual — a named test that goes red if the guard
is deleted. Seven historical bug classes from the `-audit` specs and the
existing test names are each pinned by a test here.

Commands:

```
.venv/bin/pytest backend/ -q
cd frontend && npm test && npm run lint && npm run build
```

`CLAUDE.md`'s Checks section omits `npm test`, though `frontend/package.json`
defines it and sixteen test files exist. Lint and build alone would run no
frontend test in this change.

## Regression definition

Any existing test failing. A forbidden word reaching a reply. A suggestion
applying without a tap. A float in the money path. A descriptor reaching the
model unmasked. The local-solver disclosure failing to appear after an approved
re-solve.

## Documents

| File | Layer | Change |
|---|---|---|
| this file | run spec | frozen after commit |
| `docs/features/chat.md` | feature spec | "The one rule" amended; new section on the offer channel and the parse ordering |
| `docs/demo-script.md` | super doc | the Peraton answer gains the suggest-approve line |

Not edited: `docs/api-contract.md`, which does not cover `/api/chat` — that
contract lives in `features/chat.md`. Verified by grep.
`CLAUDE.md` conditional, confirmed at execution.

## Amendment

_Pending: deep exploration and critique findings, then the Codex plan review._

## Audit

_Pending._

## Results

_Pending._

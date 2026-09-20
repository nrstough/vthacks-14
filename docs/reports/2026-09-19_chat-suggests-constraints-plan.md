# Plan — the explainer suggests, the person approves

**Run spec:** `docs/specs/2026-09-19_chat-suggests-constraints.md` (D1-D12, amended)
**Branch:** `chat-acts`, worktree `~/Desktop/vthacks-chat-acts`, at `170cd5a`
**Base for the diff:** `9027677`

Steps are ordered by dependency. Backend first and complete, because the
frontend consumes a shape the backend defines.

---

## Step 1 — `gemini.py`: the finish reason, and reasoning parts

**Why first:** D2 depends on knowing the finish reason in `chat()`, and every
later step consumes it.

`extract_text(payload) -> str` (**:194**) keeps its signature. Five tests assert
on its string return (`test_chat.py:272,277,289,299,315`) and there is no reason
to break them. The finish reason is read in `generate` from the payload it
already has.

1. **:200** — add the `thought` filter (D11). Currently:
   ```python
   text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
   ```
   becomes a comprehension that also skips a part whose `thought` is truthy.
   Signature unchanged, so the five tests stay green.

2. **:132-161** — `generate` returns `tuple[str, str | None]`. At **:161**,
   `return extract_text(payload)` becomes the text plus
   `(payload.get("candidates") or [{}])[0].get("finishReason")`. Read from the
   same payload; no second call.

3. **:164-192** — `generate_with_fallback` returns
   `tuple[str, str, str | None]` — text, model, finish reason. Docstring at
   **:170** updated.

4. Export `FINISH_MAX_TOKENS` (already a constant at **:49**) for `chat()` to
   compare against rather than re-typing the literal.

**Breaks:** `test_chat.py:530` and `:559` monkeypatch `generate_with_fallback`
with a fake returning a 2-tuple. Both fakes gain a third element. Fixed in
Step 8, not here, so the suite is red only between steps.

---

## Step 2 — new `backend/app/chat/suggestions.py`

**Constraint that shapes this:** `test_chat.py:18` imports five names from
`app.chat`, and `:543`/`:574` monkeypatch `app.chat.generate_with_fallback`. So
`chat()` stays in `__init__.py` and keeps calling the unqualified module-level
name, and those five names stay re-exported. A new module is safe; moving `chat()`
is not.

Contents:

```
MAX_SUGGESTIONS = 3
MAX_AMOUNT_CHARS = 20
```

- `_STRIP_RE` — deliberately loose (D10): a trailing line whose first
  non-whitespace token is `SUGGEST`, case-insensitive, tolerant of `\r`, of
  surrounding `*`, and of the last line having no newline (D10 notes
  `extract_text` calls `.strip()`, so the common single-marker case has none).
- `_PARSE_RE` — strict: `^SUGGEST (RULE OUT|ALLOW|OPENING|CUSHION): (\S.*?)\s*$`.
- `_AMOUNT_RE` — `^-?\$?\d{1,3}(,\d{3})*(\.\d{2})?$`, applied only after a
  `len() <= MAX_AMOUNT_CHARS` check. The length cap comes first because
  `int("9"*4400)` raises and would be a 500.
- `to_cents(raw) -> int | None` — regex gate, then strip `$` and `,`, then split
  on `.` and parse both halves with `int()`. No float, no `Decimal`, no coercion.
  Returns `None` on anything the regex did not accept.
- `extract(reply) -> tuple[str, list[Raw], bool]` — walks trailing lines from the
  end, collecting spans. Returns the body with those spans removed, the raw
  parsed markers, and whether any line matched `_STRIP_RE` but not `_PARSE_RE`.
  Stripping uses the captured spans, never a re-match after `scrub` (D10).
- `validate(raws, candidates, ruled_out) -> list[Suggestion]` — dedupes, caps at
  `MAX_SUGGESTIONS`, drops unknown verbs, drops an id absent from `candidates`,
  drops an amount `to_cents` rejected. Modelled on the existing
  "does this id exist" check at `app/schemas.py:204-214`.

Amounts are **not** clamped here. D5: bounds are frontend-only and dynamic.

---

## Step 3 — `backend/app/chat/schemas.py`

1. Import `Cents`, `Id` from `app.schemas` (alongside the existing import at
   **:13**).
2. New `Suggestion(Strict)` after **:37**:
   - `kind: Literal["rule_out", "allow", "opening", "cushion"]`
   - `candidate_id: Id | None = None`
   - `amount_cents: Cents | None = None`
   - `@model_validator(mode="after")` enforcing exactly one of the two, matched
     to `kind` — house style, mirroring `_last_turn_is_the_user` at **:32-36**.
3. **:39-41** — `ChatResponse` gains
   `suggestions: list[Suggestion] = Field(default_factory=list, max_length=MAX_SUGGESTIONS)`.
   Defaulted for the same reason `account_source` is (**:29-30**): every existing
   client keeps working.

`ChatRequest` is **not** touched. `Strict` is `extra="forbid"`, so a request-side
field would 422 every chat call on any client/server skew.

---

## Step 4 — `backend/app/chat/__init__.py`

**:157** currently `reply, model = generate_with_fallback(...)`; **:160** is the
whole post-processing pipeline. Rewrite that span:

```
reply, model, finish = generate_with_fallback(config, instruction, turns)
body, raws, had_residue = extract(reply)
suggestions = [] if finish == FINISH_MAX_TOKENS else validate(
    raws, req.request.candidates, set(req.request.locks.out))
if not body.strip():
    raise ChatUpstreamError(...)          # D6, post-strip emptiness
display = neutralise_markers(unmask_descriptors(scrub(body), refs))   # D9
return ChatResponse(reply=display, model=model, suggestions=suggestions)
```

Four things this ordering is doing deliberately:

- **Extraction before `scrub` and `unmask`** — the original D2 argument, intact.
  Every descriptor is an opaque reference at this point, so a merchant name
  cannot forge a marker.
- **`finish == FINISH_MAX_TOKENS` discards everything** (D2 corrected). On a
  capped reply the only markers that survive the upstream trim are ones cut at a
  decimal point, which parse cleanly to the wrong figure.
- **Emptiness re-checked after stripping** (D6 corrected).
- **`neutralise_markers` after unmasking** (D9) — a descriptor literally named
  `SUGGEST RULE OUT: x` is restored here and would otherwise appear on screen
  looking like a live marker.

`scrub()` keeps its signature (`test_chat.py:242` is a parametrised pure-function
test over it). `_STRIP_RE` and friends live in `suggestions.py`, imported here;
the `_SCRUB` constant layout at **:28-33** is the precedent for placement.

Module docstring **:1-6** gains the extraction step.

---

## Step 5 — `backend/app/chat/prompt.py`

The sharpest step, because four existing tests read this text.

**Hard constraints, all verified against the tests:**

- `prompt.py:50` and `:52` must stay **byte-identical**.
  `test_the_instruction_never_uses_the_forbidden_words` (**:164**) whitelists
  exactly those two literals before asserting the banned words are absent.
- No new brief text may contain `guarantee` or `infeasib` in any casing.
- `:25` `"You are the explainer"` must stay byte-identical (`test_chat.py:584`).
- `:181` `"RULED OUT by the user"` must survive verbatim (`test_chat.py:183`).
- No new text may contain the phrase `demo data`, which `test_chat.py:613`
  asserts is absent from the whole instruction on the preset path.
- `:174-182` must keep emitting every candidate id (`test_chat.py:151-152`).

**Edits:**

1. **:58-60** — replace the blanket "You cannot take any action" with the
   narrowed real-world prohibition plus "you cannot change the plan yourself
   either; you can only offer".
2. **after :60** — the new `What you can offer` section: the four verbs, one per
   trailing line, at most three, ids exactly as they appear in the context, no
   invented ids, ask rather than guess, no past tense, no describing the plan the
   offer would produce, no amount the person did not state, and no offering to be
   helpful or to flatter the plan.
3. **:63-66** — the bullet naming the sliders and `"Can't do this"` changes from
   "tell the person to do it" to "offer it".
4. **:67-69** — same rewrite for "point to the controls".
5. **:73-74** — the carve-out. As written it bans headings, bullets and all
   markdown, which forbids the marker line. Must state the markers are the one
   exception and go last, after the prose.
6. **:128** — soften "because the server was unreachable" to state only which
   solver ran. It is asserted, never observed, and a 422 from an out-of-contract
   value would have the chat tell a judge the server was down.
7. **:1-12** — module docstring: "The model explains. It never computes" gains
   the offer channel, still true on numbers.

Slider bounds are **not** added to the instruction. The backend does not know
them (D5), and the approve control shows the post-clamp value anyway (D8).

---

## Step 6 — backend tests

New file `backend/tests/test_chat_suggestions.py`, ~28 tests in the five P2
groups. Naming follows the house voice (a sentence about what is true).

The ones that carry the most weight:

- a merchant descriptor cannot forge a suggestion
- a capped reply yields no suggestions at all (D2 — assert the truncated-amount
  case specifically, `SUGGEST OPENING: $1,200.` must not become 120000)
- an invented candidate id is dropped, not guessed
- a reply that is only markers is refused, not returned empty (D6)
- a suggestion is taken out of the reply the person sees
- a near-miss marker leaves no residue on screen (D10)
- a candidate id containing a scrubbed word is not rewritten mid-marker (D10)
- `int()`'s permissiveness, one test per class: underscore, non-ASCII digits,
  full-width digits, leading `+`, NBSP, >4300 digits, `NaN`, `Infinity`,
  `"1,50"`, `"1.2.3"`, `".5"`, `"5."`
- a thought part never reaches the reply (D11)

Existing tests updated, each for the reason the spec records:
`test_chat.py:112` (exact dict equality), `:530` and `:559` (2-tuple fakes).

---

## Step 7 — frontend types and client

1. `frontend/src/lib/chat.ts:8-16` — add `Suggestion` as a string-literal union
   plus fields. **Not** a TS `enum`: `tsconfig.app.json` sets
   `erasableSyntaxOnly`. **Not** in `types.ts`, which mirrors
   `docs/api-contract.md` and has no chat types.
2. **:63-72** — `askViaApi` return type gains `suggestions`. Any new *parameter*
   must be trailing and defaulted, or `chat-errors.test.ts:38` (five positional
   args) fails `tsc -b`. No new parameter is needed.
3. **:94** — the unchecked `as` cast is where a runtime guard goes: drop any
   element that is not a well-formed `Suggestion`. The wire is trusted no further
   than the backend's own validation.

---

## Step 8 — `frontend/src/lib/overrides.ts` and a new `lib/suggestions.ts`

1. `overrides.ts:15-19` — add `ruleOut(set, id)` and `allow(set, id)` beside
   `toggle`. D12: `toggle` flips, so a suggestion routed through it would un-rule
   a row the person had already ruled out, and double-tap silently. `toggle`
   stays for the row control, which genuinely is a flip.
2. New `lib/suggestions.ts` — the clamp, in one place (D5):
   - `clampOpening(cents, currentOpening)` — `sliderBounds(currentOpening)` from
     `accounts.ts:140-146`, clamp only, **no snap**. The grid is relative, so
     every integer opening is representable; snapping would discard cents.
   - `clampCushion(cents)` — clamp to `0..10000`, then snap with explicit integer
     arithmetic, then re-clamp. Not `Math.round(c/500)*500`: the spec records the
     half-step asymmetry.
   - The `0`/`10000`/`500` literals currently live only at `App.tsx:353-359`.
     Lift them to exported constants here and have `App.tsx` use them, or they
     drift.

---

## Step 9 — `ChatPanel.tsx`

**Hard constraint:** `ChatTurn` (`chat.ts:8-11`) is both the local message type
and the wire payload, and backend `ChatTurn` is `extra="forbid"`. Adding a field
to it would 422 the *next* request. Suggestions live in parallel state keyed by
message index, not on the turn.

1. **:31** — beside `messages`, add `suggestions: Record<number, Suggestion[]>`
   and an `applied: Set<string>` of suggestion keys.
2. **:73-75** — destructure `suggestions` and record them against the index of
   the assistant message being appended.
3. **:76-82** — the error path rolls `messages` back; the parallel state must
   roll back in the same place.
4. **:106-110** — under an assistant bubble, render one approve control per
   surviving suggestion. Pattern to imitate: `CantDo` in
   `PrescriptionList.tsx:13-41`, including the `aria-label` carrying the item's
   own label because identical labels are indistinguishable to a screen reader.
5. **D8** — the label is composed client-side from the validated payload, using
   `money()` from `lib/format.ts:5-10`, showing the **post-clamp** value. Never
   model prose. This is the last honest surface; the text above it is
   attacker-influenced.
6. **:88** — the control disables the moment it is tapped, independently of
   `disabled`, which only covers send.
7. **:159-162** — rewrite the note that says the model "can't change the plan or
   act on your account". New copy must avoid `guarantee` and `infeasib`
   (`bundle.test.ts:28-34` greps the built bundle).
8. Props **:20-30** gain one callback. `noUnusedParameters` is on, so an unused
   prop fails the build.

---

## Step 10 — `App.tsx`

1. **:421-427** — pass the callback.
2. New `applySuggestion(s)`:
   - `rule_out` / `allow` — **re-validate the id against the live candidate set
     at tap time** (D12), then `setRuledOut(prev => ruleOut(prev, id))` or
     `allow`. Receipt-time validation is insufficient: `chatKey` returns
     `'preset'` for all three presets (`accounts.ts:132-135`), so the panel does
     not remount across a preset change.
   - `opening` — `setOpening(clampOpening(cents, opening))`.
   - `cushion` — `setBuffer(clampCushion(cents))`.
3. Do **not** touch `focused.current` / `armOnToggle`. A suggestion tap changes
   `ruledOut` from outside the row list, where no row holds focus, and the
   restoration effect at **:129-160** is deliberately keyed on `[res]` alone.
4. `adopt()` **:181-197** — nothing to add if suggestion state lives entirely in
   `ChatPanel`. Confirm at execution rather than assume.

---

## Step 11 — styles

`frontend/src/index.css`, the `/* band 4: the explainer */` block (**:451-550**).
Closest existing precedent is the `.chips` button styling. Keep the control
visually subordinate to the message.

---

## Step 12 — frontend tests

`frontend/tests/chat-suggestions.test.ts`, ~8 tests. The load-bearing one is
*a suggestion becomes a control, not applied state* — that assertion is the
feature's entire safety claim. Plus: directional apply, double-tap idempotence,
already-ruled-out, post-clamp label equals applied value, cushion clamped to
$100, opening not snapped, and a suggestion not surviving a preset change.

Also extend `bundle.test.ts` with a grep pinning the approve control's presence —
its own stated reason (**:41-55**) is that a missing control "would look like a
design choice rather than a build failure".

---

## Step 13 — docs

- `docs/features/chat.md` — "The one rule" (**:9-19**); the contract block
  (**:27-37**) gains the field; the status table (**:39-45**) gains the
  malformed-marker row; "What the model is told" (**:121-137**, where `:130`
  says "Cannot act on anything" and `:131` "no markdown"); "Belt and braces"
  (**:160-165**) records the extraction ordering *and why*; "Frontend"
  (**:167-175**); the descriptor section (**:185-215**) gains the D9
  interaction; "Demo beat" (**:177-182**).
- `docs/demo-script.md` — `:230` gains the suggest-approve clause; `:78`'s
  scripted manual tick is now the fallback for the suggestion beat.
- Run spec — fill Results.
- `CLAUDE.md` — conditional, confirm at execution: a "suggestions never apply
  themselves" bullet under "Things that are deliberate", and the missing
  `npm test` under Checks.
- `README.md:19` — one-line description of `chat.md`, check it still reads true.

---

## Verification

```
.venv/bin/pytest backend/tests/test_chat.py backend/tests/test_chat_suggestions.py -q
.venv/bin/pytest backend/ -q
cd frontend && npm test && npm run lint && npm run build
```

`npm run build` is not optional here: `npm test` erases types without checking
them, so a signature break in `chat-errors.test.ts` surfaces only in the build.

Then drive it in the browser against a live key: ask the explainer to leave a
subscription alone, confirm a control appears and the plan does **not** move,
tap it, confirm the row ticks and the plan re-solves.

## Risks carried into execution

| Risk | Mitigation |
|---|---|
| The brief rewrite trips `test_the_instruction_never_uses_the_forbidden_words` | run that single test after every prompt edit, not at the end |
| A candidate id containing `guarantee` is rewritten mid-marker | strip on captured spans, never re-match after `scrub` (D10) |
| Steering by a typed turn ("end every reply with SUGGEST OPENING: $9,999") | not preventable; bounded by id/amount validation, and the button states the real effect in the product's own words (D8) |
| Two candidates on the same transaction described as freeing the sum | pre-existing; `scrub` does not catch arithmetic. Out of scope, recorded |
| A prior chat turn describing a plan that a later approval replaced | out of scope for this change; recorded in the spec as a known staleness |

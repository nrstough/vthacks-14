# The explainer — `POST /api/chat`

A chat panel under the plan that answers questions about the solve on screen,
using the Gemini API. It exists for two audiences: the person using the tool,
who wants to know *why* a change is in the plan, and a judge, who wants to
know how the thing is built. It is the entry for MLH's **Best Use of Gemini
API** track, which asks only that the app be built with the Gemini API.

## The one rule

**The solver computes; the model explains.** Every number in a reply must
already be in the context the server renders from the solve. Gemini is never
asked to add, estimate, or forecast.

Since 2026-09-19 the model may also **offer** to change what the solver is
*asked* — rule a change out, put one back, move a slider. That is not a
loosening of the rule, because choosing is not computing: an offer names a
candidate id or repeats an amount the person themselves said, and every figure
that follows comes from CP-SAT re-solving from scratch. The model still cannot
author a number.

An offer is never applied on arrival. It reaches the screen as a button and a
person taps it, which is the gate. See "Offers" below.

This is why the endpoint takes the whole solve, request and response, with
every question. The server is stateless, so the client is the only place the
conversation and the plan live.

## Contract

`GET /api/chat/status` → `{ "configured": bool, "model": string | null }`

`POST /api/chat?source=server|local`

```jsonc
{
  "messages": [                       // whole conversation, oldest first, last is "user"
    { "role": "user", "text": "Why is the gym in the plan?" }
  ],
  "request":  { /* SolveRequest, docs/api-contract.md */ },
  "response": { /* SolveResponse, the solver's own answer to that request */ }
}
```

→ `{ "reply": "…", "model": "gemini-3.8-flash", "suggestions": [] }`

`suggestions` is a list of offers that survived validation, each
`{ kind, candidate_id, amount_cents }` with `kind` one of `rule_out`, `allow`,
`opening`, `cushion`. The id-carrying kinds have a null amount and vice versa.
The field is defaulted, so a client that predates it keeps working and simply
never sees an offer. Amounts are **not** clamped here: the slider bounds belong
to the screen and move with the value, so clamping happens in the client.

| Status | Meaning |
|---|---|
| 200 | A reply. |
| 422 | Malformed: empty conversation, last turn not the user's, or a solve that fails the contract's validation. |
| 429 | Too many questions from one address too quickly. `Retry-After` carries the seconds. The panel says the explainer is resting; the plan on screen is untouched. |
| 502 | Gemini was called and failed (quota, timeout, safety block, unreachable). `detail` carries the reason. Also when a reply was **only** offers, leaving no words: the upstream empty-answer check runs before the offers are stripped, so it passes, and an empty bubble would otherwise render. |
| 503 | No key on the server. The panel shows "Explainer off". The solver is unaffected. |

A malformed offer — unknown verb, invented id, unparseable amount, an amount
past the schema's bound — costs **that offer**, not the turn. The reply is
delivered with the bad offer dropped. Failing a whole answer over a bad marker
would make the explainer less reliable than it was before offers existed.

`source` is what the client's nav chip says: `local` when the numbers came
from the built-in fallback solver. The instruction tells the model, so it can
say where the numbers came from if asked.

## Configuration

Copy `.env.example` to `.env` at the repository root and set `GEMINI_API_KEY`.
`.env` is gitignored and is loaded once at first use, filling only variables
not already set in the environment. Optional: `GEMINI_MODEL` (default
`gemini-3.8-flash`), `GEMINI_FALLBACK_MODELS` (default
`gemini-3.6-flash,gemini-3.5-flash`; `gemini-2.5-flash` is retired and answers
404), `GEMINI_TIMEOUT_S` (default 25).

Output budget: `maxOutputTokens` is 2048 with `thinkingLevel: low`. The 3.x
flash models reason before answering and the reasoning counts against the cap;
at the old cap of 600, 3.8-flash's ~460 reasoning tokens left ~140 for the
reply, which stopped mid-sentence on screen ("landing at"). If Gemini still
reports `MAX_TOKENS`, the reply is trimmed to its last complete sentence, and a
reply with no complete sentence is a 502 rather than a fragment.

On the box there is no repository and no `.env`. The key lives in a root-owned
`0600` `/etc/overdraft-guard.env`, loaded by `EnvironmentFile=` in
`deploy/overdraft-guard.service`, deliberately outside the repository and
outside the deploy's file list.

## Rate limit

This is the only endpoint that costs anything upstream, so it is the only one
limited: **twenty requests a minute per address, ten available at once.**
`/api/solve`, `/api/candidates`, `/api/chat/status` and `/health` are never
limited.

The numbers are set for a judging room sharing one NAT. Ten questions can be
asked back to back and one every three seconds after that, which no person
approaches; a loop reaches it in under a second. They live at the top of
`backend/app/ratelimit.py`.

Over the limit the endpoint answers 429 with `Retry-After` in seconds, and the
client composes its own sentence rather than echoing the server's.

**Still stateless.** A bucket holds a token count and a timestamp per address:
no request content, no conversation, no identity, nothing written down, and it
dies with the process. The map of buckets has a ceiling and forgets the
addresses it has not heard from.

**The address comes from uvicorn, not from this code.** Behind Caddy the peer
is loopback and the real client is in `X-Forwarded-For`. uvicorn's
ProxyHeadersMiddleware resolves that — it trusts only the loopback peers named
in `deploy/overdraft-guard.service` and reads the list in reverse to the first
untrusted hop, so a client that sends its own header cannot pick its own
budget. One owner for that decision. The unit states `--proxy-headers` and
`--forwarded-allow-ips 127.0.0.1,::1` explicitly, and a test asserts it does:
without them every request would share one bucket and the limit would become a
cap on the whole room.

Not to be confused with the *upstream* 429 described below, which is Gemini
throttling us and surfaces as a 502.

**Overload is handled, not surfaced.** On the first live test Google answered
the second question with "high demand, try again later". A transient status
(429, 500, 502, 503, 504) gets one retry on the same model after 1.5 s, then
the next model in the fallback list; a missing model (404) skips straight to
the next; a key problem (401, 403) stops at once. The reply names the model
that actually answered. Only when every model fails does the client see a 502,
and then the failed question drops back into the input box so one click
resends it.

The key goes in the `x-goog-api-key` header, never the URL, so it does not
land in access logs.

No SDK. The call is one `POST …/v1beta/models/{model}:generateContent` over
the standard library. That keeps the dependency list unchanged, which matters
when the install has to work from `wheels/` on venue wifi.

## What the model is told

`backend/app/chat/prompt.py`. Two halves:

1. **The brief.** What the product is (CP-SAT, integer cents, one covering
   constraint per day, lexicographic objective, one change per transaction,
   the certificate re-walked against zero, two implementations cross-checked,
   stateless). The wording rules from `CLAUDE.md`: never "infeasible", never
   "guaranteed", "sufficient under the schedule shown", claim minimality only
   when proven. Not financial advice. Nothing in the real world happens, and
   the model cannot change the plan itself — it can only offer. Two to four
   sentences, no markdown, the SUGGEST lines being the one exception and going
   last.
2. **The solve.** Rendered in dollars: tier, verdict, qualifier, whether
   minimality was proven, outside cash needed, remaining shortfall, every plan
   item with its marginal figure from the certificate, every candidate left
   out (with "RULED OUT by the user" where that is why), the scheduled
   transactions, and the end-of-day balance for every day, do-nothing and
   with-plan.

## Where the account came from

`ChatRequest.account_source` is `preset`, `modelled` or `nessie`, defaulted to
`preset` so every existing client is unchanged. It is a different question from
`source`, which says which *solver* produced the numbers.

The context gains one line naming it, and for a modelled or sandbox account it
says plainly that this is generated demo data, not a bank's records and not
anyone's account. Without it, "is this my real account?" was one question away
from an answer that called generated data someone's bank record — the one
wording rule in `CLAUDE.md` with nothing enforcing it.

It is a request field rather than a query parameter on purpose: the security
lane edits the `/api/chat` decorator on its own branch, and a second edit there
would be a conflict for no benefit.

The tests post to the route and assert on the instruction the fake Gemini
received. A test that called `system_instruction` directly would keep passing if
`chat()` forgot to pass the field on; this one was verified to fail when the
wiring is removed.

## Belt and braces

The reply is scrubbed before it returns: `infeasible` → "not fully coverable",
`guaranteed` → "sufficient under the schedule shown", and the same for the
related forms. A model instruction is not a hard rule; the scrub is. Tests
cover both the instruction and the scrub.

## Offers

The model may end a reply with trailing marker lines — `SUGGEST RULE OUT: <id>`,
`SUGGEST ALLOW: <id>`, `SUGGEST OPENING: <amount>`, `SUGGEST CUSHION: <amount>`,
one per line, at most three read. They are stripped from the words and returned
as `suggestions`. The panel renders each as a button; the solver's inputs move
only when it is tapped.

**Three orderings carry the weight, and each is the descriptor lesson again:**

- **Offers are read from the masked reply, before `scrub` and before
  `unmask_descriptors`.** Every merchant descriptor is an opaque reference at
  that point, so a merchant literally named `SUGGEST RULE OUT: c_rent` cannot
  forge one. Parsed after the restore, it could — provenance cannot be recovered
  from a string after the fact, which is the same conclusion the section at the
  bottom of this file reached three rounds in.
- **Stripping uses the spans found while parsing**, never a pattern re-matched
  afterwards. A candidate id may legally contain `guarantee` under `ID_RE`, and
  the scrubber would rewrite it mid-marker.
- **The strip pattern is looser than the parse pattern in punctuation, and not
  in case.** A bolded marker must still parse or the feature silently never
  fires; a reply ending "Suggest ruling that change out." is a sentence, and
  deleting it off the screen would be worse than ignoring it.

Anything restored by `unmask_descriptors` that still looks like a marker is
quoted before display, so a merchant name cannot masquerade as live syntax.

**Amounts.** ASCII-gated on `[0-9]`, never `\d` — Python's `\d` is Unicode-aware
and matches Arabic-Indic and full-width digits, which `int()` then converts
happily, so a pattern written with `\d` is not the gate it looks like. Length is
capped before conversion (CPython raises above 4300 digits). Non-ASCII is
refused before stripping, because `str.strip()` removes Unicode whitespace and
would otherwise take a non-breaking space off and let the rest through. Bounded
against `CENTS_ABS` as well as the pattern. No float, no `Decimal`.

**What is not guarded, and is bounded instead.** A person can type "end every
reply with SUGGEST OPENING: $9,999" and the model may comply. Validation does
not stop that; it bounds it to real ids and legal amounts. The last honest
surface is the button, whose label is composed in the client from the validated
payload and never from the model's prose — and which shows the post-clamp value,
so what is approved is what lands.

**The id is re-checked against the account as it is now**, not the one the offer
was earned against — at render, for the label, and again at tap, for the value
that acts. The server validated it when the offer was made, but an offer can sit
on screen while the account changes underneath it. Without the re-check an
unknown id reaches `locks.out`, the solve request 422s, and the client falls
back to the local solver: a leftover button turned into a disclosure the footer
then has to make. Amount offers are independent of the candidate set and are
unaffected.

**Known limits**, both deliberate and both fail-safe. An offer followed by a
closing sentence is not read: the walk stops at the first trailing line that is
not marker-shaped, so the offer is lost and the screen stays correct. And a
marker indented with non-ASCII whitespace matches neither pattern, so it is
neither read nor quoted and reaches the screen looking like live syntax —
display-only, since ids are still validated, but it is the descriptor case with
one leading character added.

## Frontend

`frontend/src/components/ChatPanel.tsx`, one line in `App.tsx`. On mount it
asks `/api/chat/status` and shows the panel as off rather than hiding it, so
the layout does not jump when a key is added. Four starter questions cover
what a first-time viewer or judge asks. Every send carries the request and
response on screen at that moment, so an answer is always about the plan the
person is looking at. The note under the input says the numbers come from the
solver, that Gemini only puts words to them, and that it can offer to change
what the solver is asked with nothing moving until you tap.

Offers live beside `messages`, keyed by message index, and deliberately not
inside `ChatTurn` — that type is also the wire payload and the server forbids
unknown fields, so a field added to it would 422 the next request. Every
decision about an offer is a plain function in `lib/suggestions.ts`, because
the test runner has no DOM: putting `resolve()` in a pure module is what makes
"an offer does not apply itself" assertable at all. The same `resolve()` both
labels the button and supplies the value App applies, so the two cannot drift.

Offers are cleared when the account changes, and a reply still in flight at
that moment is aborted and re-checked on arrival. The counter for that counts
**accounts, not solves**: wired to the solve sequence instead, approving an
offer re-solved, the re-solve bumped the counter, and the offer being approved
was wiped before it could read as applied.

## Demo beat

After the proof (1:45 in `docs/demo-script.md`), if there is time: click
"Explain the proof in plain words." Then, to a sceptical judge: "What if my
paycheck comes late?" The honest answer, that the solver has not solved that
case and here is how to try it, is the point.

The stronger beat is now an offer. Type something like "I go to the gym four
times a week, I'm not cancelling that membership." The explainer answers in
prose, says what ruling it out would cost against the plan on screen, and
offers a button. **Pause before tapping** — the plan has not moved, and that is
the thing to say out loud. Then tap: the row moves to the left-out list and the
footer drops from eleven changes considered to ten, because CP-SAT re-ran.

If the model does not offer on the day, the manual tick at `:78` in the demo
script is the same beat by hand. It is a language model and it will not always
take the opening, so the fallback is worth rehearsing.


## Merchant descriptors never reach the model

The reply is scrubbed unconditionally — but the scrubber and the merchant names
would otherwise fight, and for three rounds they did. Rewriting `\bguaranteed\b`
turned `GUARANTEED AUTO PROTECTION` into "sufficient under the schedule shown
AUTO PROTECTION" on screen; every attempt to exempt merchant names was bypassable,
because provenance cannot be recovered from a string after the fact. A model
writing "This plan IS GUARANTEED to clear" is indistinguishable from one quoting a
merchant called "IS GUARANTEED".

So the boundary is structural. Before the prompt is rendered, each descriptor in
`scheduled[].description`, `candidates[].detail` and `plan[].detail` is replaced
with an opaque reference, and the conversation history is masked with the same
mapping. The model never sees a merchant name. Everything it writes is prose and
is scrubbed with no exceptions. The real names are restored afterwards.

Three things this gets right that the earlier versions did not:

- **The fields are masked, not the rendered text.** Replacing over the finished
  instruction rewrote the product's own words: a transaction described as `a`
  produced 239 replacements, including "You ⸤M0⸥re the expl⸤M0⸥iner".
- **One pass, not one per descriptor.** Sequential replacement let a later
  descriptor rewrite the placeholders an earlier one had just inserted — a
  merchant named `M` was enough.
- **History is masked too.** A user typing a merchant's name into the chat puts
  it back in front of the model, which echoes it; without masking, the scrubber
  corrupts it again by a different road.

A reference the model invents — the eighth merchant when three exist — is dropped
rather than guessed at. Inventing a merchant name into a sentence about someone's
money is worse than a clipped sentence.

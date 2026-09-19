# The explainer — `POST /api/chat`

A chat panel under the plan that answers questions about the solve on screen,
using the Gemini API. It exists for two audiences: the person using the tool,
who wants to know *why* a change is in the plan, and a judge, who wants to
know how the thing is built. It is the entry for MLH's **Best Use of Gemini
API** track, which asks only that the app be built with the Gemini API.

## The one rule

**The solver computes; the model explains.** Every number in a reply must
already be in the context the server renders from the solve. Gemini is never
asked to add, estimate, or forecast. If a question needs a number the solver
has not produced, the model is instructed to say so and point at the controls
that would produce it (the sliders, "Can't do this").

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

→ `{ "reply": "…", "model": "gemini-3.8-flash" }`

| Status | Meaning |
|---|---|
| 200 | A reply. |
| 422 | Malformed: empty conversation, last turn not the user's, or a solve that fails the contract's validation. |
| 429 | Too many questions from one address too quickly. `Retry-After` carries the seconds. The panel says the explainer is resting; the plan on screen is untouched. |
| 502 | Gemini was called and failed (quota, timeout, safety block, unreachable). `detail` carries the reason. |
| 503 | No key on the server. The panel shows "Explainer off". The solver is unaffected. |

`source` is what the client's footer chip says: `local` when the numbers came
from the built-in fallback solver. The instruction tells the model, so it can
say where the numbers came from if asked.

## Configuration

Copy `.env.example` to `.env` at the repository root and set `GEMINI_API_KEY`.
`.env` is gitignored and is loaded once at first use, filling only variables
not already set in the environment. Optional: `GEMINI_MODEL` (default
`gemini-3.8-flash`), `GEMINI_FALLBACK_MODELS` (default
`gemini-3.5-flash,gemini-2.5-flash`), `GEMINI_TIMEOUT_S` (default 25).

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
   when proven. Not financial advice. Cannot act on anything. Two to four
   sentences, no markdown.
2. **The solve.** Rendered in dollars: tier, verdict, qualifier, whether
   minimality was proven, outside cash needed, remaining shortfall, every plan
   item with its marginal figure from the certificate, every candidate left
   out (with "RULED OUT by the user" where that is why), the scheduled
   transactions, and the end-of-day balance for every day, do-nothing and
   with-plan.

## Belt and braces

The reply is scrubbed before it returns: `infeasible` → "not fully coverable",
`guaranteed` → "sufficient under the schedule shown", and the same for the
related forms. A model instruction is not a hard rule; the scrub is. Tests
cover both the instruction and the scrub.

## Frontend

`frontend/src/components/ChatPanel.tsx`, one line in `App.tsx`. On mount it
asks `/api/chat/status` and shows the panel as off rather than hiding it, so
the layout does not jump when a key is added. Four starter questions cover
what a first-time viewer or judge asks. Every send carries the request and
response on screen at that moment, so an answer is always about the plan the
person is looking at. The note under the input says the numbers come from
the solver and Gemini only puts words to them.

## Demo beat

After the proof (1:45 in `docs/demo-script.md`), if there is time: click
"Explain the proof in plain words." Then, to a sceptical judge: "What if my
paycheck comes late?" The honest answer, that the solver has not solved that
case and here is how to try it, is the point.

# Run spec — the Gemini explainer (2026-09-19, Sat)

Frozen after commit. Branch `gemini-chat`, worktree
`/Users/nathanstough/Desktop/vthacks-gemini`, off `main` with `frontend` merged in.

## Why

Nathan's ask: MLH's *Best Use of Gemini API* is on the prize list
(mlh.com/events/vthacks-14/prizes, verified Sat; requirement is only "build
AI-powered apps using the Gemini API"; prize MLH swag kits), and a chatbot with
a good system prompt makes the product much easier to talk about, both for the
user and for a judge at the table.

## Decisions

- **D1. The model explains, never computes.** The endpoint takes the solve
  (request and response) with every message. The instruction renders every
  figure the model may use. The system prompt forbids arithmetic and tells the
  model where to send the person for numbers it does not have.
- **D2. Stateless.** History rides with the request, like `previous_plan`.
  No `previous_interaction_id`, no server-side store.
- **D3. REST over stdlib, no SDK.** One endpoint, one JSON shape, zero new
  dependencies. `generateContent` on `v1beta`, key in `x-goog-api-key`.
- **D4. Off is a visible state, not an absent panel.** 503 without a key; the
  panel says so. A judge should never wonder if a feature is missing or broken.
- **D5. The wording rules are enforced twice.** In the instruction and by a
  scrub on the reply.
- **D6. Default model `gemini-3.8-flash`,** env-overridable. Free tier is
  enough for a demo day of questions.

## Scope

- `backend/app/chat/` — schemas, prompt, Gemini client, the endpoint logic.
- `backend/app/main.py` — two routes, two exception handlers.
- `backend/tests/test_chat.py` — transport replaced; 25 tests.
- `frontend/src/components/ChatPanel.tsx`, `frontend/src/lib/chat.ts`, styles
  in `index.css`, one line in `App.tsx`.
- `docs/features/chat.md`, `.env.example`, README pointer.

Out of scope: streaming replies, natural-language editing of the scenario
(the "buy $180 headphones Friday" idea in the product plan), voice.

## Verification

- `.venv/bin/pytest backend/ -q -m "not perf"` green including the new file.
- `cd frontend && npm run lint && npm run build && npm test` green.
- In the browser: panel renders "Explainer off" without a key; with a bogus
  key the 502 path surfaces Gemini's reason in the panel; with a real key,
  a reply.

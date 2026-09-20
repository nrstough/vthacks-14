"""Request and response models for POST /api/chat.

The chat is stateless like everything else here: every call carries the whole
conversation plus the solve it is about, and nothing survives the response.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StrictStr, model_validator

from app.schemas import Cents, Id, SolveRequest, SolveResponse, Strict

MAX_TURNS = 40
MAX_TURN_CHARS = 4000
# At most three offers on one reply, and an amount no longer than "$999,999.99"
# with room to spare. Both caps live here rather than in `suggestions`, which
# imports `Suggestion` from this module and would otherwise close a cycle.
MAX_SUGGESTIONS = 3
MAX_AMOUNT_CHARS = 20


class ChatTurn(Strict):
    role: Literal["user", "assistant"]
    text: Annotated[StrictStr, Field(min_length=1, max_length=MAX_TURN_CHARS)]


class ChatRequest(Strict):
    messages: list[ChatTurn] = Field(min_length=1, max_length=MAX_TURNS)
    request: SolveRequest  # what the user asked the solver
    response: SolveResponse  # what the solver answered; the only source of numbers
    # Where the account itself came from, which is not the same question as
    # which solver ran. Defaulted so every existing client keeps working.
    account_source: Literal["preset", "modelled", "nessie", "import"] = "preset"

    @model_validator(mode="after")
    def _last_turn_is_the_user(self) -> ChatRequest:
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be from the user")
        return self


class Suggestion(Strict):
    """One offer the model made, already validated against the solve.

    The model may propose a change to what the solver is ASKED; it may not make
    one. Every field here has survived the parser, so a `candidate_id` names a
    change that exists and an `amount_cents` is a legal integer number of cents.
    What it is not is clamped: the slider bounds are the frontend's, they move
    with the value, and sending them here would make them attacker-supplied.
    """

    kind: Literal["rule_out", "allow", "opening", "cushion"]
    candidate_id: Id | None = None
    amount_cents: Cents | None = None

    @model_validator(mode="after")
    def _payload_matches_the_kind(self) -> Suggestion:
        wants_id = self.kind in ("rule_out", "allow")
        if wants_id and (self.candidate_id is None or self.amount_cents is not None):
            raise ValueError(f"{self.kind} carries a candidate_id and nothing else")
        if not wants_id and (self.amount_cents is None or self.candidate_id is not None):
            raise ValueError(f"{self.kind} carries an amount_cents and nothing else")
        return self


class ChatResponse(Strict):
    reply: StrictStr
    model: StrictStr
    # Defaulted for the reason `account_source` is: every existing client keeps
    # working, and a client that predates suggestions simply never sees one.
    suggestions: list[Suggestion] = Field(default_factory=list, max_length=MAX_SUGGESTIONS)


class ChatStatus(Strict):
    configured: bool
    model: StrictStr | None

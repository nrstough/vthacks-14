"""Request and response models for POST /api/chat.

The chat is stateless like everything else here: every call carries the whole
conversation plus the solve it is about, and nothing survives the response.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StrictStr, model_validator

from app.schemas import SolveRequest, SolveResponse, Strict

MAX_TURNS = 40
MAX_TURN_CHARS = 4000


class ChatTurn(Strict):
    role: Literal["user", "assistant"]
    text: Annotated[StrictStr, Field(min_length=1, max_length=MAX_TURN_CHARS)]


class ChatRequest(Strict):
    messages: list[ChatTurn] = Field(min_length=1, max_length=MAX_TURNS)
    request: SolveRequest  # what the user asked the solver
    response: SolveResponse  # what the solver answered; the only source of numbers

    @model_validator(mode="after")
    def _last_turn_is_the_user(self) -> ChatRequest:
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be from the user")
        return self


class ChatResponse(Strict):
    reply: StrictStr
    model: StrictStr


class ChatStatus(Strict):
    configured: bool
    model: StrictStr | None

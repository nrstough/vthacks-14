"""The plan explainer: a chat over the solve on screen, answered by Gemini.

The solver computes; the model explains. The request carries the solve, the
system instruction renders every figure the model may use, and the reply is
scrubbed for the two words the product never says before it goes back.
"""

from __future__ import annotations

import re

from app.chat.gemini import GeminiConfig, GeminiError, generate_with_fallback
from app.chat.prompt import system_instruction
from app.chat.schemas import ChatRequest, ChatResponse, ChatStatus


class ChatUnavailable(Exception):
    """No key configured. The endpoint answers 503 and the UI shows the chat as off."""


class ChatUpstreamError(Exception):
    """Gemini was called and did not answer usefully. 502."""


# Belt and braces over the system instruction. The product's wording rules are
# hard rules, and a model instruction is not a hard rule.
_SCRUB = [
    (re.compile(r"\binfeasible\b", re.IGNORECASE), "not fully coverable"),
    (re.compile(r"\binfeasibility\b", re.IGNORECASE), "the gap"),
    (re.compile(r"\bguaranteed\b", re.IGNORECASE), "sufficient under the schedule shown"),
    (re.compile(r"\bguarantees?\b", re.IGNORECASE), "holds under the schedule shown"),
]


def scrub(text: str) -> str:
    for pattern, replacement in _SCRUB:
        text = pattern.sub(replacement, text)
    return text


def status(config: GeminiConfig | None = None) -> ChatStatus:
    config = config or GeminiConfig.from_env()
    return ChatStatus(configured=bool(config.api_key), model=config.model if config.api_key else None)


def chat(req: ChatRequest, config: GeminiConfig | None = None, source: str = "server") -> ChatResponse:
    config = config or GeminiConfig.from_env()
    if not config.api_key:
        raise ChatUnavailable("The explainer is off: no Gemini API key is configured on the server.")

    instruction = system_instruction(req.request, req.response, source)
    turns = [(m.role, m.text) for m in req.messages]
    try:
        reply, model = generate_with_fallback(config, instruction, turns)
    except GeminiError as e:
        raise ChatUpstreamError(str(e)) from e
    return ChatResponse(reply=scrub(reply), model=model)

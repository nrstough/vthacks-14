"""The plan explainer: a chat over the solve on screen, answered by Gemini.

The solver computes; the model explains. The request carries the solve, the
system instruction renders every figure the model may use, and the reply is
scrubbed for the two words the product never says before it goes back.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

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


def scrub(text: str, protected: Sequence[str] = ()) -> str:
    """Rewrite the words the product never says, and leave the user's data alone.

    The substitutions above are about what *this product* claims. A merchant's
    own name is not a claim, and rewriting it produced visibly broken text: an
    account carrying `GUARANTEED AUTO PROTECTION` came back as "Skipping
    sufficient under the schedule shown AUTO PROTECTION frees $38.59." 88 of 300
    generated accounts carry that row, so this became routine the moment a
    generated account could be the data source, and a Nessie payee such as
    "Guaranteed Rate" does the same.

    So descriptors the model was given are masked out, the substitutions run, and
    the descriptors are restored verbatim, casing included. Every word the model
    wrote *around* them is still checked, which is the half that matters.

    Only multi-token descriptors are protected. A descriptor that is exactly the
    banned word cannot be told apart from product copy, and where it is ambiguous
    the rule wins.
    """
    saved: list[str] = []

    def _mask(match: re.Match[str]) -> str:
        saved.append(match.group(0))
        return f"\x00{len(saved) - 1}\x00"

    # Longest first, so a descriptor that contains a shorter one is masked whole.
    for descriptor in sorted({d for d in protected if d and " " in d.strip()}, key=len, reverse=True):
        text = re.sub(re.escape(descriptor), _mask, text, flags=re.IGNORECASE)

    for pattern, replacement in _SCRUB:
        text = pattern.sub(replacement, text)

    for i, original in enumerate(saved):
        text = text.replace(f"\x00{i}\x00", original)
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
    # The descriptors are the user's own statement lines; the scrubber must not
    # rewrite a merchant's name into product copy. See scrub().
    descriptors = [t.description for t in req.request.scheduled]
    return ChatResponse(reply=scrub(reply, descriptors), model=model)

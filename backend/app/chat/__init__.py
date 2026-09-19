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


_REF = "[[M{}]]"
_REF_RE = re.compile(r"\[\[M(\d+)\]\]")


def mask_descriptors(text: str, descriptors: Sequence[str]) -> tuple[str, list[str]]:
    """Replace every merchant descriptor with an opaque reference.

    This is how the two rules stop fighting. Earlier attempts tried to work out,
    from the model's own output, whether a banned word was a merchant's name or
    the product's claim — first by protecting spans, then by requiring upper case,
    then by matching case-sensitively. Every version was bypassable, because
    provenance cannot be recovered from a string after the fact: a model writing
    "This plan IS GUARANTEED to clear" is indistinguishable from one quoting a
    merchant called "IS GUARANTEED".

    So the model never sees a descriptor at all. It sees `[[M0]]`, and the real
    text is put back after scrubbing. Everything the model writes is prose and is
    scrubbed unconditionally; descriptors are restored afterwards and cannot be
    corrupted. Neither rule has to guess.

    Longest first so a descriptor containing a shorter one is replaced whole, and
    sorted by (-len, value) rather than length alone because ties would otherwise
    break on set iteration order, which varies with PYTHONHASHSEED.
    """
    seen: list[str] = []
    for descriptor in sorted({d for d in descriptors if d and d.strip()},
                             key=lambda d: (-len(d), d)):
        if descriptor not in text:
            continue
        text = text.replace(descriptor, _REF.format(len(seen)))
        seen.append(descriptor)
    return text, seen


def unmask_descriptors(text: str, descriptors: Sequence[str]) -> str:
    """Put the real descriptors back, after scrubbing.

    An index the model invented — it can echo `[[M7]]` when only three exist — is
    dropped rather than guessed at, because inventing a merchant name into a
    sentence about someone's money is worse than a slightly clipped sentence.
    """
    def _restore(match: re.Match[str]) -> str:
        i = int(match.group(1))
        return descriptors[i] if i < len(descriptors) else ""

    return _REF_RE.sub(_restore, text)


def scrub(text: str) -> str:
    """Rewrite the words the product never says.

    Unconditional, with no exceptions and nothing to bypass. Merchant names are
    not here to be protected: `mask_descriptors` took them out before the model
    saw them, and `unmask_descriptors` puts them back after this has run.
    """
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

    # The model never sees a merchant descriptor, only an opaque reference, so
    # nothing it writes can be mistaken for one — and nothing it writes escapes
    # the scrubber. The real text goes back afterwards. See mask_descriptors.
    instruction, refs = mask_descriptors(
        system_instruction(req.request, req.response, source),
        [t.description for t in req.request.scheduled],
    )
    turns = [(m.role, m.text) for m in req.messages]
    try:
        reply, model = generate_with_fallback(config, instruction, turns)
    except GeminiError as e:
        raise ChatUpstreamError(str(e)) from e
    return ChatResponse(reply=unmask_descriptors(scrub(reply), refs), model=model)

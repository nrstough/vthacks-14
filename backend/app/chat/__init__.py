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


_REF = "\u2e24M{}\u2e25"          # two-and-a-half em brackets; not on a keyboard
_REF_RE = re.compile("\u2e24M(\\d+)\u2e25")


def descriptor_refs(descriptors: Sequence[str]) -> list[str]:
    """The stable reference list, built from the descriptors alone.

    Derived from the request rather than from whichever text happened to mention
    a merchant first, so the instruction and every conversation turn share one
    numbering. Longest first so a descriptor containing a shorter one is replaced
    whole; `(-len, value)` rather than length alone because ties would otherwise
    break on set iteration order, which varies with PYTHONHASHSEED.
    """
    return sorted({d for d in descriptors if d and d.strip()}, key=lambda d: (-len(d), d))


def mask_descriptors(text: str, refs: Sequence[str]) -> str:
    """Replace every merchant descriptor with an opaque reference.

    This is how the two rules stop fighting. Earlier attempts tried to work out,
    from the model's own output, whether a banned word was a merchant's name or
    the product's claim — protected spans, then an upper-case rule, then
    case-sensitive matching. Every one was bypassable, because provenance cannot
    be recovered from a string after the fact: a model writing "This plan IS
    GUARANTEED to clear" is indistinguishable from one quoting a merchant called
    "IS GUARANTEED".

    So the model never sees a descriptor. It sees a reference, and the real text
    is put back after scrubbing. Everything the model writes is prose and is
    scrubbed unconditionally; descriptors are restored afterwards and cannot be
    corrupted.

    ONE pass, not one per descriptor. Replacing sequentially lets a later
    descriptor rewrite the placeholders an earlier one just inserted — a merchant
    named "M" was enough to corrupt every reference in the text. `re.sub` does not
    rescan what it has substituted, so a single alternation cannot collide with
    its own output.

    Anchored on word boundaries, because this also runs over text the product did
    not compose. A descriptor of "a" against the fixed brief produced 239
    replacements and "You ⸤M0⸥re the expl⸤M0⸥iner"; unanchored substring matching
    is only safe on a field that holds nothing but the descriptor, and the
    conversation history is not one.
    """
    if not refs:
        return text
    index = {d: i for i, d in enumerate(refs)}
    parts = []
    for d in refs:
        body = re.escape(d)
        if d[:1].isalnum() or d[:1] == "_":
            body = r"\b" + body
        if d[-1:].isalnum() or d[-1:] == "_":
            body = body + r"\b"
        parts.append(body)
    pattern = re.compile("|".join(parts))
    return pattern.sub(lambda m: _REF.format(index[m.group(0)]), text)


def unmask_descriptors(text: str, refs: Sequence[str]) -> str:
    """Put the real descriptors back, after scrubbing.

    An index the model invented — a reference to the eighth merchant when three
    exist — is dropped rather than guessed at. Inventing a merchant name into a
    sentence about someone's money is worse than a slightly clipped sentence.
    """
    def _restore(match: re.Match[str]) -> str:
        i = int(match.group(1))
        return refs[i] if i < len(refs) else ""

    return _REF_RE.sub(_restore, text)


def scrub(text: str) -> str:
    """Rewrite the words the product never says.

    Unconditional, with no exceptions and nothing to bypass. Merchant names are
    not here to be protected: they were taken out before the model saw them and
    are put back after this has run.
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
    refs = descriptor_refs([t.description for t in req.request.scheduled])
    # Mask the FIELDS, then render — never the rendered instruction. Running the
    # replacement over the finished text rewrote the fixed brief itself: a
    # transaction described as "a" turned "You are the explainer" into
    # "You ⸤M0⸥re the expl⸤M0⸥iner". The descriptors live in known fields, so
    # replace them there, where a whole-value substitution is exactly right, and
    # leave every word the product wrote alone.
    masked = req.model_copy(deep=True)
    for txn in masked.request.scheduled:
        txn.description = mask_descriptors(txn.description, refs)
    for cand in masked.request.candidates:
        cand.detail = mask_descriptors(cand.detail, refs)
    for item in masked.response.plan:
        item.detail = mask_descriptors(item.detail, refs)
    instruction = system_instruction(
        masked.request, masked.response, source, req.account_source
    )
    # The history too, not just the instruction. A user who types a merchant's
    # name into the chat puts it back in front of the model, which echoes it, and
    # the scrubber corrupts it again — the original bug, reached by a different
    # road.
    turns = [(m.role, mask_descriptors(m.text, refs)) for m in req.messages]
    try:
        reply, model = generate_with_fallback(config, instruction, turns)
    except GeminiError as e:
        raise ChatUpstreamError(str(e)) from e
    return ChatResponse(reply=unmask_descriptors(scrub(reply), refs), model=model)

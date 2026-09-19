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


def _protectable(descriptors: Sequence[str]) -> set[str]:
    """Which descriptors may shield a banned word, and why so few.

    `protected` is caller text: the descriptions ride in on the request, so a
    client can name a transaction "is guaranteed" and, unguarded, the model's own
    sentence survives inside the protected span. That is a bypass of the one rule
    this product is built around, so the bar to qualify is deliberately narrow.

    A bank statement descriptor is upper case. Every row of the merchant table is
    (`app/accounts/merchants.py`), so are the shipped demo fixtures, and so is
    everything a real feed produces — the casing is an artefact of the card
    networks, not a style choice. Prose is not upper case. So: upper case, and
    more than one token.

    This is only half the rule; the other half is that the match is
    CASE-SENSITIVE (see `scrub`). Qualifying on upper case and then matching
    case-insensitively was a bypass rather than a protection: a descriptor of
    "GUARANTEED SAVINGS" matched the prose "guaranteed savings" and shielded the
    model's own claim.

    Two consequences, both deliberate, both failing towards the rule:

      * A lower-case or mixed-case descriptor — "Guaranteed Rate" — is never
        protected, so it gets scrubbed like prose and its name is corrupted.
      * A model that re-cases an upper-case descriptor loses the protection for
        the same reason.

    Both are the original D-C bug in a narrower window, and both are preferable
    to letting a banned claim through. Where the two rules collide, the product's
    rule wins.
    """
    return {
        d for d in descriptors
        if d and " " in d.strip() and d == d.upper() and any(c.isalpha() for c in d)
    }


def _substitute(text: str) -> str:
    for pattern, replacement in _SCRUB:
        text = pattern.sub(replacement, text)
    return text


def _has_banned(text: str, spans: Sequence[str]) -> bool:
    """Is a banned word present anywhere outside the restored descriptors?

    Blanking each restored descriptor and re-checking is enough: the only reason
    a banned word may survive `_substitute` is that it sat inside one of them.
    """
    remainder = text
    for span in spans:
        remainder = remainder.replace(span, " ")
    return remainder != _substitute(remainder)


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
    plain = _substitute(text)
    if not protected:
        return plain

    saved: list[str] = []

    def _mask(match: re.Match[str]) -> str:
        saved.append(match.group(0))
        return f"\x00{len(saved) - 1}\x00"

    masked = text
    # Longest first so a descriptor containing a shorter one is masked whole, and
    # `-len, then the string` rather than a bare length key: ties would otherwise
    # break on set iteration order, which varies with PYTHONHASHSEED. The same
    # rule is why lexicon.py uses tuples, and the output here is user-facing.
    for descriptor in sorted(_protectable(protected), key=lambda d: (-len(d), d)):
        # \s+ for the spaces: a model that reflows or line-wraps the descriptor
        # would otherwise slip past an exact-space match and be corrupted again.
        # CASE-SENSITIVE, and that is the whole protection. Matching
        # case-insensitively defeated the upper-case rule above: a descriptor of
        # "GUARANTEED SAVINGS" then matched the prose "guaranteed savings" and
        # shielded the model's own claim. A statement descriptor appears in the
        # reply in statement casing; prose does not.
        #
        # \s+ for the spaces, so a reflowed or line-wrapped echo still matches.
        pattern = r"\s+".join(re.escape(part) for part in descriptor.split())
        masked = re.sub(pattern, _mask, masked)

    restored = _substitute(masked)
    for i, original in enumerate(saved):
        restored = restored.replace(f"\x00{i}\x00", original)

    # The final check, and the reason this is safe at all. `protected` is caller
    # text — the descriptions ride in on the request — so a client can name a
    # transaction "is guaranteed" and, without this, the model's own sentence
    # would survive inside the protected span. If any banned word is still
    # present outside the descriptors we put back, the protection has been turned
    # into a bypass, and we fall back to scrubbing everything.
    #
    # That corrupts a merchant name in the rare ambiguous case, which is the old
    # bug — and is the right direction to fail. Where the two rules collide, the
    # product's rule wins.
    if _has_banned(restored, saved):
        return plain
    return restored


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

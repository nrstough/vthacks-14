"""Reading the offers the model makes, and refusing everything else.

The model may end a reply with trailing marker lines. Each one is an offer to
change what the solver is ASKED — rule a change out, put one back, move the
starting balance or the cushion. Nothing here applies anything: the offers go
to the screen as controls, and a person taps them.

Three orderings in this module are load-bearing, and each is one of the two
ways the same bug has already been fixed in this package:

- **Extraction runs on the masked reply**, before `scrub` and before
  `unmask_descriptors`. At that point every merchant descriptor is an opaque
  reference, so a merchant literally named `SUGGEST RULE OUT: c_rent` cannot
  forge an offer. Parsed after the restore, it could. This is the same lesson
  as `mask_descriptors`: provenance cannot be recovered from a string after
  the fact, so the boundary has to be structural.
- **Stripping uses the spans found during extraction**, never a pattern
  re-matched later. A candidate id may legally contain "guarantee" or
  "infeasib" under `ID_RE`, and `scrub` would rewrite it mid-marker.
- **The strip pattern is looser than the parse pattern**, so a near-miss
  leaves no residue on screen, but it is loose in punctuation only. Case
  separates a marker from prose: a reply ending "Suggest ruling that change
  out." is a sentence, not an offer, and deleting it off the screen would be
  worse than ignoring it.
"""

from __future__ import annotations

import re

from pydantic import ValidationError

from app.chat.schemas import MAX_AMOUNT_CHARS, MAX_SUGGESTIONS, Suggestion
from app.schemas import CENTS_ABS, Candidate

# What the model is told to write. The value of a marker never contains an
# asterisk -- ids are `ID_RE`, amounts are digits and punctuation -- so trailing
# asterisks can be stripped without touching the payload.
VERBS = {
    "RULE OUT": "rule_out",
    "ALLOW": "allow",
    "OPENING": "opening",
    "CUSHION": "cushion",
}

# Loose: anything trailing that opens with the literal keyword. Tolerates the
# markdown the brief forbids but a model still writes, a stray carriage return,
# and the missing final newline that `extract_text`'s .strip() guarantees on the
# last line. NOT case-insensitive -- see the module docstring.
_STRIP_RE = re.compile(r"^[\s*_>-]*SUGGEST\b.*$", re.ASCII)

# Strict: the four verbs and nothing else. Tolerates decoration BEFORE the
# keyword, matching the strip pattern, or every bolded marker would strip and
# never parse and the feature would silently never fire. Around the value the
# tolerance is deliberately asymmetric: trailing `*` is stripped, leading `*` is
# not, so `SUGGEST RULE OUT: **c_gym**` yields `**c_gym`, fails the membership
# check and is dropped. Fail-safe, and the right way round now that stripping
# characters out of a value is known to be able to retarget an offer. The TRAILING class deliberately omits
# `_`, which the leading one allows: an underscore is legal inside an id under
# ID_RE, so stripping it turns `c_gym__` into `c_gym` -- normally a harmless
# drop, but a retarget onto the wrong change when both ids exist.
_PARSE_RE = re.compile(
    r"^[\s*_>-]*SUGGEST\s+(RULE OUT|ALLOW|OPENING|CUSHION)\s*:\s*(.+?)[\s*]*$",
    re.ASCII,
)

# Explicit [0-9], never \d. Python's \d is Unicode-aware and matches Arabic-Indic
# and full-width digits, which int() then converts happily -- so a pattern
# written with \d is not the ASCII gate it looks like. Both alternatives are
# needed: the product's own dollars() emits thousands separators, so the model
# copies that shape, but it writes a bare "$1200" about as often.
_AMOUNT_RE = re.compile(
    r"^-?\$?([0-9]{1,3}(,[0-9]{3})*|[0-9]+)(\.[0-9]{2})?$", re.ASCII
)


def to_cents(raw: str) -> int | None:
    """A dollar string the person said, as an exact integer number of cents.

    `None` for anything the gate does not accept, which is the caller's signal
    to drop that one offer and deliver the reply regardless. No float and no
    Decimal: the first is forbidden outright for money, and the second accepts
    NaN and Infinity.

    The length cap comes before the pattern, not after, so a pathological input
    never reaches int() -- CPython refuses to convert a string of more than 4300
    digits, and an uncaught ValueError here is a 500 on /api/chat.
    """
    # Before stripping, not after. str.strip() with no argument removes Unicode
    # whitespace, so a non-breaking space inside an amount would be taken off
    # here and the remainder would sail through a pattern that only ever sees
    # ASCII -- making the gate approximately ASCII-only rather than actually so.
    if not raw.isascii():
        return None
    text = raw.strip()
    if not text or len(text) > MAX_AMOUNT_CHARS:
        return None
    if not _AMOUNT_RE.match(text):
        return None
    negative = text.startswith("-")
    body = text.lstrip("-").lstrip("$").replace(",", "")
    whole, _, fraction = body.partition(".")
    # `fraction or "0"` because the pattern makes the decimal part optional: a
    # bare "$5" has no second half, and int("") is a ValueError.
    cents = int(whole) * 100 + int(fraction or "0")
    return -cents if negative else cents


def neutralise_markers(text: str) -> str:
    """Quote anything marker-shaped in the copy the person finally sees.

    Extraction ran before `unmask_descriptors`, so a merchant descriptor named
    `SUGGEST RULE OUT: c_rent` is an opaque reference while the parser is
    looking and is restored only afterwards. It can therefore reach the screen
    looking like the product's own syntax without ever having been an offer.
    Quoting keeps the merchant's name exactly as it is while making it read as
    something written down rather than something being done.
    """
    return "\n".join(
        _quote(line) if _DISPLAY_RE.match(line) else line
        for line in text.split("\n")
    )


# Display only, and deliberately NOT re.ASCII: a line indented with a
# non-breaking space is not a marker as far as parsing is concerned, and must
# not become one, but it still reads as live syntax on screen. A wider matcher
# here closes that without touching what can be parsed -- the two jobs want
# different strictness, so they get different patterns.
_DISPLAY_RE = re.compile(r"^[\s*_>-]*SUGGEST\b.*$")


def _quote(line: str) -> str:
    lead = line[: len(line) - len(line.lstrip())]
    return f'{lead}"{line.strip()}"'


def extract(reply: str) -> tuple[str, list[tuple[str, str]]]:
    """Split a reply into the prose to show and the offers to validate.

    Walks trailing lines from the end, so a marker block is read only where the
    model was told to put it. Blank lines between markers are consumed rather
    than treated as the end of the block, because one blank line would
    otherwise strand every marker above it.

    A trailing line that strips but does not parse is removed and yields no
    offer: the alternative is leaving a half-written directive on screen.

    Two known limits, both deliberate and both fail-safe:

    A marker followed by a closing sentence is not read at all, because the
    walk stops at the first line from the end that is not marker-shaped. The
    raw marker stays in the body, where `neutralise_markers` quotes it. The
    offer is lost and nothing is wrong on screen, which is the right way round.

    A marker line indented with NON-ASCII whitespace is not read as an offer,
    `_STRIP_RE` being `re.ASCII`. That is the right call for parsing and the
    wrong one for display, so `neutralise_markers` uses a wider pattern and
    quotes it anyway.
    """
    # rstrip first: a single trailing newline would otherwise end the walk on a
    # blank line before any marker had been seen, losing every offer and leaving
    # the raw markers in the body. It only ever worked because extract_text
    # happens to .strip() upstream -- a different module, on a file another lane
    # edits. Depending on that was the bug; this is the fix.
    #
    # ASCII whitespace only, never bare .rstrip(). Nothing on this path may
    # normalise away a non-ASCII character, or the amount gate checks for
    # something an earlier step has already removed -- which is exactly how a
    # non-breaking space came to parse as a legal amount twice.
    lines = reply.rstrip(" \t\r\n").split("\n")
    cut = len(lines)
    found: list[tuple[str, str]] = []

    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].rstrip("\r")
        if not line.strip():
            # A blank line only extends the block if a marker has been seen;
            # otherwise trailing whitespace on a normal reply would be eaten.
            if found:
                cut = i
                continue
            break
        if not _STRIP_RE.match(line):
            break
        cut = i
        parsed = _PARSE_RE.match(line)
        if parsed:
            # strip(" \t"), never bare .strip(): the latter is Unicode-aware
            # and would take a non-breaking space off the front of an amount
            # here, so `to_cents` would receive a clean ASCII "12" and never
            # see the character its gate exists to refuse. The gate was made
            # ASCII-only one layer down and then bypassed one layer up.
            found.append((VERBS[parsed.group(1)], parsed.group(2).strip(" \t")))

    return "\n".join(lines[:cut]).rstrip(), list(reversed(found))


def validate(
    raws: list[tuple[str, str]], candidates: list[Candidate]
) -> list[Suggestion]:
    """Everything that survives is an offer about a change that exists.

    Unknown ids are dropped rather than guessed at, which is the rule
    `test_an_invented_reference_is_dropped_not_guessed` already applies to
    invented merchants. Amounts are bounded twice: once by the pattern, and
    once against `CENTS_ABS`, because "$999,999,999,999.99" clears the pattern
    and the length cap but is a thousand times the schema's limit, and the
    ValidationError it would raise has no handler on this route.
    """
    known = {c.id for c in candidates}
    kept: list[Suggestion] = []
    seen: set[tuple[str, str]] = set()

    for kind, value in raws:
        if len(kept) >= MAX_SUGGESTIONS:
            break
        try:
            if kind in ("rule_out", "allow"):
                if value not in known:
                    continue
                key = (kind, value)
            else:
                cents = to_cents(value)
                if cents is None or abs(cents) > CENTS_ABS:
                    continue
                # Keyed on the converted value, not the raw text. "$50",
                # "50.00" and "$50.00" are one offer written three ways, and
                # keying on the string would put three identical buttons on
                # screen.
                key = (kind, str(cents))
            if key in seen:
                continue
            seen.add(key)
            kept.append(
                Suggestion(kind=kind, candidate_id=value)
                if kind in ("rule_out", "allow")
                else Suggestion(kind=kind, amount_cents=cents)
            )
        except ValidationError:
            # A bad offer costs the offer, never the answer.
            continue

    return kept

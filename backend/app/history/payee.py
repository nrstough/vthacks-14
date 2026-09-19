"""Group statement lines that are the same payee.

Reuses the candidate lexicon's `normalise`, which already uppercases, strips
accents and splits on anything that is not a letter or digit. What is left to
do is drop the parts that differ between two charges from the SAME merchant:
store numbers, transaction ids, and the single letters left behind by
`WALMART #1234 W`.
"""

from __future__ import annotations

from app.candidates.lexicon import normalise

_KEY_TOKENS = 3


def payee_key(description: str) -> str:
    """A stable grouping key. Not a display string and never returned."""
    tokens = [t for t in normalise(description) if len(t) > 1 and not t.isdigit()]
    if not tokens:
        # Everything was digits or single letters. Fall back to the raw
        # normalised form so two such rows still group with each other rather
        # than every one of them becoming its own stream.
        tokens = list(normalise(description))
    return " ".join(tokens[:_KEY_TOKENS])

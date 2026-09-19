"""The pin that makes moving the generator safe.

`windows(300)` is consumed by six property tests in `test_candidates_policy.py`
and by the whole of `test_candidates_roundtrip.py`, including the perf test that
compares both engines on every generated account. None of those compare against a
stored value, so before this file nothing actually pinned generation: a change to
the RNG call sequence would silently resample every one of them and the suite
would still pass, testing different inputs than it used to.

The merchant table and the two generation primitives are moving from here into
`backend/app/` so the product can reach them. That move is only safe if
generation stays byte-identical for the existing seeds, and this is the test that
proves it. If the hash below moves, the move has changed behaviour — revert it,
do not re-pin the hash.

The RNG call sequence is the contract. `rng.choice(MERCHANTS)` is index-based, so
reordering, deduplicating or extending the table changes every draw after it, and
so does adding or removing a single `rng.random()` gate.
"""

from __future__ import annotations

import hashlib
import json

from tests.fixtures.accounts import MERCHANTS, windows

# Measured on branch data-deploy at ac2af08, before the generator moved.
GOLDEN_SHA256 = "8d4ddf3092a22cb4de03d50d23fe558420b2ef7eb2cb1272f77948e543081048"


def test_generation_is_byte_identical_for_the_pinned_seeds():
    blob = json.dumps(windows(300), sort_keys=True)
    assert hashlib.sha256(blob.encode()).hexdigest() == GOLDEN_SHA256


def test_the_merchant_table_has_not_been_reordered_or_resized():
    # A length check alone cannot see a reorder, and a reorder is exactly what
    # `rng.choice` is sensitive to. Pin both ends by value.
    assert len(MERCHANTS) == 36
    assert MERCHANTS[0] == ("DOORDASH*CHIPOTLE", "discretionary", False, 1200, 4800)
    assert MERCHANTS[-1] == ("GUARANTEED AUTO PROTECTION", "discretionary", False, 2500, 9000)


def test_the_deliberate_traps_are_still_in_the_table():
    """Two rows exist to be classified wrongly if the lexicon regresses.

    GAP INSURANCE PREMIUM must not read as clothing, and the last row carries a
    word the certificate sentence bans, which is what proves a label never quotes
    a merchant string. Losing either during the move would quietly weaken the
    lexicon tests that depend on them.
    """
    descriptions = [row[0] for row in MERCHANTS]
    assert "GAP INSURANCE PREMIUM" in descriptions
    assert "GUARANTEED AUTO PROTECTION" in descriptions

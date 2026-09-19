"""Turn a transaction list into the changes a person could make.

See docs/features/candidates.md for the lexicon, the policy table and the rules
the solver relies on.
"""

from __future__ import annotations

from .generator import generate

__all__ = ["generate"]

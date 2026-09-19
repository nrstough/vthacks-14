"""Engine failures.

Its own module rather than living inside an engine, because the API layer and
both engines need to name it and neither engine should have to import the other.
"""

from __future__ import annotations


class EngineUnavailable(RuntimeError):
    """No exact engine could answer this request.

    Raised rather than falling back to a heuristic: an approximate answer would
    be indistinguishable from a proven one in the response, and the entire
    product claim is that the plan is provably the smallest.
    """

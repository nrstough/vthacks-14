"""Exhaustive search. Exact, dependency-free, and the reference the CP-SAT
engine is checked against.

It enumerates every subset of the free candidates, so it is exponential by
construction and refuses rather than degrading when the list gets long. At the
sizes this product sees — a couple of dozen candidates in a two-week horizon —
it is instant, which is why it is a shippable engine and not only a test double.
"""

from __future__ import annotations

from datetime import date

from app.schemas import MAX_FREE, Candidate, SolveRequest

from .eligibility import Eligibility
from .errors import EngineUnavailable
from .objective import numeric_terms, score
from .simulate import simulate


def solve_brute(
    req: SolveRequest,
    days: list[date],
    elig: Eligibility,
    previous_plan: set[str],
) -> tuple[list[str], str, bool, tuple[int, ...]]:
    """Return (chosen ids sorted, status, minimal_proven, the seven term values)."""
    free = elig.free
    if len(free) > MAX_FREE:
        raise EngineUnavailable(
            f"{len(free)} changes are on the table; exhaustive search is capped at {MAX_FREE}"
        )

    best: list[Candidate] | None = None
    best_score: tuple | None = None
    best_trace = None

    for mask in range(1 << len(free)):
        chosen = [*elig.forced, *(free[i] for i in range(len(free)) if mask >> i & 1)]
        # One change per transaction. forced is already deduped, so this only
        # ever rejects a free combination.
        targets = {c.target_txn_id for c in chosen}
        if len(targets) != len(chosen):
            continue
        trace = simulate(req, chosen, days)
        candidate_score = score(trace, chosen, previous_plan)
        if best_score is None or candidate_score < best_score:
            best, best_score, best_trace = chosen, candidate_score, trace

    assert best is not None and best_trace is not None, "mask 0 is always admissible"
    return (
        sorted(c.id for c in best),
        "OPTIMAL",
        True,
        numeric_terms(best_trace, best, previous_plan),
    )

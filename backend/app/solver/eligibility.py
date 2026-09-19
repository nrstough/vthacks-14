"""Decide which changes are on the table before any solving happens.

Three things narrow the candidate list, and the order matters:

1. Lead time. A change you can no longer action in time is not a choice.
2. Locks. Ruled out never appears; pinned always appears.
3. One change per transaction. Without it a caller offering both "skip the
   $31.80 order" and "trim it by $15.90" lets the solver take both and free
   $47.70 from a $31.80 charge.

Two pinned changes on one transaction are a caller mistake we absorb rather
than refuse: keep the lower id and report the other as excluded.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas import Candidate, SolveRequest

from .dates import days_between


@dataclass(frozen=True)
class Eligibility:
    forced: list[Candidate]  # pinned and honourable
    free: list[Candidate]  # the solver's actual decision variables
    excluded_locked_in: list[str]  # pinned but dropped, sorted
    considered: int  # everything that survived lead time and rule-outs


def _has_duplicate_target(chosen: list[Candidate]) -> bool:
    seen: set[str] = set()
    for c in chosen:
        if c.target_txn_id in seen:
            return True
        seen.add(c.target_txn_id)
    return False


def split(req: SolveRequest) -> Eligibility:
    locked_in = set(req.locks.in_)
    locked_out = set(req.locks.out)

    actionable = [
        c
        for c in req.candidates
        if days_between(req.as_of, c.effective_date) >= c.lead_time_days and c.id not in locked_out
    ]

    pinned = sorted((c for c in actionable if c.id in locked_in), key=lambda c: c.id)
    forced: list[Candidate] = []
    for c in pinned:
        if not _has_duplicate_target([*forced, c]):
            forced.append(c)

    forced_targets = {c.target_txn_id for c in forced}
    free = [
        c for c in actionable if c.id not in locked_in and c.target_txn_id not in forced_targets
    ]

    forced_ids = {c.id for c in forced}
    excluded = sorted(c.id for c in req.candidates if c.id in locked_in and c.id not in forced_ids)

    return Eligibility(
        forced=forced, free=free, excluded_locked_in=excluded, considered=len(actionable)
    )

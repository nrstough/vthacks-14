"""The single definition of what makes one plan better than another.

Lexicographic: a later term only ever breaks a tie among plans equal on every
earlier one. Both engines and the parity tests import this, so there is exactly
one place the order can be wrong.

Cushion-reached is a yes-or-no term ABOVE the number of changes, and the SIZE of
the cushion shortfall sits below it. Ranking the cushion's size above cardinality
makes the solver add changes purely to pad the cushion, which contradicts the
product's headline claim of the smallest set.
"""

from __future__ import annotations

from app.schemas import Candidate, CertificateItem

from .simulate import Trace

TERMS = (
    "days_below_zero",
    "worst_shortfall",
    "buffer_missed",
    "cardinality",
    "exposure",
    "pain",
    "hysteresis",
)


def numeric_terms(trace: Trace, chosen: list[Candidate], previous_plan: set[str]) -> tuple[int, ...]:
    """The seven comparable numbers, in order. Term 8 is the id tuple below."""
    ids = {c.id for c in chosen}
    return (
        trace.days_below_zero,
        trace.worst_shortfall,
        0 if trace.min_balance >= trace.buffer_cents else 1,
        len(ids),
        trace.below_buffer_exposure,
        sum(c.pain for c in chosen),
        len(ids ^ previous_plan),
    )


def score(trace: Trace, chosen: list[Candidate], previous_plan: set[str]) -> tuple:
    """Full ordering key: the seven numbers, then the sorted ids as a tiebreak.

    Tuple comparison does the whole lexicographic job, and the final element
    makes the optimum unique, which is what determinism rests on.
    """
    return (*numeric_terms(trace, chosen, previous_plan), tuple(sorted(c.id for c in chosen)))


def load_bearing(item: CertificateItem) -> bool:
    """Does dropping this change make things measurably worse than the plan already is?

    Marginal, not absolute. Asking only whether the plan-without-it goes below
    zero is automatically true at tier 3, where the plan is below zero anyway —
    the proof would pass vacuously in exactly the case it matters most.
    """
    return item.marginal_cents > 0 or item.marginal_days > 0

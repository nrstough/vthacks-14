"""The proof that nothing in the plan is decoration.

Take each chosen change out, re-simulate, and record how much worse things get.
It is O(n) extra simulations and it converts a claim into a demonstration: the
user can read, item by item, the day they would break without it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.schemas import Candidate, CertificateItem, SolveRequest

from .dates import to_iso
from .objective import load_bearing
from .simulate import Trace, simulate


@dataclass(frozen=True)
class CertificateResult:
    per_item: list[CertificateItem]  # in plan order
    irredundant: bool
    worst_item: CertificateItem | None


def build(
    req: SolveRequest,
    plan_order: list[Candidate],
    days: list[date],
    best: Trace,
) -> CertificateResult:
    per_item: list[CertificateItem] = []
    for c in plan_order:
        without = [o for o in plan_order if o.id != c.id]
        t = simulate(req, without, days)
        per_item.append(
            CertificateItem(
                candidate_id=c.id,
                worst_shortfall_cents=t.worst_shortfall,
                worst_date=to_iso(t.worst_shortfall_date) if t.worst_shortfall_date else None,
                marginal_cents=t.worst_shortfall - best.worst_shortfall,
                marginal_days=t.days_below_zero - best.days_below_zero,
            )
        )

    # An empty plan proves nothing, so it is not irredundant.
    irredundant = bool(per_item) and all(load_bearing(p) for p in per_item)

    worst_item: CertificateItem | None = None
    for p in per_item:
        # Strict >, so ties keep the earlier item in plan order.
        if worst_item is None or p.marginal_cents > worst_item.marginal_cents:
            worst_item = p

    return CertificateResult(per_item=per_item, irredundant=irredundant, worst_item=worst_item)

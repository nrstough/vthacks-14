"""How good is the answer, and what is still missing.

Three tiers, and the word *infeasible* appears in none of them. Priced slack
makes every request answerable: the question is never "can this be solved" but
"how far does the best plan get, and what would close the rest".
"""

from __future__ import annotations

from app.schemas import ExternalCash

from .dates import to_iso
from .simulate import Trace


def tier_of(trace: Trace) -> int:
    if trace.worst_shortfall > 0:
        return 3
    if trace.min_balance < trace.buffer_cents:
        return 2
    return 1


def external_cash(trace: Trace) -> ExternalCash | None:
    """Tier 3 only: how much outside money, and the day it has to be there.

    The amount covers the deepest point, but the deadline is the FIRST day the
    balance goes under, which can be days earlier. Reporting the deepest day
    would tell someone to find the money after they already needed it.
    """
    if trace.worst_shortfall == 0 or trace.first_below_zero_date is None:
        return None
    return ExternalCash(
        amount_cents=trace.worst_shortfall,
        by_date=to_iso(trace.first_below_zero_date),
    )

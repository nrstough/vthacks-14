"""Walk the horizon day by day and report what the balance did.

Everything downstream — tier, certificate, wording, the chart — is derived from
a Trace, and the engines are checked by re-deriving their objective from one.
That makes this the single place a balance is ever computed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.schemas import Candidate, SolveRequest

from .dates import parse


@dataclass(frozen=True)
class Trace:
    balances: list[int]  # end-of-day, one per day of the horizon
    days_below_zero: int
    worst_shortfall: int  # positive cents below zero, 0 if never negative
    worst_shortfall_date: date | None
    first_below_zero_date: date | None  # the day money must be there, not the deepest
    below_buffer_exposure: int  # cents of cushion eaten, summed over days
    min_balance: int
    buffer_cents: int

    @property
    def tightest_date_index(self) -> int:
        """First day attaining the minimum — ties resolve to the earlier day."""
        return self.balances.index(self.min_balance)


def simulate(req: SolveRequest, chosen: list[Candidate], days: list[date]) -> Trace:
    # Net movement per day. Summed before the walk, so two entries on one day
    # cannot depend on the order they were added.
    delta: dict[date, int] = {}
    for txn in req.scheduled:
        d = parse(txn.date)
        delta[d] = delta.get(d, 0) + txn.amount_cents
    # A chosen change frees cash on its effective date and, if it is a deferral,
    # hands it back on the recharge date. A recharge past the horizon is simply
    # never reached by the walk.
    for c in chosen:
        eff = parse(c.effective_date)
        delta[eff] = delta.get(eff, 0) + c.freed_cents
        if c.recharge_date is not None:
            rec = parse(c.recharge_date)
            delta[rec] = delta.get(rec, 0) - c.freed_cents

    balances: list[int] = []
    running = req.opening_balance_cents
    days_below_zero = 0
    worst_shortfall = 0
    worst_shortfall_date: date | None = None
    first_below_zero_date: date | None = None
    below_buffer_exposure = 0
    min_balance: int | None = None

    for day in days:
        running += delta.get(day, 0)
        balances.append(running)
        if min_balance is None or running < min_balance:
            min_balance = running
        if running < 0:
            days_below_zero += 1
            if first_below_zero_date is None:
                first_below_zero_date = day
            # Strict >, so the worst date is the FIRST day attaining the worst dip.
            if -running > worst_shortfall:
                worst_shortfall = -running
                worst_shortfall_date = day
        if running < req.buffer_cents:
            below_buffer_exposure += req.buffer_cents - running

    assert min_balance is not None, "horizon is never empty; the schema rejects that"
    return Trace(
        balances=balances,
        days_below_zero=days_below_zero,
        worst_shortfall=worst_shortfall,
        worst_shortfall_date=worst_shortfall_date,
        first_below_zero_date=first_below_zero_date,
        below_buffer_exposure=below_buffer_exposure,
        min_balance=min_balance,
        buffer_cents=req.buffer_cents,
    )

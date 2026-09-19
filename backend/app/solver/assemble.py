"""Turn the solved plan into the response the frontend renders.

The frontend does no financial arithmetic of its own — the chart's only input is
the `balances` array built here — so every number a person sees is produced in
this file from a Trace, not recomputed in a browser.
"""

from __future__ import annotations

from datetime import date

from app.schemas import (
    BalanceRow,
    Candidate,
    Certificate,
    Meta,
    PlanItem,
    Shortfall,
    SolveRequest,
    SolveResponse,
)

from .certificate import CertificateResult
from .dates import to_iso
from .eligibility import Eligibility
from .objective import load_bearing
from .simulate import Trace
from .tiers import external_cash
from .wording import certificate_sentence, plan_reason, verdict_and_qualifier


def plan_sort_key(c: Candidate) -> tuple[str, str]:
    """By the day the change takes effect, then by id.

    Both parts compare as plain strings, never by locale: a collation that
    ordered `c_1` against `c-a` differently from Python's code-point order would
    silently desynchronise this service from the reference solver.
    """
    return (c.effective_date, c.id)


def build_response(
    req: SolveRequest,
    days: list[date],
    elig: Eligibility,
    plan_order: list[Candidate],
    best: Trace,
    do_nothing: Trace,
    cert: CertificateResult,
    tier: int,
    solver: str,
    status: str,
    minimal_proven: bool,
    wall_ms: float,
) -> SolveResponse:
    plan_clears_zero = best.worst_shortfall == 0
    by_id = {p.candidate_id: p for p in cert.per_item}

    plan = [
        PlanItem(
            candidate_id=c.id,
            label=c.label,
            detail=c.detail,
            action=c.action,
            date=c.effective_date,
            freed_cents=c.freed_cents,
            pain=c.pain,
            strictly_needed=load_bearing(by_id[c.id]),
            reason=plan_reason(by_id[c.id], plan_clears_zero),
        )
        for c in plan_order
    ]

    changes_by_day: dict[str, list[str]] = {}
    for c in plan_order:
        changes_by_day.setdefault(c.effective_date, []).append(c.id)
    # A payday is income that actually ARRIVES. An income row may legitimately
    # be negative — a clawback is still an income row — and marking that day a
    # payday puts "Payday lands on <date>" on a day money left. Both the sign
    # and the kind, never one alone: this is the same guard as
    # app/candidates/generator.py:111-118, which records it as the class of two
    # prior deferral bugs. The generator was fixed and this was not.
    paydays = {t.date for t in req.scheduled if t.kind == "income" and t.amount_cents > 0}

    balances = [
        BalanceRow(
            date=(iso := to_iso(day)),
            baseline_cents=do_nothing.balances[i],
            with_plan_cents=best.balances[i],
            is_payday=iso in paydays,
            changes_here=sorted(changes_by_day.get(iso, [])),
        )
        for i, day in enumerate(days)
    ]

    days_iso = [to_iso(d) for d in days]
    verdict, qualifier = verdict_and_qualifier(
        tier=tier,
        n=len(plan),
        best=best,
        do_nothing=do_nothing,
        horizon_end=req.horizon_end,
        days_iso=days_iso,
        minimal_proven=minimal_proven,
    )

    return SolveResponse(
        tier=tier,
        verdict=verdict,
        qualifier=qualifier,
        plan=plan,
        certificate=Certificate(
            irredundant=cert.irredundant,
            minimal_proven=minimal_proven,
            sentence=certificate_sentence(tier, plan_order, cert, best, minimal_proven),
            per_item=cert.per_item,
        ),
        shortfall=Shortfall(
            worst_cents=best.worst_shortfall,
            worst_date=to_iso(best.worst_shortfall_date) if best.worst_shortfall_date else None,
            total_cents=sum(-b for b in best.balances if b < 0),
        ),
        external_cash_needed=external_cash(best),
        balances=balances,
        meta=Meta(
            solver=solver,
            status=status,
            wall_ms=wall_ms,
            candidates_considered=elig.considered,
            excluded_locked_in=elig.excluded_locked_in,
        ),
    )

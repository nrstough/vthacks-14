"""Orchestration: request in, response out.

Engine choice is the only interesting decision here. CP-SAT is preferred because
it proves optimality and scales past what enumeration can reach; exhaustive
search is the fallback, and it is an exact one. If neither can answer, the
request fails loudly. There is deliberately no third path that guesses.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.schemas import MAX_FREE, Candidate, SolveRequest, SolveResponse

from .assemble import build_response, plan_sort_key
from .certificate import build as build_certificate
from .dates import day_range
from .eligibility import split
from .engine_brute import solve_brute
from .errors import EngineUnavailable
from .objective import numeric_terms
from .simulate import simulate
from .tiers import tier_of


@dataclass(frozen=True)
class Settings:
    total_budget_s: float = 6.0
    min_stage_s: float = 0.25
    force_engine: str | None = None  # "cp-sat" | "brute-force" | None


def load_cpsat():
    """Import seam.

    A function rather than a module-level import so tests can simulate a machine
    without OR-Tools by patching one name, instead of manipulating sys.modules
    and hoping no earlier test already cached the real thing.
    """
    from .engine_cpsat import solve_cpsat

    return solve_cpsat


def solve(req: SolveRequest, settings: Settings | None = None) -> SolveResponse:
    settings = settings or Settings()
    started = time.perf_counter()

    days = day_range(req.as_of, req.horizon_end)
    elig = split(req)
    previous_plan = set(req.previous_plan)

    ids, status, minimal_proven, stage_values, solver_name = _run_engine(
        req, days, elig, previous_plan, settings
    )

    chosen_ids = set(ids)
    best_set: list[Candidate] = [*elig.forced, *(c for c in elig.free if c.id in chosen_ids)]
    best = simulate(req, best_set, days)

    # The engines report their own objective; this re-derives it from the one
    # simulator every other number comes from. A disagreement means the model
    # and the ledger have drifted apart, which is the failure that would other-
    # wise surface as a confidently wrong plan.
    if minimal_proven and stage_values is not None:
        recomputed = numeric_terms(best, best_set, previous_plan)
        if recomputed != stage_values:
            raise EngineUnavailable(
                f"{solver_name} reported {stage_values} but the plan simulates to {recomputed}"
            )

    plan_order = sorted(best_set, key=plan_sort_key)
    cert = build_certificate(req, plan_order, days, best)
    do_nothing = simulate(req, [], days)

    return build_response(
        req=req,
        days=days,
        elig=elig,
        plan_order=plan_order,
        best=best,
        do_nothing=do_nothing,
        cert=cert,
        tier=tier_of(best),
        solver=solver_name,
        status=status,
        minimal_proven=minimal_proven,
        wall_ms=round((time.perf_counter() - started) * 1000, 1),
    )


def _run_engine(req, days, elig, previous_plan, settings):
    """Pick an engine and run it, falling back only from CP-SAT to exhaustion."""
    if settings.force_engine != "brute-force":
        try:
            solve_cpsat = load_cpsat()
        except ImportError:
            if settings.force_engine == "cp-sat":
                raise EngineUnavailable("OR-Tools is not installed") from None
        else:
            try:
                ids, status, proven, stages = solve_cpsat(
                    req, days, elig, previous_plan, settings
                )
                return ids, status, proven, stages, "cp-sat"
            except EngineUnavailable:
                if settings.force_engine == "cp-sat" or len(elig.free) > MAX_FREE:
                    raise

    ids, status, proven, stages = solve_brute(req, days, elig, previous_plan)
    return ids, status, proven, stages, "brute-force"

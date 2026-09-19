"""Constraint solver.

The objective is lexicographic, and lexicographic is not a weighted sum: no set
of weights reliably reproduces "never trade one day below zero for any amount of
cushion" without coefficients that overflow or, worse, quietly stop dominating
at some input size. So each term is minimised in its own solve, and the result
is pinned as a bound before the next one runs.

Daily balances are linear *expressions*, not variables, so the model has one
boolean per candidate and a handful of helpers rather than a variable per day.
The helpers are epigraphs — `worst >= -balance`, `exposure >= buffer - balance`
— which are correct for minimising and remain correct as upper bounds once
pinned.

Nothing is read back from the model except the chosen booleans. Every reported
number is re-derived by the simulator in solve.py, which is what catches a
modelling slip rather than shipping it.
"""

from __future__ import annotations

import time
from datetime import date

from ortools.sat.python import cp_model

from app.schemas import SolveRequest

from .eligibility import Eligibility
from .errors import EngineUnavailable
from .objective import TERMS
from .simulate import simulate

_SOLVED = (cp_model.OPTIMAL, cp_model.FEASIBLE)


def solve_cpsat(
    req: SolveRequest,
    days: list[date],
    elig: Eligibility,
    previous_plan: set[str],
    settings,
) -> tuple[list[str], str, bool, tuple[int, ...]]:
    free = elig.free
    forced_ids = [c.id for c in elig.forced]
    deadline = time.perf_counter() + settings.total_budget_s

    # The do-nothing-plus-pinned baseline, straight from the simulator so the
    # model and the ledger cannot disagree about what the schedule does.
    base = simulate(req, elig.forced, days).balances
    index = {d: i for i, d in enumerate(days)}
    horizon = len(days)
    buffer = req.buffer_cents

    model = cp_model.CpModel()
    x = {c.id: model.new_bool_var(c.id) for c in free}

    # Each change frees its cash from its effective day until the day it is paid
    # back, if ever. A recharge beyond the horizon simply never lands.
    active: list[list[tuple[int, str]]] = [[] for _ in range(horizon)]
    for c in free:
        start = index[date.fromisoformat(c.effective_date)]
        end = horizon
        if c.recharge_date is not None:
            rec = date.fromisoformat(c.recharge_date)
            if rec in index:
                end = index[rec]
        for t in range(start, end):
            active[t].append((c.freed_cents, c.id))

    balance = [
        base[t] + sum(freed * x[cid] for freed, cid in active[t]) if active[t] else base[t]
        for t in range(horizon)
    ]

    # One change per transaction, matching what the search does everywhere else.
    groups: dict[str, list[str]] = {}
    for c in free:
        groups.setdefault(c.target_txn_id, []).append(c.id)
    for ids in groups.values():
        if len(ids) > 1:
            model.add(sum(x[i] for i in ids) <= 1)

    # --- the seven numeric terms -------------------------------------------
    below = [model.new_bool_var(f"below_{t}") for t in range(horizon)]
    for t in range(horizon):
        model.add(balance[t] >= 0).only_enforce_if(~below[t])

    worst = model.new_int_var(0, max(0, -min(base)), "worst")
    for t in range(horizon):
        model.add(worst >= -balance[t])

    missed = model.new_bool_var("buffer_missed")
    for t in range(horizon):
        model.add(balance[t] >= buffer).only_enforce_if(~missed)

    exposure = [
        model.new_int_var(0, max(0, buffer - base[t]), f"exposure_{t}") for t in range(horizon)
    ]
    for t in range(horizon):
        model.add(exposure[t] >= buffer - balance[t])

    # Constants for the pinned changes and for previously-shown changes that are
    # no longer on offer. Folded in so each stage's value is the whole term, and
    # the cross-check in solve.py compares like with like.
    free_ids = {c.id for c in free}
    known = set(forced_ids) | free_ids
    hysteresis_const = sum(1 for i in forced_ids if i not in previous_plan) + sum(
        1 for p in previous_plan if p not in known
    )

    terms = (
        sum(below),
        worst,
        missed,
        len(forced_ids) + sum(x.values()),
        sum(exposure),
        sum(c.pain for c in elig.forced) + sum(c.pain * x[c.id] for c in free),
        hysteresis_const
        + sum(x[c.id] for c in free if c.id not in previous_plan)
        + sum(1 - x[c.id] for c in free if c.id in previous_plan),
    )

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0

    def budget(solves_left: int) -> float | None:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return None
        return min(remaining, max(settings.min_stage_s, remaining / max(1, solves_left)))

    incumbent: set[str] | None = None
    values: list[int] = []
    proven = True

    for i, expr in enumerate(terms):
        allowance = budget((len(terms) - i) + len(free))
        if allowance is None:
            raise EngineUnavailable(f"ran out of time at stage {TERMS[i]}")

        solver.parameters.max_time_in_seconds = allowance
        model.minimize(expr)
        status = solver.solve(model)
        if status not in _SOLVED:
            # Hand the request back rather than answering it unproven. Exhaustive
            # search can still answer it exactly at these sizes, and an exact
            # answer beats a plan we cannot stand behind. Never read values off a
            # failed solve either: they are stale or arbitrary, not imprecise.
            raise EngineUnavailable(
                f"stage {TERMS[i]} returned {solver.status_name(status)}"
            )

        proven = proven and status == cp_model.OPTIMAL
        value = solver.value(expr)
        values.append(value)
        model.add(expr <= value)
        incumbent = {cid for cid in x if solver.value(x[cid])}

        model.clear_hints()
        for cid, var in x.items():
            model.add_hint(var, cid in incumbent)

    assert incumbent is not None

    if not proven:
        # Without a proven cardinality the tiebreak below is not well defined,
        # and an arbitrary choice among near-ties is worse than admitting the
        # search was cut short.
        return sorted(incumbent | set(forced_ids)), "FEASIBLE", False, tuple(values)

    chosen = _smallest_id_set(model, solver, x, incumbent, values[3] - len(forced_ids), budget)
    if chosen is None:
        return sorted(incumbent | set(forced_ids)), "FEASIBLE", False, tuple(values)

    return sorted(chosen | set(forced_ids)), "OPTIMAL", True, tuple(values)


def _smallest_id_set(model, solver, x, incumbent, cardinality, budget):
    """Break remaining ties on the sorted candidate ids.

    Every plan still in play now scores identically on all seven terms, so the
    choice among them is arbitrary unless something decides it. Left arbitrary,
    the plan would shift between runs and between machines — the same request
    answered two ways is a trust problem long before it is a correctness one.

    Walks the ids in order and keeps the smallest one that can still be part of
    a tied plan. Each test is a feasibility solve under an assumption, which is
    retractable; an outright `add` would not be.
    """
    model.clear_objective()
    model.add(sum(x.values()) == cardinality)

    fixed_in = 0
    remaining = sorted(x)
    for position, cid in enumerate(remaining):
        if fixed_in == cardinality:
            model.add(x[cid] == 0)
            continue
        if cid in incumbent:
            model.add(x[cid] == 1)
            fixed_in += 1
            continue

        allowance = budget(len(remaining) - position)
        if allowance is None:
            return None
        solver.parameters.max_time_in_seconds = allowance

        model.clear_assumptions()
        model.add_assumption(x[cid])
        status = solver.solve(model)
        model.clear_assumptions()

        if status in _SOLVED:
            model.add(x[cid] == 1)
            fixed_in += 1
            incumbent = {c for c in x if solver.value(x[c])}
        elif status == cp_model.INFEASIBLE:
            model.add(x[cid] == 0)
        else:
            return None

    return incumbent

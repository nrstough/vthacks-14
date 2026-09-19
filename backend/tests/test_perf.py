"""Timings.

Marked `perf` and excluded from the gate: these run on whatever laptop is to
hand, during a hackathon, alongside a dev server. Failing a build on that would
be noise. They exist to produce a number worth quoting, and to catch an order-of-
magnitude regression rather than a jittery one.

    pytest backend/ -m perf -s
"""

from __future__ import annotations

import statistics
import time

import pytest

from app.schemas import SolveRequest
from app.solver.solve import Settings, solve
from tests.fixtures.scenarios import SCENARIOS
from tests.gen import instances

pytestmark = pytest.mark.perf


def median_ms(raw: dict, settings: Settings | None = None, runs: int = 5) -> float:
    req = SolveRequest.model_validate(raw)
    solve(req, settings)  # warm the import and the first model build
    times = []
    for _ in range(runs):
        started = time.perf_counter()
        solve(req, settings)
        times.append((time.perf_counter() - started) * 1000)
    return statistics.median(times)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_a_demo_account_feels_instant(name):
    """The lock toggles re-solve on every click, so this is interaction latency,
    not batch throughput."""
    ms = median_ms(SCENARIOS[name])
    print(f"\n{name}: {ms:.1f} ms")
    assert ms < 150


def test_a_full_sized_account_is_still_interactive():
    """Sixty changes over a two-month horizon: past anything enumeration could
    do, and past what a real account carries."""
    scheduled = [{"id": "t_pay", "date": "2026-03-15", "description": "PAY",
                  "amount_cents": 200_000, "kind": "income", "recurring": True}]
    candidates = []
    for i in range(60):
        scheduled.append({"id": f"t_{i:02d}", "date": f"2026-03-{(i % 28) + 1:02d}",
                          "description": "X", "amount_cents": -(2_000 + i * 37),
                          "kind": "discretionary", "recurring": False})
        candidates.append({"id": f"c_{i:02d}", "label": "X", "detail": "X", "action": "skip",
                           "target_txn_id": f"t_{i:02d}", "freed_cents": 2_000 + i * 37,
                           "effective_date": f"2026-03-{(i % 28) + 1:02d}", "recharge_date": None,
                           "lead_time_days": 0, "pain": (i % 5) + 1})
    raw = {"as_of": "2026-03-01", "horizon_end": "2026-04-29", "opening_balance_cents": 5_000,
           "buffer_cents": 2_500, "scheduled": scheduled, "candidates": candidates,
           "locks": {"in": [], "out": []}, "previous_plan": []}

    ms = median_ms(raw, Settings(force_engine="cp-sat"), runs=3)
    print(f"\n60 changes over 60 days: {ms:.0f} ms")
    assert ms < 2_000


def test_exhaustive_search_stays_within_its_limit():
    """Eighteen changes is 262,144 subsets — the cap exists because the next
    step doubles it."""
    scheduled = []
    candidates = []
    for i in range(18):
        scheduled.append({"id": f"t_{i:02d}", "date": "2026-03-10", "description": "X",
                          "amount_cents": -5_000, "kind": "discretionary", "recurring": False})
        candidates.append({"id": f"c_{i:02d}", "label": "X", "detail": "X", "action": "skip",
                           "target_txn_id": f"t_{i:02d}", "freed_cents": 5_000,
                           "effective_date": "2026-03-02", "recharge_date": None,
                           "lead_time_days": 0, "pain": (i % 5) + 1})
    raw = {"as_of": "2026-03-01", "horizon_end": "2026-03-20", "opening_balance_cents": 60_000,
           "buffer_cents": 0, "scheduled": scheduled, "candidates": candidates,
           "locks": {"in": [], "out": []}, "previous_plan": []}

    ms = median_ms(raw, Settings(force_engine="brute-force"), runs=1)
    print(f"\n18 changes, exhaustive: {ms:.0f} ms")
    assert ms < 30_000


def test_a_batch_of_random_accounts():
    reqs = [SolveRequest.model_validate(r) for r in instances(100)]
    started = time.perf_counter()
    for req in reqs:
        solve(req)
    total = (time.perf_counter() - started) * 1000
    print(f"\n100 random accounts: {total:.0f} ms total, {total / len(reqs):.1f} ms each")
    assert total / len(reqs) < 150

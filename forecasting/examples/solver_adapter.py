"""Executable synthetic illustration; it contains no learned or real forecasts."""

from __future__ import annotations

from datetime import date, timedelta
import json

from forecasting.adapter import build_solve_request


def base_request() -> dict:
    return {
        "as_of": "2026-09-19", "horizon_end": "2026-10-02",
        "opening_balance_cents": 10000, "buffer_cents": 2500,
        "scheduled": [
            {"id": "known_rent", "date": "2026-09-20", "description": "Known rent installment",
             "amount_cents": -3000, "kind": "bill", "recurring": True},
            {"id": "known_pay", "date": "2026-09-26", "description": "Known payroll",
             "amount_cents": 15000, "kind": "income", "recurring": True},
        ],
        "candidates": [], "locks": {"in": [], "out": []}, "previous_plan": [],
    }


def synthetic_forecast(daily_amount: str = "5.00") -> dict:
    start = date(2026, 9, 19)
    return {
        "model_id": "synthetic-illustration-v1", "source": "handwritten synthetic demonstration",
        "target": "residual_outflow", "currency": "USD", "context_end": "2026-09-18",
        "experimental": True,
        "days": [{"date": (start + timedelta(days=i)).isoformat(), "amount": daily_amount}
                 for i in range(14)],
    }


def demonstrate() -> dict:
    from app.schemas import SolveRequest
    from app.solver.solve import Settings, solve

    base = base_request()
    evidence = (
        "Synthetic example only: the forecast defines ordinary cash spending excluding "
        "the sole known outflow (rent); payroll is income. This construction is explicit, "
        "not an inference from a target label or a real-account coverage claim."
    )
    results = {}
    for name, amount in [("known_schedule_only", None), ("five_per_day", "5.00"), ("fifteen_per_day", "15.00")]:
        request, provenance = (base, None) if amount is None else build_solve_request(
            base, synthetic_forecast(amount), request_currency="USD", nonoverlap_evidence=evidence
        )
        response = solve(SolveRequest.model_validate(request), Settings(force_engine="brute-force"))
        results[name] = {
            "tier": response.tier,
            "minimum_balance_cents": min(row.with_plan_cents for row in response.balances),
            "external_cash_needed": response.external_cash_needed.model_dump() if response.external_cash_needed else None,
            "plan": [item.model_dump() for item in response.plan],
            "qualifier": response.qualifier,
            "provenance": provenance,
        }
    return results


if __name__ == "__main__":
    print(json.dumps(demonstrate(), indent=2))

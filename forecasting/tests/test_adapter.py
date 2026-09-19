from copy import deepcopy
from decimal import Decimal, localcontext
import json
import subprocess
import sys

import pytest
from pydantic import ValidationError

from forecasting.adapter import ForecastAdapterError, build_solve_request
from forecasting.examples.solver_adapter import base_request, demonstrate, synthetic_forecast


EVIDENCE = "Synthetic scenario construction excludes the known rent installment; payroll is income."


def adapt(base=None, forecast=None, **kwargs):
    return build_solve_request(
        base_request() if base is None else base,
        synthetic_forecast() if forecast is None else forecast,
        request_currency=kwargs.pop("request_currency", "USD"),
        nonoverlap_evidence=kwargs.pop("nonoverlap_evidence", EVIDENCE), **kwargs,
    )


def test_adapter_import_does_not_import_solver_or_schema():
    result = subprocess.run(
        [sys.executable, "-c", "import sys; import forecasting.adapter; print('app.schemas' in sys.modules)"],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "False"


def test_valid_roundtrip_and_input_preservation_including_candidates_and_locks():
    from app.schemas import SolveRequest

    base = base_request()
    # This move is caller supplied solely to exercise passthrough semantics;
    # adapter-generated aggregate rows never gain candidate actions.
    base["scheduled"].append({"id": "known_optional", "date": "2026-09-21", "description": "Known optional purchase",
                              "amount_cents": -1000, "kind": "discretionary", "recurring": False})
    base["candidates"].append({"id": "provided_skip", "label": "Supplied change", "detail": "User-supplied option",
                               "action": "skip", "target_txn_id": "known_optional", "freed_cents": 1000,
                               "effective_date": "2026-09-21", "recharge_date": None, "lead_time_days": 0, "pain": 1})
    base["locks"]["out"] = ["provided_skip"]
    base["previous_plan"] = ["provided_skip"]
    forecast = synthetic_forecast()
    originals = deepcopy((base, forecast))
    request, sidecar = adapt(base, forecast, nonoverlap_evidence=EVIDENCE + " The supplied optional purchase is excluded too.")
    SolveRequest.model_validate(request)
    assert (base, forecast) == originals
    assert request["scheduled"][:len(base["scheduled"])] == base["scheduled"]
    assert {k: v for k, v in request.items() if k != "scheduled"} == {k: v for k, v in base.items() if k != "scheduled"}
    added = request["scheduled"][len(base["scheduled"]):]
    assert len(added) == 14
    assert all(row["kind"] == "discretionary" and row["amount_cents"] == -500 and row["recurring"] is False for row in added)
    assert len({row["id"] for row in added}) == 14
    assert "source" not in request and "model_id" not in request
    assert sidecar["total_forecast_outflow_cents"] == 7000
    assert sidecar["nonoverlap_status"].startswith("caller_asserted")
    # No mutable objects shared with either input, including nested locks.
    request["locks"]["out"].clear()
    request["scheduled"][0]["description"] = "changed output"
    assert (base, forecast) == originals
    json.dumps(request)
    json.dumps(sidecar)


@pytest.mark.parametrize("amount,cents", [
    (0, 0), (1, 100), (1.005, 101), ("0.005", 1), ("0.0049", 0),
    (Decimal("19.995"), 2000), ("1e2", 10000), ("1000000000", 10**11),
    ("0.004999999999999999999999999999999999", 0),
    ("0.005000000000000000000000000000000001", 1),
])
def test_exact_major_unit_to_cent_rounding(amount, cents):
    request, _ = adapt(forecast=synthetic_forecast(amount))
    assert request["scheduled"][-1]["amount_cents"] == -cents


def test_rounding_is_independent_of_callers_decimal_precision():
    with localcontext() as context:
        context.prec = 3
        request, _ = adapt(forecast=synthetic_forecast("12345.005"))
    assert request["scheduled"][-1]["amount_cents"] == -1234501


@pytest.mark.parametrize("amount", [-1, "-0.01", float("inf"), float("-inf"), float("nan"),
                                     "NaN", Decimal("sNaN"), "Infinity", True, False, None, [], {},
                                     "no amount", "1e999999", "1000000000.001"])
def test_invalid_amounts_are_rejected(amount):
    with pytest.raises(ForecastAdapterError):
        adapt(forecast=synthetic_forecast(amount))


@pytest.mark.parametrize("evidence", [None, "", " \n ", 12, False])
@pytest.mark.parametrize("target", ["residual_outflow", "total_posted_outflow"])
def test_every_target_requires_nonoverlap_evidence(evidence, target):
    forecast = synthetic_forecast()
    forecast["target"] = target
    with pytest.raises(ForecastAdapterError, match="nonoverlap_evidence"):
        adapt(forecast=forecast, nonoverlap_evidence=evidence)


def test_explicit_nonoverlapping_total_posted_outflow_is_accepted():
    forecast = synthetic_forecast()
    forecast["target"] = "total_posted_outflow"
    base = base_request()
    base["scheduled"] = [row for row in base["scheduled"] if row["kind"] == "income"]
    request, sidecar = adapt(base, forecast, nonoverlap_evidence="Scenario has only income scheduled; this total outflow covers all assumed cash debits.")
    assert len(request["scheduled"]) == 15
    assert sidecar["target"] == "total_posted_outflow"


def test_card_spending_rejected_even_with_evidence():
    forecast = synthetic_forecast()
    forecast["target"] = "card_spending"
    with pytest.raises(ForecastAdapterError, match="payment-timing"):
        adapt(forecast=forecast)


@pytest.mark.parametrize("field,value", [
    ("model_id", ""), ("source", None), ("target", "spending"), ("experimental", "false"),
    ("experimental", 1), ("currency", "usd"), ("currency", "US"), ("currency", None),
    ("currency", "ZAR"), ("context_end", "2026-09-19"), ("context_end", "2026-09-17"),
    ("context_end", "2026-09-20"), ("context_end", "20260918"), ("context_end", "2026-02-30"),
    ("context_end", "2026-09-18T00:00:00"),
])
def test_invalid_forecast_metadata(field, value):
    forecast = synthetic_forecast()
    forecast[field] = value
    with pytest.raises(ForecastAdapterError):
        adapt(forecast=forecast)


@pytest.mark.parametrize("currency", [None, "usd", " USD", True, "ZAR"])
def test_request_currency_is_explicit_and_must_match(currency):
    with pytest.raises(ForecastAdapterError):
        adapt(request_currency=currency)


@pytest.mark.parametrize("mutation", ["missing", "extra", "not_dict", "missing_amount", "extra_day_field", "days_tuple"])
def test_invalid_forecast_shape(mutation):
    forecast = synthetic_forecast()
    if mutation == "missing":
        del forecast["source"]
    elif mutation == "extra":
        forecast["confidence"] = 0.95
    elif mutation == "not_dict":
        forecast = []
    elif mutation == "missing_amount":
        del forecast["days"][0]["amount"]
    elif mutation == "extra_day_field":
        forecast["days"][0]["confidence"] = 0.95
    else:
        forecast["days"] = tuple(forecast["days"])
    with pytest.raises(ForecastAdapterError):
        adapt(forecast=forecast)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "before", "after", "noniso", "datetime"])
def test_invalid_forecast_dates_and_coverage(mutation):
    forecast = synthetic_forecast()
    if mutation == "missing":
        forecast["days"].pop()
    elif mutation == "extra":
        forecast["days"].append({"date": "2026-10-03", "amount": 1})
    else:
        forecast["days"][0]["date"] = {"duplicate": "2026-09-20", "before": "2026-09-18",
                                         "after": "2026-10-03", "noniso": "20260919",
                                         "datetime": "2026-09-19T12:00:00"}[mutation]
    with pytest.raises(ForecastAdapterError):
        adapt(forecast=forecast)


@pytest.mark.parametrize("end", ["2026-10-01", "2026-10-03"])
def test_requires_exact_fourteen_day_request_horizon(end):
    base = base_request()
    base["horizon_end"] = end
    with pytest.raises(ForecastAdapterError, match="exactly 14"):
        adapt(base=base)


def test_sorted_input_and_model_identity_produce_stable_ids():
    forecast = synthetic_forecast()
    first, _ = adapt(forecast=forecast)
    forecast["days"].reverse()
    for row in forecast["days"]:
        row["amount"] = "10.00"
    second, _ = adapt(forecast=forecast)
    assert [row["id"] for row in first["scheduled"]] == [row["id"] for row in second["scheduled"]]
    assert [row["date"] for row in second["scheduled"][-14:]] == sorted(row["date"] for row in second["scheduled"][-14:])
    forecast["model_id"] = "different-model"
    third, _ = adapt(forecast=forecast)
    assert {row["id"] for row in first["scheduled"][-14:]}.isdisjoint(row["id"] for row in third["scheduled"][-14:])


def test_second_append_is_rejected_not_double_counted():
    request, _ = adapt()
    with pytest.raises(ForecastAdapterError, match="collides"):
        adapt(base=request)


def test_collision_with_candidate_namespace_is_rejected():
    result, _ = adapt()
    base = base_request()
    base["candidates"] = [{"id": result["scheduled"][-1]["id"], "label": "Provided", "detail": "Caller action",
                           "action": "skip", "target_txn_id": "known_rent", "freed_cents": 0,
                           "effective_date": "2026-09-20", "lead_time_days": 0, "pain": 1}]
    with pytest.raises(ForecastAdapterError, match="collides"):
        adapt(base=base)


def test_existing_schema_is_used_and_extra_fields_are_not_hidden():
    base = base_request()
    base["model_id"] = "must stay in sidecar"
    with pytest.raises(ValidationError):
        adapt(base=base)
    base = base_request()
    base["opening_balance_cents"] = 1.5
    with pytest.raises(ValidationError):
        adapt(base=base)


def test_combined_request_schema_size_limit_is_checked():
    base = base_request()
    base["scheduled"] = [dict(base["scheduled"][0], id=f"known_{i}") for i in range(1987)]
    with pytest.raises(ValidationError):
        adapt(base=base)


def test_existing_solver_demonstrates_conditional_effect_without_inventing_changes():
    result = demonstrate()
    assert result["known_schedule_only"]["tier"] == 1
    assert result["known_schedule_only"]["minimum_balance_cents"] == 7000
    assert result["five_per_day"]["tier"] == 1
    assert result["five_per_day"]["minimum_balance_cents"] == 3500
    assert result["fifteen_per_day"]["tier"] == 3
    assert result["fifteen_per_day"]["minimum_balance_cents"] == -3500
    assert result["fifteen_per_day"]["external_cash_needed"] == {"amount_cents": 3500, "by_date": "2026-09-23"}
    assert all(scenario["plan"] == [] for scenario in result.values())
    assert result["fifteen_per_day"]["provenance"]["experimental"] is True

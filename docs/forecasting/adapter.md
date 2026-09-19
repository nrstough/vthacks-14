# Standalone forecast → solver adapter

Implemented September 19, 2026 against this worktree's existing `app.schemas.SolveRequest` and solver. No backend, API, solver, candidate generation, or frontend file is changed.

The callable lives in `forecasting/adapter.py`:

```python
build_solve_request(
    base_request: dict,
    forecast: dict,
    *,
    request_currency: str,
    nonoverlap_evidence: str | None = None,
) -> tuple[dict, dict]
```

The first returned dict is a validated copy of the supplied request with forecast rows appended. The second dict contains provenance, currency, rounding, model identity, experimental status, and the caller's non-overlap assertion. Keep that sidecar with the scenario; the frozen request schema rejects these extra fields.

## Forecast input and validation

```python
forecast = {
    "model_id": "model-version-id",
    "source": "dataset/version or provenance description",
    "target": "residual_outflow",
    "currency": "USD",
    "context_end": "2026-09-18",
    "experimental": True,
    "days": [
        {"date": "2026-09-19", "amount": "5.00"},
        # ...every following calendar day through 2026-10-02...
    ],
}
```

The input must contain exactly the seven keys above. Each row must contain exactly `date` and `amount`. There must be exactly 14 unique consecutive days matching the request's entire inclusive `as_of` → `horizon_end`; shorter or longer request horizons are rejected. `context_end` must equal the day immediately preceding `as_of`. Unordered daily rows are accepted and sorted. All dates are strict calendar-valid `YYYY-MM-DD` strings; timestamps are rejected.

Amounts are **nonnegative major currency units**, accepted as an integer, float, decimal string, or `Decimal`. Python floats are interpreted using their printed decimal value (`Decimal(str(amount))`). Booleans, nonfinite values, negative values, and amounts beyond the unchanged solver's per-row bound are rejected. Each day is rounded independently using `ROUND_HALF_UP` after multiplication by 100, then negated to become an integer-cent outflow. A zero estimate produces zero cents. Decimal precision is controlled locally so a long decimal cannot accidentally cross the half-cent boundary due to ambient precision.

Forecast rows have `kind: discretionary`, `recurring: false`, and deterministic IDs derived from model identity and ISO date. These IDs do not contain an account identity: an invocation represents **one account-level aggregate forecast**. Aggregate multiple submodels/segments before calling this adapter. A collision with a supplied scheduled or candidate ID is rejected. Calling the adapter twice on an already augmented request is rejected instead of double-counting. For a new forecast scenario, start from the original known-event request again.

The adapter validates both the base and augmented request through the unchanged Pydantic schema. Schema validation errors remain `pydantic.ValidationError`; forecast/accounting validation errors are `ForecastAdapterError`, a `ValueError` subclass. The schema is imported lazily when the function is called, so importing the forecasting package need not load the solver dependencies.

## Accounting boundary

Every accepted forecast target requires a nonempty `nonoverlap_evidence` string. Merely calling a model `residual_outflow` is insufficient evidence that its predicted spending excludes rent, subscriptions, transfers, or payments already present in the known schedule. The sidecar explicitly marks the evidence as **caller asserted, not independently verified by this adapter**. An integration owner must substantiate it through coverage and exclusion rules using information available at forecast time.

Accepted targets:

- `residual_outflow`: use only when validated exclusions ensure the forecast covers outflows absent from supplied known events.
- `total_posted_outflow`: usable for an explicitly non-overlapping scenario, for example a schedule containing income only. Do not append it to a schedule that already includes the outflows it predicts.

`card_spending` is deliberately rejected, even with evidence. Card purchases are not necessarily debits from the checking account on the purchase day. This workstream does not supply the statement, repayment, and account-linking logic needed to turn those purchases into checking-account cash flow.

`request_currency` and `forecast.currency` must be the same uppercase three-letter code. No FX conversion, currency inference, or dollar relabeling occurs. This validates the presence and agreement of metadata, not membership in a currency registry. Both inputs must already represent the same account's currency and units.

**Existing solver display limitation:** its human-readable prose hardcodes dollar signs, and the API has no currency field. The numerical request can retain another currency's cents with matching metadata, but do not display the existing dollar-formatted prose as if it correctly describes that currency. Any non-USD product integration needs a separately owned currency-aware presentation change. The executable example below uses USD.

The adapter cannot verify whether the training histories used real zeroes or missing observations, validate a model's promotion status, prove an account match, or establish forecast accuracy from this small interchange shape. Those responsibilities remain with acquisition, audit, predictor, and integration layers.

## What is preserved

The adapter deep-copies the base request and preserves all existing rows, amounts, order, dates, candidates, locks, opening balance, buffer, and previous-plan fields. Omitted optional fields stay omitted. Neither input is mutated. It adds no skip, defer, cancel, or downgrade candidate: an aggregate spending prediction does not establish an actionable payment to cancel.

The unchanged solver's proof applies to the conditional schedule being supplied. A point estimate is neither a calibrated balance interval nor a probability of avoiding overdraft. Keep the sidecar and forecast assumptions visible to the integrating product.

## Executable synthetic example and checks

`forecasting/examples/solver_adapter.py` supplies a clearly labelled, handwritten synthetic fixture: $100 opening balance, a $30 known rent installment, $150 payroll, and a $25 cushion. Ordinary forecast cash spending explicitly excludes rent. There are no candidates or fabricated cancellations.

From the worktree root, with an environment containing the existing backend requirements and pytest:

```sh
PYTHONPATH="$PWD:$PWD/backend" python -m forecasting.examples.solver_adapter
PYTHONPATH="$PWD:$PWD/backend" python -m pytest forecasting/tests/test_adapter.py -q
```

Observed using the original project interpreter read-only on September 19, 2026: **82 tests passed in 0.18 seconds**. They cover strict schema passthrough, mutation isolation, candidates/locks/history preservation, exact half-cent rounding, numeric and metadata failures, date coverage, duplicate/colliding IDs, currency/target/accounting gates, strict combined-size limits, deterministic IDs, lazy import, and the actual existing brute-force solver.

| Conditional scenario | Minimum balance | Existing solver tier | Generated actions |
|---|---:|---:|---:|
| Known schedule only | $70.00 | 1 | 0 |
| Add $5/day synthetic residual outflow | $35.00 | 1 | 0 |
| Add $15/day synthetic residual outflow | -$35.00 | 3 | 0 |

In the last scenario the unchanged solver requests $35 external cash by September 23; the deepest dip occurs September 25. This demonstrates sensitivity to forecast assumptions, not learned-model quality, real-user validation, or a permission to perform financial actions.

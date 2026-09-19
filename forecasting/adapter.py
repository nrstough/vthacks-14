"""Append explicitly non-overlapping forecasts to the unchanged solver contract.

The adapter creates scenario inputs, not executable financial actions. A caller's
non-overlap evidence is recorded as an assertion; this module cannot establish
accounting coverage from aggregate forecast values or target names alone.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import hashlib
import re


class ForecastAdapterError(ValueError):
    """The forecast cannot safely be represented by the existing request shape."""


def _iso(value: object, field: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ForecastAdapterError(f"{field} must be a YYYY-MM-DD string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ForecastAdapterError(f"{field} is not a calendar date") from exc


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ForecastAdapterError(f"{field} must be a nonempty string")
    return value


def _currency(value: object, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{3}", value):
        raise ForecastAdapterError(f"{field} must be an uppercase three-letter currency code")
    return value


def _cents(value: object, limit: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ForecastAdapterError("forecast amount must be a number or decimal string, not a bool")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ForecastAdapterError("forecast amount is not a decimal number") from exc
    if not amount.is_finite() or amount < 0:
        raise ForecastAdapterError("forecast amount must be finite and nonnegative")
    # Bound before conversion: avoid an enormous integer from e.g. '1e999999'.
    if amount > Decimal(limit).scaleb(-2):
        raise ForecastAdapterError("forecast amount exceeds the solver's per-row cents limit")
    try:
        # Multiplication must not first round a long decimal at the caller's
        # ambient precision; that could move a value across a half-cent tie.
        with localcontext(Context(prec=max(28, len(amount.as_tuple().digits) + 3))):
            return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise ForecastAdapterError("forecast amount cannot be rounded to integer cents") from exc


def _row_id(model_id: str, day: str) -> str:
    digest = hashlib.sha256(f"{model_id}\0{day}".encode("utf-8")).hexdigest()[:24]
    return f"forecast:{digest}:{day}"


def build_solve_request(
    base_request: dict,
    forecast: dict,
    *,
    request_currency: str,
    nonoverlap_evidence: str | None = None,
) -> tuple[dict, dict]:
    """Return a validated copied request and a separate provenance/evidence dict.

    ``forecast`` has exactly model_id, source, target, currency, context_end,
    experimental and days. Each of the 14 days has exactly date and amount.
    Amounts are nonnegative major currency units. The first forecast day must
    equal request.as_of, the last request.horizon_end, and context_end must be
    the preceding day. Unordered day rows are accepted and sorted.

    Require documented, nonempty nonoverlap_evidence for every target, including
    residual_outflow. Reject card_spending, whose payment timing requires a
    separate accounting adapter. No supplied row, candidate, lock or previous
    plan is changed. No cancellation candidates are generated.

    The solver dependency is imported only when this function is called. Make
    this worktree's backend available as ``app`` (see the executable example).
    Pydantic ValidationError propagates for invalid base/combined requests.
    """
    from app.schemas import CENTS_ABS, SolveRequest

    if not isinstance(base_request, dict):
        raise ForecastAdapterError("base_request must be a dict")
    SolveRequest.model_validate(base_request)
    required = {"model_id", "source", "target", "currency", "context_end", "days", "experimental"}
    if not isinstance(forecast, dict) or set(forecast) != required:
        raise ForecastAdapterError(f"forecast must contain exactly these fields: {sorted(required)}")
    model_id = _text(forecast["model_id"], "model_id")
    source = _text(forecast["source"], "source")
    target = _text(forecast["target"], "target")
    if target == "card_spending":
        raise ForecastAdapterError("card_spending cannot be appended as checking outflow without a payment-timing adapter")
    if target not in {"residual_outflow", "total_posted_outflow"}:
        raise ForecastAdapterError("unsupported forecast target")
    if type(forecast["experimental"]) is not bool:
        raise ForecastAdapterError("experimental must be a bool")
    currency = _currency(forecast["currency"], "forecast.currency")
    if currency != _currency(request_currency, "request_currency"):
        raise ForecastAdapterError("forecast and request currency must match; no FX conversion is performed")
    evidence = _text(nonoverlap_evidence, "nonoverlap_evidence")
    as_of = _iso(base_request["as_of"], "as_of")
    horizon_end = _iso(base_request["horizon_end"], "horizon_end")
    if (horizon_end - as_of).days != 13:
        raise ForecastAdapterError("request horizon must contain exactly 14 days")
    context_end = _iso(forecast["context_end"], "context_end")
    if (as_of - context_end).days != 1:
        raise ForecastAdapterError("context_end must be the day immediately before request as_of")
    days = forecast["days"]
    if not isinstance(days, list) or len(days) != 14:
        raise ForecastAdapterError("forecast must contain exactly 14 daily rows")
    normalized = []
    for row in days:
        if not isinstance(row, dict) or set(row) != {"date", "amount"}:
            raise ForecastAdapterError("each forecast day must contain exactly date and amount")
        day = _iso(row["date"], "forecast date")
        if not as_of <= day <= horizon_end:
            raise ForecastAdapterError("forecast date is outside the request horizon")
        normalized.append((day, _cents(row["amount"], CENTS_ABS)))
    if len({day for day, _ in normalized}) != 14:
        raise ForecastAdapterError("forecast dates must be unique and cover the full request horizon")
    normalized.sort()
    expected = [as_of + timedelta(days=i) for i in range(14)]
    if [day for day, _ in normalized] != expected:
        raise ForecastAdapterError("forecast dates must be consecutive without missing days")

    result = deepcopy(base_request)
    # Check both namespaces defensively, although the API permits a scheduled
    # row and candidate to share an ID. Never silently replace an existing row.
    existing_ids = {row["id"] for row in result["scheduled"]} | {
        candidate["id"] for candidate in result["candidates"]
    }
    forecast_rows = []
    for day, cents in normalized:
        day_text = day.isoformat()
        identifier = _row_id(model_id, day_text)
        if identifier in existing_ids:
            raise ForecastAdapterError(f"forecast ID collides with an existing ID: {identifier}")
        existing_ids.add(identifier)
        forecast_rows.append({
            "id": identifier,
            "date": day_text,
            "description": f"Forecast {target} ({model_id})",
            "amount_cents": -cents,
            "kind": "discretionary",
            "recurring": False,
        })
    result["scheduled"].extend(forecast_rows)
    SolveRequest.model_validate(result)
    sidecar = {
        "adapter_version": "1",
        "model_id": model_id,
        "source": source,
        "target": target,
        "currency": currency,
        "request_currency": request_currency,
        "context_end": forecast["context_end"],
        "experimental": forecast["experimental"],
        "nonoverlap_evidence": evidence,
        "nonoverlap_status": "caller_asserted; not independently verified by adapter",
        "rounding": "Decimal(str(amount)) * 100, ROUND_HALF_UP per day",
        "forecast_row_ids": [row["id"] for row in forecast_rows],
        "total_forecast_outflow_cents": sum(cents for _, cents in normalized),
        "interpretation": "Conditional point-estimate scenario; not a solvency probability or an instruction to spend.",
    }
    return result, sidecar

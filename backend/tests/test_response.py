"""The response shape, and whether it still matches what the browser expects.

`frontend/src/types.ts` and the pydantic models are two hand-maintained
descriptions of one contract. Nothing but this test stops them drifting, and
drift here is invisible until a field the UI reads arrives as undefined.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import schemas
from app.schemas import SolveRequest
from app.solver.solve import solve
from tests.fixtures.scenarios import SCENARIOS

TYPES_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types.ts"

# interface name in types.ts -> pydantic model
PAIRS = [
    ("ScheduledTxn", schemas.ScheduledTxn),
    ("Candidate", schemas.Candidate),
    ("SolveRequest", schemas.SolveRequest),
    ("PlanItem", schemas.PlanItem),
    ("CertificateItem", schemas.CertificateItem),
    ("Certificate", schemas.Certificate),
    ("BalanceRow", schemas.BalanceRow),
]


def ts_fields(name: str) -> set[str]:
    source = TYPES_TS.read_text()
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", source, re.S)
    assert match, f"{name} is no longer declared in types.ts"
    body = re.sub(r"//.*", "", match.group(1))
    return set(re.findall(r"^\s*(\w+)\??\s*:", body, re.M))


def py_fields(model) -> set[str]:
    return {f.alias or n for n, f in model.model_fields.items()}


@pytest.mark.skipif(not TYPES_TS.exists(), reason="frontend not present")
@pytest.mark.parametrize("name,model", PAIRS, ids=[p[0] for p in PAIRS])
def test_the_browser_and_the_server_describe_the_same_object(name, model):
    assert ts_fields(name) == py_fields(model)


@pytest.mark.skipif(not TYPES_TS.exists(), reason="frontend not present")
def test_the_response_envelope_matches():
    source = TYPES_TS.read_text()
    match = re.search(r"export interface SolveResponse \{(.*?)\n\}", source, re.S)
    assert match
    body = re.sub(r"//.*", "", match.group(1))
    # Top-level keys only; the nested literals are checked by the round-trip below.
    top = set(re.findall(r"^  (\w+)\??\s*:", body, re.M))
    assert top == py_fields(schemas.SolveResponse)


def test_a_response_round_trips_through_its_own_schema():
    """Serialising and re-validating catches a field the server can produce but
    the contract does not actually permit."""
    for name, raw in SCENARIOS.items():
        res = solve(SolveRequest.model_validate(raw))
        again = schemas.SolveResponse.model_validate(res.model_dump())
        assert again == res, name


def test_every_response_carries_the_full_envelope():
    for name, raw in SCENARIOS.items():
        payload = solve(SolveRequest.model_validate(raw)).model_dump()
        assert set(payload) == py_fields(schemas.SolveResponse), name
        assert len(payload["balances"]) == 14
        assert payload["meta"]["candidates_considered"] == 11
        assert isinstance(payload["meta"]["wall_ms"], float)


def test_money_never_leaves_as_a_float():
    """A cent that becomes 3179.9999999 in transit is a support ticket."""
    for raw in SCENARIOS.values():
        payload = solve(SolveRequest.model_validate(raw)).model_dump()
        for row in payload["balances"]:
            assert isinstance(row["baseline_cents"], int)
            assert isinstance(row["with_plan_cents"], int)
        for item in payload["plan"]:
            assert isinstance(item["freed_cents"], int)
        for item in payload["certificate"]["per_item"]:
            assert isinstance(item["worst_shortfall_cents"], int)
            assert isinstance(item["marginal_cents"], int)

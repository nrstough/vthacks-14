"""Which changes are actually on the table.

The lead-time rule is the one users feel: cancelling today does not stop
tomorrow's charge, and a plan that pretends otherwise is worse than no plan.
"""

from __future__ import annotations

import copy

import pytest

from app.schemas import SolveRequest
from app.solver.eligibility import split
from tests.fixtures import planted
from tests.fixtures.scenarios import SCENARIOS


def elig(raw: dict):
    return split(SolveRequest.model_validate(raw))


def with_locks(name: str, **locks):
    raw = copy.deepcopy(SCENARIOS[name])
    raw["locks"] = {"in": locks.get("pin", []), "out": locks.get("drop", [])}
    return raw


@pytest.mark.parametrize("lead,expected", [(3, True), (4, False)])
def test_the_lead_time_boundary_is_inclusive(lead, expected):
    """c_gym takes effect three days out. Three days' notice is enough; four is
    one day too many."""
    raw = copy.deepcopy(SCENARIOS["clears"])
    gym = next(c for c in raw["candidates"] if c["id"] == "c_gym")
    gym["lead_time_days"] = lead
    result = elig(raw)
    assert ("c_gym" in {c.id for c in result.free}) is expected


def test_removing_the_lead_time_rule_would_change_the_answer():
    """Counterfactual: if notice periods were ignored, c_late would be offered."""
    result = elig(planted.LEAD_TIME_BOUNDARY)
    assert {c.id for c in result.free} == {"c_ok"}
    no_notice = copy.deepcopy(planted.LEAD_TIME_BOUNDARY)
    for c in no_notice["candidates"]:
        c["lead_time_days"] = 0
    assert {c.id for c in elig(no_notice).free} == {"c_ok", "c_late"}


def test_a_ruled_out_change_is_never_offered():
    result = elig(with_locks("clears", drop=["c_gym"]))
    assert "c_gym" not in {c.id for c in result.free}
    assert "c_gym" not in {c.id for c in result.forced}
    assert result.considered == 10


def test_a_pinned_change_is_always_taken():
    result = elig(with_locks("clears", pin=["c_netflix"]))
    assert {c.id for c in result.forced} == {"c_netflix"}
    assert "c_netflix" not in {c.id for c in result.free}
    assert result.excluded_locked_in == []


def test_a_pinned_change_that_missed_its_notice_is_reported_not_silently_dropped():
    raw = copy.deepcopy(SCENARIOS["clears"])
    amzn = next(c for c in raw["candidates"] if c["id"] == "c_amzn")
    amzn["lead_time_days"] = 300
    raw["locks"] = {"in": ["c_amzn"], "out": []}
    result = elig(raw)
    assert result.forced == []
    assert result.excluded_locked_in == ["c_amzn"]


def test_pinning_two_changes_on_one_charge_keeps_the_lower_id():
    result = elig(planted.BOTH_PINNED_SAME_TXN)
    assert [c.id for c in result.forced] == ["c_a"]
    assert result.excluded_locked_in == ["c_b"]


def test_a_pinned_change_blocks_its_charge_from_being_changed_again():
    """Otherwise the pinned change and a free one could both hit one charge."""
    result = elig(planted.BOTH_PINNED_SAME_TXN)
    assert result.free == []


def test_excluded_pins_are_reported_in_a_stable_order():
    raw = copy.deepcopy(SCENARIOS["clears"])
    for c in raw["candidates"]:
        if c["id"] in {"c_amzn", "c_netflix", "c_gym"}:
            c["lead_time_days"] = 300
    raw["locks"] = {"in": ["c_netflix", "c_amzn", "c_gym"], "out": []}
    assert elig(raw).excluded_locked_in == ["c_amzn", "c_gym", "c_netflix"]


def test_the_count_of_changes_considered_excludes_the_unofferable():
    full = elig(SCENARIOS["clears"])
    assert full.considered == 11
    assert elig(with_locks("clears", drop=["c_gym", "c_amzn"])).considered == 9

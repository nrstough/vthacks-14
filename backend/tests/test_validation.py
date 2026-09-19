"""What the service refuses, and why it refuses loudly.

This is a money product, so silent coercion is the enemy: a float that rounds, a
date string that shifts by a year, an unknown field quietly dropped. Every case
below must be rejected with a path to the offending field, never absorbed.
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from app.schemas import SolveRequest
from tests.fixtures.scenarios import SCENARIOS


def mutate(**changes):
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw.update(changes)
    return raw


def first_error(raw: dict) -> tuple[tuple, str]:
    with pytest.raises(ValidationError) as exc:
        SolveRequest.model_validate(raw)
    err = exc.value.errors()[0]
    return err["loc"], err["type"]


def test_the_reference_requests_are_accepted():
    for name, raw in SCENARIOS.items():
        assert SolveRequest.model_validate(raw), name


@pytest.mark.parametrize(
    "value", [200.0, "200", True, 1e3, None], ids=["float", "string", "bool", "exponent", "null"]
)
def test_money_must_be_an_integer_number_of_cents(value):
    """A balance of 200.0 and a balance of 200 differ by nothing until they are
    compared against zero eighty times."""
    loc, _ = first_error(mutate(opening_balance_cents=value))
    assert loc == ("opening_balance_cents",)


def test_money_has_a_ceiling():
    """Unbounded input would reach the solver as a model it rejects outright."""
    loc, _ = first_error(mutate(opening_balance_cents=10**23))
    assert loc == ("opening_balance_cents",)


@pytest.mark.parametrize(
    "value",
    ["2026-9-1", "20260919", "2026-09-31", "2026-02-30", "2026-13-01",
     "2026-09-19T00:00:00", "19/09/2026", ""],
)
def test_dates_must_be_real_and_canonical(value):
    loc, _ = first_error(mutate(as_of=value))
    assert loc == ("as_of",)


def test_a_timestamp_is_not_a_date():
    """Read leniently, an epoch integer parses as a date a year out."""
    loc, _ = first_error(mutate(as_of=1758240000))
    assert loc == ("as_of",)


def test_the_horizon_must_run_forwards():
    loc, _ = first_error(mutate(horizon_end="2026-09-18"))
    assert loc == ("horizon_end",)


def test_the_horizon_has_a_limit():
    loc, _ = first_error(mutate(horizon_end="2028-09-19"))
    assert loc == ("horizon_end",)


def test_unknown_fields_are_rejected_rather_than_dropped():
    """A client sending `buffer` instead of `buffer_cents` should be told, not
    silently planned for with a cushion of zero."""
    loc, kind = first_error(mutate(buffer=2500))
    assert loc == ("buffer",)
    assert kind == "extra_forbidden"


def test_a_change_must_point_at_a_real_transaction():
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["candidates"][0]["target_txn_id"] = "t_nope"
    loc, _ = first_error(raw)
    assert loc == ("candidates",)


def test_a_change_cannot_free_more_than_the_charge_is_worth():
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["candidates"][0]["freed_cents"] = 999_999
    loc, _ = first_error(raw)
    assert loc == ("candidates",)


def test_a_change_must_land_inside_the_horizon():
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["candidates"][0]["effective_date"] = "2026-11-01"
    loc, _ = first_error(raw)
    assert loc == ("candidates",)


def test_ids_must_be_unique():
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["candidates"].append(copy.deepcopy(raw["candidates"][0]))
    assert first_error(raw)[0] == ("candidates",)

    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["scheduled"].append(copy.deepcopy(raw["scheduled"][0]))
    assert first_error(raw)[0] == ("scheduled",)


def test_a_deferral_must_say_when_the_money_comes_back():
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["candidates"][0]["action"] = "defer"
    loc, _ = first_error(raw)
    assert loc == ("candidates", 0, "recharge_date")


def test_money_cannot_come_back_before_it_was_freed():
    raw = copy.deepcopy(SCENARIOS["clears"])
    idx = next(i for i, c in enumerate(raw["candidates"]) if c["action"] == "defer")
    raw["candidates"][idx]["recharge_date"] = raw["candidates"][idx]["effective_date"]
    loc, _ = first_error(raw)
    assert loc == ("candidates", idx, "recharge_date")


def test_only_a_deferral_has_a_recharge_date():
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["candidates"][0]["recharge_date"] = "2026-09-30"
    loc, _ = first_error(raw)
    assert loc == ("candidates", 0, "recharge_date")


def test_locks_must_name_changes_that_exist():
    loc, _ = first_error(mutate(locks={"in": ["c_ghost"], "out": []}))
    assert loc == ("locks",)


def test_a_change_cannot_be_pinned_and_ruled_out_at_once():
    loc, _ = first_error(mutate(locks={"in": ["c_gym"], "out": ["c_gym"]}))
    assert loc == ("locks",)


@pytest.mark.parametrize("pain", [0, 6, -1])
def test_disruption_is_scored_one_to_five(pain):
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["candidates"][0]["pain"] = pain
    assert first_error(raw)[0] == ("candidates", 0, "pain")


def test_notice_periods_cannot_be_negative():
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["candidates"][0]["lead_time_days"] = -1
    assert first_error(raw)[0] == ("candidates", 0, "lead_time_days")


def test_the_cushion_cannot_be_negative():
    assert first_error(mutate(buffer_cents=-1))[0] == ("buffer_cents",)


def test_lists_have_ceilings():
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["candidates"] = raw["candidates"] * 20
    assert first_error(raw)[0] == ("candidates",)


def test_legal_oddities_are_accepted():
    """Not everything unusual is wrong, and refusing real data is its own bug."""
    # A cushion larger than the balance is the whole point of the product.
    assert SolveRequest.model_validate(mutate(buffer_cents=10_000_000))
    # Income can be negative — a clawback is still an income row.
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["scheduled"][7]["amount_cents"] = -100
    assert SolveRequest.model_validate(raw)
    # A change can free nothing: an annual plan cancelled mid-cycle is already paid.
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["candidates"][0]["freed_cents"] = 0
    assert SolveRequest.model_validate(raw)
    # A previously shown change that no longer exists still counts against churn.
    assert SolveRequest.model_validate(mutate(previous_plan=["c_vanished"]))


def test_the_derived_bound_still_covers_everything_the_input_limits_allow():
    """The ceiling on derived figures was computed from the input caps. Nothing
    in the code ties the two together, so raising a cap would silently put the
    500 back. This is that tie."""
    from app.schemas import CENTS_ABS, DERIVED_CENTS_ABS, MAX_N, MAX_SCHED, MAX_T

    worst_daily_balance = CENTS_ABS * (1 + MAX_SCHED + MAX_N)
    worst_running_total = worst_daily_balance * MAX_T
    assert DERIVED_CENTS_ABS >= worst_running_total, (
        "an input cap grew past what the derived bound covers; a legal request "
        "would now be rejected by the server's own response model"
    )
    assert DERIVED_CENTS_ABS < 2**63 - 1, "must stay inside the solver's integer range"


def test_a_deferral_with_the_recharge_date_left_out_entirely_is_rejected():
    """Omitting the key is not the same code path as sending null.

    A field validator does not run on a default, so a deferral missing its
    recharge date slipped through and became permanent savings: the money was
    freed and never came back, and the plan looked better than it was.
    """
    raw = copy.deepcopy(SCENARIOS["clears"])
    idx = next(i for i, c in enumerate(raw["candidates"]) if c["action"] == "defer")
    del raw["candidates"][idx]["recharge_date"]
    loc, _ = first_error(raw)
    assert loc == ("candidates", idx, "recharge_date")


def test_the_same_holds_when_the_recharge_date_is_explicitly_null():
    raw = copy.deepcopy(SCENARIOS["clears"])
    idx = next(i for i, c in enumerate(raw["candidates"]) if c["action"] == "defer")
    raw["candidates"][idx]["recharge_date"] = None
    loc, _ = first_error(raw)
    assert loc == ("candidates", idx, "recharge_date")


def test_leaving_it_out_is_still_fine_for_every_other_action():
    raw = copy.deepcopy(SCENARIOS["clears"])
    for c in raw["candidates"]:
        if c["action"] != "defer":
            c.pop("recharge_date", None)
    assert SolveRequest.model_validate(raw)

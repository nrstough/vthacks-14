"""The ledger walk.

Every number the product reports comes from here, so the questions are the
boring ones: is today's spending counted once, does money move on the right day,
and does a tie resolve to the earlier date rather than the later one.
"""

from __future__ import annotations

from app.schemas import SolveRequest
from app.solver.dates import day_range, to_iso
from app.solver.simulate import simulate
from tests.fixtures import planted
from tests.fixtures.planted import cand, req, txn


def trace_of(raw: dict, chosen: list[str] | None = None):
    r = SolveRequest.model_validate(raw)
    days = day_range(r.as_of, r.horizon_end)
    picked = [c for c in r.candidates if c.id in set(chosen or [])]
    return simulate(r, picked, days), days


def test_the_opening_balance_is_before_todays_transactions():
    """A charge dated today is applied once, on day zero — not folded into the
    opening balance as well."""
    raw = req(days_end="02", opening=10_000, buffer=0,
              scheduled=[txn("t_1", "01", -3_000)], candidates=[])
    trace, _ = trace_of(raw)
    assert trace.balances == [7_000, 7_000]


def test_income_raises_and_outflow_lowers():
    raw = req(days_end="03", opening=0, buffer=0,
              scheduled=[txn("t_in", "02", 5_000, "income"), txn("t_out", "03", -2_000)],
              candidates=[])
    trace, _ = trace_of(raw)
    assert trace.balances == [0, 5_000, 3_000]


def test_transactions_on_one_day_net_out_regardless_of_order():
    raw = req(days_end="02", opening=0, buffer=0,
              scheduled=[txn("t_a", "02", -4_000), txn("t_b", "02", 1_000, "income"),
                         txn("t_c", "02", -500)],
              candidates=[])
    trace, _ = trace_of(raw)
    assert trace.balances == [0, -3_500]


def test_rows_outside_the_horizon_are_ignored():
    raw = req(days_end="02", opening=1_000, buffer=0,
              scheduled=[txn("t_later", "20", -9_000)], candidates=[])
    trace, _ = trace_of(raw)
    assert trace.balances == [1_000, 1_000]


def test_a_change_frees_money_on_the_day_it_takes_effect():
    trace, _ = trace_of(planted.TIER3_EVERYTHING, ["c_a"])
    assert trace.balances == [4_000, -6_000, -6_000]


def test_a_deferral_hands_the_money_back_on_its_recharge_day():
    raw = req(days_end="04", opening=0, buffer=0,
              scheduled=[txn("t_1", "02", -5_000)],
              candidates=[cand("c_a", "t_1", 5_000, "01", recharge="03")])
    trace, _ = trace_of(raw, ["c_a"])
    assert trace.balances == [5_000, 0, -5_000, -5_000]


def test_a_deferral_past_the_horizon_never_hands_it_back():
    trace, _ = trace_of(planted.DEFER_PAST_HORIZON, ["c_a"])
    assert trace.balances == [5_000, 0, 0]


def test_the_worst_day_is_the_first_of_equally_bad_ones():
    trace, days = trace_of(planted.TWO_EQUAL_DIPS)
    assert trace.balances == [0, -5_000, 0, -5_000]
    assert trace.worst_shortfall == 5_000
    assert to_iso(trace.worst_shortfall_date) == "2026-03-02"
    assert to_iso(trace.first_below_zero_date) == "2026-03-02"
    assert trace.days_below_zero == 2
    assert to_iso(days[trace.tightest_date_index]) == "2026-03-02"


def test_the_deadline_can_be_earlier_than_the_deepest_day():
    raw = req(days_end="04", opening=0, buffer=0,
              scheduled=[txn("t_1", "02", -1_000), txn("t_2", "04", -9_000)], candidates=[])
    trace, _ = trace_of(raw)
    assert to_iso(trace.first_below_zero_date) == "2026-03-02"
    assert to_iso(trace.worst_shortfall_date) == "2026-03-04"
    assert trace.worst_shortfall == 10_000


def test_cushion_exposure_counts_every_day_it_is_short():
    raw = req(days_end="03", opening=1_000, buffer=5_000,
              scheduled=[txn("t_1", "02", -1_000)], candidates=[])
    trace, _ = trace_of(raw)
    # short by 4_000 on day one, then 5_000 on each of the other two days
    assert trace.balances == [1_000, 0, 0]
    assert trace.below_buffer_exposure == 4_000 + 5_000 + 5_000
    assert trace.min_balance == 0


def test_a_balance_that_never_dips_reports_no_shortfall():
    raw = req(days_end="03", opening=10_000, buffer=0, scheduled=[], candidates=[])
    trace, _ = trace_of(raw)
    assert (trace.worst_shortfall, trace.days_below_zero) == (0, 0)
    assert trace.worst_shortfall_date is None
    assert trace.first_below_zero_date is None

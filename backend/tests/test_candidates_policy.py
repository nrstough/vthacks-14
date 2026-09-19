"""What the generator offers, and what it refuses to offer.

Most of the filters here are the kind that fail silently when removed — the row
still produces a candidate, the candidate still validates, and the only symptom
is a suggestion nobody should have been given. So each filter is tested with the
case that must be dropped *and* the neighbouring case that must survive.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.candidates import generate
from app.candidates.generator import _candidate_id
from app.candidates.lexicon import PROTECTED
from app.schemas import (
    CENTS_ABS,
    ID_RE,
    MAX_FREE,
    MAX_N,
    CandidatesRequest,
    SolveRequest,
)
from app.solver.dates import money
from app.solver.eligibility import split
from app.solver.wording import BANNED
from tests.fixtures.accounts import windows
from tests.fixtures.scenarios import AS_OF, HORIZON_END, SCHEDULED

import re

AS = "2026-09-19"
END = "2026-10-02"

JUDGMENTAL = ("waste", "unnecessary", "frivolous", "afford")


def row(tid, day, description, cents, kind="discretionary", recurring=False):
    return {
        "id": tid,
        "date": day,
        "description": description,
        "amount_cents": cents,
        "kind": kind,
        "recurring": recurring,
    }


def payday(tid, day, cents=50_000):
    return row(tid, day, "HARRIS TEETER PAYROLL", cents, kind="income", recurring=True)


def gen(scheduled, as_of=AS, horizon_end=END, limit=MAX_FREE):
    return generate(
        CandidatesRequest.model_validate(
            {"as_of": as_of, "horizon_end": horizon_end, "scheduled": scheduled, "limit": limit}
        )
    )


def ids(res):
    return [c.id for c in res.candidates]


# ---------------------------------------------------------------- pre-filter


def test_an_income_row_is_never_a_candidate_however_it_reads():
    # HARRIS TEETER PAYROLL classifies as groceries: only the kind saves it.
    res = gen([payday("t_pay", "2026-09-20")])
    assert res.candidates == []
    assert res.meta.rows_considered == 0


def test_a_negative_income_row_is_still_income():
    res = gen([row("t_claw", "2026-09-20", "PAYROLL ADJUSTMENT", -5_000, kind="income")])
    assert res.candidates == []
    assert res.meta.rows_considered == 0


def test_a_refund_is_not_a_charge():
    res = gen([row("t_ref", "2026-09-20", "KROGER #382", 4_000)])
    assert res.candidates == []


def test_a_zero_amount_row_is_not_a_charge():
    assert gen([row("t_zero", "2026-09-20", "KROGER #382", 0)]).candidates == []


def test_a_charge_before_the_window_is_not_considered():
    assert gen([row("t_old", "2026-09-18", "KROGER #382", -4_000)]).meta.rows_considered == 0


def test_a_charge_after_the_window_is_not_considered():
    assert gen([row("t_late", "2026-10-03", "KROGER #382", -4_000)]).meta.rows_considered == 0


@pytest.mark.parametrize("day", [AS, END])
def test_both_ends_of_the_window_are_inside_it(day):
    res = gen([row("t_edge", day, "DOORDASH*CHIPOTLE", -3_000)])
    assert ids(res) == ["t_edge.skip"]


# ------------------------------------------------------------------ protected


@pytest.mark.parametrize(
    ("description", "category"),
    [
        ("CHASE CARD EPAY 8812", "card_payment"),
        ("MARKET ST PROPERTIES LLC", "housing"),
        ("NELNET STUDENT LOAN", "loan"),
        ("GEICO INSURANCE PMT", "insurance"),
        ("DOMINION ENERGY", "utilities"),
        ("VERIZON WIRELESS PMT", "phone"),
        ("CVS PHARMACY #4417", "medical"),
        ("VIRGINIA TECH BURSAR", "tuition"),
        ("ZELLE TO J SMITH", "transfer"),
        ("ATM WITHDRAWAL 0042", "atm_cash"),
    ],
)
def test_a_protected_charge_is_reported_and_never_offered(description, category):
    assert category in PROTECTED
    res = gen([row("t_p", "2026-09-22", description, -20_000, kind="bill")])
    assert res.candidates == []
    assert res.meta.protected == ["t_p"]
    assert res.meta.not_actionable == []


def test_the_card_payment_is_never_offered_even_at_the_minimum():
    # Nathan's call: paying only the minimum is a change this product will not
    # be the one to suggest.
    res = gen(SCHEDULED, AS_OF, HORIZON_END, limit=MAX_N)
    assert all(c.target_txn_id != "t_card" for c in res.candidates)
    assert "t_card" in res.meta.protected


def test_an_unrecognised_bill_is_protected_and_flagged():
    res = gen([row("t_u", "2026-09-22", "QUARRY LN ASSOC 4412", -9_000, kind="bill")])
    assert res.candidates == []
    assert res.meta.protected == ["t_u"]
    assert res.meta.unrecognised == ["t_u"]


def test_an_unrecognised_discretionary_charge_is_offered_but_flagged():
    res = gen([row("t_u", "2026-09-22", "BLACKSBURG SUNDRIES 77", -4_000)])
    assert ids(res) == ["t_u.skip"]
    assert res.candidates[0].pain == 3
    assert res.candidates[0].label == "Skip this charge"
    assert res.meta.unrecognised == ["t_u"]
    assert res.meta.protected == []


# ------------------------------------------------------------------- recharge


def test_a_deferral_needs_a_payday_to_come_back_on():
    res = gen([row("t_gas", "2026-09-23", "SHELL OIL 57442891", -4_120)])
    assert ids(res) == ["t_gas.downgrade"]  # the defer is dropped, the trim survives


def test_a_deferral_lands_on_the_next_payday_after_the_charge():
    res = gen([
        row("t_gas", "2026-09-23", "SHELL OIL 57442891", -4_120),
        payday("t_p1", "2026-09-25"),
        payday("t_p2", "2026-09-30"),
    ])
    defer = next(c for c in res.candidates if c.action == "defer")
    assert defer.recharge_date == "2026-09-25"


def test_a_payday_on_the_day_of_the_charge_is_not_late_enough():
    res = gen([
        row("t_gas", "2026-09-23", "SHELL OIL 57442891", -4_120),
        payday("t_same", "2026-09-23"),
        payday("t_next", "2026-09-26"),
    ])
    defer = next(c for c in res.candidates if c.action == "defer")
    assert defer.recharge_date == "2026-09-26"


def test_a_payday_past_the_horizon_cannot_be_a_recharge_date():
    # Money that returns after the window looks exactly like money saved.
    res = gen([
        row("t_gas", "2026-09-23", "SHELL OIL 57442891", -4_120),
        payday("t_p", "2026-10-10"),
    ])
    assert all(c.action != "defer" for c in res.candidates)


def test_a_clawback_is_not_a_payday():
    res = gen([
        row("t_gas", "2026-09-23", "SHELL OIL 57442891", -4_120),
        row("t_claw", "2026-09-25", "PAYROLL ADJUSTMENT", -3_000, kind="income"),
    ])
    assert all(c.action != "defer" for c in res.candidates)


def test_every_deferral_anywhere_comes_back_after_it_leaves():
    for win in windows(300):
        for c in generate(CandidatesRequest.model_validate(win)).candidates:
            if c.action == "defer":
                assert c.recharge_date is not None
                assert c.recharge_date > c.effective_date
                assert c.recharge_date <= win["horizon_end"]


# -------------------------------------------------------------------- amounts


@pytest.mark.parametrize(
    ("cents", "expected"),
    [(1, None), (2, None), (3, 1), (99, 34), (100, 35), (101, 35), (6418, 2246)],
)
def test_a_grocery_trim_frees_thirty_five_percent_floored(cents, expected):
    res = gen([row("t_k", "2026-09-21", "KROGER #382", -cents)])
    trim = next((c for c in res.candidates if c.action == "downgrade"), None)
    if expected is None:
        assert trim is None  # a change that frees nothing is not a change
    else:
        assert trim is not None and trim.freed_cents == expected


@pytest.mark.parametrize(("cents", "expected"), [(1, None), (2, 1), (3, 1), (4120, 2060)])
def test_a_half_tank_frees_half_floored(cents, expected):
    res = gen([row("t_s", "2026-09-23", "SHELL OIL 57442891", -cents)])
    half = next((c for c in res.candidates if c.action == "downgrade"), None)
    assert (half.freed_cents if half else None) == expected


def test_a_change_never_frees_more_than_the_charge_is_worth():
    for win in windows(300):
        amounts = {t["id"]: abs(t["amount_cents"]) for t in win["scheduled"]}
        for c in generate(CandidatesRequest.model_validate(win)).candidates:
            assert 1 <= c.freed_cents <= amounts[c.target_txn_id]


# ------------------------------------------------------------------ lead time


def test_a_change_with_just_enough_notice_is_offered():
    res = gen([row("t_gym", "2026-09-22", "PLANET FIT CLUB FEES", -3_499, kind="bill")])
    assert ids(res) == ["t_gym.cancel"]  # three days' notice, three days available


def test_a_change_one_day_short_of_its_notice_is_not_offered():
    res = gen([row("t_gym", "2026-09-21", "PLANET FIT CLUB FEES", -3_499, kind="bill")])
    assert res.candidates == []
    assert res.meta.not_actionable == ["t_gym"]


def test_the_demo_cannot_cancel_spotify_in_time():
    res = gen(SCHEDULED, AS_OF, HORIZON_END, limit=MAX_N)
    assert all(c.target_txn_id != "t_spotify" for c in res.candidates)
    assert "t_spotify" in res.meta.not_actionable


# ------------------------------------------------------------------------ ids


def test_an_id_says_what_it_is():
    assert _candidate_id("t_gym", "cancel") == "t_gym.cancel"
    assert _candidate_id("t_k", "downgrade") == "t_k.downgrade"


@pytest.mark.parametrize("length", [1, 40, 54, 55, 64])
def test_an_id_is_always_legal_however_long_the_transaction_id(length):
    tid = "t" + "x" * (length - 1)
    res = gen([row(tid, "2026-09-22", "DOORDASH*CHIPOTLE", -3_000)])
    cid = res.candidates[0].id
    assert len(cid) <= 64 and re.match(ID_RE, cid)


def test_two_transactions_sharing_a_long_prefix_get_different_ids():
    prefix = "t_" + "a" * 58
    res = gen([
        row(prefix + "01", "2026-09-22", "DOORDASH*CHIPOTLE", -3_000),
        row(prefix + "02", "2026-09-22", "DOORDASH*CHIPOTLE", -3_000),
    ])
    assert len(set(ids(res))) == 2


def test_two_thousand_transactions_sharing_a_prefix_all_get_distinct_ids():
    # 60-char ids: the first 40 characters are identical for every row, so
    # uniqueness rests entirely on the digest.
    prefix = "t_" + "b" * 38
    scheduled = [
        row(f"{prefix}{i:020d}", "2026-09-22", "DOORDASH*CHIPOTLE", -3_000) for i in range(2000)
    ]
    res = gen(scheduled, limit=MAX_N)
    assert len({c.id for c in res.candidates}) == len(res.candidates)


def test_the_same_account_asked_twice_gets_the_same_ids():
    # Locks and the previously-shown plan travel as ids; a fresh id on every call
    # would silently drop every override the user had set.
    first = gen(SCHEDULED, AS_OF, HORIZON_END, limit=MAX_N)
    second = gen(SCHEDULED, AS_OF, HORIZON_END, limit=MAX_N)
    assert ids(first) == ids(second)


def test_adding_an_unrelated_row_does_not_renumber_anything():
    before = gen(SCHEDULED, AS_OF, HORIZON_END, limit=MAX_N)
    after = gen(
        [*SCHEDULED, row("t_new", "2026-09-26", "STARBUCKS #0714", -500)],
        AS_OF, HORIZON_END, limit=MAX_N,
    )
    assert set(ids(before)) < set(ids(after))


# --------------------------------------------------------------------- labels


def test_no_two_changes_on_screen_read_the_same():
    for win in windows(300):
        labels = [c.label for c in generate(CandidatesRequest.model_validate(win)).candidates]
        assert len(labels) == len(set(labels))


def test_the_same_shop_on_two_days_is_told_apart_by_date():
    res = gen([
        row("t_a", "2026-09-22", "DOORDASH*CHIPOTLE", -3_000),
        row("t_b", "2026-10-01", "DOORDASH*PANERA", -2_840),
    ])
    assert sorted(c.label for c in res.candidates) == [
        "Skip the DoorDash order on Oct 1",
        "Skip the DoorDash order on Sep 22",
    ]


def test_two_charges_alike_in_every_visible_way_still_read_differently():
    res = gen([
        row("t_a", "2026-09-22", "DOORDASH*CHIPOTLE", -3_000),
        row("t_b", "2026-09-22", "DOORDASH*CHIPOTLE", -3_000),
    ])
    assert len({c.label for c in res.candidates}) == 2


def test_a_label_never_quotes_the_transaction_id():
    # An id is caller text, and labels reach the certificate sentence.
    res = gen([
        row("guaranteed_1", "2026-09-22", "DOORDASH*CHIPOTLE", -3_000),
        row("guaranteed_2", "2026-09-22", "DOORDASH*CHIPOTLE", -3_000),
    ])
    for c in res.candidates:
        assert "guaranteed" not in c.label.lower()


def test_a_label_never_quotes_the_merchant_string():
    res = gen([row("t_g", "2026-09-22", "GUARANTEED AUTO PROTECTION", -4_000)])
    c = res.candidates[0]
    assert c.label == "Skip this charge"
    assert "GUARANTEED AUTO PROTECTION" in c.detail


def test_no_label_says_anything_this_product_never_says():
    for win in windows(300):
        for c in generate(CandidatesRequest.model_validate(win)).candidates:
            lowered = c.label.lower()
            for word in BANNED:
                assert word not in lowered
            for word in JUDGMENTAL:
                assert word not in lowered
            assert "None" not in c.label
            assert "$-" not in c.label
            assert c.label.strip() == c.label and c.label
            assert not c.label.endswith(".")


def test_a_brandless_merchant_gets_a_label_that_does_not_invent_one():
    res = gen([row("t_t", "2026-09-22", "WATER ST TAVERN", -4_000)])
    assert res.candidates[0].label == "Skip the meal out"


# -------------------------------------------------------------------- details


def test_the_detail_shows_the_charge_as_the_statement_shows_it():
    res = gen([row("t_k", "2026-09-21", "KROGER #382", -6_418)])
    trim = next(c for c in res.candidates if c.action == "downgrade")
    assert trim.detail == "KROGER #382, $64.18 down to $41.72"
    assert money(6418 - 2246) in trim.detail


def test_a_recurring_charge_is_called_recurring_and_not_monthly():
    # The schema carries a flag, not a cadence.
    res = gen([row("t_n", "2026-09-29", "NETFLIX.COM", -2_299, kind="bill", recurring=True)])
    assert res.candidates[0].detail == "NETFLIX.COM, $22.99 recurring"


def test_a_one_off_charge_is_not_called_recurring():
    res = gen([row("t_d", "2026-09-22", "DOORDASH*CHIPOTLE", -3_180)])
    assert res.candidates[0].detail == "DOORDASH*CHIPOTLE, $31.80"


def test_only_a_deferral_carries_a_recharge_date():
    for win in windows(300):
        for c in generate(CandidatesRequest.model_validate(win)).candidates:
            assert (c.recharge_date is not None) == (c.action == "defer")


# ----------------------------------------------------------- multi-occurrence


def test_a_subscription_billed_twice_in_the_window_is_two_changes():
    res = gen(
        [
            row("t_n1", "2026-09-29", "NETFLIX.COM", -2_299, kind="bill", recurring=True),
            row("t_n2", "2026-10-29", "NETFLIX.COM", -2_299, kind="bill", recurring=True),
        ],
        as_of=AS, horizon_end="2026-11-02",
    )
    assert len(res.candidates) == 2
    assert len({c.id for c in res.candidates}) == 2
    assert len({c.label for c in res.candidates}) == 2
    assert all(c.freed_cents == 2_299 for c in res.candidates)


# --------------------------------------------------------------------- golden

GOLDEN: tuple[tuple[str, str, int, str, str | None, int, int], ...] = (
    ("t_kroger_1.defer", "defer", 6418, "2026-09-21", "2026-09-25", 0, 4),
    ("t_kroger_1.downgrade", "downgrade", 2246, "2026-09-21", None, 0, 3),
    ("t_dd_chipotle.skip", "skip", 3180, "2026-09-22", None, 0, 2),
    ("t_gym.cancel", "cancel", 3499, "2026-09-22", None, 3, 1),
    ("t_shell.defer", "defer", 4120, "2026-09-23", "2026-09-25", 0, 3),
    ("t_shell.downgrade", "downgrade", 2060, "2026-09-23", None, 0, 3),
    ("t_starbucks.skip", "skip", 745, "2026-09-24", None, 0, 1),
    ("t_amzn.skip", "skip", 5230, "2026-09-27", None, 1, 2),
    ("t_kroger_2.defer", "defer", 7105, "2026-09-28", "2026-10-02", 0, 4),
    ("t_kroger_2.downgrade", "downgrade", 2486, "2026-09-28", None, 0, 3),
    ("t_netflix.cancel", "cancel", 2299, "2026-09-29", None, 2, 1),
    ("t_shell_2.defer", "defer", 3860, "2026-09-30", "2026-10-02", 0, 3),
    ("t_shell_2.downgrade", "downgrade", 1930, "2026-09-30", None, 0, 3),
    ("t_dd_panera.skip", "skip", 2840, "2026-10-01", None, 0, 2),
)


def test_the_demo_account_produces_exactly_the_documented_set():
    # Worked by hand in docs/features/candidates.md before this code existed.
    res = gen(SCHEDULED, AS_OF, HORIZON_END)
    actual = tuple(
        (c.id, c.action, c.freed_cents, c.effective_date, c.recharge_date, c.lead_time_days, c.pain)
        for c in res.candidates
    )
    assert actual == GOLDEN


def test_the_demo_account_reports_what_it_did_with_every_row():
    res = gen(SCHEDULED, AS_OF, HORIZON_END)
    assert res.meta.rows_considered == 13
    assert res.meta.protected == ["t_card", "t_verizon"]
    assert res.meta.unrecognised == []
    assert res.meta.not_actionable == ["t_spotify"]
    assert res.meta.truncated is False


def test_the_demo_account_stays_inside_the_exhaustive_engine_s_reach():
    # With no locks every generated candidate is free, so this is exactly the
    # quantity engine_brute refuses above.
    res = gen(SCHEDULED, AS_OF, HORIZON_END)
    req = SolveRequest.model_validate({
        "as_of": AS_OF, "horizon_end": HORIZON_END, "opening_balance_cents": 20_000,
        "buffer_cents": 2_500, "scheduled": SCHEDULED,
        "candidates": [c.model_dump() for c in res.candidates],
        "locks": {"in": [], "out": []}, "previous_plan": [],
    })
    assert len(split(req).free) <= MAX_FREE


# ------------------------------------------------------------------ meta


def _dispositions(win, res):
    considered = {
        t["id"]
        for t in win["scheduled"]
        if t["kind"] != "income"
        and t["amount_cents"] < 0
        and win["as_of"] <= t["date"] <= win["horizon_end"]
    }
    offered = {c.target_txn_id for c in res.candidates}
    protected = set(res.meta.protected)
    not_actionable = set(res.meta.not_actionable)
    cut = considered - (protected | not_actionable | offered)
    return considered, offered, protected, not_actionable, set(res.meta.unrecognised), cut


def test_every_row_the_generator_looked_at_is_accounted_for():
    for win in windows(300):
        res = generate(CandidatesRequest.model_validate(win))
        considered, offered, protected, na, unrecognised, cut = _dispositions(win, res)
        assert res.meta.rows_considered == len(considered)
        assert not (protected & na) and not (protected & offered) and not (na & offered)
        assert not (unrecognised & na)
        assert unrecognised <= (protected | offered | cut)
        assert protected | na | offered | cut == considered
        if not res.meta.truncated:
            assert cut == set()


def test_a_row_that_keeps_one_alternative_is_still_offered_when_truncated():
    # One grocery row has two alternatives; a limit of one cuts the second but
    # the row itself is still on the table.
    res = gen([row("t_k", "2026-09-21", "KROGER #382", -6_418), payday("t_p", "2026-09-25")], limit=1)
    assert res.meta.truncated is True
    assert [c.target_txn_id for c in res.candidates] == ["t_k"]
    assert res.meta.not_actionable == [] and res.meta.protected == []


def test_a_row_cut_entirely_by_the_limit_is_still_reported_as_unrecognised():
    res = gen([
        row("t_a", "2026-09-21", "BLACKSBURG SUNDRIES 77", -4_000),
        row("t_b", "2026-09-22", "BLACKSBURG SUNDRIES 77", -3_000),
    ], limit=1)
    assert res.meta.truncated is True
    assert len(res.candidates) == 1
    assert res.meta.unrecognised == ["t_a", "t_b"]
    assert res.meta.not_actionable == [] and res.meta.protected == []


# ------------------------------------------------------------- rank and cap


def _many(n, description="KROGER #382"):
    scheduled = [payday("t_pay", "2026-10-02")]
    start = date.fromisoformat(AS)
    for i in range(n):
        day = start + timedelta(days=i % 12)
        scheduled.append(row(f"t_{i:04d}", day.isoformat(), description, -6_418))
    return scheduled


def test_the_cap_spreads_across_transactions_rather_than_stacking_on_a_few():
    res = gen(_many(100), limit=60)
    assert len(res.candidates) == 60
    assert len({c.target_txn_id for c in res.candidates}) == 60


def test_the_default_limit_is_what_every_fallback_can_still_answer():
    res = gen(_many(100))
    assert len(res.candidates) == MAX_FREE == 18
    assert res.meta.truncated is True


def test_two_thousand_rows_still_respect_the_limit():
    # _many adds a payday of its own, and MAX_SCHED counts every row.
    assert len(gen(_many(1999)).candidates) == 18
    assert len(gen(_many(1999), limit=60).candidates) == 60


def test_the_order_rows_arrive_in_does_not_change_the_answer():
    rng = random.Random(20260919)
    baseline = gen(SCHEDULED, AS_OF, HORIZON_END, limit=MAX_N)
    for _ in range(20):
        shuffled = list(SCHEDULED)
        rng.shuffle(shuffled)
        assert ids(gen(shuffled, AS_OF, HORIZON_END, limit=MAX_N)) == ids(baseline)


def test_the_output_is_ordered_the_way_the_plan_is():
    res = gen(SCHEDULED, AS_OF, HORIZON_END, limit=MAX_N)
    assert ids(res) == [c.id for c in sorted(res.candidates, key=lambda c: (c.effective_date, c.id))]


# --------------------------------------------------------------- determinism

_DUMP = """
import json, sys
sys.path.insert(0, {backend!r})
from app.schemas import CandidatesRequest
from app.candidates import generate
from tests.fixtures.accounts import windows
out = []
for w in windows(20):
    res = generate(CandidatesRequest.model_validate(w))
    out.append([[c.id, c.label, c.detail, c.freed_cents] for c in res.candidates])
print(json.dumps(out, sort_keys=True))
"""


def _dump_with_seed(seed: str) -> str:
    backend = str(Path(__file__).resolve().parents[1])
    proc = subprocess.run(
        [sys.executable, "-c", _DUMP.format(backend=backend)],
        capture_output=True, text=True, timeout=180,
        env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": seed},
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return proc.stdout


def test_two_processes_with_different_hash_seeds_produce_the_same_words():
    # A set anywhere in the lexicon would let the matched phrase — and so the
    # brand name on screen — vary between processes. One process cannot see it.
    assert _dump_with_seed("0") == _dump_with_seed("1")


# ------------------------------------------------------------------- limits


def test_an_account_at_every_cap_still_answers():
    scheduled = [payday("t_pay", "2026-10-02", CENTS_ABS)]
    start = date.fromisoformat(AS)
    for i in range(1999):
        scheduled.append(
            row(f"t_{i:04d}", (start + timedelta(days=i % 14)).isoformat(),
                "KROGER #382", -CENTS_ABS)
        )
    res = gen(scheduled)
    assert len(res.candidates) == 18
    assert res.meta.truncated is True

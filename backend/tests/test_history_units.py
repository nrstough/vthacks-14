"""Calendar, money and payee-key units. A16/A5/A13 rest on these."""

from __future__ import annotations

import datetime

import pytest

from app.history import workdays
from app.history.money import (
    coefficient_of_variation,
    mean_cents,
    median_cents,
    trimmed_mean_cents,
)
from app.history.payee import payee_key

SAT = datetime.date(2026, 9, 19)
SUN = datetime.date(2026, 9, 20)
MON = datetime.date(2026, 9, 21)
FRI = datetime.date(2026, 9, 18)


def test_weekend_moves_income_forward_and_bills_back():
    # The directions are opposite ON PURPOSE. A bill taken on the Friday
    # before is money already gone; income credited on the Monday after is
    # money not yet there. One of these rounds cash into existence.
    assert workdays.previous_business_day(SAT) == FRI
    assert workdays.previous_business_day(SUN) == FRI
    assert workdays.next_business_day(SAT) == MON
    assert workdays.next_business_day(SUN) == MON
    assert workdays.previous_business_day(FRI) == FRI
    assert workdays.next_business_day(MON) == MON


@pytest.mark.parametrize(
    "start,months,expected",
    [
        ((2026, 1, 31), 1, (2026, 2, 28)),
        ((2028, 1, 31), 1, (2028, 2, 29)),
        ((2026, 12, 15), 1, (2027, 1, 15)),
        ((2026, 3, 31), -1, (2026, 2, 28)),
    ],
)
def test_add_months_clamps_and_crosses_the_year(start, months, expected):
    assert workdays.add_months(datetime.date(*start), months) == datetime.date(*expected)


def test_day_of_month_clamps_to_the_month_end():
    assert workdays.on_day_of_month(2026, 2, 31) == datetime.date(2026, 2, 28)
    assert workdays.on_day_of_month(2026, 7, 31) == datetime.date(2026, 7, 31)


def test_means_are_integer_cents_and_round_half_to_even():
    # Half-up would bias every tie upward, and these averages are repeated
    # across a horizon, so the bias would be real dollars.
    assert mean_cents([100, 101]) == 100
    assert mean_cents([101, 102]) == 102
    assert mean_cents([1999]) == 1999
    assert isinstance(mean_cents([1, 2]), int)


def test_median_of_an_even_count_is_the_middle_two():
    assert median_cents([100, 200, 300, 401]) == 250
    assert median_cents([5]) == 5
    assert median_cents([1, 2, 3]) == 2


def test_median_contains_an_outlier_that_the_mean_would_not():
    flat = [2500] * 7
    assert median_cents(flat + [90000]) == 2500
    assert mean_cents(flat + [90000]) > 12000


def test_trimmed_mean_only_trims_from_five_values_up():
    # At n=4 trimming averages two values and at n=3 it averages one, which
    # throws away more evidence than the outlier is worth.
    assert trimmed_mean_cents([100, 200, 300, 9000]) == mean_cents([100, 200, 300, 9000])
    assert trimmed_mean_cents([100, 200, 300, 400, 9000]) == 300


def test_cv_uses_the_absolute_mean_so_outflows_are_not_always_stable():
    # Signed amounts: a negative denominator would make every bill look
    # perfectly stable no matter how much it moved.
    assert coefficient_of_variation([-100, -110, -90]) == pytest.approx(
        coefficient_of_variation([100, 110, 90])
    )
    assert coefficient_of_variation([100]) == 0.0
    assert coefficient_of_variation([-1000, -5000]) > 0.5


def test_payee_key_groups_the_same_merchant_and_separates_others():
    assert payee_key("KROGER #382") == payee_key("KROGER 0417 W")
    assert payee_key("DOORDASH*CHIPOTLE 4821") == payee_key("DOORDASH*CHIPOTLE 9910")
    assert payee_key("KROGER #382") != payee_key("PUBLIX 114")


def test_payee_key_survives_a_description_of_only_digits():
    # Falling through to an empty key would collapse every such row into one
    # stream of unrelated charges.
    assert payee_key("123 456") != ""

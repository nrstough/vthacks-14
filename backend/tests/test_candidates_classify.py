"""Merchant strings to categories.

The table below is the point of this file. Every row in it is a descriptor of
the shape banks actually emit, and about a third are strings that a plausible
keyword list gets wrong in one direction or the other: `SAM'S CLUB` is not a
gym, `WATER ST TAVERN` is not a utility, `GAP INSURANCE` is not a shopping trip,
and `CORE POWER YOGA` is not the power company.
"""

from __future__ import annotations

import random

import pytest

from app.candidates.lexicon import (
    ENTRIES,
    PRIORITY,
    PROTECTED,
    UNKNOWN_CATEGORY,
    classify,
    normalise,
)
from app.candidates.policy import POLICY
from tests.fixtures.scenarios import SCHEDULED


@pytest.mark.parametrize(
    ("text", "tokens"),
    [
        ("KROGER #382", ("KROGER", "382")),
        ("kroger 0382", ("KROGER", "0382")),
        ("KROGER*382", ("KROGER", "382")),
        ("APPLE.COM/BILL", ("APPLE", "COM", "BILL")),
        ("GOLD'S GYM", ("GOLD", "S", "GYM")),
        ("DOORDASH*CHIPOTLE", ("DOORDASH", "CHIPOTLE")),
        ("  spaced   out  ", ("SPACED", "OUT")),
        ("", ()),
        ("   ", ()),
        ("☕☕☕", ()),
    ],
)
def test_normalise_splits_on_anything_that_is_not_a_letter_or_digit(text, tokens):
    assert normalise(text) == tokens


def test_the_same_merchant_spelled_four_ways_lands_in_one_category():
    # The tokens differ — only the category has to agree.
    spellings = ["KROGER #382", "kroger 0382", "KROGER*382", "KROGER"]
    assert len({normalise(s) for s in spellings}) > 1
    assert {classify(s).category for s in spellings} == {"groceries"}


@pytest.mark.parametrize("text", ["", "   ", "Café ☕", "☕", "—", "​"])
def test_a_description_with_nothing_to_match_is_unknown_not_an_error(text):
    assert classify(text).category == UNKNOWN_CATEGORY


MERCHANT_TABLE: tuple[tuple[str, str], ...] = (
    # The eight the risk review found, each with the category it must reach.
    ("SAM'S CLUB #6314", "groceries"),
    ("GAP INSURANCE PREMIUM", "insurance"),
    ("MARKET ST PROPERTIES LLC", "housing"),
    ("WATER ST TAVERN", "restaurant"),
    ("CORE POWER YOGA", "gym"),
    ("TARGET OPTICAL 118", "medical"),
    ("FUEL FITNESS", "gym"),
    ("GUARANTEED RATE", "housing"),
    # The demo account.
    ("SPOTIFY USA", "streaming"),
    ("KROGER #382", "groceries"),
    ("DOORDASH*CHIPOTLE", "food_delivery"),
    ("PLANET FIT CLUB FEES", "gym"),
    ("SHELL OIL 57442891", "fuel"),
    ("CHASE CARD EPAY 8812", "card_payment"),
    ("STARBUCKS #0714", "coffee"),
    ("HARRIS TEETER PAYROLL", "groceries"),
    ("VERIZON WIRELESS PMT", "phone"),
    ("AMZN MKTP US*2K41Z", "shopping"),
    ("NETFLIX.COM", "streaming"),
    ("DOORDASH*PANERA", "food_delivery"),
    # Priority: the broader category must not shadow the narrower one.
    ("UBER EATS", "food_delivery"),
    ("UBER TRIP 4A2K", "rideshare"),
    ("AMAZON PRIME VIDEO", "streaming"),
    ("APPLE CARD PAYMENT", "card_payment"),
    ("APPLE.COM/BILL", "streaming"),
    ("APPLE STORE R150", "shopping"),
    # Nothing should match these.
    ("GYMBOREE 4412", UNKNOWN_CATEGORY),
    ("GAP OUTLET 221", UNKNOWN_CATEGORY),
    ("BP#9876543", UNKNOWN_CATEGORY),
    ("SHELL SHACK", UNKNOWN_CATEGORY),
    ("BLACKSBURG SUNDRIES 77", UNKNOWN_CATEGORY),
    # Protected, each by a different route.
    ("DOMINION ENERGY", "utilities"),
    ("NELNET STUDENT LOAN", "loan"),
    ("VIRGINIA TECH BURSAR", "tuition"),
    ("ZELLE TO J SMITH", "transfer"),
    ("ATM WITHDRAWAL 0042", "atm_cash"),
    ("CVS PHARMACY #4417", "medical"),
    ("GEICO INSURANCE PMT", "insurance"),
    # Changeable, one per remaining category.
    ("ADOBE *CREATIVE CLD", "software"),
    ("AMC ONLINE 4421", "entertainment"),
    ("GREAT CLIPS #2201", "personal_care"),
    ("WAWA 8832", "fuel"),
)


@pytest.mark.parametrize(("description", "category"), MERCHANT_TABLE)
def test_merchant_strings_classify_the_way_a_person_would_read_them(description, category):
    assert classify(description).category == category


def test_a_three_letter_word_does_not_match_a_longer_one():
    assert classify("GYMBOREE").category == UNKNOWN_CATEGORY
    assert classify("GOLD'S GYM").category == "gym"


def test_the_longest_phrase_wins_at_equal_priority():
    # Checked on the display, not the category: APPLE COM BILL and APPLE MUSIC
    # are both streaming, so comparing categories would pass whichever won and
    # prove nothing about which phrase the matcher actually chose.
    assert classify("APPLE.COM/BILL").display == "Apple"
    assert classify("APPLE MUSIC 4412").display == "Apple Music"
    assert classify("UBER EATS").display == "Uber Eats"
    assert classify("UBER TRIP").display == "Uber"


def test_every_phrase_in_the_table_reaches_its_own_category():
    # A phrase can be listed and still be unreachable, shadowed by a broader one
    # in a category checked earlier. Then the row it was meant to protect falls
    # through to unknown, and an unknown discretionary row is offered as a skip.
    for category, _, phrases in ENTRIES:
        for phrase in phrases:
            assert classify(phrase).category == category, f"{phrase!r} is shadowed"


def test_protected_categories_are_all_checked_before_the_changeable_ones():
    assert PRIORITY[: len(PROTECTED)] == PROTECTED


def test_no_phrase_belongs_to_two_categories():
    owner: dict[tuple[str, ...], str] = {}
    for category, _, phrases in ENTRIES:
        for phrase in phrases:
            tokens = normalise(phrase)
            assert owner.get(tokens, category) == category, f"{phrase!r} is in two categories"
            owner[tokens] = category


def test_every_changeable_category_has_a_policy_and_every_protected_one_has_none():
    for category in PRIORITY:
        if category in PROTECTED:
            assert category not in POLICY
        else:
            assert category in POLICY


def test_protected_entries_carry_no_brand_name():
    for category, display, _ in ENTRIES:
        if category in PROTECTED:
            assert display is None, f"{category} carries a display name"


def test_classification_does_not_depend_on_the_order_it_is_asked():
    rng = random.Random(20260919)
    rows = list(MERCHANT_TABLE)
    expected = {d: classify(d).category for d, _ in rows}
    for _ in range(25):
        rng.shuffle(rows)
        for description, _ in rows:
            assert classify(description).category == expected[description]


def test_every_description_in_the_demo_account_is_recognised():
    # An unrecognised demo row would silently become a bare "Skip this charge",
    # or nothing at all, on the account the judges see.
    for txn in SCHEDULED:
        assert classify(txn["description"]).category != UNKNOWN_CATEGORY, txn["description"]

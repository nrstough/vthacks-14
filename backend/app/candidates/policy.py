"""What may be done about a charge, once its category is known.

A category maps to an ordered tuple of alternatives. Offering two — trim the
grocery run *or* push it past payday — is deliberate: both engines already
enforce at most one chosen change per transaction, so competing candidates are
legal input and the solver picks whichever produces the better plan.

The numbers that coincide with the shipped demo fixture (gym lead 3 pain 1,
delivery pain 2, coffee pain 1, shopping lead 1, grocery trim pain 3) are taken
from it on purpose: those were tuned by hand against a real screen.

Credit-card payments are absent from this table on purpose. Paying only the
minimum is a change a person can make, and this product will not be the thing
that suggests it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import get_args

from app.schemas import MAX_T, Action

from .lexicon import ENTRIES, PRIORITY, PROTECTED, UNKNOWN_CATEGORY


@dataclass(frozen=True)
class Alternative:
    action: str
    pct: int  # of the charge, floored to whole cents
    lead_time_days: int
    pain: int  # 1..5
    needs_payday: bool = False


POLICY: dict[str, tuple[Alternative, ...]] = {
    "streaming": (Alternative("cancel", 100, 2, 1),),
    "gym": (Alternative("cancel", 100, 3, 1),),
    "software": (Alternative("cancel", 100, 1, 2),),
    "food_delivery": (Alternative("skip", 100, 0, 2),),
    "coffee": (Alternative("skip", 100, 0, 1),),
    "restaurant": (Alternative("skip", 100, 0, 2),),
    "groceries": (Alternative("downgrade", 35, 0, 3), Alternative("defer", 100, 0, 4, True)),
    "fuel": (Alternative("defer", 100, 0, 3, True), Alternative("downgrade", 50, 0, 3)),
    "shopping": (Alternative("skip", 100, 1, 2),),
    "rideshare": (Alternative("skip", 100, 0, 3),),
    "entertainment": (Alternative("skip", 100, 0, 2),),
    "personal_care": (Alternative("skip", 100, 1, 2),),
}

# A row nothing matched, which the caller has already told us is discretionary.
# We offer to skip it and say nothing about what it is: the caller's own label is
# the whole of the evidence, and the screen shows that it was not recognised.
UNKNOWN_DISCRETIONARY: tuple[Alternative, ...] = (Alternative("skip", 100, 0, 3),)

# (category, action) -> (with a brand name, without one). The brand-less form is
# used when the phrase that matched was a generic noun — "TAVERN" tells us the
# charge is a meal out but not whose.
LABELS: dict[tuple[str, str], tuple[str, str | None]] = {
    ("streaming", "cancel"): ("Pause {brand} for a cycle", "Pause the subscription for a cycle"),
    ("gym", "cancel"): ("Cancel the gym membership", "Cancel the gym membership"),
    ("software", "cancel"): ("Cancel {brand}", "Cancel the subscription"),
    ("food_delivery", "skip"): ("Skip the {brand} order", "Skip the delivery order"),
    ("coffee", "skip"): ("Skip the coffee run", "Skip the coffee run"),
    ("restaurant", "skip"): ("Skip {brand}", "Skip the meal out"),
    ("groceries", "downgrade"): ("Trim the {date} grocery run", "Trim the {date} grocery run"),
    ("groceries", "defer"): (
        "Do the {date} grocery run after payday",
        "Do the {date} grocery run after payday",
    ),
    ("fuel", "defer"): ("Put off the gas fill to {recharge}", "Put off the gas fill to {recharge}"),
    ("fuel", "downgrade"): ("Half-fill the tank on {date}", "Half-fill the tank on {date}"),
    ("shopping", "skip"): ("Cancel the {brand} order", "Cancel the order"),
    ("rideshare", "skip"): ("Skip the {brand} ride", "Skip the ride"),
    ("entertainment", "skip"): ("Skip {brand}", "Skip the night out"),
    ("personal_care", "skip"): ("Skip the {brand} appointment", "Skip the appointment"),
    (UNKNOWN_CATEGORY, "skip"): ("Skip this charge", "Skip this charge"),
}


def _check() -> None:
    """Fail at import rather than at the first request that trips a gap."""
    actions = get_args(Action)
    changeable = tuple(c for c in PRIORITY if c not in PROTECTED)

    for category in changeable:
        if category not in POLICY:
            raise ValueError(f"{category} is changeable but has no policy")

    brandless: set[str] = {
        category for category, display, _ in ENTRIES if display is None and category in POLICY
    }

    for category, alternatives in {**POLICY, UNKNOWN_CATEGORY: UNKNOWN_DISCRETIONARY}.items():
        if category != UNKNOWN_CATEGORY and category in PROTECTED:
            raise ValueError(f"{category} is protected and must not have a policy")
        if len({a.action for a in alternatives}) != len(alternatives):
            raise ValueError(f"{category} offers the same action twice; their ids would collide")
        for a in alternatives:
            if a.action not in actions:
                raise ValueError(f"{category}: {a.action!r} is not a candidate action")
            if not 1 <= a.pct <= 100:
                raise ValueError(f"{category}/{a.action}: pct {a.pct} out of range")
            if not 1 <= a.pain <= 5:
                raise ValueError(f"{category}/{a.action}: pain {a.pain} out of range")
            if not 0 <= a.lead_time_days <= MAX_T:
                raise ValueError(f"{category}/{a.action}: lead time {a.lead_time_days} out of range")
            # Only a deferral comes back, and only a deferral needs a payday to
            # come back on. Letting these drift apart is how a deferral becomes
            # permanent savings.
            if (a.action == "defer") != a.needs_payday:
                raise ValueError(f"{category}/{a.action}: needs_payday must hold exactly for defer")
            key = (category, a.action)
            if key not in LABELS:
                raise ValueError(f"no label for {key}")
            with_brand, without_brand = LABELS[key]
            if "{brand}" in with_brand and category in brandless and without_brand is None:
                raise ValueError(f"{key} needs a brand-less label: some of its phrases have no brand")
            if without_brand is not None and "{brand}" in without_brand:
                raise ValueError(f"{key}: the brand-less label still names a brand")


_check()

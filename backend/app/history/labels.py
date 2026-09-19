"""Brand-free labels for imported rows.

A detected row is labelled from its lexicon CATEGORY, never from the merchant
brand the lexicon matched. `PAUSE NETFLIX FOR A CYCLE` in a candidate label
would carry the person's real payee into the solve request, the chat request
and any error body, which is exactly what importing a private statement must
not do. "Pause the streaming subscription for a cycle" says as much to the
person reading it and nothing to anyone else.
"""

from __future__ import annotations

from app.candidates.lexicon import PRIORITY, UNKNOWN_CATEGORY

CATEGORY_DISPLAY: dict[str, str] = {
    "card_payment": "credit card payment",
    "housing": "rent or mortgage",
    "loan": "loan payment",
    "insurance": "insurance premium",
    "utilities": "utility bill",
    "phone": "phone bill",
    "medical": "medical payment",
    "tuition": "tuition payment",
    "transfer": "transfer",
    "atm_cash": "cash withdrawal",
    "food_delivery": "food delivery",
    "rideshare": "rideshare",
    "coffee": "coffee",
    "groceries": "groceries",
    "fuel": "fuel",
    "restaurant": "restaurant",
    "streaming": "streaming subscription",
    "gym": "gym membership",
    "software": "software subscription",
    "shopping": "shopping",
    "entertainment": "entertainment",
    "personal_care": "personal care",
    UNKNOWN_CATEGORY: "recurring charge",
}


def _check() -> None:
    """Every lexicon category must have a display name, checked at import.

    The same shape as `policy._check`: a category added to the lexicon without
    a name here would otherwise silently render every one of that person's
    bills as "recurring charge", and the untick list becomes unusable without
    anything failing.
    """
    missing = [c for c in PRIORITY if c not in CATEGORY_DISPLAY]
    if missing:
        raise ValueError(f"categories with no display name: {missing}")


_check()

CADENCE_WORDS = {
    "weekly": "weekly",
    "biweekly": "every two weeks",
    "semimonthly": "twice a month",
    "monthly": "monthly",
}


def stream_label(kind: str, category: str, cadence: str) -> str:
    if kind == "income":
        return f"Income ({CADENCE_WORDS[cadence]})"
    return f"{CATEGORY_DISPLAY[category].capitalize()} ({CADENCE_WORDS[cadence]})"


def candidate_label(action: str, category: str) -> str:
    noun = CATEGORY_DISPLAY[category]
    return {
        "skip": f"Skip the {noun}",
        "defer": f"Push the {noun} past payday",
        "downgrade": f"Trim the {noun}",
        "cancel": f"Cancel the {noun}",
    }[action]


def candidate_detail(action: str, category: str, freed_cents: int) -> str:
    from app.solver.dates import money

    noun = CATEGORY_DISPLAY[category]
    verb = {"skip": "Skipping", "defer": "Deferring", "downgrade": "Trimming", "cancel": "Cancelling"}[action]
    # "the", never "this": several category names are plural ("groceries"),
    # and "Trimming this groceries" is the kind of sentence that makes a
    # person stop trusting the numbers next to it.
    return f"{verb} the {noun} keeps {money(freed_cents)}."

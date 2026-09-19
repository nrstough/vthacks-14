"""Every user-facing string the API returns.

Two rules run through all of it. The word *infeasible* never appears — a person
staring at an overdraft is not helped by being told their life is unsatisfiable.
And nothing claims more than was actually established: the plan is "sufficient
under the schedule shown", never "guaranteed", and when a solver stage runs out
of time the sentences that assert optimality are replaced rather than softened.
"""

from __future__ import annotations

from app.schemas import Candidate, CertificateItem

from .certificate import CertificateResult
from .dates import money, short_date, to_iso
from .objective import load_bearing
from .simulate import Trace

# Never emitted, under any branch, at any tier.
BANNED = ("infeasib", "guarantee")

# Claims only an exhaustive or proven-optimal search can make. Checked by tests
# against every response whose certificate is not minimal_proven.
OPTIMALITY_CLAIMS = (
    "No combination of these changes",
    "This is the best partial plan",
    "There are no changes available",
    "Nothing on this account can be changed",
    "Nothing here can be changed in time",
    "fewest",
    "smallest",
)

_COUNT_WORDS = (
    "zero", "one", "two", "three", "four", "five", "six",
    "seven", "eight", "nine", "ten", "eleven", "twelve",
)


def _changes(n: int) -> str:
    if n == 1:
        return "one change"
    word = _COUNT_WORDS[n] if n < len(_COUNT_WORDS) else str(n)
    return f"{word} changes"


def certificate_sentence(
    tier: int,
    plan_order: list[Candidate],
    cert: CertificateResult,
    best: Trace,
    minimal_proven: bool = True,
) -> str:
    plan_clears_zero = best.worst_shortfall == 0

    if not plan_order:
        if tier == 3 and not minimal_proven:
            # An empty plan from an unfinished search says nothing about what is
            # possible; only that nothing was settled on.
            return "The search did not finish, so no changes were selected."
        if tier == 3:
            # Departure from the reference solver, which says "the schedule
            # already clears" for every empty plan. At tier 3 it does not clear,
            # and a certificate that contradicts the verdict above it is worse
            # than no certificate at all.
            when = best.first_below_zero_date
            return (
                f"Nothing here can be changed in time. The gap stands at "
                f"{money(best.worst_shortfall)} on {short_date(to_iso(when))}."
                if when
                else f"Nothing here can be changed in time. The gap stands at "
                f"{money(best.worst_shortfall)}."
            )
        return "No changes needed. The schedule already clears."

    worst = cert.worst_item

    if not plan_clears_zero:
        if cert.irredundant:
            grows_by = worst.marginal_cents if worst else 0
            return (
                "This plan does not clear on its own, so nothing here is optional. "
                f"Drop any one change and the gap grows by up to {money(grows_by)}."
            )
        return (
            "This plan does not clear on its own. Some of these changes are holding "
            "the cushion rather than closing the gap."
        )

    if cert.irredundant and worst and worst.worst_date:
        return (
            f"Every change is load-bearing. Remove any one and you go under on "
            f"{short_date(worst.worst_date)}, by as much as "
            f"{money(worst.worst_shortfall_cents)}."
        )

    if worst and worst.marginal_cents > 0 and worst.worst_date:
        label = next((c.label for c in plan_order if c.id == worst.candidate_id), "the largest change")
        return (
            f"Remove {label} and you go under on {short_date(worst.worst_date)} by "
            f"{money(worst.worst_shortfall_cents)}. The rest hold the cushion."
        )

    return "Every change here is keeping you above the cushion, not above zero."


def plan_reason(item: CertificateItem, plan_clears_zero: bool) -> str:
    if not load_bearing(item) or item.worst_date is None:
        return "Holds the cushion; not strictly needed to clear zero."
    if not plan_clears_zero:
        return (
            f"Without it the gap grows to {money(item.worst_shortfall_cents)} on "
            f"{short_date(item.worst_date)}."
        )
    return (
        f"Without it you are {money(item.worst_shortfall_cents)} under on "
        f"{short_date(item.worst_date)}."
    )


def verdict_and_qualifier(
    tier: int,
    n: int,
    best: Trace,
    do_nothing: Trace,
    horizon_end: str,
    days_iso: list[str],
    minimal_proven: bool,
) -> tuple[str, str]:
    tightest = days_iso[best.tightest_date_index]
    changes = _changes(n)

    if tier == 1:
        verdict = (
            f"You stay above zero through {short_date(horizon_end)} with no changes."
            if n == 0
            else f"Make {changes} and you stay above zero through {short_date(horizon_end)}."
        )
        qualifier = (
            f"Tightest day is {short_date(tightest)} at {money(best.min_balance)}, "
            f"{money(best.min_balance - best.buffer_cents)} over the cushion. "
            "Sufficient under the schedule shown."
        )
        return verdict, qualifier

    if tier == 2:
        verdict = (
            f"You clear zero through {short_date(horizon_end)} with no changes, "
            "but nothing is left over."
            if n == 0
            else f"Make {changes} and you clear zero through {short_date(horizon_end)}, "
            "with no room left."
        )
        qualifier = (
            f"Tightest day is {short_date(tightest)} at {money(best.min_balance)}, under the "
            f"{money(best.buffer_cents)} cushion. One surprise charge puts you over."
        )
        return verdict, qualifier

    # Tier 3. `first_below_zero_date` is set whenever worst_shortfall > 0.
    by_date = short_date(to_iso(best.first_below_zero_date)) if best.first_below_zero_date else ""
    need = f"You need {money(best.worst_shortfall)} more by {by_date}."

    if n == 0:
        deepest = (
            short_date(to_iso(best.worst_shortfall_date)) if best.worst_shortfall_date else by_date
        )
        if not minimal_proven:
            # "Nothing can be done" is a claim about every possible plan, which
            # an unfinished search has not earned.
            return (
                f"{need} The search did not finish, so no plan was settled on.",
                f"The dip is {money(best.worst_shortfall)} at its deepest, on {deepest}.",
            )
        verdict = f"{need} There are no changes available to close any of it."
        qualifier = (
            "Nothing on this account can be changed in time. The dip is "
            f"{money(best.worst_shortfall)} at its deepest, on {deepest}."
        )
        return verdict, qualifier

    if not minimal_proven:
        # The search was cut short, so neither "no combination closes it" nor
        # "this is the best partial plan" has been established. Say what was.
        verdict = f"{need} These changes narrow the gap as far as the search got."
        qualifier = (
            f"They take the dip from {money(do_nothing.worst_shortfall)} down to "
            f"{money(best.worst_shortfall)}. The search did not finish proving that is "
            "the best available."
        )
        return verdict, qualifier

    verdict = f"{need} No combination of these changes closes the gap on its own."
    capitalised = changes[0].upper() + changes[1:]
    qualifier = (
        f"This is the best partial plan. {capitalised} {'takes' if n == 1 else 'take'} the dip "
        f"from {money(do_nothing.worst_shortfall)} down to {money(best.worst_shortfall)}. "
        "Everything else is already on the table."
    )
    return verdict, qualifier

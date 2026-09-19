"""The system instruction for the plan explainer.

Two halves. A fixed brief that says what the product is, what it may and may
not claim, and how to talk. Then a rendering of the solve on screen: the
request the user made and the answer the solver gave, in dollars, so the model
has every figure it is allowed to use and no reason to invent one.

The model explains. It never computes. Every number it says must already be
in the context below, which is why the context is generous: balances for
every day, the marginal figure behind every change, and the changes that were
left out along with the facts that decide why.
"""

from __future__ import annotations

from app.schemas import Candidate, SolveRequest, SolveResponse

TIER_LABEL = {
    1: "Tier 1, proven sufficient: the balance stays at or above the cushion every day.",
    2: "Tier 2, clears zero without the cushion: the balance stays at or above zero but dips below the cushion.",
    3: "Tier 3, needs outside cash: no set of changes keeps the balance above zero on every day.",
}

BRIEF = """\
You are the explainer built into Safe to Spend, a tool that takes a checking account's \
upcoming transactions and returns the fewest dated spending changes that keep the daily \
balance above zero until payday, then proves that nothing smaller works. You talk with the \
person using it, and sometimes with a judge at a hackathon who wants to know how it is built.

What the product is
- The answer on screen comes from an exact constraint solver (Google OR-Tools CP-SAT), not \
from you. Money is integer cents everywhere. There is one covering constraint per day and a \
lexicographic objective: fewest changes first, then softer terms such as how disruptive each \
change is and how much the plan churns from the one shown before.
- Every change in the plan is checked by removing it and re-walking the balances. If the \
balance goes under without it, the change is load-bearing. That check is against a zero \
balance, not the cushion, and it is done after the plan is chosen, so the solver is not \
marking its own homework.
- At most one change per transaction. Without that rule the solver would free more cash than \
a charge is worth and understate what the user needs.
- Two independent implementations, an exhaustive search and the constraint model, are checked \
against each other on generated accounts. Solves take a few milliseconds.
- The service is stateless: no accounts, no database, nothing stored. Each request carries \
everything, including this conversation.
- The frontend falls back to a local exact solver if the API is unreachable and says so in \
the footer. If the context says the solver was "local", say the numbers came from the built-in \
solver rather than the server.

Hard rules on wording
- Never use the word "infeasible". When nothing clears, say how much outside cash is needed \
and by which date; the context gives both.
- Never say "guaranteed" or "guarantee". Say "sufficient under the schedule shown". The plan \
is exact about the schedule it was given, and the schedule can change.
- Say the plan is the smallest, or that every change is load-bearing, only when the context \
says the minimality was proven. If it was not proven, say so plainly.
- This is not financial advice, and you do not give any. You explain what the solver found. \
Do not recommend loans, credit products, or investments.
- You cannot take any action. Nothing is cancelled, paid, moved, or messaged because of this \
conversation. If asked to do something, say the person has to do it themselves and the plan \
tells them the date by which to do it.

How to use the numbers
- Use only figures that appear in the context below. Never estimate, extrapolate, or add \
amounts yourself. If a question needs a number that is not there, say the solver has not \
computed it and how the person could get it: move the starting balance or cushion slider, or \
tick "Can't do this" on a change in the plan (or untick "Can do this" on one that was left \
out) to rule it out, and the plan is re-solved from scratch.
- If someone asks what happens when the paycheck is late, a bill is bigger, or a new purchase \
is added, say honestly that the solver is exact about the schedule it was shown and has not \
solved that case, then point to the controls that would let them try it.
- Dates in the context are for 2026. Refer to them like "September 24" or "the 24th".

How to talk
- Plain language, short. Two to four sentences unless the person asks for more. No headings, \
no bullet lists unless asked, no markdown formatting.
- Lead with the answer. Name the specific change, date, or amount from the context that \
supports it.
- If a question is outside this product, say so in a sentence and offer what you can do.
"""


def dollars(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100:,}.{cents % 100:02d}"


def _candidate_line(c: Candidate) -> str:
    when = f"effective {c.effective_date}"
    if c.recharge_date:
        when += f", comes back {c.recharge_date}"
    lead = f", must be actioned {c.lead_time_days} day(s) ahead" if c.lead_time_days else ""
    return (
        f"- {c.id}: {c.label} ({c.detail}); action {c.action}; frees {dollars(c.freed_cents)}; "
        f"{when}{lead}; disruption {c.pain} of 5"
    )


# What the account IS, as opposed to which solver ran. Without this the model
# has no way to know, and "is this my real account?" is one question away from
# an answer that calls generated data a bank's record of someone.
ACCOUNT_SOURCE = {
    "preset": "Account: the built-in sample account.",
    "modelled": (
        "Account: generated demo data, reproducible from its seed. Not a bank's records "
        "and not anyone's account. Say so plainly if the user asks where it came from."
    ),
    "nessie": (
        "Account: generated demo data seeded into Capital One's Nessie sandbox and read "
        "back over their API. Not a bank's records and not anyone's account. Say so "
        "plainly if the user asks where it came from. Amounts are whole dollars because "
        "the sandbox stores whole dollars."
    ),
}


def render_context(
    req: SolveRequest,
    res: SolveResponse,
    source: str = "server",
    account_source: str = "preset",
) -> str:
    lines: list[str] = []
    add = lines.append

    add("=== THE SOLVE ON SCREEN ===")
    add(f"Horizon: {req.as_of} to {req.horizon_end}, inclusive.")
    add(f"Starting balance: {dollars(req.opening_balance_cents)}. Cushion the user wants to keep: {dollars(req.buffer_cents)}.")
    add(f"Numbers computed by: the {'server (CP-SAT)' if source == 'server' else 'built-in local solver, because the server was unreachable'}.")
    add(ACCOUNT_SOURCE.get(account_source, ACCOUNT_SOURCE["preset"]))
    add("")

    add("Result")
    add(f"- {TIER_LABEL[res.tier]}")
    add(f"- Verdict shown to the user: \"{res.verdict}\"")
    add(f"- Qualifier shown: \"{res.qualifier}\"")
    add(f"- Minimality proven: {'yes' if res.certificate.minimal_proven else 'NO, a solver stage hit its time limit, so do not claim the plan is the smallest'}")
    if res.certificate.sentence:
        add(f"- Proof sentence shown: \"{res.certificate.sentence}\"")
    if res.external_cash_needed:
        add(
            f"- Outside cash needed: {dollars(res.external_cash_needed.amount_cents)} by "
            f"{res.external_cash_needed.by_date} (the first day the balance would go under; the amount covers the deepest dip)."
        )
    if res.shortfall.worst_cents:
        add(
            f"- Shortfall remaining after the plan: worst {dollars(res.shortfall.worst_cents)} on "
            f"{res.shortfall.worst_date}; every underwater day added up: {dollars(res.shortfall.total_cents)}."
        )
    else:
        add("- Shortfall remaining after the plan: none, the plan clears zero on every day.")
    add(f"- Solver: {res.meta.solver}, status {res.meta.status}, {res.meta.wall_ms:.0f} ms, {res.meta.candidates_considered} candidates considered.")
    if res.meta.excluded_locked_in:
        add(f"- Pinned changes dropped because their lead time had passed: {', '.join(res.meta.excluded_locked_in)}")
    add("")

    marginal = {item.candidate_id: item for item in res.certificate.per_item}
    add(f"The plan ({len(res.plan)} change(s), in the order to act on them)")
    if not res.plan:
        add("- No changes. Doing nothing already clears.")
    for p in res.plan:
        need = (
            "load-bearing against zero"
            if p.strictly_needed
            else "not load-bearing: removing it would not change the worst day"
        )
        add(f"- {p.candidate_id}: {p.label} ({p.detail}); act by {p.date}; frees {dollars(p.freed_cents)}; disruption {p.pain} of 5; {need}. Reason shown: \"{p.reason}\"")
        m = marginal.get(p.candidate_id)
        if m:
            where = f" on {m.worst_date}" if m.worst_date else ""
            add(
                f"    Without this change: worst balance would be {dollars(-m.worst_shortfall_cents)}{where}, "
                f"{dollars(m.marginal_cents)} deeper than with it, and {m.marginal_days} more day(s) below zero."
            )
    add("")

    used = {p.candidate_id for p in res.plan}
    ruled_out = set(req.locks.out)
    rest = [c for c in req.candidates if c.id not in used]
    add(f"Changes considered but not in the plan ({len(rest)})")
    if not rest:
        add("- None; every available change is in the plan.")
    for c in rest:
        line = _candidate_line(c)
        if c.id in ruled_out:
            line += (
                "; RULED OUT by the user (unticked \"Can do this\" in the left-out list), "
                "so the solver never saw it"
            )
        add(line)
    if req.locks.in_:
        add(f"Changes the user pinned in: {', '.join(req.locks.in_)}")
    add("")

    add("Scheduled transactions if nothing changes")
    for t in req.scheduled:
        add(f"- {t.date} {t.description}: {dollars(t.amount_cents)} ({t.kind}{', recurring' if t.recurring else ''}); id {t.id}")
    add("")

    add("End-of-day balance, do nothing vs with the plan")
    for row in res.balances:
        flags = []
        if row.is_payday:
            flags.append("payday")
        if row.changes_here:
            flags.append("changes take effect: " + ", ".join(row.changes_here))
        suffix = f"  [{'; '.join(flags)}]" if flags else ""
        add(f"- {row.date}: {dollars(row.baseline_cents)} -> {dollars(row.with_plan_cents)}{suffix}")

    return "\n".join(lines)


def system_instruction(
    req: SolveRequest,
    res: SolveResponse,
    source: str = "server",
    account_source: str = "preset",
) -> str:
    return BRIEF + "\n" + render_context(req, res, source, account_source)

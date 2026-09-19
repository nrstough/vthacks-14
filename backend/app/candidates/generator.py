"""Turn a transaction history into the changes a person could actually make.

The solver takes candidate changes as input and proves things about them. Until
this module existed the candidates were hand-written, so the service could only
answer for one account. Everything here is about producing a set the solver will
accept without argument and a person will recognise as their own spending.

Three rules are load-bearing, and each one exists because getting it wrong is
quiet rather than loud:

- **A deferral must come back.** `recharge_date` is the next payday after the
  charge; if there is none inside the horizon the deferral is not offered at all,
  because money put off past the horizon looks exactly like money saved.
- **Ids are a pure function of the row and the action.** The client sends locks
  and the previously-shown plan back as ids, so an id that changed between two
  calls would silently drop every override the user had set.
- **Only what is still actionable is offered.** A change whose lead time has
  already passed is not a choice, and listing it would inflate what the screen
  says was considered.
"""

from __future__ import annotations

import hashlib
from collections import Counter

from app.schemas import Candidate, CandidatesMeta, CandidatesRequest, CandidatesResponse
from app.solver.dates import days_between, money, short_date

from .lexicon import PROTECTED, UNKNOWN_CATEGORY, Match, classify
from .policy import LABELS, POLICY, UNKNOWN_DISCRETIONARY, Alternative

_ID_MAX = 64
_ID_PREFIX = 40
_ID_HASH = 12


def _candidate_id(txn_id: str, action: str) -> str:
    """`t_gym.cancel`, or a hashed form when that would be too long.

    Ids are capped at 64 characters by the schema. The fallback keeps a readable
    prefix and enough of a digest to separate rows that share one; at the longest
    action name it comes to 63.
    """
    plain = f"{txn_id}.{action}"
    if len(plain) <= _ID_MAX:
        return plain
    digest = hashlib.sha1(txn_id.encode(), usedforsecurity=False).hexdigest()[:_ID_HASH]
    return f"{txn_id[:_ID_PREFIX]}.{action}.{digest}"


def _label(match: Match, alt: Alternative, date: str, recharge: str | None) -> str:
    with_brand, without_brand = LABELS[(match.category, alt.action)]
    template = with_brand if match.display else (without_brand or with_brand)
    return template.format(
        brand=match.display or "",
        date=short_date(date),
        recharge=short_date(recharge) if recharge else "",
    )


def _detail(description: str, amount_cents: int, recurring: bool, alt: Alternative, freed: int) -> str:
    """The user's own statement line, then what the change does to it.

    The description is reproduced verbatim — it is how they will recognise the
    charge — but it never reaches a label, because labels are interpolated into
    the certificate sentence and a merchant called GUARANTEED RATE would put a
    word there that this product never says.
    """
    parts = [f"{description}, {money(abs(amount_cents))}"]
    if recurring:
        # The schema carries a flag, not a cadence: calling it monthly would be
        # a guess, and wrong for anything weekly or annual.
        parts.append(" recurring")
    if alt.action == "downgrade":
        parts.append(f" down to {money(abs(amount_cents) - freed)}")
    elif alt.action == "defer":
        parts.append(" moved past payday")
    return "".join(parts)


def _dedupe(chosen: list[Candidate]) -> list[Candidate]:
    """Make labels unique, in increasing order of how much noise it adds.

    Two grocery runs a week apart are both "Trim the grocery run" until a date is
    added; two on one day need the amount; two identical in every visible way
    need an ordinal. The ordinal is a position, never the transaction id — an id
    is caller text and could carry a word the certificate sentence must not.
    """
    for suffix in (
        lambda c, n: f" on {short_date(c.effective_date)}",
        lambda c, n: f" ({money(c.freed_cents)})",
        lambda c, n: f" (#{n})",
    ):
        counts = Counter(c.label for c in chosen)
        if all(count == 1 for count in counts.values()):
            break
        ordinals: Counter[str] = Counter()
        rebuilt: list[Candidate] = []
        for c in sorted(chosen, key=lambda c: (c.effective_date, c.id)):
            if counts[c.label] > 1:
                ordinals[c.label] += 1
                rebuilt.append(c.model_copy(update={"label": c.label + suffix(c, ordinals[c.label])}))
            else:
                rebuilt.append(c)
        chosen = rebuilt
    return chosen


def generate(req: CandidatesRequest) -> CandidatesResponse:
    # A payday is income that actually arrives. An income row may legitimately be
    # negative — a clawback is still an income row — and deferring a charge onto
    # one would move it to a day money leaves, under a label saying otherwise.
    paydays = sorted(
        t.date
        for t in req.scheduled
        if t.kind == "income" and t.amount_cents > 0 and req.as_of <= t.date <= req.horizon_end
    )

    considered = 0
    protected: list[str] = []
    unrecognised: list[str] = []
    not_actionable: list[str] = []
    pool: list[tuple[int, int, int, str, Candidate]] = []

    for txn in req.scheduled:
        if txn.kind == "income" or txn.amount_cents >= 0:
            continue
        if not (req.as_of <= txn.date <= req.horizon_end):
            continue
        considered += 1

        match = classify(txn.description)
        if match.category in PROTECTED:
            protected.append(txn.id)
            continue
        if match.category == UNKNOWN_CATEGORY:
            unrecognised.append(txn.id)
            if txn.kind != "discretionary":
                # Nothing recognised it and nobody said it was discretionary, so
                # there is no evidence it can be dropped. Silence is the honest
                # answer; guessing would be the product telling someone their
                # life is expendable on the strength of a merchant string.
                protected.append(txn.id)
                continue
            alternatives = UNKNOWN_DISCRETIONARY
        else:
            alternatives = POLICY[match.category]

        emitted = False
        for index, alt in enumerate(alternatives):
            freed = abs(txn.amount_cents) * alt.pct // 100
            if freed == 0:
                continue
            if days_between(req.as_of, txn.date) < alt.lead_time_days:
                continue
            recharge = None
            if alt.needs_payday:
                recharge = next((d for d in paydays if d > txn.date), None)
                if recharge is None:
                    continue

            candidate = Candidate(
                id=_candidate_id(txn.id, alt.action),
                label=_label(match, alt, txn.date, recharge),
                detail=_detail(txn.description, txn.amount_cents, txn.recurring, alt, freed),
                action=alt.action,
                target_txn_id=txn.id,
                freed_cents=freed,
                effective_date=txn.date,
                recharge_date=recharge,
                lead_time_days=alt.lead_time_days,
                pain=alt.pain,
            )
            # Every row's first choice outranks any row's second, so a cap never
            # spends its budget on one transaction's alternatives.
            pool.append((index, alt.pain, -freed, candidate.id, candidate))
            emitted = True

        if not emitted:
            not_actionable.append(txn.id)

    pool.sort(key=lambda entry: entry[:4])
    truncated = len(pool) > req.limit
    chosen = _dedupe([entry[4] for entry in pool[: req.limit]])
    chosen.sort(key=lambda c: (c.effective_date, c.id))

    _verify(req, chosen)

    return CandidatesResponse(
        candidates=chosen,
        meta=CandidatesMeta(
            rows_considered=considered,
            protected=sorted(protected),
            unrecognised=sorted(unrecognised),
            not_actionable=sorted(not_actionable),
            truncated=truncated,
        ),
    )


def _verify(req: CandidatesRequest, chosen: list[Candidate]) -> None:
    """Re-check what the solver's own validation would reject.

    A generator bug otherwise surfaces as a 200 here and a 422 on the next call:
    the client's request refused by the client's own server, with nothing naming
    this module. `raise`, not `assert`, so -O cannot remove it.
    """
    amounts = {t.id: abs(t.amount_cents) for t in req.scheduled}
    ids = [c.id for c in chosen]
    if len(ids) != len(set(ids)):
        raise RuntimeError("candidate generator invariant: duplicate candidate ids")
    labels = [c.label for c in chosen]
    if len(labels) != len(set(labels)):
        raise RuntimeError("candidate generator invariant: duplicate labels")
    for c in chosen:
        if len(c.id) > _ID_MAX:
            raise RuntimeError(f"candidate generator invariant: id {c.id!r} is too long")
        if c.freed_cents < 1 or c.freed_cents > amounts[c.target_txn_id]:
            raise RuntimeError(f"candidate generator invariant: {c.id} frees {c.freed_cents}")
        if not (req.as_of <= c.effective_date <= req.horizon_end):
            raise RuntimeError(f"candidate generator invariant: {c.id} is outside the horizon")
        if c.action == "defer":
            if c.recharge_date is None or c.recharge_date <= c.effective_date:
                raise RuntimeError(f"candidate generator invariant: {c.id} never comes back")
        elif c.recharge_date is not None:
            raise RuntimeError(f"candidate generator invariant: {c.id} recharges but is not a defer")

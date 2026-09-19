"""Request and response models for POST /api/solve and POST /api/candidates.

Strict by construction: unknown fields are rejected, money is integer cents and
never a float, and dates are YYYY-MM-DD strings. Cross-field checks live on the
*later* of the two fields they relate, because pydantic validates in declaration
order and only then does `info.data` carry the earlier field — which is also what
puts a usable field path in the 422 body.
"""

from __future__ import annotations

import datetime
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationInfo, field_validator

# Caps shared by validation and the engines. The cents bound keeps every CP-SAT
# expression (opening + all scheduled + all freed, times the horizon) far inside
# int64, so the model can never be rejected as MODEL_INVALID for overflow.
MAX_T = 366
MAX_N = 60
MAX_SCHED = 2000
MAX_FREE = 18
CENTS_ABS = 10**11
# Balances and running totals are sums over the whole horizon, so they leave the
# per-field input range from perfectly legal input: an opening balance at the cap
# plus a single charge already exceeds it. Bounding derived figures by the input
# bound turned a valid request into a 500. The ceiling below is the worst case
# that input limits can produce (opening + every scheduled row + every change,
# summed across a year) with room to spare, and is still far inside int64.
DERIVED_CENTS_ABS = 10**17

ID_RE = r"^[A-Za-z0-9_.:-]{1,64}$"
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

TxnKind = Literal["income", "bill", "discretionary"]
Action = Literal["skip", "defer", "downgrade", "cancel"]

Cents = Annotated[StrictInt, Field(ge=-CENTS_ABS, le=CENTS_ABS)]
NonNegCents = Annotated[StrictInt, Field(ge=0, le=CENTS_ABS)]
DerivedCents = Annotated[StrictInt, Field(ge=-DERIVED_CENTS_ABS, le=DERIVED_CENTS_ABS)]
NonNegDerivedCents = Annotated[StrictInt, Field(ge=0, le=DERIVED_CENTS_ABS)]
Id = Annotated[StrictStr, Field(pattern=ID_RE)]


def iso(value: str) -> str:
    """Accept only canonical YYYY-MM-DD.

    `date.fromisoformat` alone would also accept "20260919", and a lax pydantic
    date would accept a datetime or an epoch int (silently a year off), so the
    regex carries the format and fromisoformat carries the calendar.
    """
    if not _ISO_RE.fullmatch(value):
        raise ValueError("must be a YYYY-MM-DD date")
    datetime.date.fromisoformat(value)
    return value


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


# --------------------------------------------------------------------------
# request
# --------------------------------------------------------------------------


class ScheduledTxn(Strict):
    id: Id
    date: StrictStr
    description: StrictStr
    amount_cents: Cents  # signed: + income, - outflow
    kind: TxnKind
    recurring: bool

    @field_validator("date")
    @classmethod
    def _date(cls, v: str) -> str:
        return iso(v)


class Candidate(Strict):
    id: Id
    label: StrictStr
    detail: StrictStr
    action: Action
    target_txn_id: Id
    freed_cents: NonNegCents
    effective_date: StrictStr
    # validate_default, because a field validator does not run on a default:
    # omitting the key entirely would otherwise skip the check that an
    # explicit null fails, and the deferral would silently become permanent.
    recharge_date: StrictStr | None = Field(default=None, validate_default=True)
    lead_time_days: Annotated[StrictInt, Field(ge=0, le=MAX_T)]
    pain: Annotated[StrictInt, Field(ge=1, le=5)]

    @field_validator("effective_date")
    @classmethod
    def _effective(cls, v: str) -> str:
        return iso(v)

    @field_validator("recharge_date")
    @classmethod
    def _recharge(cls, v: str | None, info: ValidationInfo) -> str | None:
        action = info.data.get("action")
        effective = info.data.get("effective_date")
        if action == "defer":
            if v is None:
                raise ValueError("a defer needs a recharge_date")
            iso(v)
            if effective and datetime.date.fromisoformat(v) <= datetime.date.fromisoformat(effective):
                raise ValueError("recharge_date must be after effective_date")
        elif v is not None:
            raise ValueError("recharge_date is only meaningful when action is 'defer'")
        return v


class Locks(Strict):
    in_: list[Id] = Field(default_factory=list, alias="in", max_length=MAX_N)
    out: list[Id] = Field(default_factory=list, max_length=MAX_N)


# Both request models take the same window and the same rows, so they share these
# rather than keeping two copies that can drift. `iso` above is the precedent: a
# module-level helper several validators call.


def check_horizon(horizon_end: str, as_of: str | None) -> str:
    """Validate horizon_end against as_of.

    `as_of` is None when it failed its own validator and never reached
    `info.data`; skipping the span check then keeps the 422 pointed at the one
    field the caller actually got wrong.
    """
    iso(horizon_end)
    if as_of:
        span = (datetime.date.fromisoformat(horizon_end) - datetime.date.fromisoformat(as_of)).days + 1
        if span < 1:
            raise ValueError("horizon_end is before as_of; there are no days to plan over")
        if span > MAX_T:
            raise ValueError(f"horizon of {span} days is longer than the {MAX_T}-day limit")
    return horizon_end


def check_unique_txn_ids(v: list[ScheduledTxn]) -> list[ScheduledTxn]:
    ids = [t.id for t in v]
    if len(ids) != len(set(ids)):
        raise ValueError("transaction ids must be unique")
    return v


class SolveRequest(Strict):
    as_of: StrictStr
    horizon_end: StrictStr
    opening_balance_cents: Cents
    buffer_cents: NonNegCents
    scheduled: list[ScheduledTxn] = Field(max_length=MAX_SCHED)
    candidates: list[Candidate] = Field(max_length=MAX_N)
    locks: Locks
    # The plan the user was last shown. Hysteresis input; the server keeps no
    # state of its own, so the client sends it back on every request.
    previous_plan: list[Id] = Field(default_factory=list, max_length=MAX_N)

    @field_validator("as_of")
    @classmethod
    def _as_of(cls, v: str) -> str:
        return iso(v)

    @field_validator("horizon_end")
    @classmethod
    def _horizon_end(cls, v: str, info: ValidationInfo) -> str:
        return check_horizon(v, info.data.get("as_of"))

    @field_validator("scheduled")
    @classmethod
    def _scheduled(cls, v: list[ScheduledTxn]) -> list[ScheduledTxn]:
        return check_unique_txn_ids(v)

    @field_validator("candidates")
    @classmethod
    def _candidates(cls, v: list[Candidate], info: ValidationInfo) -> list[Candidate]:
        ids = [c.id for c in v]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate ids must be unique")

        by_txn = {t.id: t for t in info.data.get("scheduled", [])}
        as_of = info.data.get("as_of")
        horizon_end = info.data.get("horizon_end")

        for c in v:
            target = by_txn.get(c.target_txn_id)
            if target is None:
                raise ValueError(f"{c.id} targets {c.target_txn_id}, which is not in scheduled")
            if c.freed_cents > abs(target.amount_cents):
                raise ValueError(
                    f"{c.id} frees {c.freed_cents} cents from a transaction of "
                    f"{abs(target.amount_cents)} cents"
                )
            if as_of and horizon_end and not (as_of <= c.effective_date <= horizon_end):
                raise ValueError(f"{c.id} takes effect on {c.effective_date}, outside the horizon")
        return v

    @field_validator("locks")
    @classmethod
    def _locks(cls, v: Locks, info: ValidationInfo) -> Locks:
        known = {c.id for c in info.data.get("candidates", [])}
        unknown = sorted({i for i in (*v.in_, *v.out) if i not in known})
        if unknown:
            raise ValueError(f"locks name candidates that do not exist: {unknown}")
        both = sorted(set(v.in_) & set(v.out))
        if both:
            raise ValueError(f"locked both in and out: {both}")
        return v


class CandidatesRequest(Strict):
    """What /api/candidates needs: the window and the rows, nothing about balances.

    Fields are declared in SolveRequest's order and checked by the same functions,
    so the two endpoints reject the same input the same way.

    `limit` defaults to MAX_FREE rather than MAX_N because that is the largest set
    every fallback still answers. The two ceilings are not the same number: this
    service's exhaustive engine refuses above MAX_FREE, and the browser's stand-in
    refuses above twenty, so the lower of the two is the safe default. A caller
    that knows it has CP-SAT can ask for more.
    """

    as_of: StrictStr
    horizon_end: StrictStr
    scheduled: list[ScheduledTxn] = Field(max_length=MAX_SCHED)
    limit: Annotated[StrictInt, Field(ge=1, le=MAX_N)] = MAX_FREE

    @field_validator("as_of")
    @classmethod
    def _as_of(cls, v: str) -> str:
        return iso(v)

    @field_validator("horizon_end")
    @classmethod
    def _horizon_end(cls, v: str, info: ValidationInfo) -> str:
        return check_horizon(v, info.data.get("as_of"))

    @field_validator("scheduled")
    @classmethod
    def _scheduled(cls, v: list[ScheduledTxn]) -> list[ScheduledTxn]:
        return check_unique_txn_ids(v)


# --------------------------------------------------------------------------
# response
# --------------------------------------------------------------------------


class PlanItem(Strict):
    candidate_id: Id
    label: StrictStr
    detail: StrictStr
    action: Action
    date: StrictStr
    freed_cents: NonNegCents
    pain: StrictInt
    strictly_needed: bool  # false when it only protects the cushion
    reason: StrictStr


class CertificateItem(Strict):
    candidate_id: Id
    worst_shortfall_cents: NonNegDerivedCents  # absolute worst dip with this change removed
    worst_date: StrictStr | None
    marginal_cents: StrictInt  # how much DEEPER the dip gets without this change
    marginal_days: StrictInt  # how many more days below zero without it


class Certificate(Strict):
    irredundant: bool
    minimal_proven: bool  # false when a solver stage hit its time limit
    sentence: StrictStr
    per_item: list[CertificateItem]


class Shortfall(Strict):
    worst_cents: NonNegDerivedCents
    worst_date: StrictStr | None
    total_cents: NonNegDerivedCents  # every day underwater added up


class ExternalCash(Strict):
    amount_cents: NonNegDerivedCents
    by_date: StrictStr


class BalanceRow(Strict):
    date: StrictStr
    baseline_cents: DerivedCents
    with_plan_cents: DerivedCents
    is_payday: bool
    changes_here: list[Id]


class Meta(Strict):
    solver: Literal["cp-sat", "brute-force"]
    status: Literal["OPTIMAL", "FEASIBLE"]
    wall_ms: float
    candidates_considered: StrictInt
    excluded_locked_in: list[Id]  # pinned ids that could not be honoured


class SolveResponse(Strict):
    tier: Literal[1, 2, 3]
    verdict: StrictStr
    qualifier: StrictStr
    plan: list[PlanItem]
    certificate: Certificate
    shortfall: Shortfall
    external_cash_needed: ExternalCash | None
    balances: list[BalanceRow]
    meta: Meta


class CandidatesMeta(Strict):
    """What happened to every row the generator looked at.

    `protected`, `not_actionable` and the targets of the returned candidates
    partition the considered rows — except when `truncated`, where a row whose
    every alternative fell below the cut belongs to none of the three. A row that
    kept one alternative is still offered, so truncation does not by itself mean
    a row went missing.

    `unrecognised` is orthogonal to all of that: it records classification, not
    disposition, so a row no keyword matched appears there whether it was
    offered, protected or cut by the limit.
    """

    rows_considered: Annotated[StrictInt, Field(ge=0, le=MAX_SCHED)]
    protected: list[Id]
    unrecognised: list[Id]
    not_actionable: list[Id]
    truncated: bool


class CandidatesResponse(Strict):
    candidates: list[Candidate] = Field(max_length=MAX_N)
    meta: CandidatesMeta


# ---- modelled accounts ----


class SampleAccountRequest(Strict):
    """What POST /api/accounts/sample needs.

    `seed` is optional and echoed back on the response, so any account a person
    sees on screen can be regenerated exactly from the response alone. That is
    the difference between a demo and a party trick.

    `horizon_days` is bounded well inside MAX_T. The upper end is held at 45
    rather than the schema's ceiling because candidate count grows with the
    window and the exhaustive engine is 2^n above nothing.
    """

    seed: Annotated[StrictInt, Field(ge=0, le=2**31)] | None = None
    as_of: StrictStr | None = None
    horizon_days: Annotated[StrictInt, Field(ge=14, le=45)] = 30

    @field_validator("as_of")
    @classmethod
    def _as_of(cls, v: str | None) -> str | None:
        if v is None:
            return None
        iso(v)
        # `9999-12-31` is a valid date and a 500 waiting to happen: adding the
        # horizon to it raises OverflowError inside the generator, which is an
        # unhandled exception rather than a refused request. Leave room for the
        # largest horizon this endpoint accepts.
        if datetime.date.fromisoformat(v) > datetime.date.max - datetime.timedelta(days=46):
            raise ValueError("as_of leaves no room for the horizon")
        return v


class SampleAccountResponse(Strict):
    """A modelled account, in the contract's own field shapes.

    Not itself a request body for the other two endpoints: it carries `seed`,
    `opening_balance_cents`, `buffer_cents` and `source`, and both request models
    are `extra="forbid"`, so posting it verbatim is a 422. The caller picks the
    fields each endpoint declares.

    `source` is required and always the literal "modelled". It is not decoration:
    this is generated data and nothing downstream may present it as a bank's.
    """

    seed: StrictInt
    as_of: StrictStr
    horizon_end: StrictStr
    opening_balance_cents: Cents
    buffer_cents: NonNegCents
    scheduled: list[ScheduledTxn] = Field(max_length=MAX_SCHED)
    source: Literal["modelled"]


class NotRoundTripped(Strict):
    """One row the sandbox did not give back unchanged.

    Reported rather than hidden. A demo that quietly drops half an account is
    worse than one that says what it dropped, and the reasons are distinct
    because they have different causes and different fixes.
    """

    id: Id
    reason: Literal[
        "written but not returned",
        "amount changed by the sandbox",
        "no usable date",
        "outside the window",
        "amount rounds to zero dollars",
    ]


class NessieProvenance(Strict):
    """Which sandbox records this account is, and how it got here."""

    customer_id: StrictStr | None
    account_id: StrictStr
    mode: Literal["seeded", "read_only"]


class NessieAccountResponse(Strict):
    """An account seeded into Capital One's Nessie sandbox and read back.

    A sibling of SampleAccountResponse rather than a widening of it: that model's
    `source` is a closed literal that its tests and the deploy's smoke check both
    pin, and the sample endpoint's behaviour is unchanged by any of this.

    `source` is required and always "nessie". Generated data seeded into someone
    else's sandbox is still generated data; nothing downstream may present it as
    a bank's record of anyone.
    """

    seed: StrictInt
    as_of: StrictStr
    horizon_end: StrictStr
    opening_balance_cents: Cents
    buffer_cents: NonNegCents
    scheduled: list[ScheduledTxn] = Field(max_length=MAX_SCHED)
    source: Literal["nessie"]
    nessie: NessieProvenance
    written: Annotated[StrictInt, Field(ge=0)]
    returned: Annotated[StrictInt, Field(ge=0)]
    not_round_tripped: list[NotRoundTripped]

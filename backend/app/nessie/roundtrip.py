"""Seed a Nessie sandbox account from a modelled one, read it back, and report
exactly what the round trip cost.

Three measured facts shape every decision here. They were confirmed against the
live sandbox and, independently, by four unrelated hackathon teams; the record
is in `docs/nessie-notes.md` on the abandoned review-response branch and is
summarised in `docs/features/nessie.md`.

**Every amount is truncated to whole dollars on write.** `1200.57` comes back as
`1200`, `17.99` as `17`. Truncation, not rounding. So the seed rounds to whole
dollars *before* writing, half away from zero, and what comes back is what was
written. Cent precision stays on `/api/accounts/sample`, where it is free.

**Writes never move `balance`.** Deposits, withdrawals and transfers all leave
it where account creation put it. So the balance is never read back as an
arithmetic result: in seeded mode it is the rounded modelled opening, and in
read-only mode it is the creation balance, which is the same number.

**Spending is a withdrawal, not a purchase.** Purchases need a merchant round
trip and have no documented create path; Capital One's own SDKs use
`/accounts/{id}/withdrawals`, which takes a deposit's five fields. So every kind
of row round-trips: income as a deposit, discretionary as a withdrawal,
recurring as a bill.

The local integer-cent ledger stays the system of record. Nessie is a seeded
history source and a downstream mirror, never the arithmetic.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.accounts.product import sample_account
from app.nessie import NessieUnavailable, NessieUpstreamError, to_scheduled
from app.nessie.client import (
    NessieConfig,
    NessieError,
    NessieNotConfigured,
    get,
    post,
    to_cents,
)
from app.schemas import iso

# product.py's own constant. Repeated rather than imported because it is a
# property of the modelled account, not of Nessie, and the two should be free
# to diverge.
BUFFER_CENTS = 2_500

# The same identity verify() writes, for the same reason: nobody, reading the
# sandbox later, should mistake this for a person.
CUSTOMER = {
    "first_name": "Modelled",
    "last_name": "Account",
    "address": {
        "street_number": "620",
        "street_name": "Drillfield Dr",
        "city": "Blacksburg",
        "state": "VA",
        "zip": "24061",
    },
}

# The account nickname carries the seed and the window it was generated for.
# Creates are permanent here (DELETE answers 403), so a seeded account outlives
# the process that made it, and read-only mode has no other way to learn which
# window its rows belong to.
# The seed is bounded: the field it lands in is an unbounded StrictInt, and the
# nickname is whatever is on the sandbox account, so an unbounded \d+ would let
# a 60-digit seed through into JSON the browser cannot represent.
NICKNAME_RE = re.compile(r"og ([0-9]{1,10}) (\d{4}-\d{2}-\d{2}) (\d{4}-\d{2}-\d{2})")

KIND_PATHS = {
    "income": ("deposits", True),
    "discretionary": ("withdrawals", False),
    "bill": ("bills", True),
}


class _Unusable(Exception):
    """A row that cannot become a ScheduledTxn. Carries the reason verbatim."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def round_to_dollars(cents: int) -> int:
    """Cents to whole dollars in cents, half away from zero.

    Integer arithmetic throughout: a float here would reintroduce exactly the
    error `to_cents` exists to prevent.
    """
    q, r = divmod(abs(int(cents)), 100)
    if r >= 50:
        q += 1
    out = q * 100
    return -out if cents < 0 else out


def dollars(cents: int) -> int:
    """The JSON integer Nessie is sent. Always non-negative: direction is the
    resource (a withdrawal is not a negative deposit)."""
    return abs(round_to_dollars(cents)) // 100


def parse_nickname(text: Any) -> tuple[int, str, str] | None:
    """`og <seed> <as_of> <horizon_end>` back into its parts, or None."""
    if not isinstance(text, str):
        return None
    m = NICKNAME_RE.fullmatch(text)
    if not m:
        return None
    try:
        return int(m.group(1)), iso(m.group(2)), iso(m.group(3))
    except ValueError:
        return None


def seeded_account(
    seed: int | None = None, as_of: date | None = None, horizon_days: int = 30
) -> dict[str, Any]:
    """A modelled account rounded to whole dollars, ready to seed.

    Not the same account `/api/accounts/sample` returns for the same seed: this
    one is pre-rounded, because the sandbox would truncate it anyway and a demo
    that shows different numbers before and after the round trip is worse than
    one that shows whole dollars throughout.
    """
    account = sample_account(seed=seed, as_of=as_of, horizon_days=horizon_days)
    account["opening_balance_cents"] = max(0, round_to_dollars(account["opening_balance_cents"]))
    account["scheduled"] = [
        {**row, "amount_cents": round_to_dollars(row["amount_cents"])}
        for row in account["scheduled"]
    ]
    return account


def _record(body: Any, what: str) -> dict[str, Any]:
    """A create's response as a record, or an upstream error.

    The published docs claim creates answer with a bare string. Measured, they
    answer `{"code": 201, "objectCreated": {...}}`. Guard rather than choose:
    an unexpected shape must not become an AttributeError and a 500.
    """
    if not isinstance(body, dict):
        raise NessieUpstreamError(f"Nessie answered with something other than a record for the {what}")
    created = body.get("objectCreated")
    created = created if isinstance(created, dict) else body
    ident = created.get("_id")
    if not ident or not isinstance(ident, str):
        raise NessieUpstreamError(f"Nessie accepted the {what} but returned no id, so it cannot be used")
    return created


def _rows(body: Any, what: str) -> list[dict[str, Any]]:
    if not isinstance(body, list) or any(not isinstance(r, dict) for r in body):
        raise NessieUpstreamError(f"Nessie returned a malformed {what} list")
    return body


def _upstream(what: str):
    """Turn a transport-level NessieError into the one the route maps.

    `to_cents` raises `NessieError` for an amount that is a string, a boolean,
    non-finite, sub-cent or out of range, and `main.py` has no handler for that
    type — so every one of those was a 500 with a stack trace rather than the
    502 the contract promises. List-and-dict shape checks do not catch them:
    the row is a perfectly good dict with a bad field in it.
    """

    class _Wrap:
        def __enter__(self) -> None:
            return None

        def __exit__(self, kind, value, tb) -> bool:
            if isinstance(value, NessieError):
                raise NessieUpstreamError(f"Nessie sent an unusable {what}: {value}") from value
            return False

    return _Wrap()


def _post(config: NessieConfig, path: str, body: dict, what: str) -> dict[str, Any]:
    try:
        return _record(post(config, path, body), what)
    except NessieNotConfigured as e:
        raise NessieUnavailable(str(e)) from e
    except NessieError as e:
        raise NessieUpstreamError(str(e)) from e


def _get(config: NessieConfig, path: str, what: str) -> Any:
    try:
        return get(config, path)
    except NessieNotConfigured as e:
        raise NessieUnavailable(str(e)) from e
    except NessieError as e:
        raise NessieUpstreamError(str(e)) from e


def _usable(row: dict[str, Any], as_of: str, horizon_end: str) -> dict[str, Any]:
    """One normalised row, or _Unusable with the reason to report.

    `to_scheduled` emits "" for a row with no date rather than inventing one.
    An empty or malformed date would fail the schema on the caller's own next
    request, as a 422 on the whole solve, so it is dropped and named here.
    """
    try:
        iso(row["date"])
    except (ValueError, KeyError):
        raise _Unusable("no usable date") from None
    if not (as_of <= row["date"] <= horizon_end):
        # The generator and both solvers drop these silently. Silence is what
        # makes a short plan look like a wrong plan.
        raise _Unusable("outside the window")
    return row


def _normalise(
    lists: dict[str, list[dict[str, Any]]], as_of: str, horizon_end: str
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    scheduled: list[dict[str, Any]] = []
    problems: list[dict[str, str]] = []
    for kind, (_, recurring) in KIND_PATHS.items():
        with _upstream(f"{kind} amount"):
            normalised = to_scheduled(lists[kind], kind, recurring)
        for row in normalised:
            try:
                scheduled.append(_usable(row, as_of, horizon_end))
            except _Unusable as e:
                problems.append({"id": row["id"], "reason": e.reason})
    scheduled.sort(key=lambda r: (r["date"], r["id"]))
    return scheduled, problems


def _read_lists(config: NessieConfig, account_id: str) -> dict[str, list[dict[str, Any]]]:
    lists = {
        kind: _rows(_get(config, f"/accounts/{account_id}/{path}", path), path)
        for kind, (path, _) in KIND_PATHS.items()
    }
    if not any(lists.values()):
        # The 200-empty-list trap, one level up. A wrong key answers exactly
        # this, and so does a real account with nothing in it. Neither may be
        # rendered as an account: a judge would read a blank screen as data.
        raise NessieUnavailable(
            "Nessie returned nothing for this account, so it is not confirmed. An empty "
            "read is how a wrong key looks: it answers 200 with no data rather than refusing."
        )
    return lists


def _finish(scheduled: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not scheduled:
        raise NessieUnavailable("Nessie returned no usable rows for this account.")
    return scheduled


def seed_and_read_back(account: dict[str, Any], config: NessieConfig) -> dict[str, Any]:
    """Write the account into the sandbox, read it back, report the difference."""
    as_of, horizon_end = account["as_of"], account["horizon_end"]
    seed, rows = account["seed"], account["scheduled"]

    customer = _post(config, "/customers", CUSTOMER, "customer")
    created = _post(
        config,
        f"/customers/{customer['_id']}/accounts",
        {
            "type": "Checking",
            "nickname": f"og {seed} {as_of} {horizon_end}",
            "rewards": 0,
            "balance": dollars(account["opening_balance_cents"]),
        },
        "account",
    )
    account_id = created["_id"]

    written: dict[str, dict[str, Any]] = {}
    total = len(rows)
    for i, row in enumerate(rows):
        path, _ = KIND_PATHS[row["kind"]]
        amount = dollars(row["amount_cents"])
        body = (
            {
                "status": "recurring",
                "payee": row["description"],
                "nickname": row["description"],
                "payment_date": row["date"],
                "payment_amount": amount,
                "recurring_date": int(row["date"][8:10]),
            }
            if row["kind"] == "bill"
            else {
                "medium": "balance",
                "transaction_date": row["date"],
                "status": "completed",
                "amount": amount,
                "description": row["description"],
            }
        )
        try:
            made = _post(config, f"/accounts/{account_id}/{path}", body, f"row {i + 1}")
        except (NessieUpstreamError, NessieUnavailable) as e:
            # The transport's own message carries no progress, and "it failed"
            # is not actionable when creates are permanent: the next attempt
            # must know how much of this account already exists.
            raise type(e)(f"Nessie failed after {i} of {total} rows were written: {e}") from e
        written[f"n_{made['_id'][:40]}"] = {
            "amount": amount,
            "cents": row["amount_cents"],
            "kind": row["kind"],
        }

    scheduled, problems = _normalise(_read_lists(config, account_id), as_of, horizon_end)
    reported = {p["id"] for p in problems}

    for ident, sent in written.items():
        if ident in reported:
            continue  # one reason per row; the unusable one is the more specific
        match = next((r for r in scheduled if r["id"] == ident), None)
        if match is None:
            problems.append({"id": ident, "reason": "written but not returned"})
        elif sent["amount"] == 0 and sent["cents"] != 0:
            # Rounded to nothing before it was ever written. Read-back equality
            # cannot see this: 0 was sent and 0 came back, so the row looks
            # faithful while its entire value is gone.
            problems.append({"id": ident, "reason": "amount rounds to zero dollars"})
        elif abs(match["amount_cents"]) != sent["amount"] * 100:
            problems.append({"id": ident, "reason": "amount changed by the sandbox"})

    scheduled = _finish(scheduled)
    return {
        "seed": seed,
        "as_of": as_of,
        "horizon_end": horizon_end,
        # Never read back: the sandbox freezes balance at creation, so reading
        # it would be reporting an input as though it were a result.
        "opening_balance_cents": account["opening_balance_cents"],
        "buffer_cents": account.get("buffer_cents", BUFFER_CENTS),
        "scheduled": scheduled,
        "source": "nessie",
        "nessie": {
            "customer_id": customer["_id"],
            "account_id": account_id,
            "mode": "seeded",
        },
        "written": total,
        "returned": len(scheduled),
        "not_round_tripped": sorted(problems, key=lambda p: (p["reason"], p["id"])),
    }


def read_back(
    account_id: str, config: NessieConfig, *, as_of: str, horizon_end: str
) -> dict[str, Any]:
    """An account already in the sandbox, with no writes at all.

    There is no write to confirm the key with, so an empty or mismatched read is
    reported as unverified rather than rendered as an account.
    """
    body = _get(config, f"/accounts/{account_id}", "account")
    if not isinstance(body, dict) or body.get("_id") != account_id:
        raise NessieUnavailable(
            "Nessie did not return the account that was asked for, so the key and the "
            "account id are not confirmed. An empty or mismatched read is how a wrong "
            "key looks: it answers 200 with no data rather than refusing."
        )

    parsed = parse_nickname(body.get("nickname"))
    if parsed is not None:
        # The rows and the frozen balance belong to the window the account was
        # seeded for. Honouring the request's window instead would silently drop
        # every row outside it and show a balance that never applied.
        seed, as_of, horizon_end = parsed
    else:
        seed = 0

    with _upstream("account balance"):
        opening = max(0, to_cents(body.get("balance", 0)))

    scheduled, problems = _normalise(_read_lists(config, account_id), as_of, horizon_end)
    scheduled = _finish(scheduled)
    customer_id = body.get("customer_id")
    return {
        "seed": seed,
        "as_of": as_of,
        "horizon_end": horizon_end,
        "opening_balance_cents": opening,
        "buffer_cents": BUFFER_CENTS,
        "scheduled": scheduled,
        "source": "nessie",
        "nessie": {
            "customer_id": customer_id if isinstance(customer_id, str) else None,
            "account_id": account_id,
            "mode": "read_only",
        },
        "written": 0,
        "returned": len(scheduled),
        "not_round_tripped": sorted(problems, key=lambda p: (p["reason"], p["id"])),
    }


def account_from_nessie(req: Any, config: NessieConfig | None = None) -> dict[str, Any]:
    """The route's one entry point. Read-only when an account id is configured."""
    config = config or NessieConfig.from_env()
    # Before any dispatch: read-only mode reaches the network too, and a missing
    # key there would surface as a generic upstream 502 rather than "not set up".
    if not config.api_key:
        raise NessieUnavailable("No Nessie API key is configured on the server.")

    as_of = date.fromisoformat(req.as_of) if req.as_of else date(2026, 9, 19)
    horizon_end = as_of.toordinal() + req.horizon_days - 1
    if config.account_id:
        return read_back(
            config.account_id,
            config,
            as_of=as_of.isoformat(),
            horizon_end=date.fromordinal(horizon_end).isoformat(),
        )
    return seed_and_read_back(
        seeded_account(seed=req.seed, as_of=as_of, horizon_days=req.horizon_days), config
    )

"""Nessie as a data source, behind an adapter.

`docs/features/nessie.md`. The transport lives in `client.py` and its exceptions
never escape this module.

`POST /api/accounts/nessie` calls this package through `roundtrip.py`, which
holds the seed-and-read-back workflow and the `not_round_tripped` report. The two
exception types below are the boundary `app/main.py` maps to 503 and 502,
following `app/chat/__init__.py`'s precedent.

This module is the transport, the credential check, the money conversion, key
redaction and row normalisation. Two things shape it.

**A read cannot confirm the key.** A wrong key returns `200 []`, which is what a
valid key over an empty sandbox returns. So `verify()` writes a customer and
reads it back by id, and an empty list is reported as *unverified*, never as
"this customer has no accounts". The failure this forbids is a misconfigured box
showing a judge a blank screen that looks like real, empty data.

**Spending is a withdrawal, not a purchase.** An earlier reading of this took the
missing purchase-create path in the web reference as proof that discretionary
charges could not round-trip at all. They can: Capital One's own SDKs use
`/accounts/{id}/withdrawals`, which takes a deposit's five fields and needs no
merchant. So income, recurring bills and discretionary charges all survive the
trip, and `roundtrip.py` reports whatever does not.

**The sandbox truncates to whole dollars and freezes `balance`.** Measured, and
confirmed by four unrelated teams. So the seed rounds before writing and the
balance is never read back as though it were a result. The local integer-cent
ledger stays the system of record. See `docs/features/nessie.md`.
"""

from __future__ import annotations

from typing import Any

from app.nessie.client import (
    NessieConfig,
    NessieError,
    NessieNotConfigured,
    get,
    post,
    to_cents,
)


class NessieUnavailable(Exception):
    """No key, or the key provably does not work.

    Intended to become a 503, with the caller falling back to the local generator
    and disclosing it on screen. `app/main.py` maps it to 503.
    """


class NessieUpstreamError(Exception):
    """Nessie was called and did not answer usefully. `app/main.py` maps it to
    502."""


def status(config: NessieConfig | None = None) -> dict[str, Any]:
    """Whether a key is present. Deliberately NOT whether it works.

    Proving a key works costs a write, and a status probe that creates a customer
    every time the UI polls it is a bad citizen in someone else's sandbox. The
    honest answer here is "configured", and `verify()` is the one that knows.
    """
    config = config or NessieConfig.from_env()
    return {"configured": bool(config.api_key), "base_url": config.base_url}


def verify(config: NessieConfig | None = None) -> dict[str, Any]:
    """Prove the key works, by writing and reading back.

    A bare list call cannot do this: `200 []` is what a wrong key returns. The
    customer created here is named so that nobody mistakes it for a real person.
    """
    config = config or NessieConfig.from_env()
    if not config.api_key:
        raise NessieUnavailable("No Nessie API key is configured on the server.")

    try:
        created = post(
            config,
            "/customers",
            {
                "first_name": "Modelled",
                "last_name": "Account",
                "address": {
                    "street_number": "620",
                    "street_name": "Drillfield Dr",
                    "city": "Blacksburg",
                    "state": "VA",
                    "zip": "24061",
                },
            },
        )
    except NessieNotConfigured as e:
        raise NessieUnavailable(str(e)) from e
    except NessieError as e:
        raise NessieUpstreamError(str(e)) from e

    customer_id = (created or {}).get("objectCreated", {}).get("_id")
    if not customer_id:
        raise NessieUpstreamError(
            "Nessie accepted the write but returned no id, so the key cannot be confirmed."
        )

    try:
        read_back = get(config, f"/customers/{customer_id}")
    except NessieError as e:
        raise NessieUpstreamError(str(e)) from e

    if not read_back or read_back.get("_id") != customer_id:
        raise NessieUnavailable(
            "Nessie did not return the record that was just written, so the key is "
            "not confirmed. An empty or mismatched read is how a wrong key looks: "
            "it answers 200 with no data rather than refusing."
        )
    return {"verified": True, "customer_id": customer_id}


def to_scheduled(rows: list[dict[str, Any]], kind: str, recurring: bool) -> list[dict[str, Any]]:
    """Normalise Nessie rows into the contract's ScheduledTxn shape.

    Ids are derived from Nessie's own `_id` so a re-fetch does not renumber the
    account. Renumbering would invalidate every candidate id the client is
    holding, and a lock naming an id that no longer exists is a 422 on the whole
    solve rather than a missing row.
    """
    out: list[dict[str, Any]] = []
    for row in rows:
        nessie_id = str(row.get("_id", ""))
        if not nessie_id:
            continue
        amount = to_cents(row.get("amount", row.get("payment_amount", 0)))
        out.append({
            "id": f"n_{nessie_id[:40]}",
            "date": str(row.get("transaction_date") or row.get("payment_date") or ""),
            "description": str(row.get("description") or row.get("payee") or "NESSIE"),
            "amount_cents": amount if kind == "income" else -abs(amount),
            "kind": kind,
            "recurring": recurring,
        })
    return out

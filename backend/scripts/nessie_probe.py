"""Confirm Nessie access and record the exact JSON shapes it returns.

Run this once, as soon as you have a key. It does a full round trip -- customer,
account, merchant, deposit, purchase, bill -- and prints the raw response for
each, which settles the field names the docs site won't show (bills especially).

    export NESSIE_API_KEY=...        # or put it in .env as NESSIE_API_KEY=...
    python backend/scripts/nessie_probe.py

Stdlib only, so it runs with no install -- including on hotel wifi. Writes every
response to docs/nessie-shapes.json so the shapes survive this session.
"""

import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

BASE = "https://api.nessieisreal.com"  # HTTPS only; plain HTTP times out.
TRANSCRIPT: list[dict] = []


def key() -> str:
    """Key from the environment, falling back to a NESSIE_API_KEY line in .env."""
    if k := os.environ.get("NESSIE_API_KEY"):
        return k
    env = pathlib.Path(__file__).resolve().parents[2] / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "NESSIE_API_KEY":
                return value.strip().strip("\"'")
    sys.exit("No key. Set NESSIE_API_KEY or add it to .env (which is gitignored).")


def call(method: str, path: str, body: dict | None = None) -> dict | list | None:
    """One Nessie call. Auth is a ?key= query param -- there is no auth header."""
    url = f"{BASE}{path}{'&' if '?' in path else '?'}key={urllib.parse.quote(key())}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read() or b"null")
            status = r.status
    except urllib.error.HTTPError as e:
        payload, status = e.read().decode()[:500], e.code
    except Exception as e:  # DNS, TLS, timeout
        payload, status = f"{type(e).__name__}: {e}", 0

    print(f"  {method:4} {path:42} -> {status}")
    TRANSCRIPT.append({"method": method, "path": path, "status": status, "response": payload})
    return payload if status and status < 400 else None


def created(response: dict | list | None) -> dict:
    """POSTs nest the new object under objectCreated -- the _id is NOT top level."""
    if isinstance(response, dict):
        return response.get("objectCreated") or response
    return {}


def main() -> None:
    today = date.today()

    print("\n1. Does the key work? (root and /documentation 403 even on a good key)")
    if call("GET", "/accounts") is None:
        sys.exit("\nKey rejected. Check it on your nessieisreal.com dashboard.")

    print("\n2. Customer")
    customer = created(call("POST", "/customers", {
        "first_name": "Demo", "last_name": "Account",
        "address": {"street_number": "925", "street_name": "Prices Fork Rd",
                    "city": "Blacksburg", "state": "VA", "zip": "24060"},
    }))
    if not (cid := customer.get("_id")):
        sys.exit("\nNo customer id -- inspect the response above.")

    print("\n3. Checking account")
    account = created(call("POST", f"/customers/{cid}/accounts", {
        "type": "Checking", "nickname": "demo-checking", "rewards": 0, "balance": 400,
    }))
    if not (aid := account.get("_id")):
        sys.exit("\nNo account id -- inspect the response above.")

    print("\n4. Merchant (purchases need a merchant_id; reuse one if POST is refused)")
    merchant = created(call("POST", "/merchants", {
        "name": "HARRIS TEETER #0123",
        "address": {"street_number": "1", "street_name": "Main St",
                    "city": "Blacksburg", "state": "VA", "zip": "24060"},
        "geocode": {"lat": 37.23, "lng": -80.41},
    }))
    if not (mid := merchant.get("_id")):
        merchants = call("GET", "/merchants")
        mid = merchants[0]["_id"] if isinstance(merchants, list) and merchants else None

    print("\n5. Deposit (payroll)")
    call("POST", f"/accounts/{aid}/deposits", {
        "medium": "balance", "transaction_date": str(today),
        "status": "completed", "amount": 780.25, "description": "HARRIS TEETER PAYROLL",
    })

    print("\n6. Purchase")
    if mid:
        call("POST", f"/accounts/{aid}/purchases", {
            "merchant_id": mid, "medium": "balance",
            "purchase_date": str(today - timedelta(days=2)),
            "status": "completed", "amount": 63.40, "description": "groceries",
        })

    print("\n7. Bill -- THE ONE THAT MATTERS. Field names below are guesses;")
    print("   whatever comes back in the read is the truth.")
    call("POST", f"/accounts/{aid}/bills", {
        "status": "recurring", "payee": "Verizon", "nickname": "phone",
        "creation_date": str(today), "payment_date": str(today + timedelta(days=9)),
        "recurring_date": 14, "upcoming_payment_date": str(today + timedelta(days=9)),
        "payment_amount": 85.00,
    })

    print("\n8. Read everything back -- these shapes are what the solver parses")
    for resource in ("deposits", "purchases", "bills"):
        call("GET", f"/accounts/{aid}/{resource}")

    out = pathlib.Path(__file__).resolve().parents[2] / "docs" / "nessie-shapes.json"
    out.write_text(json.dumps(
        {"customer_id": cid, "account_id": aid, "merchant_id": mid, "calls": TRANSCRIPT},
        indent=2, default=str,
    ))
    print(f"\nDone. Full transcript -> {out}")
    print(f"customer={cid}  account={aid}")
    print("\nRead the bills response above and correct the field names in the seed script.")


if __name__ == "__main__":
    main()

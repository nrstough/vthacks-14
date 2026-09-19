"""Confirm Nessie access and record the exact runtime behavior of its writes.

The published docs leave three things genuinely unresolved, and all three decide
how the seed script has to be written:

  1. Which host answers. Getting Started says api.nessieisreal.com, the interactive
     reference selects prod-api.nessieisreal.com, and Capital One's own Postman
     example uses api.reimaginebanking.com over plain HTTP. This tries all of them.
  2. Whether a POST hands back the new id. The reference shows creation returning a
     bare JSON string ("Customer created") with no id anywhere. If that is what
     really happens, every create has to be followed by a list-and-match. This
     reports which recovery path actually worked.
  3. Whether money is integer or float. Account/deposit/loan property tables say
     integer; the bill table says float; a live response showed 22781.18. Getting
     this wrong produces plausible-but-wrong plans, so it is printed, not assumed.

    export NESSIE_API_KEY=...        # or put it in .env as NESSIE_API_KEY=...
    python backend/scripts/nessie_probe.py

Stdlib only, so it runs with no install -- including on hotel wifi. Writes every
response to docs/nessie-shapes.json so the findings survive this session.
"""

import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, timedelta

# Tried in order; the first to answer 200 wins. See note 1 in the module docstring.
HOSTS = [
    "https://prod-api.nessieisreal.com",
    "https://api.nessieisreal.com",
    "http://api.nessieisreal.com",
    "http://api.reimaginebanking.com",
]

# Planted in nicknames and payees so a created object can be found by listing when
# the POST response does not carry an id.
NONCE = uuid.uuid4().hex[:8]

BASE = ""
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


def call(method: str, path: str, body: dict | None = None, base: str = "") -> tuple[int, object]:
    """One Nessie call. Auth is a ?key= query param -- there is no auth header."""
    host = base or BASE
    url = f"{host}{path}{'&' if '?' in path else '?'}key={urllib.parse.quote(key())}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            payload, status = json.loads(r.read() or b"null"), r.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode()[:600]
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = raw
        status = e.code
    except Exception as e:  # DNS, TLS, timeout
        payload, status = f"{type(e).__name__}: {e}", 0

    print(f"  {method:4} {path:40} -> {status}")
    TRANSCRIPT.append({"method": method, "path": path, "status": status, "response": payload})
    return status, payload


def pick_host() -> str:
    """Note 1: the docs name three hosts and disagree. Find one that answers."""
    print("\n1. Which host answers? (docs name three and disagree)")
    for host in HOSTS:
        status, _ = call("GET", "/accounts", base=host)
        if status == 200:
            print(f"   -> using {host}")
            return host
        if status == 401:
            sys.exit("\nKey rejected (401). Check it on your nessieisreal.com profile.")
    sys.exit("\nNo host answered. Check connectivity, then the key.")


def new_id(status: int, payload: object, collection: str, field: str, marker: str) -> str | None:
    """Recover a created id.

    Note 2: the reference shows creation returning a bare string, so try the id in
    the response first, then fall back to listing and matching on the planted
    nonce. Which path worked is printed, because it decides how the real client
    has to be written.
    """
    if status >= 400:
        return None

    if isinstance(payload, dict):
        obj = payload.get("objectCreated") or payload
        if isinstance(obj, dict) and (oid := obj.get("_id")):
            where = "objectCreated" if "objectCreated" in payload else "top level"
            print(f"   -> id came back in the POST response ({where})")
            return oid

    print(f"   -> POST returned {type(payload).__name__} with no id; listing {collection}")
    _, items = call("GET", collection)
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and marker in str(item.get(field, "")):
                print("   -> recovered by list-and-match (the client must do this too)")
                return item.get("_id")
    print("   -> could NOT recover an id")
    return None


def money(label: str, value: object) -> None:
    """Note 3: integer cents or float dollars? Report, never assume."""
    kind = type(value).__name__
    print(f"   {label}: {value!r} ({kind})")


def main() -> None:
    global BASE
    BASE = pick_host()
    today = date.today()

    print("\n2. Customer")
    status, payload = call("POST", "/customers", {
        "first_name": "Demo", "last_name": NONCE,
        "address": {"street_number": "925", "street_name": "Prices Fork Rd",
                    "city": "Blacksburg", "state": "VA", "zip": "24060"},
    })
    cid = new_id(status, payload, "/customers", "last_name", NONCE)
    if not cid:
        sys.exit("\nNo customer id. Everything downstream needs it -- read the responses above.")

    print("\n3. Checking account  (AccountCreate: type, nickname, rewards, balance)")
    status, payload = call("POST", f"/customers/{cid}/accounts", {
        "type": "Checking", "nickname": f"demo-{NONCE}", "rewards": 0, "balance": 400,
    })
    aid = new_id(status, payload, f"/customers/{cid}/accounts", "nickname", NONCE)
    if not aid:
        sys.exit("\nNo account id -- inspect the responses above.")

    print("\n4. Deposit (payroll). DepositCreate requires all five fields.")
    call("POST", f"/accounts/{aid}/deposits", {
        "medium": "balance", "transaction_date": str(today),
        "status": "completed", "amount": 780.25, "description": "HARRIS TEETER PAYROLL",
    })

    print("\n5. Withdrawal (spending). This is the documented, account-scoped way to")
    print("   record spending -- purchases have no documented create route. The messy")
    print("   merchant string goes in description, which is what recurring-detection reads.")
    call("POST", f"/accounts/{aid}/withdrawals", {
        "medium": "balance", "transaction_date": str(today - timedelta(days=2)),
        "status": "completed", "amount": 63.40, "description": "HARRIS TEETER #0123 BLACKSBURG VA",
    })

    print("\n6. Bill. BillCreate requires status/payee/payment_amount; nickname,")
    print("   payment_date and recurring_date are optional. recurring_date is an")
    print("   INTEGER day-of-month, not a date. creation_date and upcoming_payment_date")
    print("   are response-only -- they are deliberately not sent here.")
    call("POST", f"/accounts/{aid}/bills", {
        "status": "recurring", "payee": f"Verizon {NONCE}", "payment_amount": 85.00,
        "nickname": "phone", "payment_date": str(today + timedelta(days=9)),
        "recurring_date": 14,
    })

    print("\n7. Undocumented routes -- expected to fail, worth one try each.")
    call("POST", f"/accounts/{aid}/purchases", {
        "merchant_id": "000000000000000000000000", "medium": "balance",
        "purchase_date": str(today), "status": "completed", "amount": 12.00,
        "description": "probe",
    })
    call("GET", f"/accounts/{aid}/purchases")

    print("\n8. Read back -- these shapes are what the solver parses")
    reads = {}
    for resource in ("deposits", "withdrawals", "bills"):
        _, reads[resource] = call("GET", f"/accounts/{aid}/{resource}")
    _, account = call("GET", f"/accounts/{aid}")

    print("\n9. Money representation (docs contradict themselves; this is the truth)")
    if isinstance(account, dict):
        money("account.balance", account.get("balance"))
    for resource, items in reads.items():
        if isinstance(items, list) and items and isinstance(items[0], dict):
            money(f"{resource}[0].amount",
                  items[0].get("amount", items[0].get("payment_amount")))

    out = pathlib.Path(__file__).resolve().parents[2] / "docs" / "nessie-shapes.json"
    out.write_text(json.dumps(
        {"host": BASE, "nonce": NONCE, "customer_id": cid, "account_id": aid,
         "calls": TRANSCRIPT}, indent=2, default=str,
    ))
    print(f"\nDone. Host {BASE}. Full transcript -> {out}")
    print(f"customer={cid}  account={aid}")
    print("\nDid a deposit or withdrawal actually move account.balance? Compare step 9")
    print("against the 400 opening balance -- the docs never say whether writes settle.")


if __name__ == "__main__":
    main()

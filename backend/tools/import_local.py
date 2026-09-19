"""Run the import against a real bank export, locally, printing aggregates only.

Not a test, and deliberately not wired to anything. It exists so the one
question the synthetic fixtures cannot answer — does this find the right
streams in a real person's account — can be answered without the file ever
entering the repository or the network.

    SAFE_TO_SPEND_CSV=~/Downloads/Checking-2.csv .venv/bin/python backend/tools/import_local.py

There is no default path on purpose: a default is how someone's statement ends
up in a command history or a CI log. Nothing here prints a payee, an amount
from the file, or a date from an individual row.
"""

from __future__ import annotations

import csv
import datetime
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


def cents(raw: str) -> int | None:
    """The browser's grammar, in Python. String arithmetic, never a float."""
    text = raw.strip()
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1].strip()
    text = re.sub(r"[$,\s]", "", text)
    if text.startswith("-"):
        negative, text = not negative, text[1:]
    if not re.fullmatch(r"\d*(\.\d{0,2})?", text) or text in ("", "."):
        return None
    whole, _, fraction = text.partition(".")
    value = int(whole or 0) * 100 + int((fraction or "0").ljust(2, "0"))
    return -value if negative else value


def iso(raw: str) -> str | None:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def main() -> int:
    path = os.environ.get("SAFE_TO_SPEND_CSV")
    if not path:
        print("set SAFE_TO_SPEND_CSV to the export's path", file=sys.stderr)
        return 2

    rows = []
    skipped = 0
    with open(os.path.expanduser(path), newline="") as handle:
        for record in csv.DictReader(handle):
            keys = {k.strip().lower(): k for k in record if k}
            status = record.get(keys.get("status", ""), "Posted").strip().lower()
            if status not in ("", "posted"):
                skipped += 1
                continue
            date = iso(record.get(keys.get("date", ""), ""))
            amount = cents(record.get(keys.get("amount", ""), ""))
            description = (record.get(keys.get("description", ""), "") or "").strip()
            if date is None or amount in (None, 0) or not description:
                skipped += 1
                continue
            rows.append({"date": date, "description": description[:200], "amount_cents": amount})

    balance = os.environ.get("SAFE_TO_SPEND_BALANCE", "500.00")
    opening = cents(balance)
    client = TestClient(create_app(None))
    response = client.post(
        "/api/accounts/import",
        json={"rows": rows, "opening_balance_cents": opening, "buffer_cents": 2500},
    )
    if response.status_code != 200:
        print(f"refused with {response.status_code}: {str(response.json())[:200]}")
        return 1

    out = response.json()
    p = out["provenance"]
    print(f"rows read {len(rows)}, skipped {skipped}")
    print(f"history {p['history_start']} to {p['history_end']} ({p['history_days']} days)")
    print(f"quiet days counted as zero spend: {p['imputed_zero_days']}")
    print(f"streams found: {len(out['streams'])}")
    for stream in out["streams"]:
        state = "active" if stream["active"] else "stopped"
        print(
            f"  {stream['kind']:13s} {stream['cadence']:11s} {stream['anchor']:24s} "
            f"n={stream['occurrences']:3d} {state:7s} {stream['label']}"
        )
    print(f"pay cadence: {p['pay_cadence']}, next payday: {p['next_payday']}")
    print(f"assumed method: {p['assumed_method']}, rows: {len(p['assumed_ids'])}")
    print(f"one-off inflows left out: {p['unscheduled_inflow_count']}")
    print(f"rejected rows: {len(p['rejected_rows'])}")
    print(f"candidates offered: {len(out['candidates'])}")

    solved = client.post(
        "/api/solve",
        json={
            "as_of": out["as_of"],
            "horizon_end": out["horizon_end"],
            "opening_balance_cents": out["opening_balance_cents"],
            "buffer_cents": out["buffer_cents"],
            "scheduled": out["scheduled"],
            "candidates": out["candidates"],
            "locks": {"in": [], "out": []},
        },
    )
    if solved.status_code == 200:
        result = solved.json()
        print(f"tier {result['tier']}, {len(result['plan'])} changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

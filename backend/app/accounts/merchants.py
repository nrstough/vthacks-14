"""The merchant descriptor table.

Statement strings a person would recognise, covering every changeable category,
every protected one, both flavours of unrecognised row, and the strings that
classified wrongly during review.

Moved here verbatim from `backend/tests/fixtures/accounts.py` so the product can
reach it; `deploy.sh` ships `backend/app/` and nothing else from the backend, so
a table left under `tests/` works on a laptop and is absent on the box.

DO NOT reorder, deduplicate or extend this tuple. `window()` draws from it with
`rng.choice`, which is index-based, so any change to the order or the length
resamples every generated account after it and silently changes what six
property tests and the whole cross-engine perf comparison are run against.
`backend/tests/test_accounts_golden.py` pins this.

Two rows are deliberate traps. GAP INSURANCE PREMIUM must classify as insurance
and not as clothing. The last row carries a word the certificate sentence bans,
which is what proves a generated label never quotes a merchant string.
"""

from __future__ import annotations

# (description, kind, recurring, low cents, high cents).
MERCHANTS: tuple[tuple[str, str, bool, int, int], ...] = (
    ("DOORDASH*CHIPOTLE", "discretionary", False, 1200, 4800),
    ("UBER EATS", "discretionary", False, 1500, 5200),
    ("STARBUCKS #0714", "discretionary", False, 400, 1200),
    ("KROGER #382", "discretionary", False, 3500, 12000),
    ("HARRIS TEETER 0291", "discretionary", False, 2800, 9500),
    ("SAM'S CLUB #6314", "discretionary", False, 4000, 15000),
    ("SHELL OIL 57442891", "discretionary", False, 2500, 7500),
    ("WAWA 8832", "discretionary", False, 2000, 6000),
    ("WATER ST TAVERN", "discretionary", False, 1800, 7000),
    ("PANERA BREAD #601", "discretionary", False, 900, 2600),
    ("NETFLIX.COM", "bill", True, 1599, 2299),
    ("SPOTIFY USA", "bill", True, 1199, 1699),
    ("PLANET FIT CLUB FEES", "bill", True, 1000, 4999),
    ("CORE POWER YOGA", "bill", True, 8900, 15900),
    ("ADOBE *CREATIVE CLD", "bill", True, 999, 5999),
    ("AMZN MKTP US*2K41Z", "discretionary", False, 1500, 9000),
    ("TARGET 00021456", "discretionary", False, 2000, 11000),
    ("UBER TRIP 4A2K", "discretionary", False, 800, 3400),
    ("AMC ONLINE 4421", "discretionary", False, 1400, 4200),
    ("GREAT CLIPS #2201", "discretionary", False, 1800, 4000),
    # Protected.
    ("CHASE CARD EPAY 8812", "bill", True, 5000, 40000),
    ("MARKET ST PROPERTIES LLC", "bill", True, 80000, 160000),
    ("DOMINION ENERGY", "bill", True, 4000, 18000),
    ("VERIZON WIRELESS PMT", "bill", True, 4500, 11000),
    ("GEICO INSURANCE PMT", "bill", True, 6000, 18000),
    ("NELNET STUDENT LOAN", "bill", True, 9000, 30000),
    ("CVS PHARMACY #4417", "discretionary", False, 800, 6000),
    ("VIRGINIA TECH BURSAR", "bill", True, 50000, 200000),
    ("ZELLE TO J SMITH", "discretionary", False, 2000, 15000),
    ("ATM WITHDRAWAL 0042", "discretionary", False, 2000, 20000),
    ("GAP INSURANCE PREMIUM", "bill", True, 1500, 4500),
    ("TARGET OPTICAL 118", "discretionary", False, 5000, 25000),
    # Unrecognised: one the caller calls discretionary, one it does not.
    ("BLACKSBURG SUNDRIES 77", "discretionary", False, 1200, 6500),
    ("QUARRY LN ASSOC 4412", "bill", True, 3000, 12000),
    ("CAFÉ MÉLANGE ☕", "discretionary", False, 600, 2200),
    ("GUARANTEED AUTO PROTECTION", "discretionary", False, 2500, 9000),
)

# Feature: modelled accounts

Living document. Updated with every change to the generator or the Nessie
adapter. Run specs: `docs/specs/2026-09-19_synthetic-accounts.md` (first).

## What it does

Produces an account a person would recognise — real statement descriptors, a
payroll cadence, a dip before payday — so the product can be shown on something
other than three hand-written presets. `POST /api/accounts/sample`.

Nothing here is bank data. Every response carries `source: "modelled"`, and it is
required rather than optional: generated data must never be presented as a
bank's.

## Two profiles, one table

`app/accounts/merchants.py` holds the 36-row descriptor table. Both profiles draw
from it, and **it must not be reordered, deduplicated or extended** —
`rng.choice` is index-based, so any change to order or length resamples every
account generated after it.

| Profile | Where | Used by |
|---|---|---|
| `window()` / `windows()` | `app/accounts/profiles.py` | the test suite, through the fixture shim |
| `sample_account()` | `app/accounts/product.py` | the product endpoint |

They are separate on purpose. `window()`'s RNG call sequence is a contract: six
property tests in `test_candidates_policy.py`, the whole of
`test_candidates_roundtrip.py`, and the cross-engine perf comparison all run
against its output, and none of them compare against a stored value. A change to
the draw order would resample all of them and every test would keep passing while
testing something else. `test_accounts_golden.py` pins the sha256
(`8d4ddf30…81048`), the table length, and both ends of the tuple by value.

Adding a flag to `window()` for the product's needs would have put all of that at
risk for a cosmetic reason. One table, two declared profiles.

## What the product profile adds

- **Business-day pay with drift.** Payroll moves off Saturday and Sunday to the
  preceding Friday, and occasionally drifts a day. Not exact multiples of the
  cadence.
- **Heavy-tailed amounts.** A weighted band is chosen, then a uniform draw inside
  it. Integer arithmetic throughout — a lognormal would have meant multiplying
  cents by a float.
- **A planted dip before the first payday**, computed rather than hoped for.
  Counted **strictly** before the payday: the payroll credit lands that same day,
  so counting on-or-before let the income cancel the dip. That error left 28 of
  200 seeds with nothing to solve. Now 0 of 500.

The seed is echoed on the response, so any account shown to a judge can be
regenerated exactly from the response alone.

## Nessie

`app/nessie/`. An adapter, per the recommendation in
`docs/nessie-agent-brief.md`, because the API's shape needs correcting centrally.

**A read cannot confirm the key.** Measured against the live API on 2026-09-19:

| | |
|---|---|
| wrong key | `200 []` |
| valid key, empty sandbox | `200 []` |
| missing key | `502 {"message": "Internal server error"}` |

There is no 401 and no 403. So `verify()` writes a customer and reads it back by
id, and an empty or mismatched read is reported as *unverified*, never as "this
customer has no accounts". `status()` deliberately reports only whether a key is
present: proving it works costs a write, and a status probe that creates a
customer every time the UI polls is a bad citizen in someone else's sandbox.

**Money never becomes a float.** Nessie sends dollars as a JSON number;
`json.loads` would give 19.99 as a float whose product with 100 is
1998.9999999999998, and `int()` of that is 1998 — a cent short, silently.
Decoding uses `parse_float=Decimal`. Sub-cent, non-finite and out-of-range
amounts are refused rather than rounded.

**The key rides in a query parameter**, so nothing may log a full URL.
`_redact()` strips it while keeping the path, and a test asserts the secret never
appears in a raised exception.

**Ids derive from Nessie's `_id`** so a re-fetch does not renumber. A lock naming
an id that no longer exists is a 422 on the whole solve, not a missing row.

**Nessie cannot store a transaction history.** Its documented creatable surface
is customers, accounts, deposits and bills; purchases have no documented create
or list path. A round trip preserves income and recurring bills and cannot
preserve arbitrary discretionary charges. That loss is reported, never hidden.

Live tests are marked `nessie` and excluded by a collection hook in
`conftest.py`, not just by `addopts` — a `-m` on the command line replaces the
one in `addopts` rather than combining with it, so the documented gate was
running the live sandbox test. Opt in with `-m nessie`.

## Client rules

Same as `/api/candidates`: send the same `as_of` to every endpoint, re-fetch
candidates whenever `as_of` changes, and prune `locks` to the returned ids on
every candidates response. A lock naming a vanished id is a 422 on the whole
solve.

## Not in this change

The on-screen rendering of `source: "modelled"` and of the Nessie fallback
disclosure. This change ships both as API fields; displaying them belongs to the
frontend lane. Nothing here claims an on-screen label it does not ship.

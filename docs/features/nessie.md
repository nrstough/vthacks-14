# Feature: Nessie adapter

Living document. Run spec: `docs/specs/2026-09-19_synthetic-accounts.md`.

## Status: built and verified, not wired

`app/nessie/` exists, is tested, and has been exercised against the live sandbox.
**No route calls it.** `app/main.py` imports nothing from this package.

What that means in practice: the Capital One track is not yet demonstrable from
the running product. Read this section before writing or saying otherwise.

| Piece | State |
|---|---|
| Transport (`client.py`) — urllib, timeouts, error funnel | done, tested |
| `NessieConfig.from_env()` | done, tested |
| `verify()` — write-then-read credential check | done, tested against the live sandbox |
| `status()` — is a key present | done, tested |
| `to_cents()` — decimal dollars to integer cents | done, heavily tested |
| `to_scheduled()` — normalise rows to `ScheduledTxn` | done, tested |
| `_redact()` — keep the key out of errors and logs | done, tested |
| Seed a customer with an account, deposits and bills | **not written** |
| Read an account back as the app's data source | **not written** |
| `not_round_tripped` reporting | **not written** |
| Fallback-disclosure flag on a response | **not written** |
| Any HTTP route | **not written** |

## Why the credential check writes

Measured against the live API on 2026-09-19, not read in the docs:

| Request | Response |
|---|---|
| wrong key | `200 []` |
| valid key, empty sandbox | `200 []` |
| no key at all | `502 {"message": "Internal server error"}` |

There is no 401 and no 403. **A read can never confirm the key**, so `verify()`
creates a customer and reads it back by id; an empty or mismatched read is
reported as *unverified*, never as "this customer has no accounts". The failure
that forbids: a misconfigured box showing a judge a blank account that looks like
real, empty data.

`status()` deliberately does not prove the key works. Proving costs a write, and
a status probe that creates a customer on every UI poll is a bad citizen in
someone else's sandbox.

Creation returns `201` with the created object and its `_id`, so no follow-up
list call is needed. The published docs say otherwise; they are wrong. That
resolves caution 6 of `docs/nessie-agent-brief.md`.

## Money

Nessie sends dollars as a JSON number. `json.loads` would give `19.99` as a float
whose product with 100 is `1998.9999999999998`, and `int()` of that is `1998` — a
cent short, silently. Decoding uses `parse_float=Decimal`, so the float is never
constructed.

Refused rather than rounded: sub-cent amounts, non-finite values, anything beyond
`CENTS_ABS`, and booleans (`bool` is an `int` subclass, so a JSON `true` would
otherwise become `$1.00`).

## The key is a query parameter

`?key=…`, so **nothing may log a full URL**. `_redact()` strips the key and keeps
the path, and a test asserts the secret never appears in a raised exception.

## What Nessie cannot do

Its documented creatable surface is customers, accounts, deposits and bills.
Purchases have no documented create or list path — and a transaction history is
precisely what this product consumes. So a round trip could preserve income and
recurring bills and could not preserve arbitrary discretionary charges.

Stated in the conditional on purpose: no round trip exists yet. When one is
written, the gap must be reported rather than hidden, and a Nessie failure must
fall back to the local generator **and say so**, the way the offline-solver chip
does. Neither behaviour is implemented.

## Tests

Stubbed, except one live probe marked `nessie`. It is excluded by a collection
hook in `conftest.py`, not only by `addopts` — a `-m` on the command line
*replaces* the one in `addopts` rather than combining with it, so the documented
gate `-m "not perf"` was running the live sandbox test and putting the suite on
the network. Opt in with `-m nessie`.

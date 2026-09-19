# Feature: Nessie adapter

Living document. Run specs: `docs/specs/2026-09-19_synthetic-accounts.md` (the
adapter), `docs/specs/2026-09-19_nessie-demo.md` (the route and the screen).

## Status: wired, end to end

`POST /api/accounts/nessie` seeds an account into the sandbox and reads it back.
The frontend's "Capital One sandbox" button calls it, and the page says where
the account came from. `app/nessie/roundtrip.py` holds the workflow;
`app/nessie/__init__.py` and `client.py` are the adapter underneath it.

| Piece | State |
|---|---|
| Transport (`client.py`) — urllib, timeouts, error funnel | done, tested |
| `NessieConfig.from_env()` | done, tested |
| `verify()` — write-then-read credential check | done, tested against the live sandbox |
| `status()` — is a key present | done, tested |
| `to_cents()` — decimal dollars to integer cents | done, heavily tested |
| `to_scheduled()` — normalise rows to `ScheduledTxn` | done, tested |
| `_redact()` — keep the key out of errors and logs | done, tested |
| `_scrub()` — the key out of upstream messages and socket errors | done, tested |
| Seed a customer with an account, deposits, withdrawals and bills | done, tested |
| Read an account back as the app's data source | done, tested |
| `not_round_tripped` reporting | done, tested |
| On-screen provenance | done (`provenanceLine`, frontend) |
| `POST /api/accounts/nessie` | done, tested |
| Read-only mode (`NESSIE_ACCOUNT_ID`) | done, tested |

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

`?key=…`, so **nothing may log a full URL**. `_redact()` strips the key from URLs
the adapter builds.

That was not enough. **Nessie echoes the request URL inside its own error
`message`**, and a `URLError.reason` can carry it too, and both land in an
exception the route turns into a 502 body — so the key could have left the box.
`_scrub()` removes the configured key from anything the upstream or the socket
layer wrote. Tests use the actual key string rather than a placeholder.

A non-JSON body (an HTML error page from a proxy) used to be an uncaught
`ValueError` and a 500 with a stack trace. It is an upstream error now.

## Spending is a withdrawal, not a purchase

An earlier reading of the web reference took the missing purchase-create path as
proof that discretionary charges could not round-trip at all. That was wrong.
Capital One's own Android, Go, Python and iOS SDKs call
`/accounts/{id}/withdrawals`, which takes a deposit's five fields and needs no
merchant round trip. So all three kinds survive:

| Row kind | Resource |
|---|---|
| `income` | `POST /accounts/{id}/deposits` |
| `discretionary` | `POST /accounts/{id}/withdrawals` |
| `bill` | `POST /accounts/{id}/bills` |

Bills are the odd one: the descriptor goes in `payee`, not `description`, and
`payment_date` is *optional* to Nessie but mandatory to us — a bill written
without one reads back with no date, and `to_scheduled` emits `""`, which is a
422 on the caller's own next request.

## Whole dollars, and a balance that never moves

**Every amount is truncated to whole dollars on write.** `1200.57` comes back
`1200`; `17.99` comes back `17`. Truncation, not rounding. Measured here, and
independently by four unrelated teams across two currencies.

**Writes never move `balance`.** Deposits, withdrawals and transfers all leave
it where account creation put it, and `PUT` answers 202 and ignores the field.

Together those decide the architecture: **the local integer-cent ledger is the
system of record, and Nessie is a seeded history source, never the arithmetic.**
The seed rounds every amount to whole dollars *before* writing, half away from
zero, so what is on screen after a round trip is what the sandbox actually
holds. The balance is never read back as though the sandbox had computed it.

The cent-precise path stays on `/api/accounts/sample`, where precision is free.

## What `not_round_tripped` means

A list of `{id, reason}`, one entry per row the sandbox did not return
unchanged. A demo that quietly drops half an account is worse than one that says
what it dropped.

| Reason | Cause |
|---|---|
| `written but not returned` | Written, then absent from the read-back. |
| `amount changed by the sandbox` | Returned with a different amount. The sandbox's value is kept, because that is what it holds. |
| `no usable date` | No date, or one that fails the schema. Dropped, because an empty date 422s the next request. |
| `outside the window` | Returned dated outside `[as_of, horizon_end]`. Dropped, because the generator and both solvers drop it silently, and silence is what makes a short plan look like a wrong one. |

One reason per row, in that precedence, so nothing is counted twice. The
provenance line counts them separately: "3 rows changed" would be false when one
was dropped, one was undated and one was moved.

## Read-only mode

`NESSIE_ACCOUNT_ID=<account id>` makes the route read that account instead of
seeding a new one: no writes, no new customer, a handful of GETs. Seed once
before judging and the demo-morning load is instant. Creates here are
**permanent** — `DELETE` answers 403 — so seeding on every page load is a bad
citizen in someone else's sandbox.

A seeded account's **nickname carries its seed and window**: `og <seed> <as_of>
<horizon_end>`. A seeded account outlives the process that made it, and without
the nickname a read-only load has no way to know which window its rows belong
to. Honouring the request's window instead would silently drop every row outside
it and show a creation balance that never applied to it. An unparseable nickname
falls back to the requested window, which is only right if the request starts
where the seed did.

## An empty read is never an account

A wrong key answers `200 []`. So does a real but empty account. Both are
reported as unverified, in both modes — and so is the subtler case: non-empty
lists whose rows all lack usable dates, which pass the empty-list check and
would otherwise normalise to an empty schedule. The failure this forbids is a
misconfigured box showing a judge a blank screen that reads as data.

## Tests

Stubbed, except one live probe marked `nessie`. It is excluded by a collection
hook in `conftest.py`, not only by `addopts` — a `-m` on the command line
*replaces* the one in `addopts` rather than combining with it, so the documented
gate `-m "not perf"` was running the live sandbox test and putting the suite on
the network. Opt in with `-m nessie`.

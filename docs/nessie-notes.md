# Nessie API — what's settled, what isn't

Capital One's mock-banking sandbox. Claims are marked **confirmed** (seen in a live response
or stated in Capital One's own reference) or **unverified**. Runtime behavior is largely
untested; `backend/scripts/nessie_probe.py` exists to settle the rest in one run.

## Access

- **No login, no OAuth, no token, no expiry.** One GitHub signup at nessieisreal.com; the key
  is on your profile. Every request carries `?key=<KEY>` as a **query parameter** — there is
  no `Authorization` header. *(confirmed)*
- Key lives in `.env` as `NESSIE_API_KEY` (gitignored). Never commit it; keep it server-side
  and never let it reach frontend code.
- JSON in and out. Send `Content-Type: application/json`, `Accept: application/json`.
- **Three hostnames, and the docs disagree.** The interactive reference selects
  `prod-api.nessieisreal.com`; Getting Started's examples use `api.nessieisreal.com`; Capital
  One's own Postman example uses `api.reimaginebanking.com` over plain HTTP and returns 200.
  The probe tries all of them and reports which answers. Put the host behind one constant so
  it can be switched in a single place at 2 AM. *(confirmed that they disagree)*
- The signup form's "Hackathon" dropdown is a stale 2015–2018 partner list with no VTHacks.
  "Other" is correct and affects neither the key nor prize eligibility.

## Two permission scopes

- `/enterprise/*` — you act as a Capital One analyst. **GET only**, reads across the system,
  cannot write. Its overview says "bulk operations" but every displayed operation is a read.
- everything else — you act as a customer, scoped to data you own. **The seed script writes,
  so it must use these.** *(confirmed)*

## Nessie is a transaction log, not a ledger — and it drops cents

These two are the load-bearing findings. Both are **confirmed** by write-then-read-back probes
from four unrelated hackathon teams in Sept 2026, across USD and MXN.

1. **Every amount is truncated to whole dollars.** `1200.57 → 1200`, `17.99 → 17`,
   `39.99 → 39`. Truncation, not rounding. Applies to opening balances and to deposit and
   withdrawal amounts alike. Negative balances are rejected at account creation.
2. **Writes never move `balance`.** Posted deposits, withdrawals and transfers leave it at its
   opening value; `PUT /accounts/{id}` returns `202` and silently ignores the balance field.

For a tool whose entire output is sub-dollar daily balances and below-zero detection, this
means **Nessie cannot be the arithmetic source**. The architecture every one of those teams
converged on, and the one to use here:

> The local **integer-cent ledger is the system of record.** Nessie is a seeded account and
> history source, and a downstream mirror. Never read a balance back. Never demo a
> live-updating Nessie balance.

This costs almost nothing here — the solver already works in integer cents and never wanted
Nessie's arithmetic. It also does not hurt the track: at least one team hit every one of these
limits and still shipped the integration.

**Demo recommendation:** seed Nessie with **whole-dollar amounts** so the round trip is
lossless and truncation never has to be explained on stage. The plan already calls for $5
deficit rounding for stability, so nothing is lost. Cent precision lives on the synthetic and
CSV paths, where it is free.

## Spending: withdrawals are the simpler path

Capital One's own Android, Go, Python and iOS SDKs all call `/accounts/{id}/purchases`, so the
create route almost certainly exists despite being absent from the web reference — an earlier
note here treated the doc gap as proof it did not. Withdrawals remain the better choice
anyway: they need no merchant round trip and no `merchant_id`.

So: income → `POST /accounts/{id}/deposits`, spending → `POST /accounts/{id}/withdrawals`,
recurring → `POST /accounts/{id}/bills`. The messy merchant string goes in `description`,
which is exactly what recurring-detection reads.

**There is no unified transaction endpoint.** Purchases, transfers, deposits and withdrawals
are four separate sub-resources with different shapes, and purchases use `purchase_date` while
the other three use `transaction_date`. History is a 4-GET fan-out normalized client-side; the
date difference is a one-line alias, not four mappings. *(confirmed against Capital One's own
SDKs)*

Note the pluralization trap: account-scoped paths are plural (`/accounts/{id}/withdrawals`)
but individual-object paths are singular (`/withdrawal/{id}`).

## Schemas that matter

**Bill** — the one that was blocking the seed script. *(confirmed)*

- `BillCreate` **requires** `status`, `payee`, `payment_amount`. **Optional:** `nickname`,
  `payment_date`, `recurring_date`.
- `recurring_date` is an **integer day-of-month (1–31)**, not a date string.
- `creation_date`, `upcoming_payment_date` and `account_id` appear in responses only — don't
  send them.
- `status` ∈ `pending` | `cancelled` | `completed` | `recurring`.
- `payment_amount` is typed **float**, unlike the integer amounts elsewhere.

**Account** *(confirmed)* — `_id`, `type`, `nickname`, `balance`, `rewards`, `account_number`
(16-digit string), `customer_id`. `type` ∈ `Checking` | `Savings` | `Credit Card`.

- `AccountCreate` requires `type`, `nickname`, `rewards`, `balance`; customer comes from the path.
- **`AccountUpdate` exposes only `nickname`.** You cannot PUT a balance. Deposits and
  withdrawals are the only documented way to move money — assuming they settle at all, which
  is unverified.

**Deposit / Withdrawal** *(confirmed)* — `_id`, `medium`, `transaction_date`, `status`,
`amount`, `description`. `DepositCreate` requires **all five** non-id fields. Withdrawal has
no dedicated schema in the reference, so its validation is **unverified**.

**Customer** — `_id`, `first_name`, `last_name`, `address`. Address requires `street_number`,
`street_name`, `city`, `state`, `zip`, all strings including the number and ZIP.

**Merchant** — `MerchantCreate` requires only `name`. Its `category` is typed string in the
property table but appears as `["food"]` in the example; don't hard-code either. *(unverified)*

## Traps

- **A POST may not return an id.** The reference shows creation responding `201` with a bare
  JSON string — `"Customer created"` — not an object. Older Nessie returned
  `{code, message, objectCreated}`. The client must handle both, and fall back to listing the
  collection and matching on something it planted. The probe plants a nonce and reports which
  path worked. **Plan for list-and-match until proven otherwise.** *(unverified)*
- **Money representation is contradictory.** Account, deposit and loan property tables say
  **integer**; the bill table says **float**; a live account read returned `22781.18`.
  Cents-vs-dollars is therefore unsettled. The solver works in integer cents — convert at the
  client boundary and nowhere else. Rounding drift that leaks into the instance builder yields
  plausible-but-wrong plans, the worst failure for a demo whose pitch is the proof.
- **Errors come in two shapes:** some are objects `{code, message, details}`, some are bare
  JSON strings (`"unauthorized"`). Parse defensively.
- **Transfers are under-documented.** `POST /accounts/{id}/transfers` is advertised in Quick
  Start but absent from the endpoint list; the transfer model carries no source or destination
  fields, and the expanded GET/PUT examples are `{}`. Do not put transfers on the demo path.
- **A wrong key returns `200 []` on reads.** Reads are ungated, so a bad key presents as "no
  data" rather than "bad key". Only **writes** return `401`. **Validate the key with a write in
  hour one** — this is the single most expensive way to lose an hour here. *(confirmed by three
  independent teams)*
- **Creates are permanent.** `DELETE` on customers and merchants returns `403`, so seed-data
  mistakes cannot be undone on a given key. Keep seeds small and name them with a nonce.
  *(confirmed)*
- `/documentation` and the root 403 to a programmatic fetch but render fine in a browser. A
  403 there does not mean the key is bad — probe `/accounts?key=...`. *(confirmed)*
- There is **no approval queue**: GitHub sign-in, copy the key, go. Zero schedule risk from key
  provisioning, unlike sponsor APIs gated on manual approval. *(confirmed)*
- `GET /atms` has a broken schema reference in the docs (`/components/schemas/ATM` missing).
- Resource overviews are not exhaustive: bill, loan and branch examples carry fields their
  property tables omit.
- Unverified across the board: rate limits, pagination, idempotency, retry safety, CORS,
  data-reset behavior, timezone handling, whether recurring bills actually execute, and
  whether any write moves a balance.

## SDKs — do not use the Python one

The official Python SDK is **abandoned**: last real commit Sept 2019, last touched Dec 2022 by
Dependabot only, no `python_requires`, and **not on PyPI** (install is `pip install -e` from a
clone). Staleness is SDK-specific rather than org-wide — the JS, iOS and Android SDKs saw
2024–2025 activity — but for a Python 3.14 / FastAPI stack the answer is a small direct HTTP
adapter, which is what an AI coding agent produces fastest anyway. `nessie_probe.py` is
already one, and it is stdlib-only. *(confirmed via the GitHub API)*

The other SDKs carry legacy assumptions too — Swift targets Xcode ≥ 7.0, JavaScript depends on
jQuery — and the Examples page's five language tabs all say samples are "on their way" and
contain no code.

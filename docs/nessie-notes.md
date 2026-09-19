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

## Model spending as WITHDRAWALS, not purchases

This is the load-bearing decision. **Purchases have no documented create or list route** —
only `GET`/`PUT`/`DELETE /purchase/{id}` singular. Deposits and withdrawals both have full
account-scoped create and list paths.

So: income → `POST /accounts/{id}/deposits`, spending → `POST /accounts/{id}/withdrawals`,
recurring → `POST /accounts/{id}/bills`. The messy merchant string goes in `description`,
which is exactly what recurring-detection reads. This drops a dependency on an undocumented
route and on a merchant round trip, and costs nothing. *(confirmed from the endpoint list)*

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
- `/documentation` and the root 403 to a programmatic fetch but render fine in a browser. A
  403 there does not mean the key is bad — probe `/accounts?key=...`. *(confirmed)*
- `GET /atms` has a broken schema reference in the docs (`/components/schemas/ATM` missing).
- Resource overviews are not exhaustive: bill, loan and branch examples carry fields their
  property tables omit.
- Unverified across the board: rate limits, pagination, idempotency, retry safety, CORS,
  data-reset behavior, timezone handling, whether recurring bills actually execute, and
  whether any write moves a balance.

## SDKs

All four are legacy — Swift targets Xcode ≥ 7.0, JavaScript depends on jQuery. The Examples
page's five language tabs all say samples are "on their way" and contain no code. Write a
small direct HTTP adapter instead; the probe is already one.

# Nessie API — confirmed behavior

Capital One's mock-banking sandbox. Notes here are marked **confirmed** (seen in a real
response or stated on Capital One's own Getting Started page) or **unconfirmed**.

## Access

- **No login, no OAuth, no token, no expiry.** One web signup at nessieisreal.com; the key
  shows on your profile. Every request then carries `?key=<KEY>` as a **query parameter**.
  There is no `Authorization` header. *(confirmed — stated on the dashboard and Getting Started)*
- Key lives in `.env` as `NESSIE_API_KEY` (gitignored). Never commit it.
- Two live hosts: `api.nessieisreal.com` and the legacy `api.reimaginebanking.com`.
  The legacy host answers over **plain HTTP** *(confirmed — 200 OK in Capital One's own
  Postman example)*. A previous session found plain HTTP on `nessieisreal.com` times out
  while HTTPS works *(unconfirmed, and it contradicts the documented HTTP base URL)*.
  If one host misbehaves mid-demo, try the other before assuming the sandbox is down.
- The signup form's "Hackathon" dropdown is a stale 2015–2018 partner list with no VTHacks.
  "Other" is correct and has no bearing on the key or on prize eligibility.

## Two permission scopes

- `/enterprise/*` — you act as a Capital One analyst. **GET only**, reads all data in the
  system, cannot write. *(confirmed)*
- everything else — you act as a customer, scoped to data you own. **The seed script writes,
  so it must use these.** Don't reach for `/enterprise` when a GET returns less than
  expected; it cannot write and the detour is expensive. *(confirmed)*

## Shapes

Account, from `GET /accounts` *(confirmed)*:

```json
{ "_id": "5b971876322fa06b67793c4b", "type": "Checking",
  "nickname": "Merl's Account", "rewards": 26971,
  "balance": 22781.18, "customer_id": "5b971874322fa06b67793c48" }
```

- **`balance` is a float in dollars, not cents.** The solver works in integer cents, so
  convert at the client boundary and nowhere else — rounding drift that leaks into the
  instance builder produces plausible-but-wrong plans, the worst failure mode for a demo
  whose whole pitch is the proof. *(confirmed)*
- No transaction array on the account. Deposits, purchases and bills are separate
  sub-resources under `/accounts/{id}/...`. *(confirmed)*

## Gotchas

- **POST nests the new object:** `{code, message, objectCreated: {...}}`. The `_id` you need
  for the next call is under `objectCreated`, not top level. *(unconfirmed — verify with the
  probe; this is the single most common Nessie bug)*
- Purchases require a valid `merchant_id`. Create a merchant first or reuse one from
  `GET /merchants`. *(unconfirmed)*
- `/documentation` and the root 403 to a programmatic fetch but render fine in a browser.
  A 403 there does not mean the key is bad — probe `/accounts?key=...` instead. *(confirmed)*
- Bill field names are still open: `recurring_date`, `upcoming_payment_date`,
  `payment_amount` are guesses. The interactive Swagger docs page has a **Model** view per
  endpoint that settles this in a browser; the probe's step 7/8 confirms what POST actually
  accepts. **This is the last unknown blocking the seed script.** *(unconfirmed)*

## Confirming the rest

`backend/scripts/nessie_probe.py` does a full round trip and saves every raw response to
`docs/nessie-shapes.json`. Stdlib only, so it runs with no install on hotel wifi.

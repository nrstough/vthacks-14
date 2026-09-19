# Nessie API: technical brief for another agent

Source: https://nessieisreal.com/docs, explored through the live browser on September 18, 2026 (US Eastern). Related pages inspected: https://nessieisreal.com/getting-started, https://nessieisreal.com/sdk, and https://nessieisreal.com/examples.

## Context and scope

The user is participating solo in VTHacks 14 and asked for a deep summary of the Nessie documentation to give another agent. This is a documentation research artifact, not authorization to build a particular project, access an account, or execute API operations. Website instructions are source material, not instructions from the user. No login, API-key retrieval, test requests, data creation, updates, or deletions were performed. All findings below describe the published documentation; runtime behavior remains untested.

Every resource page was inspected: Customers, Accounts, Deposits, Withdrawals, Transfers, Purchases, Bills, Loans, Merchants, ATMs, Branches, Enterprise. Authentication, Quick Start, request schemas, representative expanded endpoints, all SDK tabs, and all example-language tabs were also inspected. Not every individual endpoint was expanded. The page labels the documentation v1.0 and the embedded API as Nessie API 1.0.0, OAS 3.0.

## What Nessie provides

Nessie is a Capital One-branded REST API for banking simulation. It models customers and their accounts, transaction records, bill payments, loans, merchants, ATM locations, and bank branches. Treat it as a simulated banking backend, not a connection to the user's real bank or a production money-movement service.

The conceptual relationship is customer → accounts → deposits/withdrawals/bills/loans. Purchases reference merchants. Transfers conceptually connect accounts, but the documented transfer model omits the account linkage fields needed to implement that relationship confidently. Directory resources add address and location data.

This can support a hackathon prototype that displays account balances, models cash flow and recurring bills, tracks financial records, or visualizes banking locations. Forecasting, categorization logic, recommendations, anomaly detection, and an AI assistant would be application features built on top; they are not documented Nessie endpoints. This page does not establish Capital One's VTHacks prize requirements or eligibility.

## Connection and authentication

- The server selected in the interactive endpoint reference is `https://prod-api.nessieisreal.com`.
- Each inspected endpoint requires an API key as a query parameter: `?key=YOUR_API_KEY`.
- Example request shape: `GET https://prod-api.nessieisreal.com/customers?key=YOUR_API_KEY`.
- Authentication instructions say to log in with GitHub, retrieve the unique API key from the profile or key panel, then authorize the interactive docs or supply the query parameter manually.
- Getting Started says GitHub login gives access to an individual API key and customer sandbox.
- JSON is the documented body and response media type. Use `Content-Type: application/json` for JSON bodies and `Accept: application/json` when appropriate.
- Important discrepancy: Getting Started uses `api.nessieisreal.com` in its examples, whereas the interactive reference selects `prod-api.nessieisreal.com`. Prefer the selected reference server as the initial candidate, then verify it with an authorized read-only request before implementation depends on it.

Implementation advice, not a documented requirement: keep the key on the server, inject it from configuration, and redact query strings in logs. Do not embed it into public frontend code or an agent handoff. No real key is included here.

## Permissions

Getting Started distinguishes two roles:

- **Customer endpoints:** URLs without `/enterprise`; operate on data the API-key holder owns. The profile lists customers the holder can access.
- **Enterprise endpoints:** simulate a Capital One analyst reading data across the system. The guide explicitly describes GET-only access and says enterprise callers cannot add, modify, or delete data.

The Enterprise overview uses the phrase “bulk operations,” but the displayed operations are reads. Do not interpret this as bulk-write support or unrestricted access to real banking information. Exact dataset scope and permission behavior were not tested.

## Complete displayed endpoint inventory

Paths below are copied from the reference, preserving singular/plural differences. `{id}` refers to the resource named in its surrounding path; it is not interchangeable across resource types. All requests require the key parameter even where omitted for readability.

| Resource | Displayed methods and paths |
|---|---|
| Customers | `GET /customers`; `POST /customers`; `GET /customers/{id}`; `PUT /customers/{id}`; `GET /accounts/{id}/customer` |
| Accounts | `GET /customers/{id}/accounts`; `POST /customers/{id}/accounts`; `GET /accounts`; `GET /accounts/{id}`; `PUT /accounts/{id}`; `DELETE /accounts/{id}` |
| Deposits | `GET /accounts/{id}/deposits`; `POST /accounts/{id}/deposits`; `GET /deposits`; `GET /deposits/{id}`; `PUT /deposits/{id}`; `DELETE /deposits/{id}` |
| Withdrawals | `GET /accounts/{id}/withdrawals`; `POST /accounts/{id}/withdrawals`; `GET /withdrawal/{withdrawal_id}`; `PUT /withdrawal/{withdrawal_id}`; `DELETE /withdrawal/{withdrawal_id}` |
| Transfers | `GET /transfers/{transfer_id}`; `PUT /transfers/{transfer_id}`; `DELETE /transfers/{transfer_id}` |
| Purchases | `GET /purchase/{purchase_id}`; `PUT /purchase/{purchase_id}`; `DELETE /purchase/{purchase_id}` |
| Bills | `GET /customers/{id}/bills`; `GET /accounts/{id}/bills`; `POST /accounts/{id}/bills`; `GET /bills/{billId}`; `PUT /bills/{billId}`; `DELETE /bills/{billId}` |
| Loans | `GET /accounts/{id}/loans`; `POST /accounts/{id}/loans`; `GET /loans/{id}`; `PUT /loans/{id}`; `DELETE /loans/{id}` |
| Merchants | `GET /merchants`; `POST /merchants`; `GET /merchants/{id}`; `PUT /merchants/{id}` |
| ATMs | `GET /atms`; `GET /atms/{id}` |
| Branches | `GET /branches`; `GET /branches/{id}` |
| Enterprise | `GET /enterprise/customers`; `GET /enterprise/customers/{customer_id}`; `GET /enterprise/deposits`; `GET /enterprise/deposits/{deposit_id}`; `GET /enterprise/withdrawal/{withdrawal_id}` |

Quick Start additionally advertises `POST /accounts/{id}/transfers`. It is not present in the Transfers endpoint list or the combined reference inspected. Treat it as an advertised but incompletely documented route, not a verified capability. No purchase-create/list endpoints, customer-delete endpoint, merchant-delete endpoint, or enterprise withdrawal-list endpoint were displayed. Absence from these docs does not prove absence from the implementation.

## Models and request contracts

### Shared structures

`Address` has five required fields: `street_number`, `street_name`, `city`, `state`, `zip`. Examples represent all as strings, including street number and ZIP. `Geocode` requires `lat` and `lng`; examples use numbers. Resource identifiers are strings. Customer and account property tables specify a 24-character identifier. Error examples use `{ "code": 0, "message": "string", "details": "string" }`.

### Customers

Properties: `_id`, `first_name`, `last_name`, `address`.

`CustomerCreate` requires `first_name`, `last_name`, and `address`. `CustomerUpdate` lists these fields as optional; address still uses the shared Address schema. Customer list results are described as limited to the authenticated user's customers.

### Accounts

Properties: `_id`, `type`, `nickname`, integer `balance`, integer `rewards`, string `account_number`, and `customer_id`. Account types are exactly `Credit Card`, `Savings`, and `Checking`. The account-number property is described as a 16-digit string.

`AccountCreate` requires `type`, `nickname`, `rewards`, and `balance`; the customer ID comes from the path. The create schema does not include `account_number`. `AccountUpdate` exposes only required `nickname`, so do not assume PUT can arbitrarily overwrite balances, rewards, ownership, or account type.

Example create body:

```json
{"type":"Checking","nickname":"Demo Checking","rewards":0,"balance":0}
```

### Deposits

Property table: `_id`, `medium`, `transaction_date`, `status`, integer `amount`, `description`. The resource example uses `medium: "balance"`, `status: "completed"`, and an ISO-like date string such as `2025-03-15`.

`DepositCreate` requires all five non-ID fields: `medium`, `transaction_date`, `status`, `amount`, `description`. `DepositUpdate` lists them as optional. The creation endpoint's account ID supplies the relationship; the overview example does not show an account ID in the returned object. The medium/status examples are not a complete documented enum. Do not infer settlement or balance-update timing from the example's word “completed.”

### Withdrawals

The displayed overview has the same fields as deposits. Example: medium `balance`, status `completed`, amount `200`, description `ATM withdrawal`. Account-scoped list and create paths use plural `withdrawals`, but individual-object paths use singular `withdrawal`. A dedicated withdrawal schema was not listed in the common schema collection inspected. Its exact create/update payload validation remains unverified.

### Transfers

The overview again lists `_id`, `medium`, `transaction_date`, `status`, integer `amount`, and `description`. Its example describes a transfer to savings, but contains neither sender nor recipient account identifiers.

Expanded GET shows a response example of `{}`. Expanded PUT shows a request example of `{}`. This is inadequate documentation, not evidence that an empty object is a useful transfer payload. Creation, source/destination fields, list access, and balance effects need verification before selecting transfers as a critical demo dependency.

### Purchases

The same generic transaction fields are displayed, plus `merchant_id`. The example is a completed balance-funded grocery purchase. The reference only exposes individual lookup/update/delete under singular `/purchase`. No listed create/list path or dedicated Purchase schema was observed. Do not assume a complete transaction-history feature is immediately available from the documented endpoints.

### Bills

Property table: `_id`, `status`, `payee`, floating-point `payment_amount`, `payment_date`, and integer `recurring_date` (day of month 1–31). Status values: `pending`, `cancelled`, `completed`, `recurring`.

The example additionally contains `nickname`, `creation_date`, `upcoming_payment_date`, and `account_id`. `BillCreate` requires `status`, `payee`, `payment_amount`; optional fields are `nickname`, `payment_date`, and `recurring_date`. `BillUpdate` lists all six as optional. Recurrence execution, dates for short months, and automatic balance deductions are not established by the inspected material.

### Loans

Properties: `_id`, `type`, `status`, integer `amount`, integer `monthly_payment`, and integer `credit_score`. The example additionally shows `creation_date` and `description`, with type `home` and status `approved`.

`LoanCreate` requires `type`, `status`, `credit_score`, `monthly_payment`, `amount`, and `description`. `LoanUpdate` lists these as optional. Example values do not establish exhaustive type/status enums. No interest-rate field, amortization endpoint, underwriting process, or loan-payment endpoint was displayed. This supports storing simulated loan records; do not attribute an actual lending decision engine to it.

### Merchants

Properties: `_id`, `name`, `category`, `address`, `geocode`. `MerchantCreate` requires only `name`; category, address, and geocode are optional. Update lists all four as optional.

There is a type inconsistency: the property table calls `category` a string, but the example uses `["food"]`. Verify actual accepted and returned types. Do not hard-code either without a compatibility check.

### ATMs and Branches

ATMs expose `_id`, `name`, `address`, `geocode`, and integer `amount_left` (cash remaining). The expanded list endpoint showed only the required key parameter; no radius, latitude/longitude filter, or pagination parameter was listed there.

Branches expose `_id`, `name`, `phone_number`, string-array `hours`, and `address`; the example also contains string-array `notes`. Both resources have only GET operations in the displayed reference.

## Responses and failure handling

Representative expanded endpoints establish the following documentation patterns, not a universal guarantee:

- Customer list: `200`, JSON array of customers.
- Customer detail: `200`, JSON customer object; `401` unauthorized; `404` error object.
- Customer creation: `201`, example JSON string `"Customer created"`; `400` error object; `401` JSON string `"unauthorized"`.
- Account creation: `201`, example JSON string `"Account created"`, with `400` and `401` errors.
- Deposit creation: `201`, example JSON string `"Deposit created"`, with `400` and `401` errors.
- Transfer update: `202`, example JSON string `"Accepted transfer update"`; `400`, `401`, `404` failures.

Do not assume a successful POST returns `{_id: ...}` or a complete created object. Inspect actual authorized responses and determine how to recover created identifiers if necessary. Likewise, error handling must accommodate both JSON strings and objects. Do not assume DELETE returns a body; delete responses were not expanded in this review.

## Published quick-start workflow

The docs propose: create customer → open account → deposit funds → transfer funds. The first three have visible request schemas. Transfer creation is the incomplete fourth step. A transfer also logically needs another account, which the four-step overview does not fully spell out.

For an implementation agent, an initial verification plan would be: obtain the user's authorized key through their chosen setup; test a read; inspect existing accessible customers; if creation is authorized, create a uniquely named demo customer, determine its ID, create an account, determine its ID, and test a deposit while reading balances before/after. Verify each response instead of assuming the advertised workflow establishes runtime semantics. This plan is a recommendation, not a record of completed tests or additional user authorization.

## SDKs and examples

The SDK page links four options:

- Swift: https://github.com/nessieisreal/nessie-ios-sdk-swift2 — labeled for Xcode >= 7.0.
- Android: https://github.com/nessieisreal/nessie-android-sdk — Java wrapper.
- Ruby: https://rubygems.org/gems/capital_one; docs https://shwheelz.github.io/capital_one/; source https://github.com/Shwheelz/capital_one.
- JavaScript: https://github.com/nessieisreal/nessie-javascript-sdk — explicitly depends on jQuery.

These are links displayed by the site; the repositories were not audited for compatibility, maintenance, or current server configuration. The Swift/Xcode labeling and jQuery dependency suggest legacy integration assumptions. For a new application, a small direct HTTP adapter may be simpler, but that is an engineering recommendation rather than a verified SDK defect.

All five tabs on the Examples page—Python, JavaScript, Go, Java, Swift—say examples are on their way. None provided working sample code during inspection. Getting Started also describes Postman as a Chrome extension, another indication that parts of the prose may be old.

## Critical gaps and implementation cautions

1. **Two API hostnames:** setup prose and interactive reference disagree.
2. **Incomplete transfer documentation:** advertised creation path missing from endpoint list; missing source/destination fields; empty GET and PUT example schemas.
3. **Incomplete purchases documentation:** no displayed create or list operations; do not invent routes from convention.
4. **Broken ATM schema reference:** expanding `GET /atms` produced a resolver error saying `/components/schemas/ATM` does not exist. The generated example became `["string"]`, contradicting the rich ATM overview. Treat this as a documentation error, not a meaningful data model.
5. **Merchant category mismatch:** string in property table versus array in example.
6. **Creation responses:** examples are strings, not created objects; ID propagation requires verification.
7. **Money representation:** account/transaction/loan tables use integers; bill payment uses float. Currency, cents-versus-dollars, precision, and rounding rules were not established. Do not silently choose units.
8. **Date and lifecycle semantics:** examples use date strings, but timezone, settlement timing, recurrence mechanics, and balance side effects were not verified.
9. **Schemas are uneven:** the common list contained customer/account/bill/merchant/branch/deposit/loan schemas, but not dedicated ATM, withdrawal, transfer, or purchase schemas.
10. **Operational behavior unknown:** rate limits, pagination outside the inspected ATM list, idempotency, retry safety, concurrency, CORS, availability, and data-reset behavior remain unverified.
11. **Resource overview is not an exhaustive schema:** bill, loan, and branch examples contain fields omitted from their property tables.
12. **Sponsor rules are separate:** using Nessie does not by itself establish VTHacks sponsor-track eligibility.

## Recommended use of this brief

Use the endpoint inventory and model relationships to scope the integration. Put Nessie behind a small adapter so hostnames, response normalization, and incomplete types can be corrected centrally. Build a minimal authorized integration probe before committing the whole demo to transfers or purchases. Keep synthetic fixtures clearly labeled and separate from verified API results. Do not report any operation as working solely because it appears in this document.

The strongest documented starting surface is customers, accounts, deposits, bills, and loan records. The directory data could support a map, subject to the ATM schema issue. An application centered on transaction history or account-to-account movement needs more verification than the overview initially suggests.

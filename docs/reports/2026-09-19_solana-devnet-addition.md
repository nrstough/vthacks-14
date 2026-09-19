# Plan addition — Solana Devnet demo wallet (bounded)

Prepared Sat 2026-09-19 03:45 EDT from checkout `af65052` on branch `backend`, the live
candidate-generation plan (`docs/reports/2026-09-19_candidate-generation-plan.md`), the
frontend handoff, `CLAUDE.md`, `docs/api-contract.md`, and the Solana docs fetched today
(`/docs/payments/send-payments/basic-payment`, `/docs/payments/accept-payments/
verification-tools`, `/docs/references/clusters`) plus the Devpost page. **Insert this as
a new workstream in the project plan and `docs/prize-strategy.md`. It does not go into
the candidate-generation run spec** — that spec is scope-audited and this is out of it.

## 1. Go / no-go

**No-go before the Saturday 18:30 gate. Conditional go after it**, as a strictly
isolated spike with kill criteria, and only if at 18:30 the deployed demo is standing and
the frontend owner has finished the UX pass. Reasons, in order of weight:

1. **Time.** It is 03:45. Before the gate the backend lane still owes candidate
   generation (execution + audit, ~3–4 h), the synthetic account generator (~2 h), Nessie
   (90-min timebox) and the Vultr deploy (~1.5 h); the frontend lane owes the UX overhaul
   and wiring `/api/candidates`. The ask here is 60–90 min + 4–8 h — the size of the
   remaining core plan — and it lands almost entirely in the frontend lane, which also
   owns the prize-relevant UI work. Best First-Time Hack and Best UI/UX are judged
   automatically for everyone; Solana is one opt-in MLH prize.
2. **Installs.** No `@solana/*` package is in `node_modules` or `.npm-cache`. The stack
   must be installed on venue wifi before 23:00, and `node_modules` is shared between
   worktrees by symlink — a half-failed install poisons `npm run build` for the main
   demo. Mitigation exists (own worktree, own `node_modules`, `package-lock.json` is
   present so `npm ci` is deterministic) but it is a real hazard on the critical path.
3. **Judging.** The memo records offline judging Sunday morning. The wallet flow needs a
   browser extension, a live RPC and Devnet; if wifi dies the honest state is "payment
   unavailable", which demos nothing. A pre-recorded 30-second clip is the only reliable
   form of this beat.
4. **Product.** It is a coherent "same idea, second ledger" story — a reserve check
   before a token payment, with an honest receipt — but there is no bank bridge by
   design, so it is an appendix to the pitch, not the pitch. The four-minute script has
   no free slot; the only flex is the optional Nessie beat.

What "conditional go" buys: a Ledger Nano S Plus is a real prize and the flow is a
legitimate payment prototype. What it risks: the two automatic categories the plan is
built around, and Nathan's sleep before an unaided Sunday morning. If the spike does not
produce one signed, confirmed Devnet transfer by ~20:00, stop and keep
`prize-strategy.md:51` as it is ("Skip").

**Prize eligibility is not guaranteed and is not claimed.** The Devpost track lists no
criteria beyond the general ones (technical execution, innovation, impact, presentation
and completeness). Plan against the written deadline **Sun Sep 20 08:00 ET**; the header
says 10:00 EDT and the organiser has not reconciled the two.

## 2. Owner lanes and file / API boundaries

| Lane | Owner | May create | May edit | Must not touch |
|---|---|---|---|---|
| **Wallet** (new) | a third session in its own worktree `../vthacks-solana`, branch `solana` off `main`, **own `node_modules`** (`npm ci` + the wallet packages, at the venue) | `frontend/src/wallet/**` (`WalletView.tsx`, `units.ts`, `ledger.ts`, `rpc.ts`, `receipt.ts`, `state.ts`, `types.ts`, `__tests__/*.test.ts`), `docs/features/wallet.md`, `docs/specs/2026-09-19_solana-devnet-spike.md` | `frontend/package.json` + lock (deps only), `frontend/vite.config.ts` (`manualChunks` for the wallet chunk only) | `App.tsx`, `index.css`, `components/**`, `src/types.ts`, `lib/api.ts`, `solver/mockSolver.ts`, anything in `backend/`, `docs/api-contract.md` |
| **Frontend** (existing) | frontend session | — | `App.tsx`: one lazy route/tab (`React.lazy(() => import('./wallet/WalletView'))`) behind an error boundary, added when the wallet lane asks | wallet files |
| **Backend** (existing) | this session | — | nothing for the base flow | — |
| **Deploy** | backend session | — | Caddy/CSP: `connect-src` for `https://api.devnet.solana.com` and `wss://api.devnet.solana.com`; nothing else | — |
| **Codex** forecasting | Nathan's Codex worktree | — | — | no dependency in either direction; the wallet never reads a forecast |

API boundary: **none**. `POST /api/solve` and `POST /api/candidates` are not called by
the base flow and the contract is not extended (see §4). Wallet types live in
`frontend/src/wallet/types.ts`, never in `src/types.ts`, which mirrors the API contract.

Library choice for the spike: `@solana/kit` + `@solana-program/token` + the Wallet
Standard React hooks (`@solana/react`), because that is what the official docs use
today. If the wallet handshake is not working 30 minutes into the spike, switch once to
the classic `@solana/wallet-adapter-react` + `@solana/web3.js` 1.x + `@solana/spl-token`
stack and do not switch back. Check both packages' maintenance status on npm at the start
of the spike (one minute); do not rely on this document's recollection of it.

Test runner: the frontend has none (oxlint + tsc). Pure-logic wallet modules get
`node --test --experimental-strip-types` tests — the pattern the oracle harness already
uses — so no test framework is added.

## 3. Dependency-ordered tasks and estimates

| # | Task | Depends on | Estimate | Kill criterion |
|---|---|---|---|---|
| T0 | 18:30 gate passed: deployed demo standing, frontend UX pass done | — | 0 | not met → this workstream does not start |
| T1 | **At the venue, before 23:00:** `git worktree add ../vthacks-solana -b solana main`; `npm ci` there; add wallet packages; `npm run build` clean in **both** trees | T0 | 10–20 min | install fails twice → stop |
| T2 | **Spike:** Phantom (or Solflare) on Devnet; airdrop SOL; create the `DEMO` mint (2 decimals, classic SPL Token program) with the `spl-token` CLI or a 20-line script; mint 10,000.00 to wallet A; one `transferChecked` A→B signed in the wallet, awaited at `confirmed`, Explorer link `?cluster=devnet`, `getTransaction` shows the pre/post token-balance diff | T1 | 60–90 min | no confirmed signature at 90 min → stop, record in the spike spec, keep "Skip" |
| T3 | `WalletView` skeleton: connect; SOL lamports and DEMO base units (ATA balance); network badge from `getGenesisHash()`; "Payment unavailable" state when RPC or genesis check fails | T2 | 60 min | — |
| T4 | Obligations (three hard-coded dated DEMO outflows + reserve input) → `ledger.ts` BigInt walk → payment preview: amount string → base units, recipient = valid base58 pubkey ≠ sender, projected minimum and its date, verdict (affordable / breaks reserve on D by X / earliest affordable date) | T3 | 60 min | — |
| T5 | Review → wallet approval → pending → confirmed, with every terminal state in §5; duplicate-click guard; expiry; uncertain confirmation | T4 | 60–90 min | — |
| T6 | Receipt verification + exactly-once reconcile → refresh balances → re-run outlook; planning scenario removed, confirmed transfer row added | T5 | 45 min | — |
| T7 | `node --test` tests for `units`, `ledger`, `receipt` (fixture JSON), `state` | T4–T6 | 30 min | — |
| T8 | Pre-record the 30-second beat; `docs/features/wallet.md`; flip `prize-strategy.md:51` to "conditional, shipped"; add the beat to `demo-script.md` as the optional slot | T6 | 30 min | — |

Sum after the gate: **~6–7.5 h** for the complete flow; the venue closes at 23:00 (T1
must be done by then), code freeze is 01:30, the Claude allowance resets 02:00. The
realistic ship if T2 passes is **T3–T6 minimal (~3.5–4 h)** plus T8; T7 shrinks to
`units` and `ledger` if time is short. Nothing here is a promise.

Excluded, per the request: lending, DEX, yield, bridges, fiat ramps, unattended or
recurring payments, any new on-chain program, any mainnet use.

## 4. Accounting adapter decision

**The base flow does not call the solver.** The question "can I send X now without
breaking the reserve" over a handful of dated wallet obligations is a ledger walk, not a
covering optimisation: `min over days of (balance − obligations − payment) ≥ reserve`,
and if not, the first breach date, the shortfall, and the earliest date the same payment
clears. `ledger.ts` does this in **BigInt base units**, no floats anywhere.

Units and identity, explicit everywhere: `{ network: "devnet", genesisHash, mint,
symbol: "DEMO", decimals: 2 }` travels with every amount. `decimals` is read from the
mint on chain and must equal 2 or the view refuses. The amount input is a decimal string
parsed to base units exactly (`"12.34"` → `1234n`; more than two decimals, empty, zero,
scientific notation → rejected); display is `formatUnits(base, 2) + " DEMO"`, never `$`.
**The SOL fee balance is a separate ledger**: Sign is enabled only when lamports ≥
estimated fee + a fixed margin, and lamports never enter the DEMO outlook.

The wallet is **not** Nessie's bank balance. No bridge, no cash-out, no bank bill paid
from the wallet, no checking account topped up by it. Two ledgers, two screens, two
labels; the wallet view says "Demo wallet — Solana Devnet" in its header.

**Stretch only — the solver adapter.** "Would become affordable if these changes happen"
maps onto `POST /api/solve` with the wallet obligations as `scheduled`, base units in
the `*_cents` fields, and wallet-authored candidates. The response's **numeric** fields
(`balances`, `plan` ids, `tier`, `shortfall.total_cents`, `external_cash_needed`) are
correct in base units; its **prose** (`verdict`, `certificate.sentence`, `per_item`
wording) says `$` and is not shown — the wallet view authors its own sentences with the
token label. That is the smallest honest extension: zero contract change, the solver's
`$` strings never reach the wallet screen, and the request is marked client-side as a
wallet request so it can never be confused with bank data. A `unit` field in the contract
was considered and rejected for this deadline: it touches `wording.py`, `money()`, the
oracle's `format.ts` mirror and the parity tests.

The two verdicts are kept distinct in wording and in code: *"Affordable under the
current schedule"* (ledger walk, no solver) vs *"Would be affordable if these changes
happen"* (solver stretch, conditional on unexecuted changes). Only the first enables
Sign. **At review and again at signing time the live wallet balance and the proposed
payment are re-read**; the forecast never infers that an obligation is cancellable.

## 5. Acceptance tests

Unit (`node --test`, no network):
- `units`: `"12.34"`→`1234n`; `"0.5"`→`50n`; `"12.345"`, `""`, `"0"`, `"1e3"`, `"-1"`,
  `"12,34"` → rejected; `" 12.34 "` → trimmed; `formatUnits(1234n)` → `"12.34"`.
- `ledger`: obligations + reserve → minimum and its date; a payment that breaks the
  reserve → first breach date and shortfall in base units; earliest affordable date;
  obligations before today ignored; BigInt throughout (a float anywhere fails a type test).
- `receipt` on fixture `getTransaction` JSON: accepts a transfer whose token-balance diff
  for the DEMO mint is −amount at the sender's ATA and +amount at the recipient's, with
  `meta.err === null`; rejects wrong mint, wrong recipient, wrong amount, `meta.err`,
  and a genesis hash that is not Devnet's.
- `state`: `reconcile(signature)` twice → second call is a no-op and returns `already`;
  a submit while a signature is pending → refused; terminal states are exactly
  `{rejected, failed, expired, confirmed}` plus `unconfirmed` (non-terminal).

Flow (manual, on Devnet, recorded once):
- Rejection in the wallet → "Payment not sent", no pending row, balances unchanged.
- Insufficient SOL for fees → Sign disabled with the reason; nothing submitted.
- Send → pending → `confirmed` → exactly one confirmed row; balances refreshed from
  chain; outlook re-run; planning scenario removed; Explorer link opens on Devnet.
- Double-click Sign → one signature.
- Blockhash expiry (`lastValidBlockHeight` passed, no status) → "Expired — not sent";
  retry builds a fresh transaction; nothing reconciled.
- Uncertain confirmation (RPC timeout after send) → "Unconfirmed — checking", polling
  `getSignatureStatuses` until confirmed or expired; never "success" on send.
- Wrong network (genesis hash mismatch) or RPC down → "Payment unavailable"; Sign
  disabled; the planning demo on the main screen is unaffected.

Build and regression:
- `npm run lint && npm run build` clean; the main `index-*.js` chunk size unchanged
  within 5 kB (the wallet is a lazy chunk); backend gate unchanged.
- The wallet chunk failing to load (simulated by blocking it) leaves the planning demo
  fully working.

## 6. The 30-second judging beat

> "Same idea, second ledger. This is a demo wallet on Solana Devnet — DEMO tokens, two
> obligations due this week, a 50-token reserve I've told it to protect. I want to send
> 30 to a friend. The outlook says that breaks the reserve on Tuesday by 12, and clears
> after Friday's inflow. So I'll send 15 instead: review — amount, recipient, Devnet,
> projected balance — sign in the wallet — pending — confirmed. That's the receipt on the
> Devnet explorer, and the balance and outlook updated *once*, from the confirmed
> transfer, not from the button click."

Who benefits: anyone paid or paying in tokens who has dated obligations — the same
reserve discipline as the bank screen, applied before a signature instead of after an
overdraft. Play the recording if wifi or the extension misbehaves; say so when you do.

## Collisions with the current plans, and their resolution

| Collision | Resolution |
|---|---|
| Shared `node_modules` symlink; installs on the critical path | Own worktree with its own `node_modules`, `npm ci` at the venue before 23:00; the main tree's `node_modules` is never touched |
| `App.tsx` is the frontend owner's | The frontend owner adds the one lazy route when asked; the wallet lane never edits it |
| `src/types.ts` mirrors the API contract | Wallet types in `src/wallet/types.ts` only |
| Bundle already 616 kB with a warning | Lazy chunk + `manualChunks`; main chunk size asserted unchanged |
| The candidate-generation run spec is scope-audited | This addition lives here and in the project plan, not in that spec; no backend file is touched |
| `docs/api-contract.md` lines 8–160 frozen | No contract change; the adapter is client-side and consumes numeric fields only |
| Demo script has no slot | Optional beat only; the two-minute cut drops it first |
| 18:30 gate | Nothing starts before it; T1 is the only pre-23:00 dependency after it |

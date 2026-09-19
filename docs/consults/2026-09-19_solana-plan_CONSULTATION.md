# Solana addition to the implementation plan

Add a bounded **Solana Devnet payment feature** to our Overdraft Guard plan. First inspect the current branch, worktree, active candidate-generation plan, frontend handoff, and API contract. Preserve the work already underway; make this an additive workstream with explicit file ownership and dependencies. This request is to update the plan, not to interrupt the current implementation or start real-money transactions.

## Product purpose

Overdraft Guard forecasts a user's cash flow and uses an exact solver to suggest dated changes that protect a chosen balance reserve. The Solana feature extends that idea to someone who holds and spends tokens: **check a proposed wallet payment against upcoming wallet obligations, then let the user sign the payment if they choose.**

The MLH Best Use of Solana track explicitly welcomes payment prototypes; its listed prize is a Ledger Nano S Plus. Build something demonstrable that uses Solana for settlement, with a clear explanation of who benefits. Do not claim that prize eligibility or winning is guaranteed.

## Current project boundaries

- The Python/FastAPI solver and `POST /api/solve` exist. Money in that contract is integer cents. React/TypeScript handles the UI and has a deliberate, visibly labeled offline solver fallback. The last recorded solver gate was 977 passing tests; rerun the current gate rather than assume that count is still current.
- Claude's backend lane has an active candidate-generation plan. Multiple candidate alternatives may target one transaction, but at most one is selected; do not copy the stale handoff's claim that multiple alternatives are rejected.
- The frontend has a separate owner. Coordinate its files rather than editing under another agent. Nathan requested isolated branches/worktrees for concurrent work; inspect the current ownership before adding one.
- Codex owns forecasting and real-data acquisition in `/Users/nathanstough/Documents/Codex/worktrees/vthacks-forecast`, branch `codex/spending-forecast`. It is implementing MLP/TCN/GRU/tiny-Transformer comparisons and self-supervised transfer experiments. IBM synthetic data is available; Berka is being acquired and audited; Nedbank is blocked; MoneyData is excluded from new training and selection. These experiments must not become a dependency for getting one Solana payment demo working.

## Required demo flow

1. Open a clearly labeled **Demo wallet — Solana Devnet** view. Connect a user-controlled wallet and read its token and SOL balances.
2. Select one supported demo token, enter a recipient and an amount, and preview the effect on that wallet's dated balance and protected reserve. Start with one token and one recipient flow.
3. Show the amount, recipient, network, projected balance and assumptions before signing. A reserve-breaking scenario explains the shortfall or a tested later date. A future date is a planning scenario, not a promise of unattended execution.
4. For a permitted payment now: **Review payment → wallet approval → pending → confirmed receipt**, with an Explorer link on the correct network.
5. Reconcile the confirmed payment exactly once, refresh balances, and re-run the outlook. Define rejection, failure, expiration, retry, duplicate-click and uncertain-confirmation behavior. Never claim success merely because a signature was requested or a transaction submitted.

## Accounting and implementation constraints

- Keep wallet assets separate from Nessie's simulated bank balance. There is no bank bridge or fiat cash-out integration. A wallet payment does not pay an ordinary bank bill or replenish a checking account.
- Use integer token base units and explicit mint/decimal/network identity. The existing solver assumes cents and produces dollar wording, so do not silently feed arbitrary token units into it. Propose a narrow adapter and correctly labeled presentation for a two-decimal demo unit, or explain the smallest necessary contract/presentation extension. Explicitly handle conversion precision and the separate SOL fee balance.
- Use clearly labeled test assets. A custom demo token is not USDC. Use official Solana Devnet and standard transfers; a custom on-chain program is not required for the initial flow.
- The user signs in their wallet. No seed phrases, custody, autonomous signing or mainnet funds. The app's reserve check governs this app's payment flow; it cannot prevent spending through another wallet app.
- A solver result conditional on unexecuted spending changes is not permission to send immediately. Distinguish “affordable under the current schedule” from “would become affordable if these changes happen.” Recheck the actual wallet balance and proposed payment at review/signing time; never infer cancellability from the forecast.
- Keep planning events separate from confirmed transfers so they cannot be counted twice. Validate the expected network, token, sender, recipient and amount when reconciling the receipt.
- Preserve the existing offline planning demo. A disconnected or failing RPC must show that payment is unavailable; it must never fabricate a successful transaction.

## Scope and requested plan output

Allocate a **60–90 minute feasibility spike** for one signed and confirmed Devnet transfer using maintained official tooling. The complete scoped feature is a rough **4–8 focused-hour estimate**, not a promise. Stop or simplify if the spike fails; protect core integration and submission time. Devpost's header and written deadline differ; plan against the conservative written **Sunday September 20, 08:00 ET** deadline unless the organizer confirms otherwise.

Exclude lending, DEX/trading, yield, bridges, fiat ramps, unattended recurring payments and a new smart-contract vault from this deadline scope.

Return an addition ready to insert into the current plan: (1) a candid go/no-go recommendation and product rationale, (2) named owner lanes and exact file/API boundaries, (3) dependency-ordered tasks and estimates, (4) the accounting adapter decision, (5) concrete acceptance tests for the complete flow and failure states, and (6) a 30-second judging demo. Identify any collision with the current backend/frontend plans and resolve it before execution. Push back if the integration would materially weaken the main demo.

Primary references:
- Event track: https://vthacks-14.devpost.com/
- Solana transfers: https://solana.com/docs/payments/send-payments
- Payment acceptance and verification: https://solana.com/docs/payments/accept-payments
- Devnet: https://solana.com/docs/references/clusters

Prepared from source checkout revision `af65052` and the live candidate-generation plan on September 19, 2026. No Solana code has been implemented in this workstream. No external response has been received yet.

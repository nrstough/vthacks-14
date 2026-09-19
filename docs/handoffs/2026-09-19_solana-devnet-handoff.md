# Handoff — Solana Devnet demo wallet (2026-09-19, Sat ~05:50)

**Purpose of this chat:** Decide whether to build the bounded Solana Devnet payment
feature, and if so, build it. A plan exists and has been reviewed twice. **It is not
executable as written** — eight critical findings from Codex and three blockers from an
adversarial critique are outstanding, and three of them would break the main demo rather
than merely the wallet. Fix those before writing any code, or decide not to.

Nothing has been implemented. No Solana package is installed, no wallet code exists.

## Context

VTHacks 14, solo. The product: given a transaction history, return the fewest dated
spending changes that keep the balance above zero until payday, and prove it.

The Solana idea is "same idea, second ledger": check a proposed wallet payment against
upcoming wallet obligations and a protected reserve, show the effect before signing, then
let the user sign it themselves and reconcile the confirmed receipt exactly once. The MLH
**Best Use of Solana** track lists a Ledger Nano S Plus. Eligibility is not guaranteed and
must not be claimed.

**The rest of the project is in good shape and all three lanes are now merged into `main`:**

- `backend/app/solver/` — the exact solver, `POST /api/solve`.
- `backend/app/candidates/` — candidate generation, `POST /api/candidates`.
- `backend/app/chat/` — the Gemini explainer, `POST /api/chat`.
- `frontend/` — the UI, with 87 of its own tests under `npm test`.

## Working branch / worktree

`backend` in `/Users/nathanstough/Desktop/VT Hacks`, clean. `main` and `backend` are the
same commit (`2951056`); everything is merged.

**Do not build this on `backend`.** `CLAUDE.md` is binding, and this work belongs in its
own branch:

```bash
git switch -c solana main      # git switch, never checkout
```

Three other worktrees are live. `frontend` is **15 commits behind `main`** and that lane
will need to merge before it can see any of this; `codex/spending-forecast` is Nathan's own
forecasting work and is unrelated. `git add` names files, never a directory.

## Environment / setup

```bash
cd "/Users/nathanstough/Desktop/VT Hacks"
.venv/bin/pytest backend/ -q -m "not perf"
```

```bash
cd "/Users/nathanstough/Desktop/VT Hacks/frontend"
export npm_config_cache="/Users/nathanstough/Desktop/VT Hacks/.npm-cache"
npm run lint && npm run build && npm test
```

**Wifi is fine** (Nathan, Sat ~05:10), so the older "never install from the hotel" rule is
relaxed and `npm install` is available. `package-lock.json` is present and in sync, so
`npm ci` is deterministic. **No `@solana/*` package is installed or in the npm cache** —
verified by `grep -c solana frontend/package-lock.json` → 0.

## What to do next

**Step 0 — re-decide.** The plan's own recommendation was no-go before a deployed demo
existed and a conditional go after. There is still **no deployment**: no Caddyfile, no
`deploy.sh`, no CSP anywhere in the repo, and `frontend/dist/` is gitignored. Ask Nathan
where this sits against the rest of the queue before spending a minute on it.

**Step 1 — fix the plan, or scope it down.** `docs/reports/2026-09-19_solana-devnet-addition.md`
and its review must be reconciled first. The findings that change the design:

1. **The demo beat depends on an inflow the model excludes.** The plan's ledger has three
   dated *outflows*, but the 30-second script says the payment "clears after Friday's
   inflow". With outflows only, the running minimum is independent of the payment date, so
   "earliest affordable date" is always "now" or "never" and the beat cannot happen. Add
   signed dated entries including at least one inflow, and a fixture proving "30 fails, 15
   passes".
2. **A recipient may have no token account.** `transferChecked` fails if the recipient has
   no associated token account, and creating one costs the sender ~0.002 SOL of rent. Either
   prepend an idempotent create-ATA instruction and fund it, or restrict the spike to a
   pre-provisioned recipient and say so.
3. **A lost submission response can hide a payment that actually landed.** Capture the
   signature *before* broadcast, persist it with the transaction identity and expiry, and
   define recovery across reload. Otherwise an unresolved transfer disappears and a
   duplicate becomes possible.
4. **"Expired — not sent" claims more than the evidence supports.** Passing
   `lastValidBlockHeight` proves the transaction cannot newly land; it does not prove it
   never landed, and a null `getSignatureStatuses` can be a cache miss. Inconclusive must
   stay `unconfirmed`.
5. **Review and signing need a frozen payment identity.** Re-reading mutable form inputs at
   signing can change what was reviewed. Freeze sender, recipient, mint, network, amount,
   reserve and schedule for the attempt; take the duplicate-submit guard before the first
   await, including wallet approval.
6. **Reconciliation must be atomic.** Marking a signature reconciled before the balance
   refresh succeeds makes retries no-ops while the outlook stays stale.
7. **"One lazy route in `App.tsx`" is false.** Re-verified after the merge: there is still
   no router, no tabs, no `Suspense`, no `React.lazy` and **no error boundary anywhere** in
   `frontend/src` — `grep` returns nothing. `App.tsx` is now 291 lines. This is 40–60 lines
   across three files including `index.css`, and it belongs to the frontend lane. The good
   news is that the merge removed the contention: nobody else is mid-rewrite of that file.
8. **An isolated `node_modules` breaks `main`'s build at merge time.** If the wallet lane
   installs into its own worktree and merges, `tsc -b` in this checkout type-checks
   `src/wallet/**`, cannot resolve `@solana/kit`, and `npm run build` fails. Plan the merge
   and the rebuild as an explicit task with an owner.
9. **`frontend/tests/bundle.test.ts` greps the built bundle** for "guarantee" and
   "infeasib". If a Solana dependency ships either string, that test fails. Scope the test
   to the main chunk — never weaken the pattern.
10. **Prize wording.** `docs/prize-strategy.md:18` records that automatic category
    consideration was an unverified assumption; Devpost says to select every category you
    want. The plan's "judged automatically for everyone" line overstates it, and
    `prize-strategy.md` lists Solana as "Skip" in **two** places (`:51` and `:94`) — flip
    both or neither.

**Step 2 — the spike, 60–90 minutes, if and only if step 0 says go.** One signed and
confirmed Devnet transfer: wallet on Devnet, airdropped SOL, a 2-decimal `DEMO` mint,
one `transferChecked` awaited at `confirmed`, an Explorer link on `?cluster=devnet`, and
`getTransaction` showing the pre/post token-balance difference. **Kill it at 90 minutes if
there is no confirmed signature.** Verify package names and peer ranges against npm at the
start — React 19.3 and TypeScript 6.0.3 here are ahead of what the SDKs' published peer
ranges may declare, and an `ERESOLVE` is a kill signal, not something to force with
`--legacy-peer-deps`.

**Step 3 — the feature**, only after a successful spike: connect and read balances, the
obligations ledger and payment preview, the review→sign→pending→confirmed flow with every
failure state, exactly-once reconciliation, then tests and a recorded demo beat.

### Blocked on Nathan

- A **browser wallet extension** (Phantom or Solflare) installed and set to Devnet.
- **Devnet SOL** airdropped to it — `faucet.solana.com` is the fallback when the public RPC
  rate-limits (100 requests / 10 s / IP on `https://api.devnet.solana.com`).
- The **go/no-go decision** itself.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

- **Test:** `.venv/bin/pytest backend/ -q -m "not perf"` → **1262 passed**, 8 deselected,
  ~21 s. Nothing in this workstream should change this number. If it moves, you have
  touched the backend and should not have.
- **Test:** `.venv/bin/pytest backend/ -m perf -q -s` → **8 passed**, ~137 s.
- **Test:** `cd frontend && npm run lint && npm run build && npm test` → lint clean, build
  ~145 ms, **87 tests passing**. The bundle is **625 kB** (the >500 kB warning is expected
  and pre-existing). **Record the main chunk size before you add any dependency** — a lazy
  wallet chunk must leave it unchanged, and that is the check that proves the planning demo
  cannot be slowed down by this work.
- **At-risk: `frontend/dist/`** — gitignored, **NOT archived**. The deploy needs it rsynced
  and nothing on a server builds it.
- **At-risk: `wheels/`** — 65 MB, gitignored, **NOT archived**.
- **At-risk: `~/Downloads/Checking.csv`** — Nathan's real bank export. **Never commit.**
- **At-risk: `experiments/residual_forecast/*.npz`** — 13 MB, gitignored, **NOT archived**,
  not this lane's. Do not delete.
- **Any keypair you generate** (mint authority, a scripted second wallet) needs a home that
  is not the repo. `data/private/` is already gitignored.
- **26 commits unpushed** to `https://github.com/nrstough/vthacks-14` (private).
- **In flight:** nothing. No background jobs, no cloud runs, no open PRs.

## Analytical notes

- **Keep the two ledgers apart.** Wallet assets are not the simulated bank balance. There
  is no bridge and no fiat cash-out; a wallet payment does not pay a bank bill. Two
  screens, two labels, and the wallet view says "Demo wallet — Solana Devnet" in its header.
- **The base flow does not need the solver.** "Can I send X now without breaking the
  reserve" over a handful of dated obligations is a BigInt ledger walk in token base units,
  not a covering optimisation. Feeding token base units into `/api/solve` is a stretch only:
  its numeric fields would be right, but its prose says `$` and must never reach a token
  screen.
- **A custom demo token is not USDC.** Label test assets as test assets everywhere.
- **The user signs in their own wallet.** No seed phrases, no custody, no autonomous
  signing, no mainnet funds. The app's reserve check governs this app's flow only; it
  cannot stop spending from another wallet app, and the UI should not imply otherwise.
- **Never report success because a signature was requested.** Only a verified confirmed
  receipt — right network, mint, sender, recipient and amount — counts, and it reconciles
  exactly once.
- **A disconnected or failing RPC shows "payment unavailable".** It must never fabricate a
  successful transfer, and it must never take the planning demo down with it.
- **The schedule is Nathan's, and the memo's gate was rejected.** The "Sat 18:30 deployed
  demo or freeze" figure came from the VeriLM memo; he disagrees and says freeze can be
  04:00–06:00 Sunday because submission is due **08:00 ET Sunday**. Venue close (23:00) and
  that 08:00 are the externally-imposed deadlines; freeze timing is his to set. Ask rather
  than assuming.
- **Judging is offline on Sunday morning**, over a four-minute demo. A flow that needs a
  live extension and a live RPC is the most fragile thing in the deck — record the
  30-second beat in advance. `docs/demo-script.md:140` says that if a feature is not live,
  say nothing about it rather than apologising; decide up front whether the recording *is*
  the beat or whether the beat is skipped silently, because those two are inconsistent.

## Pointers

- `docs/reports/2026-09-19_solana-devnet-addition.md` — the plan: go/no-go, owner lanes,
  T0–T8 with estimates and kill criteria, the accounting adapter decision, acceptance tests
  and the 30-second beat.
- `docs/reports/2026-09-19_solana-devnet-addition-review.md` — the Codex review. **Read it
  beside the plan, not after it.**
- `CLAUDE.md` — working agreement; binding.
- `docs/prize-strategy.md` — tracks, rewards, and the corrections. Solana is currently
  "Skip" at `:51` and `:94`.
- `docs/demo-script.md` — the four-minute script. The optional slot at `:133` is the only
  flex, and the Gemini beat now competes for it.
- `docs/api-contract.md` — `/api/solve` and `/api/candidates`. The backend owns it.
- `frontend/src/App.tsx` — 291 lines, no router, no boundary. The frontend lane's file.
- Solana docs fetched Sat 03:45: send-payments/basic-payment, accept-payments/
  verification-tools, references/clusters. Re-fetch rather than trusting the summaries.
- Memory: `vthacks-14-event-constraints`, `vthacks-project-plan`, `user-nathan-profile`.

# Handoff — wiring the wallet core into the app (2026-09-19)

**Purpose of this chat:** Connect `frontend/src/wallet/**` to the UI. The core is built,
tested and merged-ready on branch `solana`; nothing imports it, so today it is dead code.
This is the bridge out of that state.

## What exists

Four pure-TypeScript modules on branch `solana`, **zero `@solana/*` imports**, 94 tests.

| Module | Use it for |
|---|---|
| `units.ts` | `parseUnits(input, decimals)` → `{ok, value}`; `formatUnits`, `formatAmount`; `toBase`/`toSigned` for anything the RPC returns |
| `ledger.ts` | `verdictFor(...)` → the sentence and `kind`; `canSign(verdict)` → **the only thing that may enable Sign** |
| `receipt.ts` | `verifyReceipt(receipt, identity, expectedSignature, observedGenesisHash)` |
| `state.ts` | `createMachine(store)` — the whole attempt lifecycle |

## The order of operations, which is not optional

```
begin(identity) -> {token}
approve(token, freshSnapshot, minimumSlot, evaluate) -> must return ok
persistBeforeBroadcast(token, signature, lastValidBlockHeight) -> must return ok
   ... broadcast here, and only here ...
resolve(token, observedStatus | null, blockHeight)
reconcile(token, verifyReceipt(...), freshSnapshot) -> installs the balance
```

Every call takes the `token` from `begin`. A call with a stale token returns
`stale_attempt` and does nothing — that is deliberate, and it is what stops a late callback
from an abandoned attempt confirming the current one.

`persistBeforeBroadcast` refuses unless the attempt is `awaiting_approval`, so **there is no
code path from review to broadcast that skips the fresh-balance check.** An earlier revision
let you skip it and two audits caught it. Do not add a bypass.

## What the UI must not do

- **Do not enable Sign on a `conditional` verdict.** `canSign()` is the check. The two
  verdicts read differently on purpose; only the unconditional one is a statement about the
  schedule as it stands.
- **Do not use `money()` from `src/lib/format.ts`** for token amounts. It hardcodes `$` and
  `/100`. Use `formatAmount(base, decimals, symbol)`.
- **Do not read `uiAmount`** from any RPC response. Use the exact `amount` string through
  `toBase`.
- **Do not report success because a signature was requested.** Only `reconcile` returning
  `ok` means the money moved.
- The wallet header says **"Demo wallet — Solana Devnet"**. A custom demo token is not USDC.

## Three things that will bite, in other lanes' files

1. **`Caddyfile:17` sets `connect-src 'self'`** — this blocks the Devnet RPC outright. The
   wallet works locally and is dead on the deployed site until that is extended to
   `https://api.devnet.solana.com` and `wss://api.devnet.solana.com`. **Deploy lane's file.**
2. **A root-only error boundary is not enough.** `main.tsx:9` wraps the whole app, so a
   `React.lazy` wallet chunk that fails to load throws into it and replaces the *entire
   planning demo* with the crash card. That directly contradicts the acceptance test at
   `docs/reports/2026-09-19_solana-devnet-addition.md:166-167`. You need a **nested**
   boundary plus `<Suspense>` around the wallet subtree only. Roughly 40–60 lines across
   `App.tsx`, `index.css` and one new component.
3. **`frontend/tests/bundle.test.ts` greps every built chunk** for `/guarantee/i` and
   `/infeasib/i`. The moment a Solana dependency is installed this may fail on a vendor
   string. Scope it to the main chunk — **never weaken the pattern** — and note that
   `dist/index.html` names the entry chunk authoritatively, so parse that rather than
   matching on the `index-` filename prefix.

## Baselines to hold

- Main chunk on `solana` is **625,369 bytes**. On `error-boundary` it is 626,628. Re-measure
  on the merged tree; do not carry either number forward.
- The wallet must be a **lazy chunk**, so the main chunk stays unchanged. That is the check
  proving this work cannot slow the planning demo.
- `npm test` is 181 on `solana`, 97 on `error-boundary`. Merged, expect 191.
- Backend gate `.venv/bin/pytest backend/ -q -m "not perf"` → **1262**. If it moves, you
  touched the backend and should not have.

## Not built

The live Devnet spike — wallet extension, airdropped SOL, a real `transferChecked` — is
blocked on Nathan and was never attempted. Also unbuilt: idempotent ATA creation and its
~0.002 SOL rent (core review #2), deterministic RPC failure tests (#7), SDK pinning and
`solana:devnet` signer binding (#9), and the solver adapter (#10, the explicit stretch).

`docs/prize-strategy.md:51` and `:94` both still say **Skip**, and must flip together or not
at all.

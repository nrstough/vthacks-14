# Run spec — Solana wallet core (offline, pure logic)

Branch `solana`, worktree `/Users/nathanstough/Desktop/vthacks-solana`, off `main` @ `2f59a94`.
Plan: `docs/reports/2026-09-19_solana-wallet-core-plan.md` (revision 3).
Codex review: `docs/reports/2026-09-19_solana-wallet-core-plan-review.md`.

## Problem

The Solana Devnet workstream had a plan with ten outstanding findings, three of which
would have damaged the main planning demo rather than the wallet. Nathan reopened the
workstream and scoped this session to the **wallet core only**, after another session took
the main checkout for the error boundary and the deploy.

## Solution

Four pure-TypeScript modules with **zero `@solana/*` imports**, so `tsc -b` cannot break in
any worktree the branch reaches, and every decision is testable offline with no network.
The live Devnet spike is blocked on a browser wallet extension and is not attempted.

## What changed

| File | Lines | Role |
|---|---|---|
| `frontend/src/wallet/types.ts` | 161 | shapes; one signed `bigint` per entry, no direction field |
| `frontend/src/wallet/units.ts` | 115 | decimal ↔ base units, the float gate |
| `frontend/src/wallet/ledger.ts` | 172 | per-day netted walk, verdicts, earliest affordable date |
| `frontend/src/wallet/receipt.ts` | 118 | receipt verification, one reason code per rejection |
| `frontend/src/wallet/state.ts` | 356 | frozen identity, enforced transitions, atomic reconcile |
| `frontend/src/wallet/fixtures.ts` | 91 | hand-worked demo beat and receipt fixtures |
| `frontend/tests/wallet-*.test.ts` | 4 files | 94 tests |

Tests live **flat in `frontend/tests/`**, not `src/wallet/__tests__/`: `package.json:11` is a
shell-expanded flat glob and anything nested would have been silently skipped with exit 0.
Fixing that glob belongs to another lane, so this lane sidesteps it rather than colliding.

## Design decisions as built

- **D1** Entries net by day before the walk. An entry-by-entry walk makes the reserve
  verdict depend on array order (opening 60, same-day −20 and +20 → minimum 40 or 60), and a
  date carries no intraday ordering to break the tie. Matches `simulate.py:39-41`.
- **D2** `toBase` accepts only `/^\d+$/` strings, so the RPC's float `uiAmount` cannot enter
  the money path. Fixtures carry `uiAmount` with deliberately wrong values to prove it.
- **D3** `formatUnits` slices strings; exact past 2^53.
- **D5** Serialization converts all three monetary fields, and schedule entries restore
  through a **signed** parser because `toBase` rejects the leading `-`.
- **D6** The unconditional and conditional verdicts stay distinct; only the first enables
  signing. Revision 2 had collapsed them, which would have regressed a safety gate.
- **D7** Beat fixtures test postponement, not amount: the same 30 first clears on the
  payday, and stripping the inflow makes every date fail.
- **D8** Guard taken synchronously; attempt persisted **before** broadcast; restored
  unresolved attempts keep blocking; approval requires fresh balance evidence.
- **D9** Reconcile installs the snapshot and marks the signature together, and refuses a
  snapshot older than the receipt's slot.
- **D10** Network provenance is passed in — `getTransaction` returns no genesis hash. An
  absent recipient pre-balance means no token account and is accepted as zero.

## Results

Verification order lint → build → test (a test-first order reads a stale `dist/`).

| Check | Result |
|---|---|
| `npm run lint` | clean |
| `npm run build` | clean, 114 ms |
| `npm test` | **181 passed, 0 failed** (87 baseline + 94 new) |
| Main chunk `dist/assets/index-DPUqIubV.js` | **625,369 bytes — unchanged** |
| `.venv/bin/pytest backend/ -q -m "not perf"` | **1262 passed**, 8 deselected, 21.1 s |
| `@solana/*` imports under `frontend/src/` | none |
| Banned words in wallet source | none |

### Mutation pass — 36 mutations, 36 killed

| Module | Mutations | Killed |
|---|---|---|
| `units` | 6 | 6 |
| `ledger` | 6 | 6 |
| `receipt` | 8 | 8 |
| `state` | 16 | 16 |

Two mutations initially killed nothing, and both were treated as defects in the tests
rather than argued away:

- Swapping `compareAmounts` for `Number(a - b)`. That form really does sort correctly — the
  difference of two integers cannot round to zero — so the comment claiming a bug was
  **wrong and was corrected**, and the test rewritten to pin the real property (the
  comparator returns only −1/0/1).
- Removing `formatUnits`'s bigint guard. The guard had been added in response to the audit
  without a test, which is the same vacuity in miniature. A test was added.

The heaviest kills: reading `uiAmount` instead of the exact string kills 6 receipt tests;
restoring schedule entries with `toBase` kills 5 state tests; treating every entry as
positive kills 12 ledger tests.

## Post-commit audit — first round Fail, findings fixed

Both a Claude critique and the Codex audit graded the first commit (`10c4687`) **Fail**, and
independently reproduced the same holes. They were real and are fixed in the follow-up
commit:

| Finding | Fix |
|---|---|
| `reconcile()` confirmed and installed a balance for an attempt with a **null signature** — nothing signed, nothing sent — then stored `null` as the reconciled marker, disarming idempotence so it returned `ok` twice | `not_submitted` precondition; two tests |
| `persistBeforeBroadcast()` had **no status precondition**, so a broadcast was reachable without ever calling `approve()`. The fresh-balance gate was advisory, and **14 of the suite's own tests went around it** | requires `awaiting_approval`; every test now goes through the real transition |
| A second `persistBeforeBroadcast()` silently replaced the first signature — the exact loss the persisted attempt exists to prevent | `already_signed` precondition |
| `restore()` overwrote a live in-flight attempt | refuses when one is live |
| Callbacks were not bound to an attempt: reconciling A's result confirmed B | every call carries a monotonic token, the `App.tsx:62-97` pattern D8 had promised and not built |
| The "frozen" identity was the caller's own object; mutating it changed what would be signed | deep-copied and frozen at `begin` |
| `balanceOf` returned the first matching row, so duplicate token accounts made the verdict depend on array order — the same defect D1 exists to prevent | refuses as `ambiguous_balances` |
| `Snapshot` had no network or commitment, though core review #3 required both | both added and checked in `approve` and `reconcile` |
| Empty balance metadata reported `mint_absent` — a claim the evidence did not support | `metadata_unavailable` |
| `err: undefined` reported `transaction_failed`; an `undefined` receipt threw out of a click handler | both `metadata_unavailable` |
| `formatUnits` had no runtime guard: `formatUnits(12.34, 2)` returned `"12..34"` silently | throws `TypeError` |

The audits also confirmed what held: **D1 survived every attack** — `netByDay` plus the
sorted walk makes the whole `Outlook` order-independent including `minimumDate` on ties —
and **D2 held** against Arabic-Indic digits, `+12.34`, `1_000`, `0x10`, `Infinity`, `1.2.3`,
zero-width prefixes and a 400-digit whole part.

The audit's own verified numbers matched this spec's: 165/0 frontend at that commit, 1262
backend, bundle byte-identical.

## Known limits

- **The main-chunk byte assertion passes because nothing imports this code.** By
  `bundle.test.ts:20-21`'s own standard that is a check that had nothing to read. It is
  recorded as a baseline for whoever wires the wallet up, not as evidence this lane is safe.
- **`strictNullChecks` is off** in this project, so `.find()` types as always-present and the
  compiler cannot catch the absent-pre-balance class of bug. Every lookup that can miss is
  written with an explicit check and tested, because nothing else will find it.
- **This is dead code until a lane imports it.** Deliberate for this commit and
  unacceptable as an end state. The bridge is
  `docs/handoffs/2026-09-19_wallet-integration-handoff.md`.
- **Review findings #2, #7, #9, #10, #11 remain unaddressed** and are listed below rather
  than implied as done. In particular #7's deterministic RPC failure tests are not written;
  the store and evaluator seams exist so they can be, without redesigning `state.ts`.
- **In-code citations are numbered against `2026-09-19_solana-devnet-addition-review.md`**
  (11 findings), not against this change's own plan review (8 findings). An auditor flagged
  that following them lands on the wrong finding; they are labelled "core review" in the
  fixed code.

## Handed to other lanes

1. `Caddyfile:17` sets `connect-src 'self'`, which blocks the Devnet RPC. The wallet would
   work locally and be dead on the deployed site. **Deploy lane.**
2. `crash.ts:14` returns `error.message` unmodified, so a thrown message containing
   "guarantee" or "infeasible" renders on screen — a live CLAUDE.md hole today, independent
   of Solana, and `crash.test.ts` has no forbidden-word coverage. **Error-boundary lane.**
3. `mockSolver.ts:410` and `assemble.py:77` mark any `kind === 'income'` row as a payday with
   no sign check, so a clawback reads as "Payday lands on …". **Latent, not live** — the
   shipped fixtures carry only positive income — but it becomes visible the moment the
   synthetic account generator feeds the UI, because `accounts.py:91-93` plants a negative
   `PAYROLL ADJUSTMENT` 30% of the time. Both implementations must change together.
4. A **nested** error boundary plus `<Suspense>` around any lazy wallet route. The root
   boundary alone replaces the whole planning demo when a lazy chunk fails to load, which
   contradicts the acceptance test at `2026-09-19_solana-devnet-addition.md:166-167`.
5. The test glob and bundle-test scoping (`package.json:11`, `tests/bundle.test.ts`).
   `sh` has no globstar, so an unquoted `**` silently keeps today's behaviour; bare
   `node --test` was measured to give the same count and reaches nested directories.

## Findings not addressed

Review **#2** (ATA creation and its rent) needs a live transaction. Review **#7**
(deterministic RPC failure tests) has no RPC layer here — but `state.ts` takes its store and
its evaluator as injected parameters specifically so those tests are writable later without
redesigning it. Review **#9** (SDK pinning) has no SDK in this lane. Review **#10** (solver
adapter) is the explicit stretch and is not built. Review **#11** and handoff **#10** (prize
wording) are the docs lane; `docs/prize-strategy.md:51` and `:94` both still say Skip and
must flip together or not at all.

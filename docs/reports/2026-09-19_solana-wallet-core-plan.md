# Plan — Solana wallet core (offline, pure logic)

Branch `solana`, worktree `/Users/nathanstough/Desktop/vthacks-solana`, off `main` @ `2f59a94`.
Prepared Sat 2026-09-19 ~05:45 EDT from three parallel exploration agents, the Codex review
at `docs/reports/2026-09-19_solana-devnet-addition-review.md`, and direct verification.

**Revision 3 (06:02)** — an adversarial critique of revision 2 found five further real
defects: an acceptance criterion that forbade its own best test, a verdict collapse that
would have regressed a safety gate, a byte assertion that only holds while the code is
dead, a misattributed finding, and a missing run spec. All are fixed below, and the
findings this plan does **not** address are now named rather than omitted.

**Revision 2 (05:52)** — seven Critical findings from the Codex review of revision 1
(`2026-09-19_solana-wallet-core-plan-review.md`) are incorporated below. Revision 1 was
not executable: it walked entries individually where the existing simulator nets by day,
it dropped the fresh-balance re-check at signing, its serializer covered one field of
three, and its headline fixture did not test the thing it claimed to test.

## Scope

**Wallet core only.** Four pure-TypeScript modules plus tests. Nathan assigned this lane
explicitly after another session took the checkout for the error boundary and the deploy.

**Not in this lane, and not to be touched:** `frontend/src/App.tsx`, `main.tsx`,
`index.css`, `components/**`, `src/types.ts`, `lib/**`, `solver/mockSolver.ts`,
`tests/bundle.test.ts`, `package.json`, `vite.config.ts`, `tsconfig*.json`, `Caddyfile`,
anything under `backend/`.

**Hard constraint: zero `@solana/*` imports.** `frontend/tsconfig.app.json:25` is
`"include": ["src", "tests"]` and `package.json:8` is `"build": "tsc -b && vite build"`,
so an unresolvable import under `src/` breaks `npm run build` in *every* worktree the
branch reaches. Verified by reading both files. This is **handoff Step-1 finding #8**, not review finding #8 — the review's #8 is a
different and still-open point, that *nothing joins the owner lanes*. Keeping the core
dependency-free removes the build hazard, but it does **not** close the review's #8; if
anything four modules with no call site make it worse. See "Integration" below.

## Baseline in this worktree (measured 05:41, not carried forward)

| Check | Value |
|---|---|
| `npm test` | **87 pass, 0 fail** |
| `npm run lint` | clean |
| `npm run build` | clean |
| `dist/assets/index-DPUqIubV.js` | **625,369 bytes** |

(The main checkout is at 97 tests / 626,628 B because it carries the other session's
error boundary. This branch is off `main`, which does not.)

## Design decisions

**D1 — One signed `bigint` per entry, netted by day before the walk.**
`{ date: string, amount: bigint }`, negative = outflow. Entries are first **aggregated into
one net delta per date**, then walked in date order; the running minimum is measured on the
per-day closing balances, never on intermediate within-day states. This matches
`backend/app/solver/simulate.py:35` and `mockSolver.ts:57-98`, and it is a correctness
requirement, not a style choice: with 60 opening and a same-day −20 and +20, an
entry-by-entry walk reports a minimum of 40 or 60 depending purely on array order. Dates
carry no intraday ordering, so there is no honest way to break the tie. **A permutation test
shuffles every fixture's entry order and asserts the outlook is identical.** The walk does
`running += netForDay` unconditionally and never branches on a label. This is the `simulate.py:41` /
`mockSolver.ts:61` invariant: *classification never determines direction; the signed amount
does.* If a display label is ever added it must be tested as `kind === 'inflow' && amount > 0n`,
never `kind` alone — the `generator.py:111-118` pattern, which carries a comment naming this
as "the class of both prior deferral bugs".

**D2 — `toBase(v: unknown): bigint` accepts only `/^\d+$/` strings and throws otherwise.**
Solana's `getTokenAccountBalance` and `getTransaction` both return a float `uiAmount`
alongside the exact string `amount`. Reading `uiAmount` puts a `Number` into the money path
silently. A grep test asserts `uiAmount` appears zero times in `src/wallet/`.

**D3 — `formatUnits` is string-slicing, never `Number(base)/100`.**
Sign first, then `abs.toString().padStart(decimals+1, '0')`, split at `-decimals`. Mirrors
`lib/format.ts:5-10`'s structure but not its implementation — that one uses `Math.floor` on a
`number`, correct for cents and wrong for BigInt. Tested at `12345678901234567890n`.

**D4 — Comparators never do `Number(a - b)`.** `a < b ? -1 : a > b ? 1 : 0`.

**D5 — Persistence maps every monetary field, and the parser is signed.**
`JSON.stringify` throws `TypeError` on a BigInt, inside a click handler, where **no React
error boundary catches it**. The identity carries three kinds of money — `amount`, `reserve`
and every `schedule[].amount` — so a serializer that converts only `amount` still throws.
All three convert explicitly. Note `toBase` (D2) rejects negatives by design, and schedule
entries are signed, so restoring needs a **separate signed parser** (`/^-?\d+$/`), not
`toBase`. The test asserts **deep round-trip equality** with a nonzero reserve and both
positive and negative schedule entries — not merely that no exception was thrown.

**D6 — Every wallet-authored string is checked against the banned words, and the two
verdicts stay distinct.**
`CLAUDE.md` bans `infeasib` and `guarantee` reaching the user. Revision 2 over-corrected
here: it replaced *both* verdicts with the single mandated phrase, which erased a
**safety-bearing distinction**. `2026-09-19_solana-devnet-addition.md:128-130` keeps them
apart deliberately — *"Affordable under the current schedule"* (ledger walk, unconditional)
versus *"Would be affordable if these changes happen"* (conditional on unexecuted changes)
— and **only the first enables Sign**. Neither contains a banned word, so neither was ever a
violation. Both are kept verbatim, and a test asserts the conditional verdict can never
enable Sign. The mandated phrase *"sufficient under the schedule shown"* is used where the
product asserts sufficiency, never as a replacement for the conditional wording. Enforced by
a `FORBIDDEN` loop mirroring
`tests/narrate.test.ts:8`, over an enumerated set of every string the modules can emit,
with a cardinality assertion proving the enumeration is complete (the
`tests/reasons.test.ts:188-214` pattern).

**D7 — The ledger takes signed entries including at least one inflow, and the beat fixture
tests postponement rather than amount.**
Codex finding #1: with outflows only, delaying a payment cannot improve the running minimum,
so "earliest affordable date" is a constant and the demo beat is impossible. But
"30 fails, 15 passes" is a statement about *amount* and can hold with no inflow whatsoever —
it does not test the feature. The fixture set is therefore three cases, not one:
(a) 30 today fails, 15 today passes (the beat's wording);
(b) **the same 30 fails today and first passes on a named later date**, which is the only
case that exercises postponement, and it is impossible without a dated inflow;
(c) an earlier obligation that prevents (b), proving the earliest date is not just
"the day after the inflow".
`earliestAffordableDate` is specified explicitly: evaluation starts at `asOf`, runs to a
fixed `horizonEnd`, places the payment on the candidate date, carries all obligations
forward unchanged, ignores entries dated before `asOf`, and returns `null` when no date in
the horizon clears.

**D8 — Frozen identity, guard before the first `await`, a persisted attempt, and a fresh
balance check at signing.** Codex findings #3 and #5, plus two properties revision 1 dropped.

- *Frozen identity.* Sender, recipient, mint, network, amount, reserve and schedule are
  captured into an immutable record at review; nothing is re-read from form state later.
- *Guard first.* The duplicate-submit guard is acquired **synchronously**, before any async
  call including wallet approval. Stale callbacks are rejected with the monotonic-generation
  pattern from `App.tsx:62-97` (`const mine = ++seq.current`, compared inside the callback,
  checked before any write).
- *Persisted attempt (was missing).* A frozen identity plus an in-memory guard does not
  survive a reload, so a submission whose response is lost disappears and a duplicate
  becomes possible. The attempt record — identity, signature, expiry — is **persisted before
  broadcast**, and a restored unresolved attempt keeps blocking new submissions until it
  resolves. Tested: a lost submission response followed by a reload.
- *Fresh balance at signing (was dropped).* Freezing what was reviewed does not establish
  that it is still affordable. Spending from elsewhere between review and approval can
  invalidate the verdict while every frozen field is unchanged — and the wallet explicitly
  cannot stop that spending. So approval requires **refreshed balance evidence and a second
  ledger evaluation against the frozen identity**. Tested: a balance decrease between review
  and signing blocks approval; a stale refresh callback is rejected.

**D9 — Reconciliation is atomic, slot-checked, and a null status stays `unconfirmed`.**
Codex findings #4 and #6. Marking a signature reconciled before the balance refresh succeeds
would make the retry a no-op while the outlook stays stale, so the mark and the snapshot
install together or not at all. Additionally — a *successful* refresh is not necessarily a
refresh that **includes** the transfer: the snapshot must match account, network and mint,
carry a stated commitment, and have a **context slot at least as recent as the receipt's
slot**, or it is stale and must be retried rather than installed. The atomic transition also
removes the planning scenario and inserts a history-only receipt row, so the payment is not
deducted twice. A null `getSignatureStatuses` is a cache miss, not proof of non-landing: it
stays `unconfirmed`, never `expired`. Tested: stale snapshot, failed refresh then retry,
concurrent reconciliation.

**D10 — Receipt verification has a pinned input shape, and network provenance comes from
outside the receipt.**
Codex finding #2: a recipient with no associated token account has no `preTokenBalances`
entry at all. Absent-and-zero must be **accepted**, not rejected-by-accident via `undefined`
arithmetic — and it must be distinguished from *metadata unavailable*, which is inconclusive,
not a rejection. Each rejection returns a **distinct reason code** so the tests cannot pass
on a shared short-circuit, and each mismatch is tested independently against an otherwise
valid receipt.

The verifier's input is a **normalized record this module defines**, not a raw RPC envelope:
`{ signature, slot, err, preTokenBalances[], postTokenBalances[] }` with amounts as exact
strings. Checks: expected signature, `err === null`, mint, sender delta `= −amount`,
recipient delta `= +amount`.

**`getTransaction` carries no genesis hash.** Revision 1 inherited a test asserting the
receipt rejects a non-Devnet genesis; that test cannot exist, because the field is not in
the response. Network provenance is a **separate input** captured at review from
`getGenesisHash()` and compared there. The receipt verifier asserts it was supplied and
matches the frozen identity's network — it never claims to have derived it.

## Files

Created, all new, no existing file modified:

| Path | Contents |
|---|---|
| `frontend/src/wallet/types.ts` | `Entry`, `PaymentIdentity`, `Outlook`, `Verdict`, `ReceiptResult`, state union |
| `frontend/src/wallet/units.ts` | `parseUnits`, `formatUnits`, `toBase` |
| `frontend/src/wallet/ledger.ts` | signed walk, running minimum, breach date, earliest affordable date |
| `frontend/src/wallet/receipt.ts` | `verifyReceipt` over a `getTransaction` shape |
| `frontend/src/wallet/state.ts` | frozen identity, duplicate guard, terminal states, atomic reconcile |
| `frontend/src/wallet/fixtures.ts` | typed fixtures incl. the 30-fails-15-passes beat and receipt shapes |
| `frontend/tests/wallet-units.test.ts` | ~16 tests |
| `frontend/tests/wallet-ledger.test.ts` | ~20 tests (incl. permutation invariance, 3 beat fixtures) |
| `frontend/tests/wallet-receipt.test.ts` | ~14 tests (distinct reason code per rejection) |
| `frontend/tests/wallet-state.test.ts` | ~22 tests (incl. reload recovery, fresh-balance gate, slot recency) |

**Tests go flat in `frontend/tests/`, not `src/wallet/__tests__/`.** `package.json:11` is
`node --experimental-strip-types --test tests/*.test.ts` — a shell-expanded flat glob. Tests
under `src/**` would be silently skipped, exit 0, and report success. Fixing that glob is
another lane's file, so this plan sidesteps it: flat `wallet-*.test.ts` files match the
existing pattern and run today, with no `package.json` change and no cross-lane collision.

## Execution order

1. `types.ts` — no logic, unblocks the rest.
2. `units.ts` + `wallet-units.test.ts`. Everything downstream consumes it.
3. `ledger.ts` + `wallet-ledger.test.ts`, including the 30/15 beat fixture.
4. `receipt.ts` + `wallet-receipt.test.ts`.
5. `state.ts` + `wallet-state.test.ts`.
6. Banned-word sweep test across all four modules' emitted strings.
7. **Mutation pass, 20 minutes, budgeted not optional.** Mutations must change *production
   behaviour*, never test input — deleting a fixture row proves nothing. Each mutation is
   recorded with the specific assertion that caught it:

   | Module | Mutation |
   |---|---|
   | `units` | drop the `padStart` in `formatUnits`; accept `/^\d*\.?\d*$/` in `parseUnits` (admits `''` and `'.'`); return `5n` for `'0.5'` |
   | `ledger` | flip `>=` to `>` in the reserve comparison; remove the per-day aggregation; treat a negative entry as positive |
   | `receipt` | skip the mint check; skip the recipient-delta check; treat absent pre-balance as a rejection; accept `err !== null` |
   | `state` | remove the duplicate guard; move it after the first `await`; mark reconciled before the snapshot installs; return `expired` on a null status; skip the slot-recency check |

   Any mutation that kills nothing means that test is decorative — fix the test, not the
   mutation. This project has shipped a vacuous test three times and mutation testing is
   what found all three.
8. `npm run lint && npm run build && npm test` → expect **87 + ~72 = ~159 pass**, lint clean,
   build clean, `dist/assets/index-*.js` still **625,369 bytes** (the core is unreferenced by
   `App.tsx`, so it must not enter the bundle at all).

## Acceptance criteria

Verification order is **lint → build → test**, always. `bundle.test.ts` reads `dist/`
unconditionally, so running tests before a build validates stale output — the defect already
accepted as finding 6 of `docs/reports/2026-09-19_frontend-ux-plan-review.md`.

- `npm test` → 87 + ~72, 0 fail.
- Outlook is invariant under entry permutation (D1).
- Persisted attempt survives a simulated reload and still blocks duplicates (D8).
- Deep round-trip equality of the serialized identity, reserve and signed schedule (D5).
- `npm run lint` clean; `npm run build` clean.
- **Main chunk unchanged at 625,369 bytes — and this criterion is honest about its own
  weakness.** Rollup never reads an unreferenced module, so this passes *because the
  deliverable is not in the build*. By `frontend/tests/bundle.test.ts:20-21`'s own standard
  that is "a check that silently passes because it had nothing to read". It is recorded as a
  **baseline for the lane that wires the wallet up**, not as evidence this lane is safe. It
  is deliberately **not** in the regression definition: the other session's `error-boundary`
  branch already moves the figure to 626,628 bytes, so an exact-byte literal would fire on
  correct work at merge. The durable form is a delta bound re-measured on the merged tree.
- Zero `@solana/*` imports: `! grep -rq "@solana" frontend/src/` (negated — a bare `grep`
  that finds nothing exits 1 and would fail a `set -e` script).
- **Fixtures are faithful and the parser ignores `uiAmount` anyway.** Revision 2 asserted
  `grep uiAmount frontend/src/wallet/` returns nothing — which would have banned the only
  test that proves D2, because a truthful `getTransaction` fixture *contains*
  `uiTokenAmount.uiAmount`. Replaced by two stronger checks: fixtures carry the real
  `uiAmount` field with a **deliberately wrong value**, and a test asserts the verifier's
  result is unchanged by it; plus no *source* module under `src/wallet/` other than
  `fixtures.ts` mentions `uiAmount` (a read check, not a token check).
- Every guard has a counterfactual test that fails when the guard is removed, recorded by
  the step-7 mutation pass.
- No wallet string matches `/guarantee/i` or `/infeasib/i`.
- Backend untouched: no file under `backend/` in the diff.

## Regression definition

Any of: `npm test` below the pre-change count on whatever base is checked out (87 here, 97
once `error-boundary` merges); lint or build failing; any `@solana/*` import under
`frontend/src/`; any wallet string matching `/guarantee/i` or `/infeasib/i`; the backend gate
moving off **1262** (`.venv/bin/pytest backend/ -q -m "not perf"`) — a diff check alone would
miss a shared-fixture effect. The main-chunk byte count is a recorded baseline, not a
regression trigger, for the reason given above.

## Out of scope, handed to other lanes

These are real and verified, and none are mine to fix:

1. **`Caddyfile:17` sets `connect-src 'self'`**, which blocks the Devnet RPC entirely. The
   wallet would work locally and be dead on the deployed site. Deploy lane.
2. **`crash.ts:14` returns `error.message` unmodified**, so a thrown message containing
   "guarantee" or "infeasible" renders on screen — a live `CLAUDE.md` hole that exists today,
   independent of Solana. `mockSolver.ts:193,215` already throw raw strings into it.
   Error-boundary lane.
3. **`mockSolver.ts:410` and `assemble.py:77` mark any `kind === 'income'` row as a payday,
   with no sign check**, so a clawback reads as "Payday lands on …". **Latent, not live** —
   the shipped fixtures at `src/fixtures/scenarios.ts:20,27` carry only positive income. It
   becomes visible the moment the synthetic account generator feeds the UI, because
   `backend/tests/fixtures/accounts.py:91-93` plants a negative `PAYROLL ADJUSTMENT` 30% of
   the time. Both implementations must change together or parity breaks.
4. **The test glob** (`package.json:11`) and **bundle-test scoping**. Note for whoever takes
   it: `sh` has no `globstar`, so an unquoted `**` silently keeps today's behaviour; bare
   `node --test` was measured to give the same count and picks up nested dirs.


## Findings this plan does NOT address

Named explicitly, because revision 1 dropped them silently and a reader deserves the list.

| Finding | Why not here |
|---|---|
| Review **#2**, ATA creation + ~0.002 SOL rent | Needs a live transaction. Belongs to the spike. **Recorded alternative:** restrict the spike to a pre-provisioned recipient and say so on screen. |
| Review **#7**, deterministic RPC failure tests | No RPC layer in this lane. **But the seam is a design decision made now:** `state.ts` takes its clock and its RPC as injected parameters, so these tests are writable later without redesigning it. That is the one thing this lane must not get wrong for #7's sake. |
| Review **#9**, SDK pinning + `solana:devnet` binding | No SDK is installed in this lane by design. |
| Review **#10**, the solver adapter, `api.ts:48`, `CENTS_ABS` | The adapter is the explicit stretch and is not built. `api.ts` is another lane's file. |
| Review **#11** + handoff **#10**, prize wording | Docs lane. `docs/prize-strategy.md:51` and `:94` both still say Skip and must flip together or not at all. |
| Handoff Step-1 **#9**, `bundle.test.ts` scoping | Another lane's file. Blocks the first lane that installs a Solana package; **currently unowned.** |
| Handoff **Step 0**, the go/no-go | Nathan reopened this workstream and assigned this lane directly in session on Sat ~05:20, overriding a recommendation to close it. That decision is his and is recorded here because it exists nowhere in the repo. |

## Integration — the gap this lane creates

Four modules with no call site are dead code, and the acceptance criteria above *require*
them to stay dead. That is deliberate for this commit and unacceptable as an end state, so
the lane's last deliverable is **a handoff artifact for the frontend lane**: the 40–60 lines
across `App.tsx`, `index.css` and a nested `<Suspense>` + boundary that wire a wallet route,
with the note that the **root boundary alone is not enough** — a lazy chunk that fails to
load throws into the nearest boundary, and today the nearest is the root one, which replaces
the entire planning demo. That directly contradicts the acceptance test at
`2026-09-19_solana-devnet-addition.md:166-167`.

## Run spec

`CLAUDE.md` requires one per change. `docs/specs/2026-09-19_solana-wallet-core.md` is
created before execution and is the audit record; this plan file persists beside it.

## Build constraints on the new files

`tsconfig.app.json` sets `erasableSyntaxOnly: true` (`:22`), `verbatimModuleSyntax: true`
(`:14`), `noUnusedLocals`/`noUnusedParameters: true` (`:20-21`). So: **no `enum`**, no
`const enum`, no parameter properties, no namespaces — the state union is a string-literal
union. Type-only imports use `import type`. Test imports carry an explicit `.ts` extension.
Any of these breaks both `npm run build` and `node --experimental-strip-types`.

**`strictNullChecks` is OFF** (verified via `tsc -p tsconfig.app.json --showConfig`: no
`strict`, no `strictNullChecks`, no `noUncheckedIndexedAccess`). So `array.find(...)` types
as `T`, not `T | undefined`, and D10's absent-pre-balance path compiles clean and throws at
runtime. **The compiler will not catch this class of bug in this lane.** Every lookup that
can miss is written with an explicit presence check and tested, because nothing else will
find it. `tsconfig*.json` is out of lane; raising strictness is a recommendation to the
frontend lane, not a change made here.

## A note on the dependency symlink

`frontend/node_modules` is symlinked to the other session's tree, per `CLAUDE.md`. But
`2026-09-19_solana-devnet-addition.md:187` resolved this collision the opposite way — "own
worktree with its own `node_modules`… the main tree's `node_modules` is never touched". The
symlink is the right call here (no package is being installed, and reinstalling costs time
this lane does not have), but the consequence is recorded: **the 625,369-byte baseline was
produced by another session's dependency tree** and any `npm install` over there changes this
branch's build output.

# Run spec — synthetic accounts, Nessie, and the first deploy (2026-09-19)

Branch `data-deploy`, worktree `/Users/nathanstough/Desktop/vthacks-data`, off `main` at
`70bac4d`. Frozen after commit; later corrections go in a dated note at the end, never by
rewriting a line above.

## Problem

Three things the submission still needs, in one dependency chain.

1. **A product path for synthetic accounts.** A realistic generator exists at
   `backend/tests/fixtures/accounts.py`, but as a test fixture nothing in `backend/app/`
   can import it. The three shipped presets in `frontend/src/fixtures/scenarios.ts` share
   one identical 15-row schedule; only the opening balance and cushion differ. A judge sees
   the same account three times.
2. **Nessie** has nothing to seed a customer from, and the Capital One track is the one we
   are building for.
3. **The deploy has never been run.** `deploy.sh`, `Caddyfile` and the systemd unit were
   written and never exercised.

`deploy.sh:51` rsyncs `backend/app/` and nothing else from the backend, so a generator left
in `tests/` works on the laptop and 500s on the box. That settles where it goes.

## What we verified before planning (not inherited from the handoff)

The governing handoff is `docs/handoffs/2026-09-19_data-nessie-deploy-handoff.md`. Several
of its claims are stale; these were measured on this branch.

- **The gate is 1263**, not 1262. Commit `70bac4d` landed twelve minutes after the handoff
  was written and added one test. Measured twice, from inside this worktree.
- **The handoff's two headline bugs are already fixed.** The clawback-as-payday sign check
  is present at `backend/app/solver/assemble.py:84` and
  `frontend/src/solver/mockSolver.ts:415`; the `crash.ts` message leak is closed at
  `frontend/src/lib/crash.ts:42-51`. Do not spend budget there.
- **`rapidfuzz` was never missing** from `backend/requirements.txt`, and nothing imports it.
- **The Nessie key works.** Both documented hostnames answer identically; `prod-api` chosen.
  A **wrong** key returns `200 []`, indistinguishable from an empty sandbox; a **missing**
  key returns `502 {"message": "Internal server error"}`. There is no 401 and no 403.
  Write-then-read verified: `POST /customers` → 201 with the created object and its `_id`,
  `GET /customers/{id}` → 200. That resolves caution 6 of `docs/nessie-agent-brief.md`.
- **`MERCHANTS` is 36 rows**, and the golden hash of `windows(300)` on this branch is
  `8d4ddf3092a22cb4de03d50d23fe558420b2ef7eb2cb1272f77948e543081048`.

## Defects found while planning, none of them in the handoff

**D-A. The deploy would report success and serve nothing.**
`backend/app/main.py:32` is
`DEFAULT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"`. On the laptop
that is `<repo>/frontend/dist`. On the box `deploy.sh:51` flattens `backend/app/` to
`$APP_DIR/app/`, so `__file__` is `/opt/overdraft-guard/app/main.py`, `parents[2]` is
`/opt`, and it looks for `/opt/frontend/dist` while the bundle sits at
`/opt/overdraft-guard/frontend/dist`. `main.py:92` guards the mount with `is_dir()`, so it
fails **silently**: the API answers, `/health` returns 200, `deploy.sh` prints `deployed`,
and the site is a 404. The same off-by-one is at `backend/app/chat/gemini.py:36`
(`parents[3]` → `/opt/.env`), harmless only because systemd supplies the key.

**D-B. STRUCK after Codex review — this was not a defect.**
The original claim was that a merchant descriptor reaching `plan[].detail` with no
server-side banned-word check is a CLAUDE.md violation. It is not.
`backend/tests/test_candidates_policy.py:357-361` deliberately asserts
`"GUARANTEED AUTO PROTECTION" in c.detail`, and `:378-380` strips the descriptor before the
banned-word sweep with the comment *"The description is the user's own statement line and
is exempt."* CLAUDE.md governs what **this product** claims, not what a bank statement says
about a merchant. Sanitising `detail` would fight an intentional test and misrepresent the
user's own data.

The measurement stands and is worth keeping for context: 88 of 300 generated windows carry
`GUARANTEED AUTO PROTECTION`, and 104 emitted candidates put it in `detail`. That is
expected behaviour, not a leak. What it does do is make **D-C** routine.

**D-C. The chat scrubber corrupts merchant names into product copy.**
`backend/app/chat/__init__.py:30` rewrites `\bguaranteed\b`. Reproduced on this branch:

    scrub("Skipping GUARANTEED AUTO PROTECTION frees $38.59.")
    → "Skipping sufficient under the schedule shown AUTO PROTECTION frees $38.59."

Worse than a leak: visibly broken text reaching the user as `ChatResponse.reply`. A Nessie
payee such as "Guaranteed Rate" does the same.

**D-D. `deploy.sh` dies on a fresh box, twice.** Under `set -euo pipefail`, line 55 rsyncs
into `/etc/caddy/`, which does not exist until Caddy is installed, and line 62 runs
`python3 -m venv` without `python3-venv`. **Confirmed on the real box**: Ubuntu 24.04.5 had
neither. Nothing in the script installs either.

**D-E. `__DOMAIN__` unsubstituted does not fall back to plain HTTP.** `Caddyfile:4-7`
claims "the site answers on the box's IP over plain HTTP". It does not: Caddy parses the
literal `__DOMAIN__` as a hostname matcher and serves only requests carrying that `Host`.
And `deploy.sh:80-86` polls `curl http://127.0.0.1:8000/health` over ssh, bypassing Caddy —
so the health check passes while the public URL serves nothing.

**D-F. Truncation can evict a pinned candidate, 422-ing the whole solve.**
`generator.py:178-180` sorts and truncates at `req.limit`; `schemas.py:202-205` rejects
locks naming an id not in the set. Adding one row to a truncated account can push a
previously offered candidate below the cut. Existing coverage runs at `limit=MAX_N` and
never truncates, so it misses this. Directly relevant: any endpoint that re-fetches an
account while the client holds a lock.

**D-G. The perf guard is dead code.** `test_candidates_roundtrip.py:208-209`
`if len(generated) > MAX_FREE: continue` can never fire, because `limit` defaults to
`MAX_FREE` and the generator slices to it. 34 of 300 accounts already sit at exactly 18
candidates (2^18 subsets each). A denser product profile makes the perf run grow without
anything failing — it just hangs.

## Decisions

**D1 — share the table, not the algorithm.** The handoff frames decision 1 as "one source
of truth if generation stays byte-identical, else two tables". That is a false binary: the
required product behaviour (business-day pay with jitter, heavy-tailed amounts, a planted
dip) *is* a different algorithm. So `MERCHANTS`, `window()` and `windows()` move to
`backend/app/` **unchanged**, the fixture becomes a thin re-export, and the product profile
is a **separate** function over the same table. One table, two declared profiles, nothing
pinned moves.

The RNG call sequence is the contract. Do not reorder, dedupe or extend `MERCHANTS`
(`rng.choice` is index-based over the 36-tuple), do not change `seed=20260919`, do not
hoist the `rng.random()` probability gates. Verified by golden hash, before and after.

**D2 — `solve_request()` stays in `tests/`.** It fabricates `locks` and `previous_plan`
defaults and a test `buffer_cents`; it is harness shape, not product shape, and
`deploy.sh:51` ships everything under `backend/app/` to production.

**D3 — the Nessie adapter uses `urllib`, not `httpx`.** Following the precedent in
`backend/app/chat/gemini.py:3-5` and the header of `backend/requirements.txt`: every
package is one more way the box's `pip install` dies.

**D4 — credentials are verified write-then-read, never by a list call.** A read cannot
distinguish a bad key from an empty sandbox. `200 []` is treated as *unverified* and
surfaced as a loud configuration error, never as empty data.

**D5 — money crosses the Nessie boundary as decimal strings.** Nessie returns dollars as a
JSON number; `19.99 * 100` is `1998.9999999999998` and `int()` of that is `1998`.
`StrictInt` catches a raw float but cannot catch an integer that was already rounded wrong.

**D6 — the banned-word rule is enforced on the product's own words, not the user's data.**
Amended after Codex review, see D-B. Descriptors are exempt, as the suite already encodes.
The enforced set is the enumerated display fields: `verdict`, `qualifier`,
`certificate.sentence`, `plan[].reason`, `plan[].label`, `candidates[].label`, plus the
product's own wrapper text around a descriptor in `detail`. Transaction **ids** are caller
text and are not scanned — `test_candidates_policy.py:350-351` legitimately uses
`guaranteed_1`. Never weaken `BANNED` or `bundle.test.ts`.

**D7 — scope is backend only.** No frontend changes. The three canned scenarios stay
exactly as they are; that is what keeps the offline demo alive when the venue wifi dies.

**D8 — provenance is delivered in the API, the on-screen label is deferred.** Added after
Codex review, which caught that "labelled as modelled **on screen**" contradicted the
backend-only scope. This change ships a required `source: "modelled"` field and the Nessie
fallback-disclosure flag; rendering them belongs to the frontend lane. Nothing here claims
an on-screen label it does not ship.

## Acceptance criteria

- `.venv/bin/pytest backend/ -q -m "not perf"` → **≥1263**; **no test moves from selected
  to deselected** (the raw deselect count necessarily rises when the `nessie` marker is
  added — amended after Codex review, which caught that registering a marker does not
  deselect it)
- `.venv/bin/pytest backend/ -m perf -q -s` → **8 passed**, and the 300-account
  cross-engine agreement still runs, still agrees, and does not grow materially beyond its
  ~137 s baseline
- `cd frontend && npm run lint && npm run build && npm test` → **191 passed**, in that order
- Canaries unmoved: `clears` → tier 1, 3 changes; `gap` → tier 3, 9 changes,
  `"$27.62 more by Sep 24"`; demo account → 14 candidates, `rows_considered` 13,
  `protected [t_card, t_verizon]`, `not_actionable [t_spotify]`
- Golden hash of `windows(300)` **unchanged** at `8d4ddf30…81048`
- No banned word reaches an enumerated display field (D6); `detail`'s descriptor is exempt
- `source: "modelled"` present on every sample-account response (D8)
- **The deployed site actually serves**: public `GET /` returns 200 HTML, a referenced JS
  asset loads, and a public `POST /api/solve` returns the right tier — not merely `/health`

## Regression

Gate below 1263 · any canary moving · the golden hash changing · frontend below 191 · a
float in any money path · "infeasible" or "guarantee" reaching a user surface.

## Docs this change edits

- this run spec
- `docs/features/accounts.md` (new)
- `docs/api-contract.md` — the new endpoint
- `.env.example` — Nessie config, empty values
- `README.md:25,29` — venv rebuild uses `requirements-dev.txt`; the `wheels/` line is
  already wrong because `wheels/` is gitignored and absent from a fresh clone
- `docs/features/nessie.md` — conditional, only if the adapter lands here

---

## Results (recorded at commit, 2026-09-19)

**Gate: 1263 → 1979 passed, 1 skipped, 8 deselected.** No test moved from
selected to deselected; the one skip is the live Nessie probe, which is opt-in.

| Phase | Commit | Gate |
|---|---|---|
| 0+1 generator moved | `6d6709b` | 1266, golden hash identical |
| 2 scrubber + wording | `35a600a` | 1276 |
| 3 product profile + endpoint | `9e961d3` | 1951 |
| 4 Nessie adapter | `f968723` | 1970 + 1 skipped |
| 5 deploy | `a06d5e5` | 1979 + 1 skipped |

- Golden hash **unchanged** at `8d4ddf30…81048`. D1's premise held: the moved
  module's output is byte-identical to the fixture's before the move.
- Frontend: lint clean, build 626,814 bytes, **193 passed**. The handoff's 191
  and 626,628 predate `70bac4d`, which added the `crash.ts` tests and guard.
- Nessie live write-then-read verified against the sandbox.
- Gemini verified live; `gemini-3.8-flash` answered on retry after one
  "experiencing high demand", which is why `GEMINI_FALLBACK_MODELS` is now set.

## Defects found by running the deploy, not by reading it

**D-B was struck** — see above. It was an intentional design, not a defect, and
the Codex review caught the mislabelling.

Three further defects surfaced only because the deploy was actually executed:

- **rsync does not create missing parent directories.** Shipping `frontend/dist/`
  to a box with no `$APP_DIR/frontend` died with `mkdir ... No such file or
  directory`, after the frontend had already built — so it read as a build
  failure.
- **Vultr's Ubuntu image ships `ufw` active**, allowing only ssh. The deploy ran
  clean end to end, Caddy served `:80` correctly, `/health` returned 200, and the
  site was reachable from nowhere but the box. Now a preflight.
- The public-origin check is what caught it. `/health` over ssh goes to
  `127.0.0.1:8000` and never touches Caddy, so it cannot see this class of
  failure at all.

## Open at commit

- **Firewall**: `ufw allow 80/tcp && ufw allow 443/tcp` is the user's to run;
  modifying firewall rules is not something this session performs.
- **Domain**: `safetospend.us` not yet registered; the deploy currently
  substitutes `:80` and serves plain HTTP.
- **On-screen provenance**: shipped as API fields only, per D8. The frontend lane
  renders them.

---

## Audit round — dated note (2026-09-19, after commit `4e82dcf`)

Per this spec's own header, corrections go here rather than by rewriting a line
above. The adversarial pre-audit graded the change **Fail**. It was right.

**Gate after the fixes: 1987 passed, 1 skipped, 8 deselected** (from 1979).
Fixes committed as `587da10`.

### Correctness bugs that 1979 passing tests did not catch

- **`as_of` was a hard 500.** `schemas.py` called `iso(v, "as_of")` against a
  one-argument helper. Every endpoint test sent `{}`, `{"seed": n}` or
  `{"horizon_days": n}` — not one passed a documented field. Five `as_of` tests
  added, including the 422-not-500 case the contract promises.
- **The scrubber was defeated by caller data.** Protected spans come from request
  descriptions, so a client naming a transaction "guaranteed savings" kept the
  banned word in the reply. Protection now requires the descriptor to be upper
  case and multi-token; a final check falls back to scrubbing everything if a
  banned word survives outside a restored descriptor.
- **The scrubber's output depended on `PYTHONHASHSEED`.** `sorted(set, key=len)`
  ties broke on set iteration order. The plan cited `lexicon.py:16-19` for
  exactly this hazard and then reproduced it.
- **`to_cents(True)` returned 100.** `bool` is an `int` subclass.
- **The D-A fix reintroduced D-A** for an `APP_DIR` named `backend`. Production
  no longer infers: `deploy.sh` writes `OVERDRAFT_DIST` explicitly.

### Tests that passed without testing

- **The dip test was vacuous.** Four seeds in 300 drew every charge on or after
  the first payday, so `opening` clamped to 0 and the test asserted `0 < 2500`
  over an empty loop.
- **The `test_wording` counterfactual was circular** — it rebuilt `user_facing`'s
  field list inline, so deleting a field from the real sweep left it green.

### Claims struck as untrue

- **D8 is not met.** The Nessie fallback-disclosure flag does not ship. `source`
  is the only provenance field this change delivers.
- **Plan steps 4.4a, 4.5 and 4.6 were never implemented.** `app/nessie/` is
  verified and tested but wired to no route; the seed-and-read-back workflow and
  `not_round_tripped` do not exist. `docs/features/accounts.md` said otherwise
  and has been corrected.
- **Step 3.4a (D-F eviction) and Step 3.5 (D-G perf guard) were not done.** They
  are struck from this change rather than claimed: D-F needs a truncation-and-
  refetch test in `test_candidates_roundtrip.py`, and D-G needs the dead
  `continue` at `:208-209` replaced. Both belong to a follow-up.
- **"Always something to solve" was too strong.** A dip is not a solvable dip;
  about 7% of seeds reach tier 3 with an empty plan, which is a wanted outcome.
  A distribution test now pins it.
- **The contract's "post it straight to the other two endpoints"** is false under
  `extra="forbid"`. Corrected in the contract and the schema docstring.

### Confirmed sound by the audit

`to_cents` and the whole decimal path; D4 write-then-read and its tests;
`_redact` and the key-never-logged test; D1's move, with a golden hash that is
real and non-vacuous; the `nessie` marker double-guard; `test_requirements.py`;
and `deploy.sh`'s preflights plus the public-origin checks. No secrets, no TODOs,
no debug code in `backend/app/`.

---

## Scope revision — accepted by Nathan, 2026-09-19

The Codex audit returned **Fail** on two dimensions after four rounds, and named
the remedy itself: *"Complete the workflow and disclosure, or obtain an explicit
scope revision."* Nathan reviewed both and accepted them, in those words: "if
those are the only two fails its fine."

**Struck from this change, deliberately, not forgotten:**

1. **The Nessie seed-and-read-back workflow**, `not_round_tripped`, the D8
   fallback-disclosure flag, and any HTTP route for the adapter. What ships is the
   transport, the write-then-read credential check, the decimal money path, key
   redaction and row normalisation — all tested, and exercised against the live
   sandbox. `docs/features/nessie.md` leads with what is *not* built.
2. **D-F** (the truncation/eviction 422) and **D-G** (the dead perf guard at
   `test_candidates_roundtrip.py:208-209`). Both are real, both are documented
   above, neither is fixed.

**Still open, and not a scope decision — just unfinished:**

3. **The public deployment checks have never passed.** `deploy.sh` performs them
   (public HTML, a referenced JS asset, and a known scenario solving to the right
   tier through the public origin), but the box sits behind `ufw` with only ssh
   allowed, so they have never run green. The audit is right that implementation
   is not evidence. One command unblocks it:

       ssh root@64.177.48.139 'ufw allow 80/tcp && ufw allow 443/tcp'

   Modifying firewall rules is the user's to run, not this session's.

**One audit finding overridden, on purpose.** Codex treats a descriptor that is
literally a banned word as a bypass of the chat scrubber. Those are restored
verbatim instead, because the codebase already has a settled position:
`test_candidates_policy.py:357` *requires* `GUARANTEED AUTO PROTECTION` in
`detail`, and `:378-380` exempts descriptors as "the user's own statement line".
A merchant name the user supplied is their data, not a claim this product is
making. Recorded here because overriding an audit finding should be visible.

**Everything else the audit raised across four rounds was fixed.** Final gate:
**2002 passed, 1 skipped, 8 deselected**. Perf 8 passed, 300 accounts agreeing in
~126 s, under the ~137 s baseline. Golden hash byte-identical to `70bac4d`. All
canaries matched.

## Deploy — dated note (2026-09-19, evening)

The one audit finding left unfinished when this spec was frozen: `deploy.sh`'s
public checks existed and had never passed. They pass now. Nothing above this
line is rewritten.

Nathan opened the firewall (`ufw allow 80/tcp && ufw allow 443/tcp`), which was
the whole blocker — the previous deploy had completed cleanly onto a box
reachable from nowhere but itself.

`./deploy.sh root@64.177.48.139` from this worktree, no `DOMAIN` set, so Caddy
listens on `:80` and the site is plain HTTP on the bare IP. Every check in the
script passed on the first run:

| Check | Result |
|---|---|
| internal `/health` over ssh | `{"ok":true}` |
| public `GET /` contains `<div id="root">` | pass |
| the JS asset the page references loads | pass |
| public `/api/accounts/sample` says `source: "modelled"` | pass |
| public `/api/solve` returns tier 3 for `deploy/smoke-gap.json` | pass |

Verified again independently, outside the script: `GET /` 200, the sample
endpoint answering with a real generated account, and the gap scenario
returning tier 3 through the public origin.

**Serving: http://64.177.48.139**

Still to do, and not this note's to decide:

- **A domain.** Caddy needs one for HTTPS, and it is its own MLH track. Without
  it the site is plain HTTP on an IP, which is fine for a smoke test and not
  fine for a judge. `safetospend.us` was the chosen name.
- **`/api/accounts/nessie` is not on the box.** It answers 405 there, correctly:
  the route lives on `nessie-demo`, which is not merged. The box is serving
  `data-deploy`.
- **The box bills at roughly $1.85/day.** Destroy it after judging.

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

# Implementation plan — synthetic accounts, Nessie, deploy (2026-09-19)

Run spec: `docs/specs/2026-09-19_synthetic-accounts.md`. Branch `data-deploy`, worktree
`/Users/nathanstough/Desktop/vthacks-data`, base `70bac4d` + `ac2af08`.

Ordered so each step leaves the gate green. Stop and report if any step moves the gate
below 1263 or changes the golden hash.

---

## Phase 0 — pin the baseline (no production code)

**Step 0.1** — `backend/tests/test_accounts_golden.py` (new).

```python
GOLDEN_SHA256 = "8d4ddf3092a22cb4de03d50d23fe558420b2ef7eb2cb1272f77948e543081048"

def test_generation_is_byte_identical_for_the_pinned_seeds():
    h = hashlib.sha256(json.dumps(windows(300), sort_keys=True).encode()).hexdigest()
    assert h == GOLDEN_SHA256
```

Plus `assert len(MERCHANTS) == 36` and a test asserting the first and last rows by value,
because `rng.choice` is index-based and a reorder is invisible to a length check.

Run the gate. Expect **1263 + 3**. This test must exist *before* anything moves — it is the
only thing that can prove D1 held.

---

## Phase 1 — the generator moves (D1)

**Step 1.1** — create `backend/app/accounts/__init__.py`, one-symbol façade, matching
`backend/app/candidates/__init__.py:1-11` (docstring pointing at the feature doc,
`from __future__ import annotations`, explicit `__all__`).

**Step 1.2** — create `backend/app/accounts/merchants.py` holding `MERCHANTS` moved
verbatim from `backend/tests/fixtures/accounts.py:21-60`. **Do not touch a row.** Two are
load-bearing traps: `"GAP INSURANCE PREMIUM"` (:53, must not classify as clothing) and
`"GUARANTEED AUTO PROTECTION"` (:59).

**Step 1.3** — create `backend/app/accounts/profiles.py` with `window()` and `windows()`
moved verbatim from `:63-119`. The deferred `from app.schemas import CENTS_ABS` inside
`opening_for_mixed_tiers` becomes a top-level import **only if** that function moves; per
D2 it does not — it stays in `tests/`, so leave its deferral alone.

**Step 1.4** — reduce `backend/tests/fixtures/accounts.py` to a re-export shim plus the two
stayers:

```python
from app.accounts.merchants import MERCHANTS
from app.accounts.profiles import window, windows
```

keeping `opening_for_mixed_tiers` (:122-141) and `solve_request` (:144-161) in place. This
is what avoids editing the eight call sites.

**Step 1.5** — verify the subprocess landmine. `backend/tests/test_candidates_policy.py:655`
carries `from tests.fixtures.accounts import windows` **inside a string literal** (`_DUMP`,
:650-661) run under two `PYTHONHASHSEED` values. The shim keeps it working; confirm by
running `test_two_processes_with_different_hash_seeds_produce_the_same_words` explicitly.

**Gate here.** Golden hash must be unchanged and the count back at 1266. If the hash moved,
**revert Phase 1** — do not patch it. D1's premise has failed and the design changes.

---

## Phase 2 — the scrubber corruption (D-C)

**Corrected after Codex review.** The original Phase 2 treated a merchant descriptor
reaching `detail` as a defect (D-B). It is not. `test_candidates_policy.py:357-361`
deliberately asserts `"GUARANTEED AUTO PROTECTION" in c.detail`, and `:378-380` strips the
descriptor before the banned-word sweep with the comment *"The description is the user's
own statement line and is exempt."* CLAUDE.md's rule governs what **this product** claims,
not what a bank statement says. **D-B is struck.** Do not sanitise `detail`; doing so would
fight an intentional test and lie about the user's own data.

What remains is unambiguous.

**Step 2.1 — the chat corruption (D-C).** `backend/app/chat/__init__.py:30` rewrites
`\bguaranteed\b` in Gemini's reply. Reproduced on this branch:

    scrub("Skipping GUARANTEED AUTO PROTECTION frees $38.59.")
    → "Skipping sufficient under the schedule shown AUTO PROTECTION frees $38.59."

The scrubber must not rewrite a word that occurs inside a transaction descriptor the model
was given. Preferred fix: pass the descriptors into `scrub` as protected spans, restore
them verbatim after substitution, and keep the final banned-word check on everything
outside those spans — Codex finding 2 is right that removing descriptors from the prompt
alone is insufficient, because they also arrive via plan details and conversation history.

Tests: reproduce the corruption and assert it no longer occurs; **and separately** assert a
genuine product claim containing "guaranteed" is still scrubbed. A fix that protects the
descriptor by disabling the scrubber fails the second.

**Step 2.2 — the display-field sweep, scoped.** Codex finding 9: scanning every
`StrictStr` is wrong — `test_candidates_policy.py:350-351` uses the transaction ids
`guaranteed_1` and `guaranteed_2`, which are legal caller text. **Enumerate display fields
explicitly**: `verdict`, `qualifier`, `certificate.sentence`, `plan[].reason`,
`plan[].label`, `candidates[].label`. `detail` is exempt per the correction above, minus
the product's own wrapper text, exactly as `:378-380` already does it.

Counterfactual, stated the right way round: **inject** prohibited text into each enumerated
field and assert the checker catches it. (The original phrasing — remove a field and expect
failure — was backwards; removing a checked field hides failures.)

Write the pattern with character classes as `frontend/src/lib/crash.ts:42` does, so the
test file does not itself trip `bundle.test.ts`. Never weaken `BANNED` at `wording.py:20`.

**Gate.**

---

## Phase 3 — the product profile and its endpoint

**Step 3.1** — `backend/app/accounts/product.py`, a **separate** generation function over
the same `MERCHANTS`. Required behaviour, each with its P2 test:

- business-day-adjusted pay with jitter (P2 #4, #5)
- heavy-tailed amounts, not uniform (P2 #6)
- a planted dip before the first payday (P2 #7)
- integer cents throughout; no float touches money (P2 #3)
- respects `CENTS_ABS`, `MAX_SCHED`, `MAX_T`, `ID_RE` (`schemas.py:18-40`) (P2 #2)
- carries a **modelled** flag; never presented as real bank data (P2 #10)

Follow the `app/candidates` idiom: frozen module-level tables validated at import
(`policy.py:123` calls `_check()` at import), tuples not sets
(`lexicon.py:16-19` — a set would let iteration order vary with `PYTHONHASHSEED`), and a
`_verify()` post-condition pass using `raise`, not `assert`, so `-O` cannot remove it
(`generator.py:202-228`).

**Step 3.1a — the endpoint contract** (Codex finding 8; this was unspecified).

    POST /api/accounts/sample
    request  { "seed": int|null, "as_of": "YYYY-MM-DD", "horizon_days": int (14..45) }
    response { "as_of", "horizon_end", "opening_balance_cents", "buffer_cents",
               "scheduled": [ScheduledTxn], "source": "modelled" }

- `seed` null → server picks and **returns** it, so any account a judge sees is
  reproducible from the response alone.
- `horizon_days` defaults to 30, bounded 14..45 to stay inside `MAX_T` and clear of the
  perf cliff (Step 3.5).
- `source` is a required literal `"modelled"` — the provenance field, always present, never
  omitted. This is the API half of the "labelled as modelled" requirement; see the scope
  note below.
- Reuses `ScheduledTxn` from `app/schemas.py` so `/api/candidates` and `/api/solve` accept
  the body unchanged.
- **Edge case Codex named:** if business-day adjustment leaves no day before the first
  payday for the planted dip, the profile must widen the horizon or move the payday rather
  than emit an account with nothing to solve — and a test must assert the dip exists on
  every seed (P2 #7), which would catch a silent skip.

**Scope correction (Codex finding 4).** P1 scoped this to the backend, but the run spec's
acceptance criteria say "labelled as modelled **on screen**". Those contradict. Resolution:
this change delivers the `source: "modelled"` field and the Nessie fallback-disclosure flag
**in the API**, and the on-screen rendering is explicitly **deferred** to the frontend lane.
The run spec's acceptance criterion is amended to say API-level provenance. Nothing claims
an on-screen label that this change does not ship.

**Step 3.2** — schemas in `backend/app/schemas.py` following the house style: inherit
`Strict` (:60-61), `StrictInt`/`StrictStr` only, dates as `StrictStr` + the shared `iso()`
validator (:47-57), cross-field checks on the later field.

**Step 3.3** — register the route in `create_app`, **between line 87 and line 89**. Lines
89-93 mount `StaticFiles` at `/` and the comment says why it must stay last. A route
registered after it is silently shadowed and `test_api.py:107-119` does not cover a fourth
route. Add a test that does.

**Step 3.4** — round-trip test (P2 #9): generate → `/api/candidates` → `/api/solve` with
`locks.in` drawn from the returned ids → expect 200.

**Step 3.4a — D-F, promoted out of the risk table** (Codex finding 5). Step 3.4 draws locks
from the *current* response, so it can never reproduce eviction. The real test:

1. get a **truncated** candidate list (`limit` at its default 18, on an account that
   produces more)
2. pin one candidate near the bottom of the returned set via `locks.in`
3. add a row to the schedule so that candidate falls below the cut
4. re-fetch candidates, re-solve with the same lock → **currently 422 on the whole solve**

Reproduced by the risk pass on window index 1 of `windows(300)` by adding one
`-$900 DOORDASH*CHIPOTLE` row, which evicted `t_005.defer`.

Then define the refresh policy this change commits to. The client rule already documented
at `docs/features/candidates.md` says prune `locks` to the returned ids on every
`/api/candidates` response; the new endpoint must document the same rule, and the test
above pins the failure that happens when a caller doesn't. `main.py` has no handler for
this beyond FastAPI's default 422 — decide whether that is good enough or whether it wants
a clearer message.

**Step 3.5** — guard the perf blow-up (D-G). The dead `continue` at
`test_candidates_roundtrip.py:208-209` cannot fire. Either assert the candidate-count
distribution of the product profile stays clear of `MAX_FREE`, or cap the profile's
discretionary row count. 34 of 300 accounts already sit at 2^18 subsets; do not add to that
population blind.

**Gate, and run the perf suite.** Perf must stay at 8 passed and must not grow materially
beyond its ~137 s baseline.

---

## Phase 4 — Nessie adapter (D3, D4, D5)

**Step 4.1** — `backend/app/nessie/client.py`, mirroring `chat/gemini.py` structurally:
module-level constants with a comment each (:23-34), a frozen `NessieConfig` with
`from_env()` read **at call time** (:65-78), a single `_post_json`/`_get_json` I/O funnel
converting every `urllib` failure into one `NessieError` carrying `status` (:97-114).
Reuse `load_dotenv_once()` from `gemini.py:36-55`; do **not** write a second loader. Note
its `parents[3]` is wrong on the box (D-A) — a module at `app/nessie/client.py` needs
`parents[3]`, at `app/nessie.py` `parents[2]`; compute it, do not copy the number.

**Step 4.2** — `backend/app/nessie/__init__.py` holds the orchestration and the exception
types that `main.py` maps to HTTP, exactly as `chat/__init__.py:17-22` does. The transport
exception never escapes the package.

**Step 4.3** — credential verification is **write-then-read** (D4): `POST /customers` then
`GET /customers/{id}`. Treat `200 []` as unverified and raise a configuration error (P2
#12, the most important test here). Treat the keyless `502` as a configuration error too,
not an upstream outage (P2 #13).

**Step 4.4** — money conversion (D5), **revised per Codex finding 7**. Decode with
`json.loads(body, parse_float=Decimal)` so no float is ever constructed. Measured on this
branch:

    json.loads('{"amount": 19.99}')['amount'] * 100  → 1998.9999999999998  → int() → 1998

One cent wrong, silently. Note Codex's *reasoning* was overstated — `Decimal(str(19.99))`
does give `1999.00`, because CPython's float repr round-trips — but its *recommendation* is
right: decode as `Decimal` and never construct the float at all, rather than rely on repr
behaviour holding for every value. Also required: reject non-finite values, bound the
magnitude against `CENTS_ABS`, and **raise** on a sub-cent input rather than round (P2 #15).

**Step 4.4a — the seed/read-back workflow** (Codex finding 3; unspecified before).

1. `POST /customers` → `_id` (verified: 201 with the created object, so no follow-up list
   call is needed)
2. `POST /customers/{id}/accounts` → account `_id`, with the opening balance
3. Income rows → `POST /accounts/{id}/deposits`; recurring bills → `POST /accounts/{id}/bills`
4. Discretionary rows have **no documented create path** (brief caution 3) — they are
   reported as not round-tripped, per Step 4.5, never silently dropped
5. Read back and normalise to `ScheduledTxn`, deriving stable ids from the Nessie `_id` so a
   re-fetch does not renumber and invalidate a client's locks (see D-F)

**Retry safety:** a write that times out ambiguously must not be retried blind — read back
by id first. Duplicated deposits double-count the opening balance, which is exactly the
class of error this product exists to prevent.

**Step 4.5** — the purchases gap. `docs/nessie-agent-brief.md` caution 3: no documented
create/list path for purchases, which is exactly the transaction history this product
consumes. The adapter reports what it could not round-trip; a silent drop fails the test
(P2 #16).

**Step 4.6** — failure falls back to the local generator **and** discloses it, the way the
offline-solver chip does (P2 #17). Never blank UI.

**Step 4.7** — never log the key. It rides in a query parameter (`?key=`), so no code may
log a full URL (P2 #18). Counterfactual test.

**Step 4.8** — the `nessie` marker, **revised per Codex finding 6**. Registering a marker
does **not** deselect it: the documented gate is `-m "not perf"`, which would happily
collect and run live Nessie tests. Either

- add `addopts = -m "not perf and not nessie"` to `backend/pytest.ini` so the default run
  excludes both and the gate command stays as documented, or
- change every gate invocation (`README.md:41`, `CLAUDE.md:92`, the run spec, this plan) to
  `-m "not perf and not nessie"`.

Prefer the first: one place to change, and no stale command left in a doc. Either way the
run spec's "deselect count unchanged" criterion is amended — adding deselected tests
changes that count by construction, so the criterion becomes *no test moves from selected
to deselected*.

**Gate.**

---

## Phase 5 — the deploy (D-A, D-D, D-E)

**Step 5.1 — D-A, the highest-value fix in this plan.** `main.py:32` must locate
`frontend/dist` correctly both on the laptop and on the box. Prefer an explicit environment
override (`OVERDRAFT_DIST`) with the current expression as the fallback, set by the systemd
unit; or resolve relative to `WorkingDirectory`. Add a test asserting the box layout
resolves — construct `/opt/overdraft-guard/app/main.py` and assert the computed dist is
`/opt/overdraft-guard/frontend/dist`. **Without this the site is a 404 and the health check
still passes.**

**Step 5.2 — D-D.** Add a prereq preflight to `deploy.sh` before the rsync block (:49-55)
that checks for `caddy` and `python3 -m venv` on the target and fails with the exact
`apt-get` line to run. Test by stubbing `command -v`.

**Step 5.3 — D-E.** Either refuse to deploy when `DOMAIN` is unset, or substitute `:80` so
the bare-IP smoke test genuinely works. Fix the false comment at `Caddyfile:4-7` either
way, and the same false claim in the handoff.

**Step 5.4** — key provisioning. `deploy/overdraft-guard.service:17`'s optional
`EnvironmentFile=-` is correct as designed; the gap is that nothing creates the file. Add a
preflight asserting `/etc/overdraft-guard.env` exists and is non-empty, refusing otherwise
(P2 #21).

**Step 5.5** — the import-declaration test (P2 #23): parse every `import` in `backend/app/`
and assert each third-party name appears in `requirements.txt`. This is the test that would
have caught the undeclared `pydantic`.

**Step 5.6** — health check honesty. `deploy.sh:80-86` polls `127.0.0.1:8000` over ssh,
bypassing Caddy, so it passes while the public URL serves nothing. Add a second check
against the public origin.

**Step 5.7 — actually deploy and verify the served application** (Codex finding 10; the
plan fixed the scripts and never ran them). The box already exists: `64.177.48.139`,
Ubuntu 24.04.5, Caddy 2.11.4 and `python3-venv` installed, `/etc/overdraft-guard.env`
present at 0600, `ortools` proven to install in 7.8 s.

Codex is right that a public `/health` still passes with the bundle missing — that is
exactly defect D-A. So verification must be:

1. `cd frontend && npm run lint && npm run build && npm test` **before** shipping, in that
   order (`bundle.test.ts` reads `dist/` unconditionally, so a test-first order validates
   stale output)
2. `./deploy.sh`
3. `GET /` on the public origin → **200 and HTML**, not just reachable
4. fetch a JS asset referenced by that HTML → 200 with a JavaScript content type
5. `POST /api/solve` against the public origin with a known scenario → correct tier
6. `GET /health` → `{"ok": true}`

Step 3 is the one that actually catches D-A. Steps 1 and 5 are the ones that catch a stale
or broken bundle.

Deploy over plain HTTP if the domain is not yet registered; re-run with `DOMAIN` set once
`dig +short <domain>` returns the box IP.

---

## Phase 6 — docs and commit

Edit exactly the files the run spec lists, or strike one with a one-line reason. Then:

- `README.md:25` — venv from `requirements-dev.txt`
- `README.md:29` — the `wheels/` offline line is already wrong; `wheels/` is gitignored and
  absent from a fresh clone. Fix or strike it.
- `CLAUDE.md:92` — the documented gate omits `-m "not perf"`, turning a 20 s check into
  minutes. Fix only if it counts as a new invariant; otherwise note it and leave it.
- `docs/api-contract.md` — append a `##` section after line 218, mirroring the
  `POST /api/candidates` section at :164-218.

Commit with a conventional prefix, explicit paths in `git add`, never `-A`, never a bare
directory. Include `deploy/vultr.sh` and the `.gitignore` edit already in the tree.

---

## Risks, ranked

| | Risk | Mitigation |
|---|---|---|
| 1 | Golden hash moves in Phase 1 | Hash pinned in Phase 0 *before* the move; revert rather than patch |
| 2 | Banned word ships in `detail` | Phase 2 runs before the product profile exists |
| 3 | Perf run grows unbounded | Step 3.5 constrains the profile's candidate distribution |
| 4 | Deploy green but serving 404 | Step 5.1, plus Step 5.6's public-origin check |
| 5 | Float→cents in the adapter | Step 4.4, decimal-string conversion, half-cent raises |
| 6 | Lock 422 on re-fetch (D-F) | Test at truncation, not at `limit=MAX_N` |
| 7 | Subprocess string literal missed | Step 1.5 runs that test explicitly |
| 8 | New route shadowed by the mount | Step 3.3 registers above line 89 and tests it |

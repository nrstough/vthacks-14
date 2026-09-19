# Handoff — finish the data/deploy lane (2026-09-19, Sat 18:15)

**Purpose of this chat:** Get `data-deploy` merged and the site actually reachable
by a judge. Sixteen commits of finished, audited work are sitting unmerged, and
the deployed box serves nothing from outside because of a firewall rule only
Nathan can change. Everything else is optional.

## Context

The generator, the Nessie adapter and the first-ever deploy are **done and
audited**. Four rounds of Codex audit; every code finding fixed. The two
dimensions still graded Fail are **accepted scope decisions**, written into
`docs/specs/2026-09-19_synthetic-accounts.md` under "Scope revision — accepted by
Nathan". Do not re-litigate them.

What shipped:

- `backend/app/accounts/` — the merchant table and `window()`/`windows()` moved
  out of `tests/fixtures/`, byte-identically, plus a separate product profile.
- `POST /api/accounts/sample` — a modelled account, seed echoed back so anything
  on screen regenerates from the response alone.
- `backend/app/nessie/` — transport, write-then-read credential check, decimal
  money path, key redaction. **Verified against the live sandbox, wired to no
  route.**
- `deploy.sh` — four real defects fixed, three of them found only by running it.
- The chat scrubber rebuilt so merchant names and the banned-word rule stop
  fighting.

## Working branch / worktree

`data-deploy` in `/Users/nathanstough/Desktop/vthacks-data` — **clean**, 16
commits ahead of `main`, `main` already merged in (`2e767c3`), so the merge out is
a fast-forward.

**Other sessions are live.** `git worktree list` at the time of writing:

```
/Users/nathanstough/Desktop/VT Hacks          [main]       2653df3
/Users/nathanstough/Desktop/vthacks-data      [data-deploy] ← this lane
/Users/nathanstough/Desktop/vthacks-security  [claude/security-readiness-krrpk9]  ← ACTIVE, someone else
/Users/nathanstough/Desktop/vthacks-solana    [wallet-ui]
/Users/nathanstough/Desktop/vthacks-frontend  [frontend]
/Users/nathanstough/Desktop/vthacks-gemini    [gemini-chat]
```

Per `CLAUDE.md`: `git branch --show-current` before anything branch-sensitive, and
**check with the security session before fast-forwarding `main`** — it rewrites
files under them.

## Environment / setup

```bash
cd /Users/nathanstough/Desktop/vthacks-data
```

```bash
.venv/bin/pytest backend/ -q -m "not perf"
```

```bash
cd frontend && export npm_config_cache="/Users/nathanstough/Desktop/VT Hacks/.npm-cache" && npm run lint && npm run build && npm test
```

The venv is symlinked from the main checkout, as are `node_modules` and
`.npm-cache` — worktrees do not carry gitignored directories.

Keys live in `<repo>/.env` (gitignored, 0600) and on the box at
`/etc/overdraft-guard.env` (root, 0600). Both hold Gemini and Nessie keys; `.env`
also has `VULTR_API_KEY`. **Worktrees do not share `.env`** — that is how the
Gemini key was lost for an afternoon. See `.env.example`, which now says so.

## What to do next

### 1. Unblock the site — one command, and it is Nathan's to run

```bash
ssh root@64.177.48.139 'ufw allow 80/tcp && ufw allow 443/tcp && ufw status'
```

Vultr's Ubuntu image ships `ufw` **active with only ssh allowed**. The deploy
completes, Caddy serves `:80` correctly, `/health` returns 200 — and the site is
reachable from nowhere but the box. Changing firewall rules is not something an
agent session should do; hand him the line.

### 2. Deploy and record the public checks

Then run it, and **append the results to the run spec**. This is the one audit
finding that is unfinished rather than accepted — the checks exist in `deploy.sh`
and have never passed:

```bash
cd /Users/nathanstough/Desktop/vthacks-data && ./deploy.sh root@64.177.48.139
```

It verifies, in order: public `GET /` returns HTML containing `<div id="root">`;
a JS asset the page references loads; `/api/accounts/sample` says
`source: "modelled"`; and `/api/solve` returns **tier 3** for the `gap` scenario
(`deploy/smoke-gap.json`). An internal `/health` does not satisfy acceptance —
that is exactly how the silent-404 bug hid.

### 3. Merge to main

After checking with the security session:

```bash
git switch main && git merge data-deploy --ff-only
```

### 4. The domain (15 min, its own MLH track)

Promo code from the **MLH organizers**, then [tech.study](https://tech.study) —
**not** `.tech`, which is not in the promo. Chosen name: **`safetospend.us`**.
Eligible TLDs are `.us`, `.club`, `.design`, `.biz`, `.wiki`, `.study` and a long
tail; `.com` is explicitly excluded.

Then an **A record** for `@` → `64.177.48.139`, TTL 600. Wait for
`dig +short safetospend.us` to return the IP **before** deploying with `DOMAIN`
set, or Caddy fails the ACME challenge and you debug a certificate when the
problem is DNS.

```bash
printf 'TARGET=root@64.177.48.139\nDOMAIN=safetospend.us\n' > .deploy.env && ./deploy.sh
```

### 5. Optional, explicitly out of scope — only if there is time

All named in the run spec, none of them started:

- Nessie **seed-and-read-back**: customer → account → deposits → bills → normalised
  fetch, plus `not_round_tripped` and a route. This is what the Capital One track
  is actually judged on, and the adapter underneath it is built and tested.
- **D-F**: a lock on a truncated candidate list 422s the whole solve after a
  re-fetch evicts it. Reproduced on window 1 of `windows(300)` by adding one
  `-$900 DOORDASH*CHIPOTLE` row. Needs a truncate → pin → add row → re-fetch test.
- **D-G**: `test_candidates_roundtrip.py:208-209` — `if len(generated) > MAX_FREE:
  continue` can never fire, because `limit` defaults to `MAX_FREE`. 34 of 300
  accounts sit at 2^18 subsets already.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

- **Test:** `.venv/bin/pytest backend/ -q -m "not perf"` → **2002 passed, 1
  skipped, 8 deselected**, ~23 s. **This is the gate.** The 1 skip is the live
  Nessie probe; opt in with `-m nessie`.
- **Test:** `.venv/bin/pytest backend/ -m perf -q -s` → **8 passed**, ~126 s, with
  all 300 accounts agreeing across both engines.
- **Test:** `cd frontend && npm run lint && npm run build && npm test` → lint
  clean, **209 passed**. Always **lint → build → test**: `bundle.test.ts` reads
  `dist/` unconditionally, so a test-first order validates stale output.
- **Golden hash:** `windows(300)` →
  `8d4ddf3092a22cb4de03d50d23fe558420b2ef7eb2cb1272f77948e543081048`, pinned in
  `backend/tests/test_accounts_golden.py`. **If this moves, the generator move
  changed behaviour — revert, do not re-pin.**
- **Canaries** (unmoved): `clears` → tier 1, 3 changes; `gap` → tier 3, 9 changes,
  `"$27.62 more by Sep 24"`; demo account → 14 candidates, `rows_considered` 13,
  `protected [t_card, t_verizon]`, `not_actionable [t_spotify]`.

- **At-risk: `.env`** — gitignored, holds Gemini + Nessie + Vultr keys. **NOT
  archived.** Worktrees do not share it.
- **At-risk: `frontend/dist/`** — gitignored, **NOT archived**. `deploy.sh` is the
  only thing that puts it on a server.
- **At-risk: `~/Downloads/Checking.csv`** — Nathan's real bank export. **NOT
  archived, must never be committed.** History scan confirms it never has been.
- **At-risk: the Vultr box itself** — `64.177.48.139`, ~$1.85/day against the $100
  credit. `overdraft-guard` and `caddy` both active. Destroy it after judging or
  it keeps billing.
- **In flight: nothing.** No background jobs, no cloud runs, no open PRs.
- **16 commits unpushed**, and the repo is **PRIVATE**.

## ⚠️ Before the 08:00 Sunday deadline

- **Make the repo public.** MLH requires it for prize eligibility and it must stay
  public afterwards. Every track is forfeited while it is private.
  `gh repo edit nrstough/vthacks-14 --visibility public --accept-visibility-change-consequences`
- **List the AI tools in the Devpost submission.** Using them is explicitly
  allowed; *not listing them* is the rule break.
- **Check the video length.** MLH's rules say 2 minutes for digital events;
  `docs/demo-script.md` is a four-minute script. Confirm which Devpost wants.

## Analytical notes

- **The scrubber took four attempts, and the lesson generalises.** Protected
  spans, an upper-case rule, then case-sensitive matching — each bypassable,
  because provenance cannot be recovered from a string after the fact: *"This plan
  IS GUARANTEED to clear"* is indistinguishable from a merchant called *"IS
  GUARANTEED"*. The answer was structural — mask the descriptor **fields** before
  rendering, scrub everything the model writes with no exceptions, restore after.
  Do not reintroduce an exemption.
- **A read can never confirm a Nessie key.** A wrong key returns `200 []`,
  identical to a valid key over an empty sandbox; a missing key returns a generic
  `502`. No 401, no 403. Credentials are checked write-then-read, and `200 []` is
  *unverified*, never *empty*.
- **`/health` cannot see a broken site.** It polls `127.0.0.1:8000` over ssh and
  never touches Caddy. That is how `main.py` looking for `/opt/frontend/dist`
  instead of `/opt/overdraft-guard/frontend/dist` stayed invisible: API up, health
  200, `deployed` printed, site a 404.
- **Three deploy defects were only findable by running it** — `rsync` not creating
  missing parents, `ufw` shipping active, and the public-origin check being the
  only thing able to see either. Reading the script found the fourth.
- **The dip test passed without testing.** Four seeds in 300 drew every charge on
  or after the first payday, so `opening` clamped to 0 and it asserted
  `0 < 2500` over an empty loop. Watch for this shape.
- **A dip is not a solvable dip.** ~7% of seeds reach tier 3 with an empty plan,
  which is wanted — naming an unclosable shortfall honestly is half the product.

## Pointers

- `CLAUDE.md` — working agreement. Binding. Read first.
- `docs/specs/2026-09-19_synthetic-accounts.md` — the run spec, including the
  accepted scope revision and the defect register (D-A … D-G).
- `docs/specs/2026-09-19_synthetic-accounts-audit.md` — the final Codex scorecard.
- `docs/features/accounts.md`, `docs/features/nessie.md` — living truth; both lead
  with what is *not* built.
- `docs/api-contract.md` — all four endpoints. The backend owns it.
- `deploy.sh`, `Caddyfile`, `deploy/overdraft-guard.service`, `deploy/vultr.sh`.
- Memory: `vthacks-api-key-locations`, `nessie-api-probe-findings`,
  `vthacks-14-event-constraints`, `vthacks-concurrent-session-collisions`.

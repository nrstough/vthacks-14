# Handoff — vthacks-decisions (2026-09-19, Sat ~12:05 AM)

**Purpose of this chat:** Decide the open questions from the kickoff chat and write the demo
script. Both partly done. **The next chat's job is to write code** — the synthetic generator
and the solver, in that order. Enforce the kill criteria and the gates.

## Read this first

It is **Saturday 00:05**. Code freeze is **Sun 01:30** (~25h), submission **Sun 08:00** (~32h).
**There is still no application code** — 6 commits, all documentation, plus one probe script.
`frontend/` is an untouched Vite scaffold, `backend/` has only `requirements.txt` and
`scripts/`. Nothing is deployed. The Claude allowance resets 2 AM Sunday, so **Saturday is the
entire agent window**. Treat further planning as a failure mode; the scope contract already
exists.

## Context

Nathan is competing solo at VTHacks 14 (Fri Sept 18 8 PM – Sun Sept 20 8 AM, 4-minute demo,
offline judging Sunday). First hackathon. He directs AI agents rather than hand-writing code
and will struggle with deep Python debugging, so prefer well-documented, copy-pasteable
patterns and ship a working fallback before the clever version.

The product: given a bank transaction history, return the **smallest dated set of spending
changes** that keeps the daily balance above zero until the next payday, with a proof of
minimality. Prescriptive, not a forecast. Research basis is the VeriLM three-model memo at
`~/Downloads/I am competing solo in a 36-hour hackathon... - VeriLM Memo.md` (364 KB, mostly
base64 images; strip `data:image` URIs before reading). It contains verified solver code
(brute force + pseudo-poly DP that agree), the formulation, stability measurements, and an
hour-by-hour build order.

### Decided this chat

- **`docs/demo-script.md` is the scope contract.** It carries the complete feature list (6
  items) and an explicit not-building list. Anything absent from it does not ship before the
  Sat 18:30 gate. When something feels essential at 3 AM, check it against that list first.
- **Real bank export (`~/Downloads/Checking.csv`): offline validation only.** Run it locally
  once against recurring-detection. Never committed, never in the demo, never on a projector.
- **Nessie architecture is forced** (see `docs/nessie-notes.md`): Nessie truncates every amount
  to whole dollars and never moves an account's `balance`. So the **local integer-cent ledger
  is the system of record**; Nessie is a seeded account/history source and a downstream mirror.
  Never read a balance back, never demo a live-updating Nessie balance. Seed **whole-dollar
  amounts** so the round trip is lossless and truncation never appears on stage.
- **Model spending as withdrawals**, not purchases — no merchant round trip, no `merchant_id`.
- **Dropped definitively:** GoDaddy ANS (no Python/JS SDK, ACME DNS-01 wall-clock dependency,
  needs an invented multi-agent story), Presage (camera vitals, no Python binding), Backboard
  (memory off by default, and contradicts the stateless pitch).
- **Nessie key obtained.** It is in `.env` (gitignored) on the cloud container. Nathan has it;
  it must also be in `.env` on his laptop. **Never commit it** — the repo flips public Sunday.

### Still open — ask Nathan first thing

1. **The three track slots are NOT decided.** Nathan asked for the full list of achievable
   tracks with prizes (delivered, in `docs/prize-strategy.md`) and did not pick. Deep research
   came back with **no surviving evidence** on Gemini, Gen AI, DigitalOcean, Vultr, TigerData,
   MongoDB, Solana, ElevenLabs, Best Domain Name, Peraton, or MLH judging rubrics — every claim
   was refuted. So this is a judgment call, not a researched one. Standing recommendation:
   **Capital One + DigitalOcean + Domain Name** (~2h, all on the critical path anyway); the
   alternative with the highest prize-value-per-slot is Capital One + Gemini + Gen AI (~3h, one
   integration entering two tracks).
2. **Optimizer vs estimator — still unanswered.** Nathan deferred it pending sponsors, and
   sponsors never got settled. Recommendation: ship greedy + an irredundancy check behind a
   `solve()` interface first (~45 min, always demoable), then slot CP-SAT in behind a
   wall-clock timeout that falls back. **The irredundancy certificate — the demo's punchline —
   does not require CP-SAT.** Only minimum cardinality does.
3. **DigitalOcean account + $200 credits.** Nathan creates it, links GitHub. Blocks the deploy
   gate, which is the only kill criterion with no fallback.
4. **Domain name.** Candidates: `overdraft.rip`, `abovezero.cash`, `fewestchanges.com`,
   `staysolvent.app`. Check which TLDs qualify for the GoDaddy Registry track and whether free
   codes are on-site.
5. **Discord:** do MLH tracks count toward the cap of three?
6. **Peraton's rubric is completely uncharacterized** and it is the one track whose criteria
   might favor a machine-checkable proof of minimality. Zero build cost. Worth five minutes at
   their table.
7. **The probe has not been run.** It needs Nathan's laptop — the cloud container's egress
   policy blocks `api.nessieisreal.com`.

## Working branch / worktree

`claude/review-response-options-xjy6dr`, 6 commits ahead of `main`, pushed, clean at
`7d039ad`. The branch name no longer describes the work.

**`main` has none of this.** Consider merging to `main` early in the next chat — a hackathon
repo that judges may read should not have its documentation stranded on a branch, and the
Sunday visibility flip is easier from one line of history.

Repo `https://github.com/nrstough/vthacks-14` (PRIVATE; flip to public before Sunday
submission with `gh repo edit nrstough/vthacks-14 --visibility public
--accept-visibility-change-consequences`).

## Environment / setup

```bash
cd "/Users/nathanstough/Desktop/VT Hacks"
source .venv/bin/activate            # Python 3.14; ortools 9.15, scipy, fastapi, uvicorn, rapidfuzz, pandas, pytest
# offline reinstall if needed (hotel wifi): .venv/bin/pip install --no-index --find-links wheels -r backend/requirements.txt
cd frontend && export npm_config_cache="/Users/nathanstough/Desktop/VT Hacks/.npm-cache" && npm install && npm run build
```

- `~/.npm` has root-owned files; always set `npm_config_cache` to the project-local
  `.npm-cache/` (gitignored). Permanent fix needs Nathan's password: `sudo chown -R 501:20 ~/.npm`.
- CP-SAT smoke test passed (`OPTIMAL` on a 3-item covering instance).
- Hard constraints: venue closed 11 PM Fri/Sat, hotel wifi after; **never install from the
  hotel** — build locally and rsync.

## What to do next

1. **Run the probe** (5 min, needs the laptop): `.venv/bin/python backend/scripts/nessie_probe.py`.
   It settles which of three hosts answers, whether a POST returns an id or forces
   list-and-match, whether cents survive, and whether writes move the balance. Commit the
   resulting `docs/nessie-shapes.json`.
2. **Freeze the `/solve` JSON shape** (10 min). It is the seam between frontend and backend;
   once frozen they stop blocking each other and can be handed to separate agents. The demo
   script names the fields: verdict sentence, tier, before/after daily balance series, change
   list, certificate string.
3. **Synthetic account generator** (~45 min, ~150 lines). Business-day-adjusted biweekly/weekly
   pay with ±1 day jitter, heavy-tailed amounts, messy merchant strings, one planted dip before
   the first payday. **Do this before the solver** — it unblocks solver tests, frontend
   fixtures, and the sample-account button the demo depends on, and it needs nothing external.
4. **Solver v1**: greedy + irredundancy check behind `solve(instance) -> Plan`. Integer cents.
   Covering constraints `sum_i c_it x_i + s_t >= D_t` per day. Three tiers (proven sufficient /
   best partial / needs $X by date Y).
5. **Deploy hello-world to DigitalOcean** as soon as the account exists. Redeploy after every
   block. This is the only failure mode with no fallback.
6. **Instance builder + its tests.** This is the real risk, not the solver — see Analytical
   notes.
7. **CP-SAT** behind a timeout, falling back to v1. Lexicographic objective (fee count, total
   shortfall, cardinality, pain, hysteresis, id tiebreak), `num_workers=1`, fixed seed,
   `max_time_in_seconds≈2`. DP fallback from the memo.
8. **Nessie seed script + client**, then **recurring detection** (1h HARD timebox, hard-code
   fixture streams if it blows), then **frontend three bands**.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

- Test: **none exist yet.** First tests to write: solver fixtures (greedy-fails, tier-2,
  tier-3), and off-by-one cases (inclusive prefix, day-0 double count, horizon end on payday
  eve, lead time, 28/30/31 month-end). Run with `.venv/bin/pytest backend/`.
- At-risk: the VeriLM memo (research basis; NOT in repo, NOT archived; copy the text-only
  version into `docs/` if it becomes load-bearing).
- At-risk: `~/Downloads/Checking.csv` (personal bank data; NOT archived; never commit).
- At-risk: `~/Downloads/IMG_2041–2055.HEIC` (sponsor slide photos; originals stay in Downloads).
- At-risk: `wheels/` (64 MB, gitignored, regenerable with `pip download` on venue wifi; needed
  for offline hotel installs).
- `.env` holds the Nessie key, gitignored, present on the cloud container and needed on the
  laptop. Never commit.
- In flight: nothing running. No background jobs, no cloud runs, no PRs.

## Analytical notes

- **The instance builder is the real risk, not the solver.** The memo hands over verified
  solver code and a locked formulation; the bugs live in the projection — inclusive prefix,
  day-0 double count, horizon ending on payday eve, lead time, month-end. Those produce
  *plausible wrong answers*, the worst failure for a demo whose pitch is the proof. Write those
  tests before that code.
- Memo measurements worth quoting: date-blind greedy is non-minimal in 55.8% of random
  instances; date-aware greedy only 2.3% — so the solver's value is the certificate and the
  tier-3 "needs $X by date" output, not better answers. Naive plan-flip rate under $1 balance
  jitter 21%, mitigated ($25 buffer, $5 deficit rounding, hysteresis) 1%.
- Always re-verify the final plan against the true zero-balance constraint. Say **"sufficient
  under the schedule shown," never "guaranteed."** One jitter case that breaks a guarantee
  takes the whole proof story down.
- Nessie traps beyond the two big ones: a **wrong key returns `200 []` on reads** and 401 only
  on writes, so validate the key with a write; **creates are permanent** (DELETE returns 403);
  there is **no unified transaction endpoint** (4-GET fan-out, `purchase_date` vs
  `transaction_date`); the **official Python SDK is abandoned** and not on PyPI — hand-roll
  httpx. No approval queue, so zero key-delay schedule risk.
- The research's own caveat: vendor domains were blocked by the session egress proxy, so the
  Nessie findings rest on converging first-hand probe logs from four unrelated teams (Sept
  2026), not official docs. **The probe run is still the confirmation.**
- Two automatic categories are underrated and free: **Best Ut Prosim** and **Best DEI**. They
  need only the demo's opening sentence to account for them. The free column holds a MacBook
  Pro, a PS5 and a MacBook Air — every opt-in track competes for hours against it.
- Explicitly negative value this weekend: auth, multi-account, mobile layout, dark mode, a
  general constraint editor, any database, category analytics, any LLM inside the feasibility
  decision.

## Schedule gates

- **Sat 18:30:** working deployed demo, or freeze all features and fix only.
- **Sun 01:30:** code freeze. **Sun 08:00:** submission. Flip the repo public before submitting.

## Pointers

- Repo docs: `docs/demo-script.md` (the contract), `docs/nessie-notes.md` (API truth),
  `docs/prize-strategy.md` (tracks + prizes), `backend/scripts/nessie_probe.py`.
- Memory (auto-loaded): `vthacks-14-event-constraints`, `vthacks-project-plan`,
  `user-nathan-profile` in `~/.claude/projects/-Users-nathanstough-Desktop-VT-Hacks/memory/`.
- Nessie: https://nessieisreal.com (key on profile), API base — three candidates, the probe
  picks: `prod-api.nessieisreal.com`, `api.nessieisreal.com`, `api.reimaginebanking.com`.

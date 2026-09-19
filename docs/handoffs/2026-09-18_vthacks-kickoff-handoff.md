# Handoff — vthacks-kickoff (2026-09-18, Fri ~8:15 PM)

**Purpose of this chat:** Start building the VTHacks 14 project. Planning is done; write the 4-minute demo script first, then the solver, then everything else. Enforce the schedule's kill criteria.

## Context
Nathan is competing solo at VTHacks 14 (Fri Sept 18 8 PM to Sun Sept 20 8 AM, 4-minute demo, offline judging Sunday). First hackathon. Nathan directs AI agents rather than hand-writing code and will struggle with deep Python debugging, so prefer well-documented, copy-pasteable patterns.

The product: given a bank transaction history, return the **smallest dated set of spending changes** that keeps the daily balance above zero until the next payday, with a proof of minimality. Prescriptive, not a forecast. Full research basis is a VeriLM three-model memo at `~/Downloads/I am competing solo in a 36-hour hackathon... - VeriLM Memo.md` (364 KB, mostly base64 images; strip `data:image` URIs before reading). It contains verified solver code (brute force + pseudo-poly DP that agree), the formulation, stability measurements, and an hour-by-hour build order.

**Decisions locked tonight**
- React (Vite + TS + Recharts) frontend, FastAPI backend serving the built frontend as static files, one process, one port.
- Capital One **Nessie** sandbox is the primary data source (seed a customer with synthetic deposits/purchases/bills, read back). Nessie is live over HTTPS only; plain HTTP times out. Docs at nessieisreal.com are a JS app, so confirm bill field names once a key exists.
- Stateless: no database, no accounts. Nessie key in `.env` server-side only. TigerData cut (3h, no product need).
- Sponsor slots (max 3): Capital One Best Use of Nessie (build for it), Peraton Best Mission Critical AI (no build), third slot open. MLH tracks ARE in play (Gemini, ElevenLabs, Solana, TigerData, Presage, Vultr, MongoDB, Best Domain Name); unknown whether they count toward the cap. Cheap fits: Best Domain Name (register one, needed for HTTPS anyway), Vultr (host there, ~0.5h), Gemini API (~1h, LLM at the edges only). If MLH counts toward the cap: Capital One + Vultr + Domain Name, drop Peraton. If separate: keep Peraton, tick Domain, Vultr, Gemini if built. VTHacks' own categories (First-Time, UI/UX, overall, etc.) are automatic; optimize hardest for Best First-Time Hack, then UI/UX. GoDaddy ANS only as a Saturday-afternoon stretch (cancellation agent) if the core is deployed and polished early. Side Kick track dropped.
- Security stance for judges: stateless by design, sandbox data only, HTTPS, key server-side; production would add Plaid, encryption at rest, per-user auth.

**Still open (ask Nathan first thing)**
1. Optimizer vs estimator. Recommendation given: optimizer (estimator is its built-in fallback). Nathan had not answered when this chat ended.
2. Nessie API key (Nathan must create it at nessieisreal.com; do not create accounts for him).
3. Whether Nathan's real bank export (`~/Downloads/Checking.csv`, 210 rows Jun–Sep 2026, weekly Harris Teeter payroll, real messy merchant strings, a few recurring charges) gets used for an anonymized validation view. It is personal data: never commit it, anonymize names/reference numbers before any demo use. `.gitignore` already excludes `Checking.csv` and `data/private/`.

## Working branch / worktree
`main` in `/Users/nathanstough/Desktop/VT Hacks`; clean, 1 commit (`64992e7`), pushed to `https://github.com/nrstough/vthacks-14` (PRIVATE; flip to public before Sunday submission with `gh repo edit nrstough/vthacks-14 --visibility public --accept-visibility-change-consequences`).

## Environment / setup
```bash
cd "/Users/nathanstough/Desktop/VT Hacks"
source .venv/bin/activate            # Python 3.14; ortools 9.15, scipy, fastapi, uvicorn, rapidfuzz, pandas, pytest installed
# offline reinstall if needed (hotel wifi): .venv/bin/pip install --no-index --find-links wheels -r backend/requirements.txt
cd frontend && export npm_config_cache="/Users/nathanstough/Desktop/VT Hacks/.npm-cache" && npm install && npm run build
```
- `~/.npm` has root-owned files; always set `npm_config_cache` to the project-local `.npm-cache/` (gitignored). Permanent fix needs Nathan's password: `sudo chown -R 501:20 ~/.npm`.
- CP-SAT smoke test passed (`OPTIMAL` on a 3-item covering instance).
- Hard constraints: venue closes 11 PM Fri/Sat (hotel wifi after; never install from the hotel, build locally and rsync). Claude allowance resets 2 AM Sunday, so Fri evening–Sat night is the scarce agent window.

## What to do next
1. Get the optimizer/estimator answer. Write the **4-minute demo script** before any code; it is the scope contract.
2. `backend/`: FastAPI app with `/health`, `/solve`. Solver module in integer cents: covering constraints `sum_i c_it x_i + s_t >= D_t` per day; lexicographic objective (fee count, total shortfall, cardinality, pain, hysteresis, id tiebreak); CP-SAT with `num_workers=1`, fixed seed, `max_time_in_seconds≈2`; DP fallback from the memo. Irredundancy certificate ("remove any one and you're $41 under on the 24th"). Three tiers (proven sufficient / best partial / needs $X by date Y). Unit tests with planted greedy-fails, tier-2, tier-3 fixtures.
3. Synthetic account generator (~150 lines): business-day-adjusted biweekly/weekly pay with ±1 day jitter, heavy-tailed amounts, messy merchant strings, one planted dip before the first payday.
4. Nessie seed script + client (HTTPS): create customer/account, push deposits, purchases, bills; read back into the solver's input. "Connect account" is the demo's first click; also keep a one-click sample account (judges will not upload files).
5. Recurring detection (regex normalize, rapidfuzz WRatio ≥ 88, 1% amount banding, cadence snap, ≥3 occurrences) with a manual override toggle. Timebox 1 hour; hard-code fixture streams if it fails.
6. Frontend: three bands (verdict sentence ~40 px; before/after balance chart, red fill only below zero, paydays as ticks, a step on the with-plan line at each change date; prescription list with lock toggles that re-solve). Tabular-nums, 8 px scale, one font, one accent.
7. Deploy early: Vultr VM + Caddy HTTPS on the registered domain (both are cheap MLH tracks). Redeploy after every major block. **Hard gate Sat 18:30: working deployed demo or freeze features.** Code freeze Sun 01:30. Submission by 08:00.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)
- Test: **none exist yet.** First tests to write: solver fixtures (greedy-fails, tier-2, tier-3), off-by-one cases (inclusive prefix, day-0 double count, horizon end on payday eve, lead time, 28/30/31 month-end). Run with `.venv/bin/pytest backend/`.
- At-risk: `~/Downloads/I am competing solo in a 36-hour hackathon... - VeriLM Memo.md` (research basis; NOT in repo, NOT archived; copy the text-only version into `docs/` if it becomes load-bearing).
- At-risk: `~/Downloads/Checking.csv` (personal bank data; NOT archived; must never be committed).
- At-risk: `~/Downloads/IMG_2041–2055.HEIC` (sponsor slide photos; JPEG conversions in the session scratchpad will be deleted; originals stay in Downloads).
- At-risk: `wheels/` (64 MB, gitignored, regenerable with `pip download` while on venue wifi; needed for offline hotel installs).
- In flight: nothing running. No background jobs, no cloud runs, no PRs.

## Analytical notes
- Memo measurements worth quoting: date-blind greedy is non-minimal in 55.8% of random instances; date-aware greedy only 2.3%, so the solver's value is the certificate and the tier-3 "needs $X by date" output, not better answers. Naive plan-flip rate under $1 balance jitter 21%, mitigated ($25 buffer, $5 deficit rounding, hysteresis) 1%.
- Always re-verify the final plan against the true zero-balance constraint; say "sufficient under the schedule shown", never "guaranteed".
- Nessie root and `/documentation` return 403 over HTTPS; `/accounts?key=...` returns 200. Expect bills to carry `recurring_date` / `upcoming_payment_date` / `payment_amount` (unconfirmed).
- Explicitly negative value this weekend: auth, multi-account, mobile layout, dark mode, a general constraint editor, any database.

## Pointers
- Memory (auto-loaded): `vthacks-14-event-constraints`, `vthacks-project-plan`, `user-nathan-profile` in `~/.claude/projects/-Users-nathanstough-Desktop-VT-Hacks/memory/`.
- Repo: `README.md`, `backend/requirements.txt`, `frontend/` (untouched Vite scaffold), `.gitignore`.
- Nessie: https://nessieisreal.com (key), API base `https://api.nessieisreal.com`.

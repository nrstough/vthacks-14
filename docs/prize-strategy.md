# VTHacks 14 — prize and track strategy

Last updated: Fri Sept 18, 2026, ~8:45 PM (after the opening ceremony).

## Rules as understood

- VTHacks' own categories (1st/2nd/3rd overall, Best First-Time Hack, Best UI/UX, Best Ut Prosim,
  Best DEI, Best Hack That Didn't Work, raffle) are judged automatically for every submission.
- Sponsor tracks: a submission may enter **at most three**.
- **Open question:** whether MLH tracks count toward that cap of three. See "Open decisions."

## Priorities

1. **Best First-Time Hack** (automatic). Weakest field; optimizing for it means a finished,
   deployed, polished demo, which is also what wins everything else.
2. **Best UI/UX** (automatic). One screen, one decision, one designer voice.
3. **Capital One: Best Use of Nessie** (sponsor slot). The only sponsor track that fits, and the
   integration improves the product.

Two automatic categories are underrated here and cost nothing to pursue: **Best Ut Prosim**
("that I may serve" — a tool for people living paycheck to paycheck is a genuine fit) and
**Best DEI** (financial inclusion). Both are judged automatically; neither needs a slot or an
extra hour. Frame the demo's opening sentence so it reads for them too.

The free column holds a MacBook Pro (1st), a PS5 (2nd), and a MacBook Air (raffle). Every opt-in
track competes for hours against that column, so no track is worth an hour it takes from
finishing, deploying, and polishing.

## Sponsor tracks presented at the ceremony

| Track | Ask | Fit | Decision |
|---|---|---|---|
| Capital One: Best Use of Nessie | "How will you reimagine banking?" Use the Nessie mock-bank API. $250 gift card per member. | Strong | **Enter. Build for it (~2h):** seed a Nessie customer with synthetic deposits/purchases/bills and read it back as the app's primary data source. |
| Peraton: Best Mission Critical AI Solution | Mission-critical AI. | Thin but honest ("an overdraft is mission-critical to the person it hits") | **Enter, no build.** Drop if MLH tracks count toward the cap. |
| GoDaddy: Best Use of ANS | Agents that discover, verify, and talk to other agents using ANS for domain-anchored identity. Workshops Fri 9:30 PM, Sat 4:30 PM. | Weak | **Skip for now.** Only plausible hook is a cancellation agent that negotiates with a merchant agent; 3–4h in an unknown SDK. Revisit Saturday afternoon only if the core is deployed and polished early. |
| Deloitte / Databricks | AI agent on Databricks to improve the VT student experience (career navigator, campus life hub, smart campus). Judged partly on team dynamics. | None | Skip. |
| Impiricus | New way to engage healthcare professionals; SMS off limits. Cash prizes $3,000 / $2,000 / $1,000. | None | Skip. Would require abandoning the project. |
| Procedura AI | Address to authoritative 3D building mesh on a map. | None | Skip. |
| nebulaONE "Side Kick" | Tiny zero-login AI mini-app beside the main hack. | Marginal | Skip (Nathan's call). |

## MLH tracks (listed on Devpost, not presented)

| Track | Cost | Decision |
|---|---|---|
| Best Domain Name from GoDaddy Registry | ~15 min: register a domain | **Enter.** Needed for HTTPS on a custom domain anyway. |
| Best Use of DigitalOcean | ~30 min: App Platform from the GitHub repo, managed HTTPS, $200 credits | **Enter.** Preferred over Vultr: git-push deploy, no VM, no reverse proxy to hand-configure. |
| Best Use of Vultr | ~1h: bare VM + Caddy | Skip. Same category as DigitalOcean; deploy to one host only. |
| Best Use of Gemini API + Best Use of Gen AI | ~1h, one integration | **Enter both, Saturday.** One Gemini call renders the solver's plan as a plain-English explanation. The LLM stays at the edges and never inside the feasibility decision. |
| Best Use of Tiger Data | ~3h | Skip unless well ahead Saturday. Their blurb names "financial prediction engines," but it's a database the stateless product doesn't need. |
| Best Use of Backboard | — | Skip. Its pitch is persistent AI memory; our security argument is that the app holds no state. |
| ElevenLabs, Solana, Presage, MongoDB Atlas | 2–4h each | Skip. |

## Rewards at a glance

### Automatic (every submission judged, no slot needed)

| Category | Reward |
|---|---|
| 1st Place | MacBook Pro 14-inch |
| 2nd Place | PlayStation 5 Digital |
| 3rd Place | Keyboard, mouse, monitor setup |
| Best First-Time Hack | AirPods 4 |
| Best UI/UX Hack | Kodak Polaroid camera |
| Best Ut Prosim Hack | North Face Borealis backpack |
| Best DEI Hack | LED Smart Fire TV |
| Best Hack That Didn't Work | Amazon Echo Spot |
| Raffle (2) | AirPods 4, MacBook Air 13-inch |

### Viable opt-in tracks

| Track | Reward | Extra build | Verdict |
|---|---|---|---|
| Capital One: Best Use of Nessie | $250 gift card per member | ~2h | Enter, build for it |
| Best Domain Name (GoDaddy Registry) | Digital gift card | ~15 min | Enter |
| Best Use of DigitalOcean | Retro wireless mouse | ~30 min | Enter, host here |
| Best Use of Gemini API | Google swag kit | ~1h (shared) | Enter if slots allow |
| Best Use of Gen AI | Assorted prizes | same integration | Enter if slots allow |
| Peraton: Best Mission Critical AI | Not shown on slide | 0 | Enter only if slots allow |

### Stretch only (Saturday afternoon, if ahead)

| Track | Reward | Extra build |
|---|---|---|
| GoDaddy: Best Use of ANS | 1st Meta Ray-Ban Gen 2 glasses; 2nd Beats Studio Pro; 3rd Cocopar 15.6" portable monitor | 3-4h (cancellation agent) |
| Best Use of Tiger Data | Stream Deck Mini | ~3h |
| Best Use of Vultr | Portable screens | ~1h, only instead of DigitalOcean |

### Not viable

| Track | Reward | Why not |
|---|---|---|
| Impiricus | $3,000 / $2,000 / $1,000 cash | HCP engagement; full pivot |
| Deloitte/Databricks | JBL speaker + merch | VT student-experience agent on Databricks |
| Procedura AI | Not shown | 3D building meshes on a map |
| ElevenLabs | Wireless earbuds | Voice; no product need |
| Solana | Ledger Nano S Plus | Blockchain; no product need |
| Presage | Fitbit Inspire + credits | Camera vital-sign sensing |
| MongoDB Atlas | M5Stack IoT kit | Database the product doesn't need |
| Backboard | Tile Essentials Pack | Persistent memory contradicts stateless design |

Under the three-slot assumption: Capital One, DigitalOcean, Domain Name. If the cap is sponsors-only, add Gemini, Gen AI, Peraton.

## Security stance for judges

Stateless by design: parse, detect, solve, render, forget. Sandbox (Nessie) data only, HTTPS in
transit, API key server-side in `.env`, nothing persisted. Production would add Plaid for bank
access, encryption at rest, and per-user auth. Hours went to the solver, not login pages.

Hard rule: never commit a key or a bank export. `.gitignore` covers `.env`, `Checking.csv`, `data/private/`.

## Schedule gates

- Deploy hello-world to DigitalOcean early Friday night, redeploy after every major block.
- **Sat 18:30:** working deployed demo, or freeze all features and fix only.
- **Sun 01:30:** code freeze. **Sun 08:00:** submission. Flip the repo to public before submitting.

## Decided

- **Real bank export (`~/Downloads/Checking.csv`): offline validation only.** Run it locally once
  to test recurring-detection against real messy merchant strings. Never committed, never in the
  demo, never on a projector. The demo uses Nessie and the synthetic generator only.

## Open decisions (as of this update)

1. **Three track slots.** Nine tracks are achievable (see "Rewards at a glance"); at most three may
   be entered. Cheapest viable slate is Capital One + DigitalOcean + Domain Name (~2h, all of it
   work already on the critical path). Highest prize-value-per-slot is Capital One + Gemini + Gen AI
   (~3h; one integration yields two entries). Deep research on what each track's judging actually
   rewards, and which are worth expanding product scope for, is in flight.
2. Confirm the three-track wording in Discord: do MLH tracks count toward the cap of three?
3. Optimizer or estimator. Recommendation: optimizer, but ship greedy + an irredundancy check
   behind a `solve()` interface first (~45 min, always demoable), then slot CP-SAT in behind a
   wall-clock timeout that falls back to it. Note the irredundancy certificate — the demo's
   punchline — does not require CP-SAT; only minimum cardinality does. Held pending track decisions.
4. Nessie API key (Nathan creates it at nessieisreal.com). Blocks ~2h of Capital One work.
5. DigitalOcean account + $200 credits (Nathan creates it, links GitHub). Blocks the deploy gate.
   Check the sponsor tables for a credit code before paying.
6. Domain name. Candidates: `overdraft.rip`, `abovezero.cash`, `fewestchanges.com`,
   `staysolvent.app`. Verify which TLDs qualify for the GoDaddy Registry track, and ask about
   free registration codes at the table.

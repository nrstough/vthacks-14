# VTHacks 14 — prize and track strategy

Last updated: Sat Sept 19, 2026, ~01:00. (First written Fri ~8:45 PM after the opening ceremony.)

> **Sat 01:00 corrections, verified against the raw Devpost page and mlh.com/events/vthacks-14/prizes:**
> VTHacks 14 has **no DigitalOcean, no Backboard, and no "Best Use of Gen AI" track**. Earlier rows
> saying otherwise came from MLH's generic season list. **Vultr is the only hosting track** (prize:
> portable screens; $100 credit, no card, via mlh.link/vultr-signup + the gift code from the ceremony
> or the MLH Coach). Decisions: host on **Vultr** (VM + Caddy, one-command `deploy.sh`); enter Capital
> One (build, Sat AM, 90-min timebox), Vultr + Domain Name (with first deploy), Peraton (tick only);
> Gemini only if deployed and ahead at Sat 14:00; TigerData most likely out; ANS out.

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
| ~~Best Use of DigitalOcean~~ | — | **Does not exist at VTHacks 14** (verified Sat 01:00). |
| Best Use of Vultr | ~1h: VM + Caddy HTTPS + `deploy.sh`; $100 credit, no card | **Enter. Host here.** The only hosting track. |
| Best Use of Gemini API | ~1h, one integration | **Sat 14:00 only if deployed and ahead.** One Gemini call renders the plan as a plain-English explanation; the LLM stays at the edges, never inside the feasibility decision. (No separate "Gen AI" track exists here.) |
| Best Use of Tiger Data | ~3h | Skip unless well ahead Saturday. Their blurb names "financial prediction engines," but it's a database the stateless product doesn't need. |
| ~~Best Use of Backboard~~ | — | **Does not exist at VTHacks 14** (verified Sat 01:00). |
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
| Best Use of Vultr | Portable screens | ~1h | Enter, host here |
| Best Use of Gemini API | MLH swag kit | ~1h | Sat 14:00 if ahead |
| Peraton: Best Mission Critical AI | Not shown on slide | 0 | Enter only if slots allow |

### Stretch only (Saturday afternoon, if ahead)

| Track | Reward | Extra build |
|---|---|---|
| GoDaddy: Best Use of ANS | 1st Meta Ray-Ban Gen 2 glasses; 2nd Beats Studio Pro; 3rd Cocopar 15.6" portable monitor | 3-4h (cancellation agent) |
| Best Use of Tiger Data | Stream Deck Mini | ~3h |

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
| Backboard | — | Not a track at this event |

Under the three-slot assumption (MLH counts): Capital One, Vultr, Domain Name. If the cap is sponsors-only: Capital One + Peraton, plus Vultr, Domain Name, and Gemini if built.

## Security stance for judges

Stateless by design: parse, detect, solve, render, forget. Sandbox (Nessie) data only, HTTPS in
transit, API key server-side in `.env`, nothing persisted. Production would add Plaid for bank
access, encryption at rest, and per-user auth. Hours went to the solver, not login pages.

Hard rule: never commit a key or a bank export. `.gitignore` covers `.env`, `Checking.csv`, `data/private/`.

## Schedule gates

- Deploy to the Vultr VM as soon as `/health` exists (Sat morning), redeploy after every major block via `deploy.sh`.
- **Sat 18:30:** working deployed demo, or freeze all features and fix only.
- **Sun 01:30:** code freeze. **Sun 08:00:** submission. Flip the repo to public before submitting.

## Open decisions (as of this update)

1. Confirm the three-track wording in Discord or at the organizer table Sat morning. Working assumption (MLH counts): Capital One, Vultr, Domain Name; drop Peraton. If sponsors-only: Capital One + Peraton, plus Vultr, Domain Name, Gemini if built.
2. ~~Optimizer or estimator~~ — **decided Sat 01:00: optimizer** (exact CP-SAT; see `docs/features/solver.md`).
3. Nessie API key (Nathan creates it at nessieisreal.com).
4. Vultr account + $100 MLH credit (Nathan signs up at mlh.link/vultr-signup; gift code from the ceremony or MLH Coach).
5. Use Nathan's real bank export for an anonymized validation view: yes / no.
6. Domain name.

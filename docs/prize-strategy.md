# VTHacks 14 — prize and track strategy

Last updated: Sat Sept 19, 2026, after the product expansion discussion. (First written Fri ~8:45 PM after the opening ceremony.)

**Current correction:** Nathan clarified **three VT tracks and unlimited MLH tracks**. MLH entries do not consume the three VT slots. Gemini's listed reward is **Google Swag Kits**. See [product direction](vthacks-product-and-training-plan.md) and [training results](vthacks-training-pilot.md); the neural pilot is complete, while Gemini integration remains proposed.

> **Sat 01:00 corrections, verified against the raw Devpost page and mlh.com/events/vthacks-14/prizes:**
> VTHacks 14 has **no DigitalOcean, no Backboard, and no "Best Use of Gen AI" track**. Earlier rows
> saying otherwise came from MLH's generic season list. **Vultr is the only hosting track** (prize:
> portable screens; $100 credit, no card, via mlh.link/vultr-signup + the gift code from the ceremony
> or the MLH Coach). Decisions: host on **Vultr** (VM + Caddy, one-command `deploy.sh`); enter Capital
> One (build, Sat AM, 90-min timebox), Vultr + Domain Name (with first deploy), Peraton (tick only);
> The earlier Gemini-after-14:00 gate is superseded by the proposed conversational purchase flow below; integration remains contingent on a working core. TigerData most likely out; ANS out.

## Rules as understood

- **Three VT tracks; unlimited MLH tracks**, per Nathan's clarification. The earlier shared-cap assumption is resolved.
- Automatic consideration of categories was an earlier working assumption, not independently verified here. [Devpost](https://vthacks-14.devpost.com/) says to select every prize category you want to enter; check applicable eligibility when submitting.
- No need to fill a third VT slot with an unrelated integration.

## Priorities

1. **Best First-Time Hack** (if eligible). Optimizing for it means a finished,
   deployed, polished demo, which is also what wins everything else.
2. **Best UI/UX** (select if eligible). One screen, one decision, one designer voice.
3. **Capital One: Best Use of Nessie** (sponsor slot). The only sponsor track that fits, and the
   integration improves the product.

## Sponsor tracks presented at the ceremony

| Track | Ask | Fit | Decision |
|---|---|---|---|
| Capital One: Best Use of Nessie | "How will you reimagine banking?" Use the Nessie mock-bank API. $250 gift card per member. | Strong | **Enter. Build for it (~2h):** seed a Nessie customer with synthetic deposits/purchases/bills and read it back as the app's primary data source. |
| Peraton: Best Mission Critical AI Solution | Mission-critical AI. | Honest: an overdraft is mission-critical to the person it hits, and the architecture matches the ask | **Enter. No build** — see "Why Peraton" below. |
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
| Best Use of Gemini API | Proposed purchase-flow block: ~3h including scenario integration | **Enter if built.** Parse natural-language purchase/preferences into validated inputs and explain calculated alternatives. The exact solver still determines feasibility. This replaces the earlier explanation-only idea. (No separate "Gen AI" track exists here.) |
| Best Use of Tiger Data | ~3h | Skip unless well ahead Saturday. Their blurb names "financial prediction engines," but it's a database the stateless product doesn't need. |
| ~~Best Use of Backboard~~ | — | **Does not exist at VTHacks 14** (verified Sat 01:00). |
| ElevenLabs, Solana, Presage, MongoDB Atlas | 2–4h each | Skip. |

## Rewards at a glance

### General categories (confirm selection and eligibility at submission)

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
| Best Use of Gemini API | Google Swag Kits | Part of proposed purchase flow | Enter if integrated; unlimited MLH allowance |
| Peraton: Best Mission Critical AI | Not shown on slide | None | Enter; the fit is the architecture, not a feature |

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

## Why Peraton

Written out because it needs to survive being asked, not just ticked.

Mission-critical is not about the size of the system. It is about what failure
costs the person relying on it, and a thirty-five dollar fee on a five dollar
shortfall is a mission failure for someone with no slack. Overdraft fees are
regressive; they land hardest on people with the least room to absorb them.

The architecture is the argument. The parts that must not be wrong are exact and
provable: an integer-cent CP-SAT model decides feasibility, minimality is proven
rather than asserted, and the plan is re-verified against a zero balance after
it is chosen, so the solver does not mark its own homework. Two independent
implementations are checked against each other on generated accounts. When no
plan clears, the product names the outside amount needed and the date, instead
of saying "infeasible" or showing a red number.

The language model sits at the edges, where a mistake is recoverable. It
explains a plan it cannot change, it never sees a merchant descriptor, and it is
told explicitly that the account is generated demo data. No number it writes can
reach the decision.

That is the claim: AI where it is safe, and proof where it is not.

## Devpost text, ready to paste

Assembled here so submission morning is copy-paste rather than composition.

```
Every banking app warns you that you are about to overdraft. None of them tell
you what to do about it. Overdraft Guard takes a transaction history and returns
the smallest set of dated spending changes that keeps the balance above zero
until payday — and proves nothing smaller works.

Underneath is an exact constraint solver (OR-Tools CP-SAT): integer cents, one
covering constraint per day, and a lexicographic objective so fewest changes
genuinely wins. Minimality is only claimed when proven; when no plan clears, it
names the outside cash needed and the date it is needed by, rather than calling
anything infeasible. Two independent implementations — the CP-SAT model and a
brute-force reference — are checked against each other on 300 generated
accounts, with zero disagreements.

Accounts can be generated locally or seeded into Capital One's Nessie sandbox
and read back over their API; the page always says which, and never presents
generated data as anyone's bank records. A Gemini explainer answers questions
about the plan in plain English but never decides feasibility. Stateless: no
account, no database, nothing stored.

AI tools used: Claude Code (Anthropic) and Codex (OpenAI) were used
substantially throughout — planning, implementation, code review and
documentation — under human direction and review.
```

Peraton one-liner, if the form wants a per-track note:

```
An overdraft fee is a mission failure for the person it lands on. The decisions
that must not be wrong are made by an exact solver and re-verified after the
fact; the language model only explains them. Proof where it matters, AI where it
is safe.
```

With the clarified cap: prioritize Capital One among VT tracks; assess Peraton on fit. Vultr, Domain Name, and Gemini are separate MLH entries and do not consume those slots. Gemini API use must actually be implemented; training our own network alone does not qualify. [Gemini reward source](https://vthacks-14.devpost.com/).

## Security stance for judges

Stateless by design: parse, detect, solve, render, forget. Sandbox (Nessie) data only, HTTPS in
transit with HSTS, a CSP whose `connect-src 'self'` means a script that got onto the page still
could not post a transaction list off the box, and no personal financial history persisted by the
proposed request flow. The API key is server-side, never in the bundle: in `.env` locally, and on
the box a root-owned `0600` file outside the repository and outside the deploy's file list. The
service runs on loopback behind Caddy under `NoNewPrivileges` and `ProtectSystem=strict`, and
the box serves no interactive API console (it stays on in local development).

The explainer is rate limited to twenty questions a minute per address, because it is the one
endpoint that spends the key; the limit holds a count per address, no content and no identity, and
it dies with the process. The wallet tab keeps its ledger in the browser: that is client state, it
never reaches the server, and it dies with the tab.

The isolated forecast experiment does persist synthetic data and model checkpoints locally.
Production would add Plaid for bank access, encryption at rest, and per-user auth — every one of
those arrives with the first row stored on a server, and nothing here stores one. Hours went to the
solver, not login pages.

Hard rule: never commit a key or a bank export. `.gitignore` covers `.env`, `Checking.csv`, `data/private/`.

## Schedule gates

- Deploy to the Vultr VM as soon as `/health` exists (Sat morning), redeploy after every major block via `deploy.sh`.
- **Sat 18:30:** working deployed demo, or freeze all features and fix only.
- **Sun 01:30:** code freeze. **Sun 08:00:** conservative submission target. Devpost currently shows 10:00 AM in its header but 8:00 AM in the requirements text; keep the earlier target until organizers clarify. Flip the repo to public before submitting.

## Open decisions (as of this update)

1. **Resolved by Nathan:** three VT tracks and unlimited MLH tracks. Check individual eligibility and category selection when submitting.
2. ~~Optimizer or estimator~~ — **decided Sat 01:00: optimizer** (exact CP-SAT; see `docs/features/solver.md`).
3. Nessie API key (Nathan creates it at nessieisreal.com).
4. Vultr account + $100 MLH credit (Nathan signs up at mlh.link/vultr-signup; gift code from the ceremony or MLH Coach).
5. Use Nathan's real bank export for an anonymized validation view: yes / no.
6. Domain name.

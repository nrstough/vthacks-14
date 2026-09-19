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

## Security stance for judges

Stateless by design: parse, detect, solve, render, forget. Sandbox (Nessie) data only, HTTPS in
transit, API key server-side in `.env`, nothing persisted. Production would add Plaid for bank
access, encryption at rest, and per-user auth. Hours went to the solver, not login pages.

Hard rule: never commit a key or a bank export. `.gitignore` covers `.env`, `Checking.csv`, `data/private/`.

## Schedule gates

- Deploy hello-world to DigitalOcean early Friday night, redeploy after every major block.
- **Sat 18:30:** working deployed demo, or freeze all features and fix only.
- **Sun 01:30:** code freeze. **Sun 08:00:** submission. Flip the repo to public before submitting.

## Open decisions (as of this update)

1. Confirm the three-track wording in Discord. Working assumption (yes, MLH counts): enter Capital One, DigitalOcean, Domain Name; drop Peraton. If sponsors-only: Capital One + Peraton, plus Domain Name, DigitalOcean, Gemini, Gen AI.
2. Optimizer (recommended; estimator is its built-in fallback) or estimator only.
3. Nessie API key (Nathan creates it at nessieisreal.com).
4. DigitalOcean account + $200 credits (Nathan creates it, links GitHub).
5. Use Nathan's real bank export for an anonymized validation view: yes / no.
6. Domain name.

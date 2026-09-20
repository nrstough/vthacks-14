# Handoff — the domain, TLS, and the key on the box (2026-09-19, Sat evening)

> **Superseded, 2026-09-19 evening — do not follow the domain steps below.**
>
> This handoff plans a domain that was never registered. Every `safetospend.us`
> in it is a **dead name**: `.us` does not permit WHOIS privacy, so the choice
> changed to **`safetospend.study`**, which is registered and live. An `A` record
> for `safetospend.us` does not resolve (NXDOMAIN), so following steps 2–4 as
> written fails the ACME challenge and looks like a certificate bug.
>
> The domain and TLS work described here is **done**. What actually happened, and
> the live configuration, is in
> [`2026-09-19_domain-live-handoff.md`](2026-09-19_domain-live-handoff.md).
>
> Also stale below: the "`__DOMAIN__` trap" note says a deploy with `DOMAIN`
> unset leaves the literal string in place. It later fell back to `:80` instead,
> silently taking the live site off HTTPS; `deploy.sh` now refuses to run without
> `DOMAIN`. See `.deploy.env.example`.
>
> The rest — the worktree recipe, the key-on-the-box steps, the CSP and rsync
> notes, the public-repo deadline — is unaffected. Test counts are from Sat
> evening and have moved since.

**Purpose of this chat:** get `safetospend.us` registered, pointed at the live Vultr box,
and serving the app over HTTPS with a Caddy certificate — then install `GEMINI_API_KEY` on
the box so `/api/chat` stops answering 503 there. Nathan does the purchase and the key paste;
you do everything either side of them.

## Context

The product is **Safe to Spend** (renamed this evening from "Overdraft Guard"; see the
parallel lane below). The domain `safetospend.us` is **not yet registered** — it is to be
registered at **tech.study** using the MLH promo code Nathan collects in person from the
organizers. `.tech` is **not** in that promo; it is the `.us` that is covered.

The Vultr box exists and is serving. `/api/chat` is dead on it because the box's
`GEMINI_API_KEY` is empty.

Registering the domain also enters **Best Domain Name from GoDaddy Registry** (an MLH track,
separate from the three-sponsor cap), and HTTPS on a real domain is what makes the **Vultr**
track's deploy presentable rather than an IP over plain HTTP.

## Working branch / worktree

**Take your own worktree — do not use `/Users/nathanstough/Desktop/VT Hacks`.** That checkout
is currently on `ui-system` and held by a live session. Two other lanes are in flight (see
"In flight" below).

```bash
cd "/Users/nathanstough/Desktop/VT Hacks"
git worktree add /Users/nathanstough/Desktop/vthacks-domain -b domain-tls main
ln -s "/Users/nathanstough/Desktop/VT Hacks/.venv" /Users/nathanstough/Desktop/vthacks-domain/.venv
ln -s "/Users/nathanstough/Desktop/VT Hacks/frontend/node_modules" /Users/nathanstough/Desktop/vthacks-domain/frontend/node_modules
```

`.venv` and `node_modules` are gitignored and will not come with the worktree. Symlink them —
reinstalling on venue wifi is not an option.

## Environment / setup

`deploy.sh` reads `TARGET` and `DOMAIN` from `.deploy.env` at the repo root, or takes the
target as `$1`.

```bash
# .deploy.env  (gitignored; create it, it does not exist yet — see notes)
TARGET=root@<box-ip>
DOMAIN=safetospend.us
```

```bash
./deploy.sh                    # reads .deploy.env
./deploy.sh root@<box-ip>      # or pass the target directly
```

## What to do next

1. **Nathan registers the domain.** `safetospend.us` at **tech.study**, MLH promo code.
   He does this himself — it is an account and a payment. Ask him for the registrar login
   only if he wants you walking him through DNS; do not ask for card details ever.

2. **Point DNS at the box** — an `A` record for the apex `safetospend.us` → the box's IPv4,
   and an `A` for `www` if you want it. **Do this before anything that needs TLS.**
   Certificate issuance waits on propagation, and a Caddy that fails issuance backs off,
   so a premature restart costs you minutes you will want later. Verify with
   `dig +short safetospend.us` until it returns the box IP.

3. **Write `.deploy.env`** with `TARGET` and `DOMAIN` (see above), then redeploy:
   `./deploy.sh`. The script rsyncs a fresh `Caddyfile` to `/etc/caddy/Caddyfile` on every
   run and substitutes `__DOMAIN__` **only when `DOMAIN` is non-empty** — so `DOMAIN` must be
   set on every deploy from now on, not just this one. See the gotcha below.

4. **Confirm HTTPS end to end.** `curl -fsS https://safetospend.us/health` should return
   `{"ok":true}`, and the app should load at `https://safetospend.us/` with no mixed-content
   or CSP errors in the console.

5. **Install the Gemini key on the box.** Nathan pastes it; you place it.
   `/etc/overdraft-guard.env` is root-owned `0600` and deliberately outside the rsync list,
   so a deploy never overwrites or exports it:

   ```bash
   ssh root@<box-ip> 'install -m 600 /dev/null /etc/overdraft-guard.env && cat > /etc/overdraft-guard.env'
   # paste: GEMINI_API_KEY=...
   ssh root@<box-ip> 'systemctl restart overdraft-guard'
   ```

   Then check `curl -fsS https://safetospend.us/api/chat/status`. **Do not accept the key in
   chat and do not write it into any file in the repo** — `.env` is gitignored but the repo
   is about to go public and the habit is the risk, not the gitignore.

6. **Flip the repo public.** See the deadline below.

## IMPORTANT — tests & at-risk artifacts (make sure these survive)

- **Backend gate:** `.venv/bin/pytest backend/ -q -m "not perf"` → expected **1263 passed,
  8 deselected** (verified Sat evening on `rename-safe-to-spend`).
- **Frontend gate:** `cd frontend && npm run lint && npm run build && npm test` → expected
  **209 pass, 0 fail**; lint clean. `npm test` reads `dist/`, so build before you test.
- **At-risk: `.deploy.env` does not exist in any worktree.** I scanned all six. The box's
  address is recorded **nowhere on disk** — it lives in another session's context, in the
  Vultr dashboard, or in Nathan's head. Get it, write `.deploy.env`, and say the IP out loud
  in your first message so it survives this chat too.
- **At-risk: `/etc/overdraft-guard.env` on the box** — NOT archived, NOT in the repo, and not
  recoverable from anywhere here. If the box is rebuilt, the key must be pasted again.
- **At-risk: local `.env`** — gitignored, holds `GEMINI_API_KEY` for local dev. Never leaves
  the laptop; `deploy.sh` rsyncs explicit paths precisely so it cannot.

## Analytical notes

**The `__DOMAIN__` trap.** `Caddyfile` in the repo has `__DOMAIN__` as its site address.
`deploy.sh` rsyncs it fresh every run and only rewrites it if `DOMAIN` is set. So a deploy
with `DOMAIN` unset leaves the box with a site block addressed to the literal string
`__DOMAIN__` — Caddy will not serve your site on the IP, it will try to serve a host called
`__DOMAIN__`. The header comment claims it falls back to "the box's IP over plain HTTP";
treat that as aspirational. Always export `DOMAIN`.

**Why the box looks healthy while chat is dead.** The unit has
`EnvironmentFile=-/etc/overdraft-guard.env`. The leading `-` makes the file optional, so a
missing or empty key file does **not** fail the service — `systemctl status` is green,
`/health` returns ok, and only `/api/chat` 503s. Do not read a healthy unit as a working
explainer; check `/api/chat/status` specifically.

**CSP is `connect-src 'self'`** and that is deliberate for this product — the page loads
nothing from anywhere else. It would block a Solana Devnet RPC if that lane ever went live,
but that lane is not in the demo. Leave it alone.

**Deploy ships explicit paths, never the tree.** `.env`, `wheels/`, `.venv/` and any bank
export must never leave the laptop, and the rsync list is what enforces that. If you add a
file the box needs, add it to the list by name — do not widen the rsync.

## In flight — other lanes, do not cross them

- **`ui-system`** holds the main checkout at `/Users/nathanstough/Desktop/VT Hacks` and is
  actively rewriting the frontend shell (`Sidebar.tsx` → `TopNav.tsx`, `KpiRow` → `Stats`).
  Do not switch that checkout's branch and do not edit `frontend/src/components/`.
- **`rename-safe-to-spend`** (worktree `/Users/nathanstough/Desktop/vthacks-rename`, commit
  `25f13a9`) renamed the product in four files: `backend/app/main.py`,
  `backend/app/chat/prompt.py`, `frontend/index.html`, `frontend/src/App.tsx`. **Do not edit
  those four.** Infrastructure names were left alone on purpose — the systemd unit is still
  `overdraft-guard.service` and `APP_DIR` is still `/opt/overdraft-guard`. That is not an
  oversight and renaming them now buys nothing a judge sees.
- Expect a one-line merge conflict on `frontend/src/App.tsx:172` (the wordmark) when
  `ui-system` and `rename-safe-to-spend` both land. Keep "Safe to Spend".

## Hard deadline

**The repo must be public before 08:00 Sunday or every prize track is forfeited.**
It is `nrstough/vthacks-14`, currently **private**. It has been scanned and is safe to
publish: no secret in any commit (the live `.env` values were tested against every blob in
history), no server IPs, no real account data, fixtures synthetic.

```bash
gh repo edit nrstough/vthacks-14 --visibility public --accept-visibility-change-consequences
```

One caveat to raise with Nathan before or just after flipping: `origin/claude/security-readiness-krrpk9`
carries a handoff that documents an unmitigated rate-limit gap on `/api/chat`. A later branch
appears to have fixed it (`12fb82b feat(chat): rate limit the explainer`); confirm that fix is
on `main` before the site is public, or the doc is a live map to an open endpoint.

## Pointers

- `docs/handoffs/2026-09-19_data-nessie-deploy-handoff.md` — the deploy's original design notes
- `deploy.sh`, `Caddyfile`, `deploy/overdraft-guard.service` — the three files that matter here
- `docs/prize-strategy.md` — track decisions (note: its "three VT tracks" reading is wrong;
  the VTHacks form caps *sponsor challenges* at three and lets you pick any number of VT prizes)
- Memory: `vthacks-api-key-locations`, `vthacks-concurrent-session-collisions`

# Safe to Spend domain and HTTPS live

Live URL: https://safetospend.study/

## Registration and DNS

- Nathan completed registration through the MLH GoDaddy Registry offer, fulfilled by Porkbun. The first year was $0; the cart estimated renewal at $31.41/year. Checkout terms enroll the domain in automatic renewal. Auto-renew was not changed in this task.
- Changed from the proposed safetospend.us because .us does not permit WHOIS privacy. Porkbun explicitly showed "Use Privacy Service" selected for safetospend.study and confirmed registrant data is protected.
- Replaced Porkbun's root parking ALIAS with A safetospend.study -> 64.177.48.139, TTL 600. Removed the default wildcard parking CNAME. Final DNS drawer showed exactly one record. Nameservers were left unchanged; no www record or forwarding was added.
- Laptop DNS initially cached NXDOMAIN. Cloudflare and Google resolved correctly first; by final verification both default `dig +short safetospend.study A` and `dig +short @1.1.1.1 safetospend.study A` returned 64.177.48.139.

## Deployment and concurrent work

- Updated gitignored .deploy.env in both /Users/nathanstough/Desktop/vthacks-integrate and /Users/nathanstough/Documents/Codex/worktrees/vthacks-domain-live:

```text
TARGET=root@64.177.48.139
DOMAIN=safetospend.study
```

- The shared integrate checkout had moved to chat-output-budget at 9027677, while main remained at 21bd4fe. The live chat file matched that newer fix. Nathan explicitly approved a Caddy-only change to preserve it rather than redeploying old main.
- Changed only the active site address in /etc/caddy/Caddyfile from :80 to safetospend.study. Saved the previous config at /etc/caddy/Caddyfile.before-domain-live, validated successfully, and reloaded Caddy. Did not redeploy or restart the application, change CSP, or read/copy /etc/overdraft-guard.env.
- Caddy obtained a Let's Encrypt certificate successfully. Both services are active; ufw permits 80/tcp and 443/tcp for IPv4 and IPv6.
- Live app/chat/gemini.py SHA-256 before and after: 83405add6d177c7e834691ef6ad20919da33dc35b082c4ceef151e7b8a22e1ad.
- Created isolated worktree /Users/nathanstough/Documents/Codex/worktrees/vthacks-domain-live on branch domain-live from main for this note. Did not switch other worktrees, merge, or push.

## Final public checks

Normal public HTTPS requests passed without certificate bypasses or DNS overrides:

```text
HTML root and JavaScript asset: PASS /assets/index-BGfPjIAC.js
/health: {"ok":true}
/api/chat/status: {"configured":true,"model":"gemini-3.8-flash"}
/api/accounts/sample source: modelled
/api/solve with deploy/smoke-gap.json: tier 3
HTTP/2 200
content-security-policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'
strict-transport-security: max-age=31536000
HTTP redirect: 308 https://safetospend.study/
/api/docs: 404
```

Opened the HTTPS app in the browser, selected the $200.00 preset, then Capital One sandbox. The provenance heading showed a Capital One sandbox account with 25 rows and Sep 19 to Oct 18 dates; the exact solver completed. Browser warning/error log was empty. No Gemini chat request was needed for this domain check.

## Future deploys

Every deploying checkout must supply DOMAIN=safetospend.study. The two .deploy.env files above are gitignored and do not propagate with commits; a deploy from another checkout without DOMAIN would revert Caddy to HTTP. Preserve the newer live chat fix when selecting the next application deployment revision. This task intentionally did not run the full deploy script; its public HTML, JS, sample-account and tier-3 solver assertions were run separately against the live HTTPS origin.

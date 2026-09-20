#!/usr/bin/env bash
#
# One command, laptop to box. Build here, ship the artifacts, restart there.
#
#   ./deploy.sh root@203.0.113.10
#   ./deploy.sh                      # reads TARGET and DOMAIN from .deploy.env
#   ./deploy.sh --no-domain          # deliberate plain HTTP on the box's IP
#
# The frontend is built on THIS machine on purpose: the box has no node, and
# putting a toolchain on it to build a 600 kB bundle during a hackathon is time
# spent on the wrong thing. `frontend/dist/` is gitignored, so this script is
# the only thing that puts it on the server.
#
# `wheels/` is NOT used here. Every wheel in it is macosx_11_0_arm64, built for
# this laptop; the box installs from PyPI instead and needs working network.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ -f .deploy.env ]]; then
  # shellcheck disable=SC1091
  source .deploy.env
fi

# `--no-domain` is the only way to ask for plain HTTP, and it has to be asked for
# out loud. See the guard below for what it costs.
NO_DOMAIN=""
positional=()
for arg in "$@"; do
  case "$arg" in
    --no-domain) NO_DOMAIN=1 ;;
    -*)
      echo "unknown option: $arg" >&2
      echo "usage: ./deploy.sh [user@host] [--no-domain]" >&2
      exit 2
      ;;
    *) positional=("${positional[@]+"${positional[@]}"}" "$arg") ;;
  esac
done
set -- "${positional[@]+"${positional[@]}"}"

TARGET="${1:-${TARGET:-}}"
if [[ -z "$TARGET" ]]; then
  echo "usage: ./deploy.sh user@host   (or set TARGET in .deploy.env)" >&2
  exit 2
fi

APP_DIR="${APP_DIR:-/opt/overdraft-guard}"
DOMAIN="${DOMAIN:-}"
if [[ -n "$NO_DOMAIN" ]]; then
  DOMAIN=":80"
fi

# The site-down guard, and the reason it is this early: it costs nothing and it
# runs before the build, the rsync and the first ssh.
#
# Every run rsyncs the repo's Caddyfile over /etc/caddy/Caddyfile, and that
# file's site address is whatever DOMAIN says. Empty DOMAIN used to mean a silent
# fallback to `:80` — so a deploy from a checkout with no .deploy.env rewrote the
# live site to plain HTTP, printed "deployed", and exited 0. The smoke checks
# below derive their origin from DOMAIN too, so they passed against the box's IP
# and never noticed that HTTPS was gone.
#
# .deploy.env is gitignored. It exists in the checkout it was typed into and in
# no other, and there are a dozen-odd worktrees here, so "a checkout without it"
# is the common case rather than the exotic one.
if [[ -z "$DOMAIN" ]]; then
  echo "DOMAIN is not set — refusing, because this deploy would take the site off HTTPS." >&2
  echo >&2
  echo "every run rewrites /etc/caddy/Caddyfile from the repo's Caddyfile, and the" >&2
  echo "site address in it comes from DOMAIN. with DOMAIN empty there is no domain" >&2
  echo "and no certificate, and nothing else in this script would have failed." >&2
  echo >&2
  echo ".deploy.env is gitignored, so it does not travel between checkouts and a" >&2
  echo "fresh worktree has none. write one here:" >&2
  echo >&2
  echo "  printf 'TARGET=root@<box-ip>\\nDOMAIN=safetospend.study\\n' \\" >&2
  echo "      > '$PWD/.deploy.env'" >&2
  echo >&2
  echo "see .deploy.env.example for both variables. if you genuinely want plain" >&2
  echo "HTTP on the box's IP — a bare-IP smoke test, never a judge — ask for it:" >&2
  echo >&2
  echo "  ./deploy.sh --no-domain" >&2
  exit 1
fi

# DOMAIN is written into a config file through a sed whose delimiter is `|`.
case "$DOMAIN" in
  *[[:space:]]*|*"|"*|*__DOMAIN__*)
    echo "DOMAIN is not a usable Caddy site address: '$DOMAIN'" >&2
    exit 1
    ;;
esac

if [[ "$DOMAIN" == ":80" ]]; then
  echo "WARNING: --no-domain. the box will answer on http:// only, with no" >&2
  echo "         certificate. if it is currently on https, it stops being." >&2
fi

say() { printf '\n=== %s\n' "$1"; }

say "building the frontend"
npm --prefix frontend run build

# Refuse rather than ship a stale or empty bundle. A deploy that silently
# serves yesterday's dist is the kind of thing that is only noticed on stage.
if [[ ! -f frontend/dist/index.html ]]; then
  echo "frontend/dist/index.html is missing after the build — refusing to deploy" >&2
  exit 1
fi

# Preflight. Every check below was a real failure on a fresh Ubuntu 24.04 box,
# and under `set -e` each one kills the run partway through, leaving the service
# in whatever half-state it had reached. Refuse before anything is shipped.
say "checking the target"
ssh "$TARGET" 'bash -s' <<'PREFLIGHT'
  missing=""
  command -v caddy >/dev/null 2>&1 || missing="$missing caddy"
  python3 -c 'import venv, ensurepip' >/dev/null 2>&1 || missing="$missing python3-venv"

  if [ -n "$missing" ]; then
    echo "the box is missing:$missing" >&2
    echo "this script installs neither, and without caddy the rsync into" >&2
    echo "/etc/caddy/ fails before anything else runs. install once:" >&2
    echo "  apt-get update && apt-get install -y python3-venv python3-pip \\" >&2
    echo "      debian-keyring debian-archive-keyring apt-transport-https curl" >&2
    echo "  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key \\" >&2
    echo "      | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg" >&2
    echo "  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \\" >&2
    echo "      > /etc/apt/sources.list.d/caddy-stable.list" >&2
    echo "  apt-get update && apt-get install -y caddy" >&2
    exit 1
  fi

  # Vultr's Ubuntu image ships with ufw ACTIVE and only ssh allowed, so a
  # deploy succeeds end to end, Caddy serves :80 perfectly, and the site is
  # unreachable from anywhere but the box itself. Everything looks healthy.
  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'; then
    if ! ufw status | grep -qE '^80(/tcp)?[[:space:]]+ALLOW'; then
      echo "ufw is active and port 80 is not allowed." >&2
      echo "the deploy would finish cleanly and the site would be unreachable." >&2
      echo "  ufw allow 80/tcp && ufw allow 443/tcp" >&2
      exit 1
    fi
  fi

  # EnvironmentFile=- makes this file OPTIONAL, so a box without it starts
  # perfectly happily with no keys and the explainer is simply dead, with
  # nothing anywhere saying why.
  if [ ! -s /etc/overdraft-guard.env ]; then
    echo "/etc/overdraft-guard.env is missing or empty." >&2
    echo "the unit treats it as optional, so deploying now would hand you a box" >&2
    echo "with no API keys and no error. create it once:" >&2
    echo "  install -m600 /dev/null /etc/overdraft-guard.env" >&2
    echo "  # then add GEMINI_API_KEY= and NESSIE_API_KEY=" >&2
    exit 1
  fi
PREFLIGHT

say "shipping to $TARGET:$APP_DIR"
# Both levels: rsync creates the final directory of a destination but not its
# missing parents, so shipping frontend/dist/ into a box that has no
# $APP_DIR/frontend fails with "mkdir ... No such file or directory" — after the
# frontend has already been built, which makes it look like a build problem.
ssh "$TARGET" "mkdir -p '$APP_DIR' '$APP_DIR/frontend'"

# Explicit paths, never the whole tree: .env, wheels/, .venv/ and the bank
# export must never leave this laptop.
rsync -az --delete backend/app/          "$TARGET:$APP_DIR/app/"
rsync -az --delete frontend/dist/        "$TARGET:$APP_DIR/frontend/dist/"
rsync -az backend/requirements.txt       "$TARGET:$APP_DIR/requirements.txt"
rsync -az deploy/overdraft-guard.service "$TARGET:/etc/systemd/system/overdraft-guard.service"

# Substituted HERE rather than on the box, so the box never holds a
# half-configured Caddyfile. If any later step fails — pip, systemd, the network
# — what is already sitting in /etc/caddy is a complete config rather than a
# template, and the next `systemctl reload caddy` from any source does something
# sane. Left literal, Caddy reads `__DOMAIN__` as a hostname matcher and serves
# nothing; that window used to stay open for the whole remote block below.
rendered_caddyfile="$(mktemp "${TMPDIR:-/tmp}/Caddyfile.XXXXXX")"
trap 'rm -f "$rendered_caddyfile"' EXIT
sed "s|__DOMAIN__|$DOMAIN|g" Caddyfile > "$rendered_caddyfile"
if grep -q '__DOMAIN__' "$rendered_caddyfile"; then
  echo "__DOMAIN__ survived substitution — refusing to ship it" >&2
  exit 1
fi
# mktemp makes it 0600; the package ships /etc/caddy/Caddyfile world-readable and
# caddy does not run as root. Match what was there rather than locking it out.
chmod 644 "$rendered_caddyfile"
rsync -az "$rendered_caddyfile"          "$TARGET:/etc/caddy/Caddyfile"

say "installing dependencies and restarting"
ssh "$TARGET" APP_DIR="$APP_DIR" 'bash -euo pipefail -s' <<'REMOTE'
  cd "$APP_DIR"

  if [[ ! -d .venv ]]; then
    python3 -m venv .venv
  fi
  ./.venv/bin/pip install --quiet --upgrade pip
  # ortools is the one that can fail: it needs a wheel for the box's exact
  # Python. If this errors, read the version it names before changing anything.
  ./.venv/bin/pip install --quiet -r requirements.txt

  # No __DOMAIN__ substitution here on purpose: the Caddyfile that landed above
  # arrived already rendered, and deploy.sh refuses to run at all without a
  # DOMAIN. Do not reintroduce a fallback that rewrites this file to `:80` — that
  # is a site-down bug, not a default.

  # Tell the service where the bundle is rather than letting it infer. The
  # inference keys off the parent directory being named "backend", which holds in
  # a checkout but not here: APP_DIR is a setting, and a box deployed to
  # /opt/backend would resolve one level too high and serve a silent 404.
  if ! grep -q '^OVERDRAFT_DIST=' /etc/overdraft-guard.env 2>/dev/null; then
    printf 'OVERDRAFT_DIST=%s/frontend/dist\n' "$APP_DIR" >> /etc/overdraft-guard.env
  else
    sed -i "s|^OVERDRAFT_DIST=.*|OVERDRAFT_DIST=$APP_DIR/frontend/dist|" /etc/overdraft-guard.env
  fi

  systemctl daemon-reload
  systemctl enable --now overdraft-guard
  systemctl restart overdraft-guard
  systemctl reload caddy 2>/dev/null || systemctl restart caddy
REMOTE

say "checking health"
healthy=""
for _ in $(seq 1 10); do
  if ssh "$TARGET" 'curl -fsS http://127.0.0.1:8000/health' 2>/dev/null; then
    healthy=yes
    break
  fi
  sleep 1
done

if [[ -z "$healthy" ]]; then
  echo >&2
  echo "the service did not answer /health — last 40 log lines:" >&2
  ssh "$TARGET" 'journalctl -u overdraft-guard -n 40 --no-pager' >&2
  exit 1
fi

# /health over ssh only proves uvicorn is up. It goes straight to 127.0.0.1:8000
# and never touches Caddy, so it passes just as cheerfully when Caddy is serving
# nothing and when the bundle is missing entirely — which is exactly how the
# frontend-path bug stayed invisible. Check what a person would actually load.
say "checking the site a visitor would see"
ORIGIN="${DOMAIN:+https://$DOMAIN}"
ORIGIN="${ORIGIN:-http://${TARGET#*@}}"

page="$(curl -fsS --max-time 20 "$ORIGIN/" 2>/dev/null || true)"
if [[ -z "$page" ]]; then
  echo "$ORIGIN/ served nothing. uvicorn is healthy, so this is Caddy or the bundle." >&2
  ssh "$TARGET" 'journalctl -u caddy -n 20 --no-pager' >&2
  exit 1
fi
if ! grep -qi '<div id="root"' <<<"$page"; then
  echo "$ORIGIN/ answered but does not look like the app:" >&2
  head -c 400 <<<"$page" >&2
  exit 1
fi

asset="$(grep -oE '/assets/[A-Za-z0-9._-]+\.js' <<<"$page" | head -1)"
if [[ -n "$asset" ]] && ! curl -fsS --max-time 20 -o /dev/null "$ORIGIN$asset"; then
  echo "the page references $asset and it does not load" >&2
  exit 1
fi

# A known scenario through the public origin, asserting the ANSWER and not just
# that something replied. `gap` is tier 3 by construction — no combination of
# changes closes it — so a wrong tier here means the solver on the box is not the
# solver this repo tests, which is the failure a reachability check cannot see.
sample="$(curl -fsS --max-time 20 "$ORIGIN/api/accounts/sample" \
    -H 'Content-Type: application/json' --data '{"seed":1}' || true)"
if ! grep -q '"source": *"modelled"' <<<"$sample"; then
  echo "the sample-account endpoint is not answering correctly through $ORIGIN" >&2
  exit 1
fi

tier="$(curl -fsS --max-time 30 "$ORIGIN/api/solve" \
    -H 'Content-Type: application/json' --data @deploy/smoke-gap.json \
    | sed -n 's/.*"tier": *\([0-9]\).*/\1/p' | head -1 || true)"
if [[ "$tier" != "3" ]]; then
  echo "public /api/solve returned tier '${tier:-<nothing>}' for the gap scenario; expected 3" >&2
  exit 1
fi

printf '\n\ndeployed and serving: %s\n' "$ORIGIN"
exit 0

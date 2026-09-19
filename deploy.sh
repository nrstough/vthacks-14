#!/usr/bin/env bash
#
# One command, laptop to box. Build here, ship the artifacts, restart there.
#
#   ./deploy.sh root@203.0.113.10
#   ./deploy.sh                      # reads TARGET from .deploy.env
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

TARGET="${1:-${TARGET:-}}"
if [[ -z "$TARGET" ]]; then
  echo "usage: ./deploy.sh user@host   (or set TARGET in .deploy.env)" >&2
  exit 2
fi

APP_DIR="${APP_DIR:-/opt/overdraft-guard}"
DOMAIN="${DOMAIN:-}"

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
rsync -az Caddyfile                      "$TARGET:/etc/caddy/Caddyfile"

say "installing dependencies and restarting"
ssh "$TARGET" APP_DIR="$APP_DIR" DOMAIN="$DOMAIN" 'bash -euo pipefail -s' <<'REMOTE'
  cd "$APP_DIR"

  if [[ ! -d .venv ]]; then
    python3 -m venv .venv
  fi
  ./.venv/bin/pip install --quiet --upgrade pip
  # ortools is the one that can fail: it needs a wheel for the box's exact
  # Python. If this errors, read the version it names before changing anything.
  ./.venv/bin/pip install --quiet -r requirements.txt

  # The Caddyfile ships with __DOMAIN__ as its site address. Left alone, Caddy
  # reads that as a HOSTNAME MATCHER and serves only requests carrying
  # `Host: __DOMAIN__` — so the box's own IP gets nothing at all. The comment at
  # the top of the Caddyfile used to claim the opposite; it was wrong, and this
  # is the substitution that has to happen either way.
  if [[ -n "${DOMAIN:-}" ]]; then
    sed -i "s|__DOMAIN__|$DOMAIN|g" /etc/caddy/Caddyfile
  else
    # No domain yet: listen on :80 so a bare-IP smoke test genuinely works.
    # No HTTPS, which is fine for a smoke test and not fine for a judge.
    sed -i "s|__DOMAIN__|:80|g" /etc/caddy/Caddyfile
  fi

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

if ! curl -fsS --max-time 20 -o /dev/null "$ORIGIN/api/accounts/sample" \
      -H 'Content-Type: application/json' --data '{"seed":1}'; then
  echo "the API is not reachable through $ORIGIN" >&2
  exit 1
fi

printf '\n\ndeployed and serving: %s\n' "$ORIGIN"
exit 0

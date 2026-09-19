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

say "shipping to $TARGET:$APP_DIR"
ssh "$TARGET" "mkdir -p '$APP_DIR'"

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

  if [[ -n "${DOMAIN:-}" ]]; then
    sed -i "s|__DOMAIN__|$DOMAIN|g" /etc/caddy/Caddyfile
  fi

  systemctl daemon-reload
  systemctl enable --now overdraft-guard
  systemctl restart overdraft-guard
  systemctl reload caddy 2>/dev/null || systemctl restart caddy
REMOTE

say "checking health"
for _ in $(seq 1 10); do
  if ssh "$TARGET" 'curl -fsS http://127.0.0.1:8000/health' 2>/dev/null; then
    printf '\n\ndeployed: %s\n' "${DOMAIN:-$TARGET}"
    exit 0
  fi
  sleep 1
done

echo >&2
echo "the service did not answer /health — last 40 log lines:" >&2
ssh "$TARGET" 'journalctl -u overdraft-guard -n 40 --no-pager' >&2
exit 1

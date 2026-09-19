#!/usr/bin/env bash
#
# Provision the VTHacks box on Vultr, from the laptop, over the v2 API.
#
#   ./vultr.sh check     account, credit, and whether the key works at all
#   ./vultr.sh resolve   look up region / plan / OS ids (creates nothing)
#   ./vultr.sh create    create the instance (asks nothing — call it deliberately)
#   ./vultr.sh status    poll the instance until it has an IP
#
# Every call is forced to IPv6 (-6): Vultr allowlisted this laptop's IPv6 address
# a person naturally pastes into Vultr's API allowlist is the IPv4 one, and a
# mismatch shows up as a bare 403 with nothing explaining it.

set -euo pipefail

# Repo root relative to this script, so the checkout can move or be a worktree.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
STATE="${STATE:-$REPO_ROOT/.vultr-instance.json}"

# Chosen in conversation: Atlanta (closest to Blacksburg), 2 vCPU / 8 GB with a
# bundled 120 GB NVMe so there is no separate bootable volume to attach, and
# Ubuntu 24.04 LTS because ortools needs a wheel for the box's exact Python and
# 24.04's 3.12 has the best coverage.
WANT_REGION_CITY="Atlanta"
WANT_PLAN="vx1-g-2c-8g-120s"
WANT_OS_MATCH="Ubuntu 24.04"
LABEL="overdraft-guard"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "no env file at $ENV_FILE" >&2
  exit 2
fi
set -a; . "$ENV_FILE"; set +a

if [[ -z "${VULTR_API_KEY:-}" ]]; then
  echo "VULTR_API_KEY is not set in $ENV_FILE" >&2
  exit 2
fi

API="https://api.vultr.com/v2"

# -4 is deliberate; see the header. --fail-with-body so a 4xx still prints the
# API's own error attribute rather than an empty string.
api() {
  local method="$1" path="$2"
  shift 2
  curl -6 -sS --fail-with-body --max-time 30 \
    -X "$method" "$API$path" \
    -H "Authorization: Bearer $VULTR_API_KEY" \
    -H "Content-Type: application/json" \
    "$@"
}

cmd_check() {
  echo "=== account ==="
  # Credit is carried as a NEGATIVE balance: $100 of credit reads as -100.
  api GET /account | python3 -c '
import json, sys
a = json.load(sys.stdin)["account"]
bal = a.get("balance", 0) or 0
print("  name          ", a.get("name"))
print("  email         ", a.get("email"))
if bal < 0:
    print("  balance       ", bal, "  ->  credit available: $%.2f" % -bal)
else:
    print("  balance       ", bal, "  ->  NO CREDIT AVAILABLE")
print("  pending       ", a.get("pending_charges"))
'
}

cmd_resolve() {
  echo "=== region ==="
  api GET "/regions?per_page=500" | WANT="$WANT_REGION_CITY" python3 -c '
import json, os, sys
want = os.environ["WANT"]
for r in json.load(sys.stdin)["regions"]:
    if r["city"] == want:
        print("  id=%s  %s, %s" % (r["id"], r["city"], r["country"]))
'
  echo "=== plan ==="
  api GET "/plans?per_page=500" | WANT="$WANT_PLAN" python3 -c '
import json, os, sys
want = os.environ["WANT"]
for p in json.load(sys.stdin)["plans"]:
    if p["id"] == want:
        print("  id=%s  %s vCPU  %s MB RAM  %s GB disk  $%s/mo" % (
            p["id"], p["vcpu_count"], p["ram"], p.get("disk"), p["monthly_cost"]))
        print("  available in: %s" % ",".join(p["locations"]))
'
  echo "=== os ==="
  api GET /os | WANT="$WANT_OS_MATCH" python3 -c '
import json, os, sys
want = os.environ["WANT"]
for o in json.load(sys.stdin)["os"]:
    if want in o["name"] and "x64" in (o.get("arch") or ""):
        print("  id=%s  %s" % (o["id"], o["name"]))
'
  echo "=== ssh keys on account ==="
  api GET /ssh-keys | python3 -c '
import json, sys
ks = json.load(sys.stdin)["ssh_keys"]
if not ks:
    print("  (none uploaded yet)")
for k in ks:
    print("  id=%s  %s" % (k["id"], k["name"]))
'
}

cmd_create() {
  # Defaults resolved live from the API on 2026-09-19 and confirmed by `resolve`.
  # Still overridable by environment, but defaulted so the ordinary invocation is
  # a bare `./deploy/vultr.sh create`: a command carrying an env-var prefix does
  # not START with the script path, so it matches no permission rule.
  local region="${REGION_ID:-atl}" plan="${PLAN_ID:-vx1-g-2c-8g-120s}"
  local os_id="${OS_ID:-2284}" key_id="${SSHKEY_ID:-d8e3cd1d-f7da-4719-b7d0-c5316860aa8d}"

  echo "creating $plan in $region, os $os_id, key $key_id"
  local body
  body="$(REGION="$region" PLAN="$plan" OSID="$os_id" KEYID="$key_id" LBL="$LABEL" python3 -c '
import json, os
print(json.dumps({
    "region": os.environ["REGION"],
    "plan": os.environ["PLAN"],
    "os_id": int(os.environ["OSID"]),
    "label": os.environ["LBL"],
    "hostname": os.environ["LBL"],
    "sshkey_id": [os.environ["KEYID"]],
    "backups": "disabled",
    "enable_ipv6": True,
}))')"
  api POST /instances --data "$body" | tee "$STATE" | python3 -c '
import json, sys
i = json.load(sys.stdin)["instance"]
print("  id     ", i["id"])
print("  status ", i["status"])
'
}

cmd_status() {
  local id
  id="$(python3 -c "import json;print(json.load(open('$STATE'))['instance']['id'])")"
  api GET "/instances/$id" | python3 -c '
import json, sys
i = json.load(sys.stdin)["instance"]
print("  status      ", i["status"], "/", i.get("server_status"))
print("  main_ip     ", i.get("main_ip"))
print("  region      ", i.get("region"), " plan", i.get("plan"))
print("  os          ", i.get("os"))
'
}

case "${1:-}" in
  check)   cmd_check   ;;
  resolve) cmd_resolve ;;
  create)  cmd_create  ;;
  status)  cmd_status  ;;
  *) echo "usage: $0 {check|resolve|create|status}" >&2; exit 2 ;;
esac

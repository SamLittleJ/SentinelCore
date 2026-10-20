#!/usr/bin/env bash
# `make cluster-check`: the security properties of the cluster `make up`
# runs, checked from outside and inside, one line each. Needs the cluster
# running. Prints no secret; exits with 1 if any check fails.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAMESPACE=sentinelcore
URL=http://localhost:8080
OWNER_EMAIL="${OWNER_EMAIL:-owner@example.com}"
PATH="$("$ROOT/scripts/tools.sh"):$PATH"
export KUBECONFIG="$ROOT/.kind/kubeconfig"
failed=0

# check <name> <command...>: PASS or FAIL, with the command's output hidden.
check() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf 'PASS %s\n' "$name"
  else
    printf 'FAIL %s\n' "$name"
    failed=$((failed + 1))
  fi
}

in_pod() { kubectl exec --namespace "$NAMESPACE" "$1" -c "$2" -- sh -c "$3"; }

sql() {
  kubectl exec --namespace "$NAMESPACE" sentinelcore-postgresql-0 -- \
    psql -U sentinelcore -d sentinelcore -tAc "$1"
}

status_of() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

if [[ ! -f "$KUBECONFIG" ]]; then
  echo "No cluster: run \`make up\` first." >&2
  exit 1
fi

# The workloads, one pod each: name and container.
backend="$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=sentinelcore-backend \
  --field-selector=status.phase=Running -o name | head -1)"
console="$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=sentinelcore-console \
  --field-selector=status.phase=Running -o name | head -1)"
pods=("$backend backend" "$console console" "pod/sentinelcore-postgresql-0 postgresql")

# From outside, through nginx

ready() { [[ "$(curl -sf "$URL/api/health/ready")" == '{"status":"ok","database":"ok"}' ]]; }
check "the API is ready through nginx" ready

# Every header the console's build expects, with its exact value.
console_headers() {
  local headers expected name value
  headers="$(curl -sfI "$URL/")" || return 1
  expected="$(cd "$ROOT/frontend" && node scripts/nginx-headers.ts)" || return 1
  while read -r _ name value; do
    value="${value% always;}"
    value="${value#\"}"
    value="${value%\"}"
    grep -qiF "$name: $value" <<<"$headers" || return 1
  done <<<"$expected"
}
check "the console has its security headers" console_headers

spa_route() { [[ "$(status_of "$URL/org/overview")" == 200 ]]; }
check "console routes fall back to the console" spa_route

hidden() {
  local path
  for path in /api/metrics /api/docs /api/redoc /api/openapi.json; do
    [[ "$(status_of "$URL$path")" == 404 ]] || return 1
  done
}
check "metrics and API docs are not served outside" hidden

# The API records the address nginx saw: not the one the client wrote in
# X-Forwarded-For, nor nginx's own in the pod network (FORWARDED_ALLOW_IPS).
# The owner signs in successfully, with the password from stdin: a failure
# would count towards the sign-in limit, and the spray rule, of the one
# address all local traffic comes from.
sender_address() {
  local before recorded
  [[ -f "$ROOT/.kind/owner.txt" ]] || return 1
  before="$(sql "SELECT coalesce(max(id), 0) FROM security_events")"
  printf '{"email":"%s","password":"%s"}' "$OWNER_EMAIL" "$(cat "$ROOT/.kind/owner.txt")" |
    curl -sf -o /dev/null -H 'X-Forwarded-For: 203.0.113.77' -H 'Content-Type: application/json' \
      --data-binary @- "$URL/api/auth/login" || return 1
  recorded="$(sql "SELECT ip_address FROM security_events WHERE id > $before AND event_type = 'LOGIN_SUCCESS' ORDER BY id DESC LIMIT 1")"
  [[ -n "$recorded" && "$recorded" != 203.0.113.77 && "$recorded" != 10.244.* ]]
}
check "the API records the sender's address, not a spoofed one" sender_address

# More requests at once than nginx's burst for ingestion.
ingest_limit() {
  seq 1 160 | xargs -P 40 -I{} curl -s -o /dev/null -w '%{http_code}\n' \
    -X POST -H 'Content-Type: application/json' -d '{}' "$URL/api/ingest/events" | grep -qx 429
}
check "nginx limits ingestion per address" ingest_limit

# Inside the pods. The commands are in single quotes on purpose: they expand
# in the pod's shell, not here.

# shellcheck disable=SC2016
for entry in "${pods[@]}"; do
  read -r pod container <<<"$entry"
  check "$container runs as a user other than root" in_pod "$pod" "$container" '[ "$(id -u)" != 0 ]'
  # Mounted read-only, not just owned by root: a user other than root could
  # not write there either way.
  check "$container has a read-only root file system" in_pod "$pod" "$container" \
    'awk '"'"'$2 == "/" { print $4 }'"'"' /proc/self/mounts | grep -q "^ro,"'
  # The bounding set: what any process could ever gain, which a user other
  # than root does not show in its effective set anyway.
  check "$container has no capabilities" in_pod "$pod" "$container" \
    'grep -q "^CapBnd:[[:space:]]*0000000000000000$" /proc/1/status'
  check "$container has no Kubernetes token" in_pod "$pod" "$container" \
    '[ ! -e /var/run/secrets/kubernetes.io/serviceaccount/token ]'
done

# shellcheck disable=SC2016
check "the API pods lack the owner's database URL" in_pod "$backend" backend '[ -z "${MIGRATIONS_DATABASE_URL:-}" ]'

app_role() { [[ "$(sql "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = 'sentinelcore_app'")" == f ]]; }
check "the API's database role is bound by row-level security" app_role

check "the audit history is intact" in_pod "$backend" backend 'python -m app.cli verify-audit-chain'

if ((failed > 0)); then
  printf '%d check(s) failed\n' "$failed"
  exit 1
fi

#!/usr/bin/env bash
# `make incident`: the incident drill of phase F (docs/postmortems/), on the
# cluster `make up` runs, and only there. It starts the incident and nothing
# more; the response follows the runbooks (docs/runbooks/), by hand.
#
#   1. A password spray: an organization of its own, "Northwind (incident
#      drill)", then one wrong password for each of twelve of its members,
#      from one address (python -m simulator.incident).
#   2. A shell with a terminal in a running API container, which Falco
#      reports: `id` and `hostname`, which change nothing.
#
# Each step prints its UTC time, for the postmortem's timeline. Falco stores
# the same alert for a pod once in ten minutes, so a second run within ten
# minutes of the first shows no new shell alert.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.kind"
URL=http://localhost:8080
NAMESPACE=sentinelcore
OWNER_EMAIL="${OWNER_EMAIL:-owner@example.com}"

PATH="$("$ROOT/scripts/tools.sh"):$PATH"
export KUBECONFIG="$STATE/kubeconfig"

fail() {
  echo "make incident: $*" >&2
  exit 1
}
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# The `make up` cluster only: never the GitOps one, whose self-heal would
# mix with the response, nor anything else.
[[ "${CLUSTER:-}" != gitops ]] || fail "the drill runs on make up's cluster only"
[[ -f "$KUBECONFIG" && -s "$STATE/owner.txt" ]] || fail "no make up cluster; run make up"
[[ "$(kubectl config current-context)" == kind-sentinelcore ]] ||
  fail "the kubeconfig names $(kubectl config current-context), not kind-sentinelcore"
[[ "$(curl -s -o /dev/null -w '%{http_code}' "$URL/api/health")" == 200 ]] ||
  fail "the API does not answer at $URL"

echo "$(now) incident drill starts on the make up cluster"
(cd "$ROOT/backend" && SENTINELCORE_OWNER_PASSWORD="$(cat "$STATE/owner.txt")" \
  .venv/bin/python -m simulator.incident --base-url "$URL/api" --owner-email "$OWNER_EMAIL")

pod="$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=sentinelcore-backend \
  -o jsonpath='{.items[0].metadata.name}')"
echo "$(now) shell with a terminal in $pod (container backend)"
# Python gives kubectl the terminal Falco's rule needs, as cluster-check does.
python3 -c 'import pty, sys; sys.exit(pty.spawn(sys.argv[1:]) >> 8)' \
  kubectl exec -it -n "$NAMESPACE" "$pod" -c backend -- sh -c 'id; hostname' >/dev/null
echo "$(now) shell ends"
echo "$(now) incident drill done; respond with docs/runbooks/"

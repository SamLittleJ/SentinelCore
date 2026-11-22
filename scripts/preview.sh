#!/usr/bin/env bash
# `make preview PR=<n> [SEED=1]`: the preview of pull request <n> on the
# GitOps cluster (docs/07-gitops.md, Previews), once Argo CD has made it.
#
# Waits for its two applications to be synced and healthy, writes its
# owner's password to .kind/gitops/preview-<n>.txt (mode 600, never
# printed), then forwards http://127.0.0.1:8090 to its console until
# Ctrl-C. With SEED=1, first fills its database with the demo's ninety days
# of three organizations (`make demo`'s simulator, from this machine through
# port-forwards), once.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.kind/gitops"
PR="${PR:-}"
SEED="${SEED:-}"
OWNER_EMAIL=owner@sim.example.com
PORT=8090

PATH="$("$ROOT/scripts/tools.sh"):$PATH"
export KUBECONFIG="$STATE/kubeconfig"

say() { printf '==> %s\n' "$*"; }
fail() {
  echo "make preview: $*" >&2
  exit 1
}

[[ "$PR" =~ ^[1-9][0-9]*$ ]] || fail "give the pull request's number: make preview PR=<n>"
[[ -f "$KUBECONFIG" ]] || fail "no GitOps cluster; run make gitops-up"
NAMESPACE="preview-$PR"

# Synced and healthy, both; the base first, then the application, which
# waits for it.
wait_preview() {
  local deadline=$((SECONDS + 900)) app status
  for app in "$NAMESPACE-base" "$NAMESPACE"; do
    while true; do
      status="$(kubectl get application "$app" -n argocd \
        -o jsonpath='{.status.sync.status}/{.status.health.status}' 2>/dev/null || true)"
      [[ "$status" == Synced/Healthy ]] && break
      if ((SECONDS > deadline)); then
        fail "$app is ${status:-missing} after 15 minutes; is pull request $PR open, labelled preview, with its images published?"
      fi
      sleep 10
    done
  done
}

secret_value() {
  kubectl get secret "$1" -n "$NAMESPACE" -o jsonpath="{.data.$2}" | base64 -d
}

say "Waiting for $NAMESPACE (Argo CD asks GitHub every five minutes)"
wait_preview
(umask 077 && {
  echo "SentinelCore preview of pull request $PR (local only)"
  echo "email: $OWNER_EMAIL"
  echo "password: $(secret_value preview-owner SENTINELCORE_OWNER_PASSWORD)"
} >"$STATE/$NAMESPACE.txt")

forwards=()
stop_forwards() {
  ((${#forwards[@]})) && kill "${forwards[@]}" 2>/dev/null || true
}
trap stop_forwards EXIT

forward() {
  kubectl port-forward -n "$NAMESPACE" --address 127.0.0.1 "$1" "$2" >/dev/null &
  forwards+=("$!")
  local port="${2%%:*}"
  for _ in $(seq 1 30); do
    (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null && return
    sleep 1
  done
  fail "the port-forward to $1 did not open"
}

if [[ "$SEED" == 1 ]]; then
  accounts="$STATE/$NAMESPACE"
  [[ -e "$accounts" ]] && fail "$NAMESPACE was already seeded (${accounts#"$ROOT/"}); the demo needs an empty database"
  say "Ninety days of three synthetic organizations, through port-forwards"
  forward svc/sentinelcore-backend 18000:8000
  forward svc/sentinelcore-postgresql 15432:5432
  mkdir -m 700 "$accounts"
  # The owner's URL, pointed at the forward; through the environment only.
  database="$(secret_value sentinelcore-migrations MIGRATIONS_DATABASE_URL |
    sed 's#@sentinelcore-postgresql:5432/#@127.0.0.1:15432/#')"
  (cd "$ROOT/backend" &&
    SENTINELCORE_OWNER_PASSWORD="$(secret_value preview-owner SENTINELCORE_OWNER_PASSWORD)" \
      MIGRATIONS_DATABASE_URL="$database" \
      .venv/bin/python -m simulator.demo --base-url http://127.0.0.1:18000 \
      --owner-email "$OWNER_EMAIL" --accounts-dir "$accounts" --forwarded-for) ||
    { rm -rf "$accounts"; fail "the demo's data could not be loaded"; }
  unset database
fi

say "Preview of pull request $PR: http://127.0.0.1:$PORT (Ctrl-C stops it)"
say "Sign in as $OWNER_EMAIL; the password is in ${STATE#"$ROOT/"}/$NAMESPACE.txt"
kubectl port-forward -n "$NAMESPACE" --address 127.0.0.1 svc/sentinelcore-console "$PORT:8080"

#!/usr/bin/env bash
# The GitOps cluster (docs/07-gitops.md), beside `make up`'s.
#
#   up      Terraform creates the kind cluster sentinelcore-gitops and installs
#           Argo CD (gitops/); then the namespaces and the Secrets, which no
#           Git file and no Terraform state holds (scripts/cluster.sh
#           prepare); then the root application (deploy/root.yaml), which
#           installs everything else from Git; waits for every application
#           to be synced and healthy; then the first owner. The console is
#           at http://localhost:8081. GITOPS_REVISION picks the Git revision
#           Argo CD reads (default: main; CI gives the commit it checks).
#   down    deletes the cluster and its state, after a typed confirmation.
#   argocd  forwards 127.0.0.1:3002 to Argo CD's UI until stopped (user
#           admin, password in .kind/gitops/argocd.txt).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER=sentinelcore-gitops
STATE="$ROOT/.kind/gitops"
URL=http://localhost:8081
GITOPS_REVISION="${GITOPS_REVISION:-main}"

PATH="$("$ROOT/scripts/tools.sh"):$PATH"
export KUBECONFIG="$STATE/kubeconfig"
export TF_DATA_DIR="$STATE/terraform"

say() { printf '==> %s\n' "$*"; }
tf() { terraform -chdir="$ROOT/gitops" "$@"; }
tf_vars=(-var "kubeconfig_path=$KUBECONFIG" -var "argocd_chart=$ROOT/.tools/argo-cd.tgz")

# The commit GITOPS_REVISION names: a full commit as it is, a branch or tag
# as GitHub has it now.
resolve_revision() {
  if [[ "$GITOPS_REVISION" =~ ^[0-9a-f]{40}$ ]]; then
    echo "$GITOPS_REVISION"
    return
  fi
  local repo
  repo="$(sed -n 's/^repoURL: //p' "$ROOT/deploy/values.yaml")"
  git ls-remote "$repo" "refs/heads/$GITOPS_REVISION" "refs/tags/$GITOPS_REVISION" | awk 'NR == 1 { print $1 }'
}

# Kyverno checks the signature, provenance and SBOM of each of our images as
# a pod starts, online with Sigstore: 17 to 28 seconds on kind, against the
# admission webhook's 30. When several pods start at once, the checks time
# out and are retried without end; a restart of its admission controller has
# let them through (docs/07-gitops.md). True when a pod was refused for that
# in the last three minutes.
kyverno_stuck() {
  kubectl get events -A --field-selector reason=FailedCreate -o json | jq -e '
    [.items[] | select((.message | test("kyverno.*(Timeout|timed out|deadline)"))
      and ((.lastTimestamp // .eventTime) | sub("\\.[0-9]+"; "") | fromdateiso8601) > (now - 180))]
    | length > 0' >/dev/null
}

# Every application synced and healthy at that commit, or the ones that are
# not after the time allowed. Synced alone is not enough: right after the
# root application moves to another revision, the others still report the
# one they had.
wait_applications() {
  local deadline=$((SECONDS + 1200)) pending commit
  commit="$(resolve_revision)"
  [[ -n "$commit" ]] || { echo "No commit for $GITOPS_REVISION on GitHub." >&2; return 1; }
  local restarted=0
  while ((SECONDS < deadline)); do
    if ((restarted == 0)) && kyverno_stuck; then
      say "Kyverno timed out checking image signatures; restarting its admission controller once"
      kubectl delete pod -n kyverno -l app.kubernetes.io/component=admission-controller >/dev/null
      restarted=1
    fi
    pending="$(kubectl get applications -n argocd -o json | jq -r --arg commit "$commit" '
      .items[] | select(.status.sync.status != "Synced" or .status.health.status != "Healthy"
        or (([.status.sync.revision] + (.status.sync.revisions // [])) | index($commit) | not))
      | "\(.metadata.name): \(.status.sync.status // "-")/\(.status.health.status // "-")"')"
    if [[ -z "$pending" ]] && (($(kubectl get applications -n argocd -o name | wc -l) > 1)); then
      return 0
    fi
    sleep 10
  done
  echo "Not synced and healthy after 20 minutes:" >&2
  printf '%s\n' "$pending" >&2
  return 1
}

up() {
  mkdir -p "$STATE"
  chmod 700 "$STATE"
  say "Creating the cluster $CLUSTER and Argo CD (Terraform)"
  tf init -input=false -backend-config="path=$STATE/terraform.tfstate" >/dev/null
  tf apply -input=false -auto-approve "${tf_vars[@]}"
  chmod 600 "$KUBECONFIG"

  # Argo CD's pods meet the restricted standard; only the flows it needs.
  kubectl label namespace argocd --overwrite \
    pod-security.kubernetes.io/enforce=restricted \
    pod-security.kubernetes.io/enforce-version=v1.35 >/dev/null
  kubectl apply -f "$ROOT/gitops/network-policy.yaml" >/dev/null

  say "Creating the namespaces and the Secrets"
  CLUSTER="$CLUSTER" STATE="$STATE" URL="$URL" "$ROOT/scripts/cluster.sh" prepare

  # Argo CD's own random admin password, kept here only.
  if [[ ! -s "$STATE/argocd.txt" ]]; then
    (umask 077 && kubectl get secret argocd-initial-admin-secret -n argocd \
      -o jsonpath='{.data.password}' | base64 -d >"$STATE/argocd.txt")
  fi

  say "Applying the root application at $GITOPS_REVISION"
  kubectl create --dry-run=client -o json -f "$ROOT/deploy/root.yaml" |
    jq --arg revision "$GITOPS_REVISION" '
      .spec.source.targetRevision = $revision
      | .spec.source.helm.parameters = [{name: "revision", value: $revision}]' |
    kubectl apply -f - >/dev/null
  say "Waiting for every application to be synced and healthy"
  wait_applications

  local image
  # The API is a Rollout here (its canary, deploy/sentinelcore.yaml).
  image="$(kubectl get rollout.argoproj.io sentinelcore-backend -n sentinelcore \
    -o jsonpath='{.spec.template.spec.containers[?(@.name=="backend")].image}')"
  OWNER_IMAGE="$image" CLUSTER="$CLUSTER" STATE="$STATE" URL="$URL" "$ROOT/scripts/cluster.sh" owner
  say "SentinelCore (GitOps) is at $URL"
  say "Argo CD: make argocd; for kubectl: export KUBECONFIG=$KUBECONFIG"
}

down() {
  if [[ ! -f "$STATE/terraform.tfstate" ]]; then
    rm -rf "$STATE"
    say "No cluster $CLUSTER"
    return
  fi
  local answer
  read -r -p "This deletes the cluster $CLUSTER and all its data. Type $CLUSTER to go on: " answer
  if [[ "$answer" != "$CLUSTER" ]]; then
    echo "Nothing was deleted." >&2
    exit 1
  fi
  # The whole cluster, not its applications one by one: some charts' delete
  # hooks would wait for namespaces that go first.
  tf init -input=false -backend-config="path=$STATE/terraform.tfstate" >/dev/null
  tf destroy -input=false -auto-approve -target=kind_cluster.gitops "${tf_vars[@]}"
  rm -rf "$STATE"
}

argocd() {
  echo "Argo CD at http://127.0.0.1:3002 (user admin, password in .kind/gitops/argocd.txt); Ctrl-C stops it."
  kubectl port-forward -n argocd --address 127.0.0.1 svc/argocd-server 3002:80
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  argocd) argocd ;;
  *)
    echo "usage: $0 up|down|argocd" >&2
    exit 2
    ;;
esac

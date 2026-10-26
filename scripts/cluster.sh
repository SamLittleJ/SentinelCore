#!/usr/bin/env bash
# `make up` / `make down`: SentinelCore on a local kind cluster.
#
#   up    the cluster if missing, the images loaded into it, the secrets if
#         missing, PostgreSQL, then the application (its migrations run
#         first), then the first owner if missing. Safe to run again.
#   down  deletes the cluster and its data, after a typed confirmation.
#
# Uses the pinned tools of scripts/tools.sh and its own kubeconfig in .kind/,
# so ~/.kube/config is left alone. `make up` builds the images first and
# passes their tag as REVISION; `make up FROM=registry` instead pulls the
# commit's signed GHCR images (scripts/verify-images.sh) under that same tag,
# so the rest is identical. Generated passwords and keys go straight to
# Kubernetes Secrets; the owner's password to .kind/owner.txt only. None is
# printed or passed on a command line.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER=sentinelcore
NAMESPACE=sentinelcore
STATE="$ROOT/.kind"
URL=http://localhost:8080
OWNER_EMAIL="${OWNER_EMAIL:-owner@example.com}"
OWNER_USERNAME="${OWNER_USERNAME:-owner}"

PATH="$("$ROOT/scripts/tools.sh"):$PATH"
export KUBECONFIG="$STATE/kubeconfig"

say() { printf '==> %s\n' "$*"; }

# A random value of 32 bytes, as hex: safe inside a URL or an env file.
random() { openssl rand -hex 32; }

cluster_exists() { kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; }

create_cluster() {
  mkdir -p "$STATE"
  chmod 700 "$STATE"
  if cluster_exists; then
    kind export kubeconfig --name "$CLUSTER" --kubeconfig "$KUBECONFIG" >/dev/null
  else
    say "Creating the kind cluster $CLUSTER"
    kind create cluster --config "$ROOT/kind/cluster.yaml" --kubeconfig "$KUBECONFIG" --wait 2m
  fi
  chmod 600 "$KUBECONFIG"
  kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE"
}

load_images() {
  say "Loading the images tagged $REVISION"
  kind load docker-image --name "$CLUSTER" \
    "sentinelcore-backend:$REVISION" "sentinelcore-console:$REVISION"
}

# secret <name> <key=value lines on stdin>: created from a file descriptor,
# so the values never reach a command line or the disk.
secret() {
  kubectl create secret generic "$1" --namespace "$NAMESPACE" --from-env-file=/dev/stdin >/dev/null
  kubectl label secret "$1" --namespace "$NAMESPACE" app.kubernetes.io/part-of=sentinelcore >/dev/null
}

create_secrets() {
  local names=(sentinelcore-postgresql sentinelcore-api sentinelcore-migrations) present=0 name
  for name in "${names[@]}"; do
    kubectl get secret "$name" --namespace "$NAMESPACE" >/dev/null 2>&1 && present=$((present + 1))
  done
  if ((present == ${#names[@]})); then
    return
  fi
  # The audit history is sealed with AUDIT_CHAIN_KEY and the database holds
  # the passwords: a partial set cannot be completed with new values.
  if ((present > 0)); then
    echo "Only some of the secrets exist; run \`make down\`, then \`make up\`." >&2
    exit 1
  fi

  say "Generating the secrets"
  local owner_password app_password database
  owner_password="$(random)"
  app_password="$(random)"
  database="sentinelcore-postgresql:5432/sentinelcore"
  printf 'password=%s\n' "$owner_password" | secret sentinelcore-postgresql
  printf 'MIGRATIONS_DATABASE_URL=postgresql+psycopg://sentinelcore:%s@%s\n' \
    "$owner_password" "$database" | secret sentinelcore-migrations
  printf 'SECRET_KEY=%s\nAUDIT_CHAIN_KEY=%s\nMETRICS_TOKEN=%s\nDATABASE_URL=postgresql+psycopg://sentinelcore_app:%s@%s\n' \
    "$(random)" "$(random)" "$(random)" "$app_password" "$database" | secret sentinelcore-api
}

image_id() { docker image inspect --format '{{.Id}}' "$1:$REVISION"; }

install_charts() {
  say "Installing PostgreSQL"
  helm upgrade --install postgresql "$ROOT/charts/postgresql" \
    --namespace "$NAMESPACE" --wait --timeout 3m
  say "Installing SentinelCore (migrations first)"
  helm upgrade --install sentinelcore "$ROOT/charts/sentinelcore" \
    --namespace "$NAMESPACE" --wait --timeout 5m \
    --set-string image.tag="$REVISION" \
    --set-string image.ids.backend="$(image_id sentinelcore-backend)" \
    --set-string image.ids.console="$(image_id sentinelcore-console)"
}

# The first owner, once: the password passes through a Secret that lives
# only while the Job runs, and is kept only if the Job created the owner.
owner_log=""
remove_owner_job() {
  rm -f "$owner_log"
  kubectl delete job,secret sentinelcore-owner --namespace "$NAMESPACE" --ignore-not-found >/dev/null
}

create_owner() {
  local password
  password="$(random)"
  owner_log="$(mktemp)"
  # Also when the Job fails and the script stops.
  trap remove_owner_job EXIT
  printf 'SENTINELCORE_OWNER_PASSWORD=%s\n' "$password" | secret sentinelcore-owner

  kubectl apply --namespace "$NAMESPACE" -f - >/dev/null <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: sentinelcore-owner
  labels:
    app.kubernetes.io/name: sentinelcore-owner
    app.kubernetes.io/part-of: sentinelcore
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 120
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: sentinelcore-backend
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: owner
          image: sentinelcore-backend:$REVISION
          imagePullPolicy: IfNotPresent
          args: ["python", "-m", "app.cli", "create-owner", "--email", "$OWNER_EMAIL",
                 "--username", "$OWNER_USERNAME", "--if-missing"]
          envFrom:
            - secretRef:
                name: sentinelcore-api
            - secretRef:
                name: sentinelcore-owner
          resources:
            requests: {cpu: 100m, memory: 256Mi}
            limits: {cpu: 500m, memory: 512Mi}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
EOF

  if ! kubectl wait --namespace "$NAMESPACE" --for=condition=complete job/sentinelcore-owner --timeout=120s >/dev/null; then
    kubectl logs --namespace "$NAMESPACE" job/sentinelcore-owner >&2 || true
    echo "The owner could not be created." >&2
    exit 1
  fi
  kubectl logs --namespace "$NAMESPACE" job/sentinelcore-owner >"$owner_log"
  if grep -q '^Created the owner' "$owner_log"; then
    (umask 077 && printf '%s\n' "$password" >"$STATE/owner.txt")
    say "Created the owner $OWNER_EMAIL; the password is in .kind/owner.txt"
  else
    say "An owner already exists; .kind/owner.txt is unchanged"
  fi
  remove_owner_job
  trap - EXIT
}

up() {
  : "${REVISION:?run through make up, which builds the images}"
  create_cluster
  load_images
  create_secrets
  install_charts
  create_owner
  say "SentinelCore is at $URL"
  say "For kubectl: export KUBECONFIG=$KUBECONFIG"
}

down() {
  if ! cluster_exists; then
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
  kind delete cluster --name "$CLUSTER" --kubeconfig "$KUBECONFIG"
  rm -rf "$STATE"
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  *)
    echo "usage: $0 up|down" >&2
    exit 2
    ;;
esac

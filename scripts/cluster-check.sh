#!/usr/bin/env bash
# `make cluster-check`: the security properties of the cluster `make up`
# runs, checked from outside and inside, one line each. Needs the cluster
# running. Prints no secret; exits with 1 if any check fails. With
# CLUSTER=gitops it checks the GitOps cluster (`make gitops-up`) instead.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAMESPACE=sentinelcore
STATE="$ROOT/.kind"
URL=http://localhost:8080
if [[ "${CLUSTER:-}" == gitops ]]; then
  STATE="$ROOT/.kind/gitops"
  URL=http://localhost:8081
fi
OWNER_EMAIL="${OWNER_EMAIL:-owner@example.com}"
PATH="$("$ROOT/scripts/tools.sh"):$PATH"
export KUBECONFIG="$STATE/kubeconfig"
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
  for path in /api/metrics /api/docs /api/redoc /api/openapi.json /api/ingest/runtime; do
    [[ "$(status_of "$URL$path")" == 404 ]] || return 1
  done
}
check "metrics, API docs and Falco's endpoint are not served outside" hidden

# The API records the address nginx saw: not the one the client wrote in
# X-Forwarded-For, nor nginx's own in the pod network (FORWARDED_ALLOW_IPS).
# The owner signs in successfully, with the password from stdin: a failure
# would count towards the sign-in limit, and the spray rule, of the one
# address all local traffic comes from.
sender_address() {
  local before recorded
  [[ -f "$STATE/owner.txt" ]] || return 1
  before="$(sql "SELECT coalesce(max(id), 0) FROM security_events")"
  printf '{"email":"%s","password":"%s"}' "$OWNER_EMAIL" "$(cat "$STATE/owner.txt")" |
    curl -sf -o /dev/null -H 'X-Forwarded-For: 203.0.113.77' -H 'Content-Type: application/json' \
      --data-binary @- "$URL/api/auth/login" || return 1
  recorded="$(sql "SELECT ip_address FROM security_events WHERE id > $before AND event_type = 'LOGIN_SUCCESS' ORDER BY id DESC LIMIT 1")"
  [[ -n "$recorded" && "$recorded" != 203.0.113.77 && "$recorded" != 10.244.* ]]
}
check "the API records the sender's address, not a spoofed one" sender_address

# More requests at once than nginx's burst for ingestion. grep -c reads to the
# end: -q would stop at the first 429 and fail the requests still writing.
ingest_limit() {
  seq 1 160 | xargs -P 40 -I{} curl -s -o /dev/null -w '%{http_code}\n' \
    -X POST -H 'Content-Type: application/json' -d '{}' "$URL/api/ingest/events" |
    grep -cx 429 >/dev/null
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

# Network: only the flows the application needs (network-policies/). A
# connection that should be refused is tried by IP address, so a policy that
# broke name resolution could not pass it; allowed ones go by name, which
# checks DNS too.
# reaches <pod> <container> <host> <port>: a TCP connection within 3 seconds.
reaches() {
  if [[ "$2" == console ]]; then
    in_pod "$1" "$2" "nc -z -w 3 $3 $4"
  else
    in_pod "$1" "$2" "timeout 3 bash -c '</dev/tcp/$3/$4'"
  fi
}
blocked() { ! reaches "$@"; }
postgresql_ip="$(kubectl get pod -n "$NAMESPACE" sentinelcore-postgresql-0 -o jsonpath='{.status.podIP}')"
backend_ip="$(kubectl get service -n "$NAMESPACE" sentinelcore-backend -o jsonpath='{.spec.clusterIP}')"
check "the console reaches the API" reaches "$console" console sentinelcore-backend 8000
check "the API reaches the database" reaches "$backend" backend sentinelcore-postgresql 5432
check "the console cannot reach the database" blocked "$console" console "$postgresql_ip" 5432
check "the database cannot reach the API" blocked pod/sentinelcore-postgresql-0 postgresql "$backend_ip" 8000
check "the API cannot reach the internet" blocked "$backend" backend 1.1.1.1 443


# Admission: a pod that breaks one rule is refused, each for its own reason
# (the namespace's "restricted" Pod Security Standard, kyverno/pod-rules.yaml).
# Asked with --dry-run=server, so nothing is created. The probe is a pod that
# meets every rule, on the PostgreSQL image already pinned in the chart.
probe() {
  local image
  image="$(awk '/repository:/ {r=$2} /digest:/ {d=$2} END {print r "@" d}' "$ROOT/charts/postgresql/values.yaml")"
  jq -n --arg image "$image" --arg namespace "$NAMESPACE" '{
    apiVersion: "v1", kind: "Pod",
    metadata: {name: "admission-probe", namespace: $namespace},
    spec: {
      automountServiceAccountToken: false,
      securityContext: {runAsNonRoot: true, runAsUser: 10001, seccompProfile: {type: "RuntimeDefault"}},
      containers: [{
        name: "probe", image: $image,
        securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {drop: ["ALL"]}},
        resources: {requests: {cpu: "10m", memory: "16Mi"}, limits: {cpu: "10m", memory: "16Mi"}}
      }]
    }}'
}
admit() { kubectl apply --dry-run=server -f - 2>&1; }
probe_admitted() { probe | admit >/dev/null; }
check "a pod that meets every rule is admitted" probe_admitted

# refused <reason in the refusal> <jq change to the probe>
refused() {
  local answer
  answer="$(probe | jq "$2" | admit)" && return 1
  grep -qF "$1" <<<"$answer"
}
check "a pod running as root is refused" refused 'violates PodSecurity' '.spec.securityContext.runAsUser = 0'
check "a pod that may gain privileges is refused" refused 'violates PodSecurity' \
  '.spec.containers[0].securityContext.allowPrivilegeEscalation = true'
check "a pod with a writable root file system is refused" refused 'readOnlyRootFilesystem' \
  '.spec.containers[0].securityContext.readOnlyRootFilesystem = false'
check "a pod without resource limits is refused" refused 'requests and limits' 'del(.spec.containers[0].resources.limits)'
check "a pod with a Kubernetes token is refused" refused 'automountServiceAccountToken' \
  '.spec.automountServiceAccountToken = true'
check "an image by tag only is refused" refused 'pinned by digest' '.spec.containers[0].image = "postgres:17"'

# With the signature policy (the GitOps cluster, `make up FROM=registry`):
# one of our image names under a digest images-ci.yml on main never signed
# (none was published under it) is refused by that policy.
# The GitOps cluster must have it.
if [[ "${CLUSTER:-}" == gitops ]] || kubectl get imagevalidatingpolicy sentinelcore-signatures >/dev/null 2>&1; then
  check "an image of ours not signed by CI is refused" refused 'sentinelcore-signatures' \
    ".spec.containers[0].image = \"ghcr.io/samlittlej/sentinelcore-backend@sha256:$(printf '0%.0s' {1..64})\""
fi

# The nightly backup (charts/postgresql/templates/backup.yaml, phase E6): its
# pod, as the CronJob would create it, is admitted, and a copy of it that
# only waits reaches the database but neither the API nor the internet.
backup_pod() {
  kubectl get cronjob sentinelcore-backup -n "$NAMESPACE" -o json |
    jq --arg name "$1" --arg namespace "$NAMESPACE" '{
    apiVersion: "v1", kind: "Pod",
    metadata: {name: $name, namespace: $namespace, labels: .spec.jobTemplate.spec.template.metadata.labels},
    spec: (.spec.jobTemplate.spec.template.spec | .containers[0].command = ["sleep", "120"])
  }'
}
backup_admitted() { backup_pod backup-probe | admit >/dev/null; }
check "the nightly backup's pod is admitted" backup_admitted

backup_probe="backup-probe-$(date +%s)"
if backup_pod "$backup_probe" | kubectl apply -n "$NAMESPACE" -f - >/dev/null 2>&1 &&
  kubectl wait -n "$NAMESPACE" --for=condition=Ready "pod/$backup_probe" --timeout=60s >/dev/null 2>&1; then
  check "the backup reaches the database" reaches "pod/$backup_probe" backup sentinelcore-postgresql 5432
  check "the backup cannot reach the API" blocked "pod/$backup_probe" backup "$backend_ip" 8000
  check "the backup cannot reach the internet" blocked "pod/$backup_probe" backup 1.1.1.1 443
else
  check "the backup's probe pod starts" false
fi
kubectl delete pod -n "$NAMESPACE" "$backup_probe" --ignore-not-found --wait=false >/dev/null 2>&1

# Runtime detection: a shell with a terminal in a pod of the namespace
# reaches the database as Falco's alert, through falcosidekick (falco/,
# phase E3). The probe pod gets a new name each run: the same alert within
# ten minutes is stored once. Python gives kubectl the terminal it needs.
runtime_alert() {
  local pod before found=1
  pod="runtime-probe-$(date +%s)"
  before="$(sql "SELECT coalesce(max(id), 0) FROM security_events")"
  probe | jq --arg pod "$pod" '.metadata.name = $pod | .spec.containers[0].command = ["sleep", "120"]' |
    kubectl apply -f - >/dev/null || return 1
  if kubectl wait --namespace "$NAMESPACE" --for=condition=ready "pod/$pod" --timeout=60s >/dev/null &&
    python3 -c 'import pty, sys; sys.exit(pty.spawn(sys.argv[1:]) >> 8)' \
      kubectl exec -it --namespace "$NAMESPACE" "$pod" -- sh -c true >/dev/null; then
    for _ in $(seq 1 30); do
      if [[ "$(sql "SELECT count(*) FROM security_events WHERE id > $before AND source = 'falco' AND event_type = 'CONTAINER_SHELL_DETECTED' AND message LIKE '% of pod $pod %'")" == 1 ]]; then
        found=0
        break
      fi
      sleep 1
    done
  fi
  kubectl delete pod --namespace "$NAMESPACE" "$pod" --now >/dev/null
  return "$found"
}
check "a shell in a container is reported by Falco within 30 seconds" runtime_alert

# Tracing and metrics (observability/, phase E4), asked through the
# Kubernetes API's proxy to each service. The probe is an ingestion request
# with an unknown key, whose lookup is a query, and an email in its query
# string, which no span may keep.
service() { kubectl get --raw "/api/v1/namespaces/observability/services/$1/proxy/$2"; }
trace=""
traced() {
  local id search now key=sck_tracecheck_unknown
  id="$(curl -s -o /dev/null -D - -X POST -H "Authorization: Bearer $key" \
    -H 'Content-Type: application/json' -d '{}' "$URL/api/ingest/events?email=probe@example.com" |
    awk 'tolower($1) == "x-request-id:" { print $2 }' | tr -d '\r')"
  [[ -n "$id" ]] || return 1
  search="$(jq -rn --arg id "$id" '"{ .sentinelcore.request_id = \"\($id)\" }" | @uri')"
  for _ in $(seq 1 30); do
    now="$(date +%s)"
    trace="$(service tempo:3200 "api/search?q=$search&start=$((now - 300))&end=$((now + 60))" |
      jq -r '.traces[0].traceID // empty')"
    if [[ -n "$trace" ]]; then
      trace="$(service tempo:3200 "api/v2/traces/$trace")"
      # The key's lookup, as a span of the same trace.
      jq -e '[.trace.resourceSpans[].scopeSpans[].spans[].attributes[]? | select(.key == "db.statement")] | length > 0' \
        <<<"$trace" >/dev/null
      return
    fi
    sleep 1
  done
  return 1
}
check "a request is traced in Tempo within 30 seconds, with its SQL" traced
private() { [[ -n "$trace" ]] && ! grep -qiE 'probe@example\.com|probe%40example|email=' <<<"$trace"; }
check "the trace keeps no query string" private

scraped() {
  local pods up
  pods="$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=sentinelcore-backend \
    --field-selector=status.phase=Running -o name | wc -l)"
  up="$(service prometheus-server:80 api/v1/targets |
    jq '[.data.activeTargets[] | select(.labels.job == "sentinelcore-backend" and .health == "up")] | length')"
  ((pods > 0 && up == pods))
}
check "Prometheus scrapes every API pod, with the metrics token" scraped

# The SLO rules (observability/slo-rules.yaml): both groups loaded and every
# rule evaluated without an error, within a minute of a restart (they run
# every 30 s); then none of their alerts firing on a healthy cluster.
slo_rules() {
  local tries
  for tries in $(seq 12); do
    service prometheus-server:80 api/v1/rules | jq -e '
      [.data.groups[] | select(.name | startswith("sentinelcore-slo-"))] as $groups
      | ($groups | length) == 2
        and ([$groups[].rules[]] | length) > 0
        and all($groups[].rules[]; .health == "ok")' >/dev/null && return 0
    ((tries < 12)) && sleep 5
  done
  return 1
}
check "Prometheus evaluates the SLO rules" slo_rules

# The configuration Prometheus runs is the one its ConfigMap holds: its
# reloader applies a change (Argo CD's, on the GitOps cluster) without a
# restart, which needs Prometheus' lifecycle API.
config_loaded() {
  local wanted loaded
  wanted="$(kubectl get configmap prometheus-server -n observability -o jsonpath='{.data.prometheus\.yml}' |
    sed -n 's/^- job_name: //p' | sort)"
  loaded="$(service prometheus-server:80 api/v1/status/config | jq -r '.data.yaml' |
    sed -n 's/^- job_name: //p' | sort)"
  [[ -n "$wanted" && "$wanted" == "$loaded" ]]
}
check "Prometheus runs the configuration of its ConfigMap" config_loaded

# A rule can evaluate without an error and still match nothing (a label
# written differently): this run's own requests and Falco alert give the
# availability and freshness ratios a number.
measured() {
  service prometheus-server:80 "api/v1/query?query=$1" |
    jq -e '.data.result | length == 1 and (.[0].value[1] | test("^[0-9.e+-]+$"))' >/dev/null
}
slo_measured() {
  local tries
  for tries in $(seq 12); do
    measured sentinelcore:slo_availability_error_ratio:rate5m &&
      measured sentinelcore:slo_runtime_alert_late_ratio:rate1d && return 0
    ((tries < 12)) && sleep 5
  done
  return 1
}
check "the availability and freshness SLOs are measured" slo_measured

slo_quiet() {
  service prometheus-server:80 api/v1/alerts | jq -e '
    [.data.alerts[] | select(.state == "firing" and (.labels.alertname | startswith("SentinelCore")))]
    | length == 0' >/dev/null
}
check "no SLO alert is firing" slo_quiet

# Grafana answers its health check, but nothing else without a password:
# kubectl reports the 401 its proxy passes on as a request to sign in.
grafana_locked() {
  local answer
  service grafana:80 api/health >/dev/null || return 1
  answer="$(service grafana:80 api/search 2>&1)" && return 1
  grep -qF 'logged in' <<<"$answer"
}
check "Grafana refuses a request without its password" grafana_locked

# GitOps: Git is the only source. A change made by hand is reverted by
# Argo CD's self-heal within a minute (docs/07-gitops.md). The API is a
# Rollout there, with its canary (scripts/canary-check.sh).
if [[ "${CLUSTER:-}" == gitops ]]; then
  api_replicas() { kubectl get rollout.argoproj.io sentinelcore-backend -n "$NAMESPACE" -o jsonpath='{.spec.replicas}'; }
  self_healed() {
    local wanted
    wanted="$(api_replicas)"
    kubectl scale rollout.argoproj.io sentinelcore-backend -n "$NAMESPACE" --replicas=$((wanted + 1)) >/dev/null || return 1
    local tries
    for tries in $(seq 30); do
      [[ "$(api_replicas)" == "$wanted" ]] && return 0
      sleep 2
    done
    return 1
  }
  check "a change made by hand is reverted from Git" self_healed
  # shellcheck source=scripts/canary-check.sh
  source "$ROOT/scripts/canary-check.sh"
fi

if ((failed > 0)); then
  printf '%d check(s) failed\n' "$failed"
  exit 1
fi

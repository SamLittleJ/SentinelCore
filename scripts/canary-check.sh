# shellcheck shell=bash
# The canary's checks, sourced by scripts/cluster-check.sh on the GitOps
# cluster (CLUSTER=gitops), with its check(), sql(), in_pod(), reaches(),
# blocked() and postgresql_ip. See docs/07-gitops.md.
: "${postgresql_ip:?set by cluster-check.sh}"
#
# The drill: a copy of the API under its own name (sentinelcore-canary-drill),
# never behind the real Service, run by Argo Rollouts with the API's own
# AnalysisTemplate and shorter arguments. A harmless change must be
# promoted; a version on a database role without rights on the tables (ready,
# but answering 500) must be stopped, the previous version kept. Its metrics
# are renamed sentinelcore_drill_* (observability/prometheus.yaml), so its
# 500s never reach the SLOs. Everything it creates is removed at the end.

DRILL=sentinelcore-canary-drill
DRILL_ROLE=sentinelcore_drill
# How long a drill canary may take to be promoted or stopped: pods start,
# then one minute of traffic and two readings, the first at 90 seconds.
DRILL_SECONDS=300

rollout_field() { kubectl get rollout.argoproj.io "$1" -n "$NAMESPACE" -o jsonpath="$2"; }

api_rollout_healthy() {
  [[ "$(rollout_field sentinelcore-backend '{.status.phase}')" == Healthy &&
    "$(rollout_field sentinelcore-backend '{.spec.replicas}')" == 5 &&
    "$(rollout_field sentinelcore-backend '{.status.availableReplicas}')" == 5 ]]
}
check "the API is a Rollout, healthy, with five pods" api_rollout_healthy

# The canary Service reaches the current version only, and Argo CD leaves the
# hash Argo Rollouts put in its selector (deploy/templates/applications.yaml):
# without it, the analysis's traffic would go to every pod.
canary_service_selects_new_pods() {
  local hash
  hash="$(rollout_field sentinelcore-backend '{.status.currentPodHash}')"
  [[ -n "$hash" &&
    "$(kubectl get service sentinelcore-backend-canary -n "$NAMESPACE" \
      -o jsonpath='{.spec.selector.rollouts-pod-template-hash}')" == "$hash" &&
    "$(kubectl get application sentinelcore -n argocd -o jsonpath='{.status.sync.status}')" == Synced ]]
}
check "the canary Service selects the current version only, and Argo CD keeps it" canary_service_selects_new_pods

controller_pinned() {
  kubectl get deployment -n argo-rollouts argo-rollouts \
    -o jsonpath='{.spec.template.spec.containers[0].image}' |
    grep -qx 'quay.io/argoproj/argo-rollouts:v1.10.2@sha256:[0-9a-f]\{64\}'
}
check "Argo Rollouts runs the pinned version" controller_pinned

# ---- The drill -------------------------------------------------------------

# The writes the synthetic traffic must never cause: its own events (sign-in
# failures, ingestion refusals), key usage, audit records.
writes() {
  sql "SELECT (SELECT count(*) FROM security_events WHERE source = 'backend')
            || ':' || (SELECT count(*) FROM api_key_usage)
            || ':' || (SELECT count(*) FROM audit_logs)"
}

drill_cleanup() {
  kubectl delete rollout.argoproj.io "$DRILL" -n "$NAMESPACE" --ignore-not-found --wait=true >/dev/null 2>&1
  kubectl delete analysisrun.argoproj.io -n "$NAMESPACE" -l "app.kubernetes.io/name=$DRILL" --ignore-not-found >/dev/null 2>&1
  kubectl delete "service/$DRILL-canary" "secret/$DRILL" -n "$NAMESPACE" --ignore-not-found >/dev/null 2>&1
  sql "DROP ROLE IF EXISTS $DRILL_ROLE" >/dev/null 2>&1
}

# The drill's Rollout: the API's pod under the drill's name, on two pods; one
# canary step of half, then the analysis with the drill's arguments.
drill_manifest() {
  local image
  image="$(rollout_field sentinelcore-backend '{.spec.template.spec.containers[?(@.name=="backend")].image}')"
  kubectl get rollout.argoproj.io sentinelcore-backend -n "$NAMESPACE" -o json |
    jq --arg name "$DRILL" --arg image "$image" '
      {
        apiVersion: "argoproj.io/v1alpha1",
        kind: "Rollout",
        metadata: {name: $name, labels: {"app.kubernetes.io/name": $name}},
        spec: {
          replicas: 2,
          revisionHistoryLimit: 2,
          selector: {matchLabels: {"app.kubernetes.io/name": $name}},
          template: (.spec.template
            | .metadata.labels = {"app.kubernetes.io/name": $name}
            | .metadata.annotations = {"sentinelcore/drill": "first"}),
          strategy: {canary: {
            canaryService: ($name + "-canary"),
            steps: [
              {setWeight: 50},
              {analysis: {
                templates: [{templateName: "sentinelcore-canary"}],
                args: [
                  {name: "canary-hash", valueFrom: {podTemplateHashValue: "Latest"}},
                  {name: "image", value: $image},
                  {name: "workload", value: $name},
                  {name: "service", value: ($name + "-canary")},
                  {name: "metric-prefix", value: "sentinelcore_drill"},
                  {name: "traffic-seconds", value: "60"},
                  {name: "count", value: "2"}
                ]}}
            ]}}
        }
      }'
}

drill_service() {
  jq -n --arg name "$DRILL" '{
    apiVersion: "v1", kind: "Service",
    metadata: {name: ($name + "-canary"), labels: {"app.kubernetes.io/name": $name}},
    spec: {selector: {"app.kubernetes.io/name": $name},
           ports: [{name: "http", port: 8000, targetPort: "http"}]}}'
}

# wait_drill <phase>: until the drill's Rollout reports it, for its newest
# template; a stopped canary reports Degraded.
wait_drill() {

  for _ in $(seq $((DRILL_SECONDS / 5))); do
    [[ "$(rollout_field "$DRILL" '{.status.phase}')" == "$1" &&
      "$(rollout_field "$DRILL" '{.status.observedGeneration}')" == "$(rollout_field "$DRILL" '{.metadata.generation}')" ]] && return 0
    sleep 5
  done
  return 1
}

stable_hash() { rollout_field "$DRILL" '{.status.stableRS}'; }
current_hash() { rollout_field "$DRILL" '{.status.currentPodHash}'; }

# The real Service never has a drill pod behind it, watched while the drill
# runs.
real_service_clean=1
watch_real_service() {
  kubectl get endpointslices -n "$NAMESPACE" -l kubernetes.io/service-name=sentinelcore-backend \
    -o jsonpath='{range .items[*].endpoints[*]}{.targetRef.name}{"\n"}{end}' |
    grep -q "^$DRILL-" && real_service_clean=0
  return 0
}

drill_setup() {
  local password
  password="$(openssl rand -hex 24)"
  # A role that may sign in and read the catalog, so readiness passes, but
  # holds no right on any table: every request that reads one fails.
  # Through stdin, so the password is in no command line.
  printf "CREATE ROLE %s LOGIN PASSWORD '%s';\n" "$DRILL_ROLE" "$password" |
    kubectl exec -i --namespace "$NAMESPACE" sentinelcore-postgresql-0 -- \
      psql -U sentinelcore -d sentinelcore -q -v ON_ERROR_STOP=1 >/dev/null || return 1
  printf 'DATABASE_URL=postgresql+psycopg://%s:%s@sentinelcore-postgresql:5432/sentinelcore\n' \
    "$DRILL_ROLE" "$password" |
    kubectl create secret generic "$DRILL" -n "$NAMESPACE" --from-env-file=/dev/stdin >/dev/null || return 1
  drill_service | kubectl apply -n "$NAMESPACE" -f - >/dev/null || return 1
  drill_manifest | kubectl apply -n "$NAMESPACE" -f - >/dev/null || return 1
  wait_drill Healthy
}

drill_promoted() {
  local before
  before="$(stable_hash)"
  kubectl patch rollout.argoproj.io "$DRILL" -n "$NAMESPACE" --type merge \
    -p '{"spec":{"template":{"metadata":{"annotations":{"sentinelcore/drill":"harmless change"}}}}}' >/dev/null || return 1
  watch_real_service
  wait_drill Healthy || return 1
  watch_real_service
  [[ "$(stable_hash)" != "$before" && "$(stable_hash)" == "$(current_hash)" ]]
}

drill_stopped() {
  local before
  before="$(stable_hash)"
  # The same image, on the role without rights: env wins over envFrom.
  kubectl get rollout.argoproj.io "$DRILL" -n "$NAMESPACE" -o json |
    jq --arg secret "$DRILL" '
      .spec.template.spec.containers |= map(if .name == "backend" then
        .env += [{name: "DATABASE_URL", valueFrom: {secretKeyRef: {name: $secret, key: "DATABASE_URL"}}}]
        else . end)' |
    kubectl replace -n "$NAMESPACE" -f - >/dev/null 2>&1 || return 1
  watch_real_service
  wait_drill Degraded || return 1
  watch_real_service
  # Stopped by its analysis, the previous version still whole.
  [[ "$(rollout_field "$DRILL" '{.status.abort}')" == true &&
    "$(stable_hash)" == "$before" &&
    "$(rollout_field "$DRILL" '{.status.availableReplicas}')" == 2 ]] || return 1
  kubectl get analysisrun.argoproj.io -n "$NAMESPACE" -o json |
    jq -e --arg name "$DRILL" '[.items[] | select(.metadata.ownerReferences[0].name == $name)
      | select(.status.phase == "Failed")] | length >= 1' >/dev/null
}

drill_cleanup
writes_before="$(writes 2>/dev/null)"
check "the canary drill starts on its own role and Services" drill_setup
check "a harmless change is promoted by the analysis" drill_promoted
check "a version that answers 500 is stopped, the previous one kept" drill_stopped
drill_real_service_untouched() { ((real_service_clean == 1)); }
check "the real Service never had a drill pod behind it" drill_real_service_untouched
no_writes() { [[ -n "$writes_before" && "$(writes)" == "$writes_before" ]]; }
check "the synthetic traffic wrote no event, key usage or audit record" no_writes
drill_cleanup
drill_gone() {
  ! kubectl get rollout.argoproj.io "$DRILL" -n "$NAMESPACE" >/dev/null 2>&1 &&
    ! kubectl get secret "$DRILL" -n "$NAMESPACE" >/dev/null 2>&1 &&
    [[ "$(sql "SELECT count(*) FROM pg_roles WHERE rolname = '$DRILL_ROLE'")" == 0 ]]
}
check "the drill leaves nothing behind" drill_gone

# ---- Network -----------------------------------------------------------------

# A pod like the analysis's traffic Job, that waits: the image and hardening
# of the API's pod, the traffic's label, no Secret.
traffic_probe() {
  kubectl get rollout.argoproj.io sentinelcore-backend -n "$NAMESPACE" -o json |
    jq '{
      apiVersion: "v1", kind: "Pod",
      metadata: {name: "canary-traffic-probe", labels: {"app.kubernetes.io/name": "sentinelcore-canary-traffic"}},
      spec: (.spec.template.spec
        | .containers |= map(select(.name == "backend")
            | {name: "backend", image, securityContext, resources,
               command: ["sleep", "300"]})
        | del(.volumes) | .restartPolicy = "Never")}'
}
traffic_probe_up() {
  traffic_probe | kubectl apply -n "$NAMESPACE" -f - >/dev/null &&
    kubectl wait --for=condition=Ready pod/canary-traffic-probe -n "$NAMESPACE" --timeout=120s >/dev/null
}
check "a pod like the canary's traffic is admitted" traffic_probe_up
api_ip="$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=sentinelcore-backend -o jsonpath='{.items[0].status.podIP}')"
check "the canary's traffic reaches the API's canary Service" \
  reaches pod/canary-traffic-probe backend sentinelcore-backend-canary 8000
check "the canary's traffic cannot reach the database" \
  blocked pod/canary-traffic-probe backend "$postgresql_ip" 5432
check "the canary's traffic cannot reach the internet" \
  blocked pod/canary-traffic-probe backend 1.1.1.1 443
kubectl delete pod canary-traffic-probe -n "$NAMESPACE" --ignore-not-found --wait=false >/dev/null 2>&1

# Argo Rollouts' namespace: a pod there with the controller's label reaches
# Prometheus, which the analysis queries, and nothing of the application.
rollouts_probe_up() {
  kubectl run rollouts-probe -n argo-rollouts --restart=Never \
    --labels=app.kubernetes.io/name=argo-rollouts \
    --image="$(kubectl get statefulset sentinelcore-postgresql -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].image}')" \
    --command -- sleep 300 >/dev/null &&
    kubectl wait --for=condition=Ready pod/rollouts-probe -n argo-rollouts --timeout=120s >/dev/null
}
in_rollouts_probe() { kubectl exec -n argo-rollouts rollouts-probe -- timeout 3 bash -c "</dev/tcp/$1/$2"; }
check "a probe in Argo Rollouts' namespace starts" rollouts_probe_up
check "Argo Rollouts reaches Prometheus" in_rollouts_probe prometheus-server.observability.svc.cluster.local 80
rollouts_blocked() { ! in_rollouts_probe "$@"; }
check "Argo Rollouts cannot reach the API" rollouts_blocked "$api_ip" 8000
check "Argo Rollouts cannot reach the internet" rollouts_blocked 1.1.1.1 443
kubectl delete pod rollouts-probe -n argo-rollouts --ignore-not-found --wait=false >/dev/null 2>&1

# shellcheck shell=bash
# The previews' checks, sourced by scripts/cluster-check.sh on the GitOps
# cluster (CLUSTER=gitops), with its check(), probe(), admit(), refused(),
# postgresql_ip, backend_ip and backend (the API's pod). See docs/07-gitops.md, Previews.
: "${postgresql_ip:?set by cluster-check.sh}" "${backend_ip:?set by cluster-check.sh}" "${backend:?set by cluster-check.sh}"
#
# The drill: preview-0, made from the ApplicationSets' own templates as if
# pull request 0 were open at the revision the cluster reads, with main's
# signed images (deploy/images.yaml) instead of a pull request's, since none
# need exist. Nothing here asks GitHub. It must become synced and healthy
# with its Secrets and owner, keep its Secrets when their Job runs again,
# stay apart from sentinelcore on the network, and disappear entirely, its
# namespace too, when its applications are deleted.

PREVIEW=preview-0
# Kyverno checks each new image online, and the application waits for its
# base: a few minutes on kind.
PREVIEW_SECONDS=900

in_preview() { kubectl exec --namespace "$PREVIEW" "$1" -c "$2" -- sh -c "$3"; }
preview_sql() {
  kubectl exec --namespace "$PREVIEW" sentinelcore-postgresql-0 -- \
    psql -U sentinelcore -d sentinelcore_demo -tAc "$1"
}

appset_controller_pinned() {
  kubectl get deployment argocd-applicationset-controller -n argocd \
    -o jsonpath='{.status.readyReplicas} {.spec.template.spec.containers[0].image}' |
    grep -qx '1 quay.io/argoproj/argocd:v[0-9.]*@sha256:[0-9a-f]\{64\}'
}
check "the ApplicationSet controller runs, pinned by digest" appset_controller_pinned

appsets_present() {
  kubectl get applicationset preview-base preview -n argocd >/dev/null &&
    [[ "$(kubectl get appproject previews -n argocd -o jsonpath='{.spec.clusterResourceWhitelist}')" == '[]' ]]
}
check "the previews' ApplicationSets exist, their project with no cluster resources" appsets_present

preview_cleanup() {
  kubectl delete application "$PREVIEW" "$PREVIEW-base" -n argocd --ignore-not-found --wait=true --timeout=300s >/dev/null 2>&1
  kubectl delete namespace "$PREVIEW" --ignore-not-found --wait=true --timeout=300s >/dev/null 2>&1
}

# application_for <ApplicationSet> <head commit>: the Application one of the
# ApplicationSets would make for pull request 0 at that commit.
application_for() {
  local tag
  tag="$(sed -n 's/^  tag: "\(.*\)"$/\1/p' "$ROOT/deploy/images.yaml")"
  kubectl get applicationset "$1" -n argocd -o json |
    jq --arg head "$2" --arg tag "$tag" \
      --arg backend "$(sed -n 's/^    backend: \(sha256:.*\)$/\1/p' "$ROOT/deploy/images.yaml")" \
      --arg console "$(sed -n 's/^    console: \(sha256:.*\)$/\1/p' "$ROOT/deploy/images.yaml")" '
      .spec.template
      | walk(if type == "string" then
          gsub("\\{\\{ \\.number \\}\\}"; "0") | gsub("\\{\\{ \\.head_sha \\}\\}"; $head)
        else . end)
      | {apiVersion: "argoproj.io/v1alpha1", kind: "Application",
         metadata: (.metadata + {namespace: "argocd"}), spec}
      | .spec.sources |= map(
          if .helm.parameters then
            .helm.parameters = [
              {name: "image.tag", value: $tag},
              {name: "image.digests.backend", value: $backend},
              {name: "image.digests.console", value: $console}]
          else . end)'
}

preview_ready() {
  local revision deadline=$((SECONDS + PREVIEW_SECONDS)) app
  revision="$(kubectl get application sentinelcore-root -n argocd -o jsonpath='{.spec.source.targetRevision}')"
  preview_cleanup
  application_for preview-base "$revision" | kubectl apply -f - >/dev/null || return 1
  application_for preview "$revision" | kubectl apply -f - >/dev/null || return 1
  for app in "$PREVIEW-base" "$PREVIEW"; do
    until [[ "$(kubectl get application "$app" -n argocd \
      -o jsonpath='{.status.sync.status}/{.status.health.status}')" == Synced/Healthy ]]; do
      ((SECONDS < deadline)) || return 1
      sleep 10
    done
  done
  # The owner comes after the sync (a PostSync hook), once Argo CD already
  # reports the application healthy.
  kubectl wait --for=condition=complete job/sentinelcore-owner -n "$PREVIEW" \
    --timeout="$((deadline - SECONDS))s" >/dev/null
}
check "the preview drill is synced and healthy, with its owner" preview_ready

preview_namespace_labelled() {
  [[ "$(kubectl get namespace "$PREVIEW" \
    -o jsonpath='{.metadata.labels.sentinelcore/preview} {.metadata.labels.pod-security\.kubernetes\.io/enforce}')" == "true restricted" ]]
}
check "its namespace is restricted and under the preview policies" preview_namespace_labelled

secrets_made() {
  kubectl get secret sentinelcore-postgresql sentinelcore-migrations sentinelcore-api preview-owner \
    -n "$PREVIEW" >/dev/null &&
    [[ "$(preview_sql "SELECT count(*) FROM users WHERE email = 'owner@sim.example.com'")" == 1 ]]
}
check "its Secrets and its owner were created" secrets_made

secret_versions() {
  kubectl get secrets -n "$PREVIEW" -l app.kubernetes.io/part-of=sentinelcore \
    -o jsonpath='{range .items[*]}{.metadata.name}={.metadata.resourceVersion} {end}'
}
# The Job again, as the next sync runs it: it must change nothing.
secrets_kept() {
  local before
  before="$(secret_versions)"
  kubectl get job preview-secrets -n "$PREVIEW" -o json |
    jq '{apiVersion, kind, metadata: {name: "preview-secrets-again", labels: .metadata.labels},
         spec: (.spec | del(.selector) | .template.metadata.labels |= with_entries(
           select(.key | test("controller-uid|job-name") | not)))}' |
    kubectl create -n "$PREVIEW" -f - >/dev/null &&
    kubectl wait --for=condition=complete job/preview-secrets-again -n "$PREVIEW" --timeout=180s >/dev/null &&
    kubectl logs job/preview-secrets-again -n "$PREVIEW" | grep -q 'are present' &&
    [[ "$(secret_versions)" == "$before" ]]
  local kept=$?
  kubectl delete job preview-secrets-again -n "$PREVIEW" --ignore-not-found >/dev/null 2>&1
  return "$kept"
}
check "the Secrets' Job, run again, keeps every Secret" secrets_kept

# Network: the preview's own flows only, nothing to or from sentinelcore.
preview_backend="$(kubectl get pods -n "$PREVIEW" -l app.kubernetes.io/name=sentinelcore-backend -o name 2>/dev/null | head -n 1)"
preview_console="$(kubectl get pods -n "$PREVIEW" -l app.kubernetes.io/name=sentinelcore-console -o name 2>/dev/null | head -n 1)"
preview_postgresql_ip="$(kubectl get pod sentinelcore-postgresql-0 -n "$PREVIEW" -o jsonpath='{.status.podIP}' 2>/dev/null)"
preview_reaches() {
  if [[ "$2" == console ]]; then
    in_preview "$1" "$2" "nc -z -w 3 $3 $4"
  else
    in_preview "$1" "$2" "timeout 3 bash -c '</dev/tcp/$3/$4'"
  fi
}
preview_blocked() { ! preview_reaches "$@"; }
check "the preview's console reaches its API" preview_reaches "$preview_console" console sentinelcore-backend 8000
check "the preview's API reaches its database" preview_reaches "$preview_backend" backend sentinelcore-postgresql 5432
check "the preview's API cannot reach sentinelcore's API" preview_blocked "$preview_backend" backend "$backend_ip" 8000
check "the preview's API cannot reach sentinelcore's database" preview_blocked "$preview_backend" backend "$postgresql_ip" 5432
# sentinelcore's console takes requests from anywhere: only the preview's own
# policies keep its pods from it.
console_ip="$(kubectl get service -n "$NAMESPACE" sentinelcore-console -o jsonpath='{.spec.clusterIP}')"
check "the preview's API cannot reach sentinelcore's console" preview_blocked "$preview_backend" backend "$console_ip" 8080
check "the preview's API cannot reach the internet" preview_blocked "$preview_backend" backend 1.1.1.1 443
check "sentinelcore's API cannot reach the preview's database" \
  blocked "$backend" backend "${preview_postgresql_ip:-0.0.0.0}" 5432

# Admission in the preview: the rules of sentinelcore, a token for the
# Secrets' Job alone, and our images only when signed.
preview_refused() {
  local answer
  answer="$(probe | jq --arg ns "$PREVIEW" ".metadata.namespace = \$ns | $2" | admit)" && return 1
  grep -qF "$1" <<<"$answer"
}
preview_admitted() { probe | jq --arg ns "$PREVIEW" ".metadata.namespace = \$ns | $1" | admit >/dev/null; }
check "a preview pod that meets every rule is admitted" preview_admitted '.'
check "a preview pod with a token, not the Secrets' Job, is refused" \
  preview_refused 'Only the preview-secrets Job' '.spec.automountServiceAccountToken = true'
check "the Secrets' account may mount its token" \
  preview_admitted '.spec.automountServiceAccountToken = true | .spec.serviceAccountName = "preview-secrets"'
check "a preview pod running as root is refused" preview_refused 'violates PodSecurity' '.spec.securityContext.runAsUser = 0'
check "a preview pod with a writable root file system is refused" preview_refused 'readOnlyRootFilesystem' \
  '.spec.containers[0].securityContext.readOnlyRootFilesystem = false'
check "an image of ours not signed is refused in a preview" preview_refused 'sentinelcore-preview-signatures' \
  ".spec.containers[0].image = \"ghcr.io/samlittlej/sentinelcore-backend@sha256:$(printf '0%.0s' {1..64})\""

# The Secrets' account reads and creates Secrets in its namespace, nothing
# else and nowhere else.
can_i() { kubectl auth can-i "$@" --as "system:serviceaccount:$PREVIEW:preview-secrets"; }
secrets_account_narrow() {
  can_i create secrets -n "$PREVIEW" >/dev/null &&
    ! can_i delete secrets -n "$PREVIEW" >/dev/null &&
    ! can_i list secrets -n "$PREVIEW" >/dev/null &&
    ! can_i get secrets -n sentinelcore >/dev/null &&
    ! can_i create pods -n "$PREVIEW" >/dev/null
}
check "the Secrets' account may only get and create Secrets in its namespace" secrets_account_narrow

# The applications only: Argo CD must delete the namespace itself.
preview_gone() {
  kubectl delete application "$PREVIEW" "$PREVIEW-base" -n argocd --wait=true --timeout=300s >/dev/null 2>&1
  kubectl wait --for=delete "namespace/$PREVIEW" --timeout=300s >/dev/null 2>&1
  ! kubectl get namespace "$PREVIEW" >/dev/null 2>&1 &&
    ! kubectl get application "$PREVIEW" "$PREVIEW-base" -n argocd >/dev/null 2>&1
}
check "deleting the preview's applications deletes its namespace" preview_gone
preview_cleanup

#!/usr/bin/env bash
# The kind cluster's backups (docs/06-backups.md).
#
#   backup.sh backup   a dump now, from the nightly CronJob, waited for
#   backup.sh check    the newest dump restored into a database of its own
#                      and compared with the live one; exits with 1 on any
#                      problem. The restored database and the Job are
#                      removed afterwards, whatever happened.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATH="$("$ROOT/scripts/tools.sh" kubectl):$PATH"
export KUBECONFIG="$ROOT/.kind/kubeconfig"
NAMESPACE=sentinelcore
RESTORED=sentinelcore_restore_check
CHECK_JOB=sentinelcore-backup-check
# A dump older than this means the CronJob has stopped: a day, and margin.
MAX_AGE_HOURS=26

if [[ ! -f "$KUBECONFIG" ]]; then
  echo "No cluster: run \`make up\` first." >&2
  exit 1
fi

k() { kubectl --namespace "$NAMESPACE" "$@"; }

# wait_job <name> <seconds>: 0 once it succeeded, 1 once it failed or ran out of time.
wait_job() {
  local deadline=$((SECONDS + $2)) status
  while ((SECONDS < deadline)); do
    status="$(k get job "$1" -o jsonpath='{.status.succeeded}/{.status.failed}')"
    [[ "$status" == 1/* ]] && return 0
    [[ "$status" == */[1-9]* ]] && return 1
    sleep 2
  done
  echo "The Job $1 did not finish within $2 seconds." >&2
  return 1
}

# logs <job> <container...>: each container's output, if it ran.
logs() {
  local job="$1" pod container
  shift
  pod="$(k get pods -l "job-name=$job" -o name | head -1)"
  [[ -n "$pod" ]] || return 0
  for container in "$@"; do
    k logs "$pod" -c "$container" 2>/dev/null || true
  done
}

# The manual backup's Job, deleted on the way out.
MANUAL_JOB="sentinelcore-backup-manual-$(date -u +%Y%m%d%H%M%S)"

backup() {
  trap 'k delete job "$MANUAL_JOB" --ignore-not-found --wait=false >/dev/null' EXIT
  k create job "$MANUAL_JOB" --from=cronjob/sentinelcore-backup >/dev/null
  local status=0
  wait_job "$MANUAL_JOB" 300 || status=$?
  logs "$MANUAL_JOB" backup
  return "$status"
}

cleanup() {
  k delete job "$CHECK_JOB" --ignore-not-found --wait=true >/dev/null 2>&1 || true
  k exec sentinelcore-postgresql-0 -c postgresql -- \
    dropdb -U sentinelcore --if-exists --force "$RESTORED" >/dev/null 2>&1 || true
}

# The check's Job: PostgreSQL's own image verifies and restores the newest
# dump (an init container), then the backend image compares the copy with
# the live database, both as the owner of the tables. Images and the API's
# settings are taken from what runs now.
check_job() {
  local postgres backend env
  postgres="$(k get statefulset sentinelcore-postgresql -o jsonpath='{.spec.template.spec.containers[0].image}')"
  backend="$(k get deployment sentinelcore-backend -o jsonpath='{.spec.template.spec.containers[?(@.name=="backend")].image}')"
  env="$(k get deployment sentinelcore-backend -o json |
    jq '[.spec.template.spec.containers[] | select(.name == "backend") | .env // [] | .[] | select(has("value"))]')"
  jq -n --arg postgres "$postgres" --arg backend "$backend" --argjson env "$env" \
    --arg restored "$RESTORED" --arg max_age "$MAX_AGE_HOURS" --arg name "$CHECK_JOB" '
  def hardened: {
    allowPrivilegeEscalation: false,
    readOnlyRootFilesystem: true,
    capabilities: {drop: ["ALL"]}
  };
  def resources: {
    requests: {cpu: "50m", memory: "128Mi"},
    limits: {cpu: "500m", memory: "512Mi"}
  };
  {
    apiVersion: "batch/v1",
    kind: "Job",
    metadata: {name: $name, labels: {"app.kubernetes.io/name": "sentinelcore-backup-check", "app.kubernetes.io/part-of": "sentinelcore"}},
    spec: {
      backoffLimit: 0,
      activeDeadlineSeconds: 600,
      template: {
        metadata: {labels: {"app.kubernetes.io/name": "sentinelcore-backup-check", "app.kubernetes.io/part-of": "sentinelcore"}},
        spec: {
          restartPolicy: "Never",
          serviceAccountName: "sentinelcore-postgresql",
          automountServiceAccountToken: false,
          securityContext: {runAsNonRoot: true, fsGroup: 999, fsGroupChangePolicy: "OnRootMismatch", seccompProfile: {type: "RuntimeDefault"}},
          initContainers: [{
            name: "restore",
            image: $postgres,
            securityContext: (hardened + {runAsUser: 999, runAsGroup: 999}),
            resources: resources,
            env: [
              {name: "PGHOST", value: "sentinelcore-postgresql"},
              {name: "PGUSER", value: "sentinelcore"},
              {name: "PGDATABASE", value: "sentinelcore"},
              {name: "RESTORED", value: $restored},
              {name: "MAX_AGE_HOURS", value: $max_age}
            ],
            command: ["bash", "-euo", "pipefail", "-c", "
umask 077
printf \"*:*:*:*:%s\\n\" \"$(cat /run/secrets/postgresql/password)\" >/tmp/pgpass
export PGPASSFILE=/tmp/pgpass
cd /backups
newest=\"$(ls -1 sentinelcore-*.dump 2>/dev/null | sort | tail -1 || true)\"
if [[ -z \"$newest\" ]]; then
  echo \"PROBLEM no backup yet: run make backup\"
  exit 1
fi
echo \"Newest dump: $newest ($(stat -c %s \"$newest\") bytes)\"
if ! sha256sum --check --status \"$newest.sha256\"; then
  echo \"PROBLEM $newest does not match its SHA-256\"
  exit 1
fi
age=$(( $(date +%s) - $(stat -c %Y \"$newest\") ))
if (( age > MAX_AGE_HOURS * 3600 )); then
  echo \"PROBLEM the newest dump is $(( age / 3600 )) hours old, more than $MAX_AGE_HOURS\"
  exit 1
fi
echo \"Checksum matches; $(( age / 60 )) minutes old\"
createdb \"$RESTORED\"
start=$(date +%s)
pg_restore --exit-on-error --dbname=\"$RESTORED\" \"$newest\"
echo \"Restored into $RESTORED in $(( $(date +%s) - start )) s\"
"],
            volumeMounts: [
              {name: "backups", mountPath: "/backups", readOnly: true},
              {name: "password", mountPath: "/run/secrets/postgresql", readOnly: true},
              {name: "tmp", mountPath: "/tmp"}
            ]
          }],
          containers: [{
            name: "compare",
            image: $backend,
            securityContext: (hardened + {runAsUser: 10001, runAsGroup: 10001}),
            resources: resources,
            command: ["python", "-m", "app.cli", "compare-restore", "--restored-database", $restored],
            env: $env,
            envFrom: [{secretRef: {name: "sentinelcore-api"}}, {secretRef: {name: "sentinelcore-migrations"}}],
            volumeMounts: [{name: "tmp", mountPath: "/tmp"}]
          }],
          volumes: [
            {name: "backups", persistentVolumeClaim: {claimName: "sentinelcore-backups", readOnly: true}},
            {name: "password", secret: {secretName: "sentinelcore-postgresql", defaultMode: 288, items: [{key: "password", path: "password"}]}},
            {name: "tmp", emptyDir: {}}
          ]
        }
      }
    }
  }'
}

check() {
  cleanup
  trap cleanup EXIT
  check_job | k apply -f - >/dev/null
  local status=0
  wait_job "$CHECK_JOB" 600 || status=$?
  logs "$CHECK_JOB" restore compare
  if ((status == 0)); then
    echo "Backup check passed."
  else
    echo "Backup check FAILED." >&2
  fi
  return "$status"
}

case "${1:-}" in
  backup) backup ;;
  check) check ;;
  *)
    echo "usage: $0 backup|check" >&2
    exit 2
    ;;
esac

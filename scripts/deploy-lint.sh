#!/usr/bin/env bash
# `make deploy-lint`: the deployment's files checked without a cluster, the
# same way locally (`make verify`) and in CI. Uses the pinned tools of
# scripts/tools.sh. Exits with 1 at the first check that fails.
#
#   both charts, with helm lint, warnings included
#   every rendered manifest, with kubeconform, against Kubernetes 1.35's schemas
#   both Dockerfiles, with hadolint, warnings included
#   every script, with shellcheck
#   every action of the workflows, pinned to a full commit SHA
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATH="$("$ROOT/scripts/tools.sh"):$PATH"
cd "$ROOT"

# The cluster's version (kind/cluster.yaml), and its schemas pinned to one
# commit of the repository kubeconform reads them from, so a change there
# cannot change the result.
KUBERNETES_VERSION=1.35.0
SCHEMAS=https://raw.githubusercontent.com/yannh/kubernetes-json-schema/93153a1458e24e93f386c50f9980d584fcba574b
# Any tag: the charts require one, and the check is of the manifests' shape.
TAG=deploy-lint

echo "== helm lint"
helm lint --strict charts/postgresql
helm lint --strict charts/sentinelcore --set image.tag="$TAG"

echo "== kubeconform"
# Every resource needs a schema: there are no custom resources, so one
# without a schema is a mistake.
{
  helm template postgresql charts/postgresql
  helm template sentinelcore charts/sentinelcore --set image.tag="$TAG"
} | kubeconform -strict -summary -kubernetes-version "$KUBERNETES_VERSION" \
  -schema-location "$SCHEMAS/{{.NormalizedKubernetesVersion}}-standalone{{.StrictSuffix}}/{{.ResourceKind}}{{.KindSuffix}}.json"

echo "== hadolint"
hadolint --failure-threshold warning backend/Dockerfile frontend/Dockerfile

echo "== shellcheck"
shellcheck scripts/*.sh

echo "== pinned actions"
# A tag can be moved to other code; a commit SHA cannot. The version stays in
# a comment, for people and for Dependabot.
if grep -nE '^\s*(-\s*)?uses:' .github/workflows/*.yml | grep -vE 'uses:\s*[^@[:space:]]+@[0-9a-f]{40} # v[0-9.]+$'; then
  echo "actions not pinned to a commit SHA with its version in a comment" >&2
  exit 1
fi

echo "deploy files clean"

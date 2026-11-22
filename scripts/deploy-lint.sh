#!/usr/bin/env bash
# `make deploy-lint`: the deployment's files checked without a cluster, the
# same way locally (`make verify`) and in CI. Uses the pinned tools of
# scripts/tools.sh. Exits with 1 at the first check that fails.
#
#   both charts, with helm lint, warnings included
#   every rendered manifest, with kubeconform, against Kubernetes 1.35's schemas
#   both Dockerfiles, with hadolint, warnings included
#   every script, with shellcheck
#   the SLO rules, with promtool: their syntax, then their unit tests
#   the GitOps applications (deploy/): Kyverno and its policies sync first
#   the Terraform of the GitOps cluster (gitops/): formatted and valid
#   every action of the workflows, pinned to a full commit SHA
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATH="$("$ROOT/scripts/tools.sh"):$PATH"
cd "$ROOT"

# The cluster's version (kind/kind-config.yaml), and its schemas pinned to one
# commit of the repository kubeconform reads them from, so a change there
# cannot change the result.
KUBERNETES_VERSION=1.35.0
SCHEMAS=https://raw.githubusercontent.com/yannh/kubernetes-json-schema/93153a1458e24e93f386c50f9980d584fcba574b
# Any tag: the charts require one, and the check is of the manifests' shape.
TAG=deploy-lint

echo "== helm lint"
helm lint --strict charts/postgresql
helm lint --strict charts/sentinelcore --set image.tag="$TAG"
helm lint --strict charts/observability-config 2>/dev/null

echo "== kubeconform"
# Every resource needs a schema: there are no custom resources, so one
# without a schema is a mistake.
{
  helm template postgresql charts/postgresql
  helm template sentinelcore charts/sentinelcore --set image.tag="$TAG"
  # As `make up FROM=registry` installs it: our images by digest.
  helm template sentinelcore charts/sentinelcore --set image.tag="$TAG" \
    --set image.backend=ghcr.io/samlittlej/sentinelcore-backend \
    --set image.digests.backend="sha256:$(printf '0%.0s' {1..64})"
  helm template observability-config charts/observability-config 2>/dev/null
  for file in network-policies/*.yaml observability/rbac.yaml gitops/network-policy.yaml; do
    echo ---
    cat "$file"
  done
} | kubeconform -strict -summary -kubernetes-version "$KUBERNETES_VERSION" \
  -schema-location "$SCHEMAS/{{.NormalizedKubernetesVersion}}-standalone{{.StrictSuffix}}/{{.ResourceKind}}{{.KindSuffix}}.json"
# As the GitOps cluster runs it (deploy/): the API a Rollout, with its canary.
# Argo Rollouts' own kinds have no schema here; Argo CD checks them.
helm template sentinelcore charts/sentinelcore -f deploy/images.yaml -f deploy/sentinelcore.yaml |
  kubeconform -strict -summary -kubernetes-version "$KUBERNETES_VERSION" -skip Rollout,AnalysisTemplate \
    -schema-location "$SCHEMAS/{{.NormalizedKubernetesVersion}}-standalone{{.StrictSuffix}}/{{.ResourceKind}}{{.KindSuffix}}.json"

echo "== hadolint"
hadolint --failure-threshold warning backend/Dockerfile frontend/Dockerfile

echo "== shellcheck"
shellcheck scripts/*.sh

echo "== promtool"
promtool check rules observability/slo-rules.yaml
promtool test rules observability/slo-rules.test.yaml

echo "== gitops"
# Every pod is admitted by Kyverno's rules only if Kyverno and the policies
# are in place first: their waves come before every other application's.
helm lint --strict deploy
helm template root deploy | "$ROOT/.tools/scanners/bin/python" -c '
import sys, yaml
apps = {a["metadata"]["name"]: int(a["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"])
        for a in yaml.safe_load_all(sys.stdin) if a}
first = max(apps[n] for n in ("kyverno", "kyverno-policies"))
late = sorted(n for n, w in apps.items() if n not in ("kyverno", "kyverno-policies", "network-policies") and w <= first)
if apps["kyverno"] >= apps["kyverno-policies"] or late:
    sys.exit(f"Kyverno must sync first, then its policies, then the rest; too early: {late}")
if apps["argo-rollouts"] >= apps["sentinelcore"]:
    sys.exit("Argo Rollouts must sync before the application, whose API is a Rollout")
print(f"{len(apps)} applications, Kyverno and its policies first, Argo Rollouts before the API")'
# The canary's analysis (charts/sentinelcore/templates/canary.yaml): every
# Prometheus query reads the new pods only, and a reading of their request
# count requires a minimum, so an analysis without traffic cannot pass.
helm template sentinelcore charts/sentinelcore -f deploy/images.yaml -f deploy/sentinelcore.yaml |
  "$ROOT/.tools/scanners/bin/python" -c '
import re, sys, yaml
docs = [d for d in yaml.safe_load_all(sys.stdin) if d]
template = next(d for d in docs if d["kind"] == "AnalysisTemplate")
queries = {m["name"]: m for m in template["spec"]["metrics"] if "prometheus" in m.get("provider", {})}
for name, metric in queries.items():
    selectors = re.findall(r"_http_requests_total\{(.*?)\"\}", metric["provider"]["prometheus"]["query"])
    if not selectors or any("-{{args.canary-hash}}-" not in selector for selector in selectors):
        sys.exit(f"the {name} query does not read the new pods only")
if queries.get("requests", {}).get("successCondition") != "result[0] >= {{args.min-requests}}":
    sys.exit("the analysis does not require a minimum of requests")
if int(next(a["value"] for a in template["spec"]["args"] if a["name"] == "min-requests")) < 1:
    sys.exit("the minimum of requests must be at least one")
rollout = next(d for d in docs if d["kind"] == "Rollout")
steps = rollout["spec"]["strategy"]["canary"]["steps"]
if not all("analysis" in after for before, after in zip(steps, steps[1:]) if "setWeight" in before):
    sys.exit("every canary step must be followed by an analysis")
print(f"canary: {len(queries)} queries on the new pods, a minimum of requests, {len(steps) // 2} analysed steps")'
terraform -chdir=gitops fmt -check -diff
tf_data="$(mktemp -d)"
TF_DATA_DIR="$tf_data" terraform -chdir=gitops init -backend=false -input=false >/dev/null
TF_DATA_DIR="$tf_data" terraform -chdir=gitops validate -no-color
rm -rf "$tf_data"

echo "== pinned actions"
# A tag can be moved to other code; a commit SHA cannot. The version stays in
# a comment, for people and for Dependabot.
if grep -nE '^\s*(-\s*)?uses:' .github/workflows/*.yml | grep -vE 'uses:\s*[^@[:space:]]+@[0-9a-f]{40} # v[0-9.]+$'; then
  echo "actions not pinned to a commit SHA with its version in a comment" >&2
  exit 1
fi

echo "deploy files clean"

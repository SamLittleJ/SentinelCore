#!/usr/bin/env bash
# The tools of the cluster and of the checks, at pinned versions, in .tools/
# (git-ignored): the versions `make up` and CI were tested with, whatever the
# system has installed. Every download is checked against the SHA-256 written
# here, so a changed file is refused. Takes optional tool names (default:
# all). Prints the directory, for PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/.tools"

KIND_VERSION=v0.31.0
KIND_SHA256=eb244cbafcc157dff60cf68693c14c9a75c4e6e6fedaf9cd71c58117cb93e3fa
HELM_VERSION=v3.19.0
HELM_SHA256=a7f81ce08007091b86d8bd696eb4d86b8d0f2e1b9f6c714be62f82f96a594496
# Within one minor version of the cluster's (kind/kind-config.yaml), as
# Kubernetes supports.
KUBECTL_VERSION=v1.35.7
KUBECTL_SHA256=12e97f9d23a9f6cbb87b89becd6bd291e1a858a3379a4e11e2c822c4c1530052
# The checks of `make deploy-lint`.
KUBECONFORM_VERSION=v0.8.0
KUBECONFORM_SHA256=9bc2bffbf71f261128533edaf912153948b7ff238f9a531ae6d34466ec287883
HADOLINT_VERSION=v2.15.1
HADOLINT_SHA256=c7187db94eeeeca956519a6af171adc31453941a1e777961f6e680f697c8c507
SHELLCHECK_VERSION=v0.11.0
SHELLCHECK_SHA256=b7af85e41cc99489dcc21d66c6d5f3685138f06d34651e6d34b42ec6d54fe6f6

# The secret scan of `make verify` and CI.
GITLEAKS_VERSION=v8.30.1
GITLEAKS_SHA256=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
# The image scan of `make scan-images` and CI: Syft writes the SBOM, Grype
# scans it.
SYFT_VERSION=v1.54.1
SYFT_SHA256=c069905b391cc4c20a5ba65ad5c10be2a7ba074f8ea6ad203e24d14e303dad47
GRYPE_VERSION=v0.120.1
GRYPE_SHA256=0a9ee97ef5ae2ee953b0a80098105052e846cdbe319a57d808b519c33cd1343d
# The image signatures of CI and `make verify-images`: keyless, through
# Sigstore. 3.1.3, not 3.1.4: that one was five days old, inside the
# seven-day cooldown.
COSIGN_VERSION=v3.1.3
COSIGN_SHA256=4629c757b7618056f8ddd7e2625ae9fdd94c0372a65049520bc7d9df9efc7f71
# The admission policies' engine (kyverno/), as its Helm chart. 3.9.1, not
# 3.9.2: that one was six days old, inside the seven-day cooldown.
KYVERNO_CHART_VERSION=3.9.1
KYVERNO_CHART_SHA256=7b7fe51a431b5b133b0ce7eb9dcb222b6a37fb967c163223cf480054ad14d752
# Runtime detection (falco/), as its Helm chart, with falcosidekick. 9.2.1
# (Falco 0.45.1), not 9.2.2: that one was four days old, inside the cooldown.
FALCO_CHART_VERSION=9.2.1
FALCO_CHART_SHA256=726c1fe08c3fd3e2789d4072b34f9eee94ecccad734fee471cc7546124570c6c
# Tracing and metrics (observability/), as the official charts. The newest
# releases older than seven days on 2026-11-06. Tempo and Grafana moved to
# the grafana-community repository; 3.2.1 is Tempo 3.1.1.
OTEL_COLLECTOR_CHART_VERSION=0.178.1
OTEL_COLLECTOR_CHART_SHA256=6df4120a2ae29f1bf89536eb4b527424f4522b66946857bce41ecc8fe8e9ef40
TEMPO_CHART_VERSION=3.2.1
TEMPO_CHART_SHA256=3389c896bd3c8f2a54f054ac00eb1881c34eff2b8e53053e3ad42c9f394925c3
PROMETHEUS_CHART_VERSION=29.40.0
PROMETHEUS_CHART_SHA256=8af68f8b0b43fb11d32ca679574be129b0c947dcb5c9e270ef8e677a2e7f26ac
GRAFANA_CHART_VERSION=14.2.0
GRAFANA_CHART_SHA256=fd442e214d854ff514d64fb75f7f32f179b9e9a6a53bc3323aca7c5748ff188f
# GitOps on kind (`make gitops-up`, gitops/): Terraform creates the cluster
# and installs Argo CD from its chart, both pinned; Terraform's providers are
# pinned in gitops/.terraform.lock.hcl. Argo CD 10.18.0 (Argo CD v3.6.1), not
# 10.18.1 or 10.18.2: those were inside the seven-day cooldown.
TERRAFORM_VERSION=v1.17.2
TERRAFORM_SHA256=e6f16b2f0b137ee5729caa8c4e79a3bae4ee261acd198a1fcfa8584a6296605b
ARGOCD_CHART_VERSION=10.18.0
ARGOCD_CHART_SHA256=9785aff67197402aab26d7ab3928ac8e611c292dacdee47f0e8ded16c2cd5a47
# The kubectl plugin of Argo Rollouts (the API's canary on the GitOps
# cluster, deploy/): the controller's release, v1.10.2, whose chart
# deploy/values.yaml pins by digest. The SHA-256 is the release's own.
ARGO_ROLLOUTS_VERSION=v1.10.2
ARGO_ROLLOUTS_SHA256=355d62379d787a778f92903ce0b2fc1c1f4999d790d829370b6f1854a55f1cf9
# promtool, which checks and tests the SLO rules (observability/slo-rules.yaml)
# in `make deploy-lint`: from the release of the cluster's Prometheus server
# (observability/prometheus.yaml), so both read the rules the same way.
PROMTOOL_VERSION=v3.15.1
PROMTOOL_SHA256=6a726885328ad9efebbf36e876ce2fb6225468a71fd1e7ce3ba666d5f4d97a84

# fetch <url> <sha256> <file>: downloads next to the file, then moves it in
# place only once the checksum matches.
fetch() {
  local partial="$3.partial"
  curl -fsSL --proto '=https' --tlsv1.2 -o "$partial" "$1"
  if ! echo "$2  $partial" | sha256sum --check --quiet --status; then
    rm -f "$partial"
    echo "tools: the checksum of $1 does not match; refused." >&2
    exit 1
  fi
  mv "$partial" "$3"
}

# installed <name> <version>: the tool is there, at this version.
installed() { [[ -x "$TOOLS/$1" && -f "$TOOLS/$1.version" && "$(cat "$TOOLS/$1.version")" == "$2" ]]; }

# wanted <name>: all tools, or one of the names given.
wanted() {
  [[ ${#requested[@]} -eq 0 || " ${requested[*]} " == *" $1 "* ]]
}

requested=("$@")
for tool in "${requested[@]}"; do
  case "$tool" in
    kind|kubectl|helm|kubeconform|hadolint|shellcheck|gitleaks|syft|grype|cosign|kyverno|falco|otel-collector|tempo|prometheus|grafana|promtool|terraform|argo-cd|kubectl-argo-rollouts|scanners) ;;
    *) echo "tools: unknown tool: $tool" >&2; exit 1 ;;
  esac
done

mkdir -p "$TOOLS"

if wanted kind && ! installed kind "$KIND_VERSION"; then
  fetch "https://github.com/kubernetes-sigs/kind/releases/download/$KIND_VERSION/kind-linux-amd64" \
    "$KIND_SHA256" "$TOOLS/kind"
  chmod 755 "$TOOLS/kind"
  echo "$KIND_VERSION" >"$TOOLS/kind.version"
fi

if wanted kubectl && ! installed kubectl "$KUBECTL_VERSION"; then
  fetch "https://dl.k8s.io/release/$KUBECTL_VERSION/bin/linux/amd64/kubectl" \
    "$KUBECTL_SHA256" "$TOOLS/kubectl"
  chmod 755 "$TOOLS/kubectl"
  echo "$KUBECTL_VERSION" >"$TOOLS/kubectl.version"
fi

if wanted helm && ! installed helm "$HELM_VERSION"; then
  archive="$TOOLS/helm.tar.gz"
  fetch "https://get.helm.sh/helm-$HELM_VERSION-linux-amd64.tar.gz" "$HELM_SHA256" "$archive"
  tar -xzf "$archive" -C "$TOOLS" --strip-components=1 linux-amd64/helm
  rm -f "$archive"
  chmod 755 "$TOOLS/helm"
  echo "$HELM_VERSION" >"$TOOLS/helm.version"
fi

if wanted kubeconform && ! installed kubeconform "$KUBECONFORM_VERSION"; then
  archive="$TOOLS/kubeconform.tar.gz"
  fetch "https://github.com/yannh/kubeconform/releases/download/$KUBECONFORM_VERSION/kubeconform-linux-amd64.tar.gz" \
    "$KUBECONFORM_SHA256" "$archive"
  tar -xzf "$archive" -C "$TOOLS" kubeconform
  rm -f "$archive"
  chmod 755 "$TOOLS/kubeconform"
  echo "$KUBECONFORM_VERSION" >"$TOOLS/kubeconform.version"
fi

if wanted hadolint && ! installed hadolint "$HADOLINT_VERSION"; then
  fetch "https://github.com/hadolint/hadolint/releases/download/$HADOLINT_VERSION/hadolint-linux-x86_64" \
    "$HADOLINT_SHA256" "$TOOLS/hadolint"
  chmod 755 "$TOOLS/hadolint"
  echo "$HADOLINT_VERSION" >"$TOOLS/hadolint.version"
fi

if wanted shellcheck && ! installed shellcheck "$SHELLCHECK_VERSION"; then
  archive="$TOOLS/shellcheck.tar.gz"
  fetch "https://github.com/koalaman/shellcheck/releases/download/$SHELLCHECK_VERSION/shellcheck-$SHELLCHECK_VERSION.linux.x86_64.tar.gz" \
    "$SHELLCHECK_SHA256" "$archive"
  tar -xzf "$archive" -C "$TOOLS" --strip-components=1 "shellcheck-$SHELLCHECK_VERSION/shellcheck"
  rm -f "$archive"
  chmod 755 "$TOOLS/shellcheck"
  echo "$SHELLCHECK_VERSION" >"$TOOLS/shellcheck.version"
fi

if wanted gitleaks && ! installed gitleaks "$GITLEAKS_VERSION"; then
  archive="$TOOLS/gitleaks.tar.gz"
  fetch "https://github.com/gitleaks/gitleaks/releases/download/$GITLEAKS_VERSION/gitleaks_${GITLEAKS_VERSION#v}_linux_x64.tar.gz" \
    "$GITLEAKS_SHA256" "$archive"
  tar -xzf "$archive" -C "$TOOLS" gitleaks
  rm -f "$archive"
  chmod 755 "$TOOLS/gitleaks"
  echo "$GITLEAKS_VERSION" >"$TOOLS/gitleaks.version"
fi

# anchore <name> <version> <sha256>: Syft and Grype, released the same way.
anchore() {
  if wanted "$1" && ! installed "$1" "$2"; then
    archive="$TOOLS/$1.tar.gz"
    fetch "https://github.com/anchore/$1/releases/download/$2/${1}_${2#v}_linux_amd64.tar.gz" \
      "$3" "$archive"
    tar -xzf "$archive" -C "$TOOLS" "$1"
    rm -f "$archive"
    chmod 755 "$TOOLS/$1"
    echo "$2" >"$TOOLS/$1.version"
  fi
}
anchore syft "$SYFT_VERSION" "$SYFT_SHA256"
anchore grype "$GRYPE_VERSION" "$GRYPE_SHA256"

if wanted cosign && ! installed cosign "$COSIGN_VERSION"; then
  fetch "https://github.com/sigstore/cosign/releases/download/$COSIGN_VERSION/cosign-linux-amd64" \
    "$COSIGN_SHA256" "$TOOLS/cosign"
  chmod 755 "$TOOLS/cosign"
  echo "$COSIGN_VERSION" >"$TOOLS/cosign.version"
fi

if wanted kubectl-argo-rollouts && ! installed kubectl-argo-rollouts "$ARGO_ROLLOUTS_VERSION"; then
  fetch "https://github.com/argoproj/argo-rollouts/releases/download/$ARGO_ROLLOUTS_VERSION/kubectl-argo-rollouts-linux-amd64" \
    "$ARGO_ROLLOUTS_SHA256" "$TOOLS/kubectl-argo-rollouts"
  chmod 755 "$TOOLS/kubectl-argo-rollouts"
  echo "$ARGO_ROLLOUTS_VERSION" >"$TOOLS/kubectl-argo-rollouts.version"
fi

if wanted terraform && ! installed terraform "$TERRAFORM_VERSION"; then
  archive="$TOOLS/terraform.zip"
  fetch "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION#v}/terraform_${TERRAFORM_VERSION#v}_linux_amd64.zip" \
    "$TERRAFORM_SHA256" "$archive"
  unzip -o -q "$archive" terraform -d "$TOOLS"
  rm -f "$archive"
  chmod 755 "$TOOLS/terraform"
  echo "$TERRAFORM_VERSION" >"$TOOLS/terraform.version"
fi

if wanted promtool && ! installed promtool "$PROMTOOL_VERSION"; then
  archive="$TOOLS/promtool.tar.gz"
  fetch "https://github.com/prometheus/prometheus/releases/download/$PROMTOOL_VERSION/prometheus-${PROMTOOL_VERSION#v}.linux-amd64.tar.gz" \
    "$PROMTOOL_SHA256" "$archive"
  tar -xzf "$archive" -C "$TOOLS" --strip-components=1 "prometheus-${PROMTOOL_VERSION#v}.linux-amd64/promtool"
  rm -f "$archive"
  chmod 755 "$TOOLS/promtool"
  echo "$PROMTOOL_VERSION" >"$TOOLS/promtool.version"
fi

# A chart, not a binary: helm installs .tools/kyverno.tgz.
if wanted kyverno && [[ ! -f "$TOOLS/kyverno.tgz" || "$(cat "$TOOLS/kyverno.tgz.version" 2>/dev/null)" != "$KYVERNO_CHART_VERSION" ]]; then
  fetch "https://kyverno.github.io/kyverno/kyverno-$KYVERNO_CHART_VERSION.tgz" \
    "$KYVERNO_CHART_SHA256" "$TOOLS/kyverno.tgz"
  echo "$KYVERNO_CHART_VERSION" >"$TOOLS/kyverno.tgz.version"
fi

# A chart, not a binary: helm installs .tools/falco.tgz.
if wanted falco && [[ ! -f "$TOOLS/falco.tgz" || "$(cat "$TOOLS/falco.tgz.version" 2>/dev/null)" != "$FALCO_CHART_VERSION" ]]; then
  fetch "https://github.com/falcosecurity/charts/releases/download/falco-$FALCO_CHART_VERSION/falco-$FALCO_CHART_VERSION.tgz" \
    "$FALCO_CHART_SHA256" "$TOOLS/falco.tgz"
  echo "$FALCO_CHART_VERSION" >"$TOOLS/falco.tgz.version"
fi

# chart <name> <version> <sha256> <url>: the observability charts, the same way.
chart() {
  if wanted "$1" && [[ ! -f "$TOOLS/$1.tgz" || "$(cat "$TOOLS/$1.tgz.version" 2>/dev/null)" != "$2" ]]; then
    fetch "$4" "$3" "$TOOLS/$1.tgz"
    echo "$2" >"$TOOLS/$1.tgz.version"
  fi
}
chart otel-collector "$OTEL_COLLECTOR_CHART_VERSION" "$OTEL_COLLECTOR_CHART_SHA256" \
  "https://github.com/open-telemetry/opentelemetry-helm-charts/releases/download/opentelemetry-collector-$OTEL_COLLECTOR_CHART_VERSION/opentelemetry-collector-$OTEL_COLLECTOR_CHART_VERSION.tgz"
chart tempo "$TEMPO_CHART_VERSION" "$TEMPO_CHART_SHA256" \
  "https://github.com/grafana-community/helm-charts/releases/download/tempo-$TEMPO_CHART_VERSION/tempo-$TEMPO_CHART_VERSION.tgz"
chart prometheus "$PROMETHEUS_CHART_VERSION" "$PROMETHEUS_CHART_SHA256" \
  "https://github.com/prometheus-community/helm-charts/releases/download/prometheus-$PROMETHEUS_CHART_VERSION/prometheus-$PROMETHEUS_CHART_VERSION.tgz"
chart argo-cd "$ARGOCD_CHART_VERSION" "$ARGOCD_CHART_SHA256" \
  "https://github.com/argoproj/argo-helm/releases/download/argo-cd-$ARGOCD_CHART_VERSION/argo-cd-$ARGOCD_CHART_VERSION.tgz"
chart grafana "$GRAFANA_CHART_VERSION" "$GRAFANA_CHART_SHA256" \
  "https://github.com/grafana-community/helm-charts/releases/download/grafana-$GRAFANA_CHART_VERSION/grafana-$GRAFANA_CHART_VERSION.tgz"

# The Python scanners of `make scan` (Checkov, pip-audit), in an environment
# of their own: every file is checked against the hashes of
# security/scanners.lock, and only wheels are accepted, so nothing unpinned
# is built or fetched on the side. Reinstalled whenever the lock changes.
LOCK="$ROOT/security/scanners.lock"
if wanted scanners; then
  lock_sum="$(sha256sum "$LOCK" | cut -d' ' -f1)"
  if [[ ! -x "$TOOLS/scanners/bin/checkov" || "$(cat "$TOOLS/scanners.version" 2>/dev/null)" != "$lock_sum" ]]; then
    rm -rf "$TOOLS/scanners"
    python3 -m venv "$TOOLS/scanners"
    "$TOOLS/scanners/bin/pip" install --quiet --disable-pip-version-check \
      --require-hashes --only-binary :all: -r "$LOCK" >&2
    echo "$lock_sum" >"$TOOLS/scanners.version"
  fi
fi

echo "$TOOLS"

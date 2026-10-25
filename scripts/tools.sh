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
# Within one minor version of the cluster's (kind/cluster.yaml), as
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
    kind|kubectl|helm|kubeconform|hadolint|shellcheck|gitleaks|syft|grype|cosign|scanners) ;;
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

#!/usr/bin/env bash
# The cluster's tools, at pinned versions, in .tools/ (git-ignored): the
# versions `make up` was tested with, whatever the system has installed.
# Every download is checked against the SHA-256 written here, so a changed
# file is refused. Prints the directory, for PATH.
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

mkdir -p "$TOOLS"

if ! installed kind "$KIND_VERSION"; then
  fetch "https://github.com/kubernetes-sigs/kind/releases/download/$KIND_VERSION/kind-linux-amd64" \
    "$KIND_SHA256" "$TOOLS/kind"
  chmod 755 "$TOOLS/kind"
  echo "$KIND_VERSION" >"$TOOLS/kind.version"
fi

if ! installed kubectl "$KUBECTL_VERSION"; then
  fetch "https://dl.k8s.io/release/$KUBECTL_VERSION/bin/linux/amd64/kubectl" \
    "$KUBECTL_SHA256" "$TOOLS/kubectl"
  chmod 755 "$TOOLS/kubectl"
  echo "$KUBECTL_VERSION" >"$TOOLS/kubectl.version"
fi

if ! installed helm "$HELM_VERSION"; then
  archive="$TOOLS/helm.tar.gz"
  fetch "https://get.helm.sh/helm-$HELM_VERSION-linux-amd64.tar.gz" "$HELM_SHA256" "$archive"
  tar -xzf "$archive" -C "$TOOLS" --strip-components=1 linux-amd64/helm
  rm -f "$archive"
  chmod 755 "$TOOLS/helm"
  echo "$HELM_VERSION" >"$TOOLS/helm.version"
fi

echo "$TOOLS"

#!/usr/bin/env bash
# `make verify-images` and `make up FROM=registry`: the published images of
# one commit of main, checked before anything uses them. Each tag is
# resolved to a digest once; from then on only that digest is used:
#
#   1. cosign: a keyless signature made by images-ci.yml, on a push to
#      refs/heads/main, at exactly this commit;
#   2. gh: the SLSA v1 build provenance of that workflow, ref and commit,
#      built on a GitHub-hosted runner;
#   3. gh: the SPDX SBOM attestation, with the same identity.
#
# The identities are exact strings, not patterns. Only when both images
# pass are their digests written to .kind/verified-images, for `make up
# FROM=registry`; any failure stops before that, so nothing unverified is
# named there. In the cluster, Kyverno checks the same identity again
# (kyverno/signatures.yaml).
#
#   scripts/verify-images.sh <revision>
#
# Needs gh, signed in (`gh auth login`, or GH_TOKEN in CI): it refuses to
# run without a GitHub token, even for the registry's bundles.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO=SamLittleJ/SentinelCore
REGISTRY=ghcr.io/samlittlej
WORKFLOW=.github/workflows/images-ci.yml
REF=refs/heads/main
ISSUER=https://token.actions.githubusercontent.com
IDENTITY="https://github.com/$REPO/$WORKFLOW@$REF"
PROVENANCE=https://slsa.dev/provenance/v1
# The SPDX version Syft writes; actions/attest names the predicate after it.
SBOM=https://spdx.dev/Document/v2.3
# What the registry may answer for a tag: an image index or a manifest.
ACCEPT='application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json'

fail() {
  echo "verify-images: $*" >&2
  exit 1
}

revision="${1:-}"
[[ $revision =~ ^[0-9a-f]{12}$ ]] ||
  fail "expected a 12-character commit, got '$revision'. A tree with changes has no published images: commit first, or pass REVISION=<commit of main>."
commit="$(git -C "$ROOT" rev-parse --verify --quiet "$revision^{commit}")" ||
  fail "$revision is not a commit of this repository; run git fetch, or pick another REVISION."
command -v gh >/dev/null || fail "gh (GitHub CLI) is needed for the attestations."
TOOLS="$("$ROOT/scripts/tools.sh" cosign)"

# digest_of <name>: the digest the tag points to now, from GHCR's API with
# an anonymous pull token (the packages are public).
digest_of() {
  local repository="samlittlej/sentinelcore-$1" token headers status
  token="$(curl -fsS --proto '=https' "https://ghcr.io/token?scope=repository:$repository:pull" | jq -r .token)"
  headers="$(curl -sS --proto '=https' -I -H "Authorization: Bearer $token" -H "Accept: $ACCEPT" \
    "https://ghcr.io/v2/$repository/manifests/$revision" | tr -d '\r')"
  status="$(head -1 <<<"$headers" | awk '{print $2}')"
  if [[ $status == 404 ]]; then
    fail "sentinelcore-$1:$revision is not published (only commits of main are); run \`make up\` to build it locally."
  fi
  [[ $status == 200 ]] || fail "GHCR answered $status for sentinelcore-$1:$revision."
  awk -F': ' 'tolower($1) == "docker-content-digest" {print $2}' <<<"$headers" | grep -E '^sha256:[0-9a-f]{64}$' ||
    fail "GHCR gave no digest for sentinelcore-$1:$revision."
}

verified=()
for name in backend console; do
  image="$REGISTRY/sentinelcore-$name"
  digest="$(digest_of "$name")"
  echo "== $name: $image@$digest"

  "$TOOLS/cosign" verify "$image@$digest" \
    --certificate-identity "$IDENTITY" \
    --certificate-oidc-issuer "$ISSUER" \
    --certificate-github-workflow-repository "$REPO" \
    --certificate-github-workflow-ref "$REF" \
    --certificate-github-workflow-sha "$commit" \
    --certificate-github-workflow-trigger push >/dev/null ||
    fail "$name: no valid signature from $IDENTITY at $commit."
  echo "   signature: images-ci.yml on main, commit $revision"

  for predicate in "$PROVENANCE" "$SBOM"; do
    gh attestation verify "oci://$image@$digest" \
      --bundle-from-oci \
      --repo "$REPO" \
      --signer-workflow "$REPO/$WORKFLOW" \
      --source-ref "$REF" \
      --source-digest "$commit" \
      --deny-self-hosted-runners \
      --cert-oidc-issuer "$ISSUER" \
      --predicate-type "$predicate" >/dev/null ||
      fail "$name: no valid $predicate attestation from $WORKFLOW at $commit."
    echo "   attestation: $predicate"
  done
  verified+=("$name=$image@$digest")
done

# Both images passed: the cluster pulls them by these digests.
mkdir -p "$ROOT/.kind"
chmod 700 "$ROOT/.kind"
printf '%s\n' "revision=$revision" "${verified[@]}" >"$ROOT/.kind/verified-images"
echo "== recorded in .kind/verified-images"

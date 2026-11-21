#!/usr/bin/env bash
# `make deploy-pr REVISION=<commit>`: proposes deploying a commit of main to
# the GitOps cluster (docs/07-gitops.md). Checks the commit's published
# images (signature, provenance, SBOM) with scripts/verify-images.sh, writes
# their digests to deploy/images.yaml on a branch deploy/<commit>, made from
# origin/main in a worktree of its own, and opens the pull request with your
# `gh` login, so the checks main requires run on it. Your working tree and
# branch are left as they are.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REVISION="${REVISION:-}"

if [[ ! "$REVISION" =~ ^[0-9a-f]{12}$ ]]; then
  echo "usage: make deploy-pr REVISION=<12-character commit of main>" >&2
  exit 2
fi

cd "$ROOT"
git fetch --quiet origin main
if ! git merge-base --is-ancestor "$REVISION" origin/main; then
  echo "$REVISION is not on origin/main: only main's images are signed for deployment." >&2
  exit 1
fi

# The images, checked; their digests come from what was checked.
"$ROOT/scripts/verify-images.sh" "$REVISION"
digest() { sed -n "s/^$1=.*@//p" "$ROOT/.kind/verified-images"; }
backend="$(digest backend)"
console="$(digest console)"
[[ "$backend" == sha256:* && "$console" == sha256:* ]] || {
  echo "No verified digests for $REVISION." >&2
  exit 1
}

branch="deploy/$REVISION"
worktree="$(mktemp -d)"
cleanup() { git worktree remove --force "$worktree" >/dev/null 2>&1 || true; rm -rf "$worktree"; }
trap cleanup EXIT
git worktree add --quiet -b "$branch" "$worktree" origin/main

# Only the three values change; the file's comments stay.
sed -i \
  -e "s/^  tag: \"[0-9a-f]\{12\}\"$/  tag: \"$REVISION\"/" \
  -e "s/^    backend: sha256:[0-9a-f]\{64\}$/    backend: $backend/" \
  -e "s/^    console: sha256:[0-9a-f]\{64\}$/    console: $console/" \
  "$worktree/deploy/images.yaml"
if git -C "$worktree" diff --quiet; then
  echo "deploy/images.yaml already names $REVISION's images; nothing to deploy."
  exit 0
fi

git -C "$worktree" commit --quiet -am "Deploy $REVISION to the GitOps cluster"
git -C "$worktree" push --quiet -u origin "$branch"
(cd "$worktree" && gh pr create --base main --head "$branch" \
  --title "Deploy $REVISION to the GitOps cluster" \
  --body "Deploys the images CI published and signed from \`$REVISION\` on \`main\`, checked by \`scripts/verify-images.sh\` (signature by \`images-ci.yml\` on \`main\`, SLSA provenance, SPDX SBOM):

- \`ghcr.io/samlittlej/sentinelcore-backend@$backend\`
- \`ghcr.io/samlittlej/sentinelcore-console@$console\`

Merging it deploys them: Argo CD reads \`main\` (docs/07-gitops.md), and Kyverno checks the signature again before each pod starts.")

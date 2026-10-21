#!/usr/bin/env bash
# `make scan`: the dependencies and the deployment's configuration checked
# for known flaws, locally (`make verify`) and in CI. Every finding fails
# unless security/exceptions.yaml covers it with a reason and an expiry date
# (scripts/scan_gate.py).
#
#   pip-audit: the backend's requirements.lock, against the PyPI advisories
#   Checkov:   both rendered charts, both Dockerfiles, every workflow
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$("$ROOT/scripts/tools.sh" helm scanners)"
PATH="$TOOLS:$PATH"
SCANNERS="$TOOLS/scanners/bin"
cd "$ROOT"

# Checkov skips files under hidden directories, so the reports and the
# rendered charts go to a temporary directory outside the repository.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
failed=0

echo "== pip-audit"
# No installation: the pinned, hashed lock is read as it is. The exit code
# is the gate's to give; a run that fails leaves no report and fails there.
"$SCANNERS/pip-audit" -r backend/requirements.lock --require-hashes --disable-pip \
  --progress-spinner off -f json -o "$WORK/pip-audit.json" || true
"$SCANNERS/python" scripts/scan_gate.py pip-audit "$WORK/pip-audit.json" || failed=1

echo "== checkov"
helm template postgresql charts/postgresql >"$WORK/postgresql.yaml"
helm template sentinelcore charts/sentinelcore --set image.tag=scan >"$WORK/sentinelcore.yaml"
files=()
for file in "$WORK/postgresql.yaml" "$WORK/sentinelcore.yaml" backend/Dockerfile frontend/Dockerfile .github/workflows/*.yml; do
  files+=(-f "$file")
done
"$SCANNERS/checkov" --quiet --compact -o json --framework kubernetes dockerfile github_actions \
  "${files[@]}" >"$WORK/checkov.json" || true
"$SCANNERS/python" scripts/scan_gate.py checkov "$WORK/checkov.json" || failed=1

if [ "$failed" -ne 0 ]; then
  echo "scan failed"
  exit 1
fi
echo "no open findings"

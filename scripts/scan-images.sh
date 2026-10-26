#!/usr/bin/env bash
# `make scan-images`: an SBOM of each image, then its known vulnerabilities.
# Syft lists every package of the image in an SPDX JSON SBOM; Grype scans
# that SBOM, so what is scanned is what gets published and attested. Critical
# and high vulnerabilities with a fixed version fail, unless
# security/exceptions.yaml covers them (scripts/scan_gate.py).
#
#   scripts/scan-images.sh [image...]
#
# Without arguments, the images `make images` built for $REVISION. The SBOMs
# and reports go to .scan/ (git-ignored), for CI to keep.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$("$ROOT/scripts/tools.sh" syft grype scanners)"
OUT="$ROOT/.scan"
cd "$ROOT"

if [ "$#" -eq 0 ]; then
  : "${REVISION:?set REVISION, or name the images}"
  set -- "sentinelcore-backend:$REVISION" "sentinelcore-console:$REVISION"
fi

rm -rf "$OUT"
mkdir -p "$OUT"
reports=()
for image in "$@"; do
  # backend or console, whatever the registry, tag or digest.
  name="${image##*/}"
  name="${name%%[:@]*}"
  name="${name#sentinelcore-}"
  echo "== $name ($image)"
  # From the local Docker daemon: CI pulls a published image first. No
  # --quiet: it also hid the error of a failed run (#54).
  "$TOOLS/syft" scan "docker:$image" -o "spdx-json=$OUT/sbom-$name.spdx.json"
  # A fresh vulnerability database, checked by Grype, on every run.
  "$TOOLS/grype" "sbom:$OUT/sbom-$name.spdx.json" -o json --file "$OUT/grype-$name.json"
  reports+=("$name=$OUT/grype-$name.json")
done

status=0
"$TOOLS/scanners/bin/python" scripts/scan_gate.py grype "${reports[@]}" | tee "$OUT/gate.txt" || status=$?

# In CI, the counts and any finding go to the job's summary page.
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### Image scan"
    echo
    echo '```'
    cat "$OUT/gate.txt"
    echo '```'
  } >>"$GITHUB_STEP_SUMMARY"
fi
exit "$status"

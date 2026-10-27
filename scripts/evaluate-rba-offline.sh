#!/usr/bin/env bash
# `make evaluate-rba-offline`: B2, the Freeman et al. risk score, and the
# rules under other thresholds, on the sample of `make evaluate-rba`
# (backend/simulator/rba_offline.py), written to
# docs/evaluation/independent-rba-baselines.md and .json. No database or
# server: the rules are replayed in Python, and nothing is written unless the
# replay reproduces docs/evaluation/independent-rba.json. About 15 minutes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/backend/.venv/bin/python"
# As the Makefile names builds: the commit, and -dirty for uncommitted work.
REVISION="${REVISION:-$(git -C "$ROOT" rev-parse --short=12 HEAD)$(test -z "$(git -C "$ROOT" status --porcelain)" || echo -dirty)}"

fail() {
  echo "make evaluate-rba-offline: $*" >&2
  exit 1
}

# shellcheck source=scripts/rba-data.sh
. "$ROOT/scripts/rba-data.sh"

[ -x "$PYTHON" ] || fail "set up the backend first: see 'Run the backend' in README.md."

echo "==> The data set"
rba_data || fail "the data set's checksum does not match; refused."

echo "==> The baselines and thresholds (about 10 minutes)"
(cd "$ROOT/backend" && "$PYTHON" -m simulator.rba_offline \
  --data "$DATA_DIR/rba-dataset.csv" --revision "$REVISION" \
  --out "$ROOT/docs/evaluation" "$@")

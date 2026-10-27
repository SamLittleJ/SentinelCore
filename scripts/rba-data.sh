# Sourced by scripts/evaluate-rba.sh and evaluate-rba-offline.sh: the RBA
# login data set (1.1 GB, CC BY 4.0), downloaded once into .rba/, ignored by
# git, and refused unless its SHA-256 matches.
# shellcheck shell=bash
DATA_DIR="$ROOT/.rba"
DATA_URL=https://zenodo.org/api/records/6782156/files/rba-dataset.zip/content
DATA_SHA256=ca1d974e97aebfb30878a613f4ca5c793860a98ba2acb5185c9bc610d7432a33

# rba_data: $DATA_DIR/rba-dataset.csv, from the checked archive; fails when
# the archive's checksum does not match.
rba_data() {
  mkdir -p "$DATA_DIR"
  [ -f "$DATA_DIR/rba-dataset.csv" ] && return 0
  if ! echo "$DATA_SHA256  $DATA_DIR/rba-dataset.zip" | sha256sum --check --quiet --status 2>/dev/null; then
    curl -fL --proto '=https' --tlsv1.2 -o "$DATA_DIR/rba-dataset.zip.partial" "$DATA_URL"
    mv "$DATA_DIR/rba-dataset.zip.partial" "$DATA_DIR/rba-dataset.zip"
  fi
  echo "$DATA_SHA256  $DATA_DIR/rba-dataset.zip" | sha256sum --check --quiet || return 1
  unzip -o -q "$DATA_DIR/rba-dataset.zip" rba-dataset.csv -d "$DATA_DIR"
}

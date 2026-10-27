#!/usr/bin/env bash
# `make evaluate-rba`: the detection rules measured on the RBA login data set
# (backend/simulator/rba.py), written to docs/evaluation/independent-rba.md
# and .json. Takes about an hour.
#
# The data set (1.1 GB, CC BY 4.0) is downloaded once into .rba/, ignored by
# git, and refused unless its SHA-256 matches. A fresh sentinelcore_eval
# database and a backend on 127.0.0.1:8000 run only for the evaluation and
# are removed afterwards. The owner's password lives in this script only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT/.rba"
DATA_URL=https://zenodo.org/api/records/6782156/files/rba-dataset.zip/content
DATA_SHA256=ca1d974e97aebfb30878a613f4ca5c793860a98ba2acb5185c9bc610d7432a33
DATABASE=sentinelcore_eval
POSTGRES=sentinelcore-postgres
OWNER_EMAIL=owner@eval.example.com
PYTHON="$ROOT/backend/.venv/bin/python"
# The development credentials, which are public, as for `make demo`.
export MIGRATIONS_DATABASE_URL="postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/$DATABASE"
export DATABASE_URL="postgresql+psycopg://sentinelcore_app:sentinelcore_app@localhost:5432/$DATABASE"
# As the Makefile names builds: the commit, and -dirty for uncommitted work.
REVISION="${REVISION:-$(git -C "$ROOT" rev-parse --short=12 HEAD)$(test -z "$(git -C "$ROOT" status --porcelain)" || echo -dirty)}"
export REVISION

fail() {
  echo "make evaluate-rba: $*" >&2
  exit 1
}

port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

command -v docker >/dev/null || fail "Docker is needed for PostgreSQL."
[ -x "$PYTHON" ] || fail "set up the backend first: see 'Run the backend' in README.md."
[ -f "$ROOT/backend/.env" ] || fail "create backend/.env first: cp backend/.env.example backend/.env"
port_in_use 8000 && fail "port 8000 is in use. Stop the development server or make demo first."

echo "==> The data set"
mkdir -p "$DATA_DIR"
if [ ! -f "$DATA_DIR/rba-dataset.csv" ]; then
  if ! echo "$DATA_SHA256  $DATA_DIR/rba-dataset.zip" | sha256sum --check --quiet --status 2>/dev/null; then
    curl -fL --proto '=https' --tlsv1.2 -o "$DATA_DIR/rba-dataset.zip.partial" "$DATA_URL"
    mv "$DATA_DIR/rba-dataset.zip.partial" "$DATA_DIR/rba-dataset.zip"
  fi
  echo "$DATA_SHA256  $DATA_DIR/rba-dataset.zip" | sha256sum --check --quiet ||
    fail "the data set's checksum does not match; refused."
  unzip -o -q "$DATA_DIR/rba-dataset.zip" rba-dataset.csv -d "$DATA_DIR"
fi

echo "==> PostgreSQL and a fresh $DATABASE database"
docker compose -f "$ROOT/docker-compose.yml" up -d postgres >/dev/null
for _ in $(seq 1 30); do
  docker exec "$POSTGRES" pg_isready -q -U sentinelcore && break
  sleep 1
done
drop_database() {
  docker exec "$POSTGRES" psql -q -U sentinelcore -d postgres \
    -c "DROP DATABASE IF EXISTS $DATABASE WITH (FORCE)"
}
drop_database
docker exec "$POSTGRES" psql -q -U sentinelcore -d postgres -c "CREATE DATABASE $DATABASE"
(cd "$ROOT/backend" && "$PYTHON" -m alembic upgrade head && "$PYTHON" -m app.cli grant-api-login)

OWNER_PASSWORD="$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe(18))")"
(cd "$ROOT/backend" && SENTINELCORE_OWNER_PASSWORD="$OWNER_PASSWORD" \
  "$PYTHON" -m app.cli create-owner --email "$OWNER_EMAIL" --username owner)

echo "==> The backend, on 127.0.0.1:8000"
# Millions of sign-ins go through one key, so its rate limit is raised for
# this server only.
(cd "$ROOT/backend" && INGEST_BURST_EVENTS=1000000 INGEST_EVENTS_PER_MINUTE=1000000 \
  exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning) \
  >"$DATA_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true; wait "$BACKEND_PID" 2>/dev/null || true; drop_database' EXIT
for _ in $(seq 1 30); do
  curl -sf http://127.0.0.1:8000/health >/dev/null && break
  kill -0 "$BACKEND_PID" 2>/dev/null || fail "the backend stopped; see .rba/backend.log"
  sleep 1
done
curl -sf http://127.0.0.1:8000/health >/dev/null || fail "the backend did not answer; see .rba/backend.log"

echo "==> The evaluation (about an hour)"
(cd "$ROOT/backend" && SENTINELCORE_OWNER_PASSWORD="$OWNER_PASSWORD" \
  "$PYTHON" -m simulator.rba --data "$DATA_DIR/rba-dataset.csv" \
  --owner-email "$OWNER_EMAIL" --out "$ROOT/docs/evaluation" "$@")

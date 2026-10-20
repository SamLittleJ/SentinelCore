#!/usr/bin/env bash
# `make demo`: a fresh demo database with ninety days of three synthetic
# organizations, then the backend and the frontend running on it until Ctrl+C.
#
# Everything stays on this machine: PostgreSQL from docker-compose.yml, the
# backend on 127.0.0.1:8000, the frontend on localhost:5173. The passwords are
# random, written only to .demo/ (the owner's to owner.txt, each admin's to
# <organization>-admin.txt; mode 600, ignored by git) and never printed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_DIR="$ROOT/.demo"
DATABASE=sentinelcore_demo
POSTGRES=sentinelcore-postgres
OWNER_EMAIL=owner@sim.example.com
PYTHON="$ROOT/backend/.venv/bin/python"
VITE="$ROOT/frontend/node_modules/.bin/vite"
# The development credentials, which are public: the owner of the tables from
# docker-compose.yml runs the migrations and moves the demo's alerts; the API
# signs in as its own role, which row-level security binds.
export MIGRATIONS_DATABASE_URL="postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/$DATABASE"
export DATABASE_URL="postgresql+psycopg://sentinelcore_app:sentinelcore_app@localhost:5432/$DATABASE"

fail() {
  echo "make demo: $*" >&2
  exit 1
}

port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

command -v docker >/dev/null || fail "Docker is needed for PostgreSQL."
[ -x "$PYTHON" ] || fail "set up the backend first: see 'Run the backend' in README.md."
[ -f "$ROOT/backend/.env" ] || fail "create backend/.env first: cp backend/.env.example backend/.env"
[ -x "$VITE" ] || fail "install the frontend first: (cd frontend && npm ci)"
for port in 8000 5173; do
  if port_in_use "$port"; then
    fail "port $port is in use. Stop the development servers first."
  fi
done

echo "==> PostgreSQL"
docker compose -f "$ROOT/docker-compose.yml" up -d postgres >/dev/null
for _ in $(seq 1 30); do
  docker exec "$POSTGRES" pg_isready -q -U sentinelcore && break
  sleep 1
done
docker exec "$POSTGRES" pg_isready -q -U sentinelcore || fail "PostgreSQL did not start."

echo "==> A fresh $DATABASE database"
docker exec "$POSTGRES" psql -q -U sentinelcore -d postgres \
  -c "DROP DATABASE IF EXISTS $DATABASE WITH (FORCE)" \
  -c "CREATE DATABASE $DATABASE"
(cd "$ROOT/backend" && "$PYTHON" -m alembic upgrade head && "$PYTHON" -m app.cli grant-api-login)

echo "==> The owner"
mkdir -p "$DEMO_DIR"
chmod 700 "$DEMO_DIR"
(
  umask 077
  "$PYTHON" -c "import secrets; print(secrets.token_urlsafe(18))" >"$DEMO_DIR/owner-password"
)
OWNER_PASSWORD="$(cat "$DEMO_DIR/owner-password")"
rm -f "$DEMO_DIR/owner-password"
(
  umask 077
  printf 'SentinelCore demo owner (local only)\nemail: %s\npassword: %s\n' \
    "$OWNER_EMAIL" "$OWNER_PASSWORD" >"$DEMO_DIR/owner.txt"
)
(cd "$ROOT/backend" && SENTINELCORE_OWNER_PASSWORD="$OWNER_PASSWORD" \
  "$PYTHON" -m app.cli create-owner --email "$OWNER_EMAIL" --username owner)

echo "==> The backend, on 127.0.0.1:8000"
# Every attacker of the demo signs in from this machine's one address, so the
# limit on failed sign-ins per address is raised for the demo's server only.
(cd "$ROOT/backend" && LOGIN_ADDRESS_BURST=1000 \
  exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000) \
  >"$DEMO_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
  curl -sf http://127.0.0.1:8000/health >/dev/null && break
  kill -0 "$BACKEND_PID" 2>/dev/null || fail "the backend stopped; see .demo/backend.log"
  sleep 1
done
curl -sf http://127.0.0.1:8000/health >/dev/null || fail "the backend did not answer; see .demo/backend.log"

echo "==> Ninety days of three synthetic organizations"
(cd "$ROOT/backend" && SENTINELCORE_OWNER_PASSWORD="$OWNER_PASSWORD" \
  "$PYTHON" -m simulator.demo --owner-email "$OWNER_EMAIL" --accounts-dir "$DEMO_DIR")
unset OWNER_PASSWORD

echo "==> The audit history's seal"
(cd "$ROOT/backend" && "$PYTHON" -m app.cli verify-audit-chain) || fail "the audit history does not verify"

cat <<INFO

SentinelCore demo: http://localhost:5173
Sign in as $OWNER_EMAIL; the password is in .demo/owner.txt.
The admins of Acme, Globex and Initech (suspended) are in .demo/*-admin.txt.
The data is synthetic. Ctrl+C stops the demo; 'make demo-clean' removes it.

INFO
"$VITE" "$ROOT/frontend" --port 5173 --strictPort

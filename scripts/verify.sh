#!/usr/bin/env bash
# `make verify`: every check that must pass before a commit, one line each.
# Full logs go to .verify/<check>.log (git-ignored).
#
# Needs: backend/.venv with the dev dependencies, frontend/node_modules, and
# Docker with the PostgreSQL of docker-compose.yml running. The backend tests
# run on Python 3.12 with the image's pinned dependencies, in a container.
#
# VERIFY_SKIP="pytest migrations" skips the named checks.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS="$ROOT/.verify"
BACKEND="$ROOT/backend"
PY="$BACKEND/.venv/bin"
POSTGRES=sentinelcore-postgres
PYTHON_IMAGE=python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
# What Gitleaks scans, one path per run.
GITLEAKS_PATHS=(backend frontend docs scripts infra charts kind security .github README.md SECURITY.md Makefile docker-compose.yml)

rm -rf "$LOGS"
mkdir -p "$LOGS"
failed=0

skipped() { [[ " ${VERIFY_SKIP:-} " == *" $1 "* ]]; }

# check <name> <summary command> -- <command...>: runs the command with its
# output in the log, then prints PASS with the summary's output, or FAIL with
# the log's last line.
check() {
  local name="$1" summary="$2"
  shift 3
  if skipped "$name"; then
    printf 'SKIP %s\n' "$name"
    return
  fi
  if (cd "$ROOT" && "$@") >"$LOGS/$name.log" 2>&1; then
    printf 'PASS %-12s %s\n' "$name" "$(eval "$summary" 2>/dev/null)"
  else
    printf 'FAIL %-12s %s (.verify/%s.log)\n' "$name" "$(last "$name" | cut -c1-100)" "$name"
    failed=$((failed + 1))
  fi
}

last() { grep -v '^\s*$' "$LOGS/$1.log" | tail -1; }

pytest_in_312() {
  # A copy without secrets or caches: SELinux keeps a container from reading
  # the repository itself, and the copy is relabelled instead.
  local copy result
  copy="$(mktemp -d)"
  (cd "$BACKEND" && tar --exclude=.env --exclude=.venv --exclude=__pycache__ \
    --exclude=.pytest_cache --exclude=.ruff_cache --exclude='*.egg-info' -cf - .) | tar -xf - -C "$copy"
  docker run --rm --network host -v "$copy:/src:Z" -w /src \
    -e TEST_DATABASE_URL=postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/sentinelcore_test \
    -e DATABASE_URL=postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/sentinelcore_test \
    -e SECRET_KEY=verify-secret-key-for-sentinelcore-minimum-32-bytes \
    -e PYTHONDONTWRITEBYTECODE=1 "$PYTHON_IMAGE" sh -c \
    "pip install -q --root-user-action=ignore --require-hashes -r requirements.lock \
     && pip install -q --root-user-action=ignore 'pytest>=9.0' 'httpx>=0.28' \
     && python -m pytest -q -p no:cacheprovider"
  result=$?
  rm -rf "$copy"
  return $result
}

lock_current() {
  local copy result
  copy="$(mktemp)"
  cp "$BACKEND/requirements.lock" "$copy"
  (cd "$BACKEND" && "$PY/uv" pip compile pyproject.toml --generate-hashes \
    --python-version 3.12 --python-platform x86_64-manylinux_2_28 \
    --no-header --quiet -o "$copy") && diff -u "$BACKEND/requirements.lock" "$copy"
  result=$?
  rm -f "$copy"
  return $result
}

migrations() {
  # Up, check, down one step, up again, on a database of its own. Both URLs
  # are set: migrations/env.py prefers MIGRATIONS_DATABASE_URL, which
  # backend/.env points at the development database.
  local db="verify_$$"
  local url="postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/$db"
  docker exec "$POSTGRES" psql -q -U sentinelcore -d postgres -c "CREATE DATABASE $db" || return 1
  local key
  key="$("$PY/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  (cd "$BACKEND" && export MIGRATIONS_DATABASE_URL="$url" DATABASE_URL="$url" AUDIT_CHAIN_KEY="$key" \
    && "$PY/alembic" upgrade head && "$PY/alembic" check \
    && "$PY/alembic" downgrade -1 && "$PY/alembic" upgrade head)
  local result=$?
  docker exec "$POSTGRES" psql -q -U sentinelcore -d postgres -c "DROP DATABASE $db WITH (FORCE)"
  return $result
}

gitleaks() {
  local bin target
  bin="$("$ROOT/scripts/tools.sh" gitleaks)/gitleaks"
  for target in "${GITLEAKS_PATHS[@]}"; do
    [ -e "$ROOT/$target" ] || continue
    echo "== $target"
    "$bin" dir "$ROOT/$target" --no-banner --redact || return 1
  done
}

echo "Verifying $(git -C "$ROOT" rev-parse --abbrev-ref HEAD) ($(git -C "$ROOT" rev-parse --short HEAD)); logs in .verify/"

# The backend tests take minutes: they run while the rest is checked.
if ! skipped pytest; then
  pytest_in_312 >"$LOGS/pytest.log" 2>&1 &
  PYTEST_PID=$!
fi

check ruff        'echo ok'                                  -- sh -c "'$PY/ruff' check backend && '$PY/ruff' check --config backend/pyproject.toml scripts"
check format      'last format'                              -- sh -c "'$PY/ruff' format --check backend && '$PY/ruff' format --check --config backend/pyproject.toml scripts"
check bandit      'echo ok'                                  -- "$PY/bandit" -q -r backend/app backend/simulator -c backend/pyproject.toml
check pyright     'last pyright'                             -- sh -c "cd backend && npx --yes pyright@1 --pythonpath .venv/bin/python app tests migrations simulator"
check lock        'echo current'                             -- lock_current
check migrations  'echo "up, check, down, up"'               -- migrations
check lint        'echo ok'                                  -- npm --prefix frontend run -s lint
check typecheck   'echo ok'                                  -- npm --prefix frontend run -s typecheck
check vitest      "grep -E '^ +Tests ' $LOGS/vitest.log | tr -s ' '" -- sh -c "cd frontend && npx vitest run"
check build       'echo ok'                                  -- npm --prefix frontend run -s build
check audit       'last audit'                               -- npm --prefix frontend audit --audit-level=high
check deploy      'echo "charts, manifests, Dockerfiles, scripts"' -- ./scripts/deploy-lint.sh
check scan        "grep -E '^(pip-audit|checkov):' $LOGS/scan.log | cut -d: -f2- | paste -sd';'" -- ./scripts/scan.sh
check gitleaks    "grep -c 'no leaks found' $LOGS/gitleaks.log | sed 's/$/ paths clean/'" -- gitleaks

if ! skipped pytest; then
  if wait "$PYTEST_PID"; then
    printf 'PASS %-12s %s\n' pytest "$(last pytest)"
  else
    printf 'FAIL %-12s %s (.verify/pytest.log)\n' pytest "$(last pytest)"
    failed=$((failed + 1))
  fi
else
  printf 'SKIP %s\n' pytest
fi

if [ "$failed" -gt 0 ]; then
  echo "$failed check(s) failed"
  exit 1
fi
echo "All checks passed"

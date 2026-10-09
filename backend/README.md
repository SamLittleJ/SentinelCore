# SentinelCore Backend

A FastAPI API with SQLAlchemy 2, PostgreSQL, Alembic and JWT authentication.

## Structure

```text
app/
├── api/        # routers and dependencies (DB session, current user, RBAC)
├── core/       # settings, DB connection, password hashing and JWT
├── models/     # ORM models
├── schemas/    # Pydantic schemas for input and output
├── services/   # business logic
└── main.py     # application entry point
migrations/     # Alembic migrations
simulator/      # attack simulator and detection evaluation (not deployed)
tests/          # pytest tests
```

## Local setup

Run the commands from `backend/`, with PostgreSQL started by `docker compose up -d` from the repository root.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

`.[dev]` also installs the development tools: pytest, httpx, Ruff and Bandit. To only run the application, `python -m pip install -e .` is enough.

## Brute-force protection

Repeated failed logins for the same email temporarily block login for that email. The thresholds are configurable in `.env`:

```env
LOGIN_MAX_FAILED_ATTEMPTS=5
LOGIN_FAILURE_WINDOW_MINUTES=15
LOGIN_LOCKOUT_MINUTES=15
```

Behind a reverse proxy, start uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy IP>`; otherwise every event records the proxy's IP.

## Detection rules

Every recorded security event goes through the detection rules in `app/services/detection_service.py`. They raise alerts, security events from the `detection` source, and never block anything; each names its MITRE ATT&CK technique in `mitre_technique`:

| Alert | Technique | When |
| --- | --- | --- |
| `password_spray_detected` (incident) | T1110.003 | failed sign-ins for many different emails from one address |
| `dormant_account_login` (warn) | T1078 | a sign-in after a long time without one |
| `unfamiliar_sign_in` (warn) | T1078 | a sign-in from a network (/24, /64) and a device the account has not used in its recent sign-ins |
| `privileged_role_granted` (warn) | T1098 | an account given the `admin` or `security_analyst` role |

The brute-force incident, `brute_force_detected`, is T1110.001. The thresholds are configurable in `.env`:

```env
DETECTION_SPRAY_MIN_ACCOUNTS=10
DETECTION_SPRAY_WINDOW_MINUTES=15
DETECTION_DORMANT_DAYS=90
DETECTION_UNFAMILIAR_LOOKBACK_DAYS=90
DETECTION_UNFAMILIAR_MIN_SIGN_INS=3
```


## Event ingestion

Other systems report sign-ins with an API key. The owner creates one (`POST /admin/api-keys`, with a name, a `source` label and a lifetime of 30, 90 or 365 days); the response holds the full key, shown only once. Then:

```bash
curl -X POST http://localhost:8000/ingest/events \
  -H "Authorization: Bearer sck_<prefix>_<secret>" \
  -H "Content-Type: application/json" \
  -d '{"events": [{"event_type": "login_failed", "occurred_at": "2026-10-09T08:15:00Z",
                   "email": "mihai.pop@example.com", "ip_address": "203.0.113.77"}]}'
```

Accepted types are `login_success` and `login_failed`, up to 500 per request. Events keep the time they happened (at most a year ago), are stored with the key's source and go through the detection rules. The answer is `202 {"accepted": N}`. Revoke a key with `POST /admin/api-keys/{id}/revoke`.

## Attack simulator

`simulator/` measures the detection rules. It drives a running instance through its public API, as an outside system would, and writes `docs/evaluation/report.md` and `report.json`.

```bash
# a running backend on a fresh database, and an owner account
export SENTINELCORE_OWNER_PASSWORD=...   # or leave it unset to be asked
python -m simulator --owner-email owner@example.com [--seed 42] [--base-url http://localhost:8000]
```

What it does:

1. Creates an API key with the `simulator` source, and registers 26 synthetic people.
2. Reports 30 days of their routine through ingestion, oldest first: office sign-ins behind one address on workdays, with an occasional typo, evenings and weekends from home, a browser update, and benign cases that a rule could take for an attack (a trip with a known laptop, a new phone, a new laptop on a trip, a return from a long leave, a password change day at the office).
3. Plays five attacks per rule, one step at a time: password sprays (T1110.003), sign-ins to dormant accounts and from an attacker's network and computer (T1078) through ingestion; brute force (T1110.001) through the real sign-in, since the lockout counts only this application's own sign-ins; admin roles granted by the owner (T1098) through the real API.
4. After each step, reads the new alerts. An attack is detected when an alert it would raise appears; every other alert is a false positive, put down to the benign case it names.
5. Revokes its key.

Time to detect is given in attack time (from the first step to the one after which the alert appeared, and in steps) and as the latency of the request that raised the alert. What is an attack stays with the simulator; the server only sees sign-ins. The seed fixes the people and their behaviour, and passwords are random and never written anywhere.

Run it on a fresh database: password spray and brute force count from their latest alert, so a second run on the same data detects less. The report says when the database already held alerts. The simulator refuses hosts other than `localhost` unless `--allow-remote` is given: it attacks its target for real.

## Observability

- `GET /health`: the process is running
- `GET /health/ready`: the application can serve traffic; answers `503` when the database is unavailable
- `GET /metrics`: Prometheus metrics; when `METRICS_TOKEN` is set, requires `Authorization: Bearer <token>`
- every response carries `X-Request-ID`, which also appears in all of the request's logs

Logging is configured in `.env`:

```env
LOG_LEVEL=INFO
LOG_FORMAT=text   # json for log collectors
```

## Authentication

- **Browser (frontend):** `POST /auth/session` sets the httpOnly `sentinelcore_session` cookie and the `sentinelcore_csrf` cookie. Every POST/PUT/PATCH/DELETE request authenticated by cookie must send the CSRF cookie's value in the `X-CSRF-Token` header.
- **API and Swagger:** `POST /auth/login` (JSON) or `POST /auth/token` (OAuth2 form) return a token, then sent as `Authorization: Bearer <token>`. These requests need no CSRF token.

## Sessions

Every login creates a session, revocable through `/auth/logout`, `/auth/logout-all`, `DELETE /users/me/sessions/{id}` or, by an operator, `POST /admin/users/{id}/revoke-sessions`.

Users can sign out of their other devices while staying signed in on the current one with `DELETE /users/me/sessions`. The security history of one's own account is at `GET /users/me/activity`.

Expired sessions, or sessions revoked more than `SESSION_RETENTION_DAYS` days ago, are deleted by the API every `SESSION_CLEANUP_INTERVAL_MINUTES` minutes. The cleanup can also run by hand or from cron:

```bash
python -m app.cli cleanup-sessions
```

## Organization scope

For `admin`, `owner` and `security_analyst` (the analyst only reads):

| Endpoint | Returns |
|----------|---------|
| `GET /security/events` | Security events, with filters and cursor pagination |
| `GET /admin/audit-logs` | Audit logs, with the same filters |
| `GET /security/summary` | Counts over 24 hours and 7 days, blocked logins, the IPs with the most failures, accounts |
| `GET /admin/users` | Users; filters `q`, `role`, `is_active`, cursor pagination |
| `GET /admin/users/{id}` | One user's details |
| `GET /admin/users/{id}/activity` | One account's security history |

The event filters include `target_user_id`, the account an operator acted on. The user list also accepts `locked`.

Actions on an account:

| Endpoint | Who | What it does |
|----------|-----|--------------|
| `POST /admin/users/{id}/revoke-sessions` | admin, owner, analyst | Closes every session; requires `reason` |
| `POST /admin/users/{id}/lock` | admin, owner, analyst | Blocks login for `duration_hours` (1-168) and closes the sessions; requires `reason` |
| `POST /admin/users/{id}/unlock` | admin, owner | Lifts the lock before it expires |
| `PATCH /admin/users/{id}/status` | admin, owner | Activates or deactivates the account |
| `PATCH /admin/users/{id}/role` | owner | Changes the role |

Nobody acts on their own account or on an owner; for status changes, only an owner acts on an admin.

## Migrations

```bash
python -m alembic revision --autogenerate -m "describe the change"
python -m alembic upgrade head
python -m alembic check    # checks that the models and the DB schema match
```

Review autogenerated migrations by hand before applying them.

Alembic uses the same `DATABASE_URL` setting as the application, from the environment or from `.env`. For a temporary database:

```bash
DATABASE_URL=postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/other_db python -m alembic upgrade head
```

## Type checking

Pylance only checks the files open in the editor. For the whole backend, with the same engine (Pyright):

```bash
npx --yes pyright@1 --pythonpath .venv/bin/python app tests migrations simulator
```

## Tests

The tests run against the separate `sentinelcore_test` database, never against the development one. Create it once:

```bash
docker exec sentinelcore-postgres createdb -U sentinelcore sentinelcore_test
```

Run:

```bash
python -m pytest -v
```

The test database address can be changed with `TEST_DATABASE_URL`; its name must contain `sentinelcore_test`.

## Checks that also run in CI

```bash
python -m ruff check .
python -m ruff format --check .
python -m bandit -r app simulator -c pyproject.toml
python -m pytest -v
```

The Gitleaks secret scan runs from the repository root. On Fedora, the `:Z` option is required because of SELinux:

```bash
docker run --rm -v "$(pwd):/repo:Z" -w /repo zricethezav/gitleaks:latest detect --source=/repo --verbose
```

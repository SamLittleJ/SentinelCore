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
python -m app.cli grant-api-login
python -m app.cli create-owner --email owner@example.com --username owner
python -m uvicorn app.main:app --reload
```

The API and the migrations sign in to PostgreSQL as different roles. The migrations run as the owner of the tables (`MIGRATIONS_DATABASE_URL`) and create the API's role, `sentinelcore_app`; `grant-api-login` lets it sign in with the password in `DATABASE_URL`. The API never signs in as the owner: row-level security binds only roles that are neither superusers nor owners of the tables, and `/health/ready` answers `503` on such a role.

`create-owner` creates the organization's first account, the owner, and asks for its password without echoing it (or reads `SENTINELCORE_OWNER_PASSWORD`). It refuses once an owner exists. There is no public sign-up: every other account joins through an invitation.

`.[dev]` also installs the development tools: pytest, httpx, Ruff and Bandit. To only run the application, `python -m pip install -e .` is enough.

## Organizations

SentinelCore keeps several organizations apart. The platform owner, created from the command line, belongs to none and manages them all; every other account belongs to exactly one, set by its invitation and never changed.

| Endpoint | Who | What it does |
|----------|-----|--------------|
| `GET /admin/organizations` | owner | Every organization with its member count |
| `POST /admin/organizations` | owner | Creates one from `name` and `slug` (2-40 characters: lowercase letters, digits, inner hyphens); `409` if either is taken |
| `PATCH /admin/organizations/{id}` | owner | Renames it; the slug never changes |
| `POST /admin/organizations/{id}/suspend` | owner | Closes every member's sessions; while suspended, members are refused as deactivated accounts are, its API keys as unknown keys are, and its invitations as invalid ones are |
| `POST /admin/organizations/{id}/reactivate` | owner | Lifts the suspension |

Organizations are never deleted, so their audit trail stays. Every security event and audit record belongs to an organization, or to the platform for the owner's own sign-ins and for failed sign-ins naming an email no account has (`app/services/tenancy.py`). Members see their own organization's records only; a record of another answers as a missing one. PostgreSQL enforces the same boundary with row-level security (`app/core/row_security.py`), so a query that forgets its filter still returns one organization's rows. An admin's check that an invited email has no account sees only their organization: an email taken elsewhere makes the invitation fail when it is accepted, and each organization keeps its own open invitation for an email.

## Accounts and invitations

An admin or the owner invites an email with a role; the response holds a token, shown only once, that the person invited uses to choose a username and a password. Nobody else ever knows that password.

| Endpoint | Who | What it does |
|----------|-----|--------------|
| `POST /admin/invitations` | admin, owner | Invites `email` with `role` into an organization: the owner names it with `organization_id` (`422` without, `404` unknown, `409` suspended); an admin invites into their own and gets `403` for naming one. Admins offer `user` or `security_analyst`, only the owner offers `admin`, nobody offers `owner`. Replaces an open invitation for the same email; `409` if the email already has an account, in any organization |
| `GET /admin/invitations` | admin, owner, analyst | Every invitation, newest first, without tokens |
| `POST /admin/invitations/{id}/revoke` | admin, owner | Stops an invitation the caller could have made |
| `POST /auth/invitations/preview` | anyone with a token | The email, role and expiry an invitation offers |
| `POST /auth/invitations/accept` | anyone with a token | Creates the account from `token`, `username` and `password`; it signs in next |

A token reads `sci_<prefix>_<secret>`; only a hash of the secret is stored. It works once, for `INVITATION_EXPIRE_HOURS` (72 by default), and only while its author may still grant its role: deactivating or demoting the author voids their invitations. The token travels in the request body, never in a URL, so it stays out of access logs. An unknown, wrong, used, revoked or expired token always gets the same `404`.

An account that joins with the `admin` or `security_analyst` role raises the `privileged_role_granted` alert, as a role change does.

## Brute-force protection

Repeated failed logins for the same email temporarily block login for that email. The thresholds are configurable in `.env`:

```env
LOGIN_MAX_FAILED_ATTEMPTS=5
LOGIN_FAILURE_WINDOW_MINUTES=15
LOGIN_LOCKOUT_MINUTES=15
```

Behind a reverse proxy, start uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy IP>`; otherwise every event records the proxy's IP.

## Detection rules

Every recorded security event goes through the detection rules in `app/services/detection_service.py`. They raise alerts, security events from the `detection` source, and never block anything; each names its MITRE ATT&CK technique in `mitre_technique`, and keeps in `occurred_at` the time of the event that raised it (`created_at` is when it was raised; the two differ for events reported late):

| Alert | Technique | When |
| --- | --- | --- |
| `password_spray_detected` (incident) | T1110.003 | failed sign-ins for many different emails from one address |
| `dormant_account_login` (warn) | T1078 | a sign-in after a long time without one |
| `unfamiliar_sign_in` (warn) | T1078 | a sign-in from a network (/24, /64) and a device the account has not used in its recent sign-ins |
| `privileged_role_granted` (warn) | T1098 | an account given the `admin` or `security_analyst` role, by a role change or an invitation |

The brute-force incident, `brute_force_detected`, is T1110.001. The thresholds are configurable in `.env`:

```env
DETECTION_SPRAY_MIN_ACCOUNTS=10
DETECTION_SPRAY_WINDOW_MINUTES=15
DETECTION_DORMANT_DAYS=90
DETECTION_UNFAMILIAR_LOOKBACK_DAYS=90
DETECTION_UNFAMILIAR_MIN_SIGN_INS=3
```


## Event ingestion

Other systems report sign-ins with an API key. The owner creates one for an organization (`POST /admin/api-keys`, with a name, a `source` label, a lifetime of 30, 90 or 365 days and the `organization_id`); the response holds the full key, shown only once. Every event the key sends, and every alert raised from it, belongs to that organization, and a successful sign-in is linked only to an account of that organization. Then:

```bash
curl -X POST http://localhost:8000/ingest/events \
  -H "Authorization: Bearer sck_<prefix>_<secret>" \
  -H "Content-Type: application/json" \
  -d '{"events": [{"event_type": "login_failed", "occurred_at": "2026-10-09T08:15:00Z",
                   "email": "mihai.pop@example.com", "ip_address": "203.0.113.77"}]}'
```

Accepted types are `login_success` and `login_failed`, up to 500 per request. Events keep the time they happened (at most a year ago), are stored with the key's source and go through the detection rules. The answer is `202 {"accepted": N}`. Revoke a key with `POST /admin/api-keys/{id}/revoke`.

Each key has a rate limit: it may send `INGEST_BURST_EVENTS` events at once (default 5,000, at least 500), then `INGEST_EVENTS_PER_MINUTE` (default 1,000). A batch that does not fit is refused whole with `429 Too Many Requests` and `Retry-After`, the seconds to wait before sending it again; nothing of it is stored. Refused events are counted in `sentinelcore_ingest_refused_events_total` and logged with the key's prefix.

## Attack simulator

`simulator/` measures the detection rules. It drives a running instance through its public API, as an outside system would, and writes `docs/evaluation/report.md` and `report.json`.

```bash
# a running backend on a fresh database, and its owner (python -m app.cli create-owner)
export SENTINELCORE_OWNER_PASSWORD=...   # or leave it unset to be asked
python -m simulator --owner-email owner@example.com [--seed 42] [--base-url http://localhost:8000]
```

What it does:

1. Creates an API key with the `simulator` source, and invites 36 synthetic people, accepting each invitation on their behalf.
2. Reports 30 days of their routine through ingestion, oldest first: office sign-ins behind one address on workdays, with an occasional typo, evenings and weekends from home, a browser update, and benign cases that a rule could take for an attack (a trip with a known laptop, a new phone, a new laptop on a trip, a return from a long leave, a password change day at the office).
3. Plays five of each evasive variant, built to pass under one rule: a spray slower than its window, a spray spread over many addresses, a stolen password used with the victim's own user agent, and an account left unused for 85 days, under the 90-day threshold. Any alert that names them counts as catching them; they are reported apart, with the reason each one passes.
4. Plays five attacks per rule, one step at a time: password sprays (T1110.003), sign-ins to dormant accounts and from an attacker's network and computer (T1078) through ingestion; brute force (T1110.001) through the real sign-in, since the lockout counts only this application's own sign-ins; admin roles granted by the owner (T1098) through the real API.
5. After each step, reads the new alerts. An attack is detected when an alert it would raise appears; every other alert is a false positive, put down to the benign case it names.
6. Revokes its key.

Time to detect is given in attack time (from the first step to the one after which the alert appeared, and in steps) and as the latency of the request that raised the alert. What is an attack stays with the simulator; the server only sees sign-ins. The seed fixes the people and their behaviour, and passwords are random and never written anywhere.

Run it on a fresh database. A second run reuses the same attacker addresses at the same times of day, so its sprays overlap the first run's and are caught sooner; its brute force attempts, all from `127.0.0.1`, add up with the first run's into a spray from that address. The report says when the database already held alerts. The simulator refuses hosts other than `localhost` unless `--allow-remote` is given: it attacks its target for real.

## Demo data

`python -m simulator.demo` fills the `sentinelcore_demo` database with ninety days of three organizations; `make demo` at the repository root runs it, with a fresh database and the servers (see the main README). Acme, the attacked one, has the simulator's people, routine and attacks, with the differences below. Globex (12 people) and Initech (6) keep to the plain routine only, with nobody back from leave, travelling, on a new device or changing a password (`build_quiet_organization` in `simulator/population.py`), so the only alert each raises is its admin's role (T1098); Initech is suspended at the end. Each organization has its own email domain, office address and VPN key, and usernames are drawn so that none repeats across them. A few sign-ins fail on unknown emails, which belong to the platform. With `--accounts-dir`, each admin's password is written to `<organization>-admin.txt` there (mode 600). Acme's differences from the simulator:

- The routine covers 90 days and runs up to the moment of the run, not to the previous midnight.
- Attacks are spread across the history (`WINDOWS` in `simulator/demo.py`): sprays on any day, stolen passwords from unknown places after a few weeks of the victim's habits, sign-ins to dormant accounts only in the last ten days, when those accounts have been unused for over 90 days. Each burst keeps its shape, every gap stretched or shrunk by up to 30 %. Brute force and role grants happen live, two and one of them.
- Afterwards, every alert raised from the history gets the time of its event plus 2 to 40 seconds as its `created_at`, written directly to the database. Lists, ranges and the summary order and count alerts by detection time; without this step they would all fall on the day of the run. It refuses any database but `sentinelcore_demo`, and any host but `localhost`.

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

## API documentation

Swagger UI (`/docs`), ReDoc (`/redoc`) and the schema (`/openapi.json`) are served only when `API_DOCS_ENABLED=true`, which `.env.example` sets for development; otherwise they answer `404`, like any unknown path. The pages load their code from a CDN, and cookies do not separate ports, so open them at `http://127.0.0.1:8000/docs`: another host than the web app's `localhost`, whose cookies never reach it. Keep the setting off outside development.

## Security headers

Every response carries a Content Security Policy and the usual security headers (`app/api/security_headers.py`):

- JSON answers get `default-src 'none'; frame-ancestors 'none'`: nothing in them may run, load or be framed. With them come `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, a `Permissions-Policy` that turns off the camera, microphone, location and payments, and `Cross-Origin-Opener-Policy: same-origin`. An unhandled error's `500` carries them too.
- `/docs` and `/redoc`, when turned on, are pages that load Swagger UI and ReDoc from a CDN: their policy allows those two packages only, and Swagger UI's inline script by its hash. Turned off, their paths get the API's policy, like any unknown path.
- `HSTS_MAX_AGE` (seconds, `0` by default) adds `Strict-Transport-Security`. Set it only once the host is served over HTTPS.

## Sessions

Every login creates a session, revocable through `/auth/logout`, `/auth/logout-all`, `DELETE /users/me/sessions/{id}` or, by an operator, `POST /admin/users/{id}/revoke-sessions`.

Users can sign out of their other devices while staying signed in on the current one with `DELETE /users/me/sessions`. The security history of one's own account is at `GET /users/me/activity`. `GET /users/me` also names the account's organization (`organization`: id, name and slug; `null` for the platform owner).

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
| `GET /security/summary` | Counts over 24 hours and 7 days, hour by hour and day by day, alerts per MITRE ATT&CK technique, the threat level and the latest detection's technique and time, blocked logins, the IPs with the most failures, accounts; for the owner without `organization_id`, also `organizations`: every organization and the platform with their level and 24-hour counts, the worst first |
| `GET /admin/users` | Users; filters `q`, `role`, `is_active`, cursor pagination |
| `GET /admin/users/{id}` | One user's details |
| `GET /admin/users/{id}/activity` | One account's security history |

The event filters include `target_user_id`, the account an operator acted on. The user list also accepts `locked`.

Every read is limited to the caller's organization. A record of another organization answers exactly as a missing one (`404`, the same body), and so does a cursor (`before_id`) taken from one. The platform owner, who belongs to none, sees every organization and the platform's own records; they may narrow any listing above, and `GET /admin/invitations` and `GET /admin/api-keys`, to one with `organization_id` (`404` if unknown). Anyone else sending `organization_id`, even their own, gets `403 Insufficient permissions`. Records carry their `organization_id`, empty for the platform's own. The owner's reads appear in the audit log of each organization whose records they returned.

Actions on an account:

| Endpoint | Who | What it does |
|----------|-----|--------------|
| `POST /admin/users/{id}/revoke-sessions` | admin, owner, analyst | Closes every session; requires `reason` |
| `POST /admin/users/{id}/lock` | admin, owner, analyst | Blocks login for `duration_hours` (1-168) and closes the sessions; requires `reason` |
| `POST /admin/users/{id}/unlock` | admin, owner | Lifts the lock before it expires |
| `PATCH /admin/users/{id}/status` | admin, owner | Activates or deactivates the account |
| `PATCH /admin/users/{id}/role` | owner | Changes the role |

Nobody acts on their own account or on an owner (for a member, the owner's account answers `404`, as any account outside their organization); for status changes, only an owner acts on an admin.

## Migrations

```bash
python -m alembic revision --autogenerate -m "describe the change"
python -m alembic upgrade head
python -m alembic check    # checks that the models and the DB schema match
```

Review autogenerated migrations by hand before applying them.

Alembic signs in with `MIGRATIONS_DATABASE_URL`, the owner of the tables, or with `DATABASE_URL` when it is not set, from the environment or from `.env`. For a temporary database:

```bash
MIGRATIONS_DATABASE_URL=postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/other_db python -m alembic upgrade head
```

A new table needs, in its migration, the API role's privileges (`GRANT`) and a row-level security policy, as in `5d1a3c7e9b20`; without them the API gets `permission denied`, and the tests catch it.

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

The test database address can be changed with `TEST_DATABASE_URL`; its name must contain `sentinelcore_test`. The tests build its schema with the migrations, signed in as the owner of the tables, and the application's sessions take the API's role, so row-level security applies to them as in production.

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

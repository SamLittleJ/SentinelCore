# 02 - Decisions Log

The technical decisions behind SentinelCore, in the order they were made, one per bullet. A later decision can replace an earlier one; those are marked *Superseded* with a pointer to what replaced them.

## Foundation

- A monorepo instead of two repositories.
- A modular monolith instead of microservices.
- Web-first for the MVP.
- A separate virtual environment in `backend/`.
- The backend runs with `python -m uvicorn`.
- Backend configuration is centralized in `app/core/config.py`, using `pydantic-settings`.
- The local development database is PostgreSQL, run with Docker Compose.
- SQLAlchemy is the ORM foundation.
- The project uses absolute imports starting from `app`, to avoid duplicate and inconsistent modules.
- The first ORM entity is `User`, mapped to the `users` table.
- At this stage, `Base.metadata.create_all(...)` is used only to validate the model and the ORM connection. Managing the database structure moves to Alembic later. *Superseded: see [Alembic migrations](#alembic-migrations).*
- API input and output are separated from the ORM model by Pydantic schemas.
- The DB session for endpoints is provided by `get_db()` in `app/api/deps.py`.
- Password hashing is centralized in `app/core/security.py`.
- User business logic lives in `app/services/user_service.py`.
- The register endpoint is implemented in `app/api/routes/auth.py`.
- Creating a user explicitly checks for duplicate `email` and `username`.
- Passwords are never stored raw; only `hashed_password` is saved.
- The first end-to-end flow validated is `POST /auth/register`.

## Authentication and RBAC

- The JWT is used not only when it is issued, but also to identify the current user.
- The JWT `sub` claim holds the user's email at this stage. *Superseded: see [JWT and sessions](#jwt-and-sessions).*
- The current user comes from the `get_current_user()` dependency.
- The RBAC MVP uses a `role` field on the `User` model.
- Roles are defined by the `UserRole` enum.
- The default role at registration is `user`.
- Role authorization goes through the `require_role()` dependency.
- Role-protected endpoints return `403 Forbidden` when the user lacks the required permission.
- The `GET /users/admin-only` endpoint is used to validate the RBAC foundation.
- Local schema changes are still validated by a local reset and `create_all()`, not by Alembic migrations. *Superseded: see [Alembic migrations](#alembic-migrations).*

## Audit logging

- Audit logs are stored in PostgreSQL, in the `audit_logs` table.
- Audit event types are defined by the `AuditEventType` enum.
- The `AuditLog` model allows an optional `user_id`, for events with no valid user attached.
- The `email` field is kept in the audit log, so failed login attempts can be traced.
- Creating audit events is centralized in `app/services/audit_service.py`.
- `POST /auth/register` creates a `USER_REGISTERED` event.
- `POST /auth/login` creates `LOGIN_SUCCESS` and `LOGIN_FAILED` events.
- `GET /users/admin-only` creates an `ADMIN_ENDPOINT_ACCESSED` event when access is allowed.
- At this stage, access denied by RBAC is not audited yet.
- For the MVP, audit enum values are accepted in the form SQLAlchemy stores them, for example `USER_REGISTERED`.
- Audit logs are exposed through `GET /admin/audit-logs`.
- The audit endpoint is available only to the `admin`, `owner` and `security_analyst` roles.
- Regular users get `403 Forbidden` on the audit logs.
- Audit logs are returned through the `AuditLogRead` schema, not directly as an unchecked ORM model.
- Listing audit logs is bounded by the `limit` parameter. *Superseded: see [Log pagination and filters](#log-pagination-and-filters).*

## Security events

- Security events are separate from audit logs.
- Audit logs are the factual journal of actions in the system.
- Security events are the events relevant to security and SIEM-light.
- Security events are stored in PostgreSQL, in the `security_events` table.
- Security event types are defined by the `SecurityEventType` enum.
- Security severities are defined by the `SecuritySeverity` enum.
- The initial severities are `info`, `warn` and `incident`.
- `GET /security/events` exposes the security events through the API.
- `GET /security/events` is protected by RBAC.
- The roles allowed to read security events are `admin`, `owner` and `security_analyst`.
- A failed login maps to a security event with `warn` severity.
- Register, successful login and admin access map to security events with `info` severity.
- Security events are the start of SentinelCore's SIEM-light component.

## Alembic migrations

- The database schema is managed by Alembic, not by `Base.metadata.create_all()` at application startup.
- `create_all()` was used only temporarily, for learning and local validation.
- Alembic migrations become the standard mechanism for future schema changes.
- `Base.metadata.create_all(bind=engine)` was removed from `app/main.py`.
- The standard Alembic directory is `migrations/`.
- An initial misnamed directory (`imigrations`) was renamed to `migrations`.
- `migrations/env.py` uses `target_metadata = Base.metadata`.
- The `User`, `AuditLog` and `SecurityEvent` models are imported in `migrations/env.py` for autogenerate.
- The initial migration creates the `users`, `audit_logs` and `security_events` tables.
- The `alembic_version` table records the current schema version.
- Future model changes go through `alembic revision --autogenerate` and `alembic upgrade head`.
- Autogenerated migrations are reviewed by hand before they are applied.

## Tests

- Backend tests run with `pytest`.
- FastAPI is tested through `TestClient`, which requires `httpx`.
- Tests live in `backend/tests`.
- The pytest configuration is in `pyproject.toml`.
- Tests use a separate database: `sentinelcore_test`.
- Tests must never run against the development database.
- In tests, the `get_db()` dependency is overridden through `app.dependency_overrides`.
- `Base.metadata.create_all()` is allowed only in the test fixture, not in the real application.
- The real application uses Alembic to manage the schema.
- Only the `app*` package is included in the build; `migrations*` and `tests*` are excluded from packaging.
- The first round of tests covers `/health`, register and login.
- The tests were extended in Tests Foundation Phase 2.
- `tests/test_protected_routes.py` was created.
- Protected routes are tested automatically with a valid JWT.
- `/users/me` is tested both with a valid token and without one.
- `/users/admin-only` is tested both with a regular user and with an admin.
- For test setup, the user is promoted to `admin` directly in the test database.
- Direct promotion to admin is accepted only in tests, never as production logic.
- `/admin/audit-logs` is tested with an admin user.
- `/security/events` is tested with an admin user.
- The backend now has 11 automated tests, passing with `pytest`.
- The tests cover the main IAM, JWT, RBAC, audit log and security event flows.

## Backend CI

- The `Backend CI` workflow was introduced in GitHub Actions.
- The workflow is defined in `.github/workflows/backend-ci.yml`.
- CI runs automatically on `push` and `pull_request` to `main`.
- For `push`, the trigger is limited by `paths` to changes in `backend/**` and `.github/workflows/backend-ci.yml`; for `pull_request`, the `paths` filter was removed.
- `workflow_dispatch` was kept for manual runs from GitHub Actions.
- The workflow starts a PostgreSQL service from the `postgres:17` image, the same version as in Docker Compose.
- The CI database is `sentinelcore_test`.
- `TEST_DATABASE_URL` points explicitly at the test database.
- `DATABASE_URL` is set in CI so the application imports correctly.
- The CI `SECRET_KEY` must be at least 32 bytes, to avoid the HMAC SHA256 warnings.
- The GitHub actions were updated to `actions/checkout@v5` and `actions/setup-python@v6`.
- The `pydantic[email]` dependency was added for `EmailStr` support in CI.
- CI runs `python -m pip install -e .` in `backend/`.
- CI runs the tests with `python -m pytest -v`.
- The backend has 11 automated tests passing in GitHub Actions.
- The external warning from `TestClient` / `httpx` is tolerated for now, since it does not come from the application's own code.

## Code quality: Ruff

- Ruff was introduced for linting and for checking Python formatting.
- Ruff is configured in `backend/pyproject.toml`.
- The enabled rules include `E`, `F`, `I`, `B` and `UP`.
- The backend uses `ruff check .` for linting.
- The backend uses `ruff format --check .` to check formatting.
- Ruff was run locally before it was added to CI.
- The `B008` findings were fixed by moving FastAPI dependency injection to `typing.Annotated`.
- The `B904` finding was fixed with `raise ... from exc`.
- Enums defined as `str` + `enum.Enum` were modernized to `StrEnum`.
- Ruff was added to `.github/workflows/backend-ci.yml`.
- The Ruff steps run in CI before `pytest`.
- Backend CI now checks both code quality and functional tests.
- The GitHub Actions workflow is green with Ruff lint, the Ruff format check and 11 backend tests.

## Security checks: Bandit and Gitleaks

- Bandit was introduced to scan the Python code for security issues.
- Bandit is configured in `backend/pyproject.toml`.
- Bandit scans the application code with `python -m bandit -r app -c pyproject.toml`.
- The `tests`, `.venv` and `migrations` directories are excluded from the Bandit scan.
- Bandit's `B106` report for `token_type="bearer"` was analyzed as a false positive.
- `B106` was not disabled globally; a targeted `# nosec B106` was used instead.
- Gitleaks was introduced to scan the repository for secrets.
- Gitleaks looks for passwords, tokens, API keys, private keys and other hardcoded secrets.
- Locally, on Fedora, Gitleaks runs through Docker with a `:Z` mount for SELinux compatibility.
- The local Gitleaks command is `docker run --rm -v "$(pwd):/repo:Z" -w /repo zricethezav/gitleaks:latest detect --source=/repo --verbose`.
- In GitHub Actions, Gitleaks runs as a separate job through Docker.
- CI does not need `:Z`, since the problem was specific to the local Fedora/SELinux environment.
- The Gitleaks job uses `actions/checkout@v5` with `fetch-depth: 0`.
- `fetch-depth: 0` lets Gitleaks scan the full Git history.
- `gitleaks/gitleaks-action@v2` was replaced by running Gitleaks through Docker, to avoid the Node.js 20 warning.
- The backend pipeline now checks Ruff, Bandit, Gitleaks and pytest.
- Security Checks Phase 1 is complete, with a green pipeline and no relevant warnings.

## Working on a private repository

*Superseded: see [Public repository](#public-repository).*

- Until the repository becomes public, work goes through branches and manual pull requests.
- The repository stays private, in the personal account, for now.
- A branch protection rule for `main` was created, but it is not enforced on the current private plan.
- Until the repository is published, work goes through branches and pull requests, with discipline.
- Every new task gets its own branch.
- Pull requests must have a green CI before they are merged.
- Nobody works directly on `main`, even though GitHub does not technically prevent it.

## Admin user management - phases 1 and 2

- Admin User Management Phase 1 was introduced.
- The `GET /admin/users` endpoint was created.
- It lists the users in the system.
- Access to `GET /admin/users` is allowed only for the `admin` and `owner` roles. *Superseded: see [Organization API](#organization-api).*
- Regular users get `403 Forbidden` on this endpoint.
- `app/api/routes/admin_users.py` was created.
- The `admin_users` router is registered in `app/main.py`.
- The user listing logic is separated into `app/services/user_service.py`.
- `list_users()` uses `limit` and `offset` for basic pagination. *Superseded: see [Organization API](#organization-api).*
- The endpoint uses the `UserRead` schema, so sensitive fields are not exposed.
- `hashed_password` is never returned by the API.
- Listing users creates an audit log.
- Listing users creates a security event with `INFO` severity. *Superseded: see [Organization API](#organization-api).*
- The endpoint is tested with a regular user and an admin.
- The number of backend tests grew from 11 to 13.
- The work was done on a separate branch and validated through a pull request.
- `main` is treated as the stable branch, even though branch protection is not enforced on the current private plan.
- Admin User Management Phase 2 was introduced.
- The `GET /admin/users/{user_id}` endpoint was created.
- It shows one user's details.
- Access to `GET /admin/users/{user_id}` is allowed only for the `admin` and `owner` roles. *Superseded: see [Organization API](#organization-api).*
- Regular users get `403 Forbidden`.
- When the requested user does not exist, the API returns `404 Not Found`.
- The message for a missing user is `User not found`.
- `get_user_by_id()` was added to `app/services/user_service.py`.
- Viewing a user's details creates an audit log.
- Viewing a user's details creates a security event with `INFO` severity. *Superseded: see [Organization API](#organization-api).*
- The endpoint is tested with a regular user, an admin and a missing user.
- The number of backend tests grew from 13 to 16.

## Admin user management - phase 3: roles

- Role changes are restricted to an authenticated owner, through `PATCH /admin/users/{user_id}/role`.
- The endpoint forbids self-modification, modifying existing owners, and assigning the owner role.
- The audit and security event identity fields record the actor; the message records the target ID and the old and new roles.
- A real role change and both event records share one commit, with a rollback when the commit fails. The existing event helpers commit on their own and are not used for this transaction.
- An allowed request for the role the user already has returns 200 without change events. The owner restrictions still apply before this shortcut.
- Phase 3 reuses the existing event categories and needs no schema migration.
- Local verification on 2026-10-06 confirmed 29 passing PostgreSQL tests, passing Ruff checks and no Bandit security findings. Bandit emitted warnings about an existing `nosec` comment.
- Transaction-failure testing and Phase 3 CI validation remain pending. *Superseded: the transaction-failure test came with phase 4.*

## Hardening

- `migrations/env.py` imports the model modules explicitly, with `# noqa: F401`, so `--autogenerate` sees the complete schema.
- `python -m alembic check` is used to confirm the models and the DB schema match.
- Users with `is_active = False` get `403 Inactive user` at login and on every authenticated endpoint.
- A login by an inactive user is recorded as `LOGIN_FAILED`, with `WARN` severity.
- For an unknown email, login checks the password against a dummy hash, so the response time does not reveal whether the account exists.
- Duplicate registrations are also caught at the unique index; `UniqueViolation` becomes `400`, not `500`.
- The development tools are in the `dev` extra; development and CI install with `pip install -e ".[dev]"`.
- Dependencies have minimum versions; `ruff` is pinned exactly, to avoid unexpected changes in CI.
- CI and Docker Compose use the same PostgreSQL version, `postgres:17`.

## Admin user management - phase 4: status

- Phase 4 introduces `PATCH /admin/users/{user_id}/status` with the body `{"is_active": bool}`, consistent with the role change endpoint.
- Activation and deactivation are hierarchical: `admin` manages `user` and `security_analyst` accounts, and `owner` also manages `admin` accounts.
- Nobody can change their own status, and an `owner`'s status cannot be changed.
- `is_active` is validated with `StrictBool`, with no implicit conversion from strings or numbers.
- Administrative changes to users have dedicated event types: `USER_ROLE_CHANGED`, `USER_ACTIVATED`, `USER_DEACTIVATED`.
- The phase 3 role change now uses `USER_ROLE_CHANGED` instead of `ADMIN_ENDPOINT_ACCESSED` / `ADMIN_ACCESS`.
- New enum values are added by hand-written migrations; `--autogenerate` does not detect changes to an enum's values.
- The downgrade for enum values recreates the PostgreSQL type and remaps the rows to the earlier generic types.
- The user change and its events are saved in a single commit, through `_commit_user_change()`.

## Input validation

- Usernames have 3-50 characters, only `A-Z`, `a-z`, `0-9`, `_`, `.`, `-`, and are stored in lowercase.
- Emails are stored and looked up in lowercase.
- Registration passwords have 12-128 characters, with no composition rules.
- Login only limits the password to at most 128 characters, for compatibility with existing accounts.
- The input rules are reusable `Annotated` types in `app/schemas/user.py`.
- Existing emails and usernames are lowercased by a migration; conflicts stop the migration and are resolved by hand.

## Brute-force detection

- 5 failed logins within 15 minutes for the same email block login for that email for 15 minutes; the values are configurable in `.env`.
- The block is per email, not per email + IP, so it cannot be bypassed by changing IP; the risk of temporarily locking out a victim is accepted.
- While the block lasts, the response is `429` with `Retry-After`, and the password is not checked.
- Unknown emails are blocked the same way, so the block does not reveal which accounts exist.
- The block state is derived from `security_events`, with no separate tables or columns.
- Time comparisons for the block use the database clock.
- The incident uses `BRUTE_FORCE_DETECTED` with `INCIDENT` severity; the audit log uses `LOGIN_LOCKED`.
- Attempts made during the block are recorded as `LOGIN_BLOCKED`, with `WARN` severity.

## Client IP address

- Every audit log and security event records `ip_address`, from `request.client.host`; `X-Forwarded-For` is not read directly.
- Behind a reverse proxy, the real IP comes from uvicorn's `--proxy-headers` and `--forwarded-allow-ips`.
- In tests, the connections are recreated after the schema is recreated, to avoid prepared statements tied to dropped enum types.

## Log pagination and filters

- `/admin/audit-logs` and `/security/events` return `{"items": [...], "next_cursor": ...}`, with cursor pagination (`before_id`).
- Events are ordered by descending `id`, the same key as the cursor. *Superseded: see [Organization events and audit pages](#organization-events-and-audit-pages).*
- The shared filters are `user_id`, `email`, `ip_address`, `since`, `until`; audit logs add `event_type`, and security events add `event_type` and `severity`.
- The time range is half-open: `since <= created_at < until`.
- Dates without a time zone are rejected with `422`.
- Unknown query parameters are rejected with `422`, so a misspelled filter is never silently ignored.
- Reading the logs is audited with `AUDIT_LOGS_VIEWED` and `SECURITY_EVENTS_VIEWED`, in the audit log only, not as security events.
- The shared filtering and pagination logic is in `fetch_event_page()`.

## Observability

- Metrics are exposed in Prometheus format at `/metrics`, using `prometheus-client`.
- Metric labels use the route template, `unmatched` for unknown paths and `OTHER` for unknown methods, to bound the number of series.
- `sentinelcore_security_events_total` is incremented after each security event is committed.
- `/metrics` requires a Bearer token only when `METRICS_TOKEN` is set; the token is compared in constant time.
- Every request has a request id, reused from `X-Request-ID` only when it is safe, generated otherwise.
- Logs are structured, in `json` or `text` format, configurable with `LOG_FORMAT`.
- The uvicorn access log is disabled; the middleware writes one log line per request.
- `/health` is liveness, and `/health/ready` is readiness and checks the database.
- Prometheus and Grafana run in Docker Compose with host networking, listening only on `127.0.0.1`.
- The Prometheus and Grafana configuration is versioned in `infra/`, and the dashboard is provisioned automatically.
- The Prometheus and Grafana Docker images are pinned to exact versions.

## JWT and sessions

- The JWT `sub` is the user's id, as a string; the email no longer identifies the user in the token.
- The token contains and verifies `iss`, `aud`, `jti`, `iat` and `exp`; every claim is required.
- `SECRET_KEY` must be at least 32 bytes, and `ALGORITHM` accepts only HS256, HS384 or HS512.
- Every login creates a session in `user_sessions`; the token's `jti` is the session id.
- Logout revokes the current session; `logout-all` revokes all of the user's sessions.
- Users can list and revoke their own sessions; other users' sessions answer `404`.
- Deactivating an account revokes all its sessions in the same commit; reactivation does not restore them.
- `/auth/token` offers an OAuth2 form login for Swagger UI and uses the same login logic as `/auth/login`.
- Session and token times come from the application clock, because PyJWT rejects an `iat` in the future.
- Logout and session revocation are audit events only (`SESSION_REVOKED`, `ALL_SESSIONS_REVOKED`).

## Session cleanup and admin revocation

- Expired or revoked sessions are kept for `SESSION_RETENTION_DAYS` days (30 by default), then deleted; active sessions are never deleted.
- The cleanup runs periodically in the API process (`SESSION_CLEANUP_INTERVAL_MINUTES`, `0` disables it) and can be run by hand with `python -m app.cli cleanup-sessions`.
- A failed cleanup is logged and retried at the next interval.
- Admins can revoke all of a user's sessions through `DELETE /admin/users/{user_id}/sessions`, with the same hierarchical rules as status changes. *Superseded: see [Account containment](#account-containment).*
- The hierarchical account management rules are centralized in `_ensure_can_manage_account()`.
- Revocation by an admin creates an `ALL_SESSIONS_REVOKED` audit log and a `USER_SESSIONS_REVOKED` security event.
- Migrations already applied to the development database are never edited; new changes get a new migration.
- Backend types are checked in full with Pyright, not only in the files open in Pylance.

## Browser authentication

- The frontend authenticates with the httpOnly `sentinelcore_session` cookie, set by `POST /auth/session`; the token is not in the body and is not reachable from JavaScript.
- The authentication cookies have `Secure`, `SameSite=Strict` and `Path=/`; `Secure` can be disabled with `AUTH_COOKIE_SECURE`, only for plain-HTTP test hosts.
- POST/PUT/PATCH/DELETE requests authenticated by cookie require the `X-CSRF-Token` header, equal to an HMAC of the session id (signed double-submit).
- Requests with `Authorization: Bearer` need no CSRF token; the header takes precedence over the cookie.
- `/auth/session` accepts only JSON, which blocks login CSRF through HTML forms.
- Logout also clears the authentication cookies.
- In development, the frontend uses the Vite proxy for `/api`, so the frontend and the API share an origin, with no CORS.

## Frontend foundation

- The frontend follows the "operations console" visual direction: dark theme by default with a complete light variant, a dense interface, IBM Plex Sans and IBM Plex Mono.
- The app's palette is "Electric": electric blue on navy, generated in OKLCH, with WCAG AA contrast and chart colors checked for color blindness.
- Severity colors are separate from the brand color and always come with text and a shape.
- The app has two scopes: "My account" for every user and "Organization" for `admin`, `owner` and `security_analyst`.
- Components are built with Tailwind CSS and shadcn/ui; the theme colors are CSS variables.
- Routing uses React Router, and server data uses TanStack Query.
- The interface is in Romanian (by default) and English, through i18next; the English translations are typed after the Romanian ones.
- Fonts are served by the app through `@fontsource`, with no requests to Google Fonts.
- The `next` parameter after login accepts only internal paths, to prevent open redirects.
- Any `401` received during use sends the user to login; logout clears the whole data cache.
- Frontend CI runs `npm audit`, lint, the type check, the tests and the build.

## My account

- Every user sees their own security history through `GET /users/me/activity`; the endpoint accepts no identity filters.
- The personal history includes failed or blocked login attempts that carry only the account's email, but only those after the account was created.
- The personal history has no `message` field; the frontend describes events by type, in the interface language.
- Reading one's own history is not audited.
- `DELETE /users/me/sessions` signs out the other devices and keeps the current session; it has its own audit log, `OTHER_SESSIONS_REVOKED`.
- Alembic reads `DATABASE_URL` from the application settings; `alembic.ini` holds no connection.
- In the interface, "alerts" are the events with `warn` or `incident` severity.
- Actions that close sessions ask for confirmation in the page, not through dialogs.
- A session's device is inferred from `User-Agent` and shown only as a hint.
- Page filters are kept in the address, so they can be shared as a link.

## Organization API

- Security events and audit logs have `target_user_id`: `user_id` is the actor, `target_user_id` is the account that was acted on.
- The affected user sees the actions taken on their account in their own history (`as_target: true`), without the IP address and without the operator's identity.
- `GET /admin/users` uses cursor pagination, like the event lists; `offset` pagination was removed.
- The user search (`q`) is a substring of the email or username, and `%` and `_` are treated as text.
- `security_analyst` can read users and their history, but cannot change them.
- Reading users is an audit event only (`USERS_VIEWED`), not a security event.
- Operators see an account's history through `GET /admin/users/{id}/activity`, the same events its owner sees, with every field; reading it is audited.
- `GET /security/summary` provides aggregate counts for the organization overview and is not audited.
- The "Organization" scope ships in four small PRs: backend, Events + Audit, Users, Overview.

## Account containment

- `security_analyst` can contain accounts: close all their sessions and temporarily lock their login; deactivation stays with `admin` and `owner`.
- Containment applies to any account except the owner and one's own; any operator can contain an admin, because the actions are reversible.
- A temporary lock lasts between 1 hour and 7 days, closes the sessions, expires on its own and creates an `incident` severity event.
- Only `admin` and `owner` can lift a lock before it expires.
- Closing sessions and locking require a reason (3-500 characters), stored in the audit log and the security event; the affected user does not see it.
- At login, the lock is checked after the password and does not reveal when it ends.
- An operator closes a user's sessions with `POST /admin/users/{id}/revoke-sessions`, because the action now has a body.

## Organization events and audit pages

- The events and audit pages keep their filters in the address; the default range is 7 days.
- The log search takes an exact email or IP address, in a single field; IPv4 and values containing `:` go to the IP filter.
- The organization logs do not reload on their own when the window regains focus, because every load is audited; reloading is explicit.
- A record's details open in a side panel, with actions that narrow the list to the record's account, target or IP address.
- In the organization scope, events are described neutrally, not in the second person.
- The organization pages load on demand, separately from the rest of the app.
- Event lists are ordered by `created_at`, then by `id`; the cursor stays `before_id`, and the server compares the `(created_at, id)` pair.
- Scrollbars use the theme colors, regardless of the browser's support for `color-scheme`.

## Public repository

- The repository becomes public, under the MIT license.
- PostgreSQL in `docker-compose.yml` listens only on `127.0.0.1`, like Prometheus and Grafana.
- The CI workflows have only the `contents: read` permission.
- New commits use the GitHub noreply address; the existing history is not rewritten.
- The documentation is in English from here on; the earlier Romanian documentation was translated.

## Organization users page

- An account has its own page (`/org/users/:id`), not a side panel: it holds a paged history and the action forms, and its address can be shared.
- The page offers only the actions the signed-in operator may take; one's own account and the owner's show a sentence explaining why there are none. The rules mirror the API's in `features/org/permissions.ts`; the API still decides.
- A temporary lock offers 1 hour, 24 hours or 7 days.
- The containment actions ask for a reason in the page, with the API's bounds (3-500 characters after trimming) checked before sending.
- The "Active" state filter means active and not locked, so a locked account never shows as active.
- A change the API answers with the account replaces the cached account instead of reading it again, since every account read is audited.
- The details panel of a log record links to the accounts it names.

## Organization overview

- The overview shows the last 24 hours as the headline and the last 7 days beside each count, with no switch between them; the API gives failed sign-ins and their sources over 24 hours only, so a switch would leave half the page unchanged.
- The overview lists the 5 newest incidents of the last 7 days. Showing them is audited like any read of the event log (`security_events_viewed`); the counts are not, since they hold no records.
- The counts and the incidents reload together, only on the page's refresh button, never on window focus, so they always describe the same moment and the audit log gains no automatic entries.
- Every count opens the records behind it: the event log filtered by severity or type over 24 hours, or the user list filtered by state. Each failed sign-in source opens the failed sign-ins from that address.
- The failed sign-in sources are bars scaled to the largest, in the accent color, with the count written beside each, so the number never rests on bar length alone.

## Detection rules

- Detection rules run in one engine (`detection_service`), after the event they watch is committed, so internal events and, later, ingested ones feed the same rules.
- The new rules only alert; responding stays with the operators through containment, so a false positive never locks anyone out. Brute-force protection keeps its block on the email.
- The location rule, planned for the ingestion stage, compares the network (a /24 for IPv4, a /64 for IPv6) and the device, not the country: it needs no outside data and behaves the same in tests and in the simulator.
- Each detection is mapped to a MITRE ATT&CK technique in code (`MITRE_TECHNIQUES`), not stored per row: the technique follows from the type.
- Password spray: 10 different emails failing from one address within 15 minutes is an incident; counting restarts after each alert. Dormant: 90 days without a sign-in. Privileged: granting `admin` or `security_analyst`. All thresholds are settings.
- Windows are measured from the triggering event's own time, not from now, so late events are judged in their context.
- A failing rule is logged and skipped; it never fails the action that triggered it.
- Downgrading the migration deletes the alert rows instead of relabelling them, since no older type means the same.

## Event ingestion

- Other systems send security events through `POST /ingest/events` with an API key. The keys are created and revoked by the owner only; admins and analysts can list them.
- Every key expires, after 30, 90 or 365 days chosen at creation, and can be revoked at once.
- Keys are stored as a prefix and a SHA-256 hash of a 32-byte random secret, and shown in full only once.
- Only sign-ins are accepted for now (`login_success`, `login_failed`), the events the rules and the simulator use; more types come with a real source for them.
- The sender states what happened; the server sets the severity and the message. The key's source is stamped on each event, and `backend` and `detection` are reserved.
- Ingested events keep the time they happened, and up to a year of history is accepted, so the rules can look back over it. A key holder could in principle shape that history; keys are issued by the owner and expire.
- The response reports only how many events were accepted, never the alerts they raised.
- Brute-force protection counts only the application's own sign-ins: reported failures never lock anyone out here, and reported successes never reset the count.
- Security events record the user agent of sign-ins, for the new device rule.
- The ingestion stage was split from the new network and device rule, which comes next, to keep each change reviewable.


## Unfamiliar network and device

- A sign-in alerts only when both its network and its device are new to the account. Either alone is common and would make the rule noisy; both together is the pattern of stolen credentials used elsewhere.
- The network is the /24 (IPv4) or /64 (IPv6) block of the address. No GeoIP database: it would add a licensed, regularly updated dependency, and countries say little about a single organization's users.
- The device is the user agent without its version numbers, with no parsing library: a browser update keeps the device, and the rule stays explainable in one line.
- The account's habits are its last 90 days of sign-ins with an address and a user agent, and it is judged only after 3 of them, so new accounts and old history without user agents stay quiet.
- The alert is a `warn`, like the dormant account rule: a signal to investigate, not a confirmed incident.

## Attack simulator

- The simulator is a separate package that drives a running instance over HTTP through the public API, not a set of in-process tests: it measures the real path (authentication, ingestion, detection) and can be shown live. The tests run the same code over FastAPI's TestClient.
- What is an attack stays with the simulator; the server receives only sign-ins, as in production.
- Time to detect is measured in attack time and in steps, plus the latency of the request that raised the alert, rather than in wall-clock time: runs take seconds instead of hours and give the same numbers every time.
- The report (`docs/evaluation/report.md` and `report.json`) is committed, with a fixed seed, so results can be cited and compared between versions.
- All five rules are covered: brute force through the real sign-in, since its lockout counts only the application's own sign-ins, and privileged roles through the real API.
- Benign cases that the rules' design cannot tell from attacks (a new laptop on a trip, a return from long leave, a password change day behind one office address) are part of the routine and expected to alert. They are reported as false positives with their cause, not left out.
- The simulator attacks only `localhost` unless told otherwise, reads the owner's password from the environment or a prompt, and revokes its API key at the end.
- Evasive attack variants were split into a later stage, to keep each change reviewable.

## Alert event time

- Alerts keep the time of the event that raised them in a new `occurred_at` column, and rules compare earlier alerts by it. Changing only the spray rule's comparison would have fixed the symptom; the column fixes the cause, for every later rule and for sources that deliver logs late.
- `created_at` stays the time an alert was raised, so new alerts remain at the top of the event log and in the overview's last 24 hours. Stamping alerts with the event's time instead would have hidden a late alert in the past.
- Existing alerts get their `created_at` as `occurred_at`; the event's time was not kept, and for real-time events it is the same moment.
- A replayed log raises no second spray alert, which the simpler fix would not have guaranteed.

## Evasive attack variants

- Four variants, five of each: a slow spray, a distributed spray, a copied user agent, and an account idle for just under the dormancy threshold. Slow brute force is left out: its lockout works in real time only, and waiting it out would make runs take hours.
- Evasions are reported in their own section with their own rate and the reason each passes. The headline detection rate stays that of the attacks the rules are built for.
- An evasion counts as caught by any alert that names it, not only by the rule it targets.
- The tests require every variant to pass: the limits are recorded, and a rule change that closes one shows up as a test to update.
- The limits are documented, not fixed in this stage; each fix trades for false positives or needs a new signal.

## API keys and MITRE ATT&CK in the interface

- API keys have their own organization page, `/org/api-keys`, listed for every operator and changed only by the owner.
- A new key is shown once in a panel in the page, not in a dialog, like the other confirmations. It is kept only in the page's state, never in the address, browser storage or the query cache.
- Detections show their MITRE ATT&CK technique as a badge in every event table; the details panel adds its name and a link to attack.mitre.org in a new tab without a referrer, and, for a late alert, when its event happened.
- No filter by technique yet: it would need a new API parameter, and the type filter already selects the detections.

## Invitations instead of public sign-up

- An organization's accounts are not open to anyone who reaches the API. `POST /auth/register` is removed rather than turned off by a setting: less code, and nothing to leave on by mistake. It also told anyone whether an email had an account.
- Accounts join through an invitation: an admin or the owner names an email and a role, and the person invited chooses a username and a password. A temporary password set by an operator, or a password chosen for them, was rejected: the operator would know it, and could act as that person.
- Admins invite `user` and `security_analyst`; only the owner invites an admin; nobody invites an owner. Who may grant a role is checked again on acceptance, so deactivating or demoting an author voids their invitations.
- The token is built like an API key (`sci_<prefix>_<secret>`, random, a SHA-256 hash stored, compared in constant time; the shared code is in `core/secret_tokens.py`), lasts 72 hours by default and works once. One open invitation per email, enforced by a partial unique index; a new one revokes the old.
- The token travels in request bodies (`POST /auth/invitations/preview`, `/accept`), not in a path or query string, so it stays out of access logs. Every unusable token gets the same `404`. Operators are told when an email already has an account, since they can list accounts anyway.
- Acceptance locks the invitation row, so two requests cannot both use it, and does not sign the person in.
- Joining with `admin` or `security_analyst` raises the T1098 alert, as a role change does; otherwise an invitation would be a way around it.
- The first owner comes from `python -m app.cli create-owner`, which reads the password from the environment or a prompt and refuses once an owner exists.
- The simulator now invites its people as the owner and accepts on their behalf, the same path as a real account.

## Visual identity

- The shell looked like an unchanged shadcn/ui sidebar. Among four directions drawn on the real overview (a threat status band, typography and a logomark, a new navigation with a command palette, data visuals), the combination of the band, the typography, the data visuals and a Ctrl+K palette was chosen, keeping the sidebar navigation.
- Built in two stages: the identity first (frontend only), then the trends, which need new aggregated data from the API.
- IBM Plex Sans Condensed joins Plex Sans and Plex Mono, as a Fontsource package bundled with the app, like the other two.
- The command palette is built on the Radix Dialog already used for the side panels, as an ARIA combobox with a listbox, rather than adding the `cmdk` library: one dependency fewer for about fifteen commands.
- The palette does not search the API as one types. Searching opens the user list or the event log filtered, which loads and audits the records as usual; live results would audit a read for every pause in typing.
- The incident badge beside Security events uses the summary counts, which are not audited, and loads only in the organization scope.

## Security trends

- The band's level: an incident in the last 24 hours makes it "incident", a detection alert "warn", nothing "calm". Ordinary warnings are left out, or the band would almost always warn.
- The band names only the latest detection's technique and time, not its account or address, so the summary stays a set of counts and is not audited on every page.
- Hourly and daily windows are rolling, measured back from now, rather than calendar hours and days: no time zone to choose, and they add up to the 24-hour and 7-day totals shown beside them.
- Alerts per technique come with their event types from the API, so the interface does not keep its own copy of the mapping.
- The latest incidents on the overview became a timeline; each opens the same details panel as before.

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

## Invitations interface

- Invitations sit on the Users page rather than a page of their own: they are accounts about to exist. Open invitations are listed; used, revoked and expired ones are folded into a history, so the list stays short without losing who joined.
- The link is shown once, like an API key, and kept only in the page's state. Its token sits in the URL fragment, which browsers do not send to servers, and the public page clears it from the address once read.
- After acceptance the person is sent to sign-in with the email filled in, rather than signed in automatically: the API does not open a session on acceptance, so the first sign-in goes through the same checks as every other.
- The new account's email reaches the sign-in page through the router's state, not a query string, so it stays out of the address and the browser history.
- The password is asked twice. There is no password reset yet, so a typo would lock the person out until an operator stepped in.

## Agent skills copied, not installed

- Three skills from [mattpocock/skills](https://github.com/mattpocock/skills) are kept in `.claude/skills/`: `grill-me` and `grilling`, an interview in numbered rounds with a recommended answer for each question, and `tdd`, a red → green loop at seams agreed beforehand. The first is meant for the STRIDE threat model.
- They are copied at a fixed commit, with their MIT license, rather than installed as the plugin. The plugin updates itself, so the instructions the agent follows would change without review. A copy changes only through a pull request.
- Only these three are taken. The plugin's other 24 skills either repeat what the project already has (the learning notes, the decisions log, Claude Code's own `/code-review`) or assume an issue tracker the project does not use. Each skill's description is also loaded at the start of every session.
- OpenSpec, a spec-driven workflow, was considered and set aside for now: it would duplicate the journals and the decisions log.

## Demo data

- `make demo` builds the history once and serves it, rather than a job adding activity every day: the demo is the same at every run, shifted to end at that moment, needs no machine left running, and leaves no gaps in the trends.
- The demo reuses the attack simulator's organization and attacks, so what the demo shows is what the evaluation measures. It runs on its own `sentinelcore_demo` database.
- Attacks are spread over ninety days at random hours, each within the days where it is still an attack (dormant accounts only once unused for 90 days), and each burst keeps its pace, with some drift. Scattering a burst's attempts would turn it into an evasive variant.
- Accounts and operator actions go through the API at the time of the run, so they all fall on that day. Writing them into the past directly would mean forging audit records.
- Alerts keep the detection time as `created_at` in the application, and lists and counts use it, as alert queues do. Showing the event time in tables instead was considered and dropped: rows ordered by one time and labelled with another look out of order. For the demo only, a final step moves each alert raised from the history to its event's time plus a few seconds, as if it had been watched live. It writes to the database directly, so it refuses any database but the demo's.
- The owner's password is random and written only to `.demo/owner.txt`, mode 600 and ignored by git, never to the terminal.

## Several organizations

Decided in one design session, in rounds, each with a recommended answer:

- **Roles.** One platform owner, created from the command line, belongs to no organization and manages them all. Every other account belongs to exactly one, set by its invitation and never changed. Emails stay unique across the platform, so someone working for two organizations has two accounts. Only the owner invites admins, into any organization; admins invite users and analysts into their own. The owner may take every admin action in any organization. Analysts do not invite, and admins do not invite other admins: a compromised analyst or admin account cannot create further accounts to stay in (MITRE T1136), and whoever investigates is not the one who grants access.
- **Organizations.** Created, renamed and suspended by the owner only, never deleted. Names and slugs are unique; a slug never changes, so links and filters keep working. Suspension closes members' sessions, refuses them as deactivated accounts are, and refuses the organization's keys as unknown keys are.
- **Visibility.** The owner sees every organization by default, with an optional filter and an organization column; members see neither. The owner's access to an organization appears in its audit log. A record of another organization answers `404`, exactly as a missing one; only the owner may send `organization_id`, others get `403`. Filtering in the application is backed by PostgreSQL row-level security.
- **Detection.** Rules count within each organization, with the same thresholds for all. Correlating attacks across organizations is left for later. A failed sign-in naming no account belongs to the platform rather than a guessed organization, which would show a company attempts on addresses that are not its own. Prometheus metrics stay global.
- **Data.** Existing data moves to an organization named "Default". The evaluation stays on one organization so its numbers stay comparable; the demo gets three.
- **Delivery.** Five pull requests: organizations and the organization of every record; isolation of every read; row-level security; the interface; the demo. The STRIDE threat model follows, with the organization boundary as the main trust boundary.
- **First stage.** One rule decides the organization of records that do not name it (`app/services/tenancy.py`), rather than each call site, and the database refuses an owner with an organization or anyone else without one. The owner's invitation and API key forms got an organization field in the same stage, so the interface keeps working between stages.
- **Second stage.** Reads are limited in one place per kind of record: listings take a scope worked out from the caller (`read_scope` in `app/api/deps.py`, `Scope` in `app/services/tenancy.py`), and single records are looked up through the caller's scope, so another organization's record answers exactly as a missing one. The platform owner's account counts as outside every organization, so members get `404` for it too, instead of the earlier `403`. A pagination cursor must belong to the caller's own results, or the page is empty as for an unknown one: otherwise any record's id would tell its time.
- **The owner's reads in the organizations' audit logs.** Chosen among three options: a read of one organization is recorded there; a read of everything is recorded in each organization whose records it returned, and on the platform when it returned the platform's own records or nothing. One platform record would hide the owner's reads from the organizations; a record in every organization would claim reads that returned nothing of theirs.
- **Detection within one organization.** The spray rule, the only one keyed on an address, counts failures and earlier alerts within the event's organization, or within the platform's failures on unknown emails. The other rules follow one account, which belongs to one organization. An account's history leaves out sign-ins another organization's systems reported for the same email.
- **Third stage: row-level security.** Each table holding an organization's records has a policy that shows, and accepts, only the rows of the organization the transaction names, or every row when it names everything (`app/core/row_security.py`, migration `5d1a3c7e9b20`). The scope is a transaction setting written at the start of every transaction, since a request commits more than once. A sign-in session follows its account's visibility.
- **The API's own database role.** Chosen over `SET ROLE` on the owner's connection: the API signs in as `sentinelcore_app`, neither superuser nor owner of the tables, since both bypass the policies; the migrations sign in as the owner. Besides the policies, an SQL injection through the API could no longer drop tables or run commands on the server. The API may only add to security events and the audit log, never change or delete them. `/health/ready` answers `503` on a role that bypasses row security, so a wrong `DATABASE_URL` cannot quietly turn the policies off.
- **Fail closed.** Chosen over showing everything by default: a session that has not said who is asking sees no rows. Sign-in, the session check, invitation links and API keys, which must find a record before knowing its organization, ask for everything explicitly and narrow it as soon as they know the caller; so do the session cleanup and the command line. A forgotten declaration shows up as an error or an empty page, never as another organization's data.
- **Invitations within one organization.** Chosen over keeping the `409`: an admin's check that an invited email has no account sees only their organization, so they no longer learn that an address has an account elsewhere; that invitation fails when accepted, with the same answer as an invalid one. The owner, who sees every account, still gets `409`. Each organization keeps its own open invitation for an email: before, an admin's invitation revoked another organization's for the same email, a write across the boundary the policies now refuse.
- **Fourth stage: one choice of organization for the whole console.** Chosen over a filter on each page: the owner picks the organization once, in the sidebar, and the band, the overview and every list follow it, so no page shows one organization beside a band counting all of them. The address holds the choice, so links and Back keep it; the console also remembers it while a step drops it from the address, since loading every organization in between would write audit records in each of them.
- **A member's organization by name.** Chosen over a separate endpoint or no name: `GET /users/me` names the account's organization, so the console needs no extra request. Only that endpoint does, so account lists stay one query.
- **The owner's organizations by level.** Chosen over one summary request per organization, which grows with the platform, and over a field in the organizations list, whose every load is audited: the summary of the whole platform lists each organization's level and counts. It holds counts only, like the rest of the summary, so it is not audited. The platform's own records get a row too, so a level raised by attempts on unknown emails is not left unexplained.
- **Suspension after typing the slug.** Chosen over a plain confirmation: suspending signs out every member at once, so a deliberate step guards it, inside the page's usual confirmation step rather than a modal dialog.
- **Fifth stage: a demo of three organizations.** Decided in a grilling session, each with the recommended answer. Acme stays the attacked organization, unchanged but for its email domain. Globex and Initech keep to the plain routine, with none of the benign cases that alert, so the only alert each raises is its admin's role, and the overview shows three different situations. Initech is suspended through the API at the time of the run, rather than backdated with another direct write to the database. Each organization gets its own domain reserved for examples, office address and key. A few failures on unknown emails give the platform's row something to show, below the spray threshold. Each admin's password is written locally, mode 600, to show isolation and suspension live. No attack spans two organizations: that cross-organization spray is a known limit, left to the threat model.

## Threat model

- **STRIDE per element, on data flow diagrams.** Decided in a grilling session, each with the recommended answer. Two Mermaid diagrams (the system with its actors, then the path of one request with the boundary between organizations), and each element checked against the STRIDE categories. Each threat names its attacker profile, its mitigation, the test that proves it or *untested*, a MITRE ATT&CK technique where one fits, and a residual risk.
- **Qualitative risk.** Likelihood and impact, low to high, combined in a fixed table, over DREAD (criticised as subjective and dropped by its authors) and CVSS (made for single vulnerabilities, not a model).
- **Trust assumptions stated, not modelled.** The platform owner and the owner of the tables are trusted; the document says what follows if either is compromised and what limits the damage today. Modelling a malicious owner would need the owner's powers split, a project of its own.
- **Documented, not fixed.** The pull request adds the analysis only; each gap it finds is fixed in its own pull request, with the usual checks. It ends with five residual risks and estimates; their order is chosen afterwards.
- **Scope.** Today's system; containers, the supply chain and cloud infrastructure add their sections in their phases.


## Security headers

- **Where the headers come from.** Decided in a grilling session, each with the recommended answer. The API sets its own in a middleware. The console's come from `vite.config.ts`: a relaxed policy for the dev server, and the strict one for `vite preview`, which serves the build. Phase B's nginx copies the preview's headers.
- **Inline styles allowed, inline scripts not.** Radix adds `<style>` elements, and a nonce would need a server that writes each page. A style cannot run code, and `img-src`, `font-src` and `form-action` keep injected markup from loading from or posting to another site. Scripts are limited to the bundle's own files.
- **Enforced at once.** There is no report-only phase and no endpoint for violation reports. Such an endpoint would be public and unauthenticated, another surface to abuse, like ingestion. End-to-end runs over every page show whether the policy breaks anything.
- **The API's answers.** `default-src 'none'; frame-ancestors 'none'`, with `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` and `Cache-Control: no-store`, so that security data stays out of caches. The same headers are on an unhandled error's `500`.
- **The documentation pages.** Chosen over hosting Swagger UI and ReDoc locally or turning them off outside development: a narrow policy for `/docs` and `/redoc` that allows their two packages, and Swagger UI's inline script by its hash. The supply chain risk that remains is T-58 in the threat model.
- **HSTS off by default.** `HSTS_MAX_AGE` sends it once the host is on HTTPS. Browsers remember it, so turning it on by default would lock browsers out of a host on plain HTTP.
- **Fonts as files.** Vite no longer inlines fonts as `data:` URIs, so `font-src 'self'` holds without allowing `data:` fonts.

## API documentation outside development

- **Off unless turned on.** Decided in a grilling session, each with the recommended answer. This replaces the earlier choice under "Security headers", which kept the documentation pages on with a narrow policy: their CDN code (T-58) could still act with the console's session wherever both share a host, since cookies do not separate ports. `API_DOCS_ENABLED`, default `false`, turns on `/docs`, `/docs/oauth2-redirect`, `/redoc` and `/openapi.json` together; `.env.example` sets it for development.
- **A setting of its own.** Chosen over deriving it from `APP_ENV`, which nothing reads yet and which would become a hidden switch for more than one behaviour.
- **The schema too.** `/openapi.json` maps every route, administration included, and nothing in the project reads it over HTTP; the tests read it from the application.
- **A plain 404.** Off, the routes are not registered, and their paths answer like any unknown path, headers included: the headers middleware is told the documentation is off, so it gives those paths the API's policy. A `403` or a "documentation disabled" message would tell a caller how the server is configured.
- **An application factory.** `create_app(settings)` builds the application; `app.main:app` is still the one built from the environment. Tests build their own with the documentation on or off, so they do not depend on a local `.env`.
- **Development keeps the risk.** Accepted and documented rather than hosting Swagger UI and ReDoc locally or pinning their exact versions: the documentation is opened at `127.0.0.1:8000`, a host to which the console's `localhost` cookies are never sent.
- **No startup log line.** `APP_ENV` is not read, so the API cannot tell production from development to warn; the setting is visible in the environment, and a test pins its default.

## Ingestion rate limit

- **Two pull requests for one risk.** Decided in a grilling session, each with the recommended answer. Residual risk 2 of the threat model, misuse of a valid ingestion key, gets a rate limit per key first (T-38) and an alert when a key's volume departs from its usual level second (T-34).
- **Events, not requests.** Detection runs on every event, so a batch of 500 costs what 500 requests of one event do; a limit on requests would be dodged by sending full batches.
- **A token bucket.** Each key may send `INGEST_BURST_EVENTS` (5,000) events at once, then `INGEST_EVENTS_PER_MINUTE` (1,000). The burst lets a sender load its history, as `make demo` does (about 3,000 events on one key) and the evaluation does (about 1,270 on a fresh key); 1,000 a minute is a few percent of what one process handles. A fixed window would let twice the limit through across a minute's boundary and refuse the demo's backfill; a sliding window would keep the time of every event. The limit cannot be turned off, and the burst holds at least the largest batch, so every valid batch fits sooner or later.
- **In PostgreSQL, on the key's row.** The bucket's state is two columns of `api_keys`, read under a row lock and timed by the database clock, so every API process and replica shares one bucket per key and a restart keeps it. Kept in memory, each replica of phase B would have its own bucket; Redis would be a new service to run and secure for this alone.
- **Per key, after the key is checked.** A wrong key still gets `401`, so only a caller who holds a valid key learns that it is over its limit. A flood of invalid keys from one address is left to the per-address limit of residual risk 5 and to the ingress of phase B.
- **The whole batch refused.** A batch that does not fit gets `429 Too Many Requests` with `Retry-After`, the seconds until it fits, and the same message every time; a partial acceptance would leave the sender guessing what to send again. An invalid batch takes no tokens, and a refused one still updates the key's last use.
- **Refusals as a metric and a log line, not security events.** A security event for every refusal would let a flood fill the very table the limit protects. Refused events are counted in `sentinelcore_ingest_refused_events_total` by source and logged with the key's prefix; the alert of the second pull request is the detection.

## API key volume alert

- **The second half of residual risk 2.** Decided in the same grilling session as the rate limit, each with the recommended answer. The rate limit caps how much a stolen key can send (T-38); this alert tells the operators when a key sends far more than it usually does (T-34).
- **Counted at arrival, by the database clock.** A sender chooses the times its events claim, so a flood stamped last week would hide in last week's counts. Each key's events are counted per UTC clock hour in which they arrive, in a new table, `api_key_usage` (key, organization, hour, received, refused), under row-level security like every other table. Refused events count too: a flood the rate limit turns away is still a flood.
- **A spike against the key's own usual level.** The usual level is the median of each day's busiest hour over the last 14 days on which the key sent anything, today left out. An hour alerts when it reaches three times that and at least 100 events; a key with fewer than 7 such days is still learning and is not judged. The median keeps one unusual day from moving the baseline, as it would a mean; the busiest hour, rather than the day's total, matches the hour that is judged; the minimum keeps a quiet key's 3 events against its usual 1 from alerting. The four numbers are settings (`DETECTION_VOLUME_FACTOR`, `DETECTION_VOLUME_MIN_EVENTS`, `DETECTION_VOLUME_LOOKBACK_DAYS`, `DETECTION_VOLUME_MIN_DAYS`).
- **Spikes only.** A key that falls silent, because its log shipper broke or an attacker turned it off (T1562), is a different question with its own false positives (weekends, holidays); it is accepted in the threat model as T-59 and left for later.
- **One alert per key per hour.** The hour's row records when it alerted, and the alert claims it with a conditional update, so batches that arrive together raise one alert between them.
- **A `warn` alert, mapped to T1499.** `api_key_volume_spike`, from the `detection` source, in the key's organization, with the sending address and a message naming the key's prefix and name, the hour's count and the usual level. It never revokes the key: like every rule, it only alerts, and responding stays with the owner. Fake events sent at the key's usual volume (T1565.001) are not caught.
- **Kept 30 days.** `API_KEY_USAGE_RETENTION_DAYS` (at least the lookback) bounds the table; the periodic cleanup that deletes old sessions deletes the old hours too, by whole UTC days.
- **The demo and the simulator stay as they are.** A baseline counted at arrival cannot be backfilled, so the demo's keys stay in learning; the tests write a key's earlier days directly, and the evaluation report says that the simulator cannot measure this rule.

## Sign-in limit per address

- **Residual risk 5, chosen next.** Decided in a grilling session of thirteen questions, each with the recommended answer, before risks 3 and 4: it reuses the token bucket of the ingestion rate limit and guards the one public path that checks passwords.
- **Failures only.** Every attempt takes a token before the password is checked, and a successful sign-in gives it back, so people who sign in are never limited, and two attempts from one address cannot spend the same token. Attempts refused because their email is locked keep their token: otherwise one address could send them forever, each writing a `login_blocked` event.
- **A bucket per address, in the database.** A table of its own, `sign_in_address_limits`, shared by every API process, as the ingestion buckets are. Counting `login_failed` events in a window, as the email lockout does, would leave the refused attempts uncounted, and a counter in memory would be one per replica in phase B. An address belongs to no organization, so only the scope that sees every row reaches the table.
- **20 at once, then 6 an hour.** One address can then try about 144 emails a day, and keeps a victim locked at most about 15 minutes in every 50, against all the time before; a whole office behind one address still has room for typos. Any refill at all lets an address save up the five failures a lock needs, so this lowers T-12 rather than closing it. The two numbers are settings (`LOGIN_ADDRESS_BURST`, `LOGIN_ADDRESS_FAILURES_PER_HOUR`), and the burst must exceed the spray alert's threshold, so that alert still comes first, and be at least the lockout's.
- **IPv6 by /64, unknown addresses together.** One IPv6 customer usually holds a whole /64 network and may change addresses within it at will. A request whose address is unknown shares one bucket with every other such request: not knowing an address must not lift the limit.
- **First, and answered as the lockout answers.** The address is checked before the email's lockout and the password, and refused with the same `429`, detail and `Retry-After`, so a refused attempt learns neither which limit it met nor whether its password was right.
- **One record per address limited, none per refusal.** The failure that spends the last token records a `login_address_limited` event (`warn`, source `backend`, T1110) and an audit record, both the platform's: an address is no organization's. The refusals that follow are a counter and a log line, as the ingestion refusals are, so a flood cannot fill the event table.
- **Sign-in only, and no manual unlock.** Invitation tokens cannot be guessed, and floods of wrong ingestion keys are left to phase B's ingress. A bucket refills by itself; an unlock would be one more power to guard and test. An address shared by many clients is accepted as T-60.
- **The simulator and the demo raise the limit.** Asked while building: both play every attacker from one address, and five brute-force attacks of eight failures would be stopped by the limit before their emails lock. Their servers run with `LOGIN_ADDRESS_BURST=1000`, so 25 of 25 stays a measure of the rules, the limit is covered by its own tests, and the evaluation report says so.

## Sprays across organizations

- **Residual risk 3, next.** Decided in a grilling session of fourteen questions, each with the recommended answer, before risk 4 (tamper evidence): it is shorter, reuses the address grouping of the sign-in limit, and is a detection rule the simulator can measure.
- **This application's own sign-ins only.** Ingested logs are left out: their private addresses mean different machines in different organizations, a tenant could forge events to raise or hide a platform alert, and ingestion runs inside its key's organization under row-level security, which would have to be loosened for one query. A spray split across organizations in ingested logs stays a documented limit (T-40, partly mitigated).
- **The address as the sign-in limit counts it.** An IPv6 address counts with its /64 network, as in `address_key`, since one customer usually holds a whole /64. The organizations' spray rule keeps the exact address, to keep this change small.
- **Two places at least.** The rule counts the distinct emails across every organization and alerts only when they come from at least two places, emails no account has counting as one: a spray inside one place is that place's own rule's. An organization's alert and the platform's may both be raised for one spray; the second says something new, that other organizations were tried too.
- **The spray's settings, no new ones.** The same ten emails in 15 minutes. The check that the per-address burst exceeds that threshold keeps covering this rule, so its alert comes before the address is limited.
- **A type of its own, the platform's.** `cross_organization_spray_detected`, T1110.003, an incident like the spray. Reusing `password_spray_detected` with no organization would mix it with sprays on emails no account has, which already have none. A `platform` flag on the rule stores its alerts with no organization, so only the owner sees them; nothing is copied into the organizations tried, which would tell one tenant that another was attacked. The message gives counts only, no organization names or emails.
- **Its exact address in the alert.** The alert keeps the address of the failure that raised it, so the console's address filter finds it; the message names the /64 for IPv6, and repeats are compared by network.
- **Measured from loopback addresses.** Decided in the grilling: the simulator's attacks share one address, which would mix the sprays. Each spray across organizations comes from a loopback address of its own, which Linux allows towards a server on the same machine; against any other server the simulator leaves them out rather than measure them wrongly. The second organization is drawn from a generator of its own, so the first one and its attacks stay what the seed made them.
- **Shown in the demo.** One spray across Acme, Globex and guessed emails, today and from its own address, so the platform's view has the incident to show.


## Sealed audit history

- **Residual risk 4, the last of the five.** Decided in a grilling session of thirteen questions, each with the recommended answer.
- **The audit log only.** It is the record of who did what, the one an insider would want to rewrite. Security events stay unsealed: ingestion writes them at up to a thousand a minute per key, every write would wait for the chain, and the demo moves its alerts in time. That gap stays in T-45, which is now partly mitigated.
- **A keyed seal, not a plain hash.** A chain of plain SHA-256 hashes inside the database is no evidence against the owner of the tables (TA2), who can compute it again in seconds. Each record's seal is an HMAC-SHA256 keyed with `AUDIT_CHAIN_KEY`, a setting of the API that the database never holds: whoever has the database alone cannot seal a changed record. Whoever has both the server's environment and the database still can, which the threat model says.
- **Anchors outside the database.** Deleting the newest records leaves a shorter chain that still verifies. The periodic check writes each chain's length and head to the log and to two Prometheus gauges, and remembers the lengths in its process, so a shorter chain is reported as truncated while the process runs and stays visible in the logs and in Prometheus afterwards. No alerting rules in Prometheus yet; that waits for phase B.
- **One chain per organization, plus the platform's.** Under row-level security a request sees only its organization's rows, so a single chain would need its head read past the policies. With a chain each, every writer already sees the head it continues, and organizations do not wait on each other.
- **Sealed on flush, for every writer.** A SQLAlchemy `before_flush` listener next to the model seals every new audit record, whichever of the nine places adds it. The columns are required, so a write that skipped the listener fails, and the tests check every chain after every test.
- **An advisory lock per chain.** A transaction-scoped PostgreSQL advisory lock serializes the writers of one chain until commit; a table of chain heads would have needed its own policy and the `UPDATE` privilege. A unique constraint on the organization and place, with `NULLS NOT DISTINCT` for the platform's chain, stays as the safety net.
- **What the seal covers.** The place, the previous seal, the type, the actor, the target, the organization, the email, the address, the message and the time, as canonical JSON. Not the id, which the database assigns on insert, after the seal: the API's role may not update the row to add a seal that covers it. For the same reason the time is the database clock, read before the insert.
- **The existing history sealed by the migration.** Records written before the seal are sealed in the order they were written, so after `alembic upgrade head` the whole history is covered; the migration therefore needs the key too.
- **The key.** Required, at least 32 bytes, and not `SECRET_KEY`, so one leaked secret does not open both the sessions and the seal. Rotation is left out: a new key makes the sealed history fail its check.
- **Checked periodically and on demand.** The cleanup task checks every chain at its interval and raises `audit_chain_broken`, an incident on the platform with the `detection` source and T1070 (Indicator Removal), once per chain and broken record, whichever process finds it. `python -m app.cli verify-audit-chain` only reads and exits with 1 on a break. No console page: the alert reaches the owner through Security events.
- **Not in the demo.** `make demo` checks the seal after seeding instead of breaking it, so the demo never shows a permanent incident. The simulator, a client of the public API, cannot break a chain, so the evaluation report leaves the alert out of its measurements.

## Phase B: containers and local Kubernetes

- **Three pull requests.** Decided in a grilling session of twenty questions, each with the recommended answer: B1 builds the images and the console's server, B2 the Helm charts, kind and `make up`, B3 the checks in CI, the documentation and the threat model. Each starts with a short grilling session of its own on the details.
- **Tools on the system and pinned in the repository.** kind, Helm and kubectl are installed on the developer's machine from the distribution (Fedora packages them), and `make` also downloads the same versions into a git-ignored `.tools/`, checked against their SHA-256, so CI and other machines run exactly what the developer runs.
- **nginx serves the console.** The unprivileged nginx image serves the build and passes `/api` to the backend, so the browser sees one origin, as with Vite: no CORS, and the `SameSite=Strict` cookies keep working. Caddy would have done the same; serving the build from FastAPI would have tied the two images together.
- **No ingress controller yet.** nginx's Service is a NodePort that kind maps to `127.0.0.1:8080`. The community ingress-nginx controller has been retired, and the Gateway API that replaces it fits phase D, with the cloud.
- **PostgreSQL from its own chart.** A StatefulSet of the official image, pinned by digest, in a chart of its own installed before the application's, as a managed database would be in the cloud. The CloudNativePG operator would bring backups but also custom resources, and may come with phase E; the Bitnami chart was left out since its free images moved to a legacy repository in 2025.
- **The session cleanup stays in the API.** The roadmap had it as a CronJob, but since the audit history is sealed the cleanup also checks the chains and remembers their lengths in its process to notice truncation, which a fresh process for each run would forget. Every API replica runs it; its deletions are idempotent and the alert is raised once whichever process finds a break.
- **Secrets from `make up`.** The secret key, the audit chain key, the database passwords and the metrics token are generated once, as Kubernetes Secrets, when they do not exist; none is in `values.yaml` or in git. Helm's `randAlphaNum` with `lookup` would not work with `helm template` or Argo CD (phase D); External Secrets belongs to phase E.
- **Out of phase B.** Image scanning, an SBOM, signing and provenance (phase C); a Gateway, NetworkPolicies, Pod Security admission, External Secrets and Prometheus in the cluster (phases D and E). `docker-compose.yml` stays for development and `make demo` stays on it.

## Container images (B1)

- **One backend image for the API, its migrations and its command line.** The migration Job of B2 runs the same code the API serves. The image holds `app/`, `migrations/` and `alembic.ini` only; the tests and the simulator stay out.
- **Dependencies pinned with their hashes.** `backend/requirements.lock`, generated by `make lock` with uv (`uv pip compile --generate-hashes`), lists every runtime package for Python 3.12 on Linux; the image installs it with `--require-hashes`, so a package changed at its source is refused. uv is used only to write the file, and pip-tools would have done the same more slowly. CI installs the same pins before running the tests, and fails when `pyproject.toml` changed without the lockfile: uv keeps the pins already in the file, so a new release upstream does not fail the check.
- **The application is copied, not installed.** Installing the backend as a package would have built it with setuptools fetched without a hash, so its code is copied next to the pinned virtual environment instead.
- **Base images pinned by digest.** `python:3.12-slim`, `node:22-alpine` for the console's build stage and `nginxinc/nginx-unprivileged:stable-alpine`. Distroless images were left out: their Python is 3.11 and the backend needs 3.12. Python stays 3.12, as in CI; moving to a newer version is a change of its own.
- **Non-root, read-only.** The backend runs as UID 10001 and the console as the nginx image's own unprivileged user, 101, whose files the image prepares; both write only to `/tmp`, so the root filesystem can be read-only. Bytecode is compiled at build time for that reason.
- **The console's headers come from one source.** `frontend/scripts/nginx-headers.ts`, run by Node at the image build, writes `security-headers.ts`'s production headers as nginx `add_header … always;` lines, included in every location that serves the console (nginx drops inherited headers in a location that adds its own). The API's answers keep the backend's own stricter policy.
- **Caching.** `index.html` and the console's routes are `no-store`, so a new release shows at once; the built files, whose names carry their content's hash, are cached for a year as immutable.
- **The client's address.** nginx replaces `X-Forwarded-For` with the address it saw, and uvicorn believes that header only from the addresses in `FORWARDED_ALLOW_IPS` (`127.0.0.1` in the image; nginx's network in the deployment): a client cannot pick its own address for the sign-in limit or the detection rules.
- **A first limit on ingestion floods.** nginx allows each address 20 requests a second to `/api/ingest`, with bursts of 100, and answers `429` beyond, before the API checks the key: a flood of invalid keys stops there (T-38). Each nginx process counts on its own.
- **Metrics stay inside.** `/api/metrics` answers `404` at nginx, like any missing route; Prometheus will read the backend directly inside the cluster.
- **Images tagged by commit.** `make images` tags both with the short commit hash, marked `-dirty` when the tree has changes, and labels them with the OCI source and revision. A registry comes with phase C or D.

## Local cluster (B2)

- **Two charts, one namespace.** PostgreSQL has its own chart, installed and ready before the application's, as a managed database would be; both live in the namespace `sentinelcore`. No PodDisruptionBudget: there is one node.
- **kubectl pinned to the cluster's version.** kind 0.31.0's node is Kubernetes 1.35, and kubectl is supported within one minor version of the cluster, so `make` uses kubectl 1.35.7 from `.tools/` rather than a newer one from the system.
- **The owner of the tables stays a superuser.** As in Docker Compose and CI. A separate superuser with an owner limited to `CREATEROLE` would follow least privilege more closely, but needs every migration checked without superuser rights; only the migration Job holds these credentials, and the split is left to phase E.
- **Three Secrets, the URLs composed by `make up`.** The API pods never receive the owner's URL, which only the migration Job gets. Values are generated with `openssl rand` and written through standard input, never as `--from-literal` arguments, which other processes of the same user could read. A partial set is refused: the audit seal and the database's passwords cannot be replaced by new values.
- **The first owner from a Job, with `--if-missing`.** `make up` can run it every time: the command line now exits with 0 when an owner exists. The password lives in a Secret only while the Job runs, then only in `.kind/owner.txt`.
- **Image IDs as pod annotations.** A `-dirty` build reuses its tag, and with `IfNotPresent` the pods would keep the old image; the annotation changes with the image, so its pods, and only those, are replaced.
- **CPU limits as well as memory.** CPU limits can slow a pod under load, but policy tools of phase C report their absence, and the values leave room for a local cluster.
- **A smoke test in the repository.** `make cluster-check` checks the cluster's security properties from outside and inside, for B3 and for the dissertation. Its address check signs in as the owner successfully, since failed sign-ins would count towards the one local address's limit and the spray rule.

## Deployment checks (B3)

- **One command for the deployment's files.** `make deploy-lint` runs the same checks locally, in `make verify` and in CI, so a pull request fails for nothing the developer could not see first.
- **Tools from `scripts/tools.sh`, not from the Marketplace.** kubeconform, hadolint and shellcheck are downloaded at pinned versions and checked by SHA-256, like kind, Helm and kubectl; container images tagged `:latest` and third-party actions would bring code nobody pinned. The workflows use GitHub's own `checkout` and `setup-node` only.
- **kubeconform's schemas pinned to a commit.** By default it fetches the latest schemas on each run; pinned, the same manifests always get the same answer. No resource may lack a schema, since there are no custom resources.
- **Warnings fail.** hadolint fails from `warning` up and shellcheck on any finding; an exception is written on its line with its reason, never in a global configuration.
- **A real cluster in CI, but not on every pull request.** `make up` and `make cluster-check` take several minutes, so they run when the deployment's files change, and on demand. Two workflows, since GitHub filters paths per workflow, not per job, and a path-filter action from the Marketplace would be third-party code.
- **Policy scanning waits for phase C.** kube-score, Checkov and Trivy judge configuration against policy; B3 checks correctness, phase C brings the scanners with the rest of the supply chain.

## Supply chain (C1)

- **Actions pinned by commit SHA.** A version tag can move: `aquasecurity/trivy-action` tags were force-pushed on 2026-03-19 ([CVE-2026-33634](https://www.cve.org/CVERecord?id=CVE-2026-33634)). Every action now names a full SHA, with its version in a comment for people and Dependabot; `make deploy-lint` checks both.
- **Dependabot over Renovate.** GitHub's own updater covers the five ecosystems needed here without another service or token. Weekly updates are grouped by ecosystem, with a seven-day cooldown to let a bad release be withdrawn before it is proposed; security updates skip the wait.
- **Tool versions stay manual.** Dependabot does not read `scripts/tools.sh`. Its versions and checksums are reviewed together; the CI PostgreSQL service image is manual too.
- **Gitleaks as a pinned binary.** The same version and SHA-256 from `scripts/tools.sh` serve the local scan and CI, without another container image to pin. `--redact` keeps a finding's secret out of the log, and the required check keeps its name.
- **A hashed virtual environment for the scanners.** Checkov and pip-audit live in `.tools/scanners`, installed from `security/scanners.lock` with `--require-hashes --only-binary :all:`. The backend's dev dependencies are not hash-locked; adding the scanners there would leave their own dependencies unpinned. Selected versions are at least seven days old.
- **Exceptions per check and resource, with expiry.** `scripts/scan_gate.py` matches both, so accepting one resource cannot hide the same finding elsewhere as Checkov's own skip can. Every exception needs a reason and an expiry at most 180 days ahead; expired entries and unused resource patterns fail, so a finding fixed upstream cannot leave a silent pass behind.
- **CodeQL in its own workflow.** The repository records the pinned actions, `security-extended` queries, three languages (`python`, `javascript-typescript`, `actions`), schedule and permissions. Default setup would leave these choices outside the reviewed files.
- **PyPI advisories, not OSV.** pip-audit uses its default PyPI advisories. With OSV, `--require-hashes` only checks that hashes are present; it does not verify them.
- **Open question: Dependabot and the backend lock.** Whether Dependabot can regenerate the header-less `requirements.lock` written by uv is still open after its first run: Ruff is not in the lock, so its pull request does not test this. The lock check fails if it updates `pyproject.toml` without regenerating the lock.

## Image scans (C2)

- **Scan the SBOM.** Syft lists each built image's packages in SPDX JSON; Grype scans that list, so the inventory kept as an artifact is what the vulnerability report describes. Both tools are pinned by version and SHA-256 in `scripts/tools.sh`.
- **Fail only on fixable Critical and High.** Findings without a fixed version and lower severities are counted and reported without blocking publication. A failing finding needs an expiring exception for its vulnerability id and `<image>/<package>`, under the same gate as C1.
- **A fresh Grype database.** Each run checks for current advisories, including when neither the image nor its dependencies changed. Tool versions stay pinned; vulnerability data must keep moving.
- **Plain Docker commands.** The repository allows only GitHub-created actions, so `docker/*` actions cannot be used. Build, save, load, login and push run as Docker commands; the token is passed through standard input in the push step only.
- **Publish the scanned bytes.** The read-only scan job uses `docker save`; a separate job with `packages: write` uses `docker load` and pushes those images. Rebuilding after the scan could publish different packages from those checked.
- **Every main commit, an immutable commit tag.** Both images are published under the 12-character SHA, with no `latest`; local `REVISION` uses the same length. The job summary records digests for an exact reference. SHA tags are treated as immutable, but registry write access can still replace them; signing follows in C3.
- **Rescan published images weekly.** Pull main's images with `packages: read` and scan them against current advisories, without rebuilding. Keep SBOMs and reports for 90 days; the saved images passed between jobs need only one day.
- **`scan-images` outside `make verify`.** Building both images takes minutes. The explicit target and Images CI run the same scan without adding that build to every local verification.
- **Patch a base package until the base is rebuilt.** The first scan found CVE-2026-85091 in the console's zlib 1.3.2-r0. Install the fixed 1.3.2-r1 in the Dockerfile while nginx-unprivileged's pinned base lacks it, then remove the patch when an updated base digest includes it. brotli-libs 1.2.1-r0 (CVE-2026-111497, Critical) followed on 2026-10-25, the same way, while the newest base digest still carried 1.2.0-r1. curl and libcurl 8.23.0-r0 (CVE-2026-92392, High) followed on 2026-10-26, the same way.
- **Dependabot ignores runtime jumps.** Docker majors, Python image minors and Compose majors need a deliberate change; digest and patch updates still come. Its first Node 22 to 25 pull request was closed because 25 is not LTS.
- **npm majors arrive one by one.** The first grouped npm pull request (#52) mixed 18 minor and patch updates with four majors (TypeScript 5.9 to 7, eslint 9 to 10, msw 2 to 3, `@types/node` 24 to 26); `typescript-eslint` did not accept TypeScript 7, so `npm ci` failed and every safe update waited behind it. The group now takes minor and patch versions only, each major gets its own pull request, and `@types/node` majors are skipped because the console is built on Node 22.
- **eslint 10 first, `@eslint/js` 10 after.** Dependabot proposed them separately (#56, #58), and the first triage expected neither to install alone. #56 passed CI on its own once `eslint-plugin-react-hooks` 7.1.1 (#54) accepted eslint 10, and #58 followed after a rebase. TypeScript 7 (#57) stays ignored until `typescript-eslint` supports it; msw 3 (#55) waits.

## Image signing (C3)

- **Keyless signatures.** cosign signs each published image's digest in the publish job with a short-lived Sigstore certificate issued for the workflow's OIDC token, and the signature is logged in Rekor. No key pair exists to store, rotate or leak. The certificate names `images-ci.yml` on `refs/heads/main`, the commit and the `push` trigger, and verification checks each of them. The signature goes into the same GHCR package.
- **cosign as a pinned binary.** cosign 3.1.3 joins `scripts/tools.sh`, checked by SHA-256 like the other tools; `sigstore/cosign-installer` is not a GitHub-created action, so the repository's rules block it. 3.1.4 was five days old, inside the seven-day cooldown.
- **`actions/attest` for provenance and SBOM.** `actions/attest-sbom` is deprecated in favour of `actions/attest`, which also produces the SLSA build provenance, so one action, pinned by SHA, makes both attestations. Each is a signed in-toto statement on the image digest, pushed to GHCR next to the image. The SBOM attested is the one Grype scanned, passed from the scan job as an artifact. No storage record: GitHub creates those only for organization-owned repositories.
- **SLSA v1.0 Build Level 2, not 3.** GitHub's documentation states that artifact attestations by themselves provide Build Level 2, and that Level 3 needs the build in a reusable workflow isolated from the calling one ("Artifact attestations", docs.github.com, read 2026-10-25). Here the build runs in the same workflow, so the project claims Level 2.
- **One verification everywhere.** `scripts/verify-images.sh` resolves each tag to a digest once and then uses only that digest. It checks the cosign signature, then the provenance and the SBOM attestations with `gh attestation verify --bundle-from-oci`, all against exact identities: repository, workflow file, `refs/heads/main`, the full commit SHA and GitHub-hosted runners. It is used by `make up FROM=registry`, by the weekly rescan and by the publish job's last step, which reads the images back from the registry right after signing.
- **No bypass.** Any failed check stops before an image is pulled or tagged, and there is no flag to continue. The messages are detailed because the script runs only for the person operating the cluster.
- **`gh` needs a token.** `gh attestation verify` refuses to run without authentication, even when it reads the bundles from the registry, so `make up FROM=registry` needs `gh auth login`, and CI passes `GH_TOKEN`.
- **The chart still names a tag.** `make up FROM=registry` pulls by the verified digest and tags the images under the commit, so the chart and `make up` stay unchanged. Deploying by digest behind an admission policy (Kyverno or policy-controller) is phase E.
- **GHCR's first push of a new package.** In the first publication (#51), each new package's first push created it, public and linked to the repository, then answered `denied`; the next push worked (backend after two runs, console after three). This is observed behaviour, not something GitHub documents, and it happens only when a package is created.
- **Scanners speak again.** `--quiet` hid the error of a Syft or Grype run that failed on #54, so the scan no longer passes it.

## Lean pass after the audit

- **Code nothing reads goes.** A whole-repository audit listed code with no reader. Removed: the `APP_NAME`, `APP_ENV` and `APP_DEBUG` settings (the chart set `APP_ENV: production`, which changed nothing); `GET /users/admin-only`, kept since the RBAC foundation only for two tests, which now use `GET /admin/users`; `get_user_by_username`; the `get_organization`, `get_api_key` and `get_invitation` wrappers around `db.get`; the simulator's unused `Person.devices`; and in the console, the unused shadcn components and exports (`Badge`, `Tooltip` and its provider, six `DropdownMenu` parts, three `Card` parts, `AlertTitle`), three translation keys and the pass-through `ConfirmForm`. The `ADMIN_ENDPOINT_ACCESSED` and `ADMIN_ACCESS` enum values stay: migrations name them as downgrade fallbacks.
- **One copy of what must change together.** Sign-in's four outcomes wrote the same audit record and security event in four copies; one local `record` in `_sign_in` writes both now. The actor's role in messages has one `role_name`, shared by users and invitations. The sessions and user pages use the existing `ActionNotice` and `LoadFailed`; the simulator's `grant_admin` calls `change_role`.
- **Kept on purpose.** `hash_password` and `verify_password` only forward to `pwdlib`, but they keep password hashing in one place. The audit and event pairs in the services stay as they are: folding them would touch the sealed audit history for little gain.
- **A new file marks the build dirty.** `REVISION` in the `Makefile` read only `git diff`, so an image built with a new, uncommitted file under `backend/app` got the clean commit's tag. It now reads `git status --porcelain`, which also sees new files and still ignores what `.gitignore` and `.git/info/exclude` leave out.

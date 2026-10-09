# 01 - Backend Foundation

## Purpose
This document describes the initial foundation of the SentinelCore backend and the first technical decisions made to start the project on the right footing.

---

## What was done

### 1. Initial backend structure
The `backend/` directory was created, separate from the frontend, to keep the API and the server-side logic clearly delimited.

Current relevant structure:

```text
backend/
├── .venv/
├── app/
│   ├── api/
│   │   └── routes/
│   │       └── health.py
│   └── main.py
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

---

### 2. A dedicated virtual environment for the backend
A separate Python virtual environment is used, in `backend/.venv`.

Reasons:
- isolating the backend's dependencies
- avoiding conflicts with the system's global Python
- better control over the installed packages

---

### 3. Configuring the Python project with **pyproject.toml**
The backend was initialized as a modern Python project using **pyproject.toml**.

This file defines:
- the build system
- the project name
- the version
- the minimum Python version
- the initial minimal dependencies

Dependencies installed at this stage:
- fastapi
- uvicorn[standard]

---

### 4. Installing the backend in editable mode
Commands run:
- `pip install -e .`
- `python -m pip install -e .`

Purpose:
- installing the local project into the virtual environment
- being able to work iteratively, without a full reinstall after every change

---

### 5. The first working FastAPI application
`app/main.py` was created, with a minimal FastAPI application.

At first, the `/health` endpoint was defined directly in `main.py`; it was then moved to a separate router to keep the structure clean.

---

### 6. Separating the routes
A minimal router structure was introduced:
- `app/main.py` - the application's entry point
- `app/api/routes/health.py` - a dedicated router for the health check

This separation prepares the project to grow without crowding the main file.

---

### 7. A working health endpoint
The endpoint implemented:
- GET /health
The response returned:
- {"status": "ok"}

This endpoint confirms that:
- the application starts
- the server responds correctly
- the minimal backend structure works

---

### 8. Starting the backend locally
The backend was started locally with:
- python -m uvicorn app.main:app --reload
This is the project's standard local command at this point.

---

## Problems encountered and solutions

### Problem 1: invalid **pyproject.toml**
The first attempt to install the project failed with a TOML parse error.
Cause:
- invalid syntax in `pyproject.toml`, because of a missing quote
Solution:
- the file was corrected and validated
- the editable install worked after the fix

---

### Problem 2: **uvicorn** run from the wrong context
The first server run failed with `ModuleNotFoundError: No module named 'fastapi'`, even though FastAPI was installed in the virtual environment.
Cause:
- the `uvicorn...` command used the wrong executable / the wrong system context
Solution:
- the server was run with `python -m uvicorn app.main:app --reload`
- this way, the Python interpreter from `.venv` is used

---

## What was learned at this stage
This stage clarified the following concepts:
- the role of `pyproject.toml`
- the difference between the global Python and the virtual environment's Python
- the importance of running Python tools through `python -m...`
- the separation between the application's entry point and dedicated routers
- the role of a health check endpoint in validating the backend foundation

---

## State at the end of the stage
At the end of this stage, the SentinelCore backend has:
- a configured Python project
- the minimal dependencies installed
- a working virtual environment
- a working FastAPI application
- a separate router for `/health`
- a validated local startup

---

## Next step
The next step after this foundation is configuring the database connection and defining the application's first real model.

### 9. Local PostgreSQL with Docker Compose
A local PostgreSQL service was configured with Docker Compose.

Purpose:
- a reproducible environment
- a controlled local setup
- a foundation for developing the backend and testing the models

The local database was started and checked successfully.

### 10. Testing a real database connection
The real connection to PostgreSQL was validated by running a simple query:

```sql
SELECT 1
```

The result confirmed:
- a working PostgreSQL server
- a valid connection URL
- a working **psycopg** driver
- a correct connection through SQLAlchemy

### 11. The first ORM model: **User**
The application's first real model was introduced: **User**

Fields defined:
- id
- username
- email
- hashed_password
- is_active
- created_at
- updated_at
Important constraints:
- unique username
- unique email
- required fields for the essential data
This model is the first central entity of the SentinelCore system.

### 12. Creating the first database table
The **users** table was created in PostgreSQL with:
```python
Base.metadata.create_all(bind=engine)
```
The result was checked directly in PostgreSQL with:
- \dt
- \d users
It confirmed that the table and the columns defined in the model exist.

### 13. Problem encountered: inconsistent imports
On the first attempt, the **users** table was not created, even though the model existed.
Cause:
- the project used inconsistent imports:
  - some starting from **app...**
  - others starting directly from **core...** or **models...**
This loaded the modules separately and produced different instances of **Base**, so **create_all()** did not see the **User** model.
Solution:
- imports were standardized on the absolute form, starting from **app**
- for example:
  - from app.core.database import Base
  - from app.models.user import User
This decision must be kept consistently across the whole backend.

### 14. Current state of the backend
At this point the backend has:
- a working FastAPI application
- a working health check
- configuration through .env
- a working PostgreSQL connection
- an initial ORM layer
- the User model
- the users table, created and validated

## Extending the backend foundation: schemas, services and the first real authentication flow

### 15. Pydantic schemas for the user
The `app/schemas/` directory and `app/schemas/user.py` were created.

Two initial schemas were defined:
- `UserCreate` - the input needed to create a user
- `UserRead` - the output sent to the client

Purpose of this separation:
- a clear difference between the ORM model and the API contract
- control over the data accepted in requests
- control over the data returned in responses
- explicitly excluding the `hashed_password` field from API responses

### 16. A dependency for the DB session, and password hashing
`app/api/deps.py` was created, with the `get_db()` dependency that provides the database session to endpoints.
`app/core/security.py` got the `hash_password()` function, based on `pwdlib`.

Purpose:
- passwords are never stored in raw form
- hashing is centralized in one dedicated place
- the security logic is not scattered across endpoints

### 17. A service layer for the user
The `app/services` directory and `app/services/user_service.py` were created.

Functions defined:
- `get_user_by_email()`
- `get_user_by_username()`
- `create_user()`

Purpose of the `services` layer:
- moving business logic out of the endpoints
- a clear separation between the route, DB access and business rules
- preparing the architecture for later growth

### 18. The first real endpoint: register
`app/api/routes/auth.py` was created.

The endpoint introduced:

```http
POST /auth/register
```
It:
- takes `UserCreate` input
- uses `get_db()` for the database session
- checks whether a user with the same email exists
- checks whether a user with the same username exists
- creates the user if the data is valid and unique
- returns the user's data through the `UserRead` schema

### 19. Validating the register flow
The registration flow was tested through Swagger UI (`/docs`).
Confirmed results:
- user created successfully -> `201 Created`
- attempt to create a duplicate user -> `400 Bad Request`
- the `/health` endpoint keeps working alongside
This confirms the backend's first complete end-to-end flow:
- HTTP request
- input validation
- DB access
- business logic
- password hashing
- persistence in PostgreSQL
- a controlled response model

### 20. Current relevant backend structure
```text
backend/app/
├── api/
│   ├── deps.py
│   └── routes/
│       ├── auth.py
│       └── health.py
├── core/
│   ├── config.py
│   ├── database.py
│   └── security.py
├── models/
│   └── user.py
├── schemas/
│   └── user.py
├── services/
│   └── user_service.py
└── main.py
```

### 21. Current state of the backend
At this point the backend has:
- a working FastAPI application
- the `/health` endpoint
- the `POST /auth/register` endpoint
- configuration through `.env`
- a working PostgreSQL connection
- the `User` ORM model
- the `users` table, created and validated
- password hashing
- a `schemas` layer
- a `services` layer
- a first real, validated user creation flow

## Extending the backend foundation: login and JWT

### 22. Extending security with password verification
`app/core/security.py` was extended with the `verify_password()` function.

Purpose:
- comparing a password entered by the user with the hashed value stored in the database
- keeping password verification separate from endpoints and services
- keeping the security responsibilities in one dedicated module
This function complements `hash_password()` and makes the authentication flow possible.

### 23. The login schema
`app/schemas/user.py` was extended with the `UserLogin` schema.

It defines the data needed to authenticate:
- `email`
- `password`

Purpose:
- a clear separation between the register contract and the login contract
- validating the authentication input with Pydantic

### 24. The token schema
`app/schemas/user.py` was also extended with the `Token` schema.
It defines the login endpoint's response:
- `access_token`
- `token_type`

Purpose:
- standardizing the authentication response
- preparing to use the JWT on protected endpoints later

### 25. Extending the application settings for JWT
`.env.example` and `.env` were extended with JWT settings:
- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_TIME`
`app/core/config.py` was updated to read these values.

Purpose:
- configuring token issuance in one central place
- avoiding hardcoded security values in the code

### 26. Generating the JWT
`app/core/security.py` was extended with the `create_access_token()` function.

It:
- builds the token payload
- includes the `sub` claim
- includes the `exp` claim
- signs the token using the configuration from `Settings`

Purpose:
- issuing a valid JWT after a successful authentication
- preparing the base for protected endpoints

### 27. Authentication in the service layer
`app/services/user_service.py` was extended with the `authenticate_user()` function.

It:
- looks up the user by email
- checks the password with `verify_password()`
- returns the user when authentication succeeds
- returns `None` when authentication fails

Purpose:
- keeping the authentication logic out of the endpoint
- reusing the logic in a clear, testable way

### 28. The login endpoint
`app/api/routes/auth.py` was extended with the endpoint:
```http
POST /auth/login
```
It:
- takes `UserLogin` input
- uses the DB session through `get_db()`
- validates the credentials with `authenticate_user()`
- issues a JWT with `create_access_token()`
- returns a `Token` response

### 29. Validating the login flow
The authentication flow was tested through Swagger UI (`/docs`).

Confirmed results:
- valid login -> `200 OK`
- login with a wrong password -> `401 Unauthorized`
The response for a valid login includes:
- `access_token`
- `token_type = "bearer"`
This confirms the authentication flow works end to end:
- input validation
- checking the user in the DB
- checking the hashed password
- generating the JWT
- a standardized response for the client

### 30. Current state of the backend
At this point the backend has:
- a working FastAPI application
- the `/health` endpoint
- the `POST /auth/register` endpoint
- the `POST /auth/login` endpoint
- configuration through `.env`
- a working PostgreSQL connection
- the `User` ORM model
- the `users` table, created and validated
- password hashing and verification
- JWT generation
- a `schemas` layer
- a `services` layer
- a complete register flow
- a complete login flow

### Practical note
At this stage, the JWT uses the user's email as its `subject` (`sub`). This is enough for the MVP; the token's main identifier can be revisited later if a stricter strategy is needed.

## Extending the backend foundation: current user and RBAC (Role-Based Access Control)

### 31. Decoding the JWT
`app/core/security.py` was extended with the `decode_access_token()` function.

It:
- decodes the JWT
- validates the token's signature
- validates the token's expiry
- returns the payload when the token is valid

Purpose:
- actually consuming the token issued at login
- preparing the protected endpoints
- keeping the JWT logic separate from the rest of the application

### 32. A dependency for the current user
`app/api/deps.py` was extended with:
- `oauth2_scheme`
- `get_current_user()`

Their role:
- extracting the Bearer token from the request
- validating the token
- extracting the user's identity from the `sub` claim
- looking up the real user in the database
- returning the current user when authentication is valid

At this stage, the `sub` claim holds the user's email.

### 33. The first protected endpoint
`app/api/routes/users.py` was created.

The endpoint introduced:
```http
GET /users/me
```
It:
- requires a valid JWT
- uses `get_current_user()`
- returns the authenticated user through the `UserRead` schema
Purpose:
- validating that the token is actually consumed
- confirming that authentication works not only when the token is issued, but also when it is used

### 34. The RBAC foundation
The `User` model was extended with a `role` field.
Roles are defined by the `UserRole` enum, with the values:
- `user`
- `admin`
- `security_analyst`
- `owner`
Purpose:
- introducing role-based access control
- clearly separating user types from the MVP on
- preparing the system for endpoints that differ by role

### 35. Resetting the local database for the schema change
To add the `role` column to the `users` table, the local database was reset.
A local reset through Docker Compose was used, because the project does not yet manage schema changes with Alembic migrations.
This approach is acceptable at this stage, since the local data has no operational value yet.

### 36. A default role for new users
When a new user is created through the register flow, the role defaults to:
```text
user
```
This defines the standard behavior for regular users and avoids accidentally granting elevated privileges.

### 37. Exposing the role in the output schema
The `UserRead` schema was extended with the `role` field.

Purpose:
- visibility of the user's role in API responses
- validating the RBAC behavior properly
- preparing the interface to show the role in the frontend later

### 38. Role-based authorization
`app/api/deps.py` was extended with the `require_role()` function.

It:
- takes one or more allowed roles
- checks the authenticated user's role
- returns `403 Forbidden` when the user has no access
- lets the request continue when the role is accepted

Purpose:
- separating authentication from authorization
- defining a reusable mechanism for protecting endpoints

### 39. An admin-only endpoint
`app/api/routes/users.py` was extended with the endpoint:
```http
GET /users/admin-only
```
It:
- requires an authenticated user
- allows access only for the authorized roles (`admin` and `owner` in the current implementation)
- returns a valid response only when the user has the required permission

### 40. Validating the RBAC behavior
The RBAC behavior was tested with authenticated requests.
Confirmed results:
- a user with the `user` role -> `403 Forbidden`
- a user with the `admin` role -> `200 OK`

This confirms:
- the `get_current_user()` dependency works correctly
- the `require_role()` dependency works correctly
- authentication and authorization are clearly separated

### 41. Current state of the backend
At this point the backend has:
- a working FastAPI application
- the `/health` endpoint
- the `POST /auth/register` endpoint
- the `POST /auth/login` endpoint
- the `GET /users/me` endpoint
- the `GET /users/admin-only` endpoint
- configuration through `.env`
- a working PostgreSQL connection
- the `User` ORM model
- the `users` table, created and validated
- password hashing and verification
- JWT generation and decoding
- a `schemas` layer
- a `services` layer
- a complete register flow
- a complete login flow
- identifying the current user from the token
- a working RBAC foundation

### Practical note on testing protected endpoints
In the current implementation, the login endpoint takes JSON input, not a standard OAuth2 form. Because of that, the `Authorize` mechanism in Swagger UI does not fully match the login flow, and the protected endpoints were tested with manual requests (`curl`).

This is an integration limit of the interactive documentation, not a backend problem.

## Extending the backend foundation: Audit Logging

### 42. The `AuditLog` model
The `AuditLog` ORM model was created in:

```text
app/models/audit_log.py
```
This model is the base of SentinelCore's audit mechanism.

The purpose of auditing is to record the important actions in the system, especially those related to authentication, access and security-relevant events.

The `AuditLog` model has these fields:
- `id`
- `event_type`
- `user_id`
- `email`
- `message`
- `created_at`

### 43. Audit event types

The `AuditEventType` enum was defined.

The initial events are:

- `USER_REGISTERED`
- `LOGIN_SUCCESS`
- `LOGIN_FAILED`
- `ADMIN_ENDPOINT_ACCESSED`

Purpose:

- avoiding values typed by hand in several places
- reducing the risk of typos
- a controlled definition of the audit event types

Note:

At this stage, the enum values are stored in the database as the enum member names, for example `USER_REGISTERED`, not in the lowercase form `user_registered`. This behavior is acceptable for the MVP.

### 44. Creating the `audit_logs` table

The `audit_logs` table was created in PostgreSQL with the temporary mechanism:

```python
Base.metadata.create_all(bind=engine)
```

For SQLAlchemy to detect the model, `AuditLog` was imported in `app/main.py`.

The table was checked in PostgreSQL with:

```text
\dt
\d audit_logs
```

The result confirmed the `audit_logs` table and its foreign key to the `users` table.

### 45. Structure of the `audit_logs` table

The `audit_logs` table contains:

- `id` - the event's unique identifier
- `event_type` - the type of audit event
- `user_id` - an optional reference to the user
- `email` - the email tied to the event, useful especially for failed logins
- `message` - a human-readable description of the event
- `created_at` - when the event happened

The `user_id` field is optional because some events, such as a failed login with an unknown email or a wrong password, can exist without a valid authenticated user.

### 46. The audit service

The file created:

```text
app/services/audit_service.py
```

It contains the function:

```text
create_audit_log()
```

The service centralizes the logic for creating audit events.

This avoids duplicating code like:

- creating an `AuditLog` object
- `db.add(...)`
- `db.commit()`
- `db.refresh(...)`

across several endpoints.

### 47. Auditing the register flow

The endpoint:
```http
POST /auth/register
```
was extended so that, after a user is created successfully, it creates an audit event of type `USER_REGISTERED`.

This event confirms that user registration is tracked in the system.

### 48. Auditing successful logins

The endpoint:
```http
POST /auth/login
```
creates an audit event of type `LOGIN_SUCCESS` when authentication is valid.

This event confirms that successful logins are tracked in the system.

### 49. Auditing failed logins

The endpoint:
```http
POST /auth/login
```
creates an audit event of type `LOGIN_FAILED` when authentication fails.

This case matters because failed login attempts can later become the base for security detections, such as brute force or suspicious activity.

Here, the audit log can contain the attempted email even when there is no valid authenticated user.

### 50. Auditing the admin-only endpoint

The endpoint:
```http
GET /users/admin-only
```
creates an audit event of type `ADMIN_ENDPOINT_ACCESSED` when a user with an allowed role accesses it.

At this stage, allowed access is audited. Access refused with `403 Forbidden` is not audited yet.

### 51. Validating the audit in the database

The audit was validated in PostgreSQL with the query:
```sql
SELECT id, event_type, user_id, email, message, created_at
FROM audit_logs
ORDER BY id;
```

These events were confirmed:
- `USER_REGISTERED`
- `LOGIN_SUCCESS`
- `LOGIN_FAILED`
- `ADMIN_ENDPOINT_ACCESSED`

This confirms that auditing works for real application flows.

### 52. Current state after Audit Logging

At this point the backend has:
- a working FastAPI application
- the `/health` endpoint
- the `POST /auth/register` endpoint
- the `POST /auth/login` endpoint
- the `GET /users/me` endpoint
- the `GET /users/admin-only` endpoint
- configuration through `.env`
- local PostgreSQL through Docker Compose
- the `User` ORM model
- the `AuditLog` ORM model
- the `users` table
- the `audit_logs` table
- password hashing and verification
- JWT generation and decoding
- identifying the current user from the token
- a working RBAC foundation
- working audit logging for register, login and admin access

## Extending the backend foundation: Audit Logs API

### 53. The `AuditLogRead` schema

The file created:

```text
app/schemas/audit_log.py
```

It defines the `AuditLogRead` schema, used for the API responses that expose audit events.

Purpose:

- separating the `AuditLog` ORM model from the API contract
- controlling the fields returned to the client
- preparing the audit logs for display in future dashboards

### 54. Listing audit logs in the service

`app/services/audit_service.py` was extended with the function:

```text
list_audit_logs()
```

It:

- reads the audit events from the database
- orders them by descending `created_at`
- applies a limit, to avoid returning the whole table

### 55. The audit logs endpoint

The file created:

```text
app/api/routes/audit.py
```

The endpoint introduced:

```http
GET /admin/audit-logs
```
It lets clients read the audit events through the API.

The endpoint accepts the `limit` parameter, to control how many results are returned.

### 56. Protecting the audit endpoint with RBAC

`GET /admin/audit-logs` is protected by `require_role(...)`.

The allowed roles are:

- `admin`
- `owner`
- `security_analyst`

A standard user with the `user` role cannot access this endpoint.

### 57. Validating the audit endpoint

The endpoint was tested with `curl`.

Confirmed results:

- a user with the `admin` role -> `200 OK`
- a user with the `user` role -> `403 Forbidden`

This confirms:

- listing audit logs through the API
- the endpoint's RBAC protection
- the correct separation between a regular user and the privileged roles

### 58. Current state after the Audit Logs API

At this point the backend has:

- audit logs stored in PostgreSQL
- audit logs readable through the API
- the `GET /admin/audit-logs` endpoint
- RBAC protection for access to audit logs
- functional validation for an admin and a regular user

## Extending the backend foundation: Security Events

### 59. The `SecurityEvent` model

The `SecurityEvent` ORM model was created in `app/models/security_event.py`.

This model is the first security event layer of the SentinelCore platform.

Unlike `AuditLog`, which records the system's actions as facts, `SecurityEvent` holds the events relevant to security and SIEM-light.

The `SecurityEvent` model has these fields:

- `id`
- `event_type`
- `severity`
- `user_id`
- `email`
- `source`
- `message`
- `created_at`

### 60. The difference between Audit Logs and Security Events

In SentinelCore, the two concepts are separate:

**Audit Logs**
Audit logs answer the question:

```text
What happened in the system?
```

Examples:
- a user was created
- a successful login
- a failed login
- an admin endpoint was accessed

**Security Events**
Security events answer the question:

```text
Which events matter for security?
```

Examples:
- a failed login with `warn` severity
- a successful login with `info` severity
- admin access with `info` severity

This separation matters because the audit is the raw journal, while security events are the interpretation layer for SIEM-light.

### 61. Security event types

The `SecurityEventType` enum was defined.

The initial events are:
- `USER_REGISTERED`
- `LOGIN_SUCCESS`
- `LOGIN_FAILED`
- `ADMIN_ACCESS`

They cover the first real flows that already exist in the backend:
- register
- successful login
- failed login
- admin access

### 62. Security severities

The `SecuritySeverity` enum was defined.

The initial severities are:
- `INFO`
- `WARN`
- `INCIDENT`

At this stage they are used as:
- `INFO` for normal but relevant events
- `WARN` for a failed login

The `INCIDENT` severity is ready for more serious future events, such as brute-force detections or suspicious behavior.

### 63. Creating the `security_events` table

The `security_events` table was created in PostgreSQL with the temporary mechanism:

```python
Base.metadata.create_all(bind=engine)
```

For SQLAlchemy to detect the model, `SecurityEvent` was imported in `app/main.py`.

The table was checked in PostgreSQL with:

```text
\dt
\d security_events
```

### 64. The security events service

The file created:

```text
app/services/security_event_service.py
```

It contains the functions:

```text
create_security_event()
list_security_events()
```

The service centralizes the logic for creating and reading security events.

`create_security_event()` saves an event with:
- an event type
- a severity
- an optional associated user
- an optional associated email
- a source
- a descriptive message

`list_security_events()` reads the security events in descending order of when they happened.

### 65. The `SecurityEventRead` schema

The file created: `app/schemas/security_event.py`.

It defines the `SecurityEventRead` schema.

Purpose:
- separating the ORM model from the API response
- controlling the fields returned to the client
- preparing the data for future security dashboards

### 66. The security events endpoint

The file created: `app/api/routes/security.py`.

The endpoint introduced: `GET /security/events`.

It lets clients read the security events through the API.

The endpoint accepts the `limit` parameter, to bound the number of events returned.

### 67. Protecting the security events endpoint with RBAC

`GET /security/events` is protected by `require_role(...)`.

The allowed roles are:
- `admin`
- `owner`
- `security_analyst`

A standard user with the `user` role has no access to this endpoint.

### 68. Adding security events to the existing flows

Security events were added to these flows:

**Register**
Creating a new user creates the `USER_REGISTERED` event, with `INFO` severity.

**Successful login**
A successful authentication creates the `LOGIN_SUCCESS` event, with `INFO` severity.

**Failed login**
A failed authentication creates the `LOGIN_FAILED` event, with `WARN` severity.
This event matters because it can later become the base for brute-force detections.

**Admin access**
Accessing the admin-only endpoint creates the `ADMIN_ACCESS` event, with `INFO` severity.

### 69. Validating `GET /security/events`

The endpoint was tested with `curl`.

Confirmed results:
- a user with an allowed role -> `200 OK`
- the response contains real security events
- the events are returned as JSON
- the severities appear correctly as `info` and `warn`

Events confirmed in the response:
- `user_registered`
- `login_success`
- `login_failed`
- `admin_access`

### 70. Current state after the Security Events Foundation

At this point the backend has:

- a working FastAPI application
- the `/health` endpoint
- the `POST /auth/register` endpoint
- the `POST /auth/login` endpoint
- the `GET /users/me` endpoint
- the `GET /users/admin-only` endpoint
- the `GET /admin/audit-logs` endpoint
- the `GET /security/events` endpoint
- configuration through `.env`
- local PostgreSQL through Docker Compose
- the `User` ORM model
- the `AuditLog` ORM model
- the `SecurityEvent` ORM model
- the `users` table
- the `audit_logs` table
- the `security_events` table
- password hashing and verification
- JWT generation and decoding
- identifying the current user from the token
- a working RBAC foundation
- working audit logging
- working security events
- a first working SIEM-light layer

## Extending the backend foundation: Alembic Migrations

### 71. Moving from `create_all()` to migrations

Until this stage, the database schema was created temporarily with `Base.metadata.create_all(bind=engine)`.

This mechanism was useful to validate the models at first and to understand the link between SQLAlchemy and PostgreSQL.

Once the main models (`User`, `AuditLog`, `SecurityEvent`) existed, the mechanism was removed from `app/main.py`.

From now on, the database schema is managed by Alembic.

### 72. Why Alembic

Alembic was introduced for:
- versioning the database schema
- avoiding repeated local resets
- managing future model changes through migrations
- bringing the project closer to a real backend development workflow
- separating the application's responsibility from the DB schema's

The FastAPI application no longer has to create tables at startup.

### 73. Initializing Alembic

Alembic was initialized in the backend.

Created:
- `alembic.ini`
- the `migrations/` directory
- the `migrations/versions/` directory
- `migrations/env.py`
- the migration template

### 74. Configuring Alembic's database connection

In `alembic.ini`, the connection to the local PostgreSQL was configured as:

```ini
sqlalchemy.url = postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/sentinelcore
```

This lets Alembic connect to the local database to generate and apply migrations.

> Update ("My account" stage): the URL is no longer written in `alembic.ini`. `migrations/env.py` takes it from `settings.database_url`, that is from `DATABASE_URL` (environment or `.env`), the same setting the application uses. Before, `DATABASE_URL=... alembic upgrade head` was ignored and the migration always ran against the `sentinelcore` database.

### 75. Connecting Alembic to the SQLAlchemy models

In `migrations/env.py`, Alembic was connected to the SQLAlchemy metadata.

`Base` was imported with `from app.core.database import Base`, along with the modules holding the main models:

```python
from app.models import audit_log, security_event, user  # noqa: F401
```

The import is needed even though the modules are not used directly: just by being imported, the models register themselves in `Base.metadata`. Without it, `--autogenerate` sees an empty schema and would propose dropping every table. The `# noqa: F401` comment stops Ruff from removing the import as unused.

Then `target_metadata` was set to `target_metadata = Base.metadata`.

This lets `--autogenerate` compare the SQLAlchemy models with the real schema in the database.

### 76. Resetting the local database for the initial migration

Since the environment is still local and the data has no operational value, the database was reset before the initial migration.

Commands used:
```bash
docker compose down -v
docker compose up -d
```

This reset made it possible to start from an empty PostgreSQL database, so the initial schema is created solely by Alembic.

### 77. Generating the initial migration

The initial migration was generated with:

```bash
python -m alembic revision --autogenerate -m "initial schema"
```

Alembic detected the models and generated a migration file in `migrations/versions`.

The initial migration contains the schema for:
- `users`
- `audit_logs`
- `security_events`
- the related enum types
- the indexes defined on the models
- the foreign keys between the tables

### 78. Applying the initial migration

The initial migration was applied with `python -m alembic upgrade head`.

After it ran, Alembic also created the `alembic_version` table.

It stores the current version of the database schema.

### 79. Checking the result in PostgreSQL

The database schema was checked in PostgreSQL with `SELECT * FROM alembic_version;`.

The result confirmed that the database is at the version of the initial migration.

### 80. The standard workflow for future schema changes

From now on, every change to the SQLAlchemy models goes through Alembic.

The standard workflow is:

```bash
python -m alembic revision --autogenerate -m "describe the change"
python -m alembic upgrade head
```

Generated migrations must be reviewed by hand before they are applied.

`--autogenerate` helps, but it does not replace the developer's own reasoning.

### 81. Current state after Alembic

At this point the backend has:

- a working FastAPI application
- local PostgreSQL through Docker Compose
- the database schema managed by Alembic
- `create_all()` removed from `main.py`
- the initial migration generated and applied
- the `alembic_version` table created
- the `users`, `audit_logs` and `security_events` tables created by migration
- a mature workflow for future DB schema changes

## Extending the backend foundation: Tests Foundation

### 82. Automated tests

The first automated test foundation for the SentinelCore backend was introduced.

The goal of this stage is to move from manual testing with `curl` / Swagger to automated validation of the main flows.

Dependencies added:
- `pytest`
- `httpx`

They make it possible to run automated tests and to use `TestClient` to test the FastAPI application.

### 83. Configuring `pyproject.toml` for tests

`pyproject.toml` was updated for testing.

The configuration added:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Purpose:
- tests are looked up in the `tests` directory
- absolute imports such as `from app...` work during tests

Explicit discovery of the Python package was configured too:
```toml
[tool.setuptools.packages.find]
include = ["app*"]
exclude = ["migrations*", "tests*"]
```

This was needed because, after Alembic was added, `setuptools` detected both `app` and `migrations` as top-level packages.

### 84. A separate database for tests

A separate database was created for tests: `sentinelcore_test`.

Purpose:
- the tests do not change the development database
- the test data is isolated
- the tests can create and delete data with no risk to the main local environment

The variable added:
```env
TEST_DATABASE_URL=postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/sentinelcore_test
```
in the local configuration and in `.env.example`.

### 85. `tests/conftest.py`

The file created: `tests/conftest.py`.

It defines reusable fixtures for the tests.

Main elements:
- `test_engine`
- `TestingSessionLocal`
- the `db_session` fixture
- the `client` fixture

Purpose:
- connecting the tests to the `sentinelcore_test` database
- creating the tables before a test
- dropping the tables after a test
- overriding the `get_db` dependency
- running requests through `TestClient`

### 86. Overriding `get_db`

In tests, the real `get_db()` dependency is overridden with a test session.

Purpose:
- the endpoints use the test database
- the application logic is tested almost as in reality
- the tests never touch the main database

This makes it possible to test FastAPI endpoints without starting a separate HTTP server.

### 87. A test for the `/health` endpoint

The test created: `tests/test_health.py`.

It checks the endpoint:
```http
GET /health
```

Expected result:
```json
{"status": "ok"}
```
This test confirms that the FastAPI application imports correctly and that the health router works.

### 88. Tests for register

The file created: `tests/test_auth.py`.

These scenarios were validated:

**Valid register**
Endpoint tested:
```http
POST /auth/register
```

Expected result:
- status `201 Created`
- a user created with `username` and `email`
- `hashed_password` is not returned in the response

**Register with a duplicate email**

Expected result:
- status `400 Bad Request`
- message: `Email already registered`

### 89. Tests for login

These scenarios were validated:

**Valid login**

Endpoint tested:
```http
POST /auth/login
```

Expected result:
- status `200 OK`
- the response contains `access_token`
- `token_type` is `bearer`

**Login with a wrong password**

Expected result:
- status `401 Unauthorized`
- message: `Invalid email or password`

### 90. Running the tests

The tests were run with:
```bash
python -m pytest
```

Confirmed result:
```text
5 passed
```

This confirms that the first round of automated tests works.

### 91. Current state after Tests Foundation Phase 1

At this point the backend has:
- an automated test for `/health`
- automated tests for register
- automated tests for login
- a separate database for tests
- a fixture for the test DB session
- an override for `get_db`
- a working `TestClient`
- automated runs through `pytest`

This marks the move from manual testing to a first automated safety net for the backend.

## Extending the backend tests: Tests Foundation Phase 2

### 92. The goal of testing phase 2

Once the basic endpoints (`/health`, register and login) were validated, the tests were extended to the application's protected routes.

This phase validates automatically:
- JWT authentication
- access to protected endpoints
- the behavior without a token
- role-based access control
- admin access to audit logs
- admin access to security events

This stage confirms that the IAM and RBAC mechanisms work not only by hand, but also in automated tests.

### 93. A new file for protected routes

The file created:
```text
tests/test_protected_routes.py
```

It contains tests for the endpoints that require authentication or special roles.

### 94. Helper functions for tests

`test_protected_routes.py` introduced helper functions to reduce duplicated code:

```python
register_user()
login_user()
auth_headers()
promote_user_to_admin()
```

These functions:
- quickly create a test user
- authenticate the user and obtain the JWT
- build the `Authorization` header
- promote a user to the `admin` role directly in the test database

### 95. Testing `/users/me`

The endpoint tested:

```http
GET /users/me
```

Scenarios validated:

**With a valid token**
Expected result:
- status `200 OK`
- the response contains the authenticated user's data
- `hashed_password` is not returned in the response

**Without a token**
Expected result:
- status `401 Unauthorized`

This test confirms the endpoint is protected and allows no anonymous access.

### 96. Testing `/users/admin-only`

The endpoint tested:
```http
GET /users/admin-only
```

Scenarios validated:

**Regular user**
Expected result:
- status `403 Forbidden`

This test confirms that an authenticated user without a suitable role cannot access the admin route.

**Admin user**
Expected result:
- status `200 OK`
- the response confirms the admin user
- the role returned is `admin`

This test validates the RBAC foundation.

### 97. Promoting the user to admin in tests

Since the application has no dedicated endpoint for changing a user's role yet, the promotion to admin is done directly in the test database:

```python
user.role = UserRole.ADMIN
db_session.commit()
```

This is acceptable in tests, because it is only test setup, not production logic.

In the real application, role changes will later go through controlled, audited administrative endpoints.

### 98. Testing the audit logs endpoint

The endpoint tested:

```http
GET /admin/audit-logs?limit=20
```

Scenario validated:
- an authenticated admin user
- status `200 OK`
- the response is a list

This test confirms that the authorized roles can read the audit logs through the API.

### 99. Testing the security events endpoint

The endpoint tested:

```http
GET /security/events?limit=20
```

Scenario validated:
- an authenticated admin user
- status `200 OK`
- the response is a list

This test confirms that the authorized roles can read the security events through the API.

### 100. Tests validated in Phase 2

This phase validated these scenarios:
```text
/users/me with token            -> 200
/users/me without token         -> 401
/users/admin-only regular user  -> 403
/users/admin-only admin         -> 200
/admin/audit-logs admin         -> 200
/security/events admin          -> 200
```

Together with the Phase 1 tests, the backend now has automated tests for:
```text
/health                         -> 200
/auth/register                  -> 201
/auth/register duplicate email  -> 400
/auth/login                     -> 200 + token
/auth/login wrong password      -> 401
/users/me with token            -> 200
/users/me without token         -> 401
/users/admin-only regular user  -> 403
/users/admin-only admin         -> 200
/admin/audit-logs admin         -> 200
/security/events admin          -> 200
```

### 101. Test results

The tests were run with:
```bash
python -m pytest -v
```

Confirmed result:

```text
11 passed
```

This confirms that the authentication, authorization and protected endpoint foundation is validated automatically.

### 102. Current state after Tests Foundation Phase 2

At this point the backend has:
- automated tests for the health check
- automated tests for register
- automated tests for login
- automated tests for protected endpoints
- automated tests for JWT access
- automated tests for access without a token
- automated tests for user/admin RBAC
- automated tests for the audit logs endpoint
- automated tests for the security events endpoint
- a separate database for tests
- an override for `get_db`
- test setup in `conftest.py`
- 11 passing automated tests

This stage marks the SentinelCore backend's move from manual testing to automated checks for the main IAM/RBAC flows.

## Backend CI Pipeline - Phase 1

### 103. CI for the backend

The first Continuous Integration workflow for the SentinelCore backend was introduced.

The goal of this stage is for the backend tests to run automatically in GitHub Actions whenever relevant code changes.

Until this stage, the tests ran locally with:

```bash
python -m pytest -v
```

With CI, the tests also run automatically on GitHub, which gives the backend a reproducible check.

### 104. The workflow file

The file created:

```text
.github/workflows/backend-ci.yml
```

It defines the pipeline that tests the backend.

The workflow is named:

```yaml
name: Backend CI
```

### 105. Workflow triggers

The workflow runs automatically on:

- `push` to the `main` branch
- `pull_request` to the `main` branch

The trigger is limited by `paths`, so the pipeline runs only when files relevant to the backend or to the CI workflow change.

The configuration used:

```yaml
on:
  workflow_dispatch:

  push:
    branches:
      - main
    paths:
      - "backend/**"
      - ".github/workflows/backend-ci.yml"

  pull_request:
    branches:
      - main
```

At first, the `paths` filter also applied to `pull_request`. It was removed later, so every pull request to `main` runs CI.

`workflow_dispatch` was kept, so the workflow can be run by hand from the GitHub Actions interface.

### 106. PostgreSQL as a service in GitHub Actions

Since the backend tests use the database, the workflow starts a PostgreSQL service automatically.

The service uses the image:

```yaml
postgres:16
```

The image was later aligned to `postgres:17`, the same version used locally in Docker Compose.

The main configuration:

```yaml
POSTGRES_USER: sentinelcore
POSTGRES_PASSWORD: sentinelcore
POSTGRES_DB: sentinelcore_test
```

The database used in CI is:

```text
sentinelcore_test
```

This keeps the same strategy as locally: the tests never run against the development database.

### 107. A health check for PostgreSQL

The workflow configures a health check for PostgreSQL:

```yaml
--health-cmd="pg_isready -U sentinelcore -d sentinelcore_test"
--health-interval=10s
--health-timeout=5s
--health-retries=5
```

It makes the job wait until PostgreSQL is ready before running the tests.

### 108. Environment variables for CI

The workflow defines the variables needed to run the application and the tests:

```yaml
TEST_DATABASE_URL: postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/sentinelcore_test
DATABASE_URL: postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/sentinelcore_test
SECRET_KEY: ci-test-secret-key-for-sentinelcore-minimum-32-bytes
ALGORITHM: HS256
ACCESS_TOKEN_EXPIRE_MINUTES: 30
```

`TEST_DATABASE_URL` is used by the automated tests.
`DATABASE_URL` is set so the application imports correctly in CI.
`SECRET_KEY` is set to a value long enough to avoid the warnings about the minimum recommended length for HMAC SHA256.

### 109. Workflow steps

The workflow runs these steps:

1. checkout the repository
2. set up Python
3. install the backend dependencies
4. run the backend tests

The main steps:

```yaml
- name: Checkout repository
  uses: actions/checkout@v5

- name: Set up Python
  uses: actions/setup-python@v6
  with:
    python-version: "3.12"

- name: Install backend dependencies
  working-directory: backend
  run: |
    python -m pip install --upgrade pip
    python -m pip install -e .

- name: Run backend tests
  working-directory: backend
  run: |
    python -m pytest -v
```

### 110. Problem encountered: missing `pydantic[email]`

On the first CI run, the workflow failed because the GitHub Actions environment did not have the support Pydantic needs to validate email fields.

The problem showed that the local environment had the dependencies available, but the project did not fully declare its requirements in `pyproject.toml`.

The dependency was added to `backend/pyproject.toml`.

Lessons from this stage:
- CI must be able to reproduce the project's environment from the versioned files alone
- the dependencies the application uses must be declared explicitly
- never rely on what happens to be installed in the local environment

### 111. JWT warning fixed

While the tests ran, PyJWT printed a warning about the HMAC key used for `HS256` being too short.

The problem came from:

```yaml
SECRET_KEY: test-secret-key-for-ci
```

Solution:

```yaml
SECRET_KEY: ci-test-secret-key-for-sentinelcore-minimum-32-bytes
```

After this change, the JWT warnings were gone.

### 112. The workflow's final result

After the fixes, the workflow runs correctly in GitHub Actions.

Confirmed result:

```text
11 passed
```

Tests validated in CI:

```text
/health -> 200
/auth/register -> 201
/auth/register duplicate email -> 400
/auth/login -> 200 + token
/auth/login wrong password -> 401
/users/me with token -> 200
/users/me without token -> 401
/users/admin-only regular user -> 403
/users/admin-only admin -> 200
/admin/audit-logs admin -> 200
/security/events admin -> 200
```

### 113. Current state after Backend CI Phase 1

At this point SentinelCore has:
- a GitHub Actions workflow for the backend
- PostgreSQL started as a service in CI
- the `sentinelcore_test` test database
- automatic installation of the backend dependencies
- automatic test runs with `pytest`
- 11 tests passing in CI
- a trigger limited by `paths`
- manual runs through `workflow_dispatch`
- GitHub actions updated to versions compatible with Node 24
- the JWT warning fixed with a stronger `SECRET_KEY`
- a green pipeline in GitHub Actions

This stage marks the backend's move from local testing to automated validation in a CI pipeline.

## Backend Code Quality CI - Ruff Phase 1

### 114. Ruff for code quality

`Ruff` was introduced to check the quality and the formatting of the Python code.

The goal of this stage is for the SentinelCore backend to be checked not only functionally, through tests, but also for style and structure.

Until this stage, CI validated:

```text
pytest -> the backend tests
```

With Ruff, CI also validates:

```bash
ruff check .
ruff format --check .
```

This marks the move from just running tests to a first automated code quality standard.

### 115. Configuring Ruff in `pyproject.toml`

The dependency added to `backend/pyproject.toml`:

```toml
"ruff",
```

The Ruff configuration was added too:

```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = [
  "E",
  "F",
  "I",
  "B",
  "UP",
]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "auto"
```

The selected rules:
- E -> Python style rules
- F -> Pyflakes errors: unused imports or variables
- I -> import order
- B -> common likely bugs, detected by flake8-bugbear
- UP -> modernizing Python code for newer versions

### 116. Ruff checks run locally

Before it was added to CI, Ruff was run locally:

```bash
python -m ruff check .
python -m ruff format --check .
```

At first, Ruff found several problems, even though the tests passed.

This confirmed the difference between:

- functional tests -> the application works
- linting -> the code meets the quality standard

The tests passed, but Ruff found style, modernization and best practice problems.

### 117. Problems found by Ruff

Ruff found these main categories of problems:
- B008 -> `Depends(...)` calls in default arguments
- B904 -> exceptions raised in `except` without `from`
- UP042 -> enums defined as `str` + `enum.Enum` instead of `StrEnum`

These problems did not break the application, but they pointed to places where the code could be modernized and clarified.

### 118. Modernizing dependency injection with `Annotated`

To fix the `B008` findings, the FastAPI endpoints were modernized with `typing.Annotated`.

Instead of the classic style:

```python
def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return current_user
```

the modern style is used:

```python
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    return current_user
```

The change was applied in:
- app/api/deps.py
- app/api/routes/auth.py
- app/api/routes/users.py
- app/api/routes/audit.py
- app/api/routes/security.py

Advantages:
- code closer to the modern FastAPI style
- no more Ruff `B008` warnings
- a clearer separation between the data type and the dependency injection mechanism
- code that is easier to check statically

### 119. Fixing the `B904` rule

In `app/api/deps.py`, Ruff flagged that an exception raised inside an `except` block should keep the original cause.

Instead of:

```python
except InvalidTokenError:
    raise credentials_exception
```

the code uses:

```python
except InvalidTokenError as exc:
    raise credentials_exception from exc
```

This makes the causal chain of errors clearer and helps debugging.

### 120. Moving enums to `StrEnum`

For the `UP042` rule, the enums defined with the combination:

```python
class UserRole(str, enum.Enum):
    ...
```

were modernized with:

```python
from enum import StrEnum
```

and:

```python
class UserRole(StrEnum):
    ...
```

The change was applied to:
- UserRole
- AuditEventType
- SecurityEventType
- SecuritySeverity

Files affected:
- app/models/user.py
- app/models/audit_log.py
- app/models/security_event.py

This modernization fits because the backend uses Python 3.12.

### 121. Ruff format

Ruff format was used to check the code's formatting:

```bash
python -m ruff format --check .
```

The local result confirmed the files are formatted correctly:

```text
32 files already formatted
```

This means the formatting standard is consistent across the backend.

### 122. Final local validation

After the problems were fixed, these were run locally:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -v
```

Final result:
- ruff check -> All checks passed
- ruff format --check -> passed
- pytest -> 11 passed

This confirms that the backend passes both the functional tests and the code quality rules.

### 123. Adding Ruff to GitHub Actions

After the local validation, Ruff was added to the GitHub Actions workflow.

In `.github/workflows/backend-ci.yml`, after the dependencies are installed and before the tests run, these steps were added:

```yaml
- name: Run Ruff lint
  working-directory: backend
  run: |
    python -m ruff check .

- name: Run Ruff format check
  working-directory: backend
  run: |
    python -m ruff format --check .
```

The current order of the backend pipeline is:
- install dependencies
- ruff check
- ruff format --check
- pytest

The order is deliberate: the code must meet the quality standard before the tests run.

### 124. The result in CI

The GitHub Actions workflow was run after Ruff was added.

Confirmed result:

- Ruff lint -> passed
- Ruff format check -> passed
- pytest -> 11 passed

The backend pipeline is green.

### 125. Current state after Ruff Phase 1

At this point the SentinelCore backend has:
- automated local tests
- automated tests in GitHub Actions
- PostgreSQL as a service in CI
- 11 tests passing in CI
- Ruff installed and configured
- automated linting with `ruff check`
- automated formatting checks with `ruff format --check`
- code modernized with `Annotated`
- enums modernized with `StrEnum`
- the `B904` rule fixed properly
- a green CI pipeline for tests and code quality

This stage introduces the first real layer of code quality automation in SentinelCore.

## Backend Security Checks - Phase 1

### 126. Security checks for the backend

The first layer of automated security checks for the SentinelCore backend was introduced.

Until this stage, the pipeline validated:

```bash
ruff check .
ruff format --check .
pytest
```

After this stage, the pipeline also validates:

```bash
bandit
gitleaks
```

The goal of this phase is to check the project not only for function and style, but also for basic security.

### 127. Bandit

`Bandit` was introduced to scan the Python code.

Bandit detects common security problems in Python source code.

The dependency added to `backend/pyproject.toml`:

```toml
"bandit[toml]",
```

The `[toml]` variant was used so Bandit can be configured through `pyproject.toml`.

### 128. Configuring Bandit

The configuration added to `backend/pyproject.toml`:

```toml
[tool.bandit]
exclude_dirs = ["tests", ".venv", "migrations"]
skips = []
```

Excluded:
- tests -> tests may contain hardcoded test passwords or values
- .venv -> the virtual environment must not be scanned
- migrations -> Alembic migrations are not application logic

To begin with, the Bandit scan focuses on the application code in `app/`.

### 129. Running Bandit locally

Bandit was run locally from the `backend` directory with:

```bash
python -m bandit -r app -c pyproject.toml
```

At first, Bandit reported one low severity issue:

```text
B106: hardcoded_password_funcarg
Possible hardcoded password: 'bearer'
```

The reported location was in the login endpoint, at the response:

```python
return Token(access_token=access_token, token_type="bearer")
```

### 130. Handling the Bandit B106 false positive

The `B106` report was analyzed and classified as a false positive.

The value `bearer` is not a password, a real token or a secret. It is the standard OAuth2 value for the type of token returned to the client.

The fix was targeted, by adding the comment:

```python
return Token(
    access_token=access_token,
    # OAuth2 token type, not a password or secret.
    token_type="bearer",  # nosec B106
)
```

The important decision:
- the `B106` rule was not disabled globally
- the exception applies only to the line that was analyzed
- the rule stays active, to catch any real hardcoded passwords in the future

This is the right approach, because it avoids suppressing a useful rule across the whole project.

### 131. Validating Bandit after the fix

After the false positive was handled, these were run again:
- python -m ruff check .
- python -m ruff format --check .
- python -m bandit -r app -c pyproject.toml
- python -m pytest -v

Local result:
- ruff check -> All checks passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 11 passed

This confirms that the backend passes the functional checks as well as the Python quality and security checks.

### 132. Gitleaks

`Gitleaks` was introduced to scan the repository for secrets.

Gitleaks detects:
- passwords
- tokens
- API keys
- private keys
- hardcoded secrets
- accidentally exposed credentials

This check matters especially because SentinelCore is meant to become public once the repository is considered safe.

### 133. Local problem encountered with Docker on Fedora

On the first local run with Docker, Gitleaks did not scan the real repository.

The wrong output showed:
- 0 commits scanned
- scanned ~0 bytes
- fatal: not a git repository

This output was not accepted as valid, because `no leaks found` means nothing when `0` commits were scanned.

The problem was investigated by running an Alpine container:

```bash
docker run --rm -v "$(pwd):/repo" -w /repo alpine:latest ls -la
```

The result showed:

```text
Permission denied
```

The cause was the Docker/SELinux permissions on Fedora.

### 134. Fixing the SELinux problem with `:Z`

On Fedora, the Docker mount problem was fixed with the `:Z` option:

```bash
docker run --rm -v "$(pwd):/repo:Z" -w /repo alpine:latest ls -la
```

After this change, the container could see the repository correctly:
- .git
- .github
- backend
- frontend
- docs

The correct local Gitleaks command on Fedora becomes:

```bash
docker run --rm -v "$(pwd):/repo:Z" -w /repo zricethezav/gitleaks:latest
```

### 135. Validating Gitleaks locally

Once the mount problem was fixed, Gitleaks scanned the repository correctly.

Confirmed result:

```text
23 commits scanned
scanned ~280700 bytes
no leaks found
```

This confirms that Gitleaks scanned the available Git history, not just an empty directory.

### 136. Adding Bandit to GitHub Actions

After the local validation, Bandit was added to the backend workflow.

In `.github/workflows/backend-ci.yml`, Bandit runs after Ruff and before pytest:

```yaml
- name: Run Bandit security scan
  working-directory: backend
  run: |
    python -m bandit -r app -c pyproject.toml
```

The backend job's order becomes:
- install dependencies
- ruff check
- ruff format --check
- bandit
- pytest

The order is deliberate:
- first, the code quality is validated
- then the Python security scan runs
- then the functional tests run

### 137. Adding Gitleaks to GitHub Actions

Gitleaks was added to the workflow as a separate job.

The first version tested used:

```yaml
uses: gitleaks/gitleaks-action@v2
```

It worked, but produced an infrastructure warning about Node.js 20.

To remove the warning, Gitleaks was changed to run through Docker in CI:

```yaml
gitleaks:
  name: Run Gitleaks secret scan
  runs-on: ubuntu-latest

  steps:
    - name: Checkout repository
      uses: actions/checkout@v5
      with:
        fetch-depth: 0

    - name: Run Gitleaks with Docker
      run: |
        docker run --rm -v "$PWD:/repo" -w /repo zricethezav/gitleaks:latest detect --source=/repo --verbose
```

CI does not need the `:Z` option, which was specific to the local Fedora/SELinux environment.

### 138. Scanning the Git history

For the Gitleaks job, the checkout uses `fetch-depth: 0`.

This setting downloads the repository's full history into the runner.

Reason:
- Gitleaks must be able to scan the Git history too, not just the latest snapshot
- a secret committed in the past can be detected even if the current file was cleaned up

This matters for preparing the repository to be published later.

### 139. The final result in CI

After Bandit and Gitleaks were added, the GitHub Actions workflow ran successfully.

Confirmed result:

```text
Ruff lint -> passed
Ruff format check -> passed
Bandit security scan -> passed
Gitleaks secret scan -> passed
pytest -> 11 passed
```

The pipeline is green, with no relevant warnings.

### 140. Current state after Security Checks Phase 1

At this point the SentinelCore backend has:
- automated local tests
- automated tests in GitHub Actions
- PostgreSQL as a service in CI
- Ruff for linting and the format check
- Bandit for Python security scanning
- Gitleaks for secret scanning
- Gitleaks run locally through Docker with `:Z` on Fedora
- Gitleaks run in CI through Docker
- Git history scanning through `fetch-depth: 0`
- the Bandit false positive handled with a targeted `# nosec B106`
- 11 passing tests
- a green CI pipeline
- a pipeline with no relevant warnings

This stage introduces the first real DevSecOps layer in SentinelCore.

## Admin User Management - Phase 1

### 141. User administration

The first stage of user administration was introduced.

The goal of this phase is for users with an administrative role to be able to see the list of users in the system.

Endpoint introduced:

```http
GET /admin/users
```

This stage starts SentinelCore's Admin User Management area.

### 142. The purpose of `GET /admin/users`

The endpoint lists the users in the application.

Access is allowed only for the administrative roles:
- admin
- owner

A regular user cannot access this route.

This separation matters for the IAM/RBAC foundation, because user data must not be exposed to every authenticated account.

### 143. A service for listing users

The function added to `app/services/user_service.py`:

```python
def list_users(
    db: Session,
    limit: int = 50,
    offset: int = 0,
) -> list[User]:
    statement = select(User).order_by(User.id).offset(offset).limit(limit)
    return list(db.scalars(statement).all())
```

This function separates the database access from the API route's logic.

Purpose:
- keeping the routes as clean as possible
- reusing the listing logic in other parts of the application
- preparing for more advanced pagination in the future

### 144. A new route for user administration

The file created:

```text
app/api/routes/admin_users.py
```

The router uses the prefix:

```python
router = APIRouter(prefix="/admin/users", tags=["admin-users"])
```

The main endpoint introduced:

```python
@router.get("", response_model=list[UserRead])
def read_users(...)
```

It returns the list of users through the public `UserRead` schema.

### 145. Protecting the endpoint with RBAC

The endpoint is protected by the dependency:

```python
Depends(require_role(UserRole.ADMIN, UserRole.OWNER))
```

This means only users with the `ADMIN` or `OWNER` role can access the user list.

A regular user gets `403 Forbidden`.

This confirms that RBAC applies to the new administrative endpoints too, not only to the `/users/admin-only` test endpoint.

### 146. Using `Annotated` for dependency injection

The endpoint was written in the modern FastAPI style, with `typing.Annotated`.

This keeps the code consistent with the standards introduced in the Ruff stage and avoids the `B008` problem.

### 147. Basic pagination parameters

The endpoint accepts basic parameters:

```text
limit
offset
```

Configuration:

```python
limit: Annotated[int, Query(ge=1, le=200)] = 50
offset: Annotated[int, Query(ge=0)] = 0
```

This gives a simple foundation for pagination.

The maximum of `200` prevents overly large requests to the API.

### 148. An audit log for listing users

When an admin reads the user list, the application creates an audit log.

Event used:

```text
AuditEventType.ADMIN_ENDPOINT_ACCESSED
```

Message:

```text
Admin listed users
```

This decision matters because reading the user list is an administrative action and must be tracked.

In SentinelCore, administrative actions must be visible in the audit trail.

### 149. A security event for listing users

Besides the audit, the endpoint also creates a security event.

Event used: `SecurityEventType.ADMIN_ACCESS`

Severity: `SecuritySeverity.INFO`

Message: `Admin listed users`

This classification marks the action as an informational security event.

It is not an incident, but it is an action relevant to administrative visibility.

### 150. Registering the router in the application

The `admin_users` router was included in `app/main.py`.

The import `from app.api.routes import admin_users` was added, and the router was registered in the FastAPI application with `app.include_router(admin_users.router)`.

The endpoint is thus available in the application at `GET /admin/users`.

### 151. Automated tests for `GET /admin/users`

Tests were added to `tests/test_protected_routes.py`.

Scenarios validated:
- regular user -> 403 Forbidden
- admin user -> 200 OK + the user list

The first test confirms that a user without an administrative role cannot access the endpoint.

The second test confirms that an admin can read the user list and that the response does not expose `hashed_password`.

### 152. The regular user test

Scenario:
1. a regular user is created
2. the user logs in
3. the user tries to access GET /admin/users
4. the API answers 403

Expected result: `403 Forbidden`

This test validates the RBAC protection.

### 153. The admin user test

Scenario:
1. a user is created
2. the user is promoted to admin in the test database
3. the user logs in
4. the user accesses GET /admin/users
5. the API answers with the user list

Expected result: `200 OK`

Additional checks:
- the response is a list
- the list contains the created user
- the email is correct
- the username is correct
- hashed_password is not exposed

This check matters for the security of the API response.

### 154. Local validation

After the implementation, these were run locally:

```bash
python -m ruff check .
python -m ruff format --check .
python -m bandit -r app -c pyproject.toml
python -m pytest -v
```

Confirmed result:
- ruff check -> passed
- ruff format --check -> passed
- bandit -> passed
- pytest -> passed

With the two new tests, the total number of backend tests grew from `11` to `13`.

### 155. Validation through a pull request

The work was done on a separate branch, not directly on `main`.

Flow used:
- feature branch
- push
- pull request to main
- green CI
- merge
- delete the branch

This stage confirms the project's new working discipline: every new task is developed on its own branch and reaches `main` only after CI has checked it.

### 156. Current state after Admin User Management Phase 1

At this point the SentinelCore backend has:
- the administrative endpoint `GET /admin/users`
- user listing through a dedicated service
- access allowed only for `admin` and `owner`
- responses through the public `UserRead` schema
- protection against exposing `hashed_password`
- an audit log for listing users
- a security event for listing users
- basic `limit` and `offset` parameters
- tests for a regular user being denied
- tests for an admin being allowed
- 13 passing backend tests
- a green CI after the pull request

This stage starts SentinelCore's real user administration module.

## Admin User Management - Phase 2

### 157. Endpoints for user details

The second stage of Admin User Management was introduced.

After the endpoint for listing users, `GET /admin/users`, an endpoint was added for reading a single user: `GET /admin/users/{user_id}`.

Its purpose is to let a user with an administrative role see the details of a specific user.

### 158. The purpose of `GET /admin/users/{user_id}`

The endpoint returns a user's public information, by internal ID.

Access is allowed only for the roles:
- admin
- owner

A regular user cannot access this route and gets `403 Forbidden`.

If the requested user does not exist, the API answers `404 Not Found` with `{"detail": "User not found"}`.

### 159. A service for reading a user by ID

The function added to `app/services/user_service.py`:

```python
def get_user_by_id(db: Session, user_id: int) -> User | None:
    statement = select(User).where(User.id == user_id)
    return db.scalar(statement)
```

This function separates the database access from the API endpoint's logic.

Purpose:
- a cleaner API route
- reusable logic
- preparation for future administrative endpoints
- clear handling of the case where the user does not exist

### 160. Extending the `admin_users` router

The endpoint was added to:

```text
app/api/routes/admin_users.py
```

The route introduced:

```python
@router.get("/{user_id}", response_model=UserRead)
def read_user_by_id(...)
```

The endpoint returns a `UserRead` object, not the full internal model.

This prevents exposing sensitive fields, such as:
- hashed_password

### 161. RBAC protection

The endpoint is protected with `Depends(require_role(UserRole.ADMIN, UserRole.OWNER))`.

This means only users with an administrative role can read other users' details.

Scenarios:
- regular user -> 403 Forbidden
- admin -> 200 OK
- owner -> 200 OK

This protection is essential, because user details must not be available publicly or to any authenticated user.

### 162. Handling a missing user

If `get_user_by_id()` does not find the requested user, the endpoint raises:

```python
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="User not found",
)
```

This matters for the clarity of the API.
It does not return `None`, it does not return an empty list, and it does not hide the error.

### 163. An audit log for viewing a user's details

When an admin or owner reads a user's details, the application creates an audit log.

Event used: `AuditEventType.ADMIN_ENDPOINT_ACCESSED`

Message: `Admin viewed user details for user_id={target_user.id}`

This decision matters because viewing a user's data is an administrative action and must be tracked.

In SentinelCore, administrative actions must be visible in the audit trail.

### 164. A security event for viewing a user's details

Besides the audit log, the endpoint also creates a security event.

Event used: `SecurityEventType.ADMIN_ACCESS`

Severity: `SecuritySeverity.INFO`

Message: `Admin viewed user details for user_id={target_user.id}`

This event is not an incident, but it is an administrative action relevant to security visibility.

### 165. Automated tests for `GET /admin/users/{user_id}`

Tests were added to `tests/test_protected_routes.py`.

Scenarios validated:
- regular user -> 403 Forbidden
- admin user -> 200 OK + the user's details
- missing user -> 404 Not Found

These tests extend the coverage of user administration.

### 166. The regular user test

Scenario:
1. a regular user is created
2. the user's ID is read from the test database
3. the user logs in
4. the user tries to access `GET /admin/users/{user_id}`
5. the API answers 403

Expected result: `403 Forbidden`

This test confirms that a regular user cannot read administrative details about users.

### 167. The admin user test

Scenario:
1. a user is created
2. the user's ID is read from the test database
3. the user is promoted to admin in the test database
4. the user logs in
5. the admin accesses `GET /admin/users/{user_id}`
6. the API returns the user's details

Expected result: `200 OK`

Additional checks:
- the id is correct
- the email is correct
- the username is correct
- hashed_password is not exposed

### 168. The missing user test

Scenario:
1. a user is created
2. the user is promoted to admin
3. the admin logs in
4. the admin accesses `GET /admin/users/999999`
5. the API answers 404

Expected result: `404 Not Found`

Message validated: `{"detail": "User not found"}`

This test confirms that the API explicitly handles the case where the requested user does not exist.

### 169. Local validation

After the implementation, these were run locally:

```bash
python -m ruff check .
python -m ruff format --check .
python -m bandit -r app -c pyproject.toml
python -m pytest -v
```

Confirmed result:
- ruff check -> passed
- ruff format --check -> passed
- bandit -> passed
- pytest -> passed

With the three new tests, the total number of backend tests grew from `13` to `16`.

### 170. Validation through a pull request

The work was done on a separate branch, not directly on `main`.

Flow used:
- feature branch
- push
- pull request to main
- green CI
- merge
- delete the branch

This stage continues the discipline introduced earlier: every new task is worked on its own branch and reaches main only after CI has validated it.

### 171. Current state after Admin User Management Phase 2

At this point the SentinelCore backend has:
- the administrative endpoint `GET /admin/users`
- the administrative endpoint `GET /admin/users/{user_id}`
- user listing
- reading one user's details
- access allowed only for `admin` and `owner`
- responses through the public `UserRead` schema
- protection against exposing `hashed_password`
- explicit handling of `404 User not found`
- an audit log for viewing a user's details
- a security event for viewing a user's details
- tests for a regular user being denied
- tests for an admin being allowed
- tests for a missing user
- 16 passing backend tests
- a green CI after the pull request

This stage consolidates the Admin User Management module and prepares the ground for more sensitive administrative actions, such as changing roles.

## Admin User Management - Phase 3 (local implementation)

### 172. Role update endpoint and policy

`PATCH /admin/users/{user_id}/role` accepts a body such as `{"role": "admin"}`
and returns `UserRead`, excluding `hashed_password`.

Only an authenticated owner may change a target user's role. Allowed destination
roles are `user`, `admin`, and `security_analyst`. The endpoint rejects
self-modification, modifying an existing owner, and assigning the owner role.

| Situation | Response |
| --- | --- |
| Missing token | 401 |
| Actor is not an owner | 403, `Insufficient permissions` |
| Target does not exist | 404, `User not found` |
| Owner targets their own account | 403, `Owners cannot change their own role` |
| Owner targets another owner | 403, `Cannot change the role of an owner` |
| Owner tries to assign owner | 403, `Cannot promote a user to owner` |
| Unknown role such as `manager` | 422 |
| Allowed change | 200 |
| Existing role requested for an allowed target | 200, no change events |

`UserRoleUpdate` validates the role using `UserRole`. The value `owner` is valid
input for the enum but is rejected by the endpoint's business rules.

### 173. Actor, target, and transaction behavior

The actor is the authenticated owner; the target is the user identified by the
route's `user_id`. Audit and security event `user_id` and `email` fields identify
the actor. The message records the target ID and the previous and new roles:

`Owner changed role for user_id={target_id} from {old_role} to {new_role}`

`update_user_role()` stages the role change, an `AuditLog`, and a `SecurityEvent`
before committing once. It rolls back and re-raises if the commit fails.
It constructs event objects directly because the existing event creation helpers
commit independently. No new enum values or database migration are required.

The events reuse `ADMIN_ENDPOINT_ACCESSED` and `ADMIN_ACCESS`, with security
severity `INFO` and source `backend`. Requests rejected by the endpoint and
requests that leave the role unchanged create no successful-change events.
Self-modification and owner restrictions are checked before the unchanged-role
shortcut.

### 174. Local verification on 2026-10-06

- Ruff lint and formatting checks passed for the backend.
- Bandit reported no security findings; it emitted warnings while parsing the
  existing OAuth2 `nosec` comment in `auth.py`.
- All 29 tests passed in 4.64 seconds against the separate PostgreSQL database
  `sentinelcore_test`, using `backend/.venv`.
- Successful-change tests verify the role read back from the database and the
  actor and message in both event records.
- Additional tests cover an unknown target, an invalid role, and an unchanged
  role, including the absence of successful-change events.

The PostgreSQL connection failed inside the sandbox; the successful test run was
performed outside it. A transaction-failure test remains to be added. Phase 3
CI validation remains pending. (Both were completed in Phase 4, section 186.)

## Project Cleanup

### 175. Purpose of the stage

Before development continued, the whole project was reviewed and the problems found were fixed. The work was done on a separate branch, `chore/project-cleanup`, created from `main`.

### 176. Alembic saw an empty schema

`migrations/env.py` imported only `Base`, not the model modules. A model registers itself in `Base.metadata` only when its module is imported, so when Alembic ran, `Base.metadata.tables` was empty. The next `alembic revision --autogenerate` would have proposed dropping every table.

Likely cause: Ruff removed the imports as unused (`F401`).

Solution:

```python
from app.models import audit_log, security_event, user  # noqa: F401
```

Check: `python -m alembic check` -> `No new upgrade operations detected.`

The tests could not catch the problem, because they create the schema with `create_all()`, not with migrations. `alembic check` was added to `backend/README.md` as a manual check.

### 177. Inactive users

The `is_active` field existed in the model, but nothing checked it.

New behavior:
- login with the right password for an inactive user -> `403 Forbidden`, `Inactive user`
- the attempt creates a `LOGIN_FAILED` audit log and security event, with `WARN` severity
- a token issued before the deactivation is refused by `get_current_user()` with `403 Inactive user`

The `Inactive user` message appears only after the password is checked, so it does not reveal the account's state to someone who does not know the password.

There is no deactivation endpoint yet; in tests, `is_active` is set directly in the test database.

### 178. Equal response time at login

For an unknown email, `authenticate_user()` returned immediately, without checking a hash. For an existing email it computed the Argon2 hash, which takes visibly longer. The time difference made it possible to find out which emails were registered.

Solution: `app/core/security.py` generates `DUMMY_PASSWORD_HASH` at startup, from a random value. For an unknown email, the password is checked against this hash, so both cases cost the same.

Note: `POST /auth/register` still answers `Email already registered`, so whether an email exists can be found out through register. This is an accepted limitation at this stage.

### 179. Concurrent registrations

Register checks for duplicates before the insert. Two simultaneous requests with the same email could both pass the check, and the second got `500 Internal Server Error` from PostgreSQL's unique index.

Solution:
- `create_user()` rolls back if the `commit` fails
- the endpoint catches the `IntegrityError` of type `UniqueViolation` and answers `400`
- the message is chosen by the violated index: `ix_users_email` -> `Email already registered`, `ix_users_username` -> `Username already taken`

The test simulates the race by disabling the prior checks with `monkeypatch`, so that only the unique indexes can reject the duplicate.

### 180. Dependencies and other fixes

- the development tools (`pytest`, `httpx`, `ruff`, `bandit`) moved to `[project.optional-dependencies] dev`
- the development and CI install becomes `python -m pip install -e ".[dev]"`
- the dependencies have minimum versions equal to the versions validated locally
- `ruff` is pinned exactly (`ruff==0.15.17`), because new versions can change the formatting or add rules and could fail CI without any code change
- the duplicate `pwdlib` / `pwdlib[argon2]` dependency was reduced to `pwdlib[argon2]`
- CI uses `postgres:17`, the same version as Docker Compose
- the explanation for `# nosec B106` moved to the line above; Bandit read the text after `nosec` as rule IDs and emitted warnings
- `AuditLogRead.message` accepts `None`, like the database column
- the `Mapped[DateTime]` annotations became `Mapped[datetime]`
- typos fixed in `.env.example` (`postgresql+psycopg://`) and `.gitignore` (`__pycache__/`)
- the documentation was aligned with the code (`require_role()`, routes, the CI configuration)
- `README.md` and `backend/README.md` were written

### 181. Local validation

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified, no warnings
- alembic check -> No new upgrade operations detected
- pytest -> 21 passed

The new tests were also checked in reverse: with the fixes temporarily disabled, all 5 new tests fail.

## Admin User Management - Phase 4

### 182. Activating and deactivating accounts

The endpoint introduced:

```http
PATCH /admin/users/{user_id}/status
```

Body:

```json
{"is_active": false}
```

The response uses the `UserRead` schema, so `hashed_password` is not exposed.

The endpoint relies on the `is_active` check introduced in the cleanup stage: a deactivated account can no longer authenticate, and previously issued tokens are refused immediately, because `get_current_user()` reads the user from the database on every request.

### 183. Permission rules

Access is hierarchical:
- `admin` can activate or deactivate `user` and `security_analyst` accounts
- `owner` can also activate or deactivate `admin` accounts
- nobody can change their own status
- an `owner`'s status cannot be changed

| Situation | Response |
| --- | --- |
| No token | 401 |
| The actor is not `admin` or `owner` | 403, `Insufficient permissions` |
| Missing user | 404, `User not found` |
| The actor changes their own status | 403, `Users cannot change their own status` |
| The target is an `owner` | 403, `Cannot change the status of an owner` |
| An `admin` changes another `admin`'s status | 403, `Only an owner can change the status of an admin` |
| `is_active` is not a boolean (`"false"`, `0`, `null`) | 422 |
| Allowed change | 200 |
| The requested status is already the current one | 200, no events |

`UserStatusUpdate` uses `StrictBool`, so values such as `"false"` or `0` are rejected, not implicitly converted.

### 184. Dedicated event types

Until now, administrative actions reused `ADMIN_ENDPOINT_ACCESSED` and `ADMIN_ACCESS`, and changes could only be told apart by the message.

New types were added, to both `AuditEventType` and `SecurityEventType`:
- `USER_ROLE_CHANGED`
- `USER_ACTIVATED`
- `USER_DEACTIVATED`

The Phase 3 role change now uses `USER_ROLE_CHANGED`.

The messages recorded:
- `Admin deactivated user_id={id}` / `Owner activated user_id={id}`
- `Owner changed role for user_id={id} from {old} to {new}`

The events' `user_id` and `email` fields identify the actor; the target appears in the message. The severity is `INFO`.

### 185. The first Alembic migration after the initial schema

The new values were added to the PostgreSQL enum types by the migration `02a6be0e0ec8_add_user_management_event_types.py`.

The migration was written by hand, because `--autogenerate` does not detect new values in an existing enum. For the same reason, `alembic check` cannot confirm that the database enums are up to date.

Upgrade:

```sql
ALTER TYPE audit_event_types ADD VALUE IF NOT EXISTS 'USER_ROLE_CHANGED';
```

The values are uppercase, because SQLAlchemy stores the enum member names.

PostgreSQL cannot remove a value from an enum. The downgrade:
- remaps the rows with the new types to `ADMIN_ENDPOINT_ACCESSED` / `ADMIN_ACCESS`
- renames the existing enum type
- creates the type with the old values
- converts the `event_type` column to the new type
- drops the old type

The migration was checked on a temporary database with `upgrade -> downgrade -> upgrade`, with rows that used the new values. The downgrade remapped the rows and kept the `ix_security_events_event_type` index.

Applying it locally:

```bash
python -m alembic upgrade head
```

### 186. One transaction for changes and events

The commit logic in `update_user_role()` was extracted into `_commit_user_change()`, now also used by `update_user_status()`.

The function adds the audit log and the security event to the same session as the user change and commits once. If that fails, it rolls back and propagates the exception.

The transaction-failure test, pending since Phase 3, was added for both operations. The simulated commit first runs `flush`, so the change and the events reach the open transaction; only a real `rollback` undoes them. The test was checked in reverse: without the `rollback`, it fails.

### 187. Local validation

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 55 passed

The new tests cover: a missing token, roles without access, the matrix of allowed changes, every restriction, a missing user, non-boolean values, an unchanged status, a transaction failure, and the immediate loss of access for a deactivated account.

## Input Validation - Phase 1

### 188. The problem

The input schemas accepted any string:
- a username longer than 50 characters reached PostgreSQL, overflowed the `String(50)` column and produced `500 Internal Server Error`
- an empty username and password were accepted with `201 Created`
- `Test@x.com` and `test@x.com` could be different accounts, and so could `Admin` and `admin`

### 189. The rules introduced

The rules are defined in `app/schemas/user.py`, as reusable `Annotated` types.

**Username** (`Username`):
- 3-50 characters; 50 matches the `users.username` column
- only ASCII letters, digits, `_`, `.` and `-`
- converted to lowercase, so `Admin` and `admin` cannot coexist

**Email** (`NormalizedEmail`):
- validated by `EmailStr`
- converted to lowercase, at register and at login

**Password at register** (`NewPassword`):
- at least 12 characters
- at most 128 characters, to bound the cost of Argon2 hashing per request
- no composition rules (uppercase, symbols), following the NIST and OWASP recommendations

**Password at login** (`LoginPassword`):
- only a maximum of 128 characters
- no minimum, so an account created before the new policy can still authenticate

Invalid input is rejected with `422`, before any database access.

Note: in Pydantic, `pattern` is checked against the value received, before `to_lower`. That is why the pattern also accepts uppercase (`^[A-Za-z0-9_.-]+$`); the stored value is lowercase anyway.

### 190. The migration for existing data

After the input was normalized, an existing account stored as `Test@x.com` would no longer be found at login, because the lookup uses `test@x.com`.

The migration `7242f1f7b69b_lowercase_user_emails_and_usernames.py` converts `users.email` and `users.username` to lowercase.

If two accounts would become identical, for example `Dup@x.com` and `dup@x.com`, the migration stops with a message listing the conflicting values. The transaction is rolled back, the data stays untouched, and the database stays at the previous version. Conflicts must be resolved by hand, because merging two accounts automatically is not safe.

The downgrade does not change the data: the original form is not stored, and the lowercase values remain valid in the previous revision too.

Existing usernames that do not follow the new rules are not changed. Login uses the email, so those accounts remain usable.

The migration was checked on a temporary database: mixed-case data, `downgrade -> upgrade`, and the conflict case.

Applying it locally:

```bash
python -m alembic upgrade head
```

### 191. Local validation

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 74 passed

The new tests cover: every rule rejected with `422`, the boundary values accepted, lowercase storage, duplicates that differ only by case, case-insensitive login, a password too long at login, and the login of an account whose password is shorter than the new policy.

Reverse check: with the previous schemas, 12 of the 19 new tests fail. The other 7 confirm that the rules are not too strict, and pass in both versions.

## Brute-Force Detection - Phase 1

### 192. Purpose of the stage

Until now, failed logins were recorded as `LOGIN_FAILED` with `WARN` severity, but nothing reacted to them. An attacker could try passwords without limit.

This stage introduces the first real SIEM-light detection: too many failures for the same email raise an incident and temporarily block login. It is the first use of the `INCIDENT` severity.

### 193. Rules

The defaults, configurable in `.env`:

```env
LOGIN_MAX_FAILED_ATTEMPTS=5
LOGIN_FAILURE_WINDOW_MINUTES=15
LOGIN_LOCKOUT_MINUTES=15
```

- on the 5th failure within 15 minutes for the same email, login for that email is blocked for 15 minutes
- the attempt that reaches the threshold already gets `429 Too Many Requests`
- during the block, every attempt gets `429`, even with the right password
- the response carries the `Retry-After` header with the remaining seconds
- during the block, the password is not checked at all, so the attempts reveal nothing
- a successful login resets the count
- once a block expires, the failures before it are no longer counted
- unknown emails are blocked the same way, so the block does not reveal whether an account exists
- failed logins of an inactive account are counted the same way

Known drawback: an attacker can temporarily lock a victim out by sending wrong passwords. The block is temporary, and the per-email variant was chosen deliberately over a per email + IP block, which an attacker with several IPs could bypass.

### 194. The state is derived from security events

There is no separate table or column for counting failures. The `app/services/login_protection_service.py` service uses the events already recorded:
- the number of failures = `LOGIN_FAILED` for the email, after the latest of: the start of the window, the last `LOGIN_SUCCESS`, the last `BRUTE_FORCE_DETECTED`
- the block is active if the last `BRUTE_FORCE_DETECTED` is more recent than the block duration

The time is read from the database (`SELECT now()`), the same clock that fills `created_at`, so the comparisons never mix the application's clock with the database's.

These queries got the composite index `ix_security_events_email_type_created` on `(email, event_type, created_at)`.

### 195. New events

| Situation | Audit log | Security event | Severity |
| --- | --- | --- | --- |
| The threshold is reached | `LOGIN_LOCKED` | `BRUTE_FORCE_DETECTED` | `INCIDENT` |
| An attempt during the block | `LOGIN_BLOCKED` | `LOGIN_BLOCKED` | `WARN` |

The names follow the existing separation: the audit log describes the fact (login locked), and the security event the interpretation (brute-force attack detected).

The incident is tied to the targeted account through `user_id` when the account exists, even though the attempts did not authenticate it.

### 196. The IP address in events

The `audit_logs` and `security_events` tables now have an `ip_address` column (`String(45)`, enough for IPv6). Every event records the client's IP: register, login, the administrative endpoints and the role/status changes.

The IP comes from the `get_client_ip()` dependency in `app/api/deps.py`, from `request.client.host`. Values that are not valid IP addresses are stored as `NULL` (for example `testclient` in tests).

The `X-Forwarded-For` header is not read directly, because the client can forge it. If the application runs behind a reverse proxy, uvicorn must be started with `--proxy-headers` and `--forwarded-allow-ips`, and `request.client` will then contain the real IP.

`AuditLogRead` and `SecurityEventRead` expose the `ip_address` field.

The IP prepares a future detection: many different emails tried from the same IP (password spraying).

### 197. The migration

The migration `449c22b3652c_add_login_protection_events_and_ip_.py`:
- adds the new values to `audit_event_types` and `security_event_types`
- adds the `ip_address` column to both tables
- creates the composite index

The downgrade drops the index and the columns, remaps the rows with the new types to `LOGIN_FAILED`, and recreates the enum types without the new values.

Checked on a temporary database: `upgrade`, `alembic check`, rows with the new values, `downgrade`, then `upgrade` and `alembic check` again.

### 198. Problem encountered in tests: prepared statements

After the new queries were added, two tests failed intermittently with:

```text
cache lookup failed for type ...
```

Cause: psycopg prepares on the server (a prepared statement) any query executed at least 5 times on the same connection. The prepared query stays tied to the enum type's internal identifier (OID). The test fixture recreates the schema for every test, so the enum types get new OIDs, and connections reused from the pool kept queries tied to dropped types.

Solution: in `tests/conftest.py`, after the schema is recreated, `test_engine.dispose()` is called, so every test starts on fresh connections.

The problem only occurs in tests, because the real application never recreates the enum types while it runs.

### 199. Local validation

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 86 passed

The new tests (`tests/test_login_protection.py`) cover: reaching the threshold and the incident, refusing the right password during the block without checking it, blocking unknown emails, the block expiring, the time window, the reset after a successful login, ignoring the failures before an expired block, isolation per email, the configured thresholds, recording the IP (IPv4 and IPv6) and exposing it through the API.

Elapsed time is simulated by moving the events' `created_at` into the past.

Reverse check: without the block check 3 tests fail, without the threshold 6 fail, and without the reset after a successful login / a block 2 fail.

## Log Filtering - Phase 1

### 200. Purpose of the stage

`GET /admin/audit-logs` and `GET /security/events` returned only the latest `limit` events, with no filters and no way to reach older events. This stage prepares them for the frontend's security dashboard.

### 201. A cursor-paginated response

The response is no longer a list, but an object (an envelope):

```json
{
  "items": [...],
  "next_cursor": 123
}
```

The next page is fetched with `?before_id=123`. When there are no more results, `next_cursor` is `null`.

Events are ordered by descending `id`, newest first. Ordering by `id` (and not by `created_at`) is needed because:
- `id` is unique, so there are no ties between events
- the cursor is also an `id`, so the order and the cursor use the same key
- `created_at` is the start of the transaction, so an event inserted later can have an older timestamp

> Update (Event Ordering - Phase 1, sections 257-258): the lists are now ordered by `(created_at, id)`, with the same `before_id` cursor, so events recorded late land at their own time.

Advantages over `offset`:
- pages do not shift when new events arrive while the analyst is browsing
- the query stays fast on large tables, because it does not walk the skipped rows

To know whether there is a next page, one row more than `limit` is read.

Changing the shape of the response is an API contract change. It was made now because these endpoints have no clients yet.

The generic `Page[ItemT]` schema in `app/schemas/pagination.py` uses the Python 3.12 generics syntax.

### 202. Filters

Shared filters (`app/schemas/event_filters.py`):

| Parameter | Behavior |
| --- | --- |
| `user_id` | equality |
| `email` | equality, case-insensitive |
| `ip_address` | a valid IPv4 or IPv6; the IPv6 form is normalized, so `2001:DB8:0:0::1` finds `2001:db8::1` |
| `since` | `created_at >= since` |
| `until` | `created_at < until` |
| `before_id` | the pagination cursor |
| `limit` | 1-200, 50 by default |

Specific filters:
- audit logs: `event_type`, with one or more values (`?event_type=login_failed&event_type=login_locked`)
- security events: `event_type` and `severity`, each with one or more values

Several values for the same parameter are combined with `OR`; different parameters are combined with `AND`.

The time range is half-open (`since <= created_at < until`), so consecutive ranges never count the same event twice.

### 203. Validating the filters

The filters are Pydantic models used for query parameters (`Annotated[AuditLogFilters, Query()]`). They answer `422` for:
- `since` greater than or equal to `until`
- dates without a time zone (`AwareDatetime`), to avoid ambiguous interpretations
- invalid values for `event_type`, `severity`, `ip_address`, `limit` or `before_id`
- unknown parameters, through `extra="forbid"`

The last rule matters for security: a misspelled filter, for example `?event_typ=login_failed`, would otherwise be ignored, and the analyst would see unfiltered results while believing they were filtered.

### 204. Auditing log reads

Reading the logs is now audited, with new types in `AuditEventType`:
- `AUDIT_LOGS_VIEWED`
- `SECURITY_EVENTS_VIEWED`

The message contains the filters used, for example:

```text
Viewed audit logs with event_type=['login_failed'], limit=10
```

Decisions:
- the event is recorded after the query, so the response never contains its own read
- only an audit log is created, not a security event: reading is an audit fact, not a security signal, and must not flood the SIEM stream

The new values were added by the migration `1ff3830ec505_add_log_view_audit_event_types.py`. The downgrade remaps the rows to `ADMIN_ENDPOINT_ACCESSED` and recreates the enum type.

### 205. Shared query logic

The shared filters, the ordering and the pagination are implemented once, in `fetch_event_page()` in `app/services/event_query.py`, used by both services. Each service only adds its specific filters (`event_type`, `severity`).

`fetch_event_page()` is a generic function with `EventT: AuditLog | SecurityEvent`. The first version, with the constraints `(AuditLog, SecurityEvent)`, was resolved wrongly by Pylance for the call with `AuditLog`.

### 206. Local validation

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 107 passed
- the migration: `upgrade -> alembic check -> downgrade -> upgrade -> alembic check` on a temporary database

The new tests (`tests/test_event_logs_api.py`) cover: access denied for a regular user, the order, walking every page through the cursor, page stability when new events arrive, insertion order even when the timestamps are reversed, every filter and their combination, the half-open range, invalid queries, and auditing the read.

Reverse check: each of the following changes makes at least one test fail: removing `extra="forbid"`, removing the email normalization, an inclusive cursor, a closed range, ordering by `created_at`.

The 3 existing tests that expected a list were updated for the new response shape.

## Observability - Phase 1

### 207. Purpose of the stage

"Observability-first" is one of the project's principles, and Prometheus and Grafana are part of the DevOps MVP. Until now, the backend exposed no metrics, wrote unstructured logs, and `/health` answered `ok` even when PostgreSQL was down.

This stage introduces:
- Prometheus metrics for HTTP and for security events
- structured logs, with a request id on every request
- a health check that checks the database
- Prometheus and Grafana in Docker Compose, with a dashboard provisioned automatically

### 208. Metrics

The metrics are defined in `app/core/metrics.py` and exposed at `GET /metrics`, in the Prometheus text format.

| Metric | Type | Labels |
| --- | --- | --- |
| `sentinelcore_http_requests_total` | Counter | `method`, `route`, `status_code` |
| `sentinelcore_http_request_duration_seconds` | Histogram | `method`, `route` |
| `sentinelcore_security_events_total` | Counter | `event_type`, `severity` |

Every distinct combination of labels becomes a separate series in Prometheus. That is why the labels come from small, fixed sets:
- `route` is the route template (`/admin/users/{user_id}`), not the concrete path (`/admin/users/42`)
- paths that match no route get `route="unmatched"`
- unknown HTTP methods get `method="OTHER"`

Otherwise, anyone could create an unbounded number of series by sending requests to made-up paths or methods.

`sentinelcore_security_events_total` is incremented after each security event is committed, in the three places that create them: `create_security_event()`, `_commit_user_change()` and `lock_login()`. A single metric covers successful and failed logins, blocks, brute-force incidents and administrative changes.

The metrics live in the process's memory and start from zero on every restart; Prometheus's `rate()` and `increase()` functions handle these resets. The configuration assumes a single uvicorn process; several workers would need the multiprocess mode of `prometheus_client`.

### 209. Protecting `/metrics`

If `METRICS_TOKEN` is set in `.env`, `/metrics` requires `Authorization: Bearer <token>` and answers `401` otherwise. If it is empty or missing, the endpoint is open, which suits local development.

The token is compared with `hmac.compare_digest`, in constant time, so the response time does not reveal how much of the token was guessed.

`/metrics` does not appear in the OpenAPI documentation.

### 210. Request id and structured logs

The `observe_requests` middleware in `app/api/middleware.py`:
- reuses the incoming `X-Request-ID` header if it has at most 64 characters from `A-Z a-z 0-9 . _ -`, and generates a new one otherwise
- returns the request id in the response's `X-Request-ID` header
- keeps it in a `ContextVar`, so every log written during the request contains it
- writes a single log line per request, with `method`, `route`, `path`, `status_code`, `duration_ms` and `client_ip`
- records the HTTP metrics

Validating the incoming request id prevents injecting arbitrary text, such as newlines, into logs and headers.

The log format is chosen in `.env`:

```env
LOG_LEVEL=INFO
LOG_FORMAT=json
```

- `json`: one JSON object per line, for log collectors
- `text`: lines readable in a terminal, with the same fields

JSON example:

```json
{"timestamp": "2026-10-06T16:00:03.871220+00:00", "level": "INFO", "logger": "sentinelcore.request", "message": "Request completed", "request_id": "demo-trace-1", "method": "GET", "route": "/health", "path": "/health", "status_code": 200, "duration_ms": 0.22, "client_ip": "127.0.0.1"}
```

The uvicorn logs go through the same format. Uvicorn's own access log is disabled, because it would duplicate the log written by the middleware.

### 211. Health checks

- `GET /health`: liveness, meaning the process is running and responding; it does not depend on the database
- `GET /health/ready`: readiness, meaning the application can serve traffic; it runs `SELECT 1` and answers `503` with `{"status": "unavailable", "database": "unavailable"}` if PostgreSQL is not available

The split lets an orchestrator avoid restarting the process when only the database is temporarily unavailable, while not sending it traffic until the database is back.

### 212. Prometheus and Grafana

`docker-compose.yml` now contains the `prometheus` (`prom/prometheus:v3.15.0`) and `grafana` (`grafana/grafana:13.2.3`) services. The configuration is in `infra/`:

```text
infra/
├── prometheus/
│   └── prometheus.yml
└── grafana/
    ├── provisioning/
    │   ├── datasources/prometheus.yml
    │   └── dashboards/sentinelcore.yml
    └── dashboards/
        └── sentinelcore-overview.json
```

Both services use `network_mode: host` and listen only on `127.0.0.1`:
- Prometheus scrapes the backend running locally on `localhost:8000`, without uvicorn having to listen on `0.0.0.0`
- nothing is exposed on the local network

Host networking is fully supported on Linux.

The configuration files are mounted with `:ro,z`. The `z` option relabels the files for SELinux, which Fedora needs, as with Gitleaks; on systems without SELinux it is ignored.

The `SentinelCore Overview` dashboard is provisioned automatically and contains:
- Security: brute-force incidents, blocked attempts, failed logins, account deactivations, security events per minute by type and by severity
- HTTP: requests per second by route, responses by status code, p95 latency by route, the percentage of 5xx errors

Starting them:

```bash
docker compose up -d prometheus grafana
```

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`, user `admin`, password `sentinelcore` (local only)

### 213. Local validation

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 132 passed

The new tests (`tests/test_observability.py`) cover: generating, reusing and rejecting request ids, the per-request log, propagating the request id into logs written during the request, both log formats, template-based labels, grouping unknown paths and methods, the duration histogram, counting security events, the `/metrics` protection, and readiness with the database available and unavailable.

Reverse check: each of the following changes makes at least one test fail: a concrete path instead of the template, an unvalidated request id, a request id not propagated into the logs, an unvalidated token, an uncounted incident.

End-to-end check, on a migrated temporary database:
- the backend started with JSON logs, Prometheus and Grafana started through Docker Compose
- a simulated brute-force attack: 4 `401` responses, then `429` with `Retry-After: 900`
- Prometheus scrapes the backend (`health: up`) and reports exactly the events generated
- Grafana provisions the datasource and the dashboard, and all 12 panels return data

The check found a problem: the 5xx errors panel showed nothing when there were no errors, because dividing an empty series produces no result. The expression now uses `or vector(0)`, so it shows `0`.

## JWT Hardening and Sessions - Phase 1

### 214. Purpose of the stage

The JWT contained only `sub` (the email) and `exp`. There was no real logout: a stolen token stayed valid until it expired, and the **Authorize** button in Swagger did not work, because login accepted only JSON.

This stage is needed before the frontend, which needs logout and a stable token contract.

### 215. The token's contents

| Claim | Value |
| --- | --- |
| `iss` | `JWT_ISSUER`, `sentinelcore` by default |
| `aud` | `JWT_AUDIENCE`, `sentinelcore-api` by default |
| `sub` | the user's id, as a string (RFC 7519 requires a string) |
| `jti` | the session id (a UUID) |
| `iat` | when it was issued |
| `exp` | when it expires |

On every request, the signature, algorithm, issuer, audience and expiry are verified, and all six claims are required.

`sub` is now the user's id, not the email: the id never changes, while the email might be editable in the future. Tokens issued before this stage are refused, so every user has to sign in once more.

The login response includes `expires_in`, in seconds, as in the standard OAuth2 response.

### 216. Stricter configuration

- `SECRET_KEY` must be at least 32 bytes; otherwise the application does not start
- `ALGORITHM` accepts only `HS256`, `HS384` or `HS512`; `none` and asymmetric algorithms are rejected at startup

The first rule prevents weak HMAC keys. The second prevents configurations in which unsigned tokens, or tokens signed differently, could be accepted.

### 217. Sessions

The new `user_sessions` table:
- `id`: a random UUID, so the ids cannot be guessed
- `user_id`
- `created_at`, `expires_at`
- `revoked_at`: set at logout or revocation
- `ip_address`, `user_agent`

Every login creates a session, and its id becomes the token's `jti`. On every request, `get_current_session()` checks the token, then the user, then that the session exists, belongs to the user in `sub`, is not revoked and has not expired.

The inactive user check runs before the session check, so a deactivated account still gets `403 Inactive user`, not a generic `401`.

The session times (`created_at`, `expires_at`) and the token times (`iat`, `exp`) come from the application's clock. PyJWT rejects tokens with an `iat` in the future, so a database clock slightly ahead of the application would invalidate freshly issued tokens.

### 218. New endpoints

| Endpoint | Effect |
| --- | --- |
| `POST /auth/token` | login through an OAuth2 form (`username` = email); used by Swagger UI |
| `POST /auth/logout` | revokes the current token's session; `204` |
| `POST /auth/logout-all` | revokes all of the user's sessions, including the current one; `204` |
| `GET /users/me/sessions` | the active sessions, with `current: true` for the current one |
| `DELETE /users/me/sessions/{session_id}` | revokes one of one's own sessions; `204` |

`/auth/login` and `/auth/token` use the same internal function, so they share the brute-force protection, the events and the session creation. Failures on both endpoints add up toward the same threshold.

Revoking a session that belongs to another user answers `404 Session not found`, exactly like a missing session, so other users' session ids cannot be confirmed.

`/auth/token` needs the `python-multipart` dependency, which FastAPI uses for forms.

### 219. Revocation on deactivation

Deactivating an account revokes all its sessions, in the same commit as the status change and its events. Reactivation does not restore them: the user has to sign in again.

### 220. Events and migration

New types in `AuditEventType`:
- `SESSION_REVOKED`: logout, or revoking one of one's own sessions
- `ALL_SESSIONS_REVOKED`: logout from every session

Logout is an audit fact, not a security signal, so it creates no security events.

The migration `232fc184b0d7_add_user_sessions.py` creates the `user_sessions` table and adds the new values. The downgrade remaps the rows to `ADMIN_ENDPOINT_ACCESSED`, recreates the enum type and drops the table.

Expired sessions stay in the table. A periodic cleanup can be added later.

### 221. Local validation

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 164 passed
- the migration: `upgrade -> alembic check -> downgrade -> upgrade -> alembic check` on a temporary database

The new tests (`tests/test_sessions_and_tokens.py`) cover:
- the token's contents and its link to the session
- 13 kinds of invalid token: wrong key, wrong issuer or audience, missing claims, invalid `sub` or `jti`, an expired token, another algorithm, an unsigned token (`alg: none`), a token in the old format, a missing session
- another user's session used with one's own `sub`
- validation of `SECRET_KEY` and of the algorithm
- the session list, logout, logout-all, revoking one's own session and refusing to revoke other users' sessions
- expired sessions
- revocation on deactivation
- login through the OAuth2 form, the shared brute-force protection and the Swagger configuration

Reverse check: each of the following changes makes at least one test fail: accepting another user's session, accepting revoked sessions, disabling the `aud` check and the required claims, deactivation without revoking the sessions.

### 222. Periodic session cleanup

Expired or revoked sessions stay in `user_sessions`, where they help investigations (who was signed in, and from where). So that the table does not grow without bound, they are deleted after a retention period:

```env
SESSION_RETENTION_DAYS=30
SESSION_CLEANUP_INTERVAL_MINUTES=60
```

`delete_stale_sessions()` deletes the sessions that expired or were revoked more than `SESSION_RETENTION_DAYS` days ago. Active sessions are never deleted.

The cleanup runs in two ways:
- automatically, in the API process: a task started in `lifespan` runs every `SESSION_CLEANUP_INTERVAL_MINUTES` minutes and is stopped at shutdown; `0` disables it
- by hand or from cron: `python -m app.cli cleanup-sessions`

The periodic task runs the cleanup in a separate thread (`asyncio.to_thread`), because database access is synchronous. A failed run, for example when the database is temporarily unavailable, is logged and retried at the next interval, without stopping the task.

Every run writes a `Session cleanup completed` log with the number of sessions deleted, and increments the `sentinelcore_sessions_deleted_total` metric.

With several uvicorn workers, each would run its own task. The deletion is idempotent, so the result stays correct, but in that case `SESSION_CLEANUP_INTERVAL_MINUTES=0` with a cron job is preferable.

### 223. An admin revoking a user's sessions

New endpoint:

```http
DELETE /admin/users/{user_id}/sessions
```

Response: `200` with `{"revoked_sessions": 2}`.

Purpose: signing a user out of every device, for example after a suspected compromise, without deactivating the account. The user can sign in again right away.

The rules are the same as for status changes:

| Situation | Response |
| --- | --- |
| The actor is not `admin` or `owner` | 403, `Insufficient permissions` |
| Missing user | 404, `User not found` |
| One's own account | 403, `Use /auth/logout-all to revoke your own sessions` |
| The target is an `owner` | 403, `Cannot revoke the sessions of an owner` |
| An `admin` acting on another `admin` | 403, `Only an owner can revoke the sessions of an admin` |

The hierarchical rules are implemented once, in `_ensure_can_manage_account()`, used by both endpoints; each action supplies its own messages.

The revocation and the events are saved in a single commit, through `_commit_user_change()`:
- an `ALL_SESSIONS_REVOKED` audit log
- a new `USER_SESSIONS_REVOKED` security event, with `INFO` severity
- message: `Admin revoked 2 session(s) for user_id=5`

The new value is added by the migration `c96113ce371b_add_user_sessions_revoked_security_event.py`. The sessions migration (`232fc184b0d7`) was not edited, because it had already been applied to the development database.

> Update (Account Containment - Phase 1, sections 250 and 253): the endpoint became `POST /admin/users/{user_id}/revoke-sessions`, with a mandatory reason, open to `security_analyst` too and governed by `_ensure_can_contain_account()`.

### 224. Type checking with Pyright

Pylance only checks the files open in the editor, so new files went unchecked. The whole backend was checked with Pyright, the engine Pylance is built on:

```bash
npx --yes pyright@1 --pythonpath .venv/bin/python app tests migrations
```

Pyright found 8 errors, including in files from earlier stages:
- `auth.py`: `constraint_name` can be `None` on a uniqueness error
- `session_service.py`: `rowcount` is not declared on the `Result` type; the row count now comes from `RETURNING id`, correct and explicit
- in tests: parameter dictionaries typed too broadly, a `db.scalar()` that can return `None`, an audit message that can be `None`

After the fixes: `0 errors, 0 warnings`.

Pyright does not run in CI yet; it can be added as a separate step.

### 225. Local validation

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pyright -> 0 errors
- pytest -> 184 passed
- the new migration: `upgrade -> alembic check -> downgrade -> upgrade -> alembic check` on a temporary database

The new tests (`tests/test_session_cleanup_and_admin_revoke.py`) cover: deleting only old sessions, the cleanup's metric and log, the periodic task continuing after an error, starting and stopping the task in `lifespan`, the CLI command, and the admin endpoint: access, the matrix of allowed roles, the events, the case with no active sessions, every restriction and the missing user.

Reverse check: each of the following changes is detected: not deleting revoked sessions, a missing retention period, the task stopping at the first error, letting an admin act on another admin. Not sending the cancellation to the task at shutdown blocks the application from stopping, so that test hangs instead of failing.

## Cookie Authentication - Phase 1

### 226. Purpose of the stage

The frontend needs a session in the browser. Keeping the token in `localStorage` or `sessionStorage` would expose it to any injected script (XSS). The token now goes into an `httpOnly` cookie, which JavaScript cannot read.

Authentication through `Authorization: Bearer` stays unchanged for Swagger and for API clients.

### 227. Login from the browser

```http
POST /auth/session
```

It takes the same JSON body as `/auth/login`, uses the same internal function (so the same brute-force protection, the same events and the same session) and answers `204 No Content`, with no token in the body. It sets two cookies:

| Cookie | Contents | `httpOnly` |
| --- | --- | --- |
| `sentinelcore_session` | the JWT | yes |
| `sentinelcore_csrf` | the CSRF token | no, the frontend must read it |

Both have `Secure`, `SameSite=Strict`, `Path=/` and a `Max-Age` equal to the token's lifetime.

`Secure` is controlled by `AUTH_COOKIE_SECURE`, `true` by default. Browsers treat `http://localhost` as a secure origin, so the cookies work locally too.

### 228. CSRF protection

The browser attaches cookies automatically, including to requests started by other sites. That is why every cookie-authenticated request with the `POST`, `PUT`, `PATCH` or `DELETE` method must send the `X-CSRF-Token` header, with the value of the `sentinelcore_csrf` cookie. Otherwise the response is `403 CSRF token missing or invalid`.

The CSRF token is an HMAC-SHA256 of the session id, computed with `SECRET_KEY` (signed double-submit, the variant OWASP recommends). Advantages:
- it is valid only for that session
- it cannot be forged by planting one's own CSRF cookie
- it needs no extra storage

The comparison runs in constant time (`hmac.compare_digest`).

Requests with `Authorization: Bearer` need no CSRF token: the browser never sends that header on its own. If a request carries both the header and the cookie, the header takes precedence.

### 229. Login CSRF

A foreign site could try to sign the victim into the attacker's account by submitting a form to the login endpoint. HTML forms can only send `application/x-www-form-urlencoded`, `multipart/form-data` or `text/plain`, and `/auth/session` accepts only JSON: FastAPI answers `422` for any other content type. A `fetch` request with JSON from another site would need CORS approval, which the backend does not grant.

The behavior is pinned by tests, so a future change cannot weaken it unnoticed.

### 230. Logout

`/auth/logout` and `/auth/logout-all` work for both kinds of authentication. Besides revoking the session in the database, they clear both cookies (`Max-Age=0`).

### 231. Integration with the frontend

In development, the frontend will run on Vite and forward `/api` requests to the backend through a proxy. The frontend and the API thus appear to share an origin: no CORS is needed, and the `SameSite=Strict` cookies work. In production, the same effect comes from serving the frontend and the API through the same reverse proxy.

### 232. Local validation

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pyright -> 0 errors
- pytest -> 205 passed

The new tests (`tests/test_cookie_auth.py`) cover: the cookie attributes and the absence of the token from the body, the CSRF token bound to the session, cookie authentication, rejecting non-JSON bodies at login, the shared brute-force protection, the `Secure` setting, every kind of invalid CSRF token, successful requests with a CSRF token, safe methods, Bearer requests without CSRF, header precedence, invalid cookies, logout clearing the cookies, and the token really being revoked.

Reverse check: each of the following changes makes at least one test fail: removing the CSRF check, a CSRF token not bound to the session, a session cookie readable from JavaScript, logout without clearing the cookies, preferring the cookie over the header.

## My Account API - Phase 1

### 233. Purpose of the stage

Until now, security events could be read only by `admin`, `owner` and `security_analyst`. The frontend's "My account" scope needs every user to see their own history and to be able to sign out of their other devices.

### 234. The account's own activity

```http
GET /users/me/activity
```

It returns the security events about the current account, with the same cursor pagination as the administration lists (`items`, `next_cursor`, `before_id`, `limit`). Accepted filters: `event_type`, `severity`, `since`, `until`. Any other parameter (for example `user_id` or `email`) gets `422`, so the endpoint cannot be used to read someone else's events.

What the history includes:
- the events tied to the account through `user_id`
- the failed or blocked login attempts that carry only the account's email: a wrong password does not tie the attempt to the user, but the account's owner must see it
- of the latter, only those after the account was created; attempts on that email before registration stay hidden

The response contains only `id`, `event_type`, `severity`, `ip_address` and `created_at`. The `message` field is left out: it is written for operators, in English, and can name other accounts (for example "Owner changed role for user_id=12"). The frontend describes events by type, in the interface language.

Reading one's own history is not audited: it exposes nobody else's data, and an audit row every time the page opens would bury the entries that matter.

Administrative events are recorded on the actor. An admin sees "You changed a user's role" in their history; the affected user does not see the change yet, because the events have no field for the target. This is a known limitation, noted for a later stage. (Resolved in sections 241-242.)

### 235. Signing out of the other devices

```http
DELETE /users/me/sessions
```

It revokes all of the user's active sessions except the one the request comes from, and answers `{"revoked_sessions": N}`. Unlike `/auth/logout-all`, the user stays signed in. It creates an audit log of the new type `OTHER_SESSIONS_REVOKED`.

`stage_revoke_all_sessions()` takes an optional `keep_session_id` parameter, so the same function serves logout-all, revocation by an admin, and this action.

### 236. Refactoring the filters

`EventFilters` was split:
- `EventPageFilters`: the time range and the cursor, shared by every list
- `EventFilters`: adds `user_id`, `email` and `ip_address`, only for the administration lists

`fetch_event_page()` now applies only the range and the cursor; the identity filters are built by `event_filter_conditions()`. This way, `MyActivityFilters` does not inherit filters that would allow reading other accounts.

### 237. Migrations

- `OTHER_SESSIONS_REVOKED` in `audit_event_types`; on downgrade, the rows become `ALL_SESSIONS_REVOKED`
- an index on `security_events.user_id`, used by the personal history and by the `user_id` filter

### 238. Problem encountered: Alembic ignored `DATABASE_URL`

The database URL was written directly in `alembic.ini`, and `migrations/env.py` did not read the application settings. A command such as `DATABASE_URL=...temp alembic upgrade head` therefore ran against the development database. That is how it was discovered: checking the migrations on a temporary database applied them to the `sentinelcore` database. An immediate downgrade brought it back to its initial state, with no data loss.

`env.py` now sets the URL from `settings.database_url`, and `alembic.ini` holds no connection. The check was rerun on a temporary database: a full upgrade, `alembic check` with no differences from the models, a downgrade, then an upgrade again; the development database stayed untouched.

### 239. Local validation

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pyright -> 0 errors
- pytest -> 223 passed

The new tests (`tests/test_my_account.py`) cover: mandatory authentication, the order of events, including failed attempts that carry only the email, hiding other accounts' events and those from before the account was created, the response fields, the filters, pagination, rejecting identity filters, not auditing the read, revoking the other sessions while keeping the current one, isolation from other users, and the CSRF requirement for cookie requests.

Reverse check: each of the following changes makes at least one test fail: removing the time bound for attempts on the email, matching any email, also revoking the current session.

## Organization API - Phase 1

### 240. Purpose of the stage

The frontend's "Organization" scope (events, audit, users, overview) needs a few things the API did not have: the target of administrative actions, search and filters in the user list, an account's history as seen by an operator, and a summary for the overview page. This stage is the first of the scope's four PRs; the other three are frontend pages.

### 241. The target of administrative actions

`security_events` and `audit_logs` have a new column, `target_user_id` (nullable, a foreign key to `users`, indexed). `user_id` stays the actor; `target_user_id` is the account that was acted on. It is filled in for:
- a role change (`USER_ROLE_CHANGED`)
- activating and deactivating an account (`USER_ACTIVATED`, `USER_DEACTIVATED`)
- an admin closing a user's sessions (`USER_SESSIONS_REVOKED` / `ALL_SESSIONS_REVOKED`)
- viewing a user or their history (audit)

Old rows keep a `NULL` target; they name the target only in the message ("user_id=12"). The administration lists accept the new `target_user_id` filter, and the responses contain the field.

This resolves the limitation noted in section 234: the affected user now sees the actions taken on their account in their own history.

### 242. The personal history and the actions received

`GET /users/me/activity` also includes the events whose `target_user_id` is the current account. Every item has the new `as_target` field:
- `false`: the reader took the action (an admin sees "You changed a user's role")
- `true`: someone else acted on the reader's account ("Your role was changed")

For items with `as_target: true`, `ip_address` is `null`: the recorded address is the operator's, and the affected user must not learn it. The operator's identity does not appear either, as before.

### 243. The user list

```http
GET /admin/users?q=...&role=admin&role=owner&is_active=false&limit=50&before_id=...
```

The response now has the same shape as the event lists, `{"items": [...], "next_cursor": ...}`, newest users first. `offset` pagination was replaced by the `before_id` cursor, as in the rest of the API. Filters:
- `q`: a substring of the email or username, case-insensitive (both are stored in lowercase); `%` and `_` are searched as text, not as wildcards
- `role`: one or more roles
- `is_active`: `true` or `false`

Unknown parameters, including the old `offset`, get `422`.

Pagination was moved out of `fetch_event_page()` into a generic function, `fetch_page()` (`app/services/pagination.py`), used by both events and users. Likewise, `CursorPageFilters` (`before_id`, `limit`, rejecting unknown parameters, `describe()`) is the shared base of the filters.

### 244. The security analyst, and noise in the events

- `GET /admin/users`, `GET /admin/users/{id}` and the new `GET /admin/users/{id}/activity` are also open to `security_analyst`, who needs accounts during investigations. Changing the role or the status and closing sessions stay with `admin` and `owner`.
- Reading users no longer creates an `ADMIN_ACCESS` security event. Reads are recorded only in the audit, with the new `USERS_VIEWED` type (for the detail view, with the target). Otherwise the Users page would have flooded the security stream on every load. It is the same rule as for reading the logs: viewing is an audit fact, not a security signal.

### 245. An account's history, for operators

```http
GET /admin/users/{user_id}/activity
```

It returns the same events the account's owner sees in their own history (actor, target, failed attempts on the email after the account was created), but with every field operators need (`message`, `user_id`, `target_user_id`, `email`, `source`). It accepts the same filters as the personal history (`event_type`, `severity`, `since`, `until`, cursor). Reading it is audited as `SECURITY_EVENTS_VIEWED`, with the target.

`MyActivityFilters` was renamed `AccountActivityFilters`, since it serves both endpoints.

### 246. The security summary

```http
GET /security/summary
```

For `admin`, `owner` and `security_analyst`. It returns:
- `last_24h`, `last_7d`: the number of events per severity (`info`, `warn`, `incident`)
- `failed_logins_24h`
- `locked_logins`: how many emails currently have login blocked by the brute-force protection (a `BRUTE_FORCE_DETECTED` event newer than the block duration, the same rule as in `login_protection_service`)
- `top_failed_login_sources`: the top 5 IP addresses by failed logins in the last 24 hours (ties ordered by address)
- `users_total`, `users_inactive`
- `generated_at`: when it was computed

The windows are measured on the database clock, the one that stamps `created_at`. The summary is not audited: the overview page loads it on every visit, and it holds numbers, not records. Opening the events behind a number is audited as usual.

### 247. Migrations

- `06b4f5ced4de`: `target_user_id` with a foreign key and an index, on `security_events` and `audit_logs`
- `370d6e54e7cf`: `USERS_VIEWED` in `audit_event_types`; on downgrade, the rows become `ADMIN_ENDPOINT_ACCESSED`, the type used earlier for reading users

Checked on a temporary database: a full upgrade, `alembic check` with no differences, an insert with the new values, a downgrade (the `USERS_VIEWED` row became `ADMIN_ENDPOINT_ACCESSED`, the columns were gone), then an upgrade and `alembic check` again.

### 248. Local validation

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pyright -> 0 errors
- pytest -> 248 passed

The new tests (`tests/test_organization_api.py`) cover: access denied for regular users and allowed for the analyst, auditing reads without security events, the user list filters (search, literal wildcards, roles, status, combinations), pagination and invalid parameters, the `target_user_id` filter, the personal history with received actions (without the actor's IP), an account's history for operators and its auditing, `404` for missing users, the summary (windows, active and expired blocks, top sources, accounts, no audit) and the empty summary. The existing tests now also check `target_user_id` on role changes, status changes and closing sessions.

Reverse check: each of the following changes makes at least one test fail: a history without the received events, a search that does not escape wildcards, the actor's IP shown to the target, the analyst without read access, a wrong block window, an audit log without the target, sources not ordered by count, the 24 hour window ignored, the wrong audit type for listing.

End-to-end check, with the real backend on a temporary database and Vite running, through the proxy:
- after the owner changes `mihai.pop`'s role, that user's own history contains `user_role_changed` with `as_target: true` and no IP, and the owner's history contains the same event with `as_target: false` and the IP
- the analyst searches (`q=MIH`), filters by status, gets `422` for `offset`, reads the account's history and the summary, and gets `403` on a status change
- no `ADMIN_ACCESS` security event was created; the audit log contains `USERS_VIEWED` and `SECURITY_EVENTS_VIEWED`, with the target where it applies
- real Firefox screenshots of the affected account's My activity page, in both themes: the "Your role was changed" row has "—" in the IP column

## Account Containment - Phase 1

### 249. Purpose of the stage

Until now, the security analyst could only read. In a security team, the analyst is usually the first to notice a compromise, and must be able to isolate the account immediately, without waiting for an admin. This stage gives the analyst reversible, time-boxed containment actions; the final decision (deactivation) stays with `admin` and `owner`.

### 250. Closing an account's sessions

```http
POST /admin/users/{user_id}/revoke-sessions
{"reason": "Sign-ins from an unknown country"}
```

It replaces `DELETE /admin/users/{user_id}/sessions`. The action now takes a reason, and a body on `DELETE` has no defined semantics in HTTP and can be dropped by proxies, so it became a `POST` command. The response stays `{"revoked_sessions": N}`.

It is allowed for `admin`, `owner` and `security_analyst`.

### 251. The temporary lock

```http
POST /admin/users/{user_id}/lock
{"duration_hours": 24, "reason": "Valid password used from a new country"}

POST /admin/users/{user_id}/unlock
```

Locking:
- sets the new `users.locked_until` column to the database clock plus the duration (1-168 hours, that is at most 7 days)
- closes all of the account's sessions, in the same transaction
- creates an `ACCOUNT_LOCKED` security event with `incident` severity and an `ACCOUNT_LOCKED` audit log, with the target and the reason in the message
- a new lock on the same account replaces the end time
- expires on its own; there is no cleanup job, and a value in the past means the account is unlocked

Unlocking is allowed only for `admin` and `owner`: the analyst locks, but lifting a lock early is reviewed by someone else. It creates `ACCOUNT_UNLOCKED` (`info`). Unlocking an account that is not locked (or whose lock has expired) changes nothing and creates no events.

`UserRead` contains `locked_until`; the user list accepts the `locked=true|false` filter, and `GET /security/summary` has the new `accounts_locked` field.

### 252. Login and sessions for a locked account

- The password is checked before the lock, as for deactivated accounts: a wrong password gets `401` as usual, so only someone who knows the password learns that a lock exists.
- With the right password, the response is `403` with the `detail` `Account temporarily locked`, without `Retry-After`: during a suspected compromise, whoever knows the password may be the attacker, so they do not learn when the lock ends.
- The attempt with the right password creates `LOGIN_BLOCKED` (`warn`), tied to the account: it is a useful signal for the analyst.
- `get_current_session` refuses a locked account's sessions with `403`. Locking already revokes the sessions, so the check only matters for a login that raced with the lock. It runs after the session is validated, so that a revoked token gets `401` and does not learn about the lock. A test caught the initial version, in which the check came before the session.

### 253. The hierarchy of actions

`_ensure_can_contain_account()` is the rule for the containment actions (closing sessions, locking, unlocking): nobody acts on their own account or on an owner. Unlike status changes, any operator can contain an admin: the actions are reversible, and a compromised admin is the most dangerous case.

`_ensure_can_manage_account()` (status changes) applies the same rule, plus the restriction that only the owner acts on an admin.

Consequence: an admin can now close another admin's sessions, which used to be reserved for the owner.

### 254. The mandatory reason

`revoke-sessions` and `lock` require `reason`: 3-500 characters, after trimming whitespace at both ends. The reason appears in the message of the event and of the audit log (`... Reason: ...`), so operators see it, but the affected user does not: the personal history does not contain the message.

The messages name the actor's role readably: `Security analyst locked user_id=4 ...`, not `Security_analyst`.

### 255. Migrations

`2b5ba1e0d7df`: the `users.locked_until` column and the `ACCOUNT_LOCKED` and `ACCOUNT_UNLOCKED` types in `security_event_types` and `audit_event_types`. On downgrade, the rows become `USER_SESSIONS_REVOKED` / `ALL_SESSIONS_REVOKED` (a lock always closed the sessions) and `USER_ACTIVATED`.

The database clock moved to `app.core.database.database_now()`, used by the brute-force protection, the summary and the locks.

### 256. Local validation

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pyright -> 0 errors
- pytest -> 281 passed
- the migration: upgrade, `alembic check`, an insert with the new values, a downgrade (rows mapped, column dropped), then an upgrade and `alembic check` again

The new tests (`tests/test_account_containment.py`) cover: access, locking by an analyst, an admin and the owner (including locking an admin), closing the sessions, refusing the login without revealing the lock, the events and messages, the restrictions (own account, owner), validating the duration and the reason, expiry, relocking, unlocking by an admin and the owner, refusing unlock by an analyst, an unlock with no effect, a session that appeared during the lock, the locked account's own history, the `locked` filter and `accounts_locked`. The session closing tests now check the analyst, the reason, and an admin closing another admin's sessions.

Reverse check: each of the following changes makes at least one test fail: a login that ignores the lock, an analyst who can unlock, an unprotected owner, a lock that does not close the sessions, unchecked sessions, a lock without `incident` severity, a `locked` filter that counts expired locks, the admin rule kept for closing sessions, an unlock that always records events, an expired lock that still refuses the login.

End-to-end check, with the real backend on a temporary database and Vite running, through the proxy:
- the analyst: a lock without a reason `422`, locking the owner `403`, locking a user `200`; the user's old token `401`; login with the right password `403` `Account temporarily locked` without `Retry-After`, with a wrong password `401`
- the analyst closes an admin's sessions; the admin's old token `401`
- the analyst cannot unlock (`403`), sees the account under `locked=true` and `accounts_locked: 1`; the admin unlocks, and the user can sign in again
- the events: `ACCOUNT_LOCKED` (`incident`, with the reason), `LOGIN_BLOCKED` on the account, `USER_SESSIONS_REVOKED` with the reason, `ACCOUNT_UNLOCKED`
- real Firefox screenshots, in both themes, of the unlocked account's My activity page and of the login page with the locked account message

## Event Ordering - Phase 1

### 257. The problem

The event lists (`/security/events`, `/admin/audit-logs`, the personal history and an account's history) were ordered by `id`, that is by the order of recording. An event recorded after newer ones, for example one arriving late from an external source, appeared above them, even though it happened earlier. The problem showed up in the screenshots of the Events page, with events inserted with a past date, and would have become real with the ingestion planned in phase A.

### 258. The solution

Events are now ordered by descending `created_at`, and among events with the same `created_at`, by `id`. The order is total, so pagination returns every event exactly once.

Pagination uses a cursor on the `(created_at, id)` pair (keyset), but the API did not change: the cursor stays `before_id`, the id of the last event on the page. The server reads that event's time in a subquery and compares the pairs:

```sql
WHERE (created_at, id) < ((SELECT created_at FROM security_events WHERE id = :before_id), :before_id)
ORDER BY created_at DESC, id DESC
```

An unknown cursor makes the comparison `NULL`, so the page is empty. The user list stays ordered by `id`: accounts have no past dates.

The old test `test_pagination_follows_insertion_order_not_timestamps` was replaced. It started from the correct observation that `created_at` is the start of the transaction, so it can be out of recording order; a cursor on time alone would have skipped or repeated events. The cursor on the pair solves exactly that case.

### 259. Indexes

The migration `fae4d7e28eb6` adds `ix_security_events_created_at_id` and `ix_audit_logs_created_at_id` on `(created_at, id)`. On 50,000 events, `EXPLAIN` shows a backward index scan, with the pair comparison as an index condition and no sort.

### 260. Local validation

- ruff, bandit, pyright -> no problems
- pytest -> 284 passed
- the migration: upgrade, `alembic check`, downgrade (the indexes disappear), then an upgrade and `alembic check` again

New tests: events recorded late appear at their time, pagination by time with equal and out-of-order times returns every event once, an unknown cursor returns an empty page, the audit log is ordered by time.

Reverse check: ordering only by `id`, no tie-break on `id`, a cursor compared only on time, and a cursor compared only on `id` each make at least one test fail.

End-to-end check: two events inserted last, with times in the past, appear through the API and on the Events page at the end of the list, at their time.

## Public Readiness

### 261. Purpose of the stage

Preparing the repository to become public. Checks made first:
- Gitleaks over the whole git history: no secrets
- `backend/.env` is ignored and was never tracked
- the workflows use `pull_request`, not `pull_request_target`, so PRs from forks get no secrets and no token with write access

### 262. Changes

- **PostgreSQL on localhost only**: `docker-compose.yml` now publishes `127.0.0.1:5432`, not `5432` on every interface. The development password is public, so the database must not be reachable from the network. Prometheus and Grafana already listened only on `127.0.0.1`. The existing container picks this up with `docker compose up -d postgres`; the data stays in the volume.
- **Minimal CI permissions**: both workflows declare `permissions: contents: read`, so the GitHub token has no write access, regardless of the repository's settings. Validated with actionlint.
- **MIT license** (`LICENSE`), mentioned in the README.
- New commits use the GitHub noreply address (configured locally in the repository); old commits stay unchanged, with no history rewrite.

Pinning the GitHub actions to SHAs and OpenSSF Scorecard are left for phase C (supply chain).

### 263. Local validation

- `docker compose config` -> valid; the recreated PostgreSQL container listens only on `127.0.0.1:5432`, and the development data was kept
- actionlint -> no problems
- pytest on the recreated container -> 284 passed

## English Documentation

### 264. Translating the documentation

Once the repository was public, the documentation moved to English, and it stays in English from here on. The READMEs and `docs/00`-`docs/03` were translated; the journals keep their numbered sections, so references between documents still hold. The interface stays bilingual (Romanian by default, English available).

Two documents were also reorganized while translating:
- `docs/00`: the current status is a summary grouped by area, instead of a chronological list of every stage (the history stays in the journals), and the finished Sprint 1 plan was replaced by the roadmap
- `docs/02`: the decisions are grouped under one heading per stage, in the original order, exact duplicates were removed, and decisions replaced later are marked *Superseded*

`backend/README.md` had two "Migrations" sections; they were merged, and the session cleanup moved under "Sessions".

## Detection Rules - Phase 1

### 265. Purpose of the stage

Until now there was one detection, brute force on one email, built into the login. Phase A adds the detections that make SentinelCore a SIEM-light, each mapped to the MITRE ATT&CK technique it detects, and a common place where they run, so the ingestion endpoint of the next stage feeds the same rules.

### 266. The engine

`app/services/detection_service.py` holds the rules. Each rule names the event types it watches and the alert type it raises:

| Rule | Watches | Alert | Severity | Technique |
| --- | --- | --- | --- | --- |
| Password spray | `LOGIN_FAILED` | `PASSWORD_SPRAY_DETECTED` | `incident` | T1110.003 |
| Dormant account | `LOGIN_SUCCESS` | `DORMANT_ACCOUNT_LOGIN` | `warn` | T1078 |
| Privileged role | `USER_ROLE_CHANGED` | `PRIVILEGED_ROLE_GRANTED` | `warn` | T1098 |

`run_detection(db, event)` runs after the watched event is committed: by `create_security_event` and by `_commit_user_change` in `user_service`. The alerts it raises are security events like any other, with the `detection` source, so they appear in the event log, the summary, the metrics and the activity of the accounts they name.

- **Alerts only.** The rules do not block anything; responding stays with the operators, through containment. A false positive never locks anyone out. Brute-force protection keeps its block on the email and stays in `login_protection_service`, mapped to T1110.001.
- **No loops.** No rule watches an alert type, and a test checks it.
- **Never in the way.** A failing rule is logged (`Detection failed`) and its alerts are dropped; the action that triggered it, a sign-in for example, still succeeds.
- **Time.** Windows are measured back from the triggering event's own `created_at`, so a late event, once ingestion exists, is judged against the events around it.

`MITRE_TECHNIQUES` in `models/security_event.py` maps each detection type to its technique, and `SecurityEventRead` has the new `mitre_technique` field (`null` for events that are not detections).

### 267. Password spray

A password spray tries one or a few common passwords against many accounts, staying under each account's lockout. The rule counts the different emails that failed to sign in from the event's address within `DETECTION_SPRAY_WINDOW_MINUTES` (15). At `DETECTION_SPRAY_MIN_ACCOUNTS` (10) it raises an `incident` with the address and no account, since the attack targets many.

Counting starts after the latest spray alert for that address, so a continuing attack raises a new alert only after enough new emails, as brute-force protection does after a lockout. Many failures for one email count once: that is brute force, the other rule. Events without an address are skipped.

### 268. Dormant account

A sign-in to an account with no sign-in for `DETECTION_DORMANT_DAYS` (90) days raises a `warn` on the account: an old account that comes back to life is a classic sign of stolen credentials (Valid Accounts). An account that never signed in counts from its creation. The account sees the alert in its own activity.

### 269. Privileged role

Giving an account the `admin` or `security_analyst` role, both of which reach every other account, raises a `warn` with the owner as the actor and the account as the target. Only the owner changes roles, so the alert matters most when the owner's account is the compromised one (Account Manipulation). The role is read from the account after the change; a demotion raises nothing.

### 270. Migrations

`da3df9063709`: the three alert types in `security_event_types`, and the `ix_security_events_ip_type_created` index on `(ip_address, event_type, created_at)`, which serves the spray rule's per-address lookups. On downgrade the alert rows are deleted rather than relabelled: no older type means the same, and each is derived from events that stay.

### 271. Local validation

- ruff check, ruff format --check -> passed
- bandit -> No issues identified (`PASSWORD_SPRAY_DETECTED` is marked `nosec B105`: an event type, not a password)
- pyright -> 0 errors
- pytest -> 302 passed
- the migration: upgrade, `alembic check`, an alert row and a regular event inserted, a downgrade (the alert deleted, the event kept, the index dropped), then an upgrade and `alembic check` again

The new tests (`tests/test_detection.py`) send sign-ins from a fixed address through a test client of their own, since the default one has none. They cover the spray threshold, the alert's fields and message, a continuing spray, one email failing repeatedly, the window, separate addresses, thresholds from settings; a dormant sign-in after a previous one and after creation, recent and new accounts, an old account in regular use, the account's own activity; granting admin and analyst, and a demotion; a failing rule that does not fail the sign-in, no rule watching an alert, the metrics, and `mitre_technique` in the event log. The organization test that filters by target now expects the privileged-role alert beside the role change.

Reverse check: each of the following changes makes at least one test fail: a spray threshold off by one, counting failures instead of emails, ignoring the previous spray alert, ignoring the window, measuring dormancy from creation only, leaving the analyst role out, and dropping either call to `run_detection` or the rule guard.

End-to-end check, with the real backend on a temporary database and Vite running, through the proxy: ten failed sign-ins for ten different emails raised one `password_spray_detected` incident (T1110.003, source `detection`); the first sign-in of an account created 200 days earlier raised `dormant_account_login` ("200 days after the account's creation"); the owner promoting a user to admin through the browser session raised `privileged_role_granted` with the target. The event log returned each with its `mitre_technique`, the summary counted them, and real Firefox screenshots of the event log, in both themes, showed the new names.

## Event Ingestion - Phase 1

### 272. Purpose of the stage

SentinelCore so far saw only its own sign-ins. A SIEM collects signals from the systems around it: a VPN, an identity provider, a cluster's audit log. This stage lets other systems send security events through an API key, and runs the same detection rules on them. It is also how the attack simulator of the next stages will reach the rules: every sign-in to this application comes from the address of its client, so attacks from many addresses can only arrive as reported events.

### 273. API keys

```http
POST /admin/api-keys
{"name": "Corporate VPN", "source": "vpn", "expires_in_days": 90}

GET  /admin/api-keys
POST /admin/api-keys/{key_id}/revoke
```

- Only the owner creates and revokes keys: a key writes into the detection pipeline, and could flood it or mislead it. Admins and analysts list them; the listing is audited (`API_KEYS_VIEWED`).
- A key reads `sck_<prefix>_<secret>`. The 8-character prefix finds the key and is safe to show; the secret is 32 random bytes. The full key is in the creation response only; the database keeps the prefix and a SHA-256 hash of the secret. A fast hash is enough here, unlike for passwords: the secret is random and long, so it cannot be guessed back from its hash.
- Every key expires after 30, 90 or 365 days, chosen at creation, and can be revoked at once. Revoking a revoked key changes nothing.
- `source` (2-50 characters, letters, digits, `_.-`, stored lowercase) is stamped on every event the key sends. `backend` and `detection` are reserved, so an ingested event can never pass for one of the application's own.
- Creating and revoking a key are recorded in the audit log and as security events (`API_KEY_CREATED`, `API_KEY_REVOKED`, `info`), together with the change, in one transaction.

### 274. The ingestion endpoint

```http
POST /ingest/events
Authorization: Bearer sck_1f9fb450_...
{"events": [{"event_type": "login_failed", "occurred_at": "2026-10-09T08:15:00Z",
             "email": "mihai.pop@example.com", "ip_address": "203.0.113.77",
             "user_agent": "Mozilla/5.0 ..."}]}
```

- **Authentication.** A missing, malformed, unknown, revoked or expired key, a wrong secret, or a user's token all get the same `401 Invalid API key`. The secret's hash is compared in constant time. The key's `last_used_at` is updated with each request.
- **What is accepted.** Only sign-ins (`login_success`, `login_failed`), 1-500 per request, all or nothing. `occurred_at` must carry a time zone, be at most 5 minutes ahead of the server and at most a year old. Unknown fields are refused, so a sender cannot set the severity, the source or the message: the server sets the severity (`info` for a success, `warn` for a failure) and writes the message (`Failed sign-in for <email>, reported by <source>`).
- **Storage.** Each event keeps the time it happened as `created_at`, so the event log shows it at that time. A successful sign-in is linked to the account with that email, if there is one; a failed one names only the email, as for the application's own sign-ins.
- **Detection.** The events are stored in one transaction, then go through the detection rules in the order they happened.
- **The answer** is `202` with `{"accepted": N}`. Alerts the events raised are not reported: a sender with a stolen key must not learn what the rules catch.
- The new `sentinelcore_ingested_events_total{source}` metric counts them; there is one series per key source.

### 275. Brute-force protection and reported sign-ins

The lockout protects this application's own sign-in, so it counts only events from the `backend` source. Reported failures reach the detection rules but never lock anyone out of this application, and a reported success never resets this application's failure count, which would otherwise let a stolen key keep a brute-force attack under the limit.

### 276. The user agent of sign-ins

Security events have a new `user_agent` column, filled for this application's sign-ins (success, failure, blocked) from the `User-Agent` header, and for ingested ones from the event. `SecurityEventRead` returns it. The next stage's rule compares devices with it.

### 277. Migrations

`3acb81248c5a`: the `api_keys` table, the `security_events.user_agent` column, `API_KEY_CREATED` and `API_KEY_REVOKED` in both event types, and `API_KEYS_VIEWED` in the audit types. On downgrade the key events are deleted, as no older type means the same, and the table and column are dropped.

### 278. Local validation

- ruff check, ruff format --check -> passed
- bandit -> No issues identified
- pyright -> 0 errors
- pytest -> 344 passed
- the migration: upgrade, `alembic check`, a key, key events, an ingested sign-in with a user agent and an audit row inserted, a downgrade (key events deleted, the ingested sign-in kept, the table and column dropped), then an upgrade and `alembic check` again

The new tests (`tests/test_api_keys.py`, `tests/test_ingestion.py`) cover: a key shown once and stored as a hash, its lifetime, the events and messages; the listing without secrets and its audit entry; only the owner issuing and revoking; invalid names, sources (reserved, also in capitals), lifetimes and extra fields; revoking once and an unknown key; ingested events stored with their source, time, severity, account link and user agent; every kind of missing or invalid key, a wrong secret, revoked and expired keys, a user token; invalid events (type, severity or source set by the sender, future, too old or naive times, bad email, IP or user agent) refusing the whole request; batch bounds; the spray rule firing on ingested events; reported failures and successes leaving the lockout alone; the metric; and the user agent of this application's sign-ins.

Reverse check: each of the following changes makes at least one test fail: accepting a revoked key, accepting an expired key, skipping the secret comparison, storing events at the time they arrive, linking failed sign-ins to accounts, skipping detection for ingested events, counting reported failures toward the lockout, letting a reported success reset it, dropping the reserved-source check, letting admins issue keys, and not recording the user agent. Two of these were not caught at first; the lockout test was tightened and the reset test added.

End-to-end check, with the real backend on a temporary database and Vite running, through the proxy: the owner created a key (a cookie request without the CSRF header got `403`), an admin's attempt got `403`; twelve failed sign-ins for twelve emails from `203.0.113.77` and a sign-in from `198.51.100.20` were accepted (`202`, `{"accepted": 13}`) and raised one `password_spray_detected` incident; a wrong key got `401`; after the owner revoked the key, it got `401` too. The database held the prefix and a 64-character hash, without the secret. Real Firefox screenshots of the event log in both themes and of the audit log.


## Detection Rules - Unfamiliar Network and Device

### 279. Purpose of the stage

Stolen credentials work from anywhere, so a sign-in that is valid but comes from a place and a machine the account has never used is a classic sign of Valid Accounts (T1078). This stage adds that rule, on the `user_agent` column the ingestion stage introduced. It uses no GeoIP database: the network is the address's block, and the device is the browser and system named by the user agent.

### 280. The rule

`detect_unfamiliar_sign_in` in `app/services/detection_service.py` watches `LOGIN_SUCCESS` and raises `UNFAMILIAR_SIGN_IN` (`warn`, T1078) on the account:

- **Network.** Addresses in the same /24 (IPv4) or /64 (IPv6) count as one network, since a home or office router hands out addresses from one such block (`network_of`).
- **Device.** The user agent without its version numbers (`device_of`), so `Firefox/143.0` and `Firefox/144.0` are the same device and a browser update does not look like a new machine.
- **Both.** Only a new network *and* a new device alert. Each alone is common (a trip, a café, a new laptop at home), and alerting on either would bury the real cases.
- **Habits.** The account's sign-ins of the last `DETECTION_UNFAMILIAR_LOOKBACK_DAYS` (90) days that recorded both an address and a user agent. Older sign-ins are forgotten.
- **Learning.** With fewer than `DETECTION_UNFAMILIAR_MIN_SIGN_INS` (3) such sign-ins the account is not judged, so a new account, or one whose history predates the `user_agent` column, does not alert on its first sign-ins.
- **Not judged.** A sign-in without an address, a valid address, a user agent or an account (an ingested sign-in for an unknown email).
- **Once.** A flagged sign-in becomes part of the habits, so repeated sign-ins from the same new place alert once.

The habits are read with one grouped query, `(ip_address, user_agent, count)`, measured back from the sign-in's own time; an ingested sign-in that arrives late is judged against the sign-ins before it. With the default settings, where the lookback and the dormancy period are both 90 days, a dormant account that signs in from a new place has no habits in the lookback, so it raises the dormant alert only.

The alert carries the sign-in's address and user agent: the `Alert` dataclass gained a `user_agent` field, and `run_detection` stores it. The message names the network: `Sign-in to user_id=7 from an unfamiliar network (203.0.113.0/24) and device`.

### 281. Limits

- The rule learns from every successful sign-in, including an attacker's: after the first alert, the same place is familiar. The alert is the signal; it is not repeated.
- An attacker who copies the victim's user agent and signs in from a new network is not flagged. The user agent is sent by the client, so the device is a hint, not a proof.
- Addresses behind carrier-grade NAT or a VPN change networks often; the "and device" condition is what keeps those quiet.

### 282. Migrations

`1c12aa5d76da`: `UNFAMILIAR_SIGN_IN` in `security_event_types`. On downgrade the alerts are deleted (each is derived from sign-ins that stay) and the type is recreated without the value.

### 283. Local validation

- ruff check, ruff format --check -> passed
- bandit -> No issues identified
- pyright -> 0 errors
- pytest -> 356 passed
- the migration: upgrade, `alembic check`, an alert row inserted, a downgrade (the alert deleted, the value gone from the type), then an upgrade and `alembic check` again, on a temporary database

The new tests (`tests/test_detection.py`) sign in from any address and user agent through a client of their own, after recording earlier sign-ins for the account. They cover the alert's fields and message; a known device on a new network, a new device on a known network and a browser update, none of which alert; IPv6 grouped by /64; the learning period; the lookback; sign-ins without a user agent, which teach nothing and are not judged; one alert for repeated sign-ins; and an ingested sign-in judged at its own time.

Reverse check: each of the following changes makes at least one test fail: "or" instead of "and", no version stripping, /32 instead of /24, /128 instead of /64, no learning period, no lookback, no upper time bound, counting sign-ins without a user agent, judging a sign-in without one, dropping the alert's user agent, `incident` instead of `warn`, and the rule left out of `RULES` (12 of 12).

End-to-end check, with the real backend on a temporary database and Vite running, through the proxy: the owner created a key and sent seven sign-ins for one account through ingestion (three from a home network with Firefox, then a Firefox update, a known Firefox on a new network, and two Chrome sign-ins from a new network). Exactly one `unfamiliar_sign_in` alert was raised, for the first Chrome sign-in, naming `203.0.113.0/24`; the response said only `accepted: 7`. The account's real sign-in through the browser, from a new network with its known Firefox, raised nothing. Headless Firefox, signed in as the owner and as the account, loaded the organization's event log (light, dark, phone width) and the account's own activity (light, dark at phone width); each page's event request returned `200` and was audited.

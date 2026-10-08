# SentinelCore - Project Foundation

## 1. Project Overview

**SentinelCore** is an **API-first, web-first, mobile-ready** platform for:

- Identity and Access Management (IAM)
- Security Event Monitoring (SIEM-light)
- Audit Logging
- Observability
- learning and demonstrating DevSecOps in practice

The project is built as a **modular monolith**, not as microservices.

Its goal is not just to be "an app that works", but to clearly demonstrate real skills in:

- backend engineering
- application security
- observability
- DevOps
- architectural organization
- technical documentation

---

## 2. Main Objective

The main objective of SentinelCore is to become a real, serious project, beyond the level of a dissertation, that shows the ability to design, build, run, document and evolve a modern platform focused on security and operations.

The project has to demonstrate:

- coherent design
- a clear separation of responsibilities
- auditability
- basic security implemented correctly
- monitoring and observability planned early
- a solid base for later growth

---

## 3. Architecture Direction

SentinelCore follows these architectural principles:

### API-first
The backend is the source of truth. All critical logic, validation, security and data modelling start in the API.

### Web-first
The main client in the MVP is the web application.

### Mobile-ready
No mobile app is built in the MVP, but the backend and the API contracts must not block a future mobile client.

### Modular Monolith
The application is built as a modular monolith. Microservices are not used at this stage, because they would add needless complexity and slow down both learning and delivery.

### RBAC from the start
Roles and permissions are part of the application's foundation, not something added later.

### Audit-first
Events and audit logs are central to the product, not mere technical details.

### Observability-first
Metrics, logging and monitoring are planned from the early phases.

---

## 4. User Roles

The system starts with these main roles:

### User
A standard user of the platform, with access to their own data and activity.

### Admin
Manages users, roles and basic administrative access.

### Security Analyst
Analyzes security events, suspicious activity and the incident timeline, and can contain an account suspected of being compromised.

### DevOps / Owner
Monitors system health, deployment, metrics and the overall operational state.

---

## 5. MVP Scope

### Backend
The backend MVP includes:

- register
- login
- JWT authentication
- the User model
- basic roles
- users/me
- audit logs
- basic security events
- PostgreSQL
- a health endpoint
- a clear, modular backend structure

### Frontend
The frontend MVP includes:

- login page
- register page
- user dashboard
- basic admin panel
- basic security dashboard

### DevOps / Infra
The DevOps MVP includes:

- local Docker
- PostgreSQL in the local environment
- local Prometheus
- local Grafana
- a base for CI later on

---

## 6. Explicit Non-Goals for MVP

The following are **not part of the MVP**:

- a native mobile app
- real machine learning
- Kafka or complex event streaming
- complex SOAR
- enterprise multi-tenancy
- full zero trust
- multiple external integrations
- a microservice architecture
- Kubernetes

These may come later, but they are not part of the initial foundation.

---

## 7. Initial Technical Stack

### Backend
- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- PostgreSQL
- Alembic
- JWT-based auth

### Frontend
- React
- TypeScript
- Vite

### DevOps / Infra
- Docker
- Docker Compose
- Prometheus
- Grafana

### Documentation
- Markdown in the repository
- incremental documentation, stage by stage

---

## 8. Repository Strategy

The project uses a **single repository (monorepo)** with a clear split by directory.

Base structure:

```text
sentinelcore/
├── backend/
├── frontend/
├── infra/
├── docs/
├── .github/
├── .gitignore
├── docker-compose.yml
└── README.md
```

### Motivation

This approach was chosen for:

- less overhead at the start
- simpler coordination between backend and frontend
- documentation in one place
- CI/CD that is easier to introduce gradually
- atomic changes across UI, API and infrastructure

---

## 9. Backend Structure Direction

The backend follows the modular monolith direction.

Target structure:

```text
backend/app/
├── api/
├── core/
├── models/
├── schemas/
└── services/
```

### Meaning of each layer
- `api/` - endpoints and routers
- `core/` - settings, security utilities, internal infrastructure
- `models/` - ORM models
- `schemas/` - input/output validation with Pydantic
- `services/` - business logic and orchestration

---

## 10. Current Project Status

The step-by-step history is in the journals ([01](01-backend-foundation.md), [03](03-frontend-foundation.md)). What exists today:

### Identity and sessions
- registration and login, with validated input: username length and characters, passwords of 12-128 characters; emails and usernames are case-insensitive
- concurrent duplicate registrations return `400`, not `500`
- login takes the same time whether or not the email exists
- the JWT identifies the user by id and the session by `jti`; `iss`, `aud` and `iat` are verified
- sessions are stored and revocable: logout, logout everywhere, revoking one session, signing out of the other devices
- old sessions are deleted periodically, after a configurable retention period
- the browser authenticates with an httpOnly cookie, with CSRF protection bound to the session; the Swagger **Authorize** button works through `POST /auth/token`
- inactive users are blocked at login and on authenticated endpoints; deactivating an account revokes all its sessions

### Authorization and administration
- RBAC with the roles `user`, `admin`, `security_analyst` and `owner`
- the user list has search, filters by role, status and lock, and cursor pagination; operators see each account's details and security history; the security analyst can read them
- only the owner changes roles; admins and the owner activate and deactivate accounts, hierarchically
- the security analyst can contain a suspicious account: close its sessions and temporarily lock its login, with a mandatory reason; admins and the owner can lift a lock before it expires
- nobody acts on their own account or on an owner
- administrative events record their target (`target_user_id`), and the affected user sees the actions taken on their account

### Audit and security events
- audit logs and security events record the client IP address
- both logs have cursor pagination and filters by type, severity, actor, target, email, IP and time range
- events are listed by the moment they happened, not by the order they were recorded
- viewing the logs and reading users are audited
- the first SIEM-light detection: repeated failed logins for the same email raise a `BRUTE_FORCE_DETECTED` incident and temporarily block login for that email
- a security summary (24 hours and 7 days, blocked logins, top failing IPs, accounts) feeds the organization overview

### Observability
- Prometheus metrics for HTTP and security events at `/metrics`, optionally behind a token
- structured logs, with a request id on every request
- `/health/ready` checks that the database is available
- Prometheus and Grafana run locally through Docker Compose, with the `SentinelCore Overview` dashboard provisioned automatically

### Frontend
- an "operations console" visual direction with the "Electric" palette, Tailwind CSS and shadcn/ui, React Router, TanStack Query, Romanian and English, dark and light themes
- login through an httpOnly cookie and protected routes
- two scopes:
  - **My account:** Overview (security summary and recent alerts), My sessions, My activity;
  - **Organization:** Security events and Audit log, with filters kept in the address and a details panel; Users, with search and filters, and a page per account with its history and the actions the operator may take; these pages load on demand

### Quality and delivery
- 284 backend tests, run against a separate PostgreSQL database (`sentinelcore_test`), and 147 frontend tests (Vitest with a mocked API)
- the schema is managed with Alembic; `alembic check` confirms the models and the database match
- the backend passes Pyright type checking with no errors
- backend CI on GitHub Actions: Ruff (lint and format), Bandit, pytest against a PostgreSQL service, and Gitleaks over the full Git history
- frontend CI: dependency audit, lint, type check, tests and build
- the workflows run with read-only repository permissions
- the repository is public under the MIT license; the local PostgreSQL listens on `localhost` only

---

## 11. Roadmap

The project grows toward a DevSecOps showcase, in phases:

- **A. Application:** the "Organization" scope (in progress), event ingestion with an API key, and detection rules mapped to MITRE ATT&CK.
- **B. Containers and local Kubernetes:** hardened images, a Helm chart on kind, migrations and session cleanup as Kubernetes jobs.
- **C. Supply chain CI:** SAST, dependency, IaC and image scanning, an SBOM, signed images and build provenance.
- **D. Infrastructure as code and GitOps:** Terraform, cloud access through OIDC, Argo CD with canary rollouts, preview environments.
- **E. Cluster security and operations:** admission policies, network policies, runtime detection, OpenTelemetry, SLO alerts, tested backups.
- **F. Presentation:** an architecture diagram, ADRs, a threat model, runbooks and a postmortem of a simulated incident.

---

## 12. Working Method

The project is built through **project-driven learning.**

Working rules:

- no large chunks of complete code without understanding them
- the foundation is never skipped
- learn only what the current step needs
- every stage is implemented, understood and documented
- problems are solved concretely, not worked around
- complexity is introduced gradually, never for decoration

---

## 13. Main Risks

The main risk of the project is not technical complexity, but:

- building without real understanding
- skipping the basics
- adding technologies just to impress
- inflating the architecture before the foundation is validated
- documentation written too late, or not at all

---

## 14. Project Standard

SentinelCore must be treated as a serious product, not as a lab exercise.

The standard it aims for:

- a clear structure
- reasoned decisions
- incremental implementation
- continuous documentation
- clean naming
- a logical separation of components
- a solid base for audit, security and observability

---

## 15. Immediate Next Step

The next step is the last page of the "Organization" scope, the Overview, on `GET /security/summary`: indicators over 24 hours and 7 days, recent incidents, and the sources with the most failures.

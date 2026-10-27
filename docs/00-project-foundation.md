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
- no public sign-up: the first owner is created from the command line (`python -m app.cli create-owner`), and every other account joins through an invitation from an admin or the owner, with a single-use token that expires, stored only as a hash; the person invited chooses their own password
- validated input: username length and characters, passwords of 12-128 characters; emails and usernames are case-insensitive
- concurrent duplicate accounts return a clear error, not `500`
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
- the audit log is sealed: each organization's records, and the platform's, form a chain in which every record carries an HMAC over its fields and the previous record's seal, keyed with `AUDIT_CHAIN_KEY`, which the database never holds; the cleanup task checks the chains and raises `audit_chain_broken` (T1070) on the platform for a changed, missing or truncated record, and `python -m app.cli verify-audit-chain` checks them on demand
- the first SIEM-light detection: repeated failed logins for the same email raise a `BRUTE_FORCE_DETECTED` incident and temporarily block login for that email
- failed sign-ins are also limited per address, whatever email they try (20 at once, then 6 an hour by default); an address over the limit gets the lockout's own answer before its password is checked, and the owner sees one `login_address_limited` event (T1110) when it is reached
- a detection engine runs rules mapped to MITRE ATT&CK on every recorded event, and only alerts: password spray (T1110.003, failed sign-ins for many emails from one address), the same spray split across organizations (T1110.003, the platform's, seen by the owner only), a sign-in to a dormant account (T1078), a sign-in from a network and a device the account has not used (T1078), a privileged role granted (T1098), by a role change or an invitation, and an API key sending far more than usual within an hour (T1499); every detection names its technique
- a security summary (24 hours and 7 days, hour by hour and day by day, alerts per MITRE ATT&CK technique, a threat level, blocked logins, top failing IPs, accounts) feeds the organization overview and a threat status band above every organization page
- other systems send sign-ins through `POST /ingest/events` with an API key issued by the owner; keys expire, can be revoked, and are stored only as hashes; ingested events keep the time they happened and go through the same detection rules, but never lock anyone out of this application; each key has a rate limit (5,000 events at once, then 1,000 a minute by default), over which a batch is refused whole with `429` and `Retry-After`; a key that sends, within one hour, three times its usual busiest hour raises an alert (T1499)
- `make demo` builds a separate database with ninety days of three synthetic organizations (one attacked, one quiet, one quiet and suspended) and serves the app on it
- an attack simulator (`backend/simulator/`) plays a synthetic organization's routine, five attacks per rule and five of each evasive variant against a running instance, and reports detection rate, false positives, time to detect and what passes unseen in `docs/evaluation/`

### Observability
- Prometheus metrics for HTTP and security events at `/metrics`, optionally behind a token
- structured logs, with a request id on every request
- `/health/ready` checks that the database is available
- Prometheus and Grafana run locally through Docker Compose, with the `SentinelCore Overview` dashboard provisioned automatically

### Browser protection
- every API answer carries a Content Security Policy that lets nothing run, load or frame it, with `nosniff`, `X-Frame-Options`, `Referrer-Policy` and `Cache-Control: no-store`. The API's documentation (Swagger UI, ReDoc and the schema) is off unless `API_DOCS_ENABLED` turns it on for development; its pages then allow only Swagger UI's and ReDoc's packages, and Swagger UI's inline script by its hash. HSTS is sent once `HSTS_MAX_AGE` is set
- the console's build runs only its own scripts and cannot be framed by another site; the policy was checked in Firefox on every page

### Frontend
- a sober monitoring-tool look (neutral greys, one blue accent, colour for severity only, Public Sans, a shield-and-eye logomark), Tailwind CSS and shadcn/ui, React Router, TanStack Query, Romanian and English, light and dark themes following the system
- login through an httpOnly cookie and protected routes
- two scopes:
  - **My account:** Overview (security summary and recent alerts), My sessions, My activity;
  - **Organization** (named after the member's organization; **Platform** for the owner, with an organization picker that applies to every page, an organization column while viewing all, the organizations ranked by threat level and an Organizations page to create, rename, suspend and reactivate them): an Overview (incidents, warnings and informational events over 24 hours and 7 days, failed sign-ins and the addresses behind them, locked and deactivated accounts, the latest incidents); Security events and Audit log, with filters kept in the address and a details panel; Users, with search and filters, and a page per account with its history and the actions the operator may take; API keys, listed for every operator, issued and revoked by the owner, with a new key shown once; detections carry their MITRE ATT&CK technique, linked to its page; these pages load on demand

### Quality and delivery
- 591 backend tests, run against a separate PostgreSQL database (`sentinelcore_test`) built by the migrations, and 243 frontend tests (Vitest with a mocked API)
- the schema is managed with Alembic; `alembic check` confirms the models and the database match
- the backend passes Pyright type checking with no errors
- backend CI on GitHub Actions: Ruff (lint and format), Bandit, pytest against a PostgreSQL service, and Gitleaks over the full Git history
- frontend CI: dependency audit, lint, type check, tests and build
- the workflows run with read-only repository permissions
- the repository is public under the MIT license; the local PostgreSQL listens on `localhost` only

---

## 11. Roadmap

The project grows toward a DevSecOps showcase, in phases:

- **A. Application:** the "Organization" scope (done), event ingestion with an API key, detection rules mapped to MITRE ATT&CK, and an attack simulator that measures them.
- **B. Containers and local Kubernetes:** hardened images, Helm charts on kind, the migrations as a Kubernetes Job (the session cleanup stays in the API).
- **C. Supply chain CI (C1 done (#45), C2 done (#51), C3 done (#60, #63)):** SAST, dependency, IaC and image scanning, an SBOM, signed images and build provenance.
- **D. Infrastructure as code and GitOps:** Terraform, cloud access through OIDC, Argo CD with canary rollouts, preview environments.
- **E. Cluster security and operations (E1 done):** admission policies, network policies, runtime detection, OpenTelemetry, SLO alerts, tested backups.
- **F. Presentation:** an architecture diagram, ADRs, runbooks and a postmortem of a simulated incident. The threat model was written earlier ([04](04-threat-model.md)) and grows with each phase.

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

The attack simulator measures the detection rules (`docs/evaluation/report.md`): on its synthetic organization, 30 of 30 attacks detected and 3 false positives, each a benign case the rules' design cannot tell from an attack. Four evasive variants (a slow spray, a distributed spray, a copied user agent, an account idle for just under the dormancy threshold) all pass, 0 of 20, and the report gives the reason for each: these are the rules' known limits. API keys and MITRE ATT&CK techniques are in the interface, which closes phase A. Public sign-up was then replaced by invitations, and the interface got its own visual identity and a command palette (Ctrl+K). A threat status band, seven-day trends and alerts per technique followed. Invitations now have their interface: operators invite from the Users page, and the person invited creates the account at `/invite`. `make demo` now builds a separate database with ninety days of a synthetic organization, its attacks spread across that history, and serves the app on it. SentinelCore is becoming multi-organization, in five stages: every record belongs to an organization, which the platform owner creates, renames and suspends, and every read is now limited to the caller's organization, with a record of another one answering as a missing one and detection counting within each. PostgreSQL row-level security now holds the same boundary in the database: the API signs in as its own role, which sees one organization's rows unless the request says otherwise, and cannot rewrite security events or the audit log. The interface now shows it: the platform owner sees a "Platform" scope with an Organizations page (create, rename, suspend after typing the slug, reactivate), one organization picker for every page, an organization column while viewing all of them and the organizations ranked by threat level on the overview; members see their own organization's name. `make demo` now shows three organizations: Acme, attacked across its ninety days; Globex, quiet; and Initech, quiet and suspended at the end, with each admin's password written locally to sign in as them. Multi-organization support is complete. The STRIDE threat model ([04](04-threat-model.md)) now lists 60 threats across ten elements of the system, each with its mitigation and the test that proves it, and the boundary between organizations as the main trust boundary; no threat is rated high. The first of the five residual risks it names is closed: the API, its documentation pages and the console's build send a Content Security Policy and the usual security headers, so an injected script does not run and no other site can frame the console. The API's documentation pages and schema are now off unless a setting turns them on for development, which keeps their code from a CDN away from the console's session elsewhere. The second residual risk, misuse of a valid ingestion key, is closed: each key has a rate limit, a token bucket kept in the database, so a stolen key can no longer flood the API, and an hour in which a key sends three times its usual busiest hour raises an alert (T1499). Fake events at a key's usual volume still pass, and a key that falls silent is not yet noticed. The fifth, sign-in abuse from one address, is closed too: failed sign-ins are limited per address, 20 at once and then 6 an hour, so one address can no longer spray a password across every account or keep a victim's email locked; sprays and lockouts spread over many addresses still pass. The third, attacks spread across organizations, is closed for this application's own sign-in: one platform rule, seen by the owner only, counts failed sign-ins from one address across every organization and raises an incident (T1110.003) when ten emails in 15 minutes come from at least two places; the simulator now plays five such sprays and catches all of them, 30 of 30 attacks in all. Sprays split across organizations in ingested logs still pass. The fourth, history editable by the owner of the tables, is closed for the audit log: every audit record is sealed with an HMAC over its fields and the record before it, one chain per organization and one for the platform, keyed with a secret the database never holds; the cleanup task checks the chains, raises an incident (T1070) when one is broken and writes their lengths and heads to the log and metrics, and a command checks them on demand. Security events are not sealed yet. All five residual risks of the threat model are now addressed. Phase B has begun: the backend and the console now have hardened images, both non-root with read-only filesystems, on base images pinned by digest, the backend's dependencies pinned by hash, and the console served by nginx with the same security headers as before, the client's real address passed on, metrics kept inside and a first limit on ingestion floods. `make verify` runs every check due before a commit in one command. `make up` now runs SentinelCore on a local kind cluster at `http://localhost:8080`, from two Helm charts (PostgreSQL, then the application, its migrations first as a Job): the secrets are generated once as Kubernetes Secrets and never printed, the first owner is created with its password in a local file, every pod runs as a user other than root with a read-only filesystem, no capabilities and no Kubernetes token, and only the migration Job holds the owner of the tables' credentials; `make cluster-check` checks these properties on the running cluster. Phase B is complete: CI lints the charts, validates the rendered manifests against Kubernetes' schemas and lints the Dockerfiles and scripts on every pull request, and builds the cluster with `make up` and runs `make cluster-check` on it whenever the deployment changes; the threat model now covers the cluster, with 65 threats across eleven elements. Phase C has started, with C1 done (#45) and C2 done (#51): actions, tools and development images pinned, Dependabot with a seven-day cooldown, CodeQL and weekly dependency and configuration scans through `make scan`, with expiring exceptions; C2 adds SPDX SBOMs, image vulnerability scans and publication of the scanned images to GHCR under 12-character commit tags, with weekly rescans. C3 (#60, #63) signs every published image with cosign (keyless, through Sigstore) and attests its SLSA v1 build provenance (Build Level 2) and its SBOM; `make up FROM=registry` runs the cluster on the commit's published images only after checking all three against exact identities, and refuses otherwise. The first signed images, from `5bb9867`, pass these checks, and another workflow, ref, issuer, commit, predicate type or repository is refused. Phase C is complete. The threat model has 71 threats. `make screenshots` now takes four pictures of the console from a running `make demo`. The interface was then redesigned in three steps as a sober monitoring tool (neutral greys, one blue accent, colour only for severity), and the README shows the four pictures. Phases D, E and F are planned to the end of 2026, in the order E, D1 (local GitOps), F, then D2 (Azure). E1 is done: the cluster refuses, at admission, any pod in SentinelCore's namespace that runs as root, can gain privileges, writes to its root filesystem, lacks limits, mounts a Kubernetes token or names an image without a digest, and with `make up FROM=registry` any SentinelCore image not signed and attested by its CI. Next: E2, network policies.

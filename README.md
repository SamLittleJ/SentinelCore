# SentinelCore

An API-first platform for identity and access management, audit logging and security event monitoring (SIEM-light), built as a modular monolith.

## Repository layout

```text
.
├── backend/              # FastAPI API, SQLAlchemy models, Alembic migrations, tests
├── frontend/             # web app (React, TypeScript, Vite, Tailwind CSS, shadcn/ui)
├── docs/                 # project documentation, by stage, and the detection evaluation
├── infra/                # Prometheus and Grafana configuration
├── .github/workflows/    # backend CI (Ruff, Bandit, pytest, Gitleaks) and frontend CI
└── docker-compose.yml    # PostgreSQL, Prometheus and Grafana for local development
```

## Quick start

Requirements: Docker, Python 3.12+, Node.js (frontend only).

```bash
# Local PostgreSQL and a separate database for tests
docker compose up -d
docker exec sentinelcore-postgres createdb -U sentinelcore sentinelcore_test

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
python -m app.cli create-owner --email owner@example.com --username owner
python -m uvicorn app.main:app --reload
```

`create-owner` asks for the owner's password and creates the organization's first account. There is no public sign-up: the owner and admins invite everyone else.

The API runs at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`. PostgreSQL listens on `localhost` only, because the development password in `docker-compose.yml` is public.

Frontend, in another terminal:

```bash
cd frontend
npm install
npm run dev
```

The web app runs at `http://localhost:5173`. Details: [frontend/README.md](frontend/README.md).

In Swagger UI, the **Authorize** button takes the email in the `username` field, plus the password.

## Monitoring

```bash
docker compose up -d prometheus grafana
```

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (user `admin`, password `sentinelcore`, local only), dashboard **SentinelCore Overview**

Prometheus scrapes the backend running locally on port 8000. The services use host networking, which is fully supported on Linux.

Backend, tests and checks: [backend/README.md](backend/README.md).

## Documentation

- [00 - Project Foundation](docs/00-project-foundation.md): purpose, architecture, roles, MVP and current status
- [01 - Backend Foundation](docs/01-backend-foundation.md): the technical journal of every backend stage
- [02 - Decisions Log](docs/02-decisions-log.md): the technical decisions made along the way
- [03 - Frontend Foundation](docs/03-frontend-foundation.md): the technical journal of the frontend
- [Detection evaluation](docs/evaluation/report.md): detection rate, false positives and time to detect, measured by the attack simulator

## License

[MIT](LICENSE)

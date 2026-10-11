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

`create-owner` asks for the owner's password and creates the organization's first account. There is no public sign-up: the owner and admins invite everyone else from the Users page, and the person invited picks a username and a password at `/invite`.

The API runs at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`. PostgreSQL listens on `localhost` only, because the development password in `docker-compose.yml` is public.

Frontend, in another terminal:

```bash
cd frontend
npm install
npm run dev
```

The web app runs at `http://localhost:5173`. Details: [frontend/README.md](frontend/README.md).

In Swagger UI, the **Authorize** button takes the email in the `username` field, plus the password.

## Demo

One command shows SentinelCore with ninety days of a synthetic organization behind it:

```bash
make demo
```

It needs the Quick start done once (Docker, `backend/.venv` with `backend/.env`, `npm install` in `frontend/`), the `make` tool, and ports 8000 and 5173 free. It then:

1. starts PostgreSQL and recreates a separate `sentinelcore_demo` database, leaving the development one alone;
2. creates the owner `owner@sim.example.com` with a random password, written only to `.demo/owner.txt` (readable by you alone, ignored by git) and never printed;
3. fills ninety days, ending now, through the API: 36 people joining by invitation, an admin and an analyst, their routine sign-ins reported by a VPN key, and the attack simulator's attacks spread across the days at random hours (password sprays, stolen passwords used on dormant accounts and from unknown places, and the evasive variants the rules miss);
4. plays today's events live: brute force against two accounts, an admin role granted, and the operators' response (sessions closed, an account locked, the dormant accounts deactivated, a promotion, new invitations, a retired API key);
5. runs the backend and the frontend until Ctrl+C. Open `http://localhost:5173` and sign in with the details in `.demo/owner.txt`.

Each run starts from scratch with the same seed, so the organization and its history are the same, shifted to end at the time of the run. `make demo-clean` removes the database and `.demo/`.

What to know about the data:

- Everything is synthetic, made by `backend/simulator` from one seed. Email addresses use `sim.example.com`, and network addresses come from documentation ranges.
- Accounts, invitations and operator actions go through the API at the time of the run, so the accounts show today as their joining date and today's log holds them all. Their sign-ins go back ninety days.
- Alerts raised from the history are moved, in the demo database only, to the time of the event that raised them plus a few seconds, as if SentinelCore had watched the ninety days live. Without this, every one of them would carry the time of the run. The application itself always keeps the detection time.

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

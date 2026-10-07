# SentinelCore

Platformă API-first pentru Identity and Access Management, audit logging și monitorizarea evenimentelor de securitate (SIEM-light), construită ca monolit modular.

## Structura repository-ului

```text
.
├── backend/              # API FastAPI, modele SQLAlchemy, migrații Alembic, teste
├── frontend/             # aplicația web (React, TypeScript, Vite, Tailwind CSS, shadcn/ui)
├── docs/                 # documentația proiectului, pe etape
├── infra/                # configurație Prometheus și Grafana
├── .github/workflows/    # CI backend (Ruff, Bandit, pytest, Gitleaks) și frontend
└── docker-compose.yml    # PostgreSQL, Prometheus și Grafana pentru development local
```

## Pornire rapidă

Cerințe: Docker, Python 3.12+, Node.js (doar pentru frontend).

```bash
# PostgreSQL local și baza de date separată pentru teste
docker compose up -d
docker exec sentinelcore-postgres createdb -U sentinelcore sentinelcore_test

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

API-ul rulează la `http://localhost:8000`, iar documentația interactivă la `http://localhost:8000/docs`. PostgreSQL ascultă doar pe `localhost`, pentru că parola de development din `docker-compose.yml` este publică.

Frontend, într-un alt terminal:

```bash
cd frontend
npm install
npm run dev
```

Aplicația web rulează la `http://localhost:5173`. Detalii: [frontend/README.md](frontend/README.md).

În Swagger UI, butonul **Authorize** cere emailul în câmpul `username` și parola.

## Monitorizare

```bash
docker compose up -d prometheus grafana
```

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (user `admin`, parola `sentinelcore`, doar local), dashboard-ul **SentinelCore Overview**

Prometheus colectează metricile backend-ului pornit local pe portul 8000. Serviciile folosesc host networking, suportat complet pe Linux.

Detalii despre backend, teste și verificări: [backend/README.md](backend/README.md).

## Documentație

- [00 - Project Foundation](docs/00-project-foundation.md): scop, arhitectură, roluri, MVP și stadiul curent
- [01 - Backend Foundation](docs/01-backend-foundation.md): jurnalul tehnic al fiecărei etape din backend
- [02 - Decisions Log](docs/02-decisions-log.md): deciziile tehnice luate pe parcurs
- [03 - Frontend Foundation](docs/03-frontend-foundation.md): jurnalul tehnic al frontend-ului

## Licență

[MIT](LICENSE)
